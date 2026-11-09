"""Shared set-up for the chatbot tests: the real app (data, search, photo model) in this process, with
  * corrections written to a temporary folder (data/feedback is never touched),
  * no rate limit (the tests send many requests in a minute).
Every test's outcome and time is written to tests/last_run.json (used by docs/testing-report.md).

Run (from the project folder; loading the data takes ~30-60 s):
    venv/bin/python -m pytest tests -q                 # everything (needs internet: Gemini, OpenStreetMap)
    venv/bin/python -m pytest tests -q -m "not network" # only what runs offline
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
RESULTS = []


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs the internet (an AI model or OpenStreetMap)")


@pytest.fixture(scope="session")
def client():
    from food_search import api, dishes, search
    tmp = Path(tempfile.mkdtemp(prefix="kn-tests-"))
    dishes.FEEDBACK_DIR = tmp
    dishes.CORRECTIONS_PATH = tmp / "corrections.jsonl"
    dishes.VECTORS_PATH = tmp / "vectors.pt"
    dishes.TEXT_CORRECTIONS_PATH = tmp / "text_corrections.jsonl"
    search.init()
    api.allow_request = lambda key: True
    from fastapi.testclient import TestClient
    return TestClient(api.create_app())


@pytest.fixture(scope="session")
def chat(client):
    """chat(query, **fields) -> the /api/chat answer (dict)."""
    def ask(query, **fields):
        r = client.post("/api/chat", json={"query": query, **fields})
        assert r.status_code == 200, r.text
        return r.json()
    return ask


@pytest.fixture(scope="session")
def conversation(client):
    """conversation([q1, q2, ...]) -> the answers, sent the way the web app sends them (history, shown places,
    last search, dish in focus, last photo)."""
    def run(turns, model=None):
        hist, ctx, last, dish, answers = [], [], None, None, []
        for q in turns:
            body = {"query": q, "history": hist[-12:], "context_ids": ctx, "last_query": last, "dish_id": dish,
                    "model": model}
            d = client.post("/api/chat", json=body).json()
            if d.get("need_location"):
                d = client.post("/api/chat", json={"query": d["search_query"], "direct": True, "no_location": True,
                                                   "model": model}).json()
            places = "; ".join(f"{i}. {p['name']}" for i, p in enumerate((d.get("results") or [])[:5], 1))
            hist += [{"role": "user", "text": q},
                     {"role": "assistant", "text": f"{d.get('answer') or ''} Places shown: {places}"[:1000]}]
            if d.get("kind") not in ("followup", "chat") and d.get("results"):
                ctx, last = [p["id"] for p in d["results"][:10]], d.get("search_query") or q
            dish = (d.get("dish") or {}).get("id", dish)
            answers.append(d)
        return answers
    return run


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        RESULTS.append({"test": item.nodeid.split("::", 1)[1], "category": item.cls.__doc__.split("\n")[0] if item.cls else "",
                        "outcome": report.outcome, "seconds": round(report.duration, 3)})


def pytest_sessionfinish(session, exitstatus):
    if RESULTS:
        (ROOT / "tests" / "last_run.json").write_text(json.dumps(
            {"run": time.strftime("%Y-%m-%d %H:%M"), "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
