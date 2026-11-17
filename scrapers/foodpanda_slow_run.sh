#!/bin/zsh
# The slow Foodpanda detail run (started 16 Nov 2026): one page every ~200 s (Foodpanda allows ~20 pages an hour; faster
# gets 403), central districts first. The scraper ends after 4 refusals in a row; this loop waits 2 hours and resumes
# (finished pages are skipped), and stops when nothing is left. caffeinate keeps the Mac from sleeping meanwhile.
# Stop it with: pkill -f foodpanda_slow_run.sh; pkill -f foodpanda_detail_scraper
cd "$(dirname "$0")/.." || exit 1
while true; do
  caffeinate -i venv/bin/python scrapers/foodpanda_detail_scraper.py --city "Phnom Penh" --central-first --pause 200 | tee -a data/scraped/foodpanda_slow_run.log
  tail -40 data/scraped/foodpanda_slow_run.log | grep -q " 0 to fetch" && break
  sleep 7200
done
