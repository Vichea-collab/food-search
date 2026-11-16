"""Clean harvested Khmer food dataset by filtering non-food images.

Detects and isolates:
- Restaurant logos, brand icons, emblems
- People, selfies, portraits, chefs, faces
- Menus, receipts, text flyers, promotional posters
- Cartoons, illustrations, clip art, coloring outlines
- Storefronts, empty rooms, building exteriors, ancient ruins
- Packaged goods, spice jars, bottles, display booths, merchandise
- Corrupt, unreadable, or extremely small / low-entropy images

Moves rejected images to `data/khfood/rejected/<dish_id>/` and writes a report to `data/khfood/cleaning_report.csv`.
"""

import argparse
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

import torch
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.food_search.search import DEVICE, load_clip

HARVESTED_DIR = ROOT / "data" / "khfood" / "harvested"
REJECTED_DIR = ROOT / "data" / "khfood" / "rejected"
REPORT_FILE = ROOT / "data" / "khfood" / "cleaning_report.csv"

# Classification prompts for zero-shot filtering
FOOD_PROMPTS = [
    "a photo of food, a cooked culinary dish on a plate or in a bowl",
    "a photo of delicious Asian food, noodle soup, rice plate, or stir-fry",
    "a close-up photo of a culinary dish or cooked meal",
]

NEGATIVE_PROMPTS = {
    "logo": "a company logo, brand emblem, trademark, or graphic icon",
    "person": "a portrait of a person, human face, woman, man, chef, or people",
    "menu_poster": "a restaurant menu with text, price list, flyer, receipt, or promotional poster",
    "drawing_cartoon": "a cartoon illustration, comic book art, drawing, or vector clip art",
    "building_ruins": "a building exterior, ancient temple ruins, landscape, street view, or empty room",
    "merchandise": "handbags, wallets, clothes, goods on display, or merchandise",
    "packaging": "raw packaged goods, cans, bottles, or empty boxes",
}


def check_heuristics(img: Image.Image) -> tuple[bool, str]:
    """Check image dimensions, aspect ratio, and color entropy."""
    w, h = img.size
    if w < 100 or h < 100:
        return False, f"too_small_{w}x{h}"

    aspect = max(w / h, h / w)
    if aspect > 4.5:
        return False, f"extreme_aspect_ratio_{aspect:.1f}"

    stat = ImageStat.Stat(img)
    avg_stddev = sum(stat.stddev) / len(stat.stddev)
    if avg_stddev < 12.0:
        return False, f"low_variance_stddev_{avg_stddev:.1f}"

    return True, "ok"


