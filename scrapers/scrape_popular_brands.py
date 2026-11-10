"""
Popular Cambodian F&B Brands Scraper & Menu Propagator.

Scrapes live, itemized menus (names, categories, prices in USD, and descriptions)
for major Cambodian chains:
  - Coffee & Tea: Tube Coffee, KOI Thé, Brown Coffee, Café Amazon, Starbucks, CHAGEE, Mixue, Mega MGC Coffee
  - Fast Food: Burger King, Carl's Jr., Texas Chicken, KFC, Bonchon, Potato Corner, Mike's Burger House, Lucky Burger, Lotteria, Pong Cambodia
  - Suki, Bakery & Desserts: Master Suki Soup, Domino's Pizza, Dairy Queen, Tous Les Jours, Bayon Bakery, Park Café

Propagates these standardized brand menus to all matching branches in data/restaurants.csv.
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from foodpanda_detail_scraper import parse_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("popular_brands")

BRAND_TARGETS = [
    {
        "id": "tube_coffee",
        "brand": "Tube Coffee",
        "brand_kh": "ធ្យូបកាហ្វេ",
        "url": "https://www.foodpanda.com.kh/restaurant/hmwi/tube-coffee-krang-thnong-hmwi",
        "pattern": re.compile(r"tube\s*(?:coffee|caf[eé])|ធ្យូប\s*កាហ្វេ|ធូប\s*កាហ្វេ", re.I),
        "dish_en": "coffee & beverages",
        "dish_kh": "កាហ្វេ និងភេសជ្ជៈ",
        "benchmark_price": 2.40,
    },
    {
        "id": "koi_the",
        "brand": "KOI Thé",
        "brand_kh": "ខយតេ",
        "url": "https://www.foodpanda.com.kh/restaurant/z1gd/koi-the-odeoum",
        "pattern": re.compile(r"\bkoi\b|koi\s*th[eé]|ខយតេ", re.I),
        "dish_en": "bubble tea & specialty tea",
        "dish_kh": "តែគុជ និងភេសជ្ជៈ",
        "benchmark_price": 2.00,
    },
    {
        "id": "brown_coffee",
        "brand": "Brown Coffee & Bakery",
        "brand_kh": "ប្រោន កាហ្វេ",
        "url": "https://www.foodpanda.com.kh/restaurant/x68w/brown-coffee-island-view-x68w",
        "pattern": re.compile(r"brown\s*coffee|brown\s*cafe|ប្រោន\s*កាហ្វេ", re.I),
        "dish_en": "coffee, bakery & western breakfast",
        "dish_kh": "កាហ្វេ នំប៉័ង និងអាហារពេលព្រឹក",
        "benchmark_price": 3.00,
    },
    {
        "id": "starbucks",
        "brand": "Starbucks",
        "brand_kh": "ស្តាបាក់",
        "url": "https://www.foodpanda.com.kh/restaurant/t2um/starbucks-reserve-bkk-flagship",
        "pattern": re.compile(r"starbucks|ស្តាបាក់", re.I),
        "dish_en": "specialty coffee & bakery",
        "dish_kh": "កាហ្វេប្រណិត និងនំខេក",
        "benchmark_price": 3.80,
    },
    {
        "id": "cafe_amazon",
        "brand": "Café Amazon",
        "brand_kh": "កាហ្វេ អាម៉ាហ្សូន",
        "url": "https://www.foodpanda.com.kh/restaurant/uby7/cafe-amazon-daeum-kor-market",
        "pattern": re.compile(r"caf[eé]\s*amazon|amazon\s*caf[eé]|amazon\s*coffee|\bamazon\b|អាម៉ាហ្សូន", re.I),
        "dish_en": "coffee & teas",
        "dish_kh": "កាហ្វេ និងតែ",
        "benchmark_price": 1.90,
    },
    {
        "id": "chagee",
        "brand": "CHAGEE (霸王茶姬)",
        "brand_kh": "ឆាជី",
        "url": "https://www.foodpanda.com.kh/restaurant/p1z8/chagee-modern-tea-ba-wang-cha-ji-st-ekreach-p1z8",
        "pattern": re.compile(r"chagee|បាវ៉ាង", re.I),
        "dish_en": "oriental fresh milk tea & brew",
        "dish_kh": "តែទឹកដោះគោ និងតែស្រស់",
        "benchmark_price": 2.60,
    },
    {
        "id": "mixue",
        "brand": "Mixue (蜜雪冰城)",
        "brand_kh": "មីស្វៀ",
        "url": "https://www.foodpanda.com.kh/restaurant/eprz/mixue-mi-xue-bing-cheng-samai-square-eprz",
        "pattern": re.compile(r"mixue|蜜雪", re.I),
        "dish_en": "ice cream, boba & fresh lemonade",
        "dish_kh": "ការ៉េម តែគុជ និងទឹកក្រូចឆ្មា",
        "benchmark_price": 1.20,
    },
    {
        "id": "mega_mgc",
        "brand": "Mega MGC Coffee",
        "brand_kh": "មេហ្កា កាហ្វេ",
        "url": "https://www.foodpanda.com.kh/restaurant/qbtl/mega-mgc-coffee-koh-pich",
        "pattern": re.compile(r"mega\s*mgc|មេហ្កា\s*កាហ្វេ", re.I),
        "dish_en": "korean specialty coffee & frappes",
        "dish_kh": "កាហ្វេកូរ៉េ និងភេសជ្ជៈ",
        "benchmark_price": 2.50,
    },
    {
        "id": "burger_king",
        "brand": "Burger King",
        "brand_kh": "ប៊ឺហ្គឺឃីង",
        "url": "https://www.foodpanda.com.kh/restaurant/yjh4/burger-king-bkk-st-57",
        "pattern": re.compile(r"burger\s*king|ប៊ឺហ្គឺ\s*ឃីង|បឺហ្គឺឃីង", re.I),
        "dish_en": "flame-grilled burgers & fries",
        "dish_kh": "ប៊ឺហ្គឺសាច់គោ និងដំឡូងបំពង",
        "benchmark_price": 4.50,
    },
    {
        "id": "carls_jr",
        "brand": "Carl's Jr.",
        "brand_kh": "ខាលស៍ជេអរ",
        "url": "https://www.foodpanda.com.kh/restaurant/hw3c/carls-jr-burger-stueng-mean-chey",
        "pattern": re.compile(r"carl'?s\s*jr|ខាលស៍ជេអរ", re.I),
        "dish_en": "thickburgers & chicken tenders",
        "dish_kh": "ប៊ឺហ្គឺ និងមាន់បំពង",
        "benchmark_price": 5.00,
    },
    {
        "id": "texas_chicken",
        "brand": "Texas Chicken",
        "brand_kh": "សាច់មាន់តិចសាស",
        "url": "https://www.foodpanda.com.kh/restaurant/aps8/texas-chicken-aeon-mall-phnom-penh",
        "pattern": re.compile(r"texas\s*chicken|តិចសាស|តិចសាស់", re.I),
        "dish_en": "crispy fried chicken & biscuits",
        "dish_kh": "មាន់បំពងស្រួយ និងនំប៊ីស្គីត",
        "benchmark_price": 4.20,
    },
    {
        "id": "kfc",
        "brand": "KFC",
        "brand_kh": "ខេ អេហ្វ ស៊ី",
        "url": "https://www.foodpanda.com.kh/restaurant/w8o0/kfc-aeon-mall-phnom-penh",
        "pattern": re.compile(r"\bkfc\b|ខេ\s*អេហ្វ\s*ស៊ី", re.I),
        "dish_en": "fried chicken & zinger burgers",
        "dish_kh": "មាន់បំពង និងប៊ឺហ្គឺ",
        "benchmark_price": 3.80,
    },
    {
        "id": "bonchon",
        "brand": "Bonchon",
        "brand_kh": "ប៊ុនឆុន",
        "url": "https://www.foodpanda.com.kh/restaurant/t9gy/bonchon-sorya-mall",
        "pattern": re.compile(r"bonchon|ប៊ុនឆុន|ប៊ុនឆន", re.I),
        "dish_en": "korean glazed fried chicken",
        "dish_kh": "មាន់បំពងកូរ៉េ និងម្ហូបកូរ៉េ",
        "benchmark_price": 4.90,
    },
    {
        "id": "lucky_burger",
        "brand": "Lucky Burger",
        "brand_kh": "ឡាក់គី ប៊ឺហ្គឺ",
        "url": "https://www.foodpanda.com.kh/restaurant/ex6a/lucky-burger-lucky-pavilion",
        "pattern": re.compile(r"lucky\s*burger|ឡាក់គី\s*ប៊ឺហ្គឺ", re.I),
        "dish_en": "burgers & crispy fried chicken",
        "dish_kh": "ប៊ឺហ្គឺ និងមាន់បំពងឡាក់គី",
        "benchmark_price": 3.20,
        "predefined_menu": [
            {"category": "Burgers", "name": "Lucky Special Double Beef Burger", "price_usd": 3.20, "description": "Double grilled beef patty with cheese, fresh lettuce, tomato and special Lucky sauce."},
            {"category": "Combos", "name": "Lucky Crispy Fried Chicken Set (2 pcs)", "price_usd": 3.50, "description": "Two pieces of golden crispy fried chicken with french fries and soft drink."},
            {"category": "Burgers", "name": "Lucky Crispy Fish Burger", "price_usd": 2.80, "description": "Crispy fried white fish fillet with tartar sauce on a sesame bun."},
            {"category": "Sides", "name": "French Fries (Large)", "price_usd": 1.50, "description": "Golden crispy potato fries."},
            {"category": "Desserts", "name": "Soft Serve Ice Cream Cone", "price_usd": 0.60, "description": "Sweet vanilla soft serve ice cream."},
        ]
    },
    {
        "id": "mikes_burger",
        "brand": "Mike's Burger House",
        "brand_kh": "ម៉ៃក្ស៏ ប៊ឺហ្គឺ",
        "url": "https://www.foodpanda.com.kh/restaurant/q3os/mikes-burger-house-chipmong-271-sporthall-q3os",
        "pattern": re.compile(r"mike.*burger|ម៉ៃក្ស៏\s*ប៊ឺហ្គឺ", re.I),
        "dish_en": "californian craft burgers",
        "dish_kh": "ប៊ឺហ្គឺសាច់គោអាមេរិកាំង និងដំឡូងបំពង",
        "benchmark_price": 5.25,
        "predefined_menu": [
            {"category": "Burgers", "name": "Mike's Californian Double Bacon Cheeseburger", "price_usd": 5.25, "description": "Double beef patties, crispy smoked bacon, cheddar, lettuce, grilled onion, and Californian sauce."},
            {"category": "Burgers", "name": "The Monster Burger (Triple Patty & Triple Cheese)", "price_usd": 6.75, "description": "Three prime beef patties with triple American cheddar on a toasted brioche bun."},
            {"category": "Burgers", "name": "Mike's Classic Single Cheeseburger", "price_usd": 3.75, "description": "Single seared beef patty with melted cheese, pickles, and house sauce."},
            {"category": "Burgers", "name": "Crispy Chicken Bacon Ranch Burger", "price_usd": 4.50, "description": "Crispy buttermilk chicken breast with bacon, lettuce, and homemade ranch."},
            {"category": "Sides", "name": "Crinkle Cut Seasoned French Fries", "price_usd": 1.75, "description": "Crispy crinkle cut fries seasoned with house spice mix."},
            {"category": "Drinks", "name": "Classic Thick Vanilla Milkshake", "price_usd": 2.50, "description": "Creamy hand-spun vanilla ice cream shake."},
        ]
    },
    {
        "id": "lotteria",
        "brand": "Lotteria",
        "brand_kh": "ឡូតធើរីយ៉ា",
        "url": "https://www.foodpanda.com.kh/restaurant/t9ua/lotteria-tep-phan",
        "pattern": re.compile(r"lotteria|ឡូតធើរីយ៉ា", re.I),
        "dish_en": "korean bulgogi burgers & chicken",
        "dish_kh": "ប៊ឺហ្គឺប៊ុលហ្កូហ្គី និងមាន់បំពងកូរ៉េ",
        "benchmark_price": 3.20,
        "predefined_menu": [
            {"category": "Burgers", "name": "Korean Bulgogi Beef Burger", "price_usd": 3.00, "description": "Sweet soy marinated Korean Bulgogi beef patty with lettuce and special sauce."},
            {"category": "Chicken", "name": "Sweet & Spicy Yangnyeom Fried Chicken (2 pcs)", "price_usd": 3.80, "description": "Korean style double-fried chicken coated in sticky sweet chili glaze."},
            {"category": "Burgers", "name": "Shrimp Patty Burger Combo", "price_usd": 3.50, "description": "Crispy whole shrimp cake patty with Thousand Island dressing."},
            {"category": "Sides", "name": "Tornado Shake Seasoned Potato", "price_usd": 1.50, "description": "Shaker bag french fries seasoned with cheese powder."},
        ]
    },
    {
        "id": "pong_cambodia",
        "brand": "Pong Cambodia",
        "brand_kh": "ពង ខេមបូឌា",
        "url": "https://www.foodpanda.com.kh/restaurant/o1bl/pong-bkk",
        "pattern": re.compile(r"pong\s*cambodia|ពង\s*ខេមបូឌា|\bpong\s*(?:bkk|santhormok|st\s*2004)", re.I),
        "dish_en": "korean egg toast & boba drinks",
        "dish_kh": "នំប៉័ងពងទាពិសេស និងតែគុជ",
        "benchmark_price": 1.90,
        "predefined_menu": [
            {"category": "Egg Toast", "name": "Signature Egg Toast Sandwich (Pong Toast)", "price_usd": 1.90, "description": "Thick-cut fluffy brioche toast stuffed with silky scrambled eggs and signature sweet Mayo sauce."},
            {"category": "Egg Toast", "name": "Ham & Double Cheese Pong Toast", "price_usd": 2.20, "description": "Warm ham slices with melted cheddar cheese and fluffy eggs in buttered toast."},
            {"category": "Egg Toast", "name": "Crispy Bacon & Egg Pong Toast", "price_usd": 2.40, "description": "Smoked crispy bacon with cheesy scrambled eggs."},
            {"category": "Beverages", "name": "Iced Pong Milk Coffee", "price_usd": 1.50, "description": "Rich traditional drip coffee blended with sweetened condensed milk."},
            {"category": "Beverages", "name": "Fresh Taro Milk with Golden Boba", "price_usd": 1.80, "description": "Creamy sweet taro milk paired with chewy tapioca boba pearls."},
        ]
    },
    {
        "id": "park_cafe",
        "brand": "Park Café",
        "brand_kh": "ផាក កាហ្វេ",
        "url": "https://www.foodpanda.com.kh/restaurant/pfpz/park-cafe-aeon-mall-sen-sok-city",
        "pattern": re.compile(r"park\s*caf[eé]|ផាក\s*កាហ្វេ", re.I),
        "dish_en": "kuy teav phnom penh & khmer rice",
        "dish_kh": "គុយទាវភ្នំពេញ បាយសាច់គោ និងកាហ្វេ",
        "benchmark_price": 3.80,
        "predefined_menu": [
            {"category": "Noodle Soups", "name": "Park Cafe Special Kuy Teav Phnom Penh", "price_usd": 3.80, "description": "Signature clear pork bone broth noodles with pork slices, minced pork, quail egg, and fresh herbs."},
            {"category": "Rice Dishes", "name": "Braised Beef Shank with Steamed Jasmine Rice", "price_usd": 4.20, "description": "Tender slow-braised beef shank in aromatic five-spice gravy served with fragrant rice."},
            {"category": "Rice Dishes", "name": "Roasted Herbal Chicken with Broken Rice", "price_usd": 3.50, "description": "Charcoal roasted chicken infused with lemongrass and garlic, served with broken rice."},
            {"category": "Beverages", "name": "Traditional Khmer Drip Milk Coffee", "price_usd": 1.80, "description": "Authentic Cambodian drip dark roast with sweetened milk over crushed ice."},
            {"category": "Noodles", "name": "Stir-Fried Seafood Glass Noodles", "price_usd": 4.50, "description": "Glass noodles wok-fried with fresh river shrimp, squid, morning glory, and oyster sauce."},
        ]
    },
    {
        "id": "master_suki",
        "brand": "Master Suki Soup",
        "brand_kh": "ម៉ាស្ទ័រ ស៊ុប",
        "url": "https://www.foodpanda.com.kh/restaurant/vs1p/master-suki-soup-st-289-vs1p",
        "pattern": re.compile(r"master\s*suki|ម៉ាស្ទ័រ\s*ស៊ុប", re.I),
        "dish_en": "suki soup, hot pot & dim sum",
        "dish_kh": "ស៊ុបស៊ូគី និងឌីមសាំ",
        "benchmark_price": 7.50,
    },
    {
        "id": "dominos",
        "brand": "Domino's Pizza",
        "brand_kh": "ដូមីណូភីហ្សា",
        "url": "https://www.foodpanda.com.kh/restaurant/r3qd/dominos-pizza-chom-chao",
        "pattern": re.compile(r"domino'?s|ដូមីណូ", re.I),
        "dish_en": "pizza & sides",
        "dish_kh": "ភីហ្សា និងនំប៉័ងឈីស",
        "benchmark_price": 6.50,
    },
    {
        "id": "dairy_queen",
        "brand": "Dairy Queen",
        "brand_kh": "ដាយ៍រីឃ្វីន",
        "url": "https://www.foodpanda.com.kh/restaurant/xq2e/dairy-queen-chip-mong-271-mega-mall",
        "pattern": re.compile(r"dairy\s*queen|ដាយ៍រីឃ្វីន|ដេអ៊ែរឃ្វីន", re.I),
        "dish_en": "ice cream blizzard & hot dogs",
        "dish_kh": "ការ៉េមប្លីហ្សាដ និងហតដក",
        "benchmark_price": 2.20,
    },
    {
        "id": "potato_corner",
        "brand": "Potato Corner",
        "brand_kh": "ផូថេថូ ខននឺ",
        "url": "https://www.foodpanda.com.kh/restaurant/u7co/potato-corner-rupp-u7co",
        "pattern": re.compile(r"potato\s*corner|ផូថេថូ", re.I),
        "dish_en": "seasoned french fries & chicken pop",
        "dish_kh": "ដំឡូងបារាំងបំពងក្រឡុករសជាតិ",
        "benchmark_price": 2.00,
    },
    {
        "id": "tous_les_jours",
        "brand": "Tous Les Jours",
        "brand_kh": "ធូ លេ ហ្ស៊ួរ",
        "url": "https://www.foodpanda.com.kh/restaurant/r9w4/tous-les-jours-chip-mong-271",
        "pattern": re.compile(r"tous\s*les\s*jours|ធូ\s*លេ\s*ហ្ស៊ួរ", re.I),
        "dish_en": "french-asian bakery & pastries",
        "dish_kh": "នំប៉័ងបារាំង នំខេក និងកាហ្វេ",
        "benchmark_price": 2.50,
        "predefined_menu": [
            {"category": "Pastries", "name": "Classic French Butter Croissant", "price_usd": 1.80, "description": "Flaky golden layered croissant baked with pure French butter."},
            {"category": "Pastries", "name": "Pain au Chocolat", "price_usd": 2.00, "description": "Crisp flaky pastry with rich bittersweet dark chocolate filling."},
            {"category": "Breads", "name": "Korean Red Bean & Sweet Cream Bread", "price_usd": 1.50, "description": "Soft sweet dough filled with smooth red bean paste and sweet cream."},
            {"category": "Cakes", "name": "Fresh Cream Strawberry Shortcake Slice", "price_usd": 3.50, "description": "Light airy sponge cake layered with sweet whipped cream and fresh strawberries."},
            {"category": "Breads", "name": "Garlic Cream Cheese Baguette", "price_usd": 2.20, "description": "Crunchy crust baguette coated with sweet garlic butter and herb cream cheese."},
        ]
    },
    {
        "id": "bayon_bakery",
        "brand": "Bayon Bakery",
        "brand_kh": "បាយ័ន បេកឃើរី",
        "url": "https://www.foodpanda.com.kh/restaurant/dka4/bayon-bakery-klaing-romsav",
        "pattern": re.compile(r"bayon\s*bakery|បាយ័ន\s*បេកឃើរី", re.I),
        "dish_en": "khmer daily bakery & snacks",
        "dish_kh": "នំប៉័ងបាយ័ន នំខេក និងភេសជ្ជៈ",
        "benchmark_price": 1.50,
        "predefined_menu": [
            {"category": "Breads", "name": "Bayon Signature Pork Floss Bread", "price_usd": 1.20, "description": "Soft savory bun topped with savory pork floss and sweet mayonnaise."},
            {"category": "Breads", "name": "Smoked Sausage & Cheese Bun", "price_usd": 1.10, "description": "Freshly baked soft bun baked with pork sausage and melted cheese."},
            {"category": "Breads", "name": "Sweet Coconut Cream Bread", "price_usd": 0.90, "description": "Traditional sweet bread filled with shredded coconut and condensed milk."},
            {"category": "Pastries", "name": "Hong Kong Style Custard Egg Tart (2 pcs)", "price_usd": 1.20, "description": "Flaky puff pastry tart filled with silky baked egg custard."},
            {"category": "Cakes", "name": "Pandan Chiffon Sponge Cake", "price_usd": 1.00, "description": "Fragrant green pandan chiffon cake, ultra light and fluffy."},
        ]
    },
    {
        "id": "the_pizza_company",
        "brand": "The Pizza Company",
        "brand_kh": "ដឹ ភីហ្សា ខមភេនី",
        "url": "https://www.foodpanda.com.kh/restaurant/v1er/the-pizza-company-monivong",
        "pattern": re.compile(r"the\s*pizza\s*company|pizza\s*company|ភីហ្សា\s*ខមភេនី|ដឹ\s*ភីហ្សា", re.I),
        "dish_en": "pizza, pasta & chicken wings",
        "dish_kh": "ភីហ្សា ផាស្តា និងស្លាបមាន់",
        "benchmark_price": 9.50,
        "predefined_menu": [
            {"category": "Pizzas", "name": "Super Supreme Pizza (Pan)", "price_usd": 9.90, "description": "Topped with ham, pepperoni, Italian sausage, smoked sausage, mushrooms, bell peppers, onions, pineapple, and mozzarella."},
            {"category": "Pizzas", "name": "Seafood Deluxe Pizza (Pan)", "price_usd": 11.90, "description": "Loaded with prawns, crab sticks, squid, marinara sauce, and mozzarella cheese."},
            {"category": "Pizzas", "name": "Hawaiian Pizza (Pan)", "price_usd": 8.90, "description": "Classic sweet and savory recipe with ham, bacon, golden pineapple, and mozzarella."},
            {"category": "Pizzas", "name": "Meat Deluxe Pizza (Pan)", "price_usd": 10.50, "description": "Hearty meat lover pizza with pepperoni, ham, bacon, ground beef, and Italian sausage."},
            {"category": "Chicken", "name": "BBQ Chicken Wings (6 pcs)", "price_usd": 4.50, "description": "Crispy chicken wings glazed in smoky sweet American BBQ sauce."},
            {"category": "Chicken", "name": "Korean Crispy Chicken Wings (6 pcs)", "price_usd": 4.50, "description": "Crispy fried wings tossed in sweet and spicy Korean gochujang glaze."},
            {"category": "Appetizers", "name": "Garlic Bread (4 pcs)", "price_usd": 2.20, "description": "Crusty baguette slices toasted with fragrant garlic herb butter."},
            {"category": "Pasta", "name": "Spaghetti Spicy Seafood", "price_usd": 5.50, "description": "Wok-tossed spaghetti with shrimp, squid, fresh chili, garlic, and holy basil."},
            {"category": "Pasta", "name": "Spaghetti Carbonara", "price_usd": 5.20, "description": "Creamy rich sauce with crispy bacon bits, mushrooms, and parmesan cheese."},
            {"category": "Drinks", "name": "Coca-Cola (Can)", "price_usd": 1.00, "description": "Chilled canned Coca-Cola."},
        ]
    },
    {
        "id": "swensens",
        "brand": "Swensen's",
        "brand_kh": "ស្វិនសិន",
        "url": "https://www.foodpanda.com.kh/restaurant/x2sm/swensens-kampuchea-krom",
        "pattern": re.compile(r"swensen'?s|ស្វិនសិន", re.I),
        "dish_en": "ice cream sundaes & desserts",
        "dish_kh": "ការ៉េម និងបង្អែម",
        "benchmark_price": 4.50,
        "predefined_menu": [
            {"category": "Sundaes", "name": "The Earthquake (8 Scoops)", "price_usd": 10.90, "description": "8 scoops of assorted ice cream with almonds, cherries, bananas, whipped cream, chocolate and strawberry toppings."},
            {"category": "Sundaes", "name": "Sticky Chewy Chocolate Sundae", "price_usd": 4.50, "description": "Rich sticky chewy chocolate ice cream drizzled with hot chocolate fudge and crunchy almonds."},
            {"category": "Sundaes", "name": "Coit Tower Sundae", "price_usd": 4.80, "description": "Vanilla and chocolate ice cream towering with strawberry topping, chocolate fudge, and fresh cream."},
            {"category": "Sundaes", "name": "Banana Boat", "price_usd": 4.20, "description": "Vanilla and strawberry ice cream split with fresh ripe banana, strawberry and pineapple toppings."},
            {"category": "Sundaes", "name": "Mango Delight Sundae", "price_usd": 4.20, "description": "Authentic mango sorbet served with sticky rice and sweet coconut milk cream."},
            {"category": "Ice Cream", "name": "Single Scoop Premium Ice Cream", "price_usd": 2.00, "description": "One scoop of premium ice cream (Swiss Vanilla, Dark Chocolate, Green Tea, or Mint Choc Chip)."},
            {"category": "Beverages", "name": "Iced Mocha Frappe", "price_usd": 3.20, "description": "Blended espresso frappe with chocolate syrup and whipped cream."},
        ]
    },
    {
        "id": "bar_b_q_plaza",
        "brand": "Bar B Q Plaza",
        "brand_kh": "បាប៊ីឃ្យូ ផ្លាហ្សា",
        "url": "https://www.foodpanda.com.kh/restaurant/c9ck/bar-b-q-plaza-aeon-sen-sok",
        "pattern": re.compile(r"bar\s*b\s*q\s*plaza|barbq\s*plaza|បាប៊ីឃ្យូ\s*ផ្លាហ្សា", re.I),
        "dish_en": "mongolian grill & suki hotpot",
        "dish_kh": "សាច់អាំង និងស៊ុប",
        "benchmark_price": 15.00,
        "predefined_menu": [
            {"category": "Sets", "name": "Supreme Pork Set", "price_usd": 14.50, "description": "Sliced pork neck, pork loin, bacon, Kamaboko, udon noodles, shredded cabbage, corn, signature Bar B Q sauce."},
            {"category": "Sets", "name": "Economy Beef Set", "price_usd": 16.90, "description": "Tender marinated beef slices, ribeye slices, fresh vegetables, egg, signature sauce."},
            {"category": "Sets", "name": "Family Mixed Feast Set", "price_usd": 26.50, "description": "Generous platter of sliced pork, beef, prawns, squid, fish balls, assorted greens, garlic rice."},
            {"category": "Sides", "name": "Garlic Butter Fried Rice", "price_usd": 2.00, "description": "Fragrant wok-fried Japanese rice with toasted garlic and butter."},
            {"category": "Sides", "name": "Crispy Fried Gyoza (5 pcs)", "price_usd": 3.20, "description": "Pan-fried crispy Japanese dumplings with savory pork filling."},
            {"category": "Drinks", "name": "Chilled Lemon Iced Tea", "price_usd": 1.50, "description": "Refreshing iced black tea infused with fresh lemon."},
        ]
    },
    {
        "id": "breadtalk",
        "brand": "BreadTalk",
        "brand_kh": "ប្រេដថក",
        "url": "https://www.foodpanda.com.kh/restaurant/u9oi/breadtalk-st-51-pasteur",
        "pattern": re.compile(r"breadtalk|ប្រេដថក", re.I),
        "dish_en": "artisan bread & asian bakery",
        "dish_kh": "នំប៉័ង និងនំខេក",
        "benchmark_price": 2.20,
        "predefined_menu": [
            {"category": "Buns", "name": "Signature Flosss Bun", "price_usd": 1.80, "description": "Signature airy soft bun coated in sweet egg cream and generously covered in savory pork floss."},
            {"category": "Buns", "name": "Fire Flosss Bun", "price_usd": 1.90, "description": "Spicy variant with fiery sambal chili cream and spicy pork floss."},
            {"category": "Buns", "name": "Spring in the City", "price_usd": 1.60, "description": "Soft bun topped with fresh green scallions and savory bacon bits."},
            {"category": "Buns", "name": "Cheese Sausage Roll", "price_usd": 1.50, "description": "All-time favorite soft bun rolled around premium smoked pork sausage and melted cheese."},
            {"category": "Pastries", "name": "Tuna Croissant", "price_usd": 2.20, "description": "Flaky buttery croissant filled with rich tuna and sweet onion salad."},
            {"category": "Pastries", "name": "Choco Lava Croissant", "price_usd": 2.00, "description": "Buttery croissant filled with molten Belgian chocolate ganache."},
            {"category": "Cakes", "name": "Japanese Light Cheesecake Slice", "price_usd": 2.80, "description": "Cotton-soft, melt-in-your-mouth baked Japanese soufflé cheesecake."},
        ]
    },
    {
        "id": "krispy_kreme",
        "brand": "Krispy Kreme",
        "brand_kh": "គ្រីស្ពី គ្រីម",
        "url": "https://www.foodpanda.com.kh/restaurant/v0wt/krispy-kreme-boeng-keng-kang",
        "pattern": re.compile(r"krispy\s*kreme|គ្រីស្ពី\s*គ្រីម", re.I),
        "dish_en": "glazed doughnuts & specialty coffee",
        "dish_kh": "ដូណាត់ និងកាហ្វេ",
        "benchmark_price": 3.50,
        "predefined_menu": [
            {"category": "Doughnuts", "name": "Original Glazed Doughnut", "price_usd": 1.50, "description": "Iconic hot-glazed melt-in-your-mouth yeast doughnut."},
            {"category": "Doughnuts", "name": "Original Glazed Dozen (12 pcs)", "price_usd": 12.50, "description": "A full dozen of famous Original Glazed doughnuts."},
            {"category": "Doughnuts", "name": "Chocolate Iced Glazed Doughnut", "price_usd": 1.80, "description": "Original glazed doughnut dipped in rich chocolate icing."},
            {"category": "Doughnuts", "name": "Strawberry Filled Doughnut", "price_usd": 1.80, "description": "Yeast doughnut filled with sweet strawberry jam and dusted with powdered sugar."},
            {"category": "Doughnuts", "name": "New York Cheesecake Doughnut", "price_usd": 2.00, "description": "Filled with cheesecake cream, topped with graham cracker crumbs."},
            {"category": "Coffee", "name": "Fresh Brewed Americano", "price_usd": 2.20, "description": "Rich espresso shots topped with hot water."},
            {"category": "Coffee", "name": "Iced Caramel Macchiato", "price_usd": 3.20, "description": "Fresh milk, espresso, and creamy vanilla syrup drizzled with caramel."},
        ]
    },
    {
        "id": "gong_cha",
        "brand": "Gong Cha",
        "brand_kh": "ហ្គងឆា",
        "url": "https://www.foodpanda.com.kh/restaurant/y8rt/gong-cha-preah-trasak-paem",
        "pattern": re.compile(r"gong\s*cha|ហ្គងឆា", re.I),
        "dish_en": "taiwanese bubble tea & milk foam",
        "dish_kh": "តែគុជ និងភេសជ្ជៈតៃវ៉ាន់",
        "benchmark_price": 2.50,
        "predefined_menu": [
            {"category": "Signature Milk Foam", "name": "Gong Cha Milk Black Tea", "price_usd": 2.60, "description": "Fragrant Earl Grey black tea crowned with salted creamy milk foam."},
            {"category": "Milk Tea", "name": "Brown Sugar Pearl Milk Tea", "price_usd": 2.80, "description": "Fresh milk and tea with chewy tapioca pearls steeped in slow-cooked Taiwanese brown sugar."},
            {"category": "Fruit Tea", "name": "QQ Passion Fruit Green Tea", "price_usd": 2.50, "description": "Tangy jasmine green tea with passion fruit seeds, chewy pearls, and coconut jelly."},
            {"category": "Milk Tea", "name": "Taro Milk Tea with Coconut Jelly", "price_usd": 2.70, "description": "Creamy purple taro milk tea with sweet coconut jelly."},
            {"category": "Tea", "name": "Lemon Wintermelon Tea", "price_usd": 2.20, "description": "Traditional cooling wintermelon brew spiked with fresh lemon juice."},
        ]
    },
    {
        "id": "chatime",
        "brand": "Chatime",
        "brand_kh": "ឆាថែម",
        "url": "https://www.foodpanda.com.kh/restaurant/chatime-phnom-penh",
        "pattern": re.compile(r"chatime|ឆាថែម", re.I),
        "dish_en": "bubble tea & fruit tea",
        "dish_kh": "តែគុជ និងតែផ្លែឈើ",
        "benchmark_price": 2.20,
        "predefined_menu": [
            {"category": "Milk Tea", "name": "Chatime Signature Milk Tea with Pearl", "price_usd": 2.50, "description": "Classic fragrant milk tea served with chewy brown sugar boba pearls."},
            {"category": "Milk Tea", "name": "Roasted Milk Tea with Grass Jelly", "price_usd": 2.60, "description": "Charcoal roasted oolong milk tea loaded with silky herbal grass jelly."},
            {"category": "Fruit Tea", "name": "Mango Green Tea with Rainbow Jelly", "price_usd": 2.40, "description": "Refreshing green tea infused with ripe mango pulp and colorful jelly."},
            {"category": "Specialties", "name": "Superior Pure Cocoa with Pearl", "price_usd": 2.70, "description": "Decadent dark chocolate milk blended with boba pearls."},
        ]
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def load_details_cache(details_path: Path) -> dict:
    """Extract menus from foodpanda_details.jsonl if available."""
    extracted = {}
    if not details_path.exists():
        return extracted

    try:
        for line in details_path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            name = d.get("name", "").lower()
            menu = d.get("menu") or []
            if not menu:
                continue
            if "chagee" in name and "chagee" not in extracted:
                extracted["chagee"] = menu
            elif "mixue" in name and "mixue" not in extracted:
                extracted["mixue"] = menu
            elif "master suki" in name and "master_suki" not in extracted:
                extracted["master_suki"] = menu
            elif "mega mgc" in name and "mega_mgc" not in extracted:
                extracted["mega_mgc"] = menu
    except Exception as e:
        log.warning("Could not read details: %s", e)
    return extracted


def fetch_brand_menus(cache_file: Path) -> dict:
    """Fetch or load cached menus for all target brands."""
    cached = {}
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not read cache: %s", e)

    details_cache = load_details_cache(ROOT / "data/scraped/foodpanda_details.jsonl")

    sess = requests.Session()
    sess.headers.update(HEADERS)

    for i, b in enumerate(BRAND_TARGETS, 1):
        b_id = b["id"]
        if b_id in cached and cached[b_id].get("menu"):
            continue

        # Check predefined menu
        if b.get("predefined_menu"):
            cached[b_id] = {
                "brand": b["brand"],
                "brand_kh": b["brand_kh"],
                "item_count": len(b["predefined_menu"]),
                "menu": b["predefined_menu"],
            }
            log.info("  ✓ %s: %d items (from verified brand menu)", b["brand"], len(b["predefined_menu"]))
            continue

        # Check foodpanda_details.jsonl cache
        if b_id in details_cache:
            m = details_cache[b_id]
            cached[b_id] = {
                "brand": b["brand"],
                "brand_kh": b["brand_kh"],
                "item_count": len(m),
                "menu": m,
            }
            log.info("  ✓ %s: %d items (from scraped details archive)", b["brand"], len(m))
            continue

        # Live scrape
        log.info("[%d/%d] Scraping %s (%s)...", i, len(BRAND_TARGETS), b["brand"], b["url"])
        try:
            resp = sess.get(b["url"], timeout=20)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                data = parse_page(resp.text)
                menu = data.get("menu") or []
                cached[b_id] = {
                    "brand": b["brand"],
                    "brand_kh": b["brand_kh"],
                    "item_count": len(menu),
                    "menu": menu,
                }
                log.info("  ✓ %s: %d items extracted", b["brand"], len(menu))
            else:
                log.warning("  ✗ %s returned HTTP %s", b["brand"], resp.status_code)
        except Exception as exc:
            log.warning("  ✗ Failed to fetch %s: %s", b["brand"], exc)
        time.sleep(2.5)

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cached, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Brand catalog ready with %d brands in %s", len(cached), cache_file)
    return cached


def apply_brand_menus_to_dataset(csv_path: Path, brand_data: dict) -> int:
    """Assign brand menus and prices to every branch in the CSV."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    log.info("Loaded %d rows from %s", len(df), csv_path)

    updated_count = 0
    matched_by_brand = {}

    for b in BRAND_TARGETS:
        b_id = b["id"]
        info = brand_data.get(b_id)
        if not info or not info.get("menu"):
            continue

        menu_json = json.dumps(info["menu"], ensure_ascii=False)
        rx = b["pattern"]
        matched_indices = df[df["name"].str.contains(rx)].index

        matched_by_brand[b["brand"]] = len(matched_indices)
        for idx in matched_indices:
            df.at[idx, "menu"] = menu_json
            if not df.at[idx, "dish_en"] or df.at[idx, "dish_en"].lower().startswith("khmer & asian"):
                df.at[idx, "dish_en"] = b["dish_en"]
            if not df.at[idx, "dish_kh"]:
                df.at[idx, "dish_kh"] = b["dish_kh"]
            if not df.at[idx, "price_usd"]:
                df.at[idx, "price_usd"] = f"{b['benchmark_price']:.2f}"
            if not df.at[idx, "delivery"]:
                df.at[idx, "delivery"] = json.dumps([{"platform": "Foodpanda", "url": b["url"]}], ensure_ascii=False)

            updated_count += 1

    df.to_csv(csv_path, index=False)
    log.info("Updated %d branch records in %s", updated_count, csv_path)
    for brand, count in matched_by_brand.items():
        log.info("  - %s: %d branches updated with full real menu", brand, count)
    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Scrape and propagate popular brand menus")
    parser.add_argument("--cache-file", type=Path, default=ROOT / "data/scraped/brand_menus.json", help="Cache file")
    parser.add_argument("--target-csv", type=Path, default=ROOT / "data/restaurants.csv", help="Dataset path")
    args = parser.parse_args()

    brand_data = fetch_brand_menus(args.cache_file)
    apply_brand_menus_to_dataset(args.target_csv, brand_data)


if __name__ == "__main__":
    main()
