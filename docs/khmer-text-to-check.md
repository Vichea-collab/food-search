# Khmer text to check (written by Claude, NOT yet read by a Khmer speaker)

Please read each line and mark it OK or write the correction. Everything is shown in the app to Khmer users, so a wrong or odd word matters more than a missing one.

## A. Khmer descriptions (5 dishes) — `data/dish_knowledge.csv`, column `about_kh`

The English is the source (from Klean Nham, or Wikipedia CC BY-SA for chha trob and num akor). The Khmer is my translation.

### ភ្លាសាច់គោ — Beef salad (plea sach ko) (`kh_beef_salad`)

- English: Thin slices of beef cured in lime juice, tossed with lemongrass, herbs and bean sprouts.
- Khmer: សាច់គោហាន់ស្តើងៗ ត្រាំក្នុងទឹកក្រូចឆ្មា លាយជាមួយគ្រៃ ជីរនានា និងសណ្តែកបណ្តុះ។
- Look at: «ហាន់ស្តើងៗ» (sliced thin), «ត្រាំក្នុងទឹកក្រូចឆ្មា» (cured in lime juice: «ជ្រលក់»/«ស្ល» more usual?), «សណ្តែកបណ្តុះ» (bean sprouts).
- [ ] OK   [ ] corrected to: …

### ក្តាមឆាម្រេចខ្ចី — Cha kdam kchey (Kampot green pepper crab) (`kh_cha_kdam_kampot`)

- English: World-famous coastal Cambodian delicacy: sweet sea crab wok-fried with fiery bunches of fresh green Kampot pepper.
- Khmer: ម្ហូបឆ្នេរសមុទ្រកម្ពុជាដ៏ល្បីល្បាញពាសពិភពលោក៖ ក្តាមសមុទ្រផ្អែមៗ ឆាក្នុងខ្ទះជាមួយម្រេចខ្ចីកំពតស្រស់ៗដែលហឹរ។
- Look at: Tone: «ល្បីល្បាញពាសពិភពលោក» (world-famous) is fine for a menu blurb? «ម្រេចខ្ចី» is fresh green pepper.
- [ ] OK   [ ] corrected to: …

### មីកូឡា — Mee kola (Battambang Kola-style noodles) (`kh_mee_kola`)

- English: Heritage noodle dish from Battambang: steamed noodles tossed in dark soy dressing, topped with crispy tofu, boiled eggs, dried shrimp, and pickles.
- Khmer: ម្ហូបមីបុរាណមកពីបាត់ដំបង៖ មីចំហុយលាយជាមួយទឹកស៊ីអ៊ីវខ្មៅ ញាត់ដោយតៅហ៊ូបំពង ពងស្ងោរ បង្គាស្ងួត និងបន្លែជ្រក់។
- Look at: «ញាត់» (topped with) is normally «stuff/pack into»: would «ដាក់លើ» or «ពាសដោយ» be more natural? «ទឹកស៊ីអ៊ីវខ្មៅ» (dark soy), «បង្គាស្ងួត» (dried shrimp), «បន្លែជ្រក់» (pickles).
- [ ] OK   [ ] corrected to: …

### ឆាត្រប់ — Chha trob (chargrilled eggplant with pork) (`kh_chha_trob`)

- English: Chha trob or dot trob (ដុតត្រប់) is a Cambodian dish made out of chargrilled eggplants with minced pork and fermented soybeans stir-fried in oyster sauce and garnished with spring onions. It is a typical dish from the Kampuchea Krom region in Mekong Delta.
- Khmer: ឆាត្រប់ ឬដុតត្រប់ គឺជាម្ហូបខ្មែរធ្វើពីត្រប់ដុត ឆាជាមួយសាច់ជ្រូកកិន និងសណ្តែកសៀងផ្អាប់ ក្នុងទឹកខ្យង រួចរោយស្លឹកខ្ទឹម។ វាជាម្ហូបប្រពៃណីរបស់តំបន់កម្ពុជាក្រោម នៅដីសណ្តទន្លេមេគង្គ។
- Look at: «ទឹកខ្យង» is used for oyster sauce: is that the usual word, or is it «ទឹកស៊ុបខ្យង» / «ទឹកអ៊ីស្ទ័រ»? Also check «ត្រប់» (eggplant), «សណ្តែកសៀងផ្អាប់» (fermented soybeans), «ដីសណ្តទន្លេមេគង្គ» (Mekong delta).
- [ ] OK   [ ] corrected to: …

### នំអាកោរ — Num akor (steamed fermented rice cake) (`kh_num_akor`)

- English: Num akor or num ah kor is a Cambodian steamed rice cake made from fermented rice flour.
- Khmer: នំអាកោរ ឬនំអាកោ គឺជានំអង្ករចំហុយរបស់កម្ពុជា ធ្វើពីម្សៅអង្ករដែលបានផ្អាប់។
- Look at: «ដែលបានផ្អាប់» (fermented) and the two spellings «នំអាកោរ / នំអាកោ».
- [ ] OK   [ ] corrected to: …

## B. Three home recipes — `data/recipes_khmer.csv`

The recipe text is English only (the app shows the Khmer name `dish_name_kh`). Nothing was copied from a source: I wrote them in the style of the other recipes, with typical amounts. Please check the NAME in Khmer and whether the dish is made like this.

