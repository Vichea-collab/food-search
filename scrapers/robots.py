"""
Polite crawling for every scraper: read the site's robots.txt before downloading a page, skip what it disallows,
and keep the site's requested gap between two requests (Crawl-delay / Request-rate).

    import robots
    r = robots.get(url, headers=HEADERS, timeout=20)                  # instead of requests.get(...)
    r = robots.get(url, session=sess, timeout=20)                     # instead of sess.get(...)

robots.txt is read once per site and kept for the run. How a missing or broken robots.txt is treated follows
RFC 9309 (the robots.txt standard):
  - 2xx: its rules apply
  - 4xx (404 not found, 403, ...): no rules, every page may be fetched
  - 5xx or no answer: the site is treated as fully disallowed, and robots.txt is asked again after RETRY_S
A disallowed page raises Disallowed. It is a requests.RequestException, so a scraper's existing
"except requests.RequestException" skips that page like any other failed download.

    python scrapers/robots.py https://food.grab.com/kh/en/          # check one address
"""
import logging
import sys
import threading
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

AGENT = "KleanNhamBot"     # the name matched against "User-agent:" lines (rules for "*" apply when none names it)
ROBOTS_TIMEOUT_S = 15
RETRY_S = 600              # an unreadable robots.txt (5xx / no answer) is asked again after 10 minutes

_rules: dict = {}          # "https://host" -> (RobotFileParser, time.monotonic() after which it is read again)
_last: dict = {}           # "https://host" -> time.monotonic() of the last request
_lock = threading.Lock()


class Disallowed(requests.RequestException):
    """The site's robots.txt does not allow this page (or robots.txt could not be read: 5xx / no answer)."""


def _site(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def rules(url: str) -> urllib.robotparser.RobotFileParser:
    """The robots.txt rules of the site that `url` is on (downloaded on first use, then kept)."""
    site = _site(url)
    with _lock:
        if site in _rules and time.monotonic() < _rules[site][1]:
            return _rules[site][0]
    rp = urllib.robotparser.RobotFileParser(site + "/robots.txt")
    keep = float("inf")                # rules that were read are kept for the whole run
    try:
        r = requests.get(site + "/robots.txt", timeout=ROBOTS_TIMEOUT_S,
                         headers={"User-Agent": f"Mozilla/5.0 (compatible; {AGENT}/1.0)"})
        if r.status_code >= 500:
            rp.disallow_all, keep = True, RETRY_S
            note = f"robots.txt answered {r.status_code}: nothing is fetched from this site for now"
        elif r.status_code >= 400:
            rp.allow_all = True
            note = f"no robots.txt ({r.status_code}): no rules"
        else:
            rp.parse(r.text.splitlines())
            note = "robots.txt read"
    except requests.RequestException as e:
        rp.disallow_all, keep = True, RETRY_S
        note = f"robots.txt could not be read ({type(e).__name__}): nothing is fetched from this site for now"
    rp.modified()                      # marks the rules as read (can_fetch() refuses everything before that)
    print(f"[robots] {site}: {note}" + (f", crawl delay {delay(url, rp):g} s" if delay(url, rp) else ""), flush=True)
    with _lock:
        _rules[site] = (rp, time.monotonic() + keep)
    return rp


def allowed(url: str) -> bool:
    """True when robots.txt lets this scraper download `url`."""
    return rules(url).can_fetch(AGENT, url)


def delay(url: str, rp=None) -> float:
    """Seconds the site asks for between two requests (Crawl-delay, or Request-rate as pages/seconds), 0 = none."""
    rp = rp or rules(url)
    d = rp.crawl_delay(AGENT)
    if d:
        return float(d)
    rate = rp.request_rate(AGENT)
    return rate.seconds / rate.requests if rate and rate.requests else 0.0


def wait_turn(url: str, min_pause: float = 0.0) -> None:
    """Sleeps until at least max(the site's delay, min_pause) seconds have passed since the last request to it."""
    gap = max(delay(url), min_pause)
    site = _site(url)
    with _lock:
        last = _last.get(site)
    if last is not None and gap:
        left = gap - (time.monotonic() - last)
        if left > 0:
            time.sleep(left)
    with _lock:
        _last[site] = time.monotonic()


def get(url: str, session=None, min_pause: float = 0.0, **kwargs) -> requests.Response:
    """requests.get / session.get, but only when robots.txt allows the page, and after the site's delay."""
    if not allowed(url):
        log.info("robots.txt disallows %s: skipped", url)
        raise Disallowed(f"robots.txt does not allow {url}")
    wait_turn(url, min_pause)
    return (session or requests).get(url, **kwargs)


if __name__ == "__main__":
    for u in sys.argv[1:] or ["https://www.foodpanda.com.kh/restaurant/x", "https://food.grab.com/kh/en/"]:
        print(f"{u}: {'allowed' if allowed(u) else 'NOT allowed'}, delay {delay(u):g} s")
