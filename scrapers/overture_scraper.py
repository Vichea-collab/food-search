"""
Overture Maps Places Scraper & Transformer for Phnom Penh & Cambodia Food
Source: Overture Maps Foundation (Places Theme - Food & Beverage)
Converts 11,700+ venues into the standardized 18-column search dataset format
with fine-grained category mapping (Japanese, Korean, Chinese, Thai, Vietnamese,
Italian, French, Indian, Mexican, Halal, Seafood, Vegetarian, Bakeries, Cafes, etc.),
exact GPS coordinates, Facebook links, and signature menu items.
"""

import math
import re
import csv
import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

RAW_OVERTURE_PATH = Path("data/raw/overture_food_phnom_penh.csv")
OUTPUT_CSV_PATH = Path("data/scraped/overture_places.csv")

# 14 Phnom Penh Khan Centroids (lat, lng) derived from geographic benchmarks
KHAN_CENTROIDS = {
    "Boeng Keng Kang": (11.551209, 104.920436),
    "Chamkar Mon": (11.543178, 104.922670),
    "Daun Penh": (11.567895, 104.924279),
    "Toul Kork": (11.573164, 104.896538),
    "Sen Sok": (11.579263, 104.869771),
    "Prampir Makara": (11.561506, 104.915403),
    "Chroy Changvar": (11.618494, 104.927026),
    "Chbar Ampov": (11.525313, 104.957830),
    "Mean Chey": (11.524797, 104.913278),
    "Russey Keo": (11.603507, 104.902122),
    "Pou Senchey": (11.546549, 104.845776),
    "Dangkao": (11.483491, 104.872142),
    "Prek Pnov": (11.644974, 104.796554),
    "Kamboul": (11.504926, 104.800293),
}

# Name keywords that override coordinate distance to guarantee exact Khan
AREA_KEYWORD_RULES = [
    (re.compile(r"\b(?:bkk|bkk1|bkk2|bkk3|boeung\s*keng\s*kang|boeng\s*keng\s*kang|បឹងកេងកង)\b", re.I), "Boeng Keng Kang"),
    (re.compile(r"\b(?:toul\s*tom\s*poung|tuol\s*tom\s*poung|russian\s*market|chamkar\s*mon|chamkarmon|bassac|ទួលទំពូង|ចំការមន)\b", re.I), "Chamkar Mon"),
    (re.compile(r"\b(?:daun\s*penh|doun\s*penh|riverside|phsar\s*thmei|psar\s*thmei|central\s*market|wat\s*phnom|ដូនពេញ|ផ្សារថ្មី)\b", re.I), "Daun Penh"),
    (re.compile(r"\b(?:toul\s*kork|tuol\s*kouk|tuol\s*kork|ទួលគោក)\b", re.I), "Toul Kork"),
    (re.compile(r"\b(?:sen\s*sok|sensok|aeon\s*2|aeon2|phnom\s*penh\s*thmey|pp\s*thmey|សែនសុខ)\b", re.I), "Sen Sok"),
    (re.compile(r"\b(?:prampir\s*makara|7\s*makara|olympic|orussey|អូរឫស្សី|៧មករា)\b", re.I), "Prampir Makara"),
    (re.compile(r"\b(?:chroy\s*changvar|chroy\s*changva|ជ្រោយចង្វារ)\b", re.I), "Chroy Changvar"),
    (re.compile(r"\b(?:chbar\s*ampov|chbar\s*ompov|ច្បារអំពៅ)\b", re.I), "Chbar Ampov"),
    (re.compile(r"\b(?:mean\s*chey|meanchey|steung\s*mean\s*chey|ស្ទឹងមានជ័យ|aeon\s*3)\b", re.I), "Mean Chey"),
    (re.compile(r"\b(?:russey\s*keo|toul\s*sangke|ទួលសង្កែ|ឫស្សីកែវ)\b", re.I), "Russey Keo"),
    (re.compile(r"\b(?:pou\s*senchey|por\s*senchey|choam\s*chao|ចោមចៅ|ពោធិ៍សែនជ័យ)\b", re.I), "Pou Senchey"),
    (re.compile(r"\b(?:dangkao|dangkor|ដង្កោ)\b", re.I), "Dangkao"),
    (re.compile(r"\b(?:prek\s*pnov|ព្រែកព្នៅ)\b", re.I), "Prek Pnov"),
    (re.compile(r"\b(?:kamboul|កំបូល)\b", re.I), "Kamboul"),
]

def find_nearest_khan(lat: float, lng: float, name: str) -> str:
    """Resolve venue area via name keyword match or nearest Khan centroid."""
    if name:
        for pat, khan_name in AREA_KEYWORD_RULES:
            if pat.search(name):
                return khan_name

    if lat and lng and not math.isnan(lat) and not math.isnan(lng):
        best_khan = "Phnom Penh"
        min_dist = float("inf")
        for khan, (c_lat, c_lng) in KHAN_CENTROIDS.items():
            dist = (lat - c_lat) ** 2 + (lng - c_lng) ** 2
            if dist < min_dist:
                min_dist = dist
                best_khan = khan
        return best_khan

    return "Phnom Penh"

