import pandas as pd
import re

df = pd.read_csv("data/restaurants.csv")
print(f"Total places: {len(df)}")

def extract_base_name(name):
    if not isinstance(name, str):
        return ""
    # Extract english portion before parens or khmer
    m = re.match(r"^([A-Za-z0-9\s\’\'-]+?)(?:\s*\(.*|\s*[\u1780-\u17FF].*)?$", name)
    base = m.group(1).strip() if m else name.strip()
    base = re.sub(r"[^A-Za-z0-9]", "", base).lower()
    for stop in ["restaurant", "cafe", "food", "cambodia", "phnompenh", "branch", "express"]:
        base = base.replace(stop, "")
    return base

df["base_name"] = df["name"].map(extract_base_name)
df["area_norm"] = df["area"].fillna("").astype(str).str.lower().str.strip()

has_base = df["base_name"].str.len() >= 3
potential_dups = df[has_base & df.duplicated(subset=["base_name", "area_norm"], keep=False)]
groups = potential_dups.groupby(["base_name", "area_norm"])
print(f"Potential duplicate rows in same area: {len(potential_dups)} across {groups.ngroups} groups\n")

print("Sample duplicate groups:")
sample_brands = ["mikesburgerhouse", "pizzacompany", "dominospizza", "luckyburger", "amazon", "cafamazon", "coffeetoday", "topaz", "romdeng"]
found = 0
for (base, area), group in groups:
    if any(b in base for b in sample_brands):
        found += 1
        print(f"--- Group: {base} @ {area} ({len(group)} rows) ---")
        for _, r in group.iterrows():
            print(f"  ID: {r['id']} | Name: {r['name']} | Coords: ({r['lat']}, {r['lng']}) | Phone: {r['phone_public']} | Page: {str(r['page_url'])[:50]}")
        if found >= 10:
            break

print("\n--- Checking Duplicate URLs and Phones ---")
valid_urls = df[df["page_url"].fillna("").str.startswith("http")]
dup_urls = valid_urls[valid_urls.duplicated(subset=["page_url"], keep=False)]
print(f"Places sharing exact same page_url: {len(dup_urls)} rows across {dup_urls['page_url'].nunique()} URLs")

for url, group in dup_urls.groupby("page_url"):
    if len(group) > 1:
        print(f"URL: {url[:60]}")
        for _, r in group.iterrows():
            print(f"   [{r['id']}] {r['name']} ({r['area']})")
        break

valid_phones = df[df["phone_public"].fillna("").ne("") & df["phone_public"].ne("nan")]
dup_phones = valid_phones[valid_phones.duplicated(subset=["phone_public"], keep=False)]
print(f"Places sharing exact same phone number: {len(dup_phones)} rows across {dup_phones['phone_public'].nunique()} numbers")
