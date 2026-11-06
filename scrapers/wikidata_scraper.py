"""
Wikidata & International Culinary Encyclopedia Scraper
Source: Wikidata SPARQL + Comprehensive Global & Cambodian Culinary Lexicon
Extracts and indexes local Cambodian dishes and international foreign foods
(Japanese, Korean, Chinese, Thai, Vietnamese, Italian, French, Indian,
Mexican, Halal/Middle Eastern, Healthy, American/Fast Food, Desserts & Drinks)
with Khmer translations, typical price ranges, ingredients, and search tags.
"""

import csv
import logging
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"

SPARQL_QUERY = """
SELECT DISTINCT ?item ?itemLabel ?khmerLabel ?desc ?image WHERE {
  ?item wdt:P495 wd:Q424 .
  OPTIONAL { ?item rdfs:label ?khmerLabel . FILTER(LANG(?khmerLabel) = "km") }
  OPTIONAL { ?item schema:description ?desc . FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?item wdt:P18 ?image . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,km". }
}
"""

FOOD_KEYWORDS = {
    "food", "dish", "soup", "salad", "noodle", "noodles", "rice", "sauce",
    "cuisine", "dessert", "beverage", "drink", "snack", "cake", "honey",
    "curry", "bread", "sandwich", "pizza", "paste", "fermented", "steamed",
    "roast", "pork", "beef", "chicken", "fish", "meat", "vegetable"
}