# Category mapping covering international and local cuisines
OVERTURE_CATEGORY_MAP = {
    # Japanese
    "japanese_restaurant": ("Japanese Cuisine & Sushi", "ម្ហូបជប៉ុន និងស៊ូស៊ី", "8.50", "japanese;sushi;asian;dinner"),
    "sushi_restaurant": ("Sushi & Sashimi", "ស៊ូស៊ី និងសាស៊ីមី", "9.00", "sushi;japanese;seafood;dinner"),
    "ramen_restaurant": ("Japanese Ramen & Noodles", "រ៉ាមេនជប៉ុន", "5.50", "ramen;japanese;noodles;soup"),
    "sake_bar": ("Japanese Sake & Izakaya", "បារជប៉ុន និងម្ហូបក្លែម", "10.00", "japanese;bar;izakaya;drinks"),

    # Korean
    "korean_restaurant": ("Korean BBQ & Cuisine", "ម្ហូបកូរ៉េ និងសាច់អាំងកូរ៉េ", "7.50", "korean;bbq;spicy;dinner"),

    # Chinese & Dim Sum
    "chinese_restaurant": ("Chinese Cuisine & Roast Meats", "ម្ហូបចិន និងទាខ្វៃ", "6.00", "chinese;asian;dinner;lunch"),
    "dim_sum_restaurant": ("Chinese Dim Sum & Dumplings", "ឌីមសាំ និងគាវចិន", "5.00", "dim_sum;chinese;dumpling;breakfast;lunch"),

    # Southeast Asian
    "thai_restaurant": ("Thai Cuisine & Tom Yum", "ម្ហូបថៃ និងតុមយ៉ាំ", "5.00", "thai;spicy;asian;dinner"),
    "vietnamese_restaurant": ("Vietnamese Pho & Spring Rolls", "ម្ហូបវៀតណាម និងហ្វឺ", "3.50", "vietnamese;pho;noodles;soup"),
    "malaysian_restaurant": ("Malaysian Cuisine & Roti Canai", "ម្ហូបម៉ាឡេស៊ី", "5.00", "malaysian;asian;halal"),
    "singaporean_restaurant": ("Singaporean Cuisine & Hainanese Rice", "ម្ហូបសិង្ហបុរី", "5.50", "singaporean;asian;rice"),
    "indonesian_restaurant": ("Indonesian Cuisine & Satay", "ម្ហូបឥណ្ឌូនេស៊ី", "5.00", "indonesian;asian;halal;satay"),
    "filipino_restaurant": ("Filipino Cuisine & Adobo", "ម្ហូបហ្វីលីពីន", "4.50", "filipino;asian;lunch;dinner"),
    "burmese_restaurant": ("Burmese Cuisine & Tea Leaf Salad", "ម្ហូបភូមា", "4.00", "burmese;asian;noodles"),

    # South Asian & Middle Eastern
    "indian_restaurant": ("Indian Curry & Biryani", "ម្ហូបឥណ្ឌា និងការី", "6.00", "indian;curry;biryani;halal"),
    "pakistani_restaurant": ("Pakistani Halal Grill & Biryani", "ម្ហូបប៉ាគីស្ថាន និងសាច់អាំង", "6.00", "pakistani;halal;bbq;curry"),
    "nepalese_restaurant": ("Nepalese Cuisine & Momos", "ម្ហូបនេប៉ាល់", "5.00", "nepalese;asian;dumpling"),
    "middle_eastern_restaurant": ("Middle Eastern Kebab & Shawarma", "ម្ហូបមជ្ឈិមបូព៌ា និងសាច់កេបាប់", "6.00", "middle_eastern;halal;kebab;shawarma"),
    "lebanese_restaurant": ("Lebanese Mezze & Mixed Grill", "ម្ហូបលីបង់", "7.00", "lebanese;middle_eastern;halal;grill"),
    "turkish_restaurant": ("Turkish Doner & Kebabs", "ម្ហូបតួកគី និងដូណឺកេបាប់", "6.00", "turkish;halal;kebab;shawarma"),
    "doner_kebab_restaurant": ("Doner Kebabs & Shawarma", "ដូណឺកេបាប់ និងសាច់អាំង", "4.50", "kebab;halal;fast_food;sandwich"),
    "afghani_restaurant": ("Afghani Pilaf & Grilled Meats", "ម្ហូបអាហ្វហ្គានីស្ថាន", "6.00", "afghani;halal;rice;meat"),
    "halal_restaurant": ("Halal Food & Certified Kitchen", "អាហារហាឡាល់", "5.50", "halal;muslim_friendly;dinner;lunch"),

    # Italian & European
    "italian_restaurant": ("Italian Pasta, Risotto & Pizza", "ម្ហូបអ៊ីតាលី និងប៉ាស្តា", "7.50", "italian;pasta;pizza;western;dinner"),
    "pizza_restaurant": ("Wood-Fired Pizza & Italian Sides", "ភីហ្សា និងម្ហូបអ៊ីតាលី", "7.50", "pizza;italian;fast_food;dinner"),
    "french_restaurant": ("French Bistro Cuisine & Steaks", "ម្ហូបបារាំង និងស្រា", "9.00", "french;western;fine_dining;wine"),
    "brasserie": ("French Brasserie & Classics", "ប្រាសឺរីបារាំង", "8.50", "french;bistro;western"),
    "spanish_restaurant": ("Spanish Tapas & Paella", "ម្ហូបអេស្ប៉ាញ និងតាផាស", "8.50", "spanish;tapas;western;dinner"),
    "tapas_bar": ("Tapas & Small Plates", "តាផាសបារ", "7.00", "tapas;bar;drinks;dinner"),
    "greek_restaurant": ("Greek & Mediterranean Cuisine", "ម្ហូបក្រិក និងមេឌីទែរ៉ាណេ", "7.50", "greek;mediterranean;salad;healthy"),
    "mediterranean_restaurant": ("Mediterranean Grilled Dishes", "ម្ហូបមេឌីទែរ៉ាណេ", "7.50", "mediterranean;healthy;seafood;grill"),
    "german_restaurant": ("German Sausages & European Fare", "ម្ហូបអាល្លឺម៉ង់", "8.00", "german;sausage;western;beer"),
    "eastern_european_restaurant": ("Eastern European Cuisine", "ម្ហូបអឺរ៉ុបខាងកើត", "7.00", "european;western;soup"),
    "russian_restaurant": ("Russian Cuisine & Soups", "ម្ហូបរុស្ស៊ី", "7.00", "russian;european;western"),
    "european_restaurant": ("European Continental Dining", "ម្ហូបអឺរ៉ុប", "8.00", "european;western;dinner"),

    # Americas
    "mexican_restaurant": ("Mexican Tacos, Burritos & Nachos", "ម្ហូបម៉ិចស៊ិក និងតាកូ", "5.50", "mexican;taco;burrito;spicy;western"),
    "american_restaurant": ("American Burgers & Steaks", "ម្ហូបអាមេរិកាំង", "6.50", "american;burger;fast_food;western"),
    "steakhouse": ("Steakhouse & Grilled Cuts", "ស្តេក និងសាច់គោអាំង", "12.00", "steak;beef;grill;dinner;western"),
    "burger_restaurant": ("Craft Burgers & Fries", "ប៊ឺហ្គឺ និងដំឡូងបារាំងបំពង", "4.50", "burger;fast_food;western;lunch"),
    "hot_dog_restaurant": ("Hot Dogs & Fast Food", "ហត់ដក និងអាហាររហ័ស", "3.50", "hot_dog;fast_food;american"),
    "cajun_and_creole_restaurant": ("Cajun Seafood Boil & Spices", "គ្រឿងសមុទ្រខាហ្សុន", "8.50", "cajun;seafood;spicy;american"),
    "latin_american_restaurant": ("Latin American Cuisine", "ម្ហូបអាមេរិកឡាទីន", "6.50", "latin;mexican;grill"),
    "brazilian_restaurant": ("Brazilian Churrasco & BBQ", "សាច់អាំងប្រេស៊ីល", "12.00", "brazilian;bbq;meat;buffet"),
    "peruvian_restaurant": ("Peruvian Ceviche & Grilled Meat", "ម្ហូបប៉េរូ", "7.50", "peruvian;seafood;latin"),

    # African
    "african_restaurant": ("African Spiced Stews & Rice", "ម្ហូបអាហ្វ្រិក", "6.00", "african;halal;stew;rice"),
    "ethiopian_restaurant": ("Ethiopian Injera & Curries", "ម្ហូបអេត្យូពី", "6.00", "ethiopian;african;curry;stew"),
    "egyptian_restaurant": ("Egyptian Koshari & Grilled Meats", "ម្ហូបអេហ្ស៊ីប", "5.50", "egyptian;middle_eastern;halal"),

    # Seafood, BBQ & Hot Pot
    "seafood_restaurant": ("Fresh Cambodian Seafood & Crab", "គ្រឿងសមុទ្រ និងក្តាមស្រស់ៗ", "8.00", "seafood;fish;crab;dinner"),
    "barbecue_restaurant": ("BBQ & Charcoal Grilled Meats", "សាច់អាំង និងម្ហូបក្លែម", "5.50", "bbq;grill;meat;dinner"),
    "bar_and_grill_restaurant": ("Bar & Grill Specialties", "បារ និងសាច់អាំង", "6.00", "bar;grill;bbq;beer"),
    "soup_restaurant": ("Claypot Soup & Hot Pot", "ស៊ុបឆ្នាំងដី និងស៊ុបក្ដៅៗ", "7.50", "soup;hotpot;dinner;noodles"),
    "buffet_restaurant": ("All-You-Can-Eat Buffet", "អាហារប៊ូហ្វេ", "12.00", "buffet;all_you_can_eat;seafood;bbq"),

    # Chicken & Fast Food
    "chicken_restaurant": ("Crispy Fried Chicken & Wings", "មាន់បំពងស្រួយ និងស្លាបមាន់", "4.00", "chicken;fried_chicken;fast_food"),
    "fast_food_restaurant": ("Fast Food, Burgers & Chicken", "អាហាររហ័ស ប៊ឺហ្គឺ និងមាន់បំពង", "4.00", "fast_food;burger;chicken;lunch"),
    "food_truck_stand": ("Street Food & Quick Bites", "អាហារតាមផ្លូវ និងអាហាររហ័ស", "2.50", "street_food;fast_food;snack"),
    "fish_and_chips_restaurant": ("Fish and Chips & Crispy Seafood", "ត្រីបំពង និងដំឡូងបំពង", "5.50", "fish_and_chips;british;seafood;fast_food"),

    # Healthy, Vegetarian & Salads
    "vegetarian_restaurant": ("Vegetarian Dishes & Plant Food", "ម្ហូបបួស និងអាហារសុខភាព", "3.50", "vegetarian;healthy;vegan;lunch"),
    "vegan_restaurant": ("100% Plant-Based Vegan Food", "ម្ហូបបួសសុទ្ធ", "4.00", "vegan;vegetarian;healthy;plant_based"),
    "health_food_restaurant": ("Clean Food & Health Bowls", "អាហារសុខភាព", "4.50", "healthy;salad;clean_food;organic"),
    "salad_bar": ("Salad Bowls & Fresh Greens", "សាឡាដបារ និងបន្លែស្រស់", "4.00", "salad;healthy;vegetarian;lunch"),
    "poke_restaurant": ("Hawaiian Poke Bowls", "ផូគីប៊ូលហាវ៉ៃ", "6.50", "poke;hawaiian;seafood;healthy;salmon"),

    # Cafe, Coffee & Beverages
    "coffee_shop": ("Specialty Coffee & Pastries", "កាហ្វេ និងភេសជ្ជៈ", "2.25", "coffee;cafe;espresso;drinks"),
    "cafe": ("Cafe Drinks & Light Bites", "កាហ្វេ និងអាហារសម្រន់", "2.25", "cafe;coffee;drinks;breakfast"),
    "bubble_tea_shop": ("Bubble Milk Tea & Cheese Foam", "តែគុជ និងតែផ្លែឈើ", "2.25", "bubble_tea;tea;boba;drinks"),
    "tea_room": ("Artisan Tea & Infusions", "តែបៃតង និងតែក្រអូប", "2.50", "tea;beverage;drinks"),
    "smoothie_juice_bar": ("Fresh Fruit Smoothies & Juices", "ទឹកក្រឡុក និងទឹកផ្លែឈើស្រស់", "2.25", "smoothie;juice;healthy;drinks"),
    "taiwanese_restaurant": ("Taiwanese Street Food & Boba", "ម្ហូបតៃវ៉ាន់ និងតែគុជ", "4.00", "taiwanese;asian;bubble_tea;street_food"),
    "hong_kong_style_cafe": ("Hong Kong Cha Chaan Teng", "អាហារដ្ឋានបែបហុងកុង", "4.50", "hong_kong;chinese;asian;breakfast"),

    # Bakery & Desserts
    "bakery": ("Fresh Baguettes, Breads & Pastries", "នំប៉័ង និងនំខេក", "2.00", "bakery;bread;pastry;sweet"),
    "dessert_shop": ("Sweet Desserts & Shaved Ice", "បង្អែម និងនំផ្អែម", "2.50", "dessert;sweet;cake"),
    "ice_cream_shop": ("Ice Cream & Gelato", "ការ៉េម និងជេឡាតូ", "2.50", "ice_cream;dessert;sweet"),
    "gelato_shop": ("Artisan Italian Gelato", "ការ៉េមជេឡាតូអ៊ីតាលី", "2.50", "gelato;ice_cream;dessert;italian"),
    "shaved_ice_shop": ("Korean Bingsu & Shaved Ice", "ប៊ីងស៊ូ និងបង្អែមទឹកកកឈូស", "3.00", "bingsu;ice_cream;dessert;sweet"),
    "donut_shop": ("Donuts & Sweet Pastries", "នំដូណាត់", "2.00", "donut;bakery;sweet;dessert"),
    "cupcake_shop": ("Cupcakes & Custom Cakes", "ខេក និងនំខេក", "2.50", "cake;bakery;sweet;dessert"),
    "pancake_house": ("Pancakes & Waffles", "នំផេនខេក និងវ៉ាហ្វល", "3.50", "pancake;waffle;breakfast;sweet"),
    "chocolatier": ("Artisan Chocolates & Truffles", "សូកូឡា", "4.00", "chocolate;sweet;dessert"),

    # Breakfast & Sandwiches
    "breakfast_and_brunch_restaurant": ("Breakfast & Brunch Favorites", "អាហារពេលព្រឹក និងអាហារថ្ងៃត្រង់", "3.50", "breakfast;brunch;coffee;morning"),
    "diner": ("Classic Diner Comfort Food", "អាហារបែបដាយណឺ", "4.50", "diner;american;comfort_food"),
    "sandwich_shop": ("Sub Sandwiches & Baguettes", "នំប៉័ងសាំងវិច", "3.00", "sandwich;baguette;lunch"),
    "bagel_shop": ("Fresh Bagels & Spreads", "នំប៉័ងបេហ្គល", "3.00", "bagel;bakery;breakfast"),

    # Local Cambodian & Asian
    "cambodian_restaurant": ("Traditional Khmer Cuisine", "ម្ហូបខ្មែរប្រពៃណី", "3.50", "khmer;traditional;local;cambodian"),
    "asian_restaurant": ("Asian Made-to-Order Dishes", "ម្ហូបអាស៊ី និងម្ហូបកុម្ម៉ង់", "3.00", "asian;rice;stir_fry;dinner"),
    "asian_fusion_restaurant": ("Asian Fusion Cuisine", "ម្ហូបអាស៊ីចម្រុះ", "5.00", "asian;fusion;dinner"),
    "restaurant": ("Khmer & Asian Made-to-Order Dishes", "បាយម្ហូបកុម្ម៉ង់ និងម្ហូបខ្មែរ", "2.75", "restaurant;khmer;rice;dinner"),
    "food_and_drink": ("Local Food & Cold Drinks", "អាហារ និងភេសជ្ជៈ", "2.50", "food;drinks;lunch"),
}

