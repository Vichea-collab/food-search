# Klean Nham (ឃ្លានញ៉ាំ) – QA Test Report

| | |
|---|---|
| **Date** | 2026-11-10 |
| **Build tested** | Live app at https://kleannham.luchtithvichea.com (restarted 09:28), branch `voice-and-photo-checks` (commit 5d4478f + uncommitted work) |
| **Data tested** | `data/restaurants.csv`: 14,842 places, **Phnom Penh only** (the file was replaced at 09:26 today; Siem Reap and the other provinces now have 0 places) |
| **Scope** | Telegram bot, web app (chat page + "How it works" page), API answers, voice, photo, safety, in English and Khmer |
| **Method** | Automated tests, a scripted question set, the real bot handlers with stand-in Telegram objects, and the live web app in Chrome (section 7) |

---

## Summary

| Area | Checks | Pass | Fail | Notes |
|---|---|---|---|---|
| Automated tests (`pytest`) | 138 | 132 | 6 | 5 failed because of today's data change, 1 because of bug B1. **After the fixes (section 1.3): 147 / 147 pass** |
| API question set, English + Khmer | 74 | 65 | 9 | Real failures: B1, B5, B6, B9, B10. Another 9 first-pass failures were read by hand and are correct behaviour |
| Telegram bot (real handlers) | 46 | 38 | 8 | Commands, typed questions, buttons, location, photo, voice, HTML safety |
| Web app (Chrome, live site) | 19 | 16 | 3 | Chat, dish and place cards, language switch, dark mode, phone size, `/` menu, photo, voice preview, "How it works" (4 tabs) |
| Voice (speech ↔ text) | 7 | 4 | 3 | The two Khmer voices work; speech-to-text is slow and weaker in Khmer today (Gemini quota) |
| Safety and security | 9 | 8 | 1 | Prompt injection and HTML/script are handled; a Khmer off-topic question is not caught (B5) |

**Verdict.** The core experience works in both languages. Dish questions, recipes, searches, follow-ups, photos and voice replies give correct, well-formatted answers in English and Khmer, and nothing crashed.

These **3 high-severity bugs** were found (B1, B2 and B15 are now fixed, see section 1.3):
- **B1:** "lok lak in Toul Kork" and "cheap kuy teav" show unrelated places.
- **B2:** 74% of place cards show a data source name ("overture", "foodpanda") as the category.
- **B3:** A misheard voice question once moved the whole conversation to Kep.

Today's switch to Phnom Penh-only data also left examples ("pizza in Siem Reap") and 5 tests pointing at places that no longer exist (B15).

---

## 1. Bugs found (open)

**Severity:**
- **High:** a wrong or misleading answer to a common question.
- **Medium:** wrong on a less common path, or a clear quality problem.
- **Low:** cosmetic or rare.