### បាញ់ឆែវ — Banh chhev (crispy crepe) (`kh_banh_chhev`)

Large crispy golden turmeric rice crepe filled with minced pork, shrimp, and bean sprouts. Eaten wrapped in lettuce and fresh herbs, dipped in sweet garlic fish sauce with crushed peanuts.

Ingredients:
- Batter: 150 g rice flour, 1 tsp ground turmeric, ½ tsp salt, 1 tsp sugar, 250 ml coconut milk, 250 ml water
- 200 g minced pork
- 150 g peeled shrimp
- 2 cloves garlic, minced
- 1 small onion, sliced
- 150 g bean sprouts
- 1 tbsp fish sauce
- Vegetable oil, for the pan
- To serve: lettuce leaves, mint, basil, coriander and cucumber slices
- Dip: 3 tbsp fish sauce, 3 tbsp water, 2 tbsp sugar, 1 tbsp lime juice, 2 cloves garlic (minced), 1 red chilli (sliced), 1 tbsp crushed roasted peanuts

Steps:
1. Whisk the rice flour, turmeric, salt and sugar with the coconut milk and water into a thin, smooth batter. Let it rest for 15 minutes.
2. Make the dip: stir the sugar, fish sauce, water and lime juice until the sugar dissolves, then add the garlic, chilli and peanuts.
3. Fry the garlic and onion in 1 tbsp oil, add the pork and cook until done, then add the shrimp until pink. Season with the fish sauce and set aside.
4. Heat a non-stick pan over medium-high heat with a little oil. Pour in a ladle of batter and swirl it into a thin layer.
5. Scatter some pork, shrimp and bean sprouts over one half, cover and cook for 1–2 minutes, then uncover and cook until the crepe is golden and crisp.
6. Fold the crepe over the filling and slide it onto a plate. Repeat with the rest of the batter.
7. Break the crepe into pieces, wrap them in lettuce with the herbs and dip in the sauce.

25 min prep, 25 min cook, serves 4, ~ kcal (estimate).
- [ ] name OK   [ ] recipe OK   [ ] changes: …

### បបរ — Borbor (rice porridge) (`kh_borbor`)

Silky rice congee simmered with chicken or pork broth, served with shredded chicken or pork, crispy garlic, cilantro, bean sprouts and lime.

Ingredients:
- 200 g jasmine rice, rinsed
- 2 litres water (or chicken stock)
- 500 g bone-in chicken thighs or drumsticks
- 3 cm ginger, sliced
- 1 tsp salt
- 1 tbsp fish sauce
- 4 cloves garlic, thinly sliced
- 2 tbsp vegetable oil
- To serve: spring onion, coriander, bean sprouts, lime wedges, ground black pepper
- Fried dough sticks (cha kway), optional

Steps:
1. Bring the water to a boil with the ginger and chicken. Skim off the foam and simmer for 20 minutes, then lift out the chicken.
2. Add the rice to the broth and simmer on low heat for 40–50 minutes, stirring now and then, until the grains break down and the porridge is thick and silky. Add a little hot water if it gets too thick.
3. Shred the chicken meat, discarding the skin and bones.
4. Season the porridge with the salt and fish sauce.
5. Fry the garlic in the oil until golden, then drain.
6. Ladle the porridge into bowls and top with the chicken, fried garlic, spring onion, coriander, bean sprouts and pepper. Serve with lime and cha kway.

15 min prep, 70 min cook, serves 4, ~ kcal (estimate).
- [ ] name OK   [ ] recipe OK   [ ] changes: …

### ឆាក្តៅ — Chha kdao (holy basil stir fry) (`kh_chha_kdao`)

Fiery wok-tossed beef or chicken stir-fry with yellow lemongrass kroeung, bird's eye chillies, yardlong beans, green peppercorns and holy basil.

Ingredients:
- 400 g beef sirloin (or chicken), thinly sliced
- 1½ tbsp oyster sauce
- Kroeung: 2 stalks lemongrass, thinly sliced, 3 cm galangal, sliced, 3 cm fresh turmeric (or 1 tsp ground), 4 kaffir lime leaves, stems removed, 4 cloves garlic, 3 shallots
- 3 tbsp vegetable oil
- 150 g yardlong beans, cut into 4 cm pieces
- 4 bird's eye chillies, lightly bruised
- 1 tbsp fresh green peppercorns (optional)
- 1 tbsp fish sauce
- 1 tsp palm sugar
- 2 tbsp water
- 1 large handful holy basil leaves
- Steamed jasmine rice, to serve

Steps:
1. Pound or blend the kroeung ingredients into a coarse paste.
2. Mix the sliced meat with the oyster sauce and leave it for 15 minutes.
3. Heat the oil in a wok over high heat and fry the kroeung paste for 1 minute until fragrant.
4. Add the meat and sear for 2–3 minutes, stirring, until it changes colour.
5. Add the beans, chillies, peppercorns, fish sauce, palm sugar and water, and toss for 2–3 minutes until the beans are just tender.
6. Add the basil, toss for 20 seconds until wilted and serve at once with rice.

20 min prep, 10 min cook, serves 3, ~ kcal (estimate).
- [ ] name OK   [ ] recipe OK   [ ] changes: …

## When it is checked

Change `about_kh_by` in `data/dish_knowledge.csv` for the five dishes from `machine translation (...)` to `checked by <name/role>, <date>`, and the app can drop the "machine translation" label.
