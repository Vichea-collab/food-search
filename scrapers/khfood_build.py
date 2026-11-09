"""
Build data/khfood/combined: Khmer dish photos in the same layout as Food-101 (images/<dish>/<photo>.jpg and
meta/classes.txt, train.txt, test.txt), so food_classification.ipynb can train on Food-101 + Khmer dishes together.

Sources (Roboflow Universe, both CC BY 4.0, downloaded with ROBOFLOW_API_KEY from .env):
  khfood         https://universe.roboflow.com/dataset-poorm/khfood-rjsdk           version 2, 728 photos, 14 dishes (numbered 00-13)
  kh-food image  https://universe.roboflow.com/khfood-image-g3hpx/kh-food-image     version 2, 128 photos, 7 dishes
Every Roboflow version has augmentation baked in: each training photo appears 3 times (rotated, cut out, grey...).
We keep ONE copy per original photo: the validation/test copy if there is one (not augmented), else the most colourful
copy (skips grayscale ones). Our own notebook augments during training. Exact duplicate photos are removed.

The khfood dishes are only numbered; the names below were read from the photos (checked with the project owner).
Usage:
    python scrapers/khfood_build.py --download    # download both datasets (needs: pip install roboflow), then build
    python scrapers/khfood_build.py               # build from data/khfood/<downloads>
"""
import argparse
import json
import os
import random
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parent.parent
KH = ROOT / "data" / "khfood"
OUT = KH / "combined"
TEST_FRACTION = 0.25           # as in Food-101 (750 train / 250 test per dish)
SEED = 42

DOWNLOADS = [("dataset-poorm", "khfood-rjsdk", 2, "khfood-v2"),
             ("khfood-image-g3hpx", "kh-food-image", 2, "kh-food-image-v2")]

# dish id -> display name, Khmer name, search words for the place search (the words that found the best places
# in data/restaurants.csv, checked one by one), source folders (download/class)
DISHES = {
    "kh_shrimp_salad":    ("Raw shrimp salad (plea bongkea)", "ភ្លាបង្គា", "plea bongkea shrimp salad",
                           ["khfood-v2/00", "khfood-v2/០០"]),
    "kh_khor":            ("Khor (caramelised braised pork)", "ខ", "khmer food braised pork",
                           ["khfood-v2/01", "kh-food-image-v2/Khor"]),
    "kh_beef_stew":       ("Beef stew (sach ko kho)", "សាច់គោខ", "beef stew kho", ["khfood-v2/02"]),
    "kh_cha_kney":        ("Stir-fried ginger (cha kney)", "ឆាខ្ញី", "khmer food stir fry ginger", ["khfood-v2/03"]),
    "kh_salted_crab":     ("Salted crab (kdam prai)", "ក្តាមប្រៃ", "kdam prai salted crab", ["khfood-v2/04"]),
    "kh_kari":            ("Khmer curry (kari)", "ការី", "khmer curry kari", ["khfood-v2/05"]),
    "kh_lok_lak":         ("Lok lak", "ឡុកឡាក់", "lok lak", ["khfood-v2/06"]),
    "kh_num_banh_chok":   ("Num banh chok", "នំបញ្ចុក", "num banh chok", ["khfood-v2/07"]),
    "kh_beef_salad":      ("Beef salad (plea sach ko)", "ភ្លាសាច់គោ", "plea sach ko beef salad", ["khfood-v2/08"]),
    "kh_prahok_ktiss":    ("Prahok ktiss", "ប្រហុកខ្ទិះ", "prahok", ["khfood-v2/09"]),
    "kh_samlor_korko":    ("Samlor korko", "សម្លកកូរ", "khmer soup samlor korko", ["khfood-v2/10"]),
    "kh_samlor_machu":    ("Sour soup (samlor machu)", "សម្លម្ជូរ", "សម្លម្ជូរ", ["khfood-v2/11"]),
    "kh_sngao_ngam_ngov": ("Sngao ngam ngov (soup with pickled lime)", "ស្ងោរញាំញូវ", "ស្ងោរញាំញូវ",
                           ["khfood-v2/12", "kh-food-image-v2/Moan Sngao Ngam Ngov ",
                            "kh-food-image-v2/Moan Sngao Ngam Ngov  Sngao Ngam Ngov", "kh-food-image-v2/Sngao Ngam Ngov",
                            "kh-food-image-v2/Sngao Chrouk(lime Sour)"]),
    "kh_samlor_proher":   ("Vegetable soup (samlor proher)", "សម្លប្រហើរ", "samlor proher vegetable soup", ["khfood-v2/13"]),
    "kh_kanh":            ("Kanh (minced beef salad)", "", "kanh beef salad", ["kh-food-image-v2/kanh"]),
    "kh_steamed_fish_soy": ("Steamed fish with soy sauce", "ត្រីចំហុយទឹកស៊ីអ៊ីវ", "steamed fish soy sauce",
                            ["kh-food-image-v2/*steamed-fish*"]),
}