| # | Severity | Where | Bug | Steps → actual (expected) |
|---|---|---|---|---|
| B1 | **High** ✅ fixed | Bot + web | **When a filter leaves no real match, unrelated places are shown as if they matched** | "lok lak in Toul Kork" → Carl's Jr. Burger, Sin Samnang Goat Soup, Texas Chicken. No Toul Kork place sells lok lak, so the expected answer is "nothing like that in Toul Kork yet". "cheap kuy teav" → 5 × KOI Thé bubble tea; expected: kuy teav shops, or "no prices for these". This bug also fails `test_cheap_keeps_the_dish`. |
| B2 | **High** ✅ fixed | Web place cards; "How it works" → Data | **For 74% of places, the category under the name is a data source name** | "coffee in Toul Kork" → cards read "overture, Toul Kork" and "foodpanda, Toul Kork". Data tab, "Places by type": overture 8,823, foodpanda 2,194. In English mode some cards show Khmer words (គុយទាវ) in this line. |
| B3 | **High** (intermittent) | Bot voice | **A misheard landmark moved the conversation to Kep** | Voice "Where can I eat pizza near CADT?" was heard as "near CAT" or "near Kat". Once, the AI rewrite turned it into "in Kep" (🔎 *… in Kep* shown), and the next 3 voice questions all answered "nothing like that in Kep". Not reproduced in 3 later tries, but the wrong area stuck to unrelated new questions. |
| B4 | Medium | Bot + web voice | **Speech-to-text is slow, and weaker in Khmer, today** | Both full Gemini models answer 429 (quota exceeded). Every voice message waits for 2 failures before the "lite" model answers: 9 s in English, 16 s in Khmer. "អាម៉ុកជាអ្វី?" was misheard 3 out of 3 times ("អាម្ហូបចិន អ្វី?", "អាម៉ុកជៀសវៃ", …). |
| B5 | Medium | API + bot | **Khmer off-topic questions are searched as food** | "រាជធានីនៃប្រទេសបារាំងជាអ្វី?" (what is the capital of France?) → 15 French restaurants. The same question in English is politely declined. |
| B6 | Medium | Web + bot | **"How do I make it?" after a search is refused** | "lok lak in BKK1" → "how do I make it?" → "I only help you find places to eat in Cambodia, not recipes!" Expected: the lok lak recipe. The same question works after a dish card or a photo. |
| B7 | Medium | Bot | **After "near me", anything typed is taken as a place** | "near me" → "សួស្តី" (hello) → "OK, from សួស្តី": the greeting was placed 245 km away, and the nearest coffee shown was 22.7 km. "cancel" → "I couldn't find 'cancel' on the map". Expected: a greeting or "cancel" leaves the question (a dish name already does). |
| B8 | Low | API + bot (Khmer) | Khmer filler words stay in the search heading | "តើខ្ញុំអាចញ៉ាំគុយទាវនៅឯណា?" → heading "សម្រាប់ “តើ អាចញ៉ាំគុយទាវនៅ”". In English, "where can I eat kuy teav" gives “kuy teav”. The results are correct. |
| B9 | Low | API + bot | The typo "lokluk" is not recognised | "lokluk" → AI small talk ("Lok lak is delicious…") instead of the lok lak card. "kuytiew" and "loklak" work. |
| B10 | Low | API + bot | AI-written replies are slow | Off-topic and gibberish: 15–22 s. "KFC": 13 s. "do they deliver?": 12 s. For comparison, searches take 0.1–1.5 s. |
| B11 | Low | API + bot | A heart "<3" is read as "under $3" | "pizza & pasta <3" → "Our data has no prices for these places, so I could not check that condition." |
| B12 | Low | Data | A Foodpanda parcel-courier listing appears as a restaurant | "pizza near CADT" → result #1, "Pasta Corner Prek Leap", links to a `…-pandasend` page, which is Foodpanda's courier service. |
| B13 | Low | Web | Language and wording gaps | The "How it works" page stays in English when the app is set to Khmer. The sidebar says "Place data from OpenStreetMap", but most places now come from Overture and Foodpanda. |
| B14 | Low | API + bot | Some answers have no lead sentence | "do you know Brown Coffee?" → "can it deliver?" (all 11 branches deliver) → a bare list, with no line like "All 11 deliver:". In the bot, "ខ្ញុំអាចញ៉ាំអាម៉ុកនៅឯណា?" → an AI-written list without the usual heading. |
| B15 | Medium ✅ fixed | Bot + web text, tests | **Examples and tests still assume places outside Phnom Penh** | `/start`, "hi" and "what can you do?" suggest "pizza in Siem Reap", which now answers "nothing like that in Siem Reap". 5 automated tests fail for the same reason (section 2). |

| B16 | Medium ✅ fixed | Bot + web | **A chain named after a dish was explained as the dish** (found while fixing B1) | "do you know The Pizza Company?" → "Yes, I know **Pizza**!…"; "do you know Burger King?" and "what is Burger King?" → what a hamburger is. Expected: the chain's branches. |
| B17 | Low ✅ fixed | Data | **35 kuy teav shops were tagged "tea"** (found while fixing B2) | The Foodpanda scraper matched "tea" inside the address "kuy-teav", so cards for "cheap kuy teav" read "tea". |
| B18 | Low (open) | Bot + web | A chain whose branch names include Khmer text is not treated as named | "do you know Burger King?" → Burger King, then Carl's Jr. and Burger Zone (expected: only the 4 Burger King branches). The branch is called "Burger King - បឹងកេងកង", and the named-place check requires every Khmer word of a name to be in the question. |
| B19 | Medium ✅ fixed | Bot | **Recipe and photo answers in Telegram were always in English** (found while adding `/language`) | "របៀបធ្វើសម្លកកូរ" → "How to make…". The dish card's text and buttons ("What would you like to know?", "How to make it", "Not it?") and "More results" were English only. |

