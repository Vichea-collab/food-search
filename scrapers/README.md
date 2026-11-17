# 🇰🇭 Cambodia Nationwide Food & Restaurant Scrapers Suite

Comprehensive scraping, parsing, pricing calibration, and conversational normalization pipeline to build a dataset scoped to **all of Cambodia** (Phnom Penh, Siem Reap, Battambang, Sihanoukville, Kampot, Kandal, and all provinces).

Engineered for conversational food search chatbots that answer questions about:
1. **Dish & Cuisine Discovery**: English and Khmer dish names (`គុយទាវ`, `បាយសាច់ជ្រូក`, `ឡុកឡាក់`, `អាម៉ុក`, `កាហ្វេ`, etc.).
2. **Pricing (`price_usd`)**: Meal benchmarks, exact promotion prices in USD and KHR (`$1.90`, `$2.50`, `$5.00`, `20,500៛`).
3. **Ordering & Contact Instructions ("How to order / how to contact")**: Public phone numbers (`phone_public`), online ordering links (`page_url`), delivery platform routes, and operating hours (`open_hour`–`close_hour`).
4. **Nationwide Geographic Coverage**: All 25 provinces/municipalities across Cambodia.

---

## 📊 Standardized Dataset Schema (18 + 1 Columns)

Every scraper and pipeline component outputs this exact column specification:

| Column | Type | Example | Description |
|---|---|---|---|
| `id` | String | `fp-ghpk`, `canby-0001` | Unique venue identifier |
| `name` | String | `Castella Le Gato (ខាសស្តេឡា)` | Restaurant or brand name in English / Khmer |
| `dish_en` | String | `noodles`, `kuy teav`, `pizza` | English culinary category |
| `dish_kh` | String | `គុយទាវ`, `បាយសាច់ជ្រូក`, `ភីហ្សា` | Khmer culinary category (`dish_kh`) |
| `description` | String | *Serving pizza in Siem Reap...* | Conversational notes (dish, price, ordering, hours) |
| `tags` | String | `restaurant;pizza;delivery` | Semicolon-delimited searchable tags |
| `price_usd` | Float | `2.50`, `5.00`, `1.90` | Meal price or deal benchmark in USD |
| `area` | String | `Siem Reap`, `Kampot`, `Daun Penh` | Province, Municipality, or Khan |
| `lat` | Float | `11.5564`, `13.3612` | Latitude coordinate |
| `lng` | Float | `104.9282`, `103.8596` | Longitude coordinate |
| `rating` | Float | `4.5` | Venue star rating |
| `open_hour` | Float | `7.0`, `10.5` | Opening hour in 24h format |
| `close_hour` | Float | `22.0`, `23.0` | Closing hour in 24h format |
| `source` | String | `foodpanda`, `yellowpages-cambodia` | Primary data origin |
| `source_url` | String | `https://...` | Web listing or catalog URL |
| `date` | Date | `2026-11-05` | Scraping / verification date |
| `image_path` | String | `https://cdn5.telesco.pe/...` | Dish or venue image URL |
| `phone_public`| String | `+855 88 580 0010` | Public contact for takeout / reservations |
| `page_url` | String | `https://facebook.com/...` | Social page, website, or direct order link |

---

## 📂 Architecture & Data Sources

| Source | Geographic Scope | Technique & Extraction Details | Records |
|---|---|---|---|
| **Foodpanda Cambodia** | **Nationwide** (All 25 provinces) | XML Sitemap crawler parsing 12,000+ restaurant partner slugs across Siem Reap, Sihanoukville, Battambang, Kampot, Phnom Penh, etc. Populates bilingual `dish_en` and `dish_kh`, dual-currency prices, and ordering links. | **3,500+ venues** |
| **Cambodia Yellow Pages** | **Nationwide Major Cities** | Crawls `city:Phnom_Penh`, `city:Siem_Reap`, `city:Sihanoukville`, `city:Battambang`, `city:Kampot`, `city:Kampong_Cham`. Extracts Google Maps GPS coords, phone numbers, addresses, and hours. | **120+ venues** |
| **WOWNOW Telegram Deals** | **Nationwide Delivery** | Deep multi-page web preview parser (`t.me/s/wownow_fooddelivery`). Extracts promotional menus, exact USD & KHR prices, dish images (`cdn5.telesco.pe`), and ordering instructions. | **200 deals** |
| **Canby Publications** | **Phnom Penh & Central Hubs** | Leaf-table parser extracting cuisines, opening hours, phones, addresses, and website links. | **127 venues** |
| **OpenStreetMap Overpass** | **Phnom Penh & Provincial Hubs** | Extracts food & beverage amenities (`restaurant`, `cafe`, `fast_food`, `bakery`), opening hours, GPS coords, and Khmer/English bilingual names. | **1,830 venues** |
| **Wikidata & Lexicon** | **Nationwide Khmer Cuisine** | SPARQL graph query extracting authentic Cambodian dishes (`Q424`), descriptions, translations, and regional specialties. | **31 dishes** |
| **FoodChow & GrabFood** | **Key Urban Centers** | Open ordering directory scraping + Next.js hydration category harvester. | **21 listings** |