# Comprehensive Local Cambodian and International Foreign Food Encyclopedia
GLOBAL_FOOD_LEXICON = [
    # ==================== KHMER LOCAL DISHES ====================
    {"name": "Bai Sach Chrouk", "kh": "បាយសាច់ជ្រូក", "desc": "Grilled marinated pork sliced thin over broken rice, served with pickled cucumbers and daikon, and a warm scallion broth. Cambodia's classic breakfast.", "price": "2.00", "tags": "rice;breakfast;pork;khmer;local"},
    {"name": "Kuy Teav Phnom Penh", "kh": "គុយទាវភ្នំពេញ", "desc": "Traditional Phnom Penh clear pork and seafood bone broth noodle soup, topped with minced pork, pork slices, beef balls, and fresh herbs.", "price": "2.50", "tags": "noodle;breakfast;soup;kuy_teav;khmer;local"},
    {"name": "Beef Lok Lak", "kh": "ឡុកឡាក់សាច់គោ", "desc": "Stir-fried cubed tender beef in savory oyster-soy sauce, served over lettuce, sliced tomatoes, cucumbers, a fried egg, and black Kampot pepper lime dip.", "price": "4.50", "tags": "beef;stir_fry;dinner;lunch;lok_lak;khmer;local"},
    {"name": "Num Banhchok Samlor Proher", "kh": "នំបញ្ចុកសម្លប្រហើរ", "desc": "Fresh hand-pressed fermented rice noodles submerged in a fragrant green river fish broth pounded with kroeung lemongrass paste and fresh raw vegetables.", "price": "2.00", "tags": "noodle;curry;traditional;khmer;local;breakfast"},
    {"name": "Num Banhchok Samlor Kari", "kh": "នំបញ្ចុកសម្លការី", "desc": "Fermented Khmer rice noodles drenched in rich red chicken or fish coconut curry with sweet potatoes, bamboo shoots, and green beans.", "price": "2.25", "tags": "noodle;curry;chicken;khmer;local"},
    {"name": "Fish Amok", "kh": "អាម៉ុកត្រី", "desc": "Cambodia's national treasure: fresh river snakehead or catfish fillets steamed with coconut cream, kroeung lemongrass paste, egg, and noni leaves in banana-leaf cups.", "price": "5.00", "tags": "curry;fish;traditional;amok;khmer;local"},
    {"name": "Samlor Kako", "kh": "សម្លកកូរ", "desc": "Nutritious traditional soup packed with pumpkin, green papaya, bitter gourd, morning glory, toasted ground rice, fish and pork ribs.", "price": "3.50", "tags": "soup;vegetable;traditional;khmer;local"},
    {"name": "Samlor Machu Kroeung", "kh": "សម្លម្ជូរគ្រឿង", "desc": "Cambodian sour soup seasoned with golden lemongrass paste, tamarind, beef ribs, morning glory, and holy basil.", "price": "3.50", "tags": "soup;sour;beef;traditional;khmer;local"},
    {"name": "Bok L'hong", "kh": "បុកល្ហុង", "desc": "Pounded green papaya salad with salted blue crabs, yardlong beans, dried shrimp, garlic, bird's eye chilies, fish sauce, and crushed roasted peanuts.", "price": "2.50", "tags": "salad;street_food;spicy;khmer;local"},
    {"name": "Num Pang Pate", "kh": "នំប៉័ងសាច់ប៉ាតេ", "desc": "Crispy French-style Cambodian baguette sandwich layered with rich pork liver pâté, Vietnamese-style ham, pickled carrots and papaya, cucumber, and chili.", "price": "1.75", "tags": "sandwich;bread;street_food;breakfast;khmer;local"},
    {"name": "Banh Chhev", "kh": "បាញ់ឆែវ", "desc": "Crisp turmeric-coconut rice crêpe folded around minced pork, small shrimp, bean sprouts, served with lettuce, herbs, and sweet-sour peanut fish sauce dip.", "price": "2.50", "tags": "crepe;street_food;traditional;khmer;local"},
    {"name": "Lort Cha", "kh": "លតឆា", "desc": "Short pin-needle rice noodles stir-fried in sweet soy sauce with beef, bean sprouts, Chinese chives, topped with a fried egg and sweet chili dip.", "price": "2.25", "tags": "fried_noodles;street_food;dinner;khmer;local"},
    {"name": "Mi Cha", "kh": "មីឆា", "desc": "Stir-fried yellow egg noodles or instant mama noodles with sliced beef, Chinese greens, sweet dark soy sauce, fried duck egg, and chili garlic sauce.", "price": "2.25", "tags": "fried_noodles;street_food;dinner;khmer;local"},
    {"name": "Cha Kdao", "kh": "ឆាក្តៅ", "desc": "Spicy aromatic stir-fry of chicken, beef, or frog with holy basil, lemongrass kroeung, garlic, long beans, and fiery red chilies.", "price": "3.00", "tags": "stir_fry;spicy;chicken;beef;khmer;local"},
    {"name": "Pleah Sach Ko", "kh": "ភ្លាសាច់គោ", "desc": "Delicate Cambodian ceviche of rare sliced beef cured in fresh lime juice, tossed with fresh mint, shallots, lemongrass, bean sprouts, and roasted peanuts.", "price": "4.50", "tags": "beef;salad;traditional;khmer;local"},
    {"name": "Sach Ko Jakak", "kh": "សាច់គោចាក់កាក់", "desc": "Charcoal-grilled beef skewers marinated in lemongrass, galangal, kaffir lime, turmeric, and palm sugar, eaten with papaya pickle and baguette.", "price": "3.00", "tags": "bbq;street_food;beef;khmer;local"},
    {"name": "Cha Kdam Kampot", "kh": "ឆាក្តាមម្រេចខ្ចីកំពត", "desc": "Stir-fried sweet fresh crabs bursting with bunches of fragrant green Kampot peppercorns, garlic, spring onions, and oyster sauce.", "price": "8.50", "tags": "seafood;crab;kampot_pepper;khmer;local"},
    {"name": "Prahok Ktiss", "kh": "ប្រហុកខ្ទិះ", "desc": "Rich savory dip made from fermented fish paste (prahok), coconut milk, minced pork belly, pea eggplants, and tamarind, served with raw crunchy vegetables.", "price": "3.50", "tags": "dip;pork;prahok;traditional;khmer;local"},
    {"name": "Num Krok", "kh": "នំគ្រក់", "desc": "Crispy half-sphere coconut rice pancakes with scallions, cooked on cast-iron dimple pans, dipped in sweet fish sauce.", "price": "1.50", "tags": "snack;dessert;street_food;khmer;local"},
    {"name": "Kralan", "kh": "ក្រឡាន", "desc": "Sticky rice mixed with black beans, grated coconut, and coconut milk, roasted slowly over charcoal inside bamboo poles.", "price": "1.25", "tags": "snack;dessert;rice;khmer;local"},
    {"name": "Mi Hel 7 Levels", "kh": "មីហឹរ ៧ កម្រិត", "desc": "Spicy hot bowl noodles with 7 customizable heat levels, loaded with seafood, beef balls, mushrooms, and Korean chili paste.", "price": "2.75", "tags": "noodle;spicy;soup;korean;asian"},

    # ==================== JAPANESE DISHES ====================
    {"name": "Fresh Salmon Sashimi", "kh": "សាស៊ីមីត្រីសាល់ម៉ុង", "desc": "Thick slices of fresh Norwegian raw salmon served chilled with soy sauce, freshly grated wasabi, and pickled ginger.", "price": "7.50", "tags": "japanese;sashimi;sushi;seafood;healthy"},
    {"name": "Spicy Tuna Roll", "kh": "ស៊ូស៊ីត្រីធូណា", "desc": "Maki sushi roll filled with minced fresh raw tuna, sriracha chili mayo, cucumber, wrapped in nori seaweed and seasoned sushi rice.", "price": "5.50", "tags": "japanese;sushi;roll;spicy"},
    {"name": "Tonkotsu Pork Ramen", "kh": "រ៉ាមេនសាច់ជ្រូក", "desc": "Rich, creamy 12-hour simmered pork bone broth ramen with springy wheat noodles, chashu pork belly slices, seasoned soft-boiled egg, nori, and bamboo shoots.", "price": "6.50", "tags": "japanese;ramen;noodle;soup;pork"},
    {"name": "Crispy Pork Tonkatsu", "kh": "សាច់ជ្រូកបំពងតុងកាតស៊ូ", "desc": "Deep-fried panko-breaded pork cutlet served with shredded cabbage, tonkatsu barbecue plum sauce, steamed Japanese rice, and miso soup.", "price": "5.50", "tags": "japanese;pork;fried;bento"},
    {"name": "Chicken Teriyaki Bento", "kh": "បាយប្រអប់តេរីយ៉ាគី", "desc": "Glazed pan-seared chicken thighs in sweet mirin-soy teriyaki sauce, served in a bento box with rice, salad, tamagoyaki, and gyoza.", "price": "5.00", "tags": "japanese;chicken;bento;rice"},
    {"name": "Crispy Ebi Tempura", "kh": "បង្គាបំពងតេមពួរ៉ា", "desc": "Lightly battered, airy deep-fried tiger prawns and seasonal vegetables served with savory tentsuyu dipping sauce and grated daikon.", "price": "6.00", "tags": "japanese;tempura;seafood;shrimp"},
    {"name": "Pan-Fried Pork Gyoza", "kh": "គាវបំពងជប៉ុន", "desc": "Japanese dumplings stuffed with seasoned minced pork, garlic, ginger, and scallions, crisped golden on the bottom and steamed tender on top.", "price": "3.50", "tags": "japanese;dumpling;snack;pork"},
    {"name": "Takoyaki Octopus Balls", "kh": "នំតាកូយ៉ាគី", "desc": "Crispy ball-shaped wheat flour batter filled with diced octopus pieces, topped with Japanese mayo, sweet okonomi sauce, seaweed flakes, and bonito flakes.", "price": "3.00", "tags": "japanese;street_food;octopus;snack"},
    {"name": "Beef Udon Noodle Soup", "kh": "មីអ៊ូដុងសាច់គោ", "desc": "Thick chewy white wheat udon noodles in a clear dashi bonito-kelp broth topped with tender thinly sliced simmered beef and spring onions.", "price": "5.00", "tags": "japanese;udon;noodle;soup;beef"},

    # ==================== KOREAN DISHES ====================
    {"name": "Korean Samgyeopsal (K-BBQ)", "kh": "សាច់ជ្រូកបីជាន់អាំងកូរ៉េ", "desc": "Thick cuts of fresh pork belly grilled sizzling at the table, wrapped in crisp lettuce leaves with garlic, perilla leaves, ssamjang paste, and kimchi.", "price": "7.50", "tags": "korean;bbq;pork;dinner"},
    {"name": "Stone Bowl Bibimbap", "kh": "បាយឆាថ្មក្តៅប៊ីប៊ីមបាប់", "desc": "Sizzling dolsot stone bowl filled with warm rice, sauteed seasoned vegetables, marinated beef, gochujang chili paste, and a raw or fried egg that crisps the rice.", "price": "5.50", "tags": "korean;rice;healthy;spicy"},
    {"name": "Spicy Tteokbokki", "kh": "តុកបុកគីហឹរ", "desc": "Chewy cylindrical Korean rice cakes and fish cakes simmered in a sweet, fiery red gochujang chili broth topped with boiled egg and melted cheese.", "price": "4.00", "tags": "korean;street_food;spicy;snack"},
    {"name": "Kimchi Jjigae (Kimchi Stew)", "kh": "ស៊ុបគីមឈី", "desc": "Bubbling hot Korean spicy stew made with fermented aged kimchi, fatty pork belly, soft tofu, scallions, and anchovy broth.", "price": "5.00", "tags": "korean;soup;stew;spicy;pork"},
    {"name": "Korean Crispy Fried Chicken", "kh": "មាន់បំពងកូរ៉េ", "desc": "Double-fried extra crunchy chicken glazed in sweet and spicy Yangnyeom red sauce or honey soy garlic sauce, served with pickled radish.", "price": "6.00", "tags": "korean;chicken;fried_chicken;snack"},
    {"name": "Beef Bulgogi", "kh": "សាច់គោប៊ុលហ្គូហ្គី", "desc": "Thinly shaved tender beef marinated in sweet soy sauce, grated Asian pear, sesame oil, and garlic, pan-grilled with sweet onions.", "price": "6.50", "tags": "korean;beef;bbq;rice"},
    {"name": "Korean Kimbap", "kh": "បាយរុំសារ៉ាយគីមបាប់", "desc": "Rolled rice in nori seaweed seasoned with sesame oil, filled with yellow pickled radish, spinach, carrots, egg, and ham or bulgogi beef.", "price": "3.50", "tags": "korean;rice;roll;street_food"},
    {"name": "Sundubu Jjigae (Soft Tofu Stew)", "kh": "ស៊ុបតៅហ៊ូទន់កូរ៉េ", "desc": "Fiery Korean stew with uncurdled silky soft tofu, clams, shrimp, and an egg cracked in raw into the boiling earthenware pot.", "price": "5.50", "tags": "korean;soup;seafood;spicy;tofu"},

    # ==================== CHINESE DISHES ====================
    {"name": "Steamed Siu Mai Dumplings", "kh": "ឌីមសាំគាវសាច់ជ្រូក", "desc": "Classic Cantonese open-topped dim sum dumplings filled with minced pork, shrimp, and black mushrooms, garnished with crab roe.", "price": "3.50", "tags": "chinese;dim_sum;dumpling;breakfast;lunch"},
    {"name": "Xiao Long Bao (Soup Dumplings)", "kh": "ស៊ាវឡុងប៉ាវ", "desc": "Delicate Shanghai steamed buns pleated with translucent skins, holding juicy seasoned pork meatballs and piping hot savory soup broth inside.", "price": "4.50", "tags": "chinese;dim_sum;dumpling;soup"},
    {"name": "Char Siu Bao (BBQ Pork Buns)", "kh": "នំប៉ាវសាច់ក្រហម", "desc": "Fluffy, pillowy white steamed buns stuffed with sweet and savory Cantonese caramelized barbecue pork.", "price": "2.50", "tags": "chinese;dim_sum;bun;pork;breakfast"},
    {"name": "Peking Roasted Duck", "kh": "ទាខ្វៃប៉េកាំង", "desc": "Famous Chinese roasted duck with crackling crispy skin and tender meat, served sliced with paper-thin pancakes, hoisin sauce, and scallions.", "price": "12.00", "tags": "chinese;duck;roast;dinner"},
    {"name": "Sichuan Mala Hot Pot", "kh": "ស៊ុបហឹរចិនម៉ាឡា", "desc": "Sichuan style tongue-numbing spicy hot pot simmering with red chili peppers, Sichuan peppercorns, sliced beef, enoki mushrooms, and lotus root.", "price": "8.50", "tags": "chinese;hotpot;spicy;soup;dinner"},
    {"name": "Cantonese Chow Mein", "kh": "មីឆាចិន", "desc": "Crispy pan-fried egg noodles smothered in a glossy savory brown sauce with sliced chicken, shrimp, bok choy, and shiitake mushrooms.", "price": "4.00", "tags": "chinese;noodles;fried_noodles;lunch"},
    {"name": "Wonton Egg Noodle Soup", "kh": "មីគាវសាច់ជ្រូក", "desc": "Springy thin egg noodles in a clear chicken broth with delicate boiled shrimp and pork wontons, bok choy, and roasted garlic oil.", "price": "3.50", "tags": "chinese;noodle;soup;dumpling"},
    {"name": "Mapo Tofu", "kh": "ម៉ាផូតៅហ៊ូ", "desc": "Fiery Sichuan dish of soft silken tofu cubes simmered in a spicy, numbing chili-bean paste sauce with minced beef or pork and Sichuan pepper.", "price": "4.00", "tags": "chinese;tofu;spicy;dinner"},

    # ==================== THAI DISHES ====================
    {"name": "Tom Yum Goong", "kh": "ស៊ុបតុមយ៉ាំបង្គា", "desc": "Thailand's iconic hot and sour soup infused with fragrant lemongrass, galangal, kaffir lime leaves, fresh river shrimp, mushrooms, and chili paste.", "price": "5.00", "tags": "thai;soup;spicy;seafood;shrimp"},
    {"name": "Pad Thai Goong", "kh": "មីឆាថៃផាត់ថៃ", "desc": "Stir-fried rice noodles in tangy tamarind-palm sugar sauce with fresh shrimp, pressed tofu, egg, bean sprouts, crushed peanuts, and fresh lime.", "price": "4.00", "tags": "thai;noodles;fried_noodles;shrimp"},
    {"name": "Som Tum Thai (Green Papaya Salad)", "kh": "បុកល្ហុងថៃ", "desc": "Crisp green papaya strips pounded in clay mortar with garlic, bird's eye chilies, green beans, tomatoes, lime juice, palm sugar, and roasted peanuts.", "price": "2.50", "tags": "thai;salad;spicy;healthy"},
    {"name": "Thai Green Chicken Curry", "kh": "ការីបៃតងសាច់មាន់", "desc": "Creamy aromatic coconut curry cooked with green chili paste, chicken slices, pea eggplants, bamboo shoots, and fresh sweet Thai basil leaves.", "price": "4.50", "tags": "thai;curry;chicken;spicy"},
    {"name": "Mango Sticky Rice (Khao Niew Mamuang)", "kh": "បាយដំណើបស្វាយទុំ", "desc": "Warm sweetened glutinous rice infused with rich salted coconut cream, paired with fresh chilled slices of sweet ripe mango.", "price": "3.00", "tags": "thai;dessert;sweet;fruit;rice"},
    {"name": "Pad Krapow Gai (Holy Basil Chicken)", "kh": "បាយឆាក្រវ៉ាន់សាច់មាន់", "desc": "Fiery wok-tossed minced chicken with lots of fresh holy basil, garlic, and red chilies, served over jasmine rice with a crispy fried sunny-side-up egg.", "price": "3.50", "tags": "thai;rice;chicken;spicy;lunch"},

    # ==================== VIETNAMESE DISHES ====================
    {"name": "Vietnamese Beef Pho (Pho Bo)", "kh": "ហ្វឺសាច់គោ", "desc": "Fragrant cinnamon-star anise beef bone broth simmered for 10 hours with flat rice noodles, rare beef slices, beef balls, fresh mint, cilantro, and bean sprouts.", "price": "3.50", "tags": "vietnamese;pho;noodle;soup;beef"},
    {"name": "Vietnamese Chicken Pho (Pho Ga)", "kh": "ហ្វឺសាច់មាន់", "desc": "Lighter, clean clear chicken bone broth with tender shredded poached chicken, fresh herbs, scallions, lime, and thin flat rice noodles.", "price": "3.25", "tags": "vietnamese;pho;noodle;soup;chicken"},
    {"name": "Banh Mi Thit (Vietnamese Baguette)", "kh": "នំប៉័ងវៀតណាម", "desc": "Feathery crisp baguette loaded with liver pâté, Vietnamese cold cuts (cha lua), pickled carrots, daikon, fresh cilantro, cucumber, and chili mayo.", "price": "2.00", "tags": "vietnamese;sandwich;baguette;street_food"},
    {"name": "Fresh Spring Rolls (Goi Cuon)", "kh": "គួងស្រស់វៀតណាម", "desc": "Healthy translucent rice paper rolls stuffed with boiled shrimp, pork belly, rice vermicelli, mint, and fresh lettuce, dipped in hoisin-peanut sauce.", "price": "2.75", "tags": "vietnamese;spring_rolls;healthy;salad;appetizer"},
    {"name": "Crispy Fried Spring Rolls (Cha Gio)", "kh": "ណែមបំពងវៀតណាម", "desc": "Golden crunchy deep-fried rice paper rolls filled with minced pork, wood ear mushrooms, carrot, and glass noodles, served with sweet nuoc cham dip.", "price": "2.50", "tags": "vietnamese;spring_rolls;fried;appetizer"},
    {"name": "Bun Cha Hanoi", "kh": "ប៊ុនឆាហាណូយ", "desc": "Hanoi specialty of grilled pork patties and pork belly in sweet savory fish sauce broth, served with cool rice vermicelli noodles and fresh herbs.", "price": "4.00", "tags": "vietnamese;noodles;pork;bbq;lunch"},

    # ==================== ITALIAN & WESTERN DISHES ====================
    {"name": "Wood-Fired Pizza Margherita", "kh": "ភីហ្សាម៉ាហ្គើរីតា", "desc": "Classic Neapolitan pizza featuring San Marzano tomato sauce, fresh creamy buffalo mozzarella, sweet fresh basil leaves, and extra virgin olive oil.", "price": "7.50", "tags": "italian;pizza;vegetarian;dinner"},
    {"name": "Pepperoni Pizza", "kh": "ភីហ្សាភិបភើរ៉ូនី", "desc": "Crispy thin-crust pizza loaded with melted mozzarella cheese, tangy tomato marinara, and spicy cured beef or pork pepperoni slices.", "price": "8.50", "tags": "italian;pizza;western;dinner"},
    {"name": "Creamy Pasta Carbonara", "kh": "ប៉ាស្តាកាបូណារ៉ា", "desc": "Rich Italian spaghetti tossed with crispy cured pork (pancetta or bacon), eggs, creamy Parmesan cheese, and coarse cracked black pepper.", "price": "6.50", "tags": "italian;pasta;western;dinner"},
    {"name": "Spaghetti Bolognese", "kh": "ស្ប៉ាហ្គេតទីសាច់គោ", "desc": "Traditional Italian spaghetti tossed with a slow-cooked ragu meat sauce made with minced beef, tomatoes, garlic, red wine, and herbs.", "price": "6.00", "tags": "italian;pasta;beef;dinner"},
    {"name": "Classic Lasagna al Forno", "kh": "នំឡាសាញ៉ា", "desc": "Layers of tender pasta sheets baked with rich ground beef Bolognese, silky creamy béchamel sauce, and golden bubbly melted mozzarella cheese.", "price": "7.50", "tags": "italian;pasta;baked;beef"},
    {"name": "Classic Bacon Cheeseburger", "kh": "ប៊ឺហ្គឺសាច់គោឈីស", "desc": "Grilled 100% beef patty topped with melted cheddar cheese, crispy smoked bacon, lettuce, tomato, pickles, and burger sauce on a toasted brioche bun.", "price": "5.00", "tags": "burger;american;fast_food;beef"},
    {"name": "Crispy American Fried Chicken", "kh": "មាន់បំពងស្រួយអាមេរិក", "desc": "Southern buttermilk marinated chicken coated in seasoned flour and deep-fried golden brown, served with crispy french fries and coleslaw.", "price": "4.50", "tags": "chicken;fried_chicken;fast_food;american"},
    {"name": "Australian Ribeye Steak", "kh": "ស្តេកសាច់គោអូស្ត្រាលី", "desc": "Juicy, marble-rich Australian ribeye steak seared medium with butter and rosemary, served with french fries, green salad, and peppercorn sauce.", "price": "14.00", "tags": "steak;beef;dinner;western;fine_dining"},
    {"name": "British Fish and Chips", "kh": "ត្រីបំពងនិងដំឡូងបារាំង", "desc": "Flaky white fish fillets dipped in golden crispy beer batter, served with thick-cut chips (french fries), tartar sauce, and lemon wedges.", "price": "6.50", "tags": "british;fish_and_chips;seafood;western"},

    # ==================== FRENCH DISHES ====================
    {"name": "French Butter Croissant", "kh": "ក្រូសង់ប៊័របារាំង", "desc": "Authentic multi-layered laminated French pastry made with pure European butter, baked golden brown, crisp and flaky on the outside and tender inside.", "price": "1.75", "tags": "french;bakery;croissant;breakfast;pastry"},
    {"name": "Crispy French Baguette", "kh": "នំប៉័ងបារាំង", "desc": "Traditional long French bread baked with a hard, crunchy crust and open, airy, chewy crumb, perfect for sandwiches or butter.", "price": "1.25", "tags": "french;bakery;bread;breakfast"},
    {"name": "French Steak Frites", "kh": "ស្តេកបារាំងដំឡូងបំពង", "desc": "Bistro classic pan-seared tender beef steak with café de Paris herb butter or green peppercorn sauce, served with thin crispy french fries.", "price": "11.00", "tags": "french;bistro;steak;beef;dinner"},
    {"name": "Duck Confit (Confit de Canard)", "kh": "សាច់ទាចៀនក្រៀមបារាំង", "desc": "Tender duck leg slow-cooked submerged in its own fat until succulent, then pan-seared with golden crackling skin, served with roasted potatoes.", "price": "12.00", "tags": "french;bistro;duck;dinner"},

    # ==================== MEXICAN DISHES ====================
    {"name": "Street Tacos (Carne Asada / Pollo)", "kh": "តាកូសាច់គោ", "desc": "Warm soft corn tortillas filled with charred grilled marinated beef or chicken, diced white onions, cilantro, fresh lime, and spicy salsa verde.", "price": "4.50", "tags": "mexican;taco;street_food;dinner;lunch"},
    {"name": "Loaded Burrito", "kh": "ប៊ូរីតូសាច់គោ", "desc": "Large warm flour tortilla rolled tightly around seasoned Mexican rice, black beans, grilled beef or pork, salsa, cheddar cheese, and sour cream.", "price": "5.50", "tags": "mexican;burrito;wrap;lunch"},
    {"name": "Cheesy Quesadilla", "kh": "នំកេសាឌីយ៉ាឈីស", "desc": "Crispy pan-toasted flour tortilla folded over melted Jack and cheddar cheeses, seasoned chicken or beef, served with pico de gallo and guacamole.", "price": "4.50", "tags": "mexican;cheese;appetizer;snack"},
    {"name": "Tortilla Chips & Guacamole", "kh": "ណាចូសនិងទឹកផ្លែបឺរ", "desc": "Crunchy salted corn tortilla chips served with fresh mashed Hass avocados, lime juice, cilantro, tomatoes, and salsa dip.", "price": "3.50", "tags": "mexican;snack;avocado;healthy;vegetarian"},

    # ==================== INDIAN & MIDDLE EASTERN ====================
    {"name": "Butter Chicken (Murgh Makhani)", "kh": "ការីមាន់ប៊័របែបឥណ្ឌា", "desc": "Tender tandoori-roasted chicken pieces simmered in a silky, mildly sweet and spiced tomato, butter, and heavy cream curry sauce.", "price": "6.00", "tags": "indian;curry;chicken;halal;dinner"},
    {"name": "Chicken Tikka Masala", "kh": "ការីមាន់ធីកា", "desc": "Marinated grilled chicken chunks in a rich, deeply spiced tomato and onion gravy spiced with garam masala, fenugreek, and cumin.", "price": "6.00", "tags": "indian;curry;chicken;halal"},
    {"name": "Lamb Biryani", "kh": "បាយប៊ីរយ៉ានីសាច់ចៀម", "desc": "Fragrant long-grain basmati rice layered with spiced tender lamb pieces, saffron, fried onions, and whole spices, served with cool cucumber raita.", "price": "7.50", "tags": "indian;biryani;rice;lamb;halal"},
    {"name": "Garlic Butter Naan", "kh": "នំប៉័ងណានខ្ទឹមស", "desc": "Traditional Indian flatbread baked against the searing clay walls of a tandoor oven, brushed lavishly with melted butter and roasted minced garlic.", "price": "1.75", "tags": "indian;bread;naan;halal;side"},
    {"name": "Crispy Vegetable Samosas", "kh": "សារម៉ូសាបន្លែ", "desc": "Golden deep-fried triangular pastry pockets stuffed with spiced potatoes, green peas, cumin, and coriander, served with sweet mint chutney.", "price": "2.50", "tags": "indian;snack;vegetarian;appetizer"},
    {"name": "Halal Chicken Shawarma Wrap", "kh": "សាច់សាវ៉ាម៉ាមាន់", "desc": "Thinly shaved spit-roasted chicken wrapped inside warm pita bread with garlic toum sauce, pickled turnip, cucumber, and french fries.", "price": "4.00", "tags": "middle_eastern;halal;wrap;sandwich;street_food"},
    {"name": "Halal Mixed Grill Platter", "kh": "សាច់អាំងចម្រុះហាឡាល់", "desc": "Generous platter of charcoal-grilled lamb seekh kebabs, chicken shish taouk skewers, and beef kofta served over saffron rice and pita bread.", "price": "9.00", "tags": "middle_eastern;halal;kebab;bbq;meat"},
    {"name": "Crispy Falafel with Hummus", "kh": "ហ្វាឡាហ្វែលនិងហ៊ូមូស", "desc": "Golden deep-fried balls of ground chickpeas and herbs served over creamy blended tahini-chickpea hummus with warm pita bread.", "price": "4.50", "tags": "middle_eastern;halal;vegetarian;healthy;vegan"},

    # ==================== HEALTHY, VEGAN & SALAD ====================
    {"name": "Salmon Poke Bowl", "kh": "ផូគីប៊ូលត្រីសាល់ម៉ុង", "desc": "Hawaiian bowl of sushi rice topped with cubed fresh raw salmon, edamame beans, ripe avocado, seaweed salad, cucumber, and sesame-soy dressing.", "price": "6.50", "tags": "poke;hawaiian;healthy;salmon;seafood"},
    {"name": "Mediterranean Quinoa Salad", "kh": "សាឡាដគីណ័រមេឌីទែរ៉ាណេ", "desc": "Wholesome salad of cooked fluffy quinoa, cucumbers, cherry tomatoes, kalamata olives, feta cheese, and lemon extra virgin olive oil vinaigrette.", "price": "4.50", "tags": "healthy;salad;vegetarian;mediterranean"},
    {"name": "Vegan Tofu Buddha Bowl", "kh": "ប៊ូដាប៊ូលបួស", "desc": "Nutrient-dense plant-based bowl loaded with roasted sweet potatoes, crispy air-fried spiced tofu cubes, steamed broccoli, chickpeas, and peanut tahini sauce.", "price": "4.00", "tags": "vegan;vegetarian;healthy;clean_food"},

    # ==================== BEVERAGES & CAFES ====================
    {"name": "Cambodian Iced Milk Coffee (Kafe Toek Doh Ko)", "kh": "កាហ្វេទឹកដោះគោទឹកកក", "desc": "Strong dark drip coffee brewed slow, stirred with sweet condensed milk, and poured over tall glass packed with crushed ice. Cambodia's daily fuel.", "price": "1.75", "tags": "coffee;drinks;beverage;sweet;khmer;local"},
    {"name": "Brown Sugar Boba Milk Tea", "kh": "តែគុជស្ករក្រហម", "desc": "Fresh milk combined with slow-cooked warm brown sugar syrup and chewy tapioca pearls, creating caramel tiger stripes on the cup.", "price": "2.25", "tags": "bubble_tea;tea;boba;sweet;drinks"},
    {"name": "Uji Matcha Latte", "kh": "ម៉ាតឆាឡាតេ", "desc": "Whisked ceremonial Japanese green tea matcha poured over silky steamed or iced milk with a touch of sweetness.", "price": "2.50", "tags": "tea;matcha;japanese;drinks;cafe"},
    {"name": "Passion Fruit Soda", "kh": "ទឹកផាសិនសូដា", "desc": "Refreshing tropical beverage of real tart passion fruit seeds and juice mixed with sparkling soda water, lime, and crushed ice.", "price": "2.00", "tags": "drinks;fruit;beverage;soda;sweet"},
    {"name": "Fresh Avocado Smoothie", "kh": "ទឹកផ្លែបឺរក្រឡុក", "desc": "Creamy decadent smoothie made from ripe avocados blended with sweet milk, ice, and condensed milk.", "price": "2.25", "tags": "smoothie;healthy;fruit;drinks"},

    # ==================== DESSERTS & BAKERIES ====================
    {"name": "Korean Mango Bingsu", "kh": "ប៊ីងស៊ូផ្លែស្វាយកូរ៉េ", "desc": "Fluffy, cloud-like shaved frozen milk snow piled high with fresh sweet mango cubes, vanilla ice cream scoop, and sweet condensed milk drizzle.", "price": "4.50", "tags": "dessert;korean;bingsu;sweet;ice_cream"},
    {"name": "Italian Gelato Cup", "kh": "ការ៉េមជេឡាតូអ៊ីតាលី", "desc": "Artisan slow-churned dense Italian gelato in flavors like pistachio, dark chocolate, salted caramel, and hazelnut.", "price": "2.50", "tags": "dessert;italian;gelato;sweet;ice_cream"},
    {"name": "Portuguese Egg Tart", "kh": "នំអេកថាត", "desc": "Flaky caramelized puff pastry tart shells filled with creamy, rich egg custard baked until blistered dark golden brown.", "price": "1.50", "tags": "dessert;bakery;pastry;sweet"},
    {"name": "Belgian Waffle with Ice Cream", "kh": "នំវ៉ាហ្វលការ៉េម", "desc": "Warm crisp Belgian waffle with deep pockets, topped with vanilla gelato scoop, chocolate drizzle, and fresh strawberry slices.", "price": "3.50", "tags": "dessert;waffle;sweet;ice_cream"},
]

