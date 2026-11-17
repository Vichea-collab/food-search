"""
Make more of the harvested Khmer dishes classes of the photo model (they have photos, a description and a recipe, but the
classifier did not know them).

A dish needs enough photos to be learned AND tested: --min-photos (default 45 kept photos) leaves 9 of the 34. The rest
(a dozen photos or fewer) stay "unknown to the photo model" until more photos exist. --skip leaves out dishes whose
photos are too mixed to label by eye (cha houy teuk and num plae ai: about half of the checked test candidates were
another dessert; the CLIP check cannot tell Khmer desserts apart). The training photos of the new dishes must also be
among the --max-rank closest dishes for CLIP (measured on the checked candidates: keeps 79% of the right photos,
drops 58% of the wrong ones), and --train-sheets lets you look at the rest of a dish and list the wrong ones in
data/khfood/new_dish_bad_train.txt.

Two steps, because the test photos must be right (the harvest is ~25% noisy, a wrong test photo makes the score lie):

  1. venv/bin/python scrapers/add_harvested_dishes.py --sheets DIR
       picks --test-per-dish random candidate test photos per new dish (seeded, fixed) and writes contact sheets
       DIR/<dish>_<n>.jpg with a number on every photo. Look at them and write the numbers of the photos that are NOT the
       dish (another dish, a person, a video thumbnail, a drawing) into data/khfood/new_dish_bad_test.txt, one "dish number" per line.
  2. venv/bin/python scrapers/add_harvested_dishes.py --apply
       copies all kept photos into data/khfood/combined/images/<dish>/, then writes in data/khfood/combined/meta
         train_plus2.txt  train_plus.txt + the other kept photos of the new dishes
         test_plus.txt    test.txt (the 337 photos every earlier model was scored on) + the checked test photos of the new dishes
       and models/food101_classes_plus.json (the 127 classes + the new ones; the live class file is NOT changed).
  Then: train_khmer_finetune.py --classes models/food101_classes_plus.json --khmer-train train_plus2 --khmer-test test_plus

train.txt, train_plus.txt and test.txt are never changed.
"""
import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KH = ROOT / "data" / "khfood"
META = KH / "combined" / "meta"
BAD = KH / "new_dish_bad_test.txt"
BAD_TRAIN = KH / "new_dish_bad_train.txt"
SKIP = {"kh_cha_houy_teuk", "kh_num_plae_ai"}


def kept_by_dish():
    out = defaultdict(list)
    for r in csv.DictReader(open(KH / "verify_report.csv", encoding="utf-8")):
        if r["decision"] == "KEEP" and (KH / "harvested" / r["file"]).exists():
            out[r["dish_id"]].append(Path(r["file"]).name)
    return {d: sorted(v) for d, v in out.items()}


def new_dishes(min_photos, skip=SKIP):
    known = {c["id"] for c in json.load(open(ROOT / "models" / "food101_classes.json", encoding="utf-8"))}
    return {d: v for d, v in sorted(kept_by_dish().items()) if d not in known and d not in skip and len(v) >= min_photos}


def test_candidates(files, n, dish):
    return random.Random(f"test-{dish}").sample(files, min(n, len(files)))


def ranks():
    return {r["file"]: int(r["dish_rank"]) for r in csv.DictReader(open(KH / "verify_report.csv", encoding="utf-8"))}


def train_pool(dish, files, n, max_rank):
    """the photos of a dish that are not test candidates and pass the CLIP rank test (stable order = the sheet numbers)"""
    rk, cand = ranks(), set(test_candidates(files, n, dish))
    return [f for f in files if f not in cand and rk[f"{dish}/{f}"] <= max_rank]


def read_bad(path):
    bad = defaultdict(set)
    if path.exists():
        for line in path.read_text().splitlines():
            m = re.match(r"(kh_\w+)\s+(\d+)", line.strip())
            if m:
                bad[m.group(1)].add(int(m.group(2)))
    return bad