---

## 🤖 Polite crawling (robots.txt)

Every scraper that downloads web pages goes through `scrapers/robots.py` (`robots.get(url, ...)` instead of
`requests.get`). Before the first page of a site it reads that site's `robots.txt`, then:

- a page that `robots.txt` disallows is **not downloaded** (it is skipped like a failed download);
- the site's `Crawl-delay` / `Request-rate` is kept between two requests (GrabFood asks for 2 s), on top of each
  scraper's own pause;
- a missing `robots.txt` (404, 403) means no rules; one that cannot be read (5xx, no answer) blocks the site and is
  asked again after 10 minutes (the rules of RFC 9309, the robots.txt standard).

Checked on 2026-11-10, every page the scrapers use is allowed: Foodpanda (sitemap and `/restaurant/` pages), GrabFood
(2 s crawl delay), Grab's sitemap host, Cambodia Yellow Pages, FoodChow, Canby (no robots.txt) and Telegram's public
channel pages (no robots.txt). Check any address with `python scrapers/robots.py <url>`.

Wikipedia, Wikidata and OpenStreetMap Overpass are used through their official APIs, not crawled. Their
`robots.txt` is meant for crawlers (it disallows the API paths), so those scripts follow the APIs' usage policies
instead: a named User-Agent and few requests (one query each for Wikidata and Overpass; Wikipedia summaries one
per second, waiting and retrying when the service says it is busy).

The website itself has a `robots.txt` too (`frontend/public/robots.txt`): search engines may list `/` and `/demo`,
and stay out of `/api/` and the API docs.

## 🚀 CLI Commands

### 1. Run all scrapers nationwide & update the dataset
```bash
./venv/bin/python scrapers/run_all.py --all --update-main-dataset
```

### 2. Run specific scrapers
```bash
# Scrape Foodpanda nationwide (3500+ venues across Cambodia)
./venv/bin/python scrapers/foodpanda_sitemap_scraper.py --limit 3500

# Scrape WOWNOW Telegram Deals (multi-page with prices & photos)
./venv/bin/python scrapers/telegram_wownow_scraper.py --pages 10 --limit 200

# Scrape Yellow Pages across major cities
./venv/bin/python scrapers/yellowpages_scraper.py --pages 2
```

### 3. Re-run Normalization, Price Calibration & Conversational Enrichment
```bash
./venv/bin/python scrapers/normalize_and_merge.py
```

## 🧹 Facts-only menus (13 Nov 2026)

`menu` and `price_usd` hold only what a source says. `scrapers/remove_template_menus.py` removed 3,129 menus that
`enrich_all_menus.py` / `enrich_street_food_menus.py` had given to places by pattern (the same Num Pang menu on 664
unrelated cafes); those two scripts are now disabled. The column `menu_source` says where a menu comes from:
`foodpanda` (the place's own page), `chain:<brand>` (the chain's own menu on its branches) or empty (no menu).
What was removed is kept in `data/raw/removed_template_menus.csv`; the file before the cleanup is
`data/raw/restaurants_backup_before_template_removal.csv`. Overture phones and street addresses are fetched into
`data/scraped/overture_contacts.csv` (`overture_contacts.py`) but not added to the dataset until the team decides
(`apply_overture_contacts.py --with-phones`): the proposal says no personal phone numbers or home addresses of
private sellers.

## 📍 Phnom Penh only (15 Nov 2026)

