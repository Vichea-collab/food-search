# Project Milestone 1 — Proposal

**Project:** Khmer–English Food Search for Phnom Penh
**Team:** Chhoeun Venghourt, Luch Tithvichea, Heng Hakley
**Date:** 2 November 2026

---

## 1. Problem: what information need will the search engine serve? Who is the user?

**User.** Anyone in Phnom Penh who wants to decide where to eat or order food: residents, students and visitors. They write in **Khmer, English, or romanized Khmer** (for example `kuy teav`, `នំបញ្ចុក`, `amok`) and often add a condition such as *cheap*, *open late* or *near me*.

**Information need.** "Where can I get *this dish*, in *this area*, at *this budget*, *right now*?" For example:
- `នំបញ្ចុក` or `curry noodle` (the same dish in two languages)
- `cheap kuy teav open late`
- `korean bbq in Toul Kork`
- `pizza near me` (the user shares their **current location** and gets the closest matches, with the distance in km)

**Online ordering.** Many sellers take orders through a Facebook page or profile, a Telegram channel or a phone call instead of a delivery app. The user types what they want (`kuy teav`, `tacos`) and expects to learn **who sells it and how to order**: the seller's Facebook page or profile, Telegram channel or website when it is published, and the place with a map link when there is a physical location.

**Why a dedicated search engine.** Map apps list places by category and name. Two things are hard to find with them:
1. **Dish-level queries in Khmer and English**, including spelling variants and typos (`carry noodle`, `kuytiew`).
2. **Online food sellers**, many of whom sell through Telegram channels and are not in any directory.

**Our system.** A search engine over food places and sellers that combines keyword search (BM25 with fuzzy matching for typos), semantic search with multilingual embeddings, and filters for price, opening hours, area and distance. For **"near me"** queries the user shares their current location in Telegram; results are sorted from the closest place and show the distance in km and a map link. The location is kept in memory only for the session and is never stored. It is a chatbot built with retrieval-augmented generation (RAG): the engine first retrieves the best sellers and places, then a language model writes a short reply using only those results, so it cannot invent sellers; without the model the bot shows plain result cards. The chatbot runs on Telegram, and a working prototype already exists.

---

## 2. Corpus: what will we collect?

**Topic and language.** Restaurants, cafés, street-food stalls and online food sellers in **Phnom Penh** (all 14 khans). Text is Khmer, English, or a mix of both.

**Unit of retrieval.** One document = one place or seller, with name, dishes (English and Khmer), description, tags, area, coordinates, price, rating, opening hours, source and source link, and an **order link** (Facebook page or profile, Telegram channel or website) when known.

| Source | What it gives | Size | Status |
|---|---|---|---|
| **OpenStreetMap** (Overpass API; open licence ODbL, with credit) | Name, location, khan, cuisine, sometimes Khmer name, hours, business phone | **1,830 named places** downloaded on 30 Oct 2026 | Done |
| **Telegram seller channels** (official API; public channels of shops and brands) | Online sellers: menu items with prices, taken from recent posts | Target 20–30 channels, a few hundred menu items | Reader built; first run on real channels pending |
| **Manual enrichment** in a shared Google Sheet | Dish names in English and Khmer, price, short description for chosen places | Target 150–200 places | In progress |

**Expected size:** about **1,900–2,000 documents** (the 1,830 OpenStreetMap places plus the Telegram sellers). The 150–200 manually enriched places are the best-described part of the corpus.

**What the OpenStreetMap data contains (measured on the 1,830 places):**

| Field | Share of places |
|---|---|
| Khmer place name | 30% |
| Any Khmer text (name or dish category) | 53% |
| Cuisine / dish information | 37% |
| Opening hours | 16% |
| Business phone | 16% |
| Facebook page link | 3% |
| Any online page (Facebook, website or Instagram) | 9% |
| Price, rating | 0% (added by hand or from Telegram) |

**Order links are the weakest part of OpenStreetMap.** Only 168 of the 1,830 places (9%) have any online page. Among the 55 noodle places (for example `kuy teav`) only 3 have one, and among the 11 Mexican or taco places only 1. We fill this gap with the Telegram channels and by recording seller links by hand with the seller's agreement (see Team roles).