CATEGORY_SIGNATURE_ITEMS = [
    # Specific Khmer specialties
    (re.compile(r"kuy\s*teav|kuyteav|គុយទាវ|soup\s*mee", re.I),
     "Kuy Teav Phnom Penh, Beef Ball Noodle Soup, Seafood Rice Noodles, Pork Intestine Soup",
     "គុយទាវភ្នំពេញ គុយទាវប្រហិតសាច់គោ និងគុយទាវគ្រឿងសមុទ្រ"),
    (re.compile(r"num\s*banhchok|nom\s*banhchok|នំបញ្ចុក|nom\s*bonjok|somlor\s*khmer", re.I),
     "Nom Banh Chok with Green Fish Curry, Red Curry Noodle Soup, Fresh Vegetables",
     "នំបញ្ចុកសម្លប្រហើរ នំបញ្ចុកសម្លការី និងបន្លែស្រស់"),
    (re.compile(r"lort\s*cha|lot\s*cha|mi\s*cha|លតឆា|មីឆា", re.I),
     "Lort Cha with Fried Egg & Beef, Stir-Fried Egg Noodles (Mi Cha), Chive Cakes",
     "លតឆាសាច់គោពងទា មីឆា និងនំកាឆាយ"),
    (re.compile(r"bok\s*l['\s]?hong|បុកល្ហុង", re.I),
     "Spicy Papaya Salad (Bok Lhong) with Salted Crab, Grilled Chicken Wings, Sticky Rice",
     "បុកល្ហុងក្តាមប្រៃ ស្លាបមាន់អាំង និងបាយដំណើប"),
    (re.compile(r"banh\s*chhe?a?v|banh\s*chao|បាញ់ឆែវ", re.I),
     "Crispy Banh Chhev (Stuffed Rice Crepes) with Minced Pork, Shrimps & Fresh Herbs",
     "បាញ់ឆែវស្រួយ សាច់ជ្រូកចិញ្ច្រាំ និងបន្លែស្រស់"),
    (re.compile(r"num\s*pang|nom\s*pang|baguette|sandwich|នំប៉័ង|chrouk\s*kvai", re.I),
     "Num Pang Pate (Pork & Liver Pate Baguette), Roast Pork with Pickled Daikon & Herbs",
     "នំប៉័ងសាច់ប៉ាតេ នំប៉័ងសាច់ជ្រូកខ្វៃ និងជ្រក់បន្លែ"),
    (re.compile(r"cha[-_ ]?kda[vo]|chha[-_ ]?kdao|ឆាក្តៅ", re.I),
     "Cha Kdao (Spicy Holy Basil Stir-Fry with Chicken or Beef), Jasmine Rice",
     "ឆាក្តៅសាច់មាន់ ឆាក្តៅសាច់គោ និងបាយស"),
    (re.compile(r"mi[-_ ]?sour|mee[-_ ]?sour|មីសួរ", re.I),
     "Mi Sour (Khmer Glass Noodle Soup with Chicken and Mushrooms)",
     "មីសួរសាច់មាន់ និងស៊ុបផ្សិត"),
    (re.compile(r"mi[-_ ]?hel|mee[-_ ]?hal|spicy[-_ ]?noodle|មីហឹរ", re.I),
     "Spicy Level Noodles (Mi Hel 7 Levels) with Seafood, Beef and Meatballs",
     "មីហឹរ ៧ កម្រិត គ្រឿងសមុទ្រ និងសាច់គោ"),
    (re.compile(r"ramen|ramyeon|pho\b|noodle|មី", re.I),
     "Tonkotsu Pork Ramen, Vietnamese Beef Pho, Wonton Egg Noodle Soup",
     "រ៉ាមេនសាច់ជ្រូក ហ្វឺសាច់គោ និងមីគាវ"),

    # Dining Styles, BBQ & Hot Pot
    (re.compile(r"buffet|all\s*you\s*can\s*eat|ប៊ូហ្វេ", re.I),
     "All-You-Can-Eat Seafood, BBQ Beef & Pork, Fresh Oysters, Hot Pot, Salad Bar, Dessert",
     "អាហារប៊ូហ្វេគ្រឿងសមុទ្រ សាច់អាំង ស៊ុបឆ្នាំងដី និងបង្អែមច្រើនមុខ"),
    (re.compile(r"seafood|crab|shrimp|fish|prawn|squid|lobster|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី|មឹក|បង្កង", re.I),
     "Stir-Fried Crab with Fresh Kampot Green Peppercorns, Grilled River Prawns, Steamed Fish with Ginger",
     "ក្តាមថ្មឆាម្រេចខ្ចីកំពត បង្គាទន្លេអាំង និងត្រីចំហុយមីសួរខ្ញី"),
    (re.compile(r"hot\s*pot|suki|soup|ស៊ុប|shabu", re.I),
     "Claypot Suki Soup, Seafood Shabu Shabu, Sliced Australian Beef Hot Pot, Fresh Greens",
     "ស៊ុបឆ្នាំងដី ស៊ុបស៊ូគីគ្រឿងសមុទ្រ និងស៊ុបសាច់គោស្លាយ"),
    (re.compile(r"bbq|barbecue|grill|សាច់អាំង|sach\s*ko\s*jakak", re.I),
     "Grilled Beef Skewers (Sach Ko Ang), BBQ Pork Ribs, Grilled Chicken Wings, Pickled Papaya",
     "សាច់គោចាក់កាក់អាំង ឆ្អឹងជំនីជ្រូកអាំង និងជ្រក់ល្ហុង"),

    # Khmer Rice Dishes
    (re.compile(r"bai\s*sach|bay\s*sach|បាយសាច់ជ្រូក", re.I),
     "Bai Sach Chrouk (Marinated Grilled Pork with Broken Rice), Pickled Cucumbers, Clear Broth",
     "បាយសាច់ជ្រូកអាំង ជ្រក់ត្រសក់ និងទឹកស៊ុប"),
    (re.compile(r"lok\s*lak|ឡុកឡាក់", re.I),
     "Shaking Beef Lok Lak with Lime & Kampot Pepper Dip, Fried Egg, Steamed Rice",
     "ឡុកឡាក់សាច់គោ អំបិលម្រេចក្រូចឆ្មា ពងទាចៀន និងបាយស"),
    (re.compile(r"amok|អាម៉ុក", re.I),
     "Steamed Fish Amok in Banana Leaves, Khmer Red Chicken Curry, Jasmine Rice",
     "អាម៉ុកត្រីស្លឹកចេក ការីមាន់ខ្មែរ និងបាយក្រអូប"),
    (re.compile(r"bay\s*m[oa]i?n|bai\s*moan|chicken\s*rice|បាយមាន់", re.I),
     "Hainanese Steamed Chicken Rice, Roasted Village Chicken Rice with Ginger Sauce",
     "បាយមាន់ហៃណាំ និងបាយមាន់ស្រែទឹកត្រីខ្ញី"),
    (re.compile(r"ptes\s*bay|ptah\s*bay|louk\s*bay|mhob\s*kamong", re.I),
     "Khmer Made-to-Order Dishes: Beef Lok Lak, Pork with Rice, Seafood Fried Rice, Stir-Fried Morning Glory",
     "បាយម្ហូបកុម្ម៉ង់ ឡុកឡាក់សាច់គោ បាយសាច់ជ្រូក បាយឆា និងឆាត្រកួន"),

    # Japanese
    (re.compile(r"sushi|japanese|sashimi|ម្ហូបជប៉ុន|ស៊ូស៊ី", re.I),
     "Fresh Salmon Sashimi, Spicy Tuna Roll, Chicken Teriyaki Bento, Tonkotsu Ramen",
     "សាស៊ីមីសាល់ម៉ុង ស៊ូស៊ី បាយប្រអប់តេរីយ៉ាគី និងរ៉ាមេន"),

    # Korean
    (re.compile(r"korean|kimchi|k-bbq|samgyeopsal|ម្ហូបកូរ៉េ", re.I),
     "Korean Grilled Pork Belly (Samgyeopsal), Stone-Bowl Bibimbap, Tteokbokki, Kimchi Jjigae",
     "សាច់ជ្រូកបីជាន់អាំងកូរ៉េ បាយឆាថ្មប៊ីប៊ីមបាប់ តុកបុកគី និងស៊ុបគីមឈី"),

    # Chinese
    (re.compile(r"chinese|dim\s*sum|dumpling|ម្ហូបចិន|ឌីមសាំ", re.I),
     "Steamed Pork Dumplings (Siu Mai), BBQ Pork Buns (Char Siu Bao), Peking Duck, Chow Mein",
     "ឌីមសាំគាវសាច់ជ្រូក នំប៉ាវសាច់ក្រហម ទាខ្វៃ និងមីឆាចិន"),

    # Thai
    (re.compile(r"thai|tom\s*yum|pad\s*thai|ម្ហូបថៃ", re.I),
     "Tom Yum Kung, Pad Thai Noodles, Som Tum Papaya Salad, Green Curry Chicken",
     "តុមយ៉ាំបង្គា ផាត់ថៃ បុកល្ហុងថៃ និងការីបៃតងសាច់មាន់"),

    # Vietnamese
    (re.compile(r"vietnam|pho\b|banh\s*mi|ម្ហូបវៀតណាម", re.I),
     "Vietnamese Beef Pho Bo, Fresh Spring Rolls (Goi Cuon), Banh Mi Pate, Bun Cha",
     "ហ្វឺសាច់គោ គួងស្រស់វៀតណាម នំប៉័ងប៉ាតេ និងប៊ុនឆា"),

    # Indian & Middle Eastern
    (re.compile(r"indian|curry|biryani|naan|tandoori|ម្ហូបឥណ្ឌា", re.I),
     "Butter Chicken Curry, Lamb Biryani with Raita, Garlic Naan, Vegetable Samosas",
     "ការីមាន់ប៊័រ បាយប៊ីរយ៉ានីសាច់ចៀម នំប៉័ងណាន និងសារម៉ូសា"),
    (re.compile(r"middle\s*eastern|kebab|shawarma|falafel|halal|អាហារហាឡាល់", re.I),
     "Chicken Shawarma Wrap, Beef Doner Kebab Plate, Crispy Falafel, Hummus with Pita",
     "សាច់សាវ៉ាម៉ា សាច់កេបាប់ ហ្វាឡាហ្វែល និងទឹកជ្រលក់ហ៊ូមូស"),

    # Italian & Western
    (re.compile(r"pizza|pasta|spaghetti|italian|ភីហ្សា|ម្ហូបអ៊ីតាលី", re.I),
     "Wood-Fired Pizza (Margherita, Pepperoni), Creamy Pasta Carbonara, Spaghetti Bolognese",
     "ភីហ្សាដុតភ្លើងអុស ភីហ្សាភិបភើរ៉ូនី ប៉ាស្តាកាបូណារ៉ា និងស្ប៉ាហ្គេតទី"),
    (re.compile(r"french|bistro|ម្ហូបបារាំង", re.I),
     "French Steak Frites, Duck Confit, Classic Butter Croissants, French Onion Soup",
     "ស្តេកបារាំង ដំឡូងបំពង ទាចៀនក្រៀម និងក្រូសង់ប៊័រ"),
    (re.compile(r"mexican|taco|burrito|nachos|ម្ហូបម៉ិចស៊ិក", re.I),
     "Street Tacos (Carne Asada / Pollo), Loaded Burritos, Cheesy Quesadillas, Tortilla Chips & Guacamole",
     "តាកូសាច់គោ ប៊ូរីតូ ឈីសកេសាឌីយ៉ា និងណាចូស"),
    (re.compile(r"burger|ប៊ឺហ្គឺ|fast\s*food", re.I),
     "Classic Cheeseburger, Crispy Fried Chicken Burger, Seasoned French Fries, Onion Rings",
     "ប៊ឺហ្គឺសាច់គោឈីស ប៊ឺហ្គឺមាន់បំពងស្រួយ និងដំឡូងបារាំងបំពង"),
    (re.compile(r"fried\s*chicken|crispy\s*chicken|មាន់បំពង", re.I),
     "Crispy Fried Chicken (Original / Spicy), Chicken Tenders, Fries, Coleslaw",
     "មាន់បំពងស្រួយរសជាតិហឹរ សាច់មាន់បន្ទះ និងដំឡូងបំពង"),
    (re.compile(r"steak|steakhouse|ស្តេក", re.I),
     "Grilled Australian Ribeye Steak, Tenderloin with Peppercorn Sauce, Mashed Potatoes",
     "ស្តេកសាច់គោអូស្ត្រាលី ទឹកជ្រលក់ម្រេច និងដំឡូងបារាំងកិន"),

    # Healthy & Vegetarian
    (re.compile(r"vegetarian|vegan|plant[-_ ]?based|ម្ហូបបួស", re.I),
     "Tofu & Vegetable Stir-Fry, Fresh Spring Rolls with Peanut Dip, Vegetarian Amok, Garden Salad",
     "ឆាតៅហ៊ូបន្លែស្រស់ គួងបួសទឹកជ្រលក់សណ្តែកដី អាម៉ុកបួស និងសាឡាដ"),
    (re.compile(r"salad|healthy|poke|អាហារសុខភាព", re.I),
     "Salmon Poke Bowl with Edamame, Mediterranean Quinoa Salad, Avocado Greens Bowl",
     "ផូគីប៊ូលត្រីសាល់ម៉ុង សាឡាដគីណ័រ និងសាឡាដផ្លែបឺរ"),

    # Beverages & Cafes
    (re.compile(r"coffee|cafe|café|espresso|cappuccino|latte|កាហ្វេ|kfae|kafe|kofi", re.I),
     "Cambodian Iced Milk Coffee (Kafe Toek Doh Ko), Iced Latte, Americano, Cold Brew, Passion Fruit Soda",
     "កាហ្វេទឹកដោះគោទឹកកក ឡាតេទឹកកក អាមេរិកាណូ និងកាហ្វេត្រជាក់"),
    (re.compile(r"bubble\s*tea|boba|milk\s*tea|matcha|តែគុជ|តែទឹកដោះគោ|chagee", re.I),
     "Brown Sugar Boba Milk Tea, Uji Matcha Latte, Jasmine Cheese Foam Tea, Mango Fruit Tea",
     "តែគុជស្ករក្រហម ម៉ាតឆាឡាតេ តែបៃតងហ្វូមឈីស និងតែផ្លែឈើស្រស់"),
    (re.compile(r"yogurt|smoothie|shake|juice|fruit|ទឹកក្រឡុក|យ៉ាអួ", re.I),
     "Fresh Avocado Smoothie, Passion Fruit Shake, Greek Yogurt Bowls, Cold-Pressed Juices",
     "ទឹកផ្លែបឺរក្រឡុក ទឹកក្រូចឆ្មាផាសិន យ៉ាអួផ្លែឈើ និងទឹកផ្លែឈើស្រស់"),

    # Bakery & Desserts
    (re.compile(r"bakery|cake|pastry|bread|croissant|dessert|នំប៉័ង|នំ|នំខេក", re.I),
     "French Butter Croissants, Fresh Baguettes, Chocolate Mousse Cake, Fruit Danish, Egg Tarts",
     "នំប៉័ងបារាំង ក្រូសង់ប៊័រ នំខេកសូកូឡា និងនំដេនីសផ្លែឈើ"),
    (re.compile(r"ice\s*cream|gelato|bingsoo|bingsu|ការ៉េម", re.I),
     "Artisan Gelato, Mango Bingsu (Korean Shaved Snow Ice), Waffle Sundae Bowls",
     "ការ៉េមជេឡាតូ ប៊ីងស៊ូផ្លែស្វាយ និងការ៉េមកែវធំ"),
]

