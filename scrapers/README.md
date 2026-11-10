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
