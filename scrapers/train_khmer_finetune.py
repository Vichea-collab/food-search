"""
Fine-tune EfficientNet-B0 on the expanded 26 Khmer dishes (1,430 photos).

Transfers existing Food-101 + Khmer backbone weights from models/food101_efficientnet_b0.pt,
expands classifier head to 127 classes, trains on MPS / CPU, evaluates on the 353 test photos,
and saves the updated checkpoint.
"""

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

from PIL import Image
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
import torchvision
import torchvision.transforms as T

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("khmer_finetune")

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
CKPT_PATH = MODELS_DIR / "food101_efficientnet_b0.pt"
CLASSES_PATH = MODELS_DIR / "food101_classes.json"
COMBINED_DIR = ROOT / "data" / "khfood" / "combined"

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
IMG_SIZE = 224
MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]


class KhmerFoodDataset(Dataset):
    def __init__(self, list_file: Path, transform=None):
        self.transform = transform
        self.samples = []
        with open(list_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                dish, name = line.split("/")
                img_path = COMBINED_DIR / "images" / dish / f"{name}.jpg"
                if img_path.exists():
                    self.samples.append((img_path, dish))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, dish = self.samples[idx]
        with Image.open(path) as im:
            img = im.convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, dish


def build_transforms():
    train_tf = T.Compose([
        T.Resize(256),
        T.RandomCrop(IMG_SIZE),
        T.RandomHorizontalFlip(),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD),
    ])
    eval_tf = T.Compose([
        T.Resize(256),
        T.CenterCrop(IMG_SIZE),
        T.ToTensor(),
        T.Normalize(mean=MEAN, std=STD),
    ])
    return train_tf, eval_tf


def finetune(epochs: int = 6):
    log.info("Running on device: %s", DEVICE)

    # 1. Load classes
    with open(CLASSES_PATH, encoding="utf-8") as f:
        class_entries = json.load(f)
    classes = [c["id"] for c in class_entries]
    class_to_idx = {c: i for i, c in enumerate(classes)}
    num_classes = len(classes)
    log.info("Total classes: %d (101 Food-101 + %d Khmer)", num_classes, num_classes - 101)

    # 2. Build model architecture
    model = torchvision.models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)

    # 3. Load existing weights
    if CKPT_PATH.exists():
        log.info("Loading base weights from %s", CKPT_PATH)
        ckpt = torch.load(CKPT_PATH, map_location="cpu", weights_only=False)
        old_sd = ckpt["state_dict"]
        old_classes = ckpt.get("classes", [])
        old_class_to_idx = {c: i for i, c in enumerate(old_classes)}

        # Load backbone
        backbone_sd = {k: v for k, v in old_sd.items() if not k.startswith("classifier.1.")}
        model.load_state_dict(backbone_sd, strict=False)

        # Transfer overlapping classifier weights
        old_w = old_sd["classifier.1.weight"]
        old_b = old_sd["classifier.1.bias"]
        with torch.no_grad():
            for c, new_idx in class_to_idx.items():
                if c in old_class_to_idx:
                    old_idx = old_class_to_idx[c]
                    model.classifier[1].weight[new_idx] = old_w[old_idx]
                    model.classifier[1].bias[new_idx] = old_b[old_idx]
                else:
                    # Initialize new class weights
                    nn.init.normal_(model.classifier[1].weight[new_idx], std=0.01)
                    nn.init.zeros_(model.classifier[1].bias[new_idx])
        log.info("Transferred %d existing class weights to classifier head", len(old_classes))
    else:
        log.info("Initializing from pretrained ImageNet weights")
        weights = torchvision.models.EfficientNet_B0_Weights.IMAGENET1K_V1
        base = torchvision.models.efficientnet_b0(weights=weights)
        base.classifier[1] = nn.Linear(in_features, num_classes)
        model = base

    model = model.to(DEVICE)

    # 4. Prepare data loaders
    train_tf, eval_tf = build_transforms()
    train_ds = KhmerFoodDataset(COMBINED_DIR / "meta" / "train.txt", transform=train_tf)
    test_ds = KhmerFoodDataset(COMBINED_DIR / "meta" / "test.txt", transform=eval_tf)

    log.info("Dataset loaded: %d train images, %d test images across Khmer classes", len(train_ds), len(test_ds))

    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False, num_workers=2)

    # 5. Training setup
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW([
        {"params": model.features.parameters(), "lr": 1e-4},
        {"params": model.classifier.parameters(), "lr": 1e-3},
    ], weight_decay=1e-4)

    # 6. Training loop
    log.info("Starting fine-tuning for %d epochs...", epochs)
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        t0 = time.time()

        for imgs, dish_names in train_loader:
            targets = torch.tensor([class_to_idx[d] for d in dish_names], device=DEVICE)
            imgs = imgs.to(DEVICE)

            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * len(targets)
            preds = outputs.argmax(dim=1)
            correct += (preds == targets).sum().item()
            total += len(targets)

        train_acc = correct / max(1, total) * 100
        avg_loss = total_loss / max(1, total)
        elapsed = time.time() - t0

        # Quick eval each epoch
        model.eval()
        test_correct = 0
        test_total = 0
        top5_correct = 0
        with torch.no_grad():
            for imgs, dish_names in test_loader:
                targets = torch.tensor([class_to_idx[d] for d in dish_names], device=DEVICE)
                imgs = imgs.to(DEVICE)
                outputs = model(imgs)

                preds = outputs.argmax(dim=1)
                test_correct += (preds == targets).sum().item()

                _, top5 = outputs.topk(5, dim=1)
                top5_correct += top5.eq(targets.view(-1, 1)).sum().item()
                test_total += len(targets)

        test_top1 = test_correct / max(1, test_total) * 100
        test_top5 = top5_correct / max(1, test_total) * 100

        log.info("Epoch [%d/%d] in %.1fs | Loss: %.3f | Train Acc: %.1f%% | Test Top-1: %.1f%% | Test Top-5: %.1f%%",
                 epoch, epochs, elapsed, avg_loss, train_acc, test_top1, test_top5)

    # 7. Backup and Save
    if CKPT_PATH.exists():
        backup_path = CKPT_PATH.with_suffix(".pt.bak")
        shutil.copy2(CKPT_PATH, backup_path)
        log.info("Backed up old model to %s", backup_path)

    save_dict = {
        "arch": "efficientnet_b0",
        "state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
        "classes": classes,
        "img_size": IMG_SIZE,
        "resize": 256,
        "mean": MEAN,
        "std": STD,
        "test_top1_khmer": float(test_top1 / 100),
        "test_top5_khmer": float(test_top5 / 100),
        "trained": time.strftime("%Y-%m-%d"),
        "num_classes": num_classes,
    }
    torch.save(save_dict, CKPT_PATH)
    log.info("Saved fine-tuned 127-class model checkpoint to %s", CKPT_PATH)


if __name__ == "__main__":
    finetune(epochs=6)
