"""
Review what users taught the app (data/feedback/, written by backend/food_search/dishes.py).

Three kinds of corrections:
  photo  A wrong dish guess, corrected with the "Not it?" buttons, "no, it's amok" or "/correction amok".
         The photo is saved in data/feedback/photos/<dish>/ (corrections.jsonl). From then on the app answers that
         photo (sent again) with the corrected dish, and food_classification.ipynb trains on these photos next time.
  new    A photo of a dish the app does not know yet ("/correction bai cha"): saved in data/feedback/photos/_new/
         (new_dishes.jsonl), for when that dish is added to the training data.
  text   A wrong text answer ("/correction this place closed last year"): saved with the question and the answer
         (text_corrections.jsonl). Shown to the same user when they ask that question again, and to everyone once
         approved here (--approve).
Corrections can be wrong (a joke, a mis-tap): look at them here and remove the bad ones. The running app picks up a
change by itself (it re-reads the files).

Usage:
    python scrapers/feedback_review.py                 # summary
    python scrapers/feedback_review.py --list          # every correction with its id
    python scrapers/feedback_review.py --open          # open the corrected photos in Finder / the file viewer
    python scrapers/feedback_review.py --approve ID    # show a text correction to everyone
    python scrapers/feedback_review.py --remove ID     # remove a correction (and its photo)
"""
import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDBACK = ROOT / "data" / "feedback"
CORRECTIONS = FEEDBACK / "corrections.jsonl"
NEW_DISHES = FEEDBACK / "new_dishes.jsonl"
TEXT = FEEDBACK / "text_corrections.jsonl"


def read(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path, rows):
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in rows), encoding="utf-8")
    tmp.replace(path)


def summary(photos, new, texts):
    if not (photos or new or texts):
        print("No corrections yet.")
        return
    if photos:
        by_dish = defaultdict(list)
        for e in photos:
            by_dish[e["dish"]].append(e)
        print(f"Photo corrections: {len(photos)}, {len(by_dish)} dishes, "
              f"{len({e['user'] for e in photos if e['user']})} different people "
              f"({', '.join(f'{k}: {v}' for k, v in Counter(e['channel'] for e in photos).items())})\n")
        print(f"{'dish':28s} {'photos':>6s}  {'people':>6s}  the model had said")
        for dish, es in sorted(by_dish.items(), key=lambda kv: -len(kv[1])):
            guesses = Counter(e["guess"] for e in es).most_common(3)
            print(f"{dish:28s} {len(es):6d}  {len({e['user'] for e in es}):6d}  "
                  + ", ".join(f"{g} ×{n}" for g, n in guesses))
    if new:
        print("\nDishes the app does not know yet (photos in data/feedback/photos/_new/):")
        for name, n in Counter(e["name"].lower() for e in new).most_common():
            print(f"  {name}: {n} photo{'s' if n > 1 else ''}")
    if texts:
        waiting = sum(not e["approved"] for e in texts)
        print(f"\nText corrections: {len(texts)} ({waiting} waiting for review: see --list, then --approve or --remove)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show every correction")
    ap.add_argument("--open", action="store_true", help="open the photos folder")
    ap.add_argument("--approve", metavar="ID", help="show a text correction to everyone")
    ap.add_argument("--remove", metavar="ID", help="remove a correction (its id or its photo id) and its photo")
    args = ap.parse_args()
    photos, new, texts = read(CORRECTIONS), read(NEW_DISHES), read(TEXT)

    if args.approve:
        hit = [e for e in texts if e["id"] == args.approve]
        if not hit:
            sys.exit(f"No text correction with id {args.approve} (see --list).")
        for e in hit:
            e["approved"] = True
            print(f"approved {e['id']}: “{e['question']}” -> {e['correction']}")
        write(TEXT, texts)
        return

    if args.remove:
        removed = 0
        for path, rows in ((CORRECTIONS, photos), (NEW_DISHES, new), (TEXT, texts)):
            gone = [e for e in rows if args.remove in (e["id"], e.get("photo"))]
            for e in gone:
                if e.get("file"):
                    (FEEDBACK / e["file"]).unlink(missing_ok=True)
                what = e.get("dish") or e.get("name") or f"“{e.get('correction')}”"
                print(f"removed {e['id']}: {e.get('guess') or e.get('question')} -> {what}")
            if gone:
                write(path, [e for e in rows if e not in gone])
                removed += len(gone)
        if not removed:
            sys.exit(f"No correction with id {args.remove} (see --list).")
        return

    if args.list:
        for e in photos:
            print(f"{e['id']}  {e['time']}  {e['channel']:8s}  photo  {e['guess']} ({e['confidence']:.0%}) -> {e['dish']}"
                  f"  data/feedback/{e['file']}")
        for e in new:
            print(f"{e['id']}  {e['time']}  {e['channel']:8s}  new    {e['guess']} -> \"{e['name']}\""
                  f"  data/feedback/{e['file']}")
        for e in texts:
            state = "approved" if e["approved"] else "waiting"
            print(f"{e['id']}  {e['time']}  {e['channel']:8s}  text   [{state}] “{e['question']}”\n"
                  f"{'':14s}answer: {e['answer'][:160]}\n{'':14s}correction: {e['correction']}")
        return

    summary(photos, new, texts)
    if args.open and (FEEDBACK / "photos").exists():
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(FEEDBACK / "photos")])


if __name__ == "__main__":
    main()
