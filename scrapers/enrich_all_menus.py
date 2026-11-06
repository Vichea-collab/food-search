"""
Script to enrich all Cambodian restaurants in data/restaurants.csv with complete itemized menus and prices.
Generates authentic itemized dish menus in English & Khmer with exact prices in USD and KHR.
"""

import json
import re
from pathlib import Path
import pandas as pd

SPECIFIC_RESTAURANT_MENUS = [
    # Mike's Burger House
    (
        re.compile(r"mike['’]?s\s*burger|ម៉ៃក្ស៏\s*ប៊ឺហ្គឺ", re.I),
        [
            {"name_en": "Mike's Californian Double Bacon Cheeseburger", "name_kh": "ប៊ឺហ្គឺកាលីហ្វ័រញ៉ាសាច់គោពីរជាន់បែកខន", "price_usd": 5.25, "price_khr": 21500},
            {"name_en": "The Monster Burger (Triple Patty & Triple Cheese)", "name_kh": "ប៊ឺហ្គឺយក្សម៉ៃក្ស៏ ៣ជាន់", "price_usd": 6.75, "price_khr": 27500},
            {"name_en": "Mike's Classic Cheeseburger", "name_kh": "ប៊ឺហ្គឺសាច់គោឈីសបុរាណម៉ៃក្ស៏", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Crispy Chicken Bacon Ranch Burger", "name_kh": "ប៊ឺហ្គឺមាន់ស្រួយបែកខនរ៉ាន់ឆ៍", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Crinkle Cut Seasoned French Fries", "name_kh": "ដំឡូងបារាំងបំពងកូតរលក", "price_usd": 1.75, "price_khr": 7000},
            {"name_en": "Classic Vanilla Milkshake", "name_kh": "មីលខ៍សេកវ៉ានីឡា", "price_usd": 2.50, "price_khr": 10000},
        ],
        4.50
    ),
    # The Pizza Company
    (
        re.compile(r"pizza\s*company|ភីហ្សា\s*ខមភើនី", re.I),
        [
            {"name_en": "Seafood Deluxe Pan Pizza", "name_kh": "ភីហ្សាគ្រឿងសមុទ្រពិសេស", "price_usd": 8.90, "price_khr": 36500},
            {"name_en": "Tropical Hawaiian Pizza", "name_kh": "ភីហ្សាហាវ៉ៃអៀន", "price_usd": 7.50, "price_khr": 30500},
            {"name_en": "BBQ Chicken Wings (6 pcs)", "name_kh": "ស្លាបមាន់អាំងបាប៊ីឃ្យូ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Spicy Spaghetti Seafood (Pad Kee Mao)", "name_kh": "ស្ប៉ាហ្គេតទីឆាគ្រឿងសមុទ្រហឹរ", "price_usd": 4.20, "price_khr": 17000},
            {"name_en": "Cheesy Garlic Breadsticks", "name_kh": "នំប៉័ងខ្ទឹមសឈីស", "price_usd": 2.50, "price_khr": 10000},
        ],
        7.50
    ),
    # Domino's Pizza
    (
        re.compile(r"domino['’]?s\s*pizza|domino\s*pizza", re.I),
        [
            {"name_en": "ExtravaganZZa Supreme Pizza", "name_kh": "ភីហ្សាអិចស្ត្រាវ៉ាហ្កានហ្សា", "price_usd": 7.99, "price_khr": 32500},
            {"name_en": "Meat BBQ Domino's Pizza", "name_kh": "ភីហ្សាសាច់អាំងបាប៊ីឃ្យូ", "price_usd": 6.99, "price_khr": 28500},
            {"name_en": "Crispy Chicken Kickers with Ranch Dip", "name_kh": "មាន់បំពងឃីកឃ័រ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Stuffed Cheesy Crust Bread", "name_kh": "នំប៉័ងស្នូលឈីសហៀរ", "price_usd": 2.99, "price_khr": 12000},
        ],
        6.50
    ),
    # Brown Coffee & Bakery
    (
        re.compile(r"brown\s*coffee|brown\s*cafe|ប្រោន\s*កាហ្វេ", re.I),
        [
            {"name_en": "Brown Signature Iced Palm Cappuccino (Kafe Tnaot)", "name_kh": "កាហ្វេទឹកត្នោតទឹកកកប្រោន", "price_usd": 2.75, "price_khr": 11000},
            {"name_en": "Brown Khmer Latte", "name_kh": "ឡាតេខ្មែរប្រោន", "price_usd": 2.60, "price_khr": 10500},
            {"name_en": "Smoked Salmon & Cream Cheese Bagel", "name_kh": "នំប៉័ងបេហ្គលសាល់ម៉ុងផ្សែង", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Almond Butter Croissant", "name_kh": "នំខ្វាសង់គ្រាប់អាល់ម៉ុន", "price_usd": 2.20, "price_khr": 9000},
            {"name_en": "Uji Matcha Green Tea Frappe", "name_kh": "ម៉ាតឆាក្រឡុកគ្រីម", "price_usd": 3.20, "price_khr": 13000},
        ],
        2.75
    ),
    # Tube Coffee
    (
        re.compile(r"tube\s*coffee|ធូប\s*កាហ្វេ", re.I),
        [
            {"name_en": "Thnol Coffee (Signature Condensed Milk Coffee)", "name_kh": "កាហ្វេថ្នល់ធូប", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Tube Passion Fruit Cream Cheese", "name_kh": "ផាសិនគ្រីមឈីស", "price_usd": 1.80, "price_khr": 7500},
            {"name_en": "Iced Americano Strong", "name_kh": "អាមេរិកាណូទឹកកក", "price_usd": 1.30, "price_khr": 5500},
            {"name_en": "Butter Sugar Condensed Toast", "name_kh": "នំប៉័ងអាំងប៊័រស្ករ", "price_usd": 1.00, "price_khr": 4000},
        ],
        1.50
    ),
    # Park Café
    (
        re.compile(r"park\s*caf[eé]|ផាក\s*កាហ្វេ", re.I),
        [
            {"name_en": "Park Cafe Special Kuy Teav Phnom Penh", "name_kh": "គុយទាវភ្នំពេញពិសេសផាកកាហ្វេ", "price_usd": 3.80, "price_khr": 15500},
            {"name_en": "Braised Beef Shank with Steamed Rice", "name_kh": "បាយសាច់គោផាត់", "price_usd": 4.20, "price_khr": 17000},
            {"name_en": "Roasted Herbal Chicken with Broken Rice", "name_kh": "បាយមាន់ដុតឱសថ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Traditional Khmer Drip Milk Coffee", "name_kh": "កាហ្វេទឹកដោះគោដំណក់ខ្មែរ", "price_usd": 1.80, "price_khr": 7500},
        ],
        3.80
    ),
    # Lucky Burger
    (
        re.compile(r"lucky\s*burger|ឡាក់គី\s*ប៊ឺហ្គឺ", re.I),
        [
            {"name_en": "Lucky Special Double Beef Burger", "name_kh": "ប៊ឺហ្គឺសាច់គោឡាក់គី", "price_usd": 3.20, "price_khr": 13000},
            {"name_en": "Lucky Crispy Fried Chicken Combo Set", "name_kh": "មាន់បំពងឡាក់គីឈុត", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "French Fries & Soft Drink", "name_kh": "ដំឡូងបារាំងបំពងនិងកូកា", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.20
    ),
    # Lotteria
    (
        re.compile(r"lotteria|ឡូតធើរីយ៉ា", re.I),
        [
            {"name_en": "Korean Bulgogi Beef Burger", "name_kh": "ប៊ឺហ្គឺសាច់គោប៊ុលហ្កូហ្គី", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Sweet & Spicy Yangnyeom Fried Chicken", "name_kh": "មាន់បំពងកូរ៉េហឹរផ្អែម", "price_usd": 3.80, "price_khr": 15500},
            {"name_en": "Tornado Shake Seasoned Potato", "name_kh": "ដំឡូងបារាំងក្រឡុកឈីស", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.20
    ),
    # KFC Cambodia
    (
        re.compile(r"\bkfc\b|ខេអេហ្វស៊ី", re.I),
        [
            {"name_en": "Hot & Spicy Fried Chicken (2 pcs Combo)", "name_kh": "មាន់បំពងហឹរខេអេហ្វស៊ី", "price_usd": 3.80, "price_khr": 15500},
            {"name_en": "KFC Spicy Zinger Burger", "name_kh": "ប៊ឺហ្គឺហ្ស៊ីងហ្គឺ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Whipped Potato with Rich Gravy", "name_kh": "ដំឡូងបារាំងកិនទឹកស៊ុប", "price_usd": 1.20, "price_khr": 5000},
            {"name_en": "Colonel Fresh Coleslaw", "name_kh": "សាឡាដកូឡេស្លរ", "price_usd": 1.00, "price_khr": 4000},
        ],
        3.80
    ),
    # Burger King Cambodia
    (
        re.compile(r"burger\s*king|ប៊ឺហ្គឺ\s*ឃីង", re.I),
        [
            {"name_en": "Whopper Flame-Grilled Beef Burger", "name_kh": "ប៊ឺហ្គឺវ៉ុបភើរសាច់គោអាំងភ្លើង", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Double Cheeseburger Meal", "name_kh": "ប៊ឺហ្គឺសាច់គោឈីសពីរជាន់", "price_usd": 3.20, "price_khr": 13000},
            {"name_en": "King French Fries", "name_kh": "ដំឡូងបារាំងឃីងហ្វ្រាយ", "price_usd": 1.60, "price_khr": 6500},
            {"name_en": "Golden Crispy Onion Rings (8 pcs)", "name_kh": "ខ្ទឹមបារាំងបំពងស្រួយ", "price_usd": 1.80, "price_khr": 7500},
        ],
        4.00
    ),
    # Texas Chicken
    (
        re.compile(r"texas\s*chicken|តិចសាស់\s*ឈីកខិន", re.I),
        [
            {"name_en": "Texas Mega Crunch Spicy Chicken (2 pcs)", "name_kh": "មាន់បំពងមេហ្កាស្រួយតិចសាស់", "price_usd": 3.80, "price_khr": 15500},
            {"name_en": "Classic Tender Wrap", "name_kh": "នំរុំសាច់មាន់ស្រួយតិចសាស់", "price_usd": 2.90, "price_khr": 12000},
            {"name_en": "Signature Honey-Butter Biscuits (2 pcs)", "name_kh": "នំប៊ីស្គីតប៊័រទឹកឃ្មុំ", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Seasoned French Fries", "name_kh": "ដំឡូងបារាំងបំពង", "price_usd": 1.40, "price_khr": 5500},
        ],
        3.50
    ),
    # Pong Cambodia
    (
        re.compile(r"pong\s*cambodia|ពង\s*ខេមបូឌា", re.I),
        [
            {"name_en": "Signature Egg Toast Sandwich (Pong Toast)", "name_kh": "នំប៉័ងពងទាពិសេសពងខេមបូឌា", "price_usd": 1.90, "price_khr": 8000},
            {"name_en": "Ham & Double Cheese Pong Toast", "name_kh": "នំប៉័ងពងទាហាំឈីស", "price_usd": 2.20, "price_khr": 9000},
            {"name_en": "Iced Milk Coffee (Pong Coffee)", "name_kh": "កាហ្វេទឹកដោះគោពង", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Fresh Taro Milk with Boba", "name_kh": "ទឹកដោះគោត្រាវគុជ", "price_usd": 1.80, "price_khr": 7500},
        ],
        1.90
    ),
    # BonChon
    (
        re.compile(r"bonchon|ប៊ុនឆុន", re.I),
        [
            {"name_en": "BonChon Soy Garlic Crispy Chicken Wings (6 pcs)", "name_kh": "ស្លាបមាន់បំពងខ្ទឹមសសណ្តែកប៊ុនឆុន", "price_usd": 4.95, "price_khr": 20000},
            {"name_en": "Spicy Korean Glazed Chicken Wings (6 pcs)", "name_kh": "ស្លាបមាន់បំពងហឹរកូរ៉េ", "price_usd": 4.95, "price_khr": 20000},
            {"name_en": "Steamed White Rice with Pickled Radish", "name_kh": "បាយផ្កាម្លិះនិងជ្រក់ឆៃថាវ", "price_usd": 1.20, "price_khr": 5000},
            {"name_en": "Kimchi Seasoned French Fries", "name_kh": "ដំឡូងបារាំងបំពងគីមឈី", "price_usd": 2.00, "price_khr": 8000},
        ],
        4.50
    ),
    # Mexican (Itacate / Family Taco Recipe / Taqueria)
    (
        re.compile(r"itacate|family\s*taco|taqueria|corona\s*mexican|តាកូ|ម៉ិកស៊ិក", re.I),
        [
            {"name_en": "Carne Asada Beef Street Tacos (3 pcs)", "name_kh": "តាកូសាច់គោម៉ិកស៊ិក ៣ដុំ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Stuffed Pork Carnitas Burrito with Guacamole", "name_kh": "ប៊ូរីតូសាច់ជ្រូកខានីតាស", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Cheesy Nachos Supreme with Jalapenos", "name_kh": "ណាឈូសឈីសហៀរម៉ិកស៊ិក", "price_usd": 4.00, "price_khr": 16500},
            {"name_en": "Grilled Chicken Quesadilla with Salsa", "name_kh": "កេសាឌីឡាសាច់មាន់", "price_usd": 4.25, "price_khr": 17500},
            {"name_en": "Horchata Cinnamon Rice Milk", "name_kh": "ទឹកដោះគោហ័របាតា", "price_usd": 1.75, "price_khr": 7000},
        ],
        4.75
    ),
    # Vietnamese Pho (Pho 24 / Pho Phnom Penh)
    (
        re.compile(r"pho\s*24|pho\s*phnom\s*penh|pho\s*bo|ហ្វឺ\s*វៀតណាម", re.I),
        [
            {"name_en": "Pho Bo Special (Sliced Rare Beef & Beef Balls Noodle Soup)", "name_kh": "ហ្វឺសាច់គោពិសេសវៀតណាម", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Pho Ga (Shredded Chicken Noodle Soup)", "name_kh": "ហ្វឺសាច់មាន់", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Fresh Summer Salad Rolls with Shrimps (3 pcs)", "name_kh": "គួងបង្គាស្រស់វៀតណាម", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Vietnamese Iced Drip Coffee (Ca Phe Sua Da)", "name_kh": "កាហ្វេតម្រងទឹកដោះគោវៀតណាម", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.25
    ),
    # Indian (Aroma / Sher-e-Punjab)
    (
        re.compile(r"aroma\s*indian|sher-e-punjab|curry\s*king|indian\s*restaurant", re.I),
        [
            {"name_en": "Butter Chicken Curry in Rich Cashew Gravy", "name_kh": "ការីមាន់ប៊័រឥណ្ឌា", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Aromatic Mutton Biryani with Mint Raita", "name_kh": "បាយប៊ីរយ៉ានីសាច់ចៀម", "price_usd": 6.50, "price_khr": 26500},
            {"name_en": "Garlic Butter Tandoori Naan Bread", "name_kh": "នំប៉័ងណានខ្ទឹមសប៊័រ", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Crispy Spiced Potato Samosas (3 pcs)", "name_kh": "សារម៉ូសាដំឡូងបារាំង", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Mango Lassi Yogurt Drink", "name_kh": "ឡាស៊ីស្វាយឥណ្ឌា", "price_usd": 2.00, "price_khr": 8000},
        ],
        5.00
    ),
    # Halal / Middle Eastern
    (
        re.compile(r"halal|shawarma|kebab|warung\s*bali|lebanese|middle\s*eastern", re.I),
        [
            {"name_en": "Roasted Chicken Shawarma Wrap with Garlic Sauce", "name_kh": "នំរុំសាច់មាន់ស្ហាវ៉ាម៉ា", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Grilled Lamb Kebab Skewers with Fragrant Rice", "name_kh": "សាច់ចៀមកេបាប់អាំងជាមួយបាយ", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Crispy Falafel Platter with Fresh Hummus & Pita", "name_kh": "ហ្វាឡាហ្វែលនិងហ៊ូមូស", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Middle Eastern Fresh Mint Lemonade", "name_kh": "ទឹកក្រូចឆ្មាជីរអង្កាម", "price_usd": 1.75, "price_khr": 7000},
        ],
        4.50
    ),
    # Nesat Seafood House
    (
        re.compile(r"nesat|នេសាទ", re.I),
        [
            {"name_en": "Steamed Kampot Blue Crab with Green Peppercorns", "name_kh": "ក្តាមសេះកំពតចំហុយម្រេចខ្ចី", "price_usd": 8.50, "price_khr": 35000},
            {"name_en": "Grilled Calamari Squid with Spicy Koh Kong Dip", "name_kh": "មឹកបំពង់អាំងទឹកត្រីកោះកុង", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Nesat Seafood Fried Rice with Prawns", "name_kh": "បាយឆាគ្រឿងសមុទ្រនេសាទ", "price_usd": 3.80, "price_khr": 15500},
            {"name_en": "Stir-Fried Clams with Sweet Basil & Chili", "name_kh": "លៀសសមុទ្រឆាជីរនាងវង", "price_usd": 4.00, "price_khr": 16000},
        ],
        6.50
    ),
    # Cadillac Bar & Grill
    (
        re.compile(r"cadillac|កាឌីឡាក់", re.I),
        [
            {"name_en": "Cadillac Hickory Smoked BBQ Pork Ribs", "name_kh": "ឆ្អឹងជំនីជ្រូកអាំងផ្សែងកាឌីឡាក់", "price_usd": 7.50, "price_khr": 30500},
            {"name_en": "Texas Chili Cheeseburger with Fries", "name_kh": "ប៊ឺហ្គឺសាច់គោឈីលីតិចសាស់", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Buffalo Chicken Wings with Blue Cheese Dip", "name_kh": "ស្លាបមាន់បាហ្វាឡូ", "price_usd": 4.50, "price_khr": 18500},
        ],
        6.00
    ),
    # Freebird Bar & Grill
    (
        re.compile(r"freebird|ហ្វ្រីបឺដ", re.I),
        [
            {"name_en": "Freebird Bacon Cheeseburger with Fries", "name_kh": "ប៊ឺហ្គឺសាច់គោបែកខនហ្វ្រីបឺដ", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Sizzling Steak Fajitas with Warm Tortillas", "name_kh": "ហ្វាហ៊ីតាសាច់គោខ្ទះដែក", "price_usd": 6.50, "price_khr": 26500},
            {"name_en": "Tex-Mex Beef Enchiladas with Guacamole", "name_kh": "អង់ឈីឡាដាសាច់គោម៉ិកស៊ិក", "price_usd": 5.50, "price_khr": 22500},
        ],
        5.50
    ),
    # Malis Restaurant
    (
        re.compile(r"malis|ម៉ាលីស", re.I),
        [
            {"name_en": "Royal Mak Mee Crispy Pork & Rice Noodles", "name_kh": "ម៉ាក់មីសាច់ជ្រូកបំពង", "price_usd": 8.00, "price_khr": 32500},
            {"name_en": "Kampot Crab Fried Rice with Fragrant Jasmine Rice", "name_kh": "បាយឆាក្តាមកំពត", "price_usd": 7.50, "price_khr": 30500},
            {"name_en": "Takeo River Prawn in Sweet Coconut Curry", "name_kh": "បង្កងទន្លេតាកែវសម្លការី", "price_usd": 14.00, "price_khr": 57000},
        ],
        9.50
    ),
    # French Cuisine (Topaz / Khema)
    (
        re.compile(r"topaz|khema|french\s*bistro|french\s*restaurant", re.I),
        [
            {"name_en": "Duck Leg Confit with Rosemary Roasted Potatoes", "name_kh": "ភ្លៅទាចៀនខនហ្វីតបែបបារាំង", "price_usd": 9.50, "price_khr": 39000},
            {"name_en": "Slow-Braised Beef Bourguignon in Red Wine", "name_kh": "សាច់គោខស្រាក្រហមបួរហ្គីញ៉ុង", "price_usd": 9.00, "price_khr": 37000},
            {"name_en": "Traditional French Onion Soup with Gruyere", "name_kh": "ស៊ុបខ្ទឹមបារាំងបែបបារាំង", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Classic Croque Monsieur Toast with Emmental", "name_kh": "នំប៉័ងក្រូកម៉ុងសៀរបារាំង", "price_usd": 4.50, "price_khr": 18500},
        ],
        8.50
    ),
]

MENU_CATALOG = [
    # Mexican & Tex-Mex
    (
        re.compile(r"mexican|taco|burrito|nacho|quesadilla|fajita|ម៉ិកស៊ិក|តាកូ", re.I),
        [
            {"name_en": "Carne Asada Beef Street Tacos (3 pcs)", "name_kh": "តាកូសាច់គោម៉ិកស៊ិក ៣ដុំ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Stuffed Pork Carnitas Burrito with Guacamole", "name_kh": "ប៊ូរីតូសាច់ជ្រូកខានីតាស", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Cheesy Nachos Supreme with Jalapenos", "name_kh": "ណាឈូសឈីសហៀរម៉ិកស៊ិក", "price_usd": 4.00, "price_khr": 16500},
            {"name_en": "Grilled Chicken Quesadilla with Salsa", "name_kh": "កេសាឌីឡាសាច់មាន់", "price_usd": 4.25, "price_khr": 17500},
            {"name_en": "Horchata Cinnamon Rice Milk", "name_kh": "ទឹកដោះគោហ័របាតា", "price_usd": 1.75, "price_khr": 7000},
        ],
        4.50
    ),
    # Vietnamese Cuisine
    (
        re.compile(r"vietnamese|pho\b|banh\s*mi|bun\s*cha|spring\s*roll|វៀតណាម|ហ្វឺ", re.I),
        [
            {"name_en": "Traditional Pho Bo Beef Noodle Soup", "name_kh": "ហ្វឺសាច់គោពិសេសវៀតណាម", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Vietnamese Banh Mi Crispy Baguette with Pork & Pate", "name_kh": "នំប៉័ងបាញ់មីសាច់ជ្រូកប៉ាតេ", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Bun Cha Hanoi (Grilled Pork with Vermicelli)", "name_kh": "ប៊ុនឆាហាណូយសាច់ជ្រូកអាំង", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Fresh Summer Rolls with Shrimp & Peanut Dip (3 pcs)", "name_kh": "គួងបង្គាស្រស់វៀតណាម ៣ដុំ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Vietnamese Iced Drip Coffee", "name_kh": "កាហ្វេទឹកដោះគោវៀតណាម", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.25
    ),
    # Thai Cuisine
    (
        re.compile(r"thai|tom\s*yum|pad\s*thai|som\s*tum|green\s*curry|ម្ហូបថៃ|តុមយ៉ាំ|ផាត់ថៃ", re.I),
        [
            {"name_en": "Tom Yum Goong Spicy & Sour Prawn Soup", "name_kh": "ស៊ុបតុមយ៉ាំបង្គាហឹរជូរ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Classic Stir-Fried Pad Thai with Shrimps", "name_kh": "មីផាត់ថៃបង្គា", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Green Curry Chicken with Thai Eggplant", "name_kh": "ការីបៃតងសាច់មាន់", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Spicy Som Tum Papaya Salad", "name_kh": "បុកល្ហុងបែបថៃស៊ុមតាំ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Mango Sticky Rice with Coconut Cream", "name_kh": "បាយដំណើបស្វាយទុំ", "price_usd": 3.00, "price_khr": 12000},
        ],
        3.75
    ),
    # French Cuisine
    (
        re.compile(r"french|bistro|croque|confit|bourguignon|ម្ហូបបារាំង", re.I),
        [
            {"name_en": "Classic Croque Monsieur with Emmental Cheese", "name_kh": "នំប៉័ងក្រូកម៉ុងសៀរបារាំង", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Slow-Braised Beef Bourguignon in Red Wine", "name_kh": "សាច់គោខស្រាក្រហមបួរហ្គីញ៉ុង", "price_usd": 8.50, "price_khr": 35000},
            {"name_en": "Traditional French Onion Soup with Gruyere", "name_kh": "ស៊ុបខ្ទឹមបារាំងបែបបារាំង", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Duck Leg Confit with Rosemary Potatoes", "name_kh": "ភ្លៅទាចៀនខនហ្វីតបែបបារាំង", "price_usd": 9.00, "price_khr": 37000},
            {"name_en": "Fresh Butter Croissant", "name_kh": "នំខ្វាសង់ប៊័រស្រួយ", "price_usd": 1.50, "price_khr": 6000},
        ],
        6.50
    ),
    # Halal & Middle Eastern Cuisine
    (
        re.compile(r"halal|middle\s*eastern|shawarma|kebab|falafel|hummus|mandi|ហាឡាល់|ស្ហាវ៉ាម៉ា", re.I),
        [
            {"name_en": "Roasted Chicken Shawarma Wrap with Garlic Sauce", "name_kh": "នំរុំសាច់មាន់ស្ហាវ៉ាម៉ា", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Grilled Lamb Kebab Skewers with Fragrant Rice", "name_kh": "សាច់ចៀមកេបាប់អាំងជាមួយបាយ", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Crispy Falafel Platter with Fresh Hummus & Pita", "name_kh": "ហ្វាឡាហ្វែលនិងហ៊ូមូស", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Aromatic Lamb Mandi Rice Platter", "name_kh": "បាយម៉ាន់ឌីសាច់ចៀម", "price_usd": 6.50, "price_khr": 26500},
            {"name_en": "Middle Eastern Fresh Mint Lemonade", "name_kh": "ទឹកក្រូចឆ្មាជីរអង្កាម", "price_usd": 1.75, "price_khr": 7000},
        ],
        4.50
    ),
    # Steakhouse & Grills
    (
        re.compile(r"steak|steakhouse|ribeye|tenderloin|striploin|ស្ទេក|សាច់គោអូស្ត្រាលី", re.I),
        [
            {"name_en": "Australian Ribeye Steak with Kampot Black Pepper Sauce", "name_kh": "ស្ទេកសាច់គោអូស្ត្រាលីរីបអាយម្រេចកំពត", "price_usd": 9.50, "price_khr": 39000},
            {"name_en": "Grilled Sizzling Striploin Steak with French Fries", "name_kh": "ស្ទេកសាច់គោស្ត្រីបឡយខ្ទះដែក", "price_usd": 8.00, "price_khr": 32500},
            {"name_en": "Creamy Garlic Mashed Potatoes", "name_kh": "ដំឡូងបារាំងកិនខ្ទឹមស", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Classic Caesar Salad with Grilled Chicken", "name_kh": "សាឡាដស៊ីហ្សាមាន់អាំង", "price_usd": 4.00, "price_khr": 16000},
        ],
        8.00
    ),
    # Healthy Bowls, Poke & Salads
    (
        re.compile(r"healthy|poke|salad|quinoa|diet|សាឡាដ|ភូគី", re.I),
        [
            {"name_en": "Fresh Salmon & Avocado Poke Bowl", "name_kh": "បាយភូគីសាល់ម៉ុងផ្លែបឺរ", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Mediterranean Quinoa Salad with Feta & Olive Oil", "name_kh": "សាឡាដគីន័រមេឌីទែរ៉ាណេ", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Teriyaki Tofu & Edamame Brown Rice Bowl", "name_kh": "បាយសម្រូបតៅហ៊ូតេរីយ៉ាគី", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Cold-Pressed Green Detox Juice", "name_kh": "ទឹកបន្លែផ្លែឈើស្រស់ឌីថក", "price_usd": 2.50, "price_khr": 10000},
        ],
        4.00
    ),
    # Kuy Teav & Soups
    (
        re.compile(r"kuy\s*teav|kuyteav|គុយទាវ|soup\s*mee", re.I),
        [
            {"name_en": "Kuy Teav Phnom Penh (Pork & Prawn)", "name_kh": "គុយទាវភ្នំពេញ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Beef Ball Noodle Soup", "name_kh": "គុយទាវប្រហិតសាច់គោ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Seafood Rice Noodle Soup", "name_kh": "គុយទាវគ្រឿងសមុទ្រ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Dry Kuy Teav with Savory Broth", "name_kh": "គុយទាវគោក", "price_usd": 2.75, "price_khr": 11000},
            {"name_en": "Crispy Spring Rolls (4 pcs)", "name_kh": "ណែមចៀនស្រួយ", "price_usd": 1.50, "price_khr": 6000},
        ],
        2.50
    ),
    # Num Banhchok
    (
        re.compile(r"num\s*banhchok|nom\s*banhchok|នំបញ្ចុក|nom\s*bonjok|somlor\s*khmer", re.I),
        [
            {"name_en": "Nom Banh Chok Somlor Proher (Green Fish Curry)", "name_kh": "នំបញ្ចុកសម្លប្រហើរ", "price_usd": 1.75, "price_khr": 7000},
            {"name_en": "Nom Banh Chok Somlor Kari (Red Chicken Curry)", "name_kh": "នំបញ្ចុកសម្លការី", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Nom Banh Chok Namya (Spicy Fish Curry)", "name_kh": "នំបញ្ចុកណាំយ៉ា", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Deep Fried Fish Cakes", "name_kh": "ប្រហិតត្រីចៀន", "price_usd": 1.50, "price_khr": 6000},
        ],
        2.00
    ),
    # Lort Cha & Mi Cha
    (
        re.compile(r"lort\s*cha|lot\s*cha|mi\s*cha|លតឆា|មីឆា", re.I),
        [
            {"name_en": "Stir-Fried Silver Needle Noodles (Lort Cha Beef & Egg)", "name_kh": "លតឆាសាច់គោពងទា", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Stir-Fried Yellow Egg Noodles (Mi Cha)", "name_kh": "មីឆាសាច់គោ", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Fried Chive Cakes (Num Kachay, 3 pcs)", "name_kh": "នំកាឆាយ", "price_usd": 1.00, "price_khr": 4000},
            {"name_en": "Sunny Side Up Egg (Add-on)", "name_kh": "ពងទាចៀនបន្ថែម", "price_usd": 0.50, "price_khr": 2000},
        ],
        2.00
    ),
    # Bok Lhong (Papaya Salad)
    (
        re.compile(r"bok\s*l['\s]?hong|បុកល្ហុង", re.I),
        [
            {"name_en": "Spicy Green Papaya Salad with Salted Crab (Bok Lhong)", "name_kh": "បុកល្ហុងក្តាមប្រៃ", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Seafood Papaya Salad (Shrimp & Squid)", "name_kh": "បុកល្ហុងគ្រឿងសមុទ្រ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Grilled Chicken Wings (3 pcs)", "name_kh": "ស្លាបមាន់អាំង", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Steamed Sticky Rice in Banana Leaf", "name_kh": "បាយដំណើប", "price_usd": 0.75, "price_khr": 3000},
        ],
        2.50
    ),
    # Banh Chhev
    (
        re.compile(r"banh\s*chhe?a?v|banh\s*chao|បាញ់ឆែវ", re.I),
        [
            {"name_en": "Crispy Stuffed Rice Crepe (Banh Chhev with Pork & Shrimp)", "name_kh": "បាញ់ឆែវស្រួយ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Fresh Herb & Green Lettuce Basket", "name_kh": "បន្លែស្រស់និងជីរ", "price_usd": 1.00, "price_khr": 4000},
            {"name_en": "Sweet Fish Sauce with Crushed Peanuts", "name_kh": "ទឹកត្រីផ្អែមសណ្តែកដី", "price_usd": 0.50, "price_khr": 2000},
        ],
        2.50
    ),
    # Num Pang (Cambodian Baguette)
    (
        re.compile(r"num\s*pang|nom\s*pang|baguette|sandwich|នំប៉័ង", re.I),
        [
            {"name_en": "Num Pang Pate & Ham (Traditional Baguette)", "name_kh": "នំប៉័ងប៉ាតេសាច់ជ្រូក", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Num Pang Roast Pork (Sach Chrouk Kvai)", "name_kh": "នំប៉័ងសាច់ជ្រូកខ្វៃ", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Num Pang Grilled Beef Skewers", "name_kh": "នំប៉័ងសាច់គោអាំង", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Cambodian Iced Milk Coffee", "name_kh": "កាហ្វេទឹកដោះគោ", "price_usd": 1.25, "price_khr": 5000},
        ],
        1.75
    ),
    # Bai Sach Chrouk & Chicken Rice
    (
        re.compile(r"bai\s*sach|bay\s*sach|បាយសាច់ជ្រូក|bai\s*moan|bay\s*moan|chicken\s*rice|បាយមាន់", re.I),
        [
            {"name_en": "Bai Sach Chrouk (Marinated Grilled Pork with Broken Rice)", "name_kh": "បាយសាច់ជ្រូកអាំង", "price_usd": 1.75, "price_khr": 7000},
            {"name_en": "Bai Sach Moan (Hainanese Steamed Chicken Rice)", "name_kh": "បាយមាន់ហៃណាំ", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Grilled Pork Chop Rice with Fried Egg", "name_kh": "បាយសាច់ជ្រូកពងទាចៀន", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Clear Winter Melon Broth & Pickled Daikon", "name_kh": "ស៊ុបត្រឡាចនិងជ្រក់ឆៃថាវ", "price_usd": 0.50, "price_khr": 2000},
        ],
        2.00
    ),
    # Beef Lok Lak
    (
        re.compile(r"lok\s*lak|ឡុកឡាក់", re.I),
        [
            {"name_en": "Shaking Beef Lok Lak with Fried Egg & Steamed Rice", "name_kh": "ឡុកឡាក់សាច់គោពងទាចៀន", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Australian Beef Tenderloin Lok Lak", "name_kh": "ឡុកឡាក់សាច់គោអូស្ត្រាលី", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Chicken Lok Lak with Kampot Pepper Lime Dip", "name_kh": "ឡុកឡាក់សាច់មាន់", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Crispy French Fries (Add-on)", "name_kh": "ដំឡូងបារាំងបំពង", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.50
    ),
    # Amok & Traditional Khmer Curries
    (
        re.compile(r"amok|អាម៉ុក|curry|ការី", re.I),
        [
            {"name_en": "Traditional Steamed Fish Amok in Banana Leaf", "name_kh": "អាម៉ុកត្រីស្លឹកចេក", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Chicken Amok in Rich Coconut Cream", "name_kh": "អាម៉ុកមាន់ខ្ទិះដូង", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Khmer Red Chicken Curry with Fresh Baguette", "name_kh": "ការីក្រហមខ្មែរ", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Fragrant Jasmine Steamed Rice", "name_kh": "បាយផ្កាម្លិះ", "price_usd": 0.75, "price_khr": 3000},
        ],
        3.75
    ),
    # BBQ & Grill (Sach Ko Ang)
    (
        re.compile(r"bbq|barbecue|grill|សាច់អាំង|sach\s*ko\s*jakak", re.I),
        [
            {"name_en": "Grilled Beef Skewers with Lemongrass (Sach Ko Ang, 5 pcs)", "name_kh": "សាច់គោចាក់កាក់អាំង ៥ចង្កាក់", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "BBQ Pork Ribs with Honey Garlic Glaze", "name_kh": "ឆ្អឹងជំនីជ្រូកអាំងទឹកឃ្មុំ", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Grilled Pork Belly (Sach Chrouk Ang)", "name_kh": "សាច់ជ្រូកបីជាន់អាំង", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Grilled Chicken Wings with Kampot Pepper (4 pcs)", "name_kh": "ស្លាបមាន់អាំងម្រេចកំពត", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Pickled Papaya & Toasted Baguette", "name_kh": "ជ្រក់ល្ហុងនិងនំប៉័ង", "price_usd": 1.00, "price_khr": 4000},
        ],
        4.00
    ),
    # Hot Pot & Soup
    (
        re.compile(r"hot\s*pot|suki|soup|ស៊ុប|shabu", re.I),
        [
            {"name_en": "Claypot Suki Soup with Sliced Beef & Seafood", "name_kh": "ស៊ុបឆ្នាំងដីសាច់គោគ្រឿងសមុទ្រ", "price_usd": 6.00, "price_khr": 24500},
            {"name_en": "Australian Beef Shabu Shabu Set", "name_kh": "ស៊ុបសាច់គោស្លាយអូស្ត្រាលី", "price_usd": 7.50, "price_khr": 30000},
            {"name_en": "Assorted Fishball & Meatball Platter", "name_kh": "ប្រហិតចម្រុះ", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Fresh Mixed Greens & Glass Noodle Basket", "name_kh": "បន្លែស្រស់និងមីសួរ", "price_usd": 2.00, "price_khr": 8000},
        ],
        6.00
    ),
    # Seafood
    (
        re.compile(r"seafood|crab|shrimp|fish|prawn|squid|lobster|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី|មឹក", re.I),
        [
            {"name_en": "Stir-Fried Sea Crab with Fresh Kampot Green Peppercorns", "name_kh": "ក្តាមថ្មឆាម្រេចខ្ចីកំពត", "price_usd": 8.50, "price_khr": 35000},
            {"name_en": "Grilled Giant River Prawns with Chili Salt Dip", "name_kh": "បង្គាទន្លេអាំងអំបិលម្ទេស", "price_usd": 7.50, "price_khr": 30000},
            {"name_en": "Steamed Sea Bass with Ginger & Soy Sauce", "name_kh": "ត្រីតុកកែចំហុយខ្ញី", "price_usd": 6.50, "price_khr": 26500},
            {"name_en": "Grilled Calamari Squid with Koh Kong Spicy Sauce", "name_kh": "មឹកបំពង់អាំងទឹកត្រីកោះកុង", "price_usd": 4.50, "price_khr": 18500},
        ],
        6.75
    ),
    # Coffee & Cafes
    (
        re.compile(r"coffee|cafe|café|espresso|cappuccino|latte|កាហ្វេ|kfae|starbucks", re.I),
        [
            {"name_en": "Cambodian Iced Milk Coffee (Kafe Toek Doh Ko)", "name_kh": "កាហ្វេទឹកដោះគោទឹកកក", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Iced Vanilla Latte", "name_kh": "វ៉ានីឡាឡាតេទឹកកក", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Cold Brew Artisan Coffee", "name_kh": "កាហ្វេត្រជាក់", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Passion Fruit Iced Green Tea", "name_kh": "តែបៃតងផាសិន", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Fresh French Butter Croissant", "name_kh": "នំខ្វាសង់ប៊័រ", "price_usd": 1.75, "price_khr": 7000},
        ],
        2.00
    ),
    # Bubble Tea & Drinks
    (
        re.compile(r"bubble\s*tea|boba|milk\s*tea|matcha|តែគុជ|តែទឹកដោះគោ|chagee|koi|mixue", re.I),
        [
            {"name_en": "Brown Sugar Boba Milk Tea with Tapioca Pearls", "name_kh": "តែគុជស្ករក្រហម", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Jasmine Green Tea with Cheese Foam", "name_kh": "តែបៃតងហ្វូមឈីស", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Uji Japanese Matcha Latte", "name_kh": "ម៉ាតឆាឡាតេ", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Mango Fruit Tea with Coconut Jelly", "name_kh": "តែស្វាយចាហួយដូង", "price_usd": 2.25, "price_khr": 9000},
        ],
        2.25
    ),
    # Smoothies & Juices
    (
        re.compile(r"yogurt|smoothie|shake|juice|fruit|ទឹកក្រឡុក|ទឹកផ្លែឈើ|យ៉ាអួ", re.I),
        [
            {"name_en": "Fresh Avocado Smoothie with Condensed Milk", "name_kh": "ទឹកផ្លែបឺរក្រឡុក", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Passion Fruit & Mango Slushie", "name_kh": "ទឹកក្រូចឆ្មាផាសិននិងស្វាយក្រឡុក", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Greek Yogurt Bowl with Honey & Berries", "name_kh": "យ៉ាអួផ្លែឈើស្រស់", "price_usd": 3.00, "price_khr": 12000},
            {"name_en": "Cold-Pressed Green Detox Juice", "name_kh": "ទឹកបន្លែផ្លែឈើស្រស់", "price_usd": 2.50, "price_khr": 10000},
        ],
        2.25
    ),
    # Pizza & Pasta
    (
        re.compile(r"pizza|pasta|spaghetti|ភីហ្សា|italian", re.I),
        [
            {"name_en": "Classic Margherita Pizza (Mozzarella, Basil, Tomato)", "name_kh": "ភីហ្សាម៉ាហ្គើរីតា", "price_usd": 5.50, "price_khr": 22500},
            {"name_en": "Pepperoni Feast Pizza with Extra Cheese", "name_kh": "ភីហ្សាភិបភើរ៉ូនី", "price_usd": 6.50, "price_khr": 26500},
            {"name_en": "Creamy Pasta Carbonara with Smoked Bacon", "name_kh": "ប៉ាស្តាកាបូណារ៉ា", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Spaghetti Bolognese with Minced Beef", "name_kh": "ស្ប៉ាហ្គេតទីសាច់គោ", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Garlic Bread with Melted Cheese", "name_kh": "នំប៉័ងខ្ទឹមសឈីស", "price_usd": 2.25, "price_khr": 9000},
        ],
        5.00
    ),
    # Burgers & Fast Food
    (
        re.compile(r"burger|ប៊ឺហ្គឺ|fried\s*chicken|មាន់បំពង|fast\s*food", re.I),
        [
            {"name_en": "Classic Beef Cheeseburger with Secret Sauce", "name_kh": "ប៊ឺហ្គឺសាច់គោឈីស", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Crispy Fried Chicken Burger with Spicy Mayo", "name_kh": "ប៊ឺហ្គឺមាន់បំពងស្រួយ", "price_usd": 3.25, "price_khr": 13000},
            {"name_en": "Crispy Fried Chicken (3 pcs Original / Spicy)", "name_kh": "មាន់បំពងស្រួយ ៣ដុំ", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Golden French Fries with Cheese Dip", "name_kh": "ដំឡូងបារាំងបំពង", "price_usd": 1.75, "price_khr": 7000},
            {"name_en": "Crispy Onion Rings", "name_kh": "ខ្ទឹមបារាំងបំពងស្រួយ", "price_usd": 1.50, "price_khr": 6000},
        ],
        3.50
    ),
    # Japanese & Sushi
    (
        re.compile(r"sushi|japanese|sashimi|ramen|ម្ហូបជប៉ុន|ស៊ូស៊ី", re.I),
        [
            {"name_en": "Fresh Norwegian Salmon Sashimi (5 pcs)", "name_kh": "សាស៊ីមីសាល់ម៉ុង ៥ដុំ", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Spicy Salmon & Avocado California Roll", "name_kh": "ស៊ូស៊ីសាល់ម៉ុងផ្លែបឺរ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Chicken Teriyaki Bento Box Set", "name_kh": "បាយប្រអប់តេរីយ៉ាគី", "price_usd": 4.00, "price_khr": 16000},
            {"name_en": "Pork Tonkotsu Ramen Noodle Soup", "name_kh": "រ៉ាមេនសាច់ជ្រូកតុងខុតស៊ុ", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Crispy Japanese Pork Gyoza (5 pcs)", "name_kh": "គាវជប៉ុនចៀន", "price_usd": 2.50, "price_khr": 10000},
        ],
        4.50
    ),
    # Korean Food
    (
        re.compile(r"korean|kimchi|k-bbq|ម្ហូបកូរ៉េ|samgyeopsal", re.I),
        [
            {"name_en": "Korean Grilled Pork Belly (Samgyeopsal BBQ Set)", "name_kh": "សាច់ជ្រូកបីជាន់អាំងកូរ៉េ", "price_usd": 6.00, "price_khr": 24500},
            {"name_en": "Stone-Bowl Bibimbap with Beef & Sunny Egg", "name_kh": "បាយឆាឆ្នាំងថ្មប៊ីប៊ីមបាប់", "price_usd": 4.50, "price_khr": 18500},
            {"name_en": "Spicy Cheesy Tteokbokki Rice Cakes", "name_kh": "តុកបុកគីឈីស", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Kimchi Jjigae Stew with Pork & Soft Tofu", "name_kh": "ស៊ុបគីមឈីតៅហ៊ូ", "price_usd": 4.00, "price_khr": 16000},
        ],
        4.75
    ),
    # Chinese & Dim Sum
    (
        re.compile(r"chinese|dim\s*sum|ម្ហូបចិន|dumpling", re.I),
        [
            {"name_en": "Steamed Pork & Prawn Dumplings (Siu Mai, 4 pcs)", "name_kh": "ឌីមសាំគាវសាច់ជ្រូកបង្គា", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Honey Glazed BBQ Pork Buns (Char Siu Bao, 2 pcs)", "name_kh": "នំប៉ាវសាច់ជ្រូកក្រហម", "price_usd": 2.25, "price_khr": 9000},
            {"name_en": "Cantonese Roast Duck Rice", "name_kh": "បាយទាខ្វៃ", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Stir-Fried Beef Rice Noodles (Chow Fun)", "name_kh": "មីគុយទាវឆាសាច់គោ", "price_usd": 3.25, "price_khr": 13000},
        ],
        3.50
    ),
    # Indian Cuisine
    (
        re.compile(r"indian|curry|ម្ហូបឥណ្ឌា|biryani", re.I),
        [
            {"name_en": "Butter Chicken Curry in Rich Cream Sauce", "name_kh": "ការីមាន់ប៊័រ", "price_usd": 5.00, "price_khr": 20500},
            {"name_en": "Aromatic Lamb Biryani with Mint Raita", "name_kh": "បាយប៊ីរយ៉ានីសាច់ចៀម", "price_usd": 6.00, "price_khr": 24500},
            {"name_en": "Garlic Butter Tandoori Naan", "name_kh": "នំប៉័ងណានខ្ទឹមស", "price_usd": 1.75, "price_khr": 7000},
            {"name_en": "Crispy Vegetable Samosas with Chutney (3 pcs)", "name_kh": "សារម៉ូសាបន្លែ", "price_usd": 2.25, "price_khr": 9000},
        ],
        4.50
    ),
    # Vegetarian & Vegan
    (
        re.compile(r"vegetarian|vegan|ម្ហូបបួស", re.I),
        [
            {"name_en": "Fresh Tofu Spring Rolls with Roasted Peanut Dip", "name_kh": "គួងបួសទឹកជ្រលក់សណ្តែកដី", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Vegetarian Mushroom & Tofu Amok", "name_kh": "អាម៉ុកតៅហ៊ូបួស", "price_usd": 3.50, "price_khr": 14000},
            {"name_en": "Wok-Tossed Morning Glory with Garlic", "name_kh": "ឆាត្រកួនខ្ទឹមស", "price_usd": 2.00, "price_khr": 8000},
            {"name_en": "Organic Brown Rice", "name_kh": "បាយសម្រូប", "price_usd": 1.00, "price_khr": 4000},
        ],
        2.75
    ),
    # Bakery & Desserts
    (
        re.compile(r"bakery|cake|pastry|dessert|នំប៉័ង|នំ|នំខេក", re.I),
        [
            {"name_en": "French Butter Croissant", "name_kh": "នំខ្វាសង់ប៊័រ", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Rich Dark Chocolate Mousse Cake Slice", "name_kh": "នំខេកសូកូឡា", "price_usd": 2.50, "price_khr": 10000},
            {"name_en": "Crispy Portuguese Egg Tarts (2 pcs)", "name_kh": "នំពងទាក្តៅៗ", "price_usd": 1.50, "price_khr": 6000},
            {"name_en": "Artisan Fruit Danish Pastry", "name_kh": "នំដេនីសផ្លែឈើ", "price_usd": 2.00, "price_khr": 8000},
        ],
        2.00
    ),
    # Ice Cream & Bingsu
    (
        re.compile(r"ice\s*cream|gelato|bingsoo|bingsu|ការ៉េម", re.I),
        [
            {"name_en": "Fresh Mango Snow Ice Bingsu with Condensed Milk", "name_kh": "ប៊ីងស៊ូផ្លែស្វាយ", "price_usd": 3.75, "price_khr": 15000},
            {"name_en": "Double Scoop Artisan Gelato (Choice of Flavors)", "name_kh": "ការ៉េមជេឡាតូ ២ដុំ", "price_usd": 2.75, "price_khr": 11000},
            {"name_en": "Belgian Waffle Sundae with Chocolate Drizzle", "name_kh": "នំវ៉ាហ្វលការ៉េម", "price_usd": 3.25, "price_khr": 13000},
        ],
        3.25
    ),
]

# Default Khmer Made-to-Order Dishes for general places
DEFAULT_KHMER_MENU = (
    [
        {"name_en": "Shaking Beef Lok Lak with Fried Egg & Rice", "name_kh": "ឡុកឡាក់សាច់គោពងទាចៀន", "price_usd": 3.50, "price_khr": 14000},
        {"name_en": "Bai Sach Chrouk (Grilled Marinated Pork with Rice)", "name_kh": "បាយសាច់ជ្រូកអាំង", "price_usd": 1.75, "price_khr": 7000},
        {"name_en": "Seafood Fried Rice with Lime & Chili (Bai Cha)", "name_kh": "បាយឆាគ្រឿងសមុទ្រ", "price_usd": 2.75, "price_khr": 11000},
        {"name_en": "Stir-Fried Morning Glory with Garlic (Cha Trakuon)", "name_kh": "ឆាត្រកួនខ្ទឹមស", "price_usd": 2.00, "price_khr": 8000},
        {"name_en": "Crispy Spring Rolls (4 pcs)", "name_kh": "ណែមចៀនស្រួយ", "price_usd": 1.50, "price_khr": 6000},
    ],
    2.75
)

def match_menu(name: str, dish_en: str, dish_kh: str, tags: str) -> tuple[list, float]:
    # 1. Match specific restaurant brand/name FIRST
    for pat, dishes, avg_price in SPECIFIC_RESTAURANT_MENUS:
        if pat.search(name):
            return dishes, avg_price

    # 2. Match general cuisine categories
    combined_text = f"{name} {dish_en} {dish_kh} {tags}"
    for pat, dishes, avg_price in MENU_CATALOG:
        if pat.search(combined_text):
            return dishes, avg_price
    return DEFAULT_KHMER_MENU

def main():
    # Every menu, dish price and "Price: about $X" below was typed into this script, not taken from a place or its
    # page, so the chatbot would repeat them as facts (the same five dishes for every pizza place). Disabled: use a
    # real menu source per place instead (e.g. its Foodpanda page).
    raise SystemExit("enrich_all_menus.py is disabled: its menus and prices are invented, not scraped.")
    csv_path = Path("data/restaurants.csv")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} places from {csv_path}")

    menus = []
    prices = []
    updated_descriptions = []

    for idx, row in df.iterrows():
        name = str(row.get("name", ""))
        dish_en = str(row.get("dish_en", ""))
        dish_kh = str(row.get("dish_kh", ""))
        tags = str(row.get("tags", ""))
        desc = str(row.get("description", ""))
        existing_price = row.get("price_usd")

        dish_list, cat_price = match_menu(name, dish_en, dish_kh, tags)
        menus.append(json.dumps(dish_list, ensure_ascii=False))

        # Use existing valid price if present, otherwise set the category price
        final_price = float(existing_price) if (pd.notna(existing_price) and float(existing_price) > 0) else cat_price
        prices.append(final_price)

        # Build clean menu summary for conversational notes
        menu_en_str = ", ".join([f"{d['name_en']} (${d['price_usd']:.2f})" for d in dish_list])
        menu_kh_str = ", ".join([f"{d['name_kh']} (${d['price_usd']:.2f})" for d in dish_list])

        # Remove previous template menu sentence or vague popular items text
        desc = re.sub(r"(?:Menu / មុខម្ហូប៖|Menu:|Popular menu items:[^.]*\.|មុខម្ហូបពិសេសៗ៖[^។]*។).*?(?=\s*(?:How to order|Open:|$))", "", desc, flags=re.I).strip()
        
        # Format price string
        khr_str = f"{int(round(final_price * 4100, -2)):,}"
        price_snippet = f"Price: about ${final_price:.2f} ({khr_str} Riel). តម្លៃប្រហែល ${final_price:.2f} (ឬ {khr_str} រៀល)។"
        if "Price:" not in desc and "តម្លៃ" not in desc:
            desc = f"{price_snippet} {desc}"

        menu_snippet = f"Menu: {menu_en_str}. មុខម្ហូបទាំងអស់៖ {menu_kh_str}។"
        new_desc = f"{desc} {menu_snippet}".strip()
        new_desc = re.sub(r"\s+", " ", new_desc)
        updated_descriptions.append(new_desc)

    df["menu"] = menus
    df["price_usd"] = prices
    df["description"] = updated_descriptions

    # Save to data/restaurants.csv and data/scraped/restaurants_combined.csv
    df.to_csv(csv_path, index=False)
    print(f"✅ Successfully enriched {len(df)} places in {csv_path} with menus & prices!")

    comb_path = Path("data/scraped/restaurants_combined.csv")
    if comb_path.parent.exists():
        df.to_csv(comb_path, index=False)
        print(f"✅ Also updated {comb_path}")

if __name__ == "__main__":
    main()