### 1.1 Root cause of B1 (measured)

A place counts as a match when **either** of these holds:
- its keyword score share is at least 0.15, **or**
- its similarity in meaning (MiniLM embeddings) is at least 0.45.

Unrelated places pass on meaning alone:

| Query | Place | Keyword share (min 0.15) | Meaning (min 0.45) |
|---|---|---|---|
| lok lak | Carl's Jr. Burger (Toul Kork) | 0.025 | **0.545** |
| lok lak | Texas Chicken (Toul Kork) | 0.052 | **0.474** |
| kuy teav | KOI Steung Mean Chey | 0.136 | **0.592** ("koy teav" ≈ "KOI") |

Normally the real matches rank above these places. When an area or price filter removes every real match, only these places remain, and they are shown under "Here's what I found for “lok lak” in Toul Kork". The price filter makes this worse, because only 1% of places have a price.

**Suggested fix:** after the filters, if no remaining place has a keyword or menu match, answer "no match", as already happens for Siem Reap. Another option is to require a higher meaning score (about 0.6) from places with no keyword or menu match. Re-run the IR evaluation after the change (section 4).

### 1.2 Root cause of B2

`backend/food_search/api.py` line 222 sets `"kind"` to the first tag of the place. For 11,017 of the 14,842 places, that first tag is a source name: overture (8,823) or foodpanda (2,194).

**Fix:** skip source names (overture, foodpanda, grab, …) when choosing the category, and show nothing if no real category is left.

### 1.3 Fixes made after this QA run (10 Nov)

| Bug | Change | Re-test |
|---|---|---|
| B1 | `search.py`: when the question names a known dish exactly ("lok lak", "kuy teav", "piza" → pizza, "បាយសាច់ជ្រូក"), a place must contain the dish's name, Khmer name or another spelling in its text or menu. Meaning-only matches and broad related words ("beef", "pho") still rank but are no longer enough. Descriptions ("spicy noodle soup") and unknown words keep the looser rule. A price, rating or hours condition is applied only when at least 3 matching places have that value; otherwise the answer says it cannot be checked. | "lok lak in Toul Kork" → "Sorry, our list has nothing like that in Toul Kork yet…". "cheap kuy teav" → kuy teav places + "Our data has no prices for these places…". IR evaluation unchanged overall (hybrid 0.888 / 0.930 / 0.911); "amok" P@5 0.8 → 1.0 |
| B2 | `api.py` `place_kind()`: the category skips data source tags (overture, foodpanda…) and service tags (lunch, takeaway, delivery…), prefers a tag in the reader's language, and shows "restaurant" / "ភោជនីយដ្ឋាន" in the reader's language | English cards: coffee, bakery, chicken, tea, bbq…; Khmer cards: កាហ្វេ, នំប៉័ង, សាច់អាំង…; no source names left (0 of 14,842) |
| B15 | Bot help text, the bot's Telegram profile, greetings and "what can you do?" now say Phnom Penh, with Phnom Penh examples ("pizza in Toul Kork", "coffee in BKK1"), in English and Khmer. The 5 outdated tests use places that exist now (KFC, Mixue, Daun Penh) | All pass |
| B17 | `scrapers/foodpanda_sitemap_scraper.py` matches whole words of the address. In `data/restaurants.csv` the "tea" tag was removed from 33 places where it came only from "teav" (2 places that really sell tea kept it). | Kuy teav cards show "noodle" / "noodles" |
| B16 | `dishes.py` `about_intent()`: after "do you know / what is", other English words besides the dish name ("company", "king") mean a place is named, so it is a search | "do you know The Pizza Company?" → its 13 branches; "do you know about pizza?" and "what's kuy teav like?" still explain the dish |

