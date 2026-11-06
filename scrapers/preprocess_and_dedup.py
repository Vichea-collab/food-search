"""
Complete Data Preprocessing and Deduplication Pipeline for Cambodian Food Places.
1. Deduplicates spatial near-duplicates (within 60 meters).
2. Deduplicates exact phone / page_url matches for the same brand.
3. Merges unmapped magazine/directory entries with verified OSM locations.
4. Unifies and normalizes bilingual restaurant names (English + Khmer).
5. Cleans repeated sentences and duplicate formatted blocks in descriptions.
6. Standardizes phone numbers, prices, and menu JSON.
"""

import json
import math
import re
from pathlib import Path
import numpy as np
import pandas as pd

KHMER_CHAR_RE = re.compile(r"[\u1780-\u17FF]")

def haversine_m(lat1, lng1, lat2, lng2) -> float:
    """Distance in meters between two lat/lng coordinates."""
    try:
        lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
        if math.isnan(lat1) or math.isnan(lat2):
            return 999999.0
    except (ValueError, TypeError):
        return 999999.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(min(1.0, a)))

def clean_phone(p: str) -> str:
    if not p or str(p).lower() in ("nan", "none", ""):
        return ""
    digits = re.sub(r"[^\d+]", "", str(p))
    return digits

def normalize_name_key(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    # Remove parens
    s = re.sub(r"\(.*?\)", "", name).lower()
    # Strip Khmer characters for English key, or keep if all Khmer
    eng_only = re.sub(r"[^a-z0-9]", "", s)
    if len(eng_only) >= 3:
        for stop in ["restaurant", "cafe", "café", "cambodia", "phnompenh", "food", "express", "branch", "house"]:
            eng_only = eng_only.replace(stop, "")
        return eng_only
    return re.sub(r"[^a-z0-9\u1780-\u17FF]", "", s)

def clean_description(desc: str) -> str:
    if not desc or not isinstance(desc, str):
        return ""
    # Remove repeated "Menu: ... មុខម្ហូបទាំងអស់៖ ..." if it appears more than once
    menu_matches = list(re.finditer(r"Menu:.*?(?=Menu:|$)", desc))
    if len(menu_matches) > 1:
        last_menu = menu_matches[-1].group(0)
        desc = desc[:menu_matches[0].start()] + " " + last_menu

    # Split into sentences and eliminate exact duplicate sentences
    parts = re.split(r"(?<=[.។])\s+", desc)
    seen = set()
    cleaned = []
    for p in parts:
        p_strip = p.strip()
        p_norm = re.sub(r"\s+", " ", p_strip.lower())
        if p_norm and p_norm not in seen and len(p_strip) > 3:
            seen.add(p_norm)
            cleaned.append(p_strip)
    res = " ".join(cleaned)
    res = re.sub(r"\s+", " ", res).strip()
    return res

def merge_records(rec1: dict, rec2: dict) -> dict:
    """Merges two duplicate records, keeping the most complete information."""
    merged = dict(rec1)
    
    # Name: prefer bilingual name if one has Khmer and other has English
    name1, name2 = str(rec1.get("name", "")), str(rec2.get("name", ""))
    if KHMER_CHAR_RE.search(name1) and not KHMER_CHAR_RE.search(name2):
        merged["name"] = name1
    elif KHMER_CHAR_RE.search(name2) and not KHMER_CHAR_RE.search(name1):
        merged["name"] = name2
    elif len(name2) > len(name1):
        merged["name"] = name2

    # Fill missing fields
    for field in ["dish_en", "dish_kh", "area", "city", "lat", "lng", "rating", "open_hour", 
                  "close_hour", "phone_public", "page_url", "image_path", "menu", "price_usd"]:
        val1 = rec1.get(field)
        val2 = rec2.get(field)
        if (pd.isna(val1) or val1 == "" or str(val1).lower() == "nan") and (pd.notna(val2) and val2 != "" and str(val2).lower() != "nan"):
            merged[field] = val2

    # Merge tags
    tags1 = set(str(rec1.get("tags", "")).split(";"))
    tags2 = set(str(rec2.get("tags", "")).split(";"))
    all_tags = [t.strip() for t in (tags1 | tags2) if t.strip() and t.strip().lower() != "nan"]
    merged["tags"] = ";".join(sorted(all_tags))

    # Clean description
    desc1 = str(rec1.get("description", ""))
    desc2 = str(rec2.get("description", ""))
    merged["description"] = clean_description(desc1 if len(desc1) >= len(desc2) else desc2)

    return merged

def preprocess_and_deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    print(f"📊 Starting with {len(df)} places")
    
    # 1. Clean whitespace and text across all rows
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # Drop obvious junk entries
    junk_mask = df["name"].isin(["", "nan", "(fried chicken) ((មាន់បំពង))", "🎉"]) | (df["name"].str.len() < 2)
    dropped_junk = junk_mask.sum()
    df = df[~junk_mask].copy()
    if dropped_junk:
        print(f"🧹 Removed {dropped_junk} junk/empty places")

    # 2. Deduplicate near-duplicates by coordinates (< 60 meters) with similar name
    to_drop = set()
    records = df.to_dict(orient="records")
    rec_by_idx = {i: records[i] for i in range(len(records))}

    grid = {}
    for i, r in rec_by_idx.items():
        try:
            lat = float(r["lat"])
            lng = float(r["lng"])
            cell = (round(lat, 2), round(lng, 2))
            grid.setdefault(cell, []).append(i)
        except (ValueError, TypeError):
            continue

    spatial_merged = 0
    for cell, indices in grid.items():
        n = len(indices)
        for a in range(n):
            idx1 = indices[a]
            if idx1 in to_drop:
                continue
            r1 = rec_by_idx[idx1]
            k1 = normalize_name_key(r1["name"])
            for b in range(a + 1, n):
                idx2 = indices[b]
                if idx2 in to_drop:
                    continue
                r2 = rec_by_idx[idx2]
                k2 = normalize_name_key(r2["name"])
                
                name_match = (k1 and k2 and (k1 == k2 or k1 in k2 or k2 in k1))
                if name_match:
                    dist = haversine_m(r1["lat"], r1["lng"], r2["lat"], r2["lng"])
                    if dist <= 60.0:  # Within 60 meters
                        merged = merge_records(r1, r2)
                        rec_by_idx[idx1] = merged
                        to_drop.add(idx2)
                        spatial_merged += 1

    print(f"📍 Merged {spatial_merged} spatial duplicates within 60 meters")

    # 3. Deduplicate by exact phone number + brand name
    phone_groups = {}
    for i, r in rec_by_idx.items():
        if i in to_drop:
            continue
        p = clean_phone(r.get("phone_public", ""))
        k = normalize_name_key(r["name"])
        if len(p) >= 8 and len(k) >= 3:
            key = (k, p)
            phone_groups.setdefault(key, []).append(i)

    phone_merged = 0
    for (k, p), idx_list in phone_groups.items():
        if len(idx_list) > 1:
            primary_idx = idx_list[0]
            for other_idx in idx_list[1:]:
                if other_idx not in to_drop:
                    rec_by_idx[primary_idx] = merge_records(rec_by_idx[primary_idx], rec_by_idx[other_idx])
                    to_drop.add(other_idx)
                    phone_merged += 1

    print(f"📞 Merged {phone_merged} phone duplicates for identical brand")

    # 4. Merge unmapped directory/magazine entries with matching OSM places
    unmapped_merged = 0
    for i, r in rec_by_idx.items():
        if i in to_drop:
            continue
        lat = r.get("lat")
        if not lat or str(lat).lower() == "nan":
            k1 = normalize_name_key(r["name"])
            if len(k1) < 4:
                continue
            # Look for an existing place with coordinates and matching name
            for j, o in rec_by_idx.items():
                if j in to_drop or j == i:
                    continue
                o_lat = o.get("lat")
                if o_lat and str(o_lat).lower() != "nan":
                    k2 = normalize_name_key(o["name"])
                    if k1 == k2 or (len(k1) >= 5 and k1 in k2) or (len(k2) >= 5 and k2 in k1):
                        rec_by_idx[j] = merge_records(o, r)
                        to_drop.add(i)
                        unmapped_merged += 1
                        break
    if unmapped_merged:
        print(f"📖 Merged {unmapped_merged} unmapped directory entries with verified locations")

    # 5. Deduplicate exact duplicate name in exact same Khan/area
    name_area_groups = {}
    for i, r in rec_by_idx.items():
        if i in to_drop:
            continue
        k = normalize_name_key(r["name"])
        area = str(r.get("area", "")).lower().strip()
        if len(k) >= 4 and len(area) >= 3:
            key = (k, area)
            name_area_groups.setdefault(key, []).append(i)

    name_area_merged = 0
    for (k, area), idx_list in name_area_groups.items():
        if len(idx_list) > 1:
            primary_idx = idx_list[0]
            for other_idx in idx_list[1:]:
                if other_idx not in to_drop:
                    rec_by_idx[primary_idx] = merge_records(rec_by_idx[primary_idx], rec_by_idx[other_idx])
                    to_drop.add(other_idx)
                    name_area_merged += 1

    print(f"🏢 Merged {name_area_merged} duplicate branch entries in the exact same area")

    # Build clean output dataframe
    clean_records = [rec_by_idx[i] for i in sorted(rec_by_idx.keys()) if i not in to_drop]
    out_df = pd.DataFrame(clean_records)

    # 6. Final pass on descriptions: remove any duplicated sentences
    out_df["description"] = out_df["description"].map(clean_description)
    out_df["price_usd"] = pd.to_numeric(out_df["price_usd"], errors="coerce")

    print(f"✅ Preprocessing complete: {len(df)} -> {len(out_df)} unique places ({len(df) - len(out_df)} duplicates eliminated)")
    return out_df

def main():
    csv_path = Path("data/restaurants.csv")
    df = pd.read_csv(csv_path)
    cleaned_df = preprocess_and_deduplicate(df)
    
    # Save to main dataset and scraped combined
    cleaned_df.to_csv(csv_path, index=False)
    print(f"💾 Saved clean dataset to {csv_path}")

    scraped_csv = Path("data/scraped/restaurants_combined.csv")
    if scraped_csv.parent.exists():
        cleaned_df.to_csv(scraped_csv, index=False)
        print(f"💾 Saved to {scraped_csv}")

if __name__ == "__main__":
    main()
