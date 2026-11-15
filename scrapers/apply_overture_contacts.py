"""
Merge the Overture contact fields (scrapers/overture_contacts.py) into the main dataset: phone and street address of
businesses with a landline. (Overture websites were checked: only 20 were new and most are Google Maps links: skipped.)

  --with-phones   also fill the empty `phone_public` and `address`, but only for BUSINESSES: a landline number (+855 2x)
                  only. The proposal says "we do not collect personal phone
                  numbers or home addresses of private sellers", and most other Overture phones are the mobile numbers
                  of small sellers, so those (and the addresses that go with them) are left out.

Only empty cells are filled; nothing already in the dataset is overwritten.

  venv/bin/python scrapers/apply_overture_contacts.py --out data/scraped/restaurants_clean.csv   [--with-phones]
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "data/restaurants.csv"
CONTACTS = ROOT / "data/scraped/overture_contacts.csv"


def clean_phone(p: str) -> str:
    """'+85523 218 630' -> '+855 23 218 630' is not attempted; digits only, a Cambodian number or ''."""
    digits = re.sub(r"[^\d+]", "", p or "")
    if digits.startswith("0") and 8 <= len(digits) <= 10:
        digits = "+855" + digits[1:]
    return digits if re.fullmatch(r"\+855\d{8,9}", digits) else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(MAIN))
    ap.add_argument("--out", required=True)
    ap.add_argument("--with-phones", action="store_true")
    a = ap.parse_args()
    d = pd.read_csv(a.src, dtype=str, keep_default_na=False)
    c = pd.read_csv(CONTACTS, dtype=str, keep_default_na=False).set_index("restaurant_id")
    hit = d["id"].isin(c.index)
    if a.with_phones:
        ph = d.loc[hit, "id"].map(c["phone"]).map(clean_phone)
        business = ph.str.match(r"\+8552\d")
        ph = ph.where(business, "")
        f2 = hit.copy(); f2[hit] = ph.ne("") & d.loc[hit, "phone_public"].eq("")
        d.loc[f2, "phone_public"] = ph[f2[hit]].values
        ad = d.loc[hit, "id"].map(c["address"]).str.strip().where(business, "")
        if "address" not in d.columns:
            d.insert(d.columns.get_loc("phone_public"), "address", "")
        f3 = hit.copy(); f3[hit] = ad.ne("") & d.loc[hit, "address"].eq("")
        d.loc[f3, "address"] = ad[f3[hit]].values
        print(f"phone filled on {int(f2.sum())} places, address on {int(f3.sum())}")
    d.to_csv(a.out, index=False)
    print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