| B19 + new `/language` | `bot_handlers.py`: `/language` (or `/lang`) offers 🔄 Auto (the default: each answer in the language of the message), 🇬🇧 English and 🇰🇭 ខ្មែរ; `/language kh` sets it at once. A chosen language is used for every answer (searches, follow-ups, dish cards, recipes, photos, voice prompts) and for the bot's own texts and buttons, and that chat's `/` menu switches to it. In Auto mode, recipes and photos now follow the question's language. | `TestTelegramLanguage` (4 tests) |

New tests: `test_a_filter_never_leaves_places_without_the_dish` (2), `test_category_is_never_a_data_source`, 3 chain questions in `test_place_questions_still_search`, and 3 dish questions in `test_what_the_dish_is_and_what_to_ask_next`. Result: **147 passed, 0 failed**.

**Note (10:56):** `data/restaurants.csv` and `data/scraped/brand_menus.json` were rewritten again by another process during this work (235 places now have a price, and all 9 Mixue branches list delivery). With the new data, 3 tests fail: `test_cheap_keeps_the_dish` and `test_cheaper_keeps_dish_and_place` (3+ noodle places now have prices, so "cheap kuy teav" keeps the one under $3: Koi Garden, a pho shop) and `test_detail_only_some_places_have` (no chain left with partial delivery). These need a decision once the data is final (section 1.1); they are not caused by the code changes. With the `/language` tests: 148 passed, 3 failed.

---

## 2. Automated tests

`venv/bin/python -m pytest tests/test_chatbot.py`: **132 passed, 6 failed** (45 s) at the start of QA. After the fixes and the test updates in section 1.3: **147 passed, 0 failed**.

| Failed test | Cause | Action |
|---|---|---|
| `TestSystem::test_config` | Expects more than 15,000 places; the data now has 14,842 (Phnom Penh only) | Update the test to the new data |
| `TestDemo::test_data_overview` | Same as above | Update the test |
| `TestDishSearch::test_named_place_shows_only_that_place` | "9k Foods Chhouk Meas" is no longer in the data | Use a place that still exists |
| `TestConversation::test_follow_up_with_they` | Starts with "coffee in Siem Reap", which now has no places | Use a Phnom Penh area |
| `TestConversation::test_detail_only_some_places_have` | All 11 Brown Coffee branches now list delivery, so there is no "only some" case left | Use another chain (see also B14) |
| `TestFilters::test_cheap_keeps_the_dish` | **Bug B1**: "cheap kuy teav" → KOI Thé | Fix B1 |

All 8 new voice tests in `TestVoice` pass. They check that there are only two Khmer voices, that English numbers are read as words, and that both voices read Khmer and English.

---

## 3. Results by area

### 3.1 API question set (English and Khmer): 74 checks

Each answer was checked for:
- the type of answer;
- the language of the answer;
- whether the top 3 places are relevant;
- no leftover template text (`None`, `nan`, `{name}`);
- response time.