def download():
    from roboflow import Roboflow
    key = os.environ.get("ROBOFLOW_API_KEY") or next(
        (l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text().splitlines() if l.startswith("ROBOFLOW_API_KEY=")), "")
    if not key:
        sys.exit("Set ROBOFLOW_API_KEY in .env (Roboflow → Settings → API Keys).")
    rf = Roboflow(api_key=key)
    KH.mkdir(parents=True, exist_ok=True)
    for ws, project, version, folder in DOWNLOADS:
        rf.workspace(ws).project(project).version(version).download("folder", location=str(KH / folder), overwrite=True)


def class_dirs(pattern: str) -> list:
    """'khfood-v2/04' -> that folder in every split. '*steamed-fish*': the one folder whose name is not ASCII
    (the Khmer name ត្រីចំហុយទឹកស៊ីអ៊ីវ, garbled by the zip)."""
    ds, cls = pattern.split("/", 1)
    splits = [d for d in (KH / ds).iterdir() if d.is_dir()]
    if cls == "*steamed-fish*":
        return [c for s in splits for c in s.iterdir() if c.is_dir() and not c.name.isascii()]
    return [s / cls for s in splits if (s / cls).is_dir()]


def colourfulness(path) -> float:
    return sum(ImageStat.Stat(Image.open(path).convert("HSV")).mean[1:2])


def tiny_hash(path) -> str:
    small = Image.open(path).convert("L").resize((8, 8))
    pixels = list(small.tobytes())
    avg = sum(pixels) / 64
    return "".join("1" if p > avg else "0" for p in pixels)


def build():
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "meta").mkdir(parents=True)
    rng = random.Random(SEED)
    classes, train, test, stats = [], [], [], []
    seen_hashes = set()
    for dish, (name, name_kh, search, sources) in DISHES.items():
        copies = defaultdict(list)                       # original photo -> its copies (split, path)
        for pattern in sources:
            for folder in class_dirs(pattern):
                for p in folder.glob("*.jpg"):
                    original = re.sub(r"\.rf\.[0-9a-f]+$", "", p.stem)
                    copies[f"{pattern.split('/')[0]}:{original}"].append((folder.parent.name, p))
        kept = []
        for original, cs in sorted(copies.items()):
            plain = [p for split, p in cs if split in ("valid", "test")]
            best = plain[0] if plain else max((p for _, p in cs), key=colourfulness)
            h = tiny_hash(best)
            if h in seen_hashes:                         # the same photo again (in both datasets, or twice)
                continue
            seen_hashes.add(h)
            kept.append(best)
        (OUT / "images" / dish).mkdir(parents=True)
        names = []
        for n, src in enumerate(sorted(kept)):
            names.append(f"{dish}/{n:04d}")
            shutil.copy2(src, OUT / "images" / dish / f"{n:04d}.jpg")
        rng.shuffle(names)
        n_test = max(1, round(len(names) * TEST_FRACTION))
        test += sorted(names[:n_test])
        train += sorted(names[n_test:])
        classes.append({"id": dish, "name": name, "name_kh": name_kh, "search": search})
        stats.append((dish, len(copies), len(kept), len(names) - n_test, n_test))
    (OUT / "meta" / "classes.txt").write_text("\n".join(c["id"] for c in classes) + "\n")
    (OUT / "meta" / "classes.json").write_text(json.dumps(classes, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "meta" / "train.txt").write_text("\n".join(train) + "\n")
    (OUT / "meta" / "test.txt").write_text("\n".join(test) + "\n")
    (OUT / "README.txt").write_text(
        "Khmer dish photos for food_classification.ipynb (Food-101 layout). Built by scrapers/khfood_build.py from\n"
        "Roboflow Universe datasets (CC BY 4.0): dataset-poorm/khfood-rjsdk v2 and khfood-image-g3hpx/kh-food-image v2.\n")
    print(f"{'dish':22s} {'originals':>9s} {'kept':>5s} {'train':>6s} {'test':>5s}")
    for row in stats:
        print(f"{row[0]:22s} {row[1]:9d} {row[2]:5d} {row[3]:6d} {row[4]:5d}")
    print(f"total: {len(classes)} dishes, {len(train)} train + {len(test)} test photos -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true", help="download both Roboflow datasets first")
    if ap.parse_args().download:
        download()
    build()