def clean_dataset(apply_changes: bool = False, min_food_sim: float = 0.16):
    print(f"Loading CLIP model on {DEVICE}...")
    model, preprocess, tokenizer = load_clip()

    # Pre-encode text features
    with torch.no_grad():
        food_tokens = tokenizer(FOOD_PROMPTS).to(DEVICE)
        food_feats = model.encode_text(food_tokens)
        food_feats = food_feats / food_feats.norm(dim=-1, keepdim=True)

        neg_keys = list(NEGATIVE_PROMPTS.keys())
        neg_tokens = tokenizer(list(NEGATIVE_PROMPTS.values())).to(DEVICE)
        neg_feats = model.encode_text(neg_tokens)
        neg_feats = neg_feats / neg_feats.norm(dim=-1, keepdim=True)

    image_paths = sorted(HARVESTED_DIR.glob("*/*.*"))
    image_paths = [p for p in image_paths if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
    print(f"Found {len(image_paths)} images across {len(set(p.parent.name for p in image_paths))} classes.")

    results = []
    stats = {"total": len(image_paths), "kept": 0, "rejected": 0}

    for p in image_paths:
        dish_id = p.parent.name
        rel_path = f"{dish_id}/{p.name}"

        # 1. PIL validation
        try:
            with Image.open(p) as raw_img:
                img = raw_img.convert("RGB")
        except Exception as e:
            results.append({
                "path": rel_path,
                "dish_id": dish_id,
                "decision": "REJECT",
                "category": "corrupt",
                "reason": f"corrupt_file_{e}",
                "food_sim": 0.0,
                "neg_sim": 1.0,
            })
            stats["rejected"] += 1
            continue

        # 2. Heuristics check
        passed_heuristics, reason = check_heuristics(img)
        if not passed_heuristics:
            results.append({
                "path": rel_path,
                "dish_id": dish_id,
                "decision": "REJECT",
                "category": "heuristic",
                "reason": reason,
                "food_sim": 0.0,
                "neg_sim": 1.0,
            })
            stats["rejected"] += 1
            continue

        # 3. CLIP zero-shot classification
        try:
            tensor = preprocess(img).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                f = model.encode_image(tensor)
                f = f / f.norm(dim=-1, keepdim=True)
                food_sim = (f @ food_feats.T).max().item()
                neg_sims = (f @ neg_feats.T).squeeze(0)
                best_neg_idx = neg_sims.argmax().item()
                best_neg_val = neg_sims[best_neg_idx].item()
                best_neg_cat = neg_keys[best_neg_idx]

            # Decision: reject if negative concept similarity exceeds food similarity, or food similarity is low
            if best_neg_val >= food_sim or food_sim < min_food_sim:
                decision = "REJECT"
                category = best_neg_cat
                reason = f"detected_{best_neg_cat}"
                stats["rejected"] += 1
            else:
                decision = "KEEP"
                category = "food"
                reason = "verified_food"
                stats["kept"] += 1

            results.append({
                "path": rel_path,
                "dish_id": dish_id,
                "decision": decision,
                "category": category,
                "reason": reason,
                "food_sim": round(food_sim, 4),
                "neg_sim": round(best_neg_val, 4),
            })
        except Exception as e:
            results.append({
                "path": rel_path,
                "dish_id": dish_id,
                "decision": "REJECT",
                "category": "error",
                "reason": f"error_{e}",
                "food_sim": 0.0,
                "neg_sim": 1.0,
            })
            stats["rejected"] += 1

    # Save CSV report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "dish_id", "decision", "category", "reason", "food_sim", "neg_sim"])
        writer.writeheader()
        writer.writerows(results)

    print("\n================ CLEANING REPORT ================")
    print(f"Total Processed: {stats['total']}")
    print(f"Kept (Dishes & Food) : {stats['kept']} ({stats['kept']/stats['total']*100:.1f}%)")
    print(f"Rejected (Non-Food)  : {stats['rejected']} ({stats['rejected']/stats['total']*100:.1f}%)")

    rej_cats = Counter(r["category"] for r in results if r["decision"] == "REJECT")
    print("\nRejected Breakdown by Category:")
    for cat, count in rej_cats.most_common():
        print(f"  - {cat:20s}: {count:2d}")

    # Class breakdown
    kept_by_class = Counter(r["dish_id"] for r in results if r["decision"] == "KEEP")
    rej_by_class = Counter(r["dish_id"] for r in results if r["decision"] == "REJECT")
    all_classes = sorted(set(r["dish_id"] for r in results))
    print("\nClass Breakdown:")
    for cls in all_classes:
        k = kept_by_class[cls]
        r = rej_by_class[cls]
        tot = k + r
        print(f"  {cls:20s}: {k:2d}/{tot:2d} kept ({k/tot*100:.1f}%), {r:2d} rejected")

    if apply_changes:
        print(f"\nMoving {stats['rejected']} non-food images to {REJECTED_DIR}...")
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        for r in results:
            if r["decision"] == "REJECT":
                src = HARVESTED_DIR / r["path"]
                dst = REJECTED_DIR / r["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.exists():
                    shutil.move(str(src), str(dst))
        print("Done moving rejected images. Dataset is clean!")
    else:
        print("\n[Dry Run Mode] No files were moved. Run with --apply to isolate non-food images.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean harvested food dataset")
    parser.add_argument("--apply", action="store_true", help="Move rejected images to data/khfood/rejected/")
    parser.add_argument("--min-food-sim", type=float, default=0.16, help="Minimum cosine similarity for food")
    args = parser.parse_args()

    clean_dataset(apply_changes=args.apply, min_food_sim=args.min_food_sim)
