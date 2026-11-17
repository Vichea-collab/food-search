"""
Add the harvested, verified photos (data/khfood/harvested, scrapers/verify_harvested_images.py) of the 26 photo-model
dishes to data/khfood/combined as EXTRA TRAINING photos:

  combined/images/<dish>/<harvested file name>.jpg      the photo is copied there
  combined/meta/train_plus.txt                           train.txt + the new photos

train.txt and test.txt are NOT changed. The test photos stay the same, so a model trained on train_plus.txt can be compared
with the earlier ones on exactly the same test set (scrapers/khfood_build.py would split everything again at random, and
the old and new scores could no longer be compared). The verify step already dropped every harvested photo that is a
near-copy (CLIP cosine >= 0.93) of a photo in combined, test photos included.
Only photos that the verify report keeps are added; dishes that are not photo-model classes are left alone.

    venv/bin/python scrapers/merge_harvested_into_khfood.py
    venv/bin/python scrapers/train_khmer_finetune.py --base <checkpoint> --khmer-train train_plus --out <new checkpoint>
"""
import csv
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KH = ROOT / "data" / "khfood"
META = KH / "combined" / "meta"


def main():
    classes = {l.strip() for l in open(META / "classes.txt") if l.strip()}
    train = [l.strip() for l in open(META / "train.txt") if l.strip()]
    test = {l.strip() for l in open(META / "test.txt") if l.strip()}
    added, per = [], Counter()
    for r in csv.DictReader(open(KH / "verify_report.csv", encoding="utf-8")):
        dish, stem = r["dish_id"], Path(r["file"]).stem
        src = KH / "harvested" / r["file"]
        if r["decision"] != "KEEP" or dish not in classes or not src.exists():
            continue
        dst = KH / "combined" / "images" / dish / f"{stem}.jpg"
        if not dst.exists():
            shutil.copy2(src, dst)
        entry = f"{dish}/{stem}"
        assert entry not in test, entry
        added.append(entry)
        per[dish] += 1
    out = META / "train_plus.txt"
    out.write_text("\n".join(train + sorted(set(added) - set(train))) + "\n")
    print(f"train.txt {len(train)} + {len(set(added) - set(train))} harvested = {out.name}; test.txt unchanged ({len(test)})")
    for dish, n in per.most_common():
        print(f"  {dish:22} +{n}")


if __name__ == "__main__":
    main()