| Group | English | Khmer | Result |
|---|---|---|---|
| Greetings, "who are you", "what can you do" | hi, thank you very much, who are you?, what can you do? | សួស្តី, អរគុណច្រើន, អ្នកជានរណា?, តើអ្នកអាចជួយអ្វីខ្លះ? | 8/8 ✅ Instant, in the right language |
| What a dish is (no places shown) | kuy teav, what is amok?, do you know lok lak?, what is pizza, where does amok come from? | គុយទាវ, អាម៉ុកជាអ្វី?, តើឡុកឡាក់ជាអ្វី | 8/8 ✅ Wikipedia text with its source; Khmer marked "(បកប្រែដោយ AI)" |
| Where to eat | where can I eat kuy teav, pizza near CADT, cheap coffee, lok lak in Toul Kork, noodles open now, sushi rated 4.5+, breakfast under $3, find amok, cheap kuy teav, bubble tea in BKK1, vegetarian food, fried rice in Siem Reap, nom banh chok | ខ្ញុំអាចញ៉ាំគុយទាវនៅឯណា?, ភីហ្សានៅជិតវិមានឯករាជ្យ, កាហ្វេថោក, បាយសាច់ជ្រូកនៅទួលគោក, ខ្ញុំចង់ញ៉ាំ pizza | 16/18 ❌ "lok lak in Toul Kork" and "cheap kuy teav" (B1) |
| Recipes | how to make amok, how long does lok lak take to cook?, ingredients for kuy teav, calories in pizza | របៀបធ្វើអាម៉ុក, ធ្វើគុយទាវប្រើពេលប៉ុន្មាន? | 6/6 ✅ |
| Named places | KFC, Brown Coffee, Koi The, "do u know Shayoo Bite (Toul Sangke)?", 9k Foods Chhouk Meas | – | 5/5 ✅ Shayoo gives exactly 1 place. 9k Foods is no longer in the data, so the Chhouk Meas places are shown |
| Follow-ups | "pizza near CADT" → cheapest? → do they deliver? → phone number of number 1. "what is kuy teav?" → where can I eat it? → any cheaper ones? "lok lak in BKK1" → what about in Toul Kork? → how do I make it? "sushi" → what's the weather today? | "កាហ្វេនៅទួលគោក" → មួយណាថោកជាងគេ? → តើលេខ ១ បើកម៉ោងប៉ុន្មាន? | 12/15 ❌ B1 (twice), B6 |
| Safety and edge cases | capital of France, "ignore previous instructions…", quicksort code, how to make a bomb, ?????, asdfghjkl, 🍜, a 600-character question, `<script>`, PIZZA!!!, kuytiew near me, lokluk, empty message | រាជធានីនៃប្រទេសបារាំងជាអ្វី? | 10/14 ❌ B5, B9, B10 (two slow replies) |

Nine answers failed the first automatic check but are correct on closer reading:
- The sushi and amok places do have those dishes on their menus.
- "kuytiew near me" asks where you are, as it should.
- "fried rice in Siem Reap" honestly says there is nothing there.
- "what is kuy teav?" → "where can I eat it?" works with the dish id the web app sends.
- The Khmer dish name in an English recipe title is intended.
- The `<script>` text is shown as plain words, never run.

### 3.2 Telegram bot: 46 checks

The bot's real handlers were run with stand-in Telegram objects that record every reply. Feedback went to a temporary folder, never to `data/feedback`.

| Feature | Checks | Result |
|---|---|---|
| `/start`, `/app`, `/privacy`, `/voice`, `/model`, `/new`, `/setlocation`, `/stats` (as a non-admin), `/correction` (nothing to correct yet) | 9 | ✅ 9. Texts are bilingual and the Mini App button is shown; `/stats` is refused ("Admins only") |
| Dish card for "kuy teav", "គុយទាវ", "what is amok?" | 3 | ✅ 3. Text in the asker's language, plus 3 buttons: How to make it · Cooking time · Where to eat it |
| Buttons: recipe, cooking time, where to eat it, ➕ More results | 4 | ✅ 4. Steps and times are correct (kuy teav: 6 steps, 2 h 20 min); "More" shows places 6–10 |
| Typed searches, recipes and follow-ups in English and Khmer | 11 | ✅ 8, ❌ 3: B1 (twice), B8. "which one is the cheapest?" correctly says no prices are known |
| "near me" → landmark buttons → tap CADT; share a location; "near me" followed by a dish, a greeting, "cancel" or an area | 6 | ✅ 4, ❌ 2: B7. "Closest first" shows distances (360 m, 420 m…) |
| Photos: lok lak, pizza | 2 | ✅ 2. "Lok lak (96% sure)" and "Pizza (95% sure)" with 3 buttons; 2.1 s for the first photo |
| Voice: English and Khmer question → "How should I answer?" (Khmer buttons for a Khmer question) → reply as text or as voice; tapping again later → "Send the voice message again"; a short Khmer question | 6 | ✅ 3, ❌ 3: B3 (twice), B4 |
| Voice settings: Female / Male | 2 | ✅ 2. Two Khmer voices: Sreymom and Piseth |
| HTML in questions (`<script>…`, `<b>`, `&`) | 3 | ✅ 3. Escaped (`&lt;script&gt;`), so Telegram accepts the message |

### 3.3 Web app (live site in Chrome): 19 checks

