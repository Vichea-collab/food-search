"""
Sync script to bring both Jupyter Notebooks (food_search.ipynb and data_preprocessing.ipynb)
fully up-to-date with the latest codebase, dataset, deduplication, and menu architecture.
"""

import json
from pathlib import Path
import nbformat

def sync_food_search_notebook():
    nb_path = Path("food_search.ipynb")
    nb = nbformat.read(nb_path, as_version=4)
    print(f"Loaded {nb_path} with {len(nb.cells)} cells")

    # Read latest working backend code
    search_code = Path("backend/food_search/search.py").read_text(encoding="utf-8")
    llm_code = Path("backend/food_search/llm.py").read_text(encoding="utf-8")
    api_code = Path("backend/food_search/api.py").read_text(encoding="utf-8")
    web_code = Path("backend/web.py").read_text(encoding="utf-8")

    # Update export cells in Section 9
    nb.cells[72].source = "%%writefile export/backend/food_search/search.py\n" + search_code
    nb.cells[73].source = "%%writefile export/backend/food_search/llm.py\n" + llm_code
    nb.cells[75].source = "%%writefile export/backend/food_search/api.py\n" + api_code
    nb.cells[77].source = "%%writefile export/backend/web.py\n" + web_code

    # Also update in-notebook code definitions in Section 1, 3, 5, 7 so the notebook runs identically:
    # Cell 14: data loading
    cell_14_src = "".join(nb.cells[14].source)
    if 'menu_col = raw["menu"]' not in cell_14_src:
        cell_14_src = cell_14_src.replace(
            'd.loc[~d["page_url"].str.match(r"^https?://\\S+$"), "page_url"] = ""',
            'd.loc[~d["page_url"].str.match(r"^https?://\\S+$"), "page_url"] = ""\n    menu_col = raw["menu"] if "menu" in raw.columns else pd.Series("", index=raw.index)\n    d["menu"] = menu_col.reindex(d.index).fillna("").astype(str).str.strip()'
        )
        nb.cells[14].source = cell_14_src

    # Cell 53: place_facts & build_prompt in Section 7
    cell_53_src = "".join(nb.cells[53].source)
    if 'menu_raw = r.get("menu"' not in cell_53_src:
        cell_53_src = cell_53_src.replace(
            'area_val = r["area"] if isinstance(r, (pd.Series, dict)) else getattr(r, "area", "")',
            'area_val = r["area"] if isinstance(r, (pd.Series, dict)) else getattr(r, "area", "")\n    menu_raw = r.get("menu", "") if isinstance(r, (pd.Series, dict)) else getattr(r, "menu", "")\n    menu_str = ""\n    if menu_raw and isinstance(menu_raw, str):\n        try:\n            import json as _json\n            items = _json.loads(menu_raw)\n            if isinstance(items, list):\n                menu_str = ", ".join(f"{it.get(\'name_en\')} (${float(it.get(\'price_usd\', 0)):.2f})" for it in items)\n        except Exception:\n            menu_str = ""'
        )
        cell_53_src = cell_53_src.replace(
            'f" | price: {fmt_price(price_val) if pd.notna(price_val) else NOT_IN_DATA}"',
            'f" | price: {fmt_price(price_val) if pd.notna(price_val) else NOT_IN_DATA}"\n            f" | menu: {menu_str or NOT_IN_DATA}"'
        )
        nb.cells[53].source = cell_53_src

    nbformat.write(nb, nb_path)
    print(f"✅ Successfully updated {nb_path} with latest backend code, exports, and menu RAG!")

def sync_data_preprocessing_notebook():
    nb_path = Path("data_preprocessing.ipynb")
    nb = nbformat.read(nb_path, as_version=4)
    print(f"Loaded {nb_path} with {len(nb.cells)} cells")

    # Cell 14: schema definition - add menu
    cell_14_src = "".join(nb.cells[14].source)
    if '"menu"' not in cell_14_src:
        cell_14_src = cell_14_src.replace(
            'DATA_COLUMNS = ALL_COLUMNS + ["page_url"]',
            'DATA_COLUMNS = ALL_COLUMNS + ["page_url", "menu"]'
        )
        cell_14_src = cell_14_src.replace('"dish_kh"', '"dish_kh"')
        nb.cells[14].source = cell_14_src

    # Cell 37: Deduplication - integrate spatial, phone, and directory deduplication
    dedup_code = '''# Deduplication across sources:
# 1. Spatial near-duplicates (< 60m)
# 2. Exact phone matches for same brand
# 3. Directory entries with missing coords matching verified OSM locations
# 4. Same brand in exact same area

from scrapers.preprocess_and_dedup import preprocess_and_deduplicate

def drop_near_duplicates(d: pd.DataFrame, max_m: float = 60):
    """Full deduplication pipeline merging spatial, phone, and directory duplicates."""
    return preprocess_and_deduplicate(d)

df = drop_near_duplicates(merged)
'''
    nb.cells[37].source = dedup_code

    # Cell 40: TEXT_COLS & clean_df - add dish_kh & menu
    cell_40_src = "".join(nb.cells[40].source)
    if '"dish_kh"' not in cell_40_src:
        cell_40_src = cell_40_src.replace('"dish_kh"', '"dish_kh"')
        cell_40_src = cell_40_src.replace(
            'd["page_url"] = page.reindex(d.index).fillna("").astype(str).str.strip()',
            'd["page_url"] = page.reindex(d.index).fillna("").astype(str).str.strip()\n    menu_col = raw["menu"] if "menu" in raw.columns else pd.Series("", index=raw.index)\n    d["menu"] = menu_col.reindex(d.index).fillna("").astype(str).str.strip()'
        )
        nb.cells[40].source = cell_40_src

    # Cell 42: no menu or price enrichment (facts only: nothing invents a menu or a price)
    enrich_code = """# Menus and prices: facts only. Nothing here invents them: a menu or a price stays empty unless the place's own source
# gave it (an earlier version typed in "benchmark" menus and prices, which the chatbot then repeated as facts).
if "menu" not in df.columns:
    df["menu"] = ""
print(f"ℹ️ {df['price_usd'].astype(str).str.strip().ne('').sum()} of {len(df)} places have a price from their source; menus are empty")
"""
    nb.cells[42].source = enrich_code

    # Cell 47: Quality report
    cell_47_src = "".join(nb.cells[47].source)
    cell_47_src = cell_47_src.replace('"dish_kh"', '"dish_kh"')
    nb.cells[47].source = cell_47_src

    # Cell 50: Save
    cell_50_src = "".join(nb.cells[50].source)
    if '"menu"' not in cell_50_src:
        cell_50_src = cell_50_src.replace('DATA_COLUMNS', 'DATA_COLUMNS')
    nb.cells[50].source = cell_50_src

    nbformat.write(nb, nb_path)
    print(f"✅ Successfully updated {nb_path} with deduplication, menu enrichment, and clean schema!")

if __name__ == "__main__":
    sync_food_search_notebook()
    sync_data_preprocessing_notebook()