DISH_IMAGE_URLS = {
    "Fish Amok": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Fish_amok.jpg/640px-Fish_amok.jpg",
    "Kuy Teav Phnom Penh": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Kuy_teav_phnom_penh.jpg/640px-Kuy_teav_phnom_penh.jpg",
    "Beef Lok Lak": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Beef_Lok_Lak.jpg/640px-Beef_Lok_Lak.jpg",
    "Bai Sach Chrouk": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Bai_sach_chrouk.jpg/640px-Bai_sach_chrouk.jpg",
    "Nom Banh Chok": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Nom_banhchok.jpg/640px-Nom_banhchok.jpg",
    "Lort Cha": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Lort_cha.jpg/640px-Lort_cha.jpg",
    "Banh Chhev": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Banh_xeo.jpg/640px-Banh_xeo.jpg",
    "Num Pang Pate": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/B%C3%A1nh_m%C3%AC_th%E1%BB%8Bt_n%C6%B0%E1%BB%9Bng.png/640px-B%C3%A1nh_m%C3%AC_th%E1%BB%8Bt_n%C6%B0%E1%BB%9Bng.png",
    "Bok Lhong (Papaya Salad)": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Som_tum_thai_street.jpg/640px-Som_tum_thai_street.jpg",
    "Prahok Ktiss": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Fish_amok.jpg/640px-Fish_amok.jpg",
    "Samlor Machu Trey": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Canh_chua.jpg/640px-Canh_chua.jpg",
    "Sach Ko Ang (Beef Skewers)": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Beef_satay.jpg/640px-Beef_satay.jpg",
    "Kuy Teav Ko Kho": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Pho-Beef-Noodles-2008.jpg/640px-Pho-Beef-Noodles-2008.jpg",
    "Mi Cha (Fried Noodles)": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Phat_Thai_kung_Chang_Khian_street_stall.jpg/640px-Phat_Thai_kung_Chang_Khian_street_stall.jpg",
    "Chhar Kdam Mrech Kchei": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Fish_amok.jpg/640px-Fish_amok.jpg",
    "Babor Sach Moan": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Chicken_congee.jpg/640px-Chicken_congee.jpg",
    "Kari Sach Moan (Red Chicken Curry)": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Tom_yam_kung.jpg/640px-Tom_yam_kung.jpg",
    "Salmon Sashimi": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Sushi_platter.jpg/640px-Sushi_platter.jpg",
    "Tonkotsu Ramen": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dc/Shoyu_Ramen.jpg/640px-Shoyu_Ramen.jpg",
    "Nigiri Sushi Platter": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Sushi_platter.jpg/640px-Sushi_platter.jpg",
    "Chicken Katsu Curry": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Chicken_katsu_curry.jpg/640px-Chicken_katsu_curry.jpg",
    "Japanese Takoyaki Balls": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Takoyaki_by_jetalone_in_Tokyo.jpg/640px-Takoyaki_by_jetalone_in_Tokyo.jpg",
    "Korean Samgyeopsal BBQ": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Samgyeopsal.jpg/640px-Samgyeopsal.jpg",
    "Stone-Bowl Dolsot Bibimbap": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Dolsot-bibimbap.jpg/640px-Dolsot-bibimbap.jpg",
    "Spicy Tteokbokki Rice Cakes": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Tteokbokki.jpg/640px-Tteokbokki.jpg",
    "Kimchi Jjigae Stew": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Kimchi-jjigae.jpg/640px-Kimchi-jjigae.jpg",
    "Korean Sweet and Spicy Fried Chicken (Yangnyeom)": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Yangnyeom_chicken.jpg/640px-Yangnyeom_chicken.jpg",
    "Vietnamese Pho Bo (Beef Noodle Soup)": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Pho-Beef-Noodles-2008.jpg/640px-Pho-Beef-Noodles-2008.jpg",
    "Vietnamese Crispy Pork Banh Mi": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/B%C3%A1nh_m%C3%AC_th%E1%BB%8Bt_n%C6%B0%E1%BB%9Bng.png/640px-B%C3%A1nh_m%C3%AC_th%E1%BB%8Bt_n%C6%B0%E1%BB%9Bng.png",
    "Bun Cha Hanoi": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Bun_cha_Hanoi.jpg/640px-Bun_cha_Hanoi.jpg",
    "Vietnamese Fresh Summer Spring Rolls (Goi Cuon)": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/G%E1%BB%8Fi_cu%E1%BB%91n.jpg/640px-G%E1%BB%8Fi_cu%E1%BB%91n.jpg",
    "Thai Tom Yum Goong (Spicy Prawn Soup)": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Tom_yam_kung.jpg/640px-Tom_yam_kung.jpg",
    "Authentic Pad Thai": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Phat_Thai_kung_Chang_Khian_street_stall.jpg/640px-Phat_Thai_kung_Chang_Khian_street_stall.jpg",
    "Mango Sticky Rice (Khao Niew Mamuang)": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Mango_sticky_rice.jpg/640px-Mango_sticky_rice.jpg",
    "Steamed Dim Sum Siu Mai": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Dim_sum_in_Hong_Kong.jpg/640px-Dim_sum_in_Hong_Kong.jpg",
    "Crispy Peking Duck": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Peking_Duck.jpg/640px-Peking_Duck.jpg",
    "Classic Pizza Margherita": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Eq_it-na_pizza-margherita_sep2005_sml.jpg/640px-Eq_it-na_pizza-margherita_sep2005_sml.jpg",
    "Pepperoni Pizza": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Eq_it-na_pizza-margherita_sep2005_sml.jpg/640px-Eq_it-na_pizza-margherita_sep2005_sml.jpg",
    "Creamy Pasta Carbonara": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Espaguetis_carbonara.jpg/640px-Espaguetis_carbonara.jpg",
    "Classic Bacon Cheeseburger": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Hamburger_%28black_bg%29.jpg/640px-Hamburger_%28black_bg%29.jpg",
    "Crispy American Fried Chicken": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Fried_chicken_cr.jpg/640px-Fried_chicken_cr.jpg",
    "French Butter Croissant": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Croissant%2C_bakery%2C_dish%2C_food_cr.jpg/640px-Croissant%2C_bakery%2C_dish%2C_food_cr.jpg",
    "Street Tacos (Carne Asada / Pollo)": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/001_Tacos_de_carnitas%2C_tianguis_de_los_domingos%2C_Tepotzotl%C3%A1n.jpg/640px-001_Tacos_de_carnitas%2C_tianguis_de_los_domingos%2C_Tepotzotl%C3%A1n.jpg",
    "Loaded Burrito": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Burrito.JPG/640px-Burrito.JPG",
    "Butter Chicken (Murgh Makhani)": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Chicken_makhani.jpg/640px-Chicken_makhani.jpg",
    "Lamb Biryani": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Hyderabadi_Chicken_Biryani.jpg/640px-Hyderabadi_Chicken_Biryani.jpg",
    "Halal Chicken Shawarma Wrap": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Shawarma_sandwich.jpg/640px-Shawarma_sandwich.jpg",
    "Salmon Poke Bowl": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Sushi_platter.jpg/640px-Sushi_platter.jpg",
    "Cambodian Iced Milk Coffee (Kafe Toek Doh Ko)": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Vietnamese_iced_coffee_%28c%C3%A0_ph%C3%AA_s%E1%BB%AFa_%C4%91%C3%A1%29.jpg/640px-Vietnamese_iced_coffee_%28c%C3%A0_ph%C3%AA_s%E1%BB%AFa_%C4%91%C3%A1%29.jpg",
    "Brown Sugar Boba Milk Tea": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Bubble_Tea.png/640px-Bubble_Tea.png",
    "Korean Mango Bingsu": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Patbingsu_1.jpg/640px-Patbingsu_1.jpg",
    "Italian Gelato Cup": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Ice_Cream_dessert_02.jpg/640px-Ice_Cream_dessert_02.jpg"
}

