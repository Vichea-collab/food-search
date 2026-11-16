"""
Fine-tune EfficientNet-B0 on Food-101 + the 26 Khmer dishes together (127 classes).

Why both: training on the Khmer photos alone made the model forget Food-101 ("catastrophic forgetting"):
on 2026-11-15 the Khmer-only checkpoint called 90% of Food-101 test photos a Khmer dish (Food-101 top-1 9.6%).
So every epoch mixes the Khmer training photos with a fresh sample of Food-101 training photos
("replay"), about the same number per class, and the best epoch is chosen on BOTH test sets.

  python scrapers/train_khmer_finetune.py --base <checkpoint> --out models/food101_efficientnet_b0.mixed.pt

--base: the checkpoint to start from (its backbone and the classifier rows of the classes it knows are kept);
        a good start is the original Food-101 + 16 Khmer model: git show b2566f0:models/food101_efficientnet_b0.pt
--out:  where the new checkpoint goes. The live model (models/food101_efficientnet_b0.pt) is never overwritten:
        compare first, then copy it over and restart the app.
"""

import argparse
import json
import logging
import math
import random
import time
from pathlib import Path

from PIL import Image
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import torchvision
import torchvision.transforms as T

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mixed_finetune")

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
LIVE_PATH = MODELS_DIR / "food101_efficientnet_b0.pt"
CLASSES_PATH = MODELS_DIR / "food101_classes.json"
COMBINED_DIR = ROOT / "data" / "khfood" / "combined"
FOOD101_DIR = ROOT / "data" / "food101" / "food-101"

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
IMG_SIZE = 224
RESIZE = 256
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]
# not food (found by the app's CLIP food check on 2026-11-15): a crocodile, screenshots and text cards
NOT_FOOD = {"kh_bok_lhong/0020", "kh_borbor/0022", "kh_kuy_teav/0022", "kh_prahok_ktiss/0049",
            "kh_salted_crab/0009", "kh_samlor_proher/0043"}


def khmer_list(split):
    """[(path, class)] of one split of data/khfood/combined, without the NOT_FOOD photos."""
    out = []
    for line in open(COMBINED_DIR / "meta" / f"{split}.txt"):
        line = line.strip()
        if not line or line in NOT_FOOD:
            continue
        dish, name = line.split("/")
        path = COMBINED_DIR / "images" / dish / f"{name}.jpg"
        if path.exists():
            out.append((path, dish))
    return out


def food101_list(split, per_class=None, rng=None):
    """[(path, class)] of a Food-101 split; per_class: a random sample of that many photos per class."""
    meta = json.load(open(FOOD101_DIR / "meta" / f"{split}.json"))
    out = []
    for dish, items in sorted(meta.items()):
        if per_class:
            items = rng.sample(items, min(per_class, len(items)))
        out += [(FOOD101_DIR / "images" / f"{i}.jpg", dish) for i in items]
    return out


class Photos(Dataset):
    def __init__(self, samples, class_to_idx, transform):
        self.samples, self.class_to_idx, self.transform = samples, class_to_idx, transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        path, dish = self.samples[i]
        with Image.open(path) as im:
            img = im.convert("RGB")
        return self.transform(img), self.class_to_idx[dish]


def build_transforms():
    train_tf = T.Compose([T.RandomResizedCrop(IMG_SIZE, scale=(0.6, 1.0)), T.RandomHorizontalFlip(),
                          T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2), T.ToTensor(),
                          T.Normalize(mean=MEAN, std=STD)])
    eval_tf = T.Compose([T.Resize(RESIZE), T.CenterCrop(IMG_SIZE), T.ToTensor(), T.Normalize(mean=MEAN, std=STD)])
    return train_tf, eval_tf


def load_model(base, classes):
    """EfficientNet-B0 with a head for `classes`; backbone and known class rows copied from `base`."""
    model = torchvision.models.efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(classes))
    ckpt = torch.load(base, map_location="cpu", weights_only=True)
    sd, old = ckpt["state_dict"], {c: i for i, c in enumerate(ckpt["classes"])}
    model.load_state_dict({k: v for k, v in sd.items() if not k.startswith("classifier.1.")}, strict=False)
    with torch.no_grad():
        head = model.classifier[1]
        nn.init.normal_(head.weight, std=0.01)
        nn.init.zeros_(head.bias)
        for i, c in enumerate(classes):
            if c in old:
                head.weight[i] = sd["classifier.1.weight"][old[c]]
                head.bias[i] = sd["classifier.1.bias"][old[c]]
    new = [c for c in classes if c not in old]
    log.info("Base %s: %d classes kept, %d new: %s", base, len(classes) - len(new), len(new), ", ".join(new))
    return model.to(DEVICE)


@torch.no_grad()
def evaluate(model, loader):
    """(top-1, top-5, share of photos predicted as a Khmer dish)."""
    model.eval()
    top1 = top5 = khmer = n = 0
    for imgs, targets in loader:
        out = model(imgs.to(DEVICE)).cpu()
        top1 += (out.argmax(1) == targets).sum().item()
        top5 += out.topk(5, 1).indices.eq(targets.view(-1, 1)).any(1).sum().item()
        khmer += (out.argmax(1) >= loader.dataset.first_khmer).sum().item()
        n += len(targets)
    return top1 / n, top5 / n, khmer / n


def loader_for(samples, class_to_idx, tf, shuffle, workers, first_khmer=None):
    ds = Photos(samples, class_to_idx, tf)
    ds.first_khmer = first_khmer
    return DataLoader(ds, batch_size=48, shuffle=shuffle, num_workers=workers, persistent_workers=workers > 0)


