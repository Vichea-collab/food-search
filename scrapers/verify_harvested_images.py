"""
Check the photos harvested by scrapers/harvest_khmer_open_images.py with CLIP, before they are used for training.

The harvester only reads TEXT (titles, tags), so it keeps whatever is filed under a name: a selfie from the restaurant
that is called Num Pang, a film actor for "amok", the same bowl of noodles cropped six ways. This script looks at the
PICTURE. For every photo of dish X it asks CLIP (zero-shot, independent of our trained model, so no circular
reasoning) which of these it looks like most: the descriptions of all the Khmer dishes, or one of the non-food
"distractors" (a person, a building, a street, a sign, a landscape, an animal ...). A photo is

  REJECT  not_dish      the distractors get more than --max-distractor of the probability, or
  REJECT  wrong_dish    X is not among the --top-k closest dishes, or
  REJECT  near_duplicate  its CLIP image vector is >= --dup-sim (cosine) like a photo we already keep
                        (the existing training/test photos count: a copy of a test photo in the training set would
                        make the test score look better than it is)
  KEEP    otherwise.

--calibrate runs the same test on the photos whose labels we trust (data/khfood/combined) to show how many good photos
the thresholds would lose; a check is only worth something if it keeps most of those.
Writes data/khfood/verify_report.csv. --apply moves the rejected files to data/khfood/rejected/<dish>/ (the harvester
sees that folder, so it will not download them again).

    venv/bin/python scrapers/verify_harvested_images.py --calibrate     # how strict are the thresholds?
    venv/bin/python scrapers/verify_harvested_images.py                 # dry run: the report only
    venv/bin/python scrapers/verify_harvested_images.py --apply
"""
import argparse
import csv
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import torch
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.food_search.search import DEVICE, load_clip       # noqa: E402

KH = ROOT / "data" / "khfood"
HARVESTED, REJECTED, COMBINED = KH / "harvested", KH / "rejected", KH / "combined"
REPORT = KH / "verify_report.csv"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
# the same dish under another id: left out of the dish list, so it cannot "win" against the dish itself
SAME_DISH = {"kh_amok", "kh_bok_lahong", "kh_num_pang_pate", "kh_sach_ko_ang_jakak"}

DISTRACTORS = [
    "a portrait photo of a person", "a selfie of two people smiling", "a group of people standing together",
    "a person on a stage or a theatre performance", "a street scene with cars and buildings", "the outside of a building",
    "an empty room or the inside of a shop", "a shop sign, a poster or a menu with text", "a company logo or graffiti",
    "a landscape with sky and water", "a sailing boat or a vehicle", "an animal", "a map or satellite image",
    "a drawing, cartoon or screenshot", "a cocktail or a glass of drink", "a person cooking, hands and kitchen equipment",
    "raw vegetables, fruit or fish on display at a market", "a temple or ancient ruins",
    "a restaurant front with customers queueing outside", "the staff behind the counter of a restaurant",
    # web image search also returns art and video covers, which are not photos of the dish
    "a cartoon, flat vector or AI-generated illustration of food, not a real photo", "a video thumbnail with large text and a presenter's face",
    "a stock photo with a watermark", "a collage of many small pictures",
]


def first_words(text, n):
    return " ".join((text or "").replace("\n", " ").split()[:n])


def dish_prompts():
    """{dish_id: [prompts]} from data/dish_knowledge.csv: its name and the start of its description."""
    out = {}
    for r in csv.DictReader(open(ROOT / "data" / "dish_knowledge.csv", encoding="utf-8")):
        i = r["dish_id"]
        if not i.startswith("kh_") or i in SAME_DISH:
            continue
        name = re.sub(r"\s*\(.*\)$", "", r["name_en"]).strip()
        inside = re.findall(r"\(([^)]*)\)", r["name_en"])
        what = f", {inside[0]}" if inside else ""
        out[i] = [f"a photo of {name}{what}, a Cambodian dish", f"a photo of {first_words(r['about_en'], 22)}"]
    return out


class Clip:
    def __init__(self):
        self.model, self.preprocess, self.tokenizer = load_clip()
        prompts = dish_prompts()
        self.ids = list(prompts)
        with torch.no_grad():
            def enc(texts):
                v = self.model.encode_text(self.tokenizer(texts).to(DEVICE)).float()
                return v / v.norm(dim=-1, keepdim=True)
            dish = torch.stack([enc(p).mean(0) for p in prompts.values()])
            self.text = torch.cat([dish / dish.norm(dim=-1, keepdim=True), enc(DISTRACTORS)])
        self.n_dish = len(self.ids)

    @torch.no_grad()
    def embed(self, paths, batch=48):
        """-> (image vectors [n, d], dish probabilities [n, n_dish], distractor mass [n]); a bad file gets nan."""
        vecs, probs, mass = [], [], []
        for i in range(0, len(paths), batch):
            ims, ok = [], []
            for p in paths[i:i + batch]:
                try:
                    with Image.open(p) as im:
                        ims.append(self.preprocess(im.convert("RGB")))
                    ok.append(True)
                except Exception:
                    ok.append(False)
            if ims:
                v = self.model.encode_image(torch.stack(ims).to(DEVICE)).float()
                v = (v / v.norm(dim=-1, keepdim=True)).cpu()
                pr = (100 * v.to(DEVICE) @ self.text.T).softmax(1).cpu()
            it = iter(range(len(ims)))
            for good in ok:
                if good:
                    j = next(it)
                    vecs.append(v[j]); probs.append(pr[j, :self.n_dish]); mass.append(float(pr[j, self.n_dish:].sum()))
                else:
                    vecs.append(torch.full((self.text.shape[1],), float("nan"))); probs.append(torch.zeros(self.n_dish)); mass.append(1.0)
        return torch.stack(vecs), torch.stack(probs), torch.tensor(mass)

    def rank(self, probs, dish):
        """1 = the closest dish. A dish this script has no prompt for is judged by the distractors only (rank 1)."""
        if dish not in self.ids:
            return torch.ones(len(probs), dtype=torch.long)
        k = self.ids.index(dish)
        return (probs > probs[:, k:k + 1]).sum(1) + 1