| Check | Result |
|---|---|
| Page loads with a greeting, 7 example buttons and the sidebar (About, Appearance, Language, AI model, Voice) | ✅ No console errors |
| "kuy teav" → dish card with a Wikipedia link and 3 follow-up buttons | ✅ |
| "where can I eat it?" → 5 kuy teav places + "Show more" | ✅ |
| Place card layout: number, name, area, open now, rating, hours, Directions / Foodpanda / Website | ✅ |
| Place card category text | ❌ B2 |
| Switching to Khmer: labels, buttons, placeholder and follow-up buttons all in Khmer | ✅ |
| "តើអាម៉ុកជាអ្វី?" → Khmer dish card marked "(បកប្រែដោយ AI)" | ✅ |
| Dark mode | ✅ Readable, good contrast |
| `/` command menu (/correction, /new, /photo) with Khmer descriptions | ✅ |
| Phone size (390 × 780): no sideways scrolling, buttons wrap, the input stays at the bottom | ✅ No element is wider than the screen |
| A Khmer search at phone size: the cards fit | ✅ |
| Photo in chat: preview before sending, then "Pizza (95%)" in Khmer with buttons | ✅ |
| Voice preview ("Hear the voice") | ✅ `/api/voice/speak` returns 200 |
| Answers render safely: built as React elements, links only http/https, never raw HTML | ✅ (code review of `frontend/src/components/Markdown.tsx`) |
| "How it works" → Ask: 3 steps, rows given to the model, the prompt | ✅ The AI answer took 6.9 s |
| "How it works" → Compare retrieval ("carry nodle") | ✅ |
| "How it works" → Data and Photo (lok lak 95.5%, top 5, the 224×224 input) | ✅ |
| "How it works" in Khmer mode | ❌ English only (B13) |
| Sidebar data credit | ❌ Says OpenStreetMap only (B13) |

Not testable by automation: recording with the microphone, which needs a real microphone. The endpoint it calls, `/api/voice/transcribe`, was tested directly (section 3.4).

### 3.4 Voice: 7 checks

| Check | Result |
|---|---|
| Only two voices, both Khmer (female Sreymom, male Piseth), each reading Khmer **and** English | ✅ `TestVoice` and live `/api/voice/speak` |
| English numbers read as words ("10 pm", "$5.50", phone numbers); digits after Khmer words read in Khmer | ✅ |
| Transcribing English ("Where can I eat kuy teav near the Russian Market?") | ✅ Exact |
| Transcribing Khmer ("តើខ្ញុំអាចញ៉ាំបាយសាច់ជ្រូកនៅឯណា?") | ✅ Close: "…ដែលណា?" means the same |
| Transcribing a short Khmer question ("អាម៉ុកជាអ្វី?") | ❌ Misheard 3 out of 3 times (B4) |
| The spoken word "CADT" | ❌ Heard as "CAT" or "Kat"; once led to B3 |
| Speed of transcription | ❌ 9.2 s in English, 16.2 s in Khmer (B4) |

### 3.5 Speed (in process, on the same machine as the live server)

| Answer type | Typical time |
|---|---|
| Greeting, dish card, recipe, follow-up answered from the data | under 0.05 s |
| Search (BM25 + embeddings) | 0.1–1.5 s |
| Photo recognition | 2–3 s for the first photo, then faster |
| Spoken answer (text → speech) | 1.5–5 s |
| AI-written answer (Gemini 3.5 Flash Lite) | 7–22 s (B10) |
| Speech → text | 9–16 s today (B4) |

---

## 4. Retrieval quality (IR evaluation, re-run today)

The test set has 50 judged questions (`data/eval/queries.csv`), scored on the top 5 results:

| Method | P@5 | MRR | nDCG@5 | 2026-11-09 (previous data): P@5 / MRR / nDCG@5 |
|---|---|---|---|---|
| BM25 + fuzzy | 0.816 | 0.860 | 0.840 | 0.852 / 0.910 / 0.889 |
| Embeddings | 0.452 | 0.495 | 0.446 | 0.468 / 0.509 / 0.467 |
| **Hybrid (app)** | **0.888** | **0.930** | **0.911** | 0.948 / 1.000 / 0.987 |

The hybrid search is still the best of the three methods. After the fixes the scores are unchanged (hybrid 0.888 / 0.930 / 0.911), and "amok" improved from P@5 0.8 to 1.0.

