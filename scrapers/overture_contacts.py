"""
Fetch the contact fields of the Overture places we already hold: phone, website, social links, street address and
operating status. The first Overture extraction (scrapers/overture_scraper.py -> data/raw/overture_food_phnom_penh.csv)
kept only name, category, coordinates, Facebook and website; the release also has phones and addresses.

Reads the same release as the raw file, straight from Overture's public bucket with DuckDB (no scraping, no login):
only the rows inside Cambodia's Phnom Penh box and whose id is in the raw file are kept.
Output: data/scraped/overture_contacts.csv  (id = the id used in data/restaurants.csv, e.g. overture-06fec42a-364)

  venv/bin/python scrapers/overture_contacts.py
"""
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/overture_food_phnom_penh.csv"
OUT = ROOT / "data/scraped/overture_contacts.csv"
BOX = dict(xmin=104.6, xmax=105.2, ymin=11.35, ymax=11.8)          # Phnom Penh with a margin


def short_id(full: str) -> str:
    """The id used in data/restaurants.csv: first 8 characters, then the first 3 of the second block."""
    return f"overture-{full[:8]}-{full[9:12]}"


def main():
    raw = pd.read_csv(RAW, dtype=str, keep_default_na=False)
    release = raw["release"].iloc[0].rsplit(".", 0)[0]
    ids = pd.DataFrame({"id": raw["id"]})
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    con.register("ours", ids)
    src = f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"
    print("reading", src)
    df = con.execute(f"""
        SELECT p.id,
               p.phones[1]                 AS phone,
               p.websites[1]               AS website,
               p.socials                   AS socials,
               p.addresses[1].freeform     AS address,
               p.addresses[1].postcode     AS postcode,
               p.operating_status          AS operating_status,
               p.brand.names.primary       AS brand
        FROM read_parquet('{src}', hive_partitioning=1) p
        JOIN ours o ON o.id = p.id
        WHERE p.bbox.xmin BETWEEN {BOX['xmin']} AND {BOX['xmax']} AND p.bbox.ymin BETWEEN {BOX['ymin']} AND {BOX['ymax']}
    """).fetchdf()
    df["socials"] = df["socials"].map(lambda s: ";".join(s) if isinstance(s, (list, tuple)) or hasattr(s, "__array__") and not pd.isna(s).all() else "")
    df.insert(0, "restaurant_id", df["id"].map(short_id))
    df.drop(columns="id").to_csv(OUT, index=False)
    f = lambda c: int(df[c].notna().sum() - (df[c] == "").sum())
    print(f"{len(df)} of {len(raw)} places found | phone {f('phone')} | website {f('website')} | socials {f('socials')} "
          f"| address {f('address')} | operating_status {f('operating_status')} | brand {f('brand')}")


if __name__ == "__main__":
    sys.exit(main())
