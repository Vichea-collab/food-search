"""
Master CLI to orchestrate all Phnom Penh Food Scrapers
Usage:
    python scrapers/run_all.py --all
    python scrapers/run_all.py --sources canby,yellowpages,wownow,wikidata
    python scrapers/run_all.py --update-main-dataset
"""

import sys
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AVAILABLE_SCRAPERS = {
    "canby": ("Canby Publications", "scrapers/canby_scraper.py"),
    "yellowpages": ("Cambodia Yellow Pages", "scrapers/yellowpages_scraper.py"),
    "wownow": ("WOWNOW Telegram Deals", "scrapers/telegram_wownow_scraper.py"),
    "foodchow": ("FoodChow Phnom Penh", "scrapers/foodchow_scraper.py"),
    "foodpanda": ("Foodpanda Sitemaps", "scrapers/foodpanda_sitemap_scraper.py"),
    "grabfood": ("GrabFood Categories", "scrapers/grabfood_scraper.py"),
    "grabfood-merchants": ("GrabFood Merchants (sitemaps)", "scrapers/grabfood_sitemap_scraper.py"),
    "wikidata": ("Wikidata Khmer Dishes", "scrapers/wikidata_scraper.py"),
    "osm": ("OpenStreetMap Overpass", "scrapers/osm_overpass_scraper.py"),
    "overture": ("Overture Maps Foundation", "scrapers/overture_scraper.py"),
}

def run_scraper(name: str, py_script: str, python_bin: str = sys.executable) -> bool:
    print(f"\n==========================================")
    print(f"🚀 Running {name} ({py_script})")
    print(f"==========================================")
    res = subprocess.run([python_bin, py_script])
    return res.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Orchestrate Phnom Penh Food Scrapers")
    parser.add_argument("--all", action="store_true", help="Run all available scrapers")
    parser.add_argument("--sources", type=str, default="", help="Comma-separated scrapers (e.g. canby,wownow,yellowpages)")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping and only run merge/normalize")
    parser.add_argument("--update-main-dataset", action="store_true", help="Overwrite data/restaurants.csv with merged data")
    args = parser.parse_args()

    selected = []
    if args.all:
        selected = list(AVAILABLE_SCRAPERS.keys())
    elif args.sources:
        for s in args.sources.split(","):
            s = s.strip().lower()
            if s in AVAILABLE_SCRAPERS:
                selected.append(s)
            else:
                print(f"Warning: unknown scraper '{s}', available: {list(AVAILABLE_SCRAPERS.keys())}")
    elif not args.skip_scrape:
        print("No sources specified. Use --all or --sources <name1,name2>. Available:")
        for k, (name, _) in AVAILABLE_SCRAPERS.items():
            print(f"  - {k}: {name}")
        return

    if not args.skip_scrape:
        for key in selected:
            name, script = AVAILABLE_SCRAPERS[key]
            success = run_scraper(name, script)
            if not success:
                print(f"⚠️ Warning: Scraper {key} finished with non-zero exit code.")

    # Run merge and normalization
    print("\n==========================================")
    print("🔄 Merging, Deduplicating & Normalizing...")
    print("==========================================")
    from scrapers.normalize_and_merge import merge_and_normalize
    combined_csv = "data/scraped/restaurants_combined.csv"
    df = merge_and_normalize(output_file=combined_csv)

    if args.update_main_dataset:
        main_csv = Path("data/restaurants.csv")
        # Backup existing
        if main_csv.exists():
            backup_csv = Path(f"data/raw/restaurants_backup_before_scrape.csv")
            backup_csv.write_bytes(main_csv.read_bytes())
            print(f"Backed up existing data/restaurants.csv to {backup_csv}")
        df.to_csv(main_csv, index=False)
        print(f"✅ Updated main dataset: {main_csv} ({len(df)} places)")

if __name__ == "__main__":
    main()