The notebook's own evaluation (`food_search.ipynb`, re-run after the fixes, saved to `results/eval_results.csv`) gives **Hybrid 0.945 / 0.989 / 0.970** (P@5 / MRR / nDCG@5), compared with BM25 0.868 / 0.915 / 0.894 and embeddings 0.481 / 0.527 / 0.475. The two evaluations are computed differently, so compare each one only with its own earlier run (the notebook gave 0.948 / 1.000 / 0.987 on 9 Nov).

**The drop is not a fair comparison yet.** 173 of the 1,955 places judged relevant are no longer in the data. The newly added places (Foodpanda menus, brand menus) were never judged, so they count as wrong even when they are right. Before reporting these numbers, judge the new places with `scrapers/eval_build.py`, then run the evaluation again.

---

## 5. Data coverage (from the "Data" tab)

14,842 places in 15 areas of Phnom Penh. Share of places that have each field:

| Field | Share | Effect on answers |
|---|---|---|
| Area | 100% | Area searches work |
| Website or Facebook | 92% | Most cards have a link |
| Map location | 85% | "Near me" and distances work for most places |
| English / Khmer dish name | 77% / 76% | |
| Opening hours | 6% | "open now" can check only a few places (the answer says so) |
| Phone | 3% | "phone number of number 1" is usually "not in our data" |
| Price | 1% | "cheap" and "under $3" can rarely be checked, which makes B1 worse |
| Rating | 1% | "rated 4.5+" can rarely be checked |

---

## 6. Previously fixed bugs (still covered by tests)

The 2026-11-09 report (in git: `git show HEAD:docs/testing-report.md`) lists bugs 1–12, all fixed and covered by tests:
- Khmer small talk treated as a search;
- gibberish answered with random places;
- a rate limit that blocked normal conversations;
- Khmer names of international dishes not recognised;
- prompt injections and off-topic questions searched as food;
- ratings not understood;
- link codes searchable as words;
- a lost place in follow-up questions;
- place names containing off-topic words;
- "weather today" treated as a search;
- typos;
- guessed lok lak labels.

Fixed since then:

| # | Bug | Fix | Test |
|---|---|---|---|
| 13 | "Shayoo Bite (Toul Sangke)" listed 4 unrelated places | Named places are matched against the whole question, not only the words left after removing the area | `test_named_place_with_its_area_in_the_name` |
| 14 | "can it deliver?" answers were terse and unclear when several places were shown | Clear sentences. When only some places deliver, the answer lists those places and the rest in one line | `test_delivery_question_is_answered_yes_with_the_link`, `test_detail_only_some_places_have` |
| 15 | "do u know amok?" showed seafood places, and menus were not searched | Dish questions explain the dish; menu items are searched, with a fair minimum score | `test_dish_on_a_menu_is_found` |
| 16 | "kuy teav" and "what is kuy teav?" listed restaurants | The dish is explained from `data/dish_knowledge.csv` (155 dishes); restaurants appear only after "where can I eat…" | `TestDishQuestions` (19 tests) |
| 17 | Mixed-language answers switched between a Khmer voice and an English voice | Two Khmer voices read everything; numbers in English parts are read as words | `TestVoice` (8 tests) |

---

## 7. How the testing was done

1. **Automated tests:** `venv/bin/python -m pytest tests/test_chatbot.py` (138 tests). The results are also saved in `tests/last_run.json`.
2. **Question set:** 74 questions and follow-ups were sent to the app's real code and today's data, in process, with the rate limit off and feedback written to a temporary folder. Every answer was checked automatically, then each failure was read by hand.
3. **Telegram bot:** the bot's real handlers (`backend/food_search/bot_handlers.py`) were driven with stand-in Telegram messages, button taps, a location, two photos and four voice notes made with the app's own voices. Nothing was sent to Telegram.
4. **Web app:** the live site in Chrome. This covered typed questions in both languages, buttons, settings, a photo upload, the voice preview and all four "How it works" tabs. A 390-pixel phone-size frame was checked for sideways overflow.

**Not covered:** these need a real phone, so test them by hand before a demo:
- the Mini App inside the Telegram phone app;
- a real microphone recording in the browser;
- the browser's location permission prompt;
- Safari on iPhone.