def get_signature_items(text: str) -> tuple[str, str]:
    for pat, sig_en, sig_kh in CATEGORY_SIGNATURE_ITEMS:
        if pat.search(text):
            return sig_en, sig_kh
    return (
        "Khmer Made-to-Order Dishes: Beef Lok Lak, Pork with Rice, Fried Rice, Stir-Fried Morning Glory",
        "បាយម្ហូបកុម្ម៉ង់ ឡុកឡាក់សាច់គោ បាយសាច់ជ្រូក បាយឆា និងឆាត្រកួន"
    )

def transform_overture_data(max_rows: int = None) -> list[dict]:
    """Transform Overture Maps food venues into normalized search places."""
    if not RAW_OVERTURE_PATH.exists():
        print(f"Error: {RAW_OVERTURE_PATH} does not exist.")
        return []

    print(f"Loading Overture raw places from {RAW_OVERTURE_PATH}...")
    df = pd.read_csv(RAW_OVERTURE_PATH, dtype=str)
    print(f"Total raw places in file: {len(df)}")

    places = []
    seen_ids = set()

    for idx, row in df.iterrows():
        raw_id = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        category = str(row.get("category") or "").strip().lower()
        facebook = str(row.get("facebook") or "").strip()
        website = str(row.get("website") or "").strip()
        
        try:
            lat = float(row.get("lat"))
            lng = float(row.get("lng"))
        except (ValueError, TypeError):
            lat, lng = None, None

        if not name or name.lower() in ["unknown", "restaurant", "none", "nan"]:
            continue

        venue_id = f"overture-{raw_id[:12]}" if raw_id else f"overture-{idx}"
        if venue_id in seen_ids:
            continue
        seen_ids.add(venue_id)

        # 1. Resolve Area
        area = find_nearest_khan(lat, lng, name)

        # 2. Resolve Category & Dish
        if category in OVERTURE_CATEGORY_MAP:
            dish_en, dish_kh, price_usd, base_tags = OVERTURE_CATEGORY_MAP[category]
        else:
            dish_en = "Khmer & Asian Made-to-Order Dishes"
            dish_kh = "បាយម្ហូបកុម្ម៉ង់ និងម្ហូបខ្មែរ"
            price_usd = "2.75"
            base_tags = "restaurant;khmer;rice;dinner"

        # Check name for more specific cuisine keywords if general category
        target_text = f"{name} {dish_en} {dish_kh} {base_tags}"
        sig_en, sig_kh = get_signature_items(target_text)

        # 3. Resolve Contact / Ordering links
        page_url = ""
        if website and website.startswith("http") and not any(bad in website for bad in ["google.com/maps", "maps.app"]):
            page_url = website
        elif facebook and facebook.startswith("http"):
            page_url = facebook

        source_url = facebook if (facebook and facebook.startswith("http")) else (website if (website and website.startswith("http")) else "")

        # 4. Hours, price, rating: Overture has none of them, so they stay empty (never a guess from the category)

        # 5. Build the description from what is known
        desc_parts = [
            f"Serving {dish_en} ({dish_kh}) in {area}, Cambodia.",
            f"មានបម្រើ {dish_kh} នៅ{area}។",
        ]

        if page_url:
            desc_parts.append(f"How to order: Contact / view menu online at {page_url}. អាចមើលម៉ឺនុយ និងទាក់ទងតាមអនឡាញ។")

        places.append({
            "id": venue_id,
            "name": name,
            "dish_en": dish_en,
            "dish_kh": dish_kh,
            "description": " ".join(desc_parts),
            "tags": f"{base_tags};overture",
            "price_usd": "",
            "area": area,
            "lat": f"{lat:.6f}" if lat else "",
            "lng": f"{lng:.6f}" if lng else "",
            "rating": "",
            "open_hour": "",
            "close_hour": "",
            "source": "overture",
            "source_url": source_url,
            "date": "2026-11-05",
            "image_path": "",
            "phone_public": "",
            "page_url": page_url,
        })

        if max_rows and len(places) >= max_rows:
            break

    return places

def main():
    places = transform_overture_data()
    print(f"Successfully processed {len(places)} food places from Overture Maps!")
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"✅ Saved to {OUTPUT_CSV_PATH}")

        # Summary of cuisines
        df_out = pd.DataFrame(places)
        print("\nTop Cuisines / Categories generated:")
        print(df_out["dish_en"].value_counts().head(20).to_string())
        print("\nTop Areas generated:")
        print(df_out["area"].value_counts().head(14).to_string())

if __name__ == "__main__":
    main()