Foodpanda's sitemap lists every city, and the sitemap scraper labelled a place "Phnom Penh" unless a khan was in its slug.
Of 565 places whose Foodpanda page gives the city, 89 (16%) were in Sihanoukville, Poipet, Kampong Speu and other cities.
`scrapers/remove_non_phnom_penh.py` moved 281 places out (89 by the page's city, 192 by a city at the end of the name:
17 hits, 0 wrong on the known places); they are in `data/raw/non_phnom_penh_places.csv`. About a fifth of the wrong
places can be told apart this way, so an estimated 140 are still in the data until the Foodpanda detail run (blocked by
Foodpanda's rate limit at 675 of 2,705 pages) can finish. Places that have only a Foodpanda slug have no address and no
coordinates (1,994 places), and are not geocoded from their name: a guessed position would give wrong "near me" distances.


## 📷 Khmer dish photos for the photo model (16 Nov 2026)

The photo classifier is weakest where it has the fewest photos (kuy teav 22 training photos, borbor 25, amok 38, against 750
per Food-101 dish). Scripts add photos and record where each one came from (source, page URL, and the licence when the source states one):

| Script | What it does |
|---|---|
| `harvest_khmer_open_images.py` | Wikimedia Commons (files in the Cambodian-food categories, labelled by the category name, plus a text search) and Openverse (Creative-Commons photos, anonymous limit 200 requests/day, remembered in `data/khfood/openverse_budget.json`). A photo is kept only when its own title/tags name the dish, it is a real photo (>= 256 px) and it is not a near-duplicate of any photo we have. Every file is listed in `data/khfood/harvest_sources.csv` (dish, source, title, creator, licence, page URL). `--new` does the other Khmer dishes of `data/recipes_khmer.csv`. `--sources bing` adds Bing image search for much more volume: **its photos have no known licence** (marked "unknown (web image search)" with the page URL), and Bing's terms do not allow automated scraping, so this is for training our own course model only. |
| `verify_harvested_images.py` | Looks at the picture, because text alone is not enough ("amok" also names a film and a dance show; a New York restaurant called Num Pang tags its selfies). CLIP zero-shot: a photo is rejected when it looks like a person / building / sign (distractors), when its dish is not among the 20 closest of 68 dishes, or when its CLIP vector is >= 0.93 cosine like a photo we already have (crops of the same bowl; a copy of a test photo in the training set would flatter the test score). `--calibrate` shows what the thresholds cost on the trusted photos (92% kept). `--apply` moves rejects to `data/khfood/rejected/`. |

Order: `harvest_khmer_open_images.py` -> `verify_harvested_images.py` (look at the dry-run, then `--apply`; Bing files get a stricter test) -> `merge_harvested_into_khfood.py` (copies the kept photos of the 26 model classes into `combined/` and writes `meta/train_plus.txt`; the test split is untouched so scores stay comparable) -> `train_khmer_finetune.py --khmer-train train_plus.txt` (keep the Food-101 replay about 4:1 against the Khmer photos, see the results in the notes). Result: a weight average of three retrains (`soup3`) is the live model: Khmer 82.2%, Food-101 85.8%, amok 7 -> 10 of 12 test photos. The photos stay out of git
(`data/khfood/` is ignored); the credits are in `docs/khmer-photo-credits.csv`. Many are CC BY-NC / ND and the Bing ones have no licence: fine for training a
course model, never for publishing the photos. About a quarter of the Bing photos are still wrong (video thumbnails, another dish). Wikimedia throttles generic clients hard: the script paces itself and skips a
file when the host asks for a long pause, so run it again later to pick those up. Measured limits: for a dish with a rare name
(cha kney, chha kdao, sach ko ang) open archives hold almost nothing; only a handful of Khmer dishes have 20+ open photos.

**Adding more dishes as classes (17 Nov 2026).** `add_harvested_dishes.py` turns harvested dishes with 45+ photos into classes (7 of the 34: Kampot pepper crab, fried spider, green mango salad, num ansorm chek, num kom, pumpkin custard, teuk kroeung; cha houy teuk and num plae ai were left out because about half of their photos were another dessert). Test photos of the new dishes were checked by eye (a third of the candidates were wrong and were dropped); training photos must also pass a stricter CLIP rank (top 3), and the two noisiest dishes were also checked by eye. It writes `train_plus2.txt`, `test_plus.txt` (the old 337 test photos + the new ones) and `models/food101_classes_plus.json`; train with `train_khmer_finetune.py --classes models/food101_classes_plus.json --khmer-train train_plus2 --khmer-test test_plus --per-class 100 --epochs 8`. Result vs the live model on the same photos: the 7 new dishes 78% (live: 0%), old Khmer 82.2 -> 81.3%, Food-101 85.8 -> 85.6%. Weight-averaging with the live model gave back 0.3 points on the old dishes but lost 12 points on the new ones, so it was not used. Weak: green mango salad 3/12, num kom 5/9.