def images(folder):
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in IMAGE_EXT)


def calibrate(clip, per_dish, top_k, max_d):
    """The photos whose labels we trust: how many would each rule drop?"""
    rows = defaultdict(list)
    for p in images(COMBINED / "images"):
        rows[p.parent.name].append(p)
    rng = __import__("random").Random(0)
    keep = Counter(); n = 0; per = {}
    for dish, ps in sorted(rows.items()):
        ps = rng.sample(ps, min(per_dish, len(ps)))
        _, probs, mass = clip.embed(ps)
        rk = clip.rank(probs, dish)
        bad_d, bad_k = (mass > max_d), (rk > top_k)
        per[dish] = (len(ps), int(bad_d.sum()), int(bad_k.sum()))
        keep["distractor"] += int(bad_d.sum()); keep["wrong_dish"] += int((bad_k & ~bad_d).sum()); keep["kept"] += int((~bad_d & ~bad_k).sum()); n += len(ps)
    print(f"CALIBRATION on {n} trusted photos (top-{top_k}, distractor mass > {max_d}): kept {keep['kept'] / n:.1%}, "
          f"dropped as distractor {keep['distractor'] / n:.1%}, as wrong dish {keep['wrong_dish'] / n:.1%}")
    for dish, (m, d, k) in sorted(per.items(), key=lambda kv: -(kv[1][1] + kv[1][2]) / kv[1][0])[:8]:
        print(f"   hardest for CLIP: {dish:22} {m - d - k}/{m} kept (distractor {d}, wrong dish {k})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="move rejected files to data/khfood/rejected/<dish>/")
    ap.add_argument("--calibrate", action="store_true", help="test the thresholds on data/khfood/combined and stop")
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--max-distractor", type=float, default=0.35)
    ap.add_argument("--dup-sim", type=float, default=0.93)
    # Bing photos are labelled only by a page title (no licence either), so they get a stricter test than Commons/Openverse
    ap.add_argument("--bing-top-k", type=int, default=10)
    ap.add_argument("--bing-max-distractor", type=float, default=0.25)
    ap.add_argument("--per-dish", type=int, default=25, help="calibration: photos per dish")
    a = ap.parse_args()
    clip = Clip()
    print(f"CLIP on {DEVICE}: {clip.n_dish} dishes, {len(DISTRACTORS)} distractors")
    if a.calibrate:
        calibrate(clip, a.per_dish, a.top_k, a.max_distractor)
        return

    # the photos we already keep (training and test) come first: a harvested copy of one of them is a duplicate
    existing = images(COMBINED / "images")
    ev, _, _ = clip.embed(existing)
    kept_vecs = [ev[~torch.isnan(ev).any(1)]]
    # only the photos the harvester added (listed in harvest_sources.csv): the older harvested photos were cleaned
    # by clean_harvested_images.py and are already part of data/khfood/combined
    listed = {r["file"] for r in csv.DictReader(open(KH / "harvest_sources.csv", encoding="utf-8"))}
    todo = [p for p in images(HARVESTED) if f"{p.parent.name}/{p.name}" in listed]
    # harvested photos that are in combined already (the first harvest was merged there) are not duplicates of themselves
    names = {p.name for p in existing}
    rows, moved, stats = [], 0, Counter()
    by_dish = defaultdict(list)
    for p in todo:
        by_dish[p.parent.name].append(p)
    for dish, ps in sorted(by_dish.items()):
        v, probs, mass = clip.embed(ps)
        rk = clip.rank(probs, dish)
        for i, p in enumerate(ps):
            reason, dup = "", 0.0
            if torch.isnan(v[i]).any():
                reason = "unreadable"
            elif mass[i] > (a.bing_max_distractor if p.name.startswith("bg_") else a.max_distractor):
                reason = "not_dish"
            elif rk[i] > (a.bing_top_k if p.name.startswith("bg_") else a.top_k):
                reason = "wrong_dish"
            else:
                pool = torch.cat(kept_vecs)
                dup = float((pool @ v[i]).max()) if len(pool) else 0.0
                if dup >= a.dup_sim and p.name not in names:
                    reason = "near_duplicate"
            if not reason:
                kept_vecs.append(v[i:i + 1])
            stats[(dish, reason or "keep")] += 1
            rows.append({"dish_id": dish, "file": f"{dish}/{p.name}", "decision": "REJECT" if reason else "KEEP",
                         "reason": reason or "ok", "dish_rank": int(rk[i]), "distractor_mass": round(float(mass[i]), 3),
                         "max_dup_sim": round(dup, 3)})
            if reason and a.apply:
                dst = REJECTED / dish
                dst.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dst / p.name))
                moved += 1
    with REPORT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    total = Counter(r["reason"] for r in rows)
    print(f"{len(rows)} harvested photos: {total['ok']} keep | " + ", ".join(f"{k} {v}" for k, v in total.items() if k != "ok"))
    for dish in sorted(by_dish):
        c = {k[1]: v for k, v in stats.items() if k[0] == dish}
        print(f"  {dish:26} keep {c.get('keep', 0):3} | " + ", ".join(f"{k} {v}" for k, v in c.items() if k != "keep"))
    print(f"report: {REPORT}" + (f"; moved {moved} files to {REJECTED}" if a.apply else "  (dry run: nothing moved)"))


if __name__ == "__main__":
    main()