def finetune(base, out, epochs, per_class, eval_per_class, workers, seed, khmer_repeat=1):
    rng = random.Random(seed)
    torch.manual_seed(seed)
    classes = [c["id"] for c in json.load(open(CLASSES_PATH, encoding="utf-8"))]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    first_khmer = min(i for c, i in class_to_idx.items() if c.startswith("kh_"))
    assert all(c.startswith("kh_") for c in classes[first_khmer:]), "Khmer classes must come last in the class list"
    log.info("Device %s, %d classes (%d Food-101 + %d Khmer)", DEVICE, len(classes), first_khmer,
             len(classes) - first_khmer)
    model = load_model(base, classes)

    train_tf, eval_tf = build_transforms()
    kh_train, kh_test = khmer_list("train"), khmer_list("test")
    f_test = food101_list("test", eval_per_class, random.Random(seed + 1))
    kh_loader = loader_for(kh_test, class_to_idx, eval_tf, False, workers, first_khmer)
    f_loader = loader_for(f_test, class_to_idx, eval_tf, False, workers, first_khmer)
    log.info("Khmer: %d train, %d test photos. Food-101: %d replay photos per class per epoch, %d test photos",
             len(kh_train), len(kh_test), per_class, len(f_test))

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW([{"params": model.features.parameters(), "lr": 5e-5},
                                   {"params": model.classifier.parameters(), "lr": 5e-4}], weight_decay=1e-4)
    steps_per_epoch = math.ceil((len(kh_train) * khmer_repeat + per_class * first_khmer) / 48)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=[5e-5, 5e-4], total_steps=epochs * steps_per_epoch,
                                                    pct_start=0.15)

    f1, _, fk = evaluate(model, f_loader)
    k1, _, _ = evaluate(model, kh_loader)
    log.info("Before: Food-101 top-1 %.1f%% (%.1f%% called Khmer) | Khmer top-1 %.1f%%", f1 * 100, fk * 100, k1 * 100)

    best, history = None, []
    for epoch in range(1, epochs + 1):
        model.train()
        samples = kh_train * khmer_repeat + food101_list("train", per_class, rng)   # a fresh Food-101 sample every epoch
        loader = loader_for(samples, class_to_idx, train_tf, True, workers)
        t0, loss_sum, n = time.time(), 0.0, 0
        for step, (imgs, targets) in enumerate(loader):
            if step >= steps_per_epoch:
                break
            imgs, targets = imgs.to(DEVICE), targets.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(imgs), targets)
            loss.backward()
            optimizer.step()
            scheduler.step()
            loss_sum += loss.item() * len(targets)
            n += len(targets)
        f1, f5, fk = evaluate(model, f_loader)
        k1, k5, _ = evaluate(model, kh_loader)
        score = (f1 + k1) / 2                     # both halves matter equally
        history.append({"epoch": epoch, "loss": loss_sum / n, "food101_top1": f1, "food101_top5": f5,
                        "food101_called_khmer": fk, "khmer_top1": k1, "khmer_top5": k5})
        log.info("Epoch %d/%d %.0fs | loss %.3f | Food-101 top-1 %.1f%% (%.1f%% called Khmer) | Khmer top-1 %.1f%% "
                 "| mean %.1f%%", epoch, epochs, time.time() - t0, loss_sum / n, f1 * 100, fk * 100, k1 * 100, score * 100)
        if best is None or score > best[0]:
            best = (score, epoch, f1, f5, k1, k5, {k: v.cpu().clone() for k, v in model.state_dict().items()})

    score, epoch, f1, f5, k1, k5, state = best
    torch.save({"arch": "efficientnet_b0", "state_dict": state, "classes": classes, "img_size": IMG_SIZE,
                "resize": RESIZE, "mean": MEAN, "std": STD, "quick_run": False,
                "run": f"Food-101 + Khmer mixed fine-tune ({per_class} Food-101 photos/class/epoch, Khmer x{khmer_repeat}), "
                       f"best epoch {epoch}",
                "test_top1": (f1 + k1) / 2, "test_top1_food101": f1, "test_top5_food101": f5,
                "test_top1_khmer": k1, "test_top5_khmer": k5, "food101_test_sample": eval_per_class,
                "base": str(base), "history": history, "trained": time.strftime("%Y-%m-%d")}, out)
    log.info("Saved best epoch %d to %s (Food-101 %.1f%%, Khmer %.1f%%)", epoch, out, f1 * 100, k1 * 100)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, default=LIVE_PATH)
    p.add_argument("--out", type=Path, default=MODELS_DIR / "food101_efficientnet_b0.mixed.pt")
    p.add_argument("--epochs", type=int, default=6)
    p.add_argument("--per-class", type=int, default=40, help="Food-101 replay photos per class per epoch")
    p.add_argument("--eval-per-class", type=int, default=10, help="Food-101 test photos per class for the epoch check")
    p.add_argument("--khmer-repeat", type=int, default=1, help="each Khmer training photo this many times per epoch "
                   "(the Khmer dishes have fewer photos than look-alike Food-101 dishes: kuy teav / pho, borbor / ramen)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    if a.out.resolve() == LIVE_PATH.resolve():
        p.error("--out must not be the live model; compare first, then copy it over")
    finetune(a.base, a.out, a.epochs, a.per_class, a.eval_per_class, a.workers, a.seed, a.khmer_repeat)