**Collection rules.**
- We do **not** scrape Google Maps, Facebook or delivery apps, because their terms of service forbid it. For Facebook we only store the public link to a seller's page when OpenStreetMap or the seller gives it, so the chatbot can send the user there to order.
- Telegram: we read only **public broadcast channels** (not groups or private channels) through the official API. We read **channels of shops and brands**; individual or home sellers only if the owner agrees. Where we asked and the owner agreed, rows are marked `source = telegram`. Where we did not ask, rows are marked `source = telegram-public`, so the report can show both groups separately.
- From Telegram we keep only menu lines with prices and the post link. Phone numbers, emails, links and @handles are removed, and no customer names or comments are collected. We read a limited number of recent posts per channel, with pauses, and we do not republish the collected data.
- OpenStreetMap is credited "© OpenStreetMap contributors" and kept under its licence.
- We do not collect personal phone numbers or home addresses of private sellers.

---

## 3. Team roles

The crawler for Sessions 5–6 is already working: the OpenStreetMap downloader is finished, and the Telegram reader is implemented and tested with a simulated Telegram connection. Its first run on real channels is the next step.

| Area | Owner | Tasks |
|---|---|---|
| **Crawling / data collection** | Chhoeun Venghourt | Run and extend the OpenStreetMap and Telegram collectors; contact seller channels and record consent; record order links (Facebook page, Telegram channel, website) for online sellers; keep the Google Sheet in the agreed format; data-quality checks |
| **Indexing** | Luch Tithvichea | Cleaning and Khmer Unicode normalization; tokenization (Khmer has no spaces between words); BM25 index; embeddings and the ChromaDB vector index; order-link field in the index; chatbot with RAG answers; Telegram bot, including "near me" search with the shared location |
| **Ranking / evaluation** | Heng Hakley | Build the evaluation set (30–50 hand-labelled queries in English, Khmer and with typos); metrics (Recall@5, MRR, nDCG@5); include queries for online sellers (for example `kuy teav`, `tacos`); compare BM25, embeddings and hybrid; tune the hybrid weight, filters and distance scoring (check that "near me" results are really the closest relevant places) |
| **Write-up** | All three, edited by Luch Tithvichea | Each member writes the section for the area they own; one member edits the final report and presentation |

*Roles are our proposal; any change will be agreed within the team and noted in the next milestone.*

---

## 4. Risks: what is the biggest uncertainty right now?

**Biggest uncertainty: Khmer text processing, and how much dish-level information the corpus really contains.**

| Risk | Why it matters | How we handle it |
|---|---|---|
| **Khmer text processing** | Khmer is written without spaces between words. We currently split Khmer into character 2- and 3-grams, which is a rough method. Multilingual embedding models have seen much less Khmer than English, and 47% of the places have no Khmer text at all, so Khmer queries must also reach English-only records. | Evaluate the n-gram method against a dedicated Khmer word segmenter on our labelled queries; add Khmer dish names (`dish_kh`) in the enrichment step; report Khmer and English results separately |
| **Few online sellers and order links** | Only 9% of the OpenStreetMap places have an online page, and sellers who exist only on Facebook cannot be collected automatically. A query like `tacos` may return places but no way to order. | Record Facebook, Telegram and website links of online sellers by hand with their agreement, use the Telegram channels, and say clearly in the answer when no order link is known |
| **Corpus content** | OpenStreetMap has no prices or ratings and little dish information, so conditions like "cheap" cannot work for most places yet. | Enrich 150–200 places by hand; take prices from Telegram menus; report clearly which filters work only on the enriched subset |
| **Access to sources** | Google Maps and Facebook are not allowed. Telegram needs a login with our own account, and we have not yet checked how many shop channels post usable menus with prices. Reading channels without asking the owner is a judgement call we must justify. | Read only public channels of businesses, mark them separately in the data, keep contact details out, check Telegram's API terms with our instructor, and fall back on OpenStreetMap and manual data if too few channels are usable |
| **Wrong chatbot answers** | A language model can invent details, for example a seller or a link. | It receives only the retrieved results, is told not to add facts, and the result cards with the data source are always shown next to its text |
| **Evaluation quality** | A test set of 30–50 queries is small, and "relevant" is partly subjective. | Two members label independently and resolve differences; present results as trends, not exact scores |
| **Possible requirement for an HTML crawler** | If the course requires crawling web pages, our API-based collectors may not be enough. | Add a polite crawler (respecting `robots.txt` and rate limits) for the websites listed in OpenStreetMap, which is a small share of places (about 6%) |