def train_sheets(dishes, n, max_rank, outdir, only):
    from PIL import Image, ImageDraw
    outdir.mkdir(parents=True, exist_ok=True)
    cell, cols = 170, 8
    for dish in only:
        pool = train_pool(dish, dishes[dish], n, max_rank)
        for s in range(0, len(pool), 40):
            part = pool[s:s + 40]
            sheet = Image.new("RGB", (cols * cell, ((len(part) + cols - 1) // cols) * cell), "white")
            d = ImageDraw.Draw(sheet)
            for i, f in enumerate(part):
                with Image.open(KH / "harvested" / dish / f) as im:
                    im = im.convert("RGB"); im.thumbnail((cell - 6, cell - 6))
                x, y = (i % cols) * cell, (i // cols) * cell
                sheet.paste(im, (x + 3, y + 3))
                d.rectangle([x + 3, y + 3, x + 36, y + 22], fill="black")
                d.text((x + 7, y + 7), str(s + i + 1), fill="yellow")
            sheet.save(outdir / f"{dish}_train_{s // 40 + 1}.jpg", quality=85)
        print(f"{dish}: {len(pool)} training photos to look at (numbers 1-{len(pool)})")


def sheets(dishes, n, outdir):
    from PIL import Image, ImageDraw
    outdir.mkdir(parents=True, exist_ok=True)
    cell, cols = 220, 6
    for dish, files in dishes.items():
        cand = test_candidates(files, n, dish)
        for s in range(0, len(cand), 24):
            part = cand[s:s + 24]
            sheet = Image.new("RGB", (cols * cell, ((len(part) + cols - 1) // cols) * cell), "white")
            d = ImageDraw.Draw(sheet)
            for i, f in enumerate(part):
                with Image.open(KH / "harvested" / dish / f) as im:
                    im = im.convert("RGB"); im.thumbnail((cell - 6, cell - 6))
                x, y = (i % cols) * cell, (i // cols) * cell
                sheet.paste(im, (x + 3, y + 3))
                d.rectangle([x + 3, y + 3, x + 44, y + 28], fill="black")
                d.text((x + 8, y + 8), str(s + i + 1), fill="yellow")
            sheet.save(outdir / f"{dish}_{s // 24 + 1}.jpg", quality=85)
        print(f"{dish}: {len(cand)} test candidates (numbers 1-{len(cand)}) of {len(files)} photos")


def apply(dishes, n, max_rank):
    import shutil
    bad, bad_train = read_bad(BAD), read_bad(BAD_TRAIN)
    train = [l.strip() for l in open(META / "train_plus.txt") if l.strip()]
    test = [l.strip() for l in open(META / "test.txt") if l.strip()]
    new_train, new_test, per = [], [], {}
    for dish, files in dishes.items():
        cand = test_candidates(files, n, dish)
        bad_names = {cand[i - 1] for i in bad[dish] if 0 < i <= len(cand)}
        good = [f for f in cand if f not in bad_names]
        pool = train_pool(dish, files, n, max_rank)
        drop_train = {pool[i - 1] for i in bad_train[dish] if 0 < i <= len(pool)}
        use_train = [f for f in pool if f not in drop_train]
        (KH / "combined" / "images" / dish).mkdir(parents=True, exist_ok=True)
        for f in files:
            dst = KH / "combined" / "images" / dish / f"{Path(f).stem}.jpg"
            if not dst.exists():
                shutil.copy2(KH / "harvested" / dish / f, dst)
            if f in good:
                new_test.append(f"{dish}/{Path(f).stem}")
            elif f in use_train:
                new_train.append(f"{dish}/{Path(f).stem}")     # a wrong or doubtful photo is neither tested on nor trained on
        per[dish] = (len(use_train), len(good), len(bad_names))
    (META / "train_plus2.txt").write_text("\n".join(train + new_train) + "\n")
    (META / "test_plus.txt").write_text("\n".join(test + new_test) + "\n")
    assert not set(new_train) & set(new_test)
    names = {r["dish_id"]: r for r in csv.DictReader(open(ROOT / "data" / "recipes_khmer.csv", encoding="utf-8"))}
    classes = json.load(open(ROOT / "models" / "food101_classes.json", encoding="utf-8"))
    for dish in dishes:
        r = names[dish]
        classes.append({"id": dish, "name": r["dish_name"], "name_kh": r["dish_name_kh"], "search": r["search"]})
    (ROOT / "models" / "food101_classes_plus.json").write_text(json.dumps(classes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"train_plus2.txt {len(train)} + {len(new_train)}; test_plus.txt {len(test)} + {len(new_test)}; {len(classes)} classes")
    for dish, (tr, te, b) in per.items():
        print(f"  {dish:24} train {tr:3} test {te:2} (dropped {b} wrong test photos)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-photos", type=int, default=45)
    ap.add_argument("--test-per-dish", type=int, default=14)
    ap.add_argument("--sheets", type=Path)
    ap.add_argument("--max-rank", type=int, default=3)
    ap.add_argument("--train-sheets", type=Path)
    ap.add_argument("--train-dishes", default="kh_num_ansorm_chek,kh_num_kom")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    dishes = new_dishes(a.min_photos)
    print(f"{len(dishes)} new dishes: " + ", ".join(f"{d} ({len(v)})" for d, v in dishes.items()))
    if a.sheets:
        sheets(dishes, a.test_per_dish, a.sheets)
    if a.train_sheets:
        train_sheets(dishes, a.test_per_dish, a.max_rank, a.train_sheets, a.train_dishes.split(","))
    if a.apply:
        apply(dishes, a.test_per_dish, a.max_rank)