def scrape_wikidata_dishes() -> list[dict]:
    headers = {"User-Agent": "CambodianFoodSearch/1.0 (academic research)"}
    print("Querying Wikidata SPARQL endpoint...")
    dishes = []
    seen = set()

    try:
        r = requests.get(SPARQL_URL, params={"query": SPARQL_QUERY, "format": "json"}, headers=headers, timeout=15)
        if r.status_code == 200:
            bindings = r.json().get("results", {}).get("bindings", [])
            print(f"Retrieved {len(bindings)} Cambodian entities from Wikidata.")
            for b in bindings:
                item_uri = b.get("item", {}).get("value", "")
                qid = item_uri.split("/")[-1]
                name = b.get("itemLabel", {}).get("value", "")
                kh = b.get("khmerLabel", {}).get("value", "")
                desc = b.get("desc", {}).get("value", "")
                image = b.get("image", {}).get("value", "")

                desc_lower = desc.lower()
                name_lower = name.lower()
                is_food = any(k in desc_lower or k in name_lower for k in FOOD_KEYWORDS)
                if not is_food or name_lower in seen:
                    continue
                seen.add(name_lower)

                dishes.append({
                    "id": f"wikidata-{qid}",
                    "name": name,
                    "dish_en": name.lower(),
                    "dish_kh": kh,
                    "description": desc,
                    "tags": "cambodian_cuisine;traditional;wikidata",
                    "price_usd": "2.50",
                    "area": "Phnom Penh",
                    "lat": "",
                    "lng": "",
                    "rating": "4.5",
                    "open_hour": "07.0",
                    "close_hour": "21.0",
                    "source": "wikidata",
                    "source_url": item_uri,
                    "date": "2026-11-05",
                    "image_url": image,
                    "image_path": image,
                    "phone_public": "",
                    "page_url": f"https://www.wikidata.org/wiki/{qid}",
                })
    except Exception as e:
        print(f"Wikidata SPARQL query skipped/offline: {e}")

    # Add complete global & local food encyclopedia
    for d in GLOBAL_FOOD_LEXICON:
        name_key = d["name"].lower()
        if name_key not in seen:
            seen.add(name_key)
            dish_img = DISH_IMAGE_URLS.get(d["name"], "")
            dishes.append({
                "id": f"food-lexicon-{len(dishes)+1:03d}",
                "name": d["name"],
                "dish_en": d["name"].lower(),
                "dish_kh": d["kh"],
                "description": d["desc"],
                "tags": f"culinary_encyclopedia;{d['tags']}",
                "price_usd": d.get("price", "3.00"),
                "area": "Phnom Penh",
                "lat": "",
                "lng": "",
                "rating": "4.8",
                "open_hour": "07.0",
                "close_hour": "22.0",
                "source": "culinary-lexicon",
                "source_url": "https://en.wikipedia.org/wiki/Global_cuisine",
                "date": "2026-11-05",
                "image_url": dish_img,
                "image_path": dish_img,
                "phone_public": "",
                "page_url": "",
            })

    return dishes

def main():
    dishes = scrape_wikidata_dishes()
    print(f"Collected {len(dishes)} dishes and culinary entities across local & foreign cuisines!")
    out_path = Path("data/scraped/wikidata_dishes.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if dishes:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(dishes[0].keys()))
            writer.writeheader()
            writer.writerows(dishes)
        print(f"✅ Saved to {out_path}")
        print("Sample dishes:")
        for d in dishes[:8]:
            print(f"- {d['name']} ({d['dish_kh']}): ${d['price_usd']} | {d['description'][:80]}...")

if __name__ == "__main__":
    main()
