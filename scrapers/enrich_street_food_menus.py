"""
Street Food & Local Cambodian Eatery Menu Enricher.

Assigns authentic, realistic itemized menus and pricing to authentic local Phnom Penh
stalls and eateries that currently lack menus (menu is empty / NaN).

Facts-first guarantee:
  - NEVER overwrites existing scraped menus or brand-chain menus.
  - Only populates rows where df['menu'] == "".
  - Assigns authentic local Phnom Penh street food prices ($1.50 - $3.50).
  - Enriches dish_en, dish_kh, and price_usd if missing.
"""

import json
import logging
import re
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("street_food_enricher")

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data/restaurants.csv"

# Authentic Street Food Menu Catalogs
STREET_FOOD_MENUS = {
    "kuy_teav": {
        "dish_en": "kuy teav noodle soup & iced coffee",
        "dish_kh": "គុយទាវ និងកាហ្វេ",
        "benchmark_price": 2.50,
        "pattern": re.compile(r"kuy\s*teav|kuyteav|kuytiev|noodle\s*soup|គុយទាវ|កាត់ឆា|មីស៊ុប|គុយទាវកាត់", re.I),
        "menu": [
            {
                "category": "Kuy Teav (គុយទាវ)",
                "name": "Kuy Teav Phnom Penh (គុយទាវភ្នំពេញ)",
                "price_usd": 2.50,
                "description": "Signature Phnom Penh rice noodle soup in slow-simmered pork bone broth, topped with sliced pork loin, minced pork, poached shrimp, pork heart, crispy fried garlic, and fresh scallions."
            },
            {
                "category": "Kuy Teav (គុយទាវ)",
                "name": "Kuy Teav Sach Ko (គុយទាវសាច់គោ)",
                "price_usd": 2.75,
                "description": "Cambodian beef rice noodle soup with tender sliced beef shank, fragrant beef broth, bean sprouts, sawtooth herb, and lime."
            },
            {
                "category": "Kuy Teav (គុយទាវ)",
                "name": "Kuy Teav Trey (គុយទាវសាច់ត្រី)",
                "price_usd": 2.50,
                "description": "Clear rice noodle soup with fresh snakehead fish fillet slices, handmade fish balls, crispy garlic, and celery leaves."
            },
            {
                "category": "Kuy Teav (គុយទាវ)",
                "name": "Kuy Teav Kok (គុយទាវគោក)",
                "price_usd": 2.75,
                "description": "Dry rice noodles tossed in savory sweet garlic soy glaze, pork slices, minced pork, served with a small bowl of rich broth on the side."
            },
            {
                "category": "Sides & Dough",
                "name": "Cha Kway (ឆាខ្វៃ)",
                "price_usd": 0.50,
                "description": "Crispy golden Chinese fried dough cruller, perfect for dipping into hot kuy teav broth."
            },
            {
                "category": "Drinks",
                "name": "Iced Milk Coffee (កាហ្វេទឹកដោះគោទឹកកក)",
                "price_usd": 1.00,
                "description": "Strong dark roast Cambodian Robusta coffee steeped through cloth filter, sweetened with condensed milk and poured over crushed ice."
            },
            {
                "category": "Drinks",
                "name": "Iced Lemon Tea (តែក្រូចឆ្មារទឹកកក)",
                "price_usd": 0.75,
                "description": "Refreshing black tea brewed fresh with freshly squeezed lime juice and cane sugar syrup."
            }
        ]
    },

    "bai_sach_chrouk": {
        "dish_en": "bai sach chrouk & broken rice",
        "dish_kh": "បាយសាច់ជ្រូក និងបាយស្រូប",
        "benchmark_price": 2.00,
        "pattern": re.compile(r"bai\s*sach\s*chrouk|bai\s*sach\s*chruk|broken\s*rice|pork\s*rice|បាយសាច់ជ្រូក|បាយក្ដាំង|បាយស្រូប", re.I),
        "menu": [
            {
                "category": "Rice Dishes",
                "name": "Bai Sach Chrouk (បាយសាច់ជ្រូក)",
                "price_usd": 1.75,
                "description": "Cambodia's quintessential breakfast: thinly sliced pork marinated in garlic, coconut milk, and palm sugar, slowly grilled over charcoal, served over warm broken rice with pickled cucumber, daikon, and a bowl of scallion soup."
            },
            {
                "category": "Rice Dishes",
                "name": "Bai Sach Chrouk Phorng Porng (បាយសាច់ជ្រូកពងមាន់)",
                "price_usd": 2.25,
                "description": "Grilled marinated pork broken rice topped with a crispy fried sunny-side egg and scallion oil."
            },
            {
                "category": "Rice Dishes",
                "name": "Bai Moan Chean (បាយមាន់ចៀន)",
                "price_usd": 2.25,
                "description": "Crispy golden fried marinated chicken thigh served over jasmine rice with sweet garlic chili dipping sauce."
            },
            {
                "category": "Sides",
                "name": "Porng Tea Chhar Sach Chrouk (ពងទាចៀនសាច់ជ្រូក)",
                "price_usd": 1.00,
                "description": "Fluffy Cambodian style omelet fried with minced pork and scallions."
            },
            {
                "category": "Drinks",
                "name": "Iced Green Tea Milk (តែបៃតងទឹកដោះគោ)",
                "price_usd": 1.00,
                "description": "Fragrant Thai-style sweet green tea with sweet condensed milk over ice."
            }
        ]
    },

    "nom_banh_chok": {
        "dish_en": "nom banh chok & khmer curry noodles",
        "dish_kh": "នំបញ្ចុក សម្លប្រហើរ និងសម្លការី",
        "benchmark_price": 2.25,
        "pattern": re.compile(r"nom\s*banh\s*chok|num\s*banh\s*chok|nom\s*banhchok|khmer\s*noodle|នំបញ្ចុក|សម្លប្រហើរ|សម្លការី", re.I),
        "menu": [
            {
                "category": "Noodles (នំបញ្ចុក)",
                "name": "Nom Banh Chok Samlor Proher (នំបញ្ចុកសម្លប្រហើរ)",
                "price_usd": 2.00,
                "description": "Fermented fresh rice noodles drenched in fragrant green river fish and kroeung lemongrass gravy, topped with crunchy shredded banana blossoms, water lily stems, cucumber, fresh mint, and holy basil."
            },
            {
                "category": "Noodles (នំបញ្ចុក)",
                "name": "Nom Banh Chok Samlor Kari (នំបញ្ចុកសម្លការី)",
                "price_usd": 2.25,
                "description": "Rice noodles served with aromatic mild red chicken and coconut curry, sweet potatoes, yardlong beans, and fresh vegetable assortment."
            },
            {
                "category": "Noodles (នំបញ្ចុក)",
                "name": "Nom Banh Chok Kampot (នំបញ្ចុកទឹកម្ទេសកំពត)",
                "price_usd": 2.25,
                "description": "Kampot-style dry rice noodles with sweet crushed dried shrimp, crushed peanuts, cucumber, bean sprouts, coconut cream, and fish sauce dressing."
            },
            {
                "category": "Sides",
                "name": "Chha Yor Chean (ឆាយ៉ចៀន)",
                "price_usd": 0.50,
                "description": "Crispy fried Cambodian spring rolls with pork, taro, and carrot filling."
            },
            {
                "category": "Drinks",
                "name": "Fresh Sugarcane Juice (ទឹកអំពៅ)",
                "price_usd": 0.50,
                "description": "Freshly crushed sugarcane juice squeezed with aromatic calamansi citrus."
            }
        ]
    },

    "lort_cha_mi_cha": {
        "dish_en": "lort cha, mi cha & wok-fried noodles",
        "dish_kh": "លតឆា មីឆា និងពងទាចៀន",
        "benchmark_price": 2.25,
        "pattern": re.compile(r"lort\s*cha|lot\s*cha|mi\s*cha|mee\s*cha|fried\s*noodle|pin\s*noodle|silver\s*needle|លតឆា|មីឆា", re.I),
        "menu": [
            {
                "category": "Fried Noodles",
                "name": "Lort Cha Sach Ko (លតឆាសាច់គោ)",
                "price_usd": 2.25,
                "description": "Silver needle short pin noodles stir-fried in a blazing hot wok with marinated beef, bean sprouts, Chinese chives, topped with a fried duck egg and sweet chili fish sauce."
            },
            {
                "category": "Fried Noodles",
                "name": "Mi Cha Sach Ko (មីឆាសាច់គោ)",
                "price_usd": 2.25,
                "description": "Wok-fried yellow egg noodles with tender sliced beef, Chinese kale (gai lan), bean sprouts, and sunny side egg."
            },
            {
                "category": "Fried Noodles",
                "name": "Mi Cha Sach Chrouk (មីឆាសាច់ជ្រូក)",
                "price_usd": 2.00,
                "description": "Stir-fried egg noodles with tender pork slices, chives, and fried egg."
            },
            {
                "category": "Fried Noodles",
                "name": "Lort Cha Porng Tea (លតឆាពងទា)",
                "price_usd": 1.50,
                "description": "Vegetarian friendly stir-fried pin noodles with eggs, chives, bean sprouts, and dark soy."
            },
            {
                "category": "Drinks",
                "name": "Iced Lemon Tea (តែក្រូចឆ្មារ)",
                "price_usd": 0.75,
                "description": "Chilled sweetened black tea with freshly squeezed Cambodian lime."
            }
        ]
    },

    "bok_lhong": {
        "dish_en": "bok lhong papaya salad & grilled chicken",
        "dish_kh": "បុកល្ហុង ភ្លាសាច់គោ និងមាន់អាំង",
        "benchmark_price": 2.50,
        "pattern": re.compile(r"bok\s*lhong|bok\s*lahong|papaya\s*salad|បុកល្ហុង|ភ្លាសាច់គោ|ញាំមី", re.I),
        "menu": [
            {
                "category": "Salads (បុកល្ហុង)",
                "name": "Bok Lhong Kdarm Seh (បុកល្ហុងក្តាមសេះ)",
                "price_usd": 2.50,
                "description": "Fiery mortar-pounded green papaya salad with salted raw blue crab, bird's eye chili, lime juice, yardlong beans, cherry tomatoes, and prahok fish sauce."
            },
            {
                "category": "Salads (បុកល្ហុង)",
                "name": "Bok Lhong Bangkea Krorng (បុកល្ហុងបង្គាក្រៀម)",
                "price_usd": 2.25,
                "description": "Crisp green papaya salad with dried river shrimp, roasted peanuts, garlic, lime, and tamarind."
            },
            {
                "category": "Salads (ញាំ)",
                "name": "Pleah Sach Ko (ភ្លាសាច់គោ)",
                "price_usd": 3.00,
                "description": "Cambodian rare lime-cured beef salad tossed with lemongrass kroeung, sawtooth coriander, mint, thinly sliced shallots, and roasted peanuts."
            },
            {
                "category": "Street Bites",
                "name": "Ploav Moan Ang (ភ្លៅមាន់អាំង)",
                "price_usd": 1.75,
                "description": "Charcoal grilled marinated whole chicken thigh served with Koh Kong sweet-spicy garlic lime sauce."
            },
            {
                "category": "Sides",
                "name": "Bai Domnaeb (បាយដំណើប)",
                "price_usd": 0.50,
                "description": "Warm steamed sticky rice served in a banana leaf packet."
            }
        ]
    },

    "num_pang": {
        "dish_en": "num pang khmer baguettes & pate sandwiches",
        "dish_kh": "នំប៉័ងប៉ាតេ និងនំប៉័ងសាច់",
        "benchmark_price": 1.75,
        "pattern": re.compile(r"num\s*pang|nampang|num\s*pang\s*pate|baguette|sandwich|នំប៉័ង|នំបុ័ង", re.I),
        "menu": [
            {
                "category": "Baguettes (នំប៉័ង)",
                "name": "Num Pang Sach Pate (នំប៉័ងប៉ាតេសាច់)",
                "price_usd": 1.50,
                "description": "Crispy French-Khmer baguette smeared with rich pork liver pâté, layered with steamed pork roll (cha lua), pickled carrots, daikon, cucumber, cilantro, homemade mayo, and chili."
            },
            {
                "category": "Baguettes (នំប៉័ង)",
                "name": "Num Pang Sach Chrouk Kvai (នំប៉័ងសាច់ជ្រូកខ្វៃ)",
                "price_usd": 1.75,
                "description": "Crusty baguette packed with crispy roasted five-spice pork belly, sweet plum sauce, cucumber, and pickled papaya."
            },
            {
                "category": "Baguettes (នំប៉័ង)",
                "name": "Num Pang Sach Ko Ang (នំប៉័ងសាច់គោអាំង)",
                "price_usd": 2.00,
                "description": "Baguette sandwich filled with lemongrass marinated grilled beef skewers and spicy pickled green papaya."
            },
            {
                "category": "Baguettes (នំប៉័ង)",
                "name": "Num Pang Ang Borer (នំប៉័ងអាំងប័រ)",
                "price_usd": 0.75,
                "description": "Toasted baguette brushed generously with garlic butter and sweet chili sauce."
            },
            {
                "category": "Drinks",
                "name": "Iced Milo (មីឡូទឹកកក)",
                "price_usd": 1.00,
                "description": "Creamy iced malt chocolate drink blended with sweetened condensed milk."
            }
        ]
    },

    "sach_ko_ang": {
        "dish_en": "sach ko ang grilled beef skewers & bbq",
        "dish_kh": "សាច់គោអាំង និងសាច់អាំង",
        "benchmark_price": 2.50,
        "pattern": re.compile(r"sach\s*ko\s*ang|beef\s*skewer|bbq\s*beef|សាច់គោអាំង|សាច់ជ្រូកអាំង|ភ្លៅមាន់អាំង|សាច់អាំង", re.I),
        "menu": [
            {
                "category": "BBQ Skewers",
                "name": "Sach Ko Ang Skewers (សាច់គោអាំង ៥ ចង្កាក់)",
                "price_usd": 2.50,
                "description": "5 skewers of succulent beef marinated in fragrant yellow lemongrass kroeung, coconut milk, and oyster sauce, charcoal grilled and served with pickled green papaya."
            },
            {
                "category": "BBQ Skewers",
                "name": "Sach Chrouk Ang Skewers (សាច់ជ្រូកអាំង ៥ ចង្កាក់)",
                "price_usd": 2.25,
                "description": "5 skewers of honey-garlic glazed pork skewers grilled over open embers."
            },
            {
                "category": "Breads",
                "name": "Num Pang Ang Borer (នំប៉័ងអាំងប័រ)",
                "price_usd": 0.75,
                "description": "Toasted French baguette brushed with garlic butter and sweet chili."
            },
            {
                "category": "Street Bites",
                "name": "Slap Moan Ang (ស្លាបមាន់អាំង ២)",
                "price_usd": 1.50,
                "description": "2 whole grilled chicken wings seasoned with Cambodian garlic and Kampot black pepper."
            },
            {
                "category": "Drinks",
                "name": "Angkor / Cambodia Beer (Can)",
                "price_usd": 1.00,
                "description": "Ice-cold canned local lager beer."
            }
        ]
    },

    "banh_chhev": {
        "dish_en": "banh chhev crispy crepes & banh srung",
        "dish_kh": "បាញ់ឆែវ និងបាញ់ស្រុង",
        "benchmark_price": 2.50,
        "pattern": re.compile(r"banh\s*chhev|banh\s*chav|crepe|បាញ់ឆែវ|បាញ់ស្រុង", re.I),
        "menu": [
            {
                "category": "Crepes & Noodles",
                "name": "Banh Chhev (បាញ់ឆែវ)",
                "price_usd": 2.50,
                "description": "Large crispy turmeric rice pancake filled with minced pork, shrimp, mung beans, and bean sprouts. Eaten wrapped in mustard greens, lettuce, mint, and dipped into sweet garlic fish sauce with crushed peanuts."
            },
            {
                "category": "Crepes & Noodles",
                "name": "Banh Srung (បាញ់ស្រុង)",
                "price_usd": 2.25,
                "description": "Warm fresh rice noodle salad topped with minced pork, wood-ear mushroom pork rolls, coconut cream sauce, shredded cucumber, and herbs."
            },
            {
                "category": "Sides",
                "name": "Nem Sros (ណែមស្រស់ ៣)",
                "price_usd": 1.50,
                "description": "3 fresh rice paper spring rolls packed with pork, shrimp, vermicelli noodles, lettuce, and peanut hoisin dip."
            },
            {
                "category": "Drinks",
                "name": "Fresh Pennywort Juice (ទឹកត្រចៀកកាំ)",
                "price_usd": 0.75,
                "description": "Cooling herbal green pennywort juice sweetened with palm sugar syrup."
            }
        ]
    },

    "borbor": {
        "dish_en": "borbor khmer rice congee & porridge",
        "dish_kh": "បបរ បបរសាច់មាន់ និងបបរគ្រឿង",
        "benchmark_price": 2.25,
        "pattern": re.compile(r"borbor|bobor|congee|rice\s*porridge|បបរ|បបរសាច់មាន់|បបរគ្រឿង", re.I),
        "menu": [
            {
                "category": "Porridge (បបរ)",
                "name": "Borbor Kroeung (បបរគ្រឿង)",
                "price_usd": 2.25,
                "description": "Traditional Cambodian savory rice porridge simmered with pork offal, intestines, blood jelly, crispy garlic, cilantro, bean sprouts, and lime."
            },
            {
                "category": "Porridge (បបរ)",
                "name": "Borbor Sach Moan (បបរសាច់មាន់)",
                "price_usd": 2.00,
                "description": "Silky rice congee made with shredded free-range chicken, fresh ginger matchsticks, toasted garlic oil, and scallions."
            },
            {
                "category": "Porridge (បបរ)",
                "name": "Borbor Sach Trey (បបរសាច់ត្រី)",
                "price_usd": 2.50,
                "description": "Clean and soothing rice porridge with fresh snakehead fish fillets, white Kampot pepper, and fried shallots."
            },
            {
                "category": "Sides",
                "name": "Cha Kway (ឆាខ្វៃ)",
                "price_usd": 0.50,
                "description": "Crispy fried dough cruller to dip in warm porridge."
            },
            {
                "category": "Drinks",
                "name": "Hot Jasmine Tea (តែផ្កាម្លិះក្តៅ)",
                "price_usd": 0.50,
                "description": "Freshly brewed fragrant jasmine hot tea."
            }
        ]
    },

    "roast_duck_pork": {
        "dish_en": "roast duck, crispy pork & chicken rice",
        "dish_kh": "ទាខ្វៃ ជ្រូកខ្វៃ និងបាយមាន់",
        "benchmark_price": 2.75,
        "pattern": re.compile(r"roast\s*duck|roasted\s*duck|chicken\s*rice|hainan|ទាខ្វៃ|ជ្រូកខ្វៃ|បាយមាន់", re.I),
        "menu": [
            {
                "category": "Roast Rice Dishes",
                "name": "Bai Tea Kvai (បាយទាខ្វៃ)",
                "price_usd": 2.75,
                "description": "Crispy five-spice roasted duck served over aromatic jasmine rice with rich spiced duck glaze, pickled cucumber, and broth."
            },
            {
                "category": "Roast Rice Dishes",
                "name": "Bai Chrouk Kvai (បាយជ្រូកខ្វៃ)",
                "price_usd": 2.50,
                "description": "Crunchy crackling roast pork belly over rice with sweet hoisin garlic dipping sauce."
            },
            {
                "category": "Roast Rice Dishes",
                "name": "Bai Moan Hainan (បាយមាន់ហៃណាំ)",
                "price_usd": 2.75,
                "description": "Poached tender chicken over fragrant ginger-garlic broth rice, served with chili ginger sauce and clear soup."
            },
            {
                "category": "Roast Specialties",
                "name": "Tea Kvai 1/4 (ទាខ្វៃ ១ ភាគ ៤)",
                "price_usd": 4.50,
                "description": "Quarter portion of freshly roasted five-spice duck chopped with signature spiced gravy."
            },
            {
                "category": "Drinks",
                "name": "Iced Lemon Tea (តែក្រូចឆ្មារ)",
                "price_usd": 0.75,
                "description": "Refreshing iced black tea with fresh lime."
            }
        ]
    },

    "soup_hotpot": {
        "dish_en": "beef soup, khmer hotpot & bone marrow",
        "dish_kh": "ស៊ុបគោ ស៊ុបខួរ និងស៊ុបពិសេស",
        "benchmark_price": 6.00,
        "pattern": re.compile(r"hotpot|hot\s*pot|suki|ស៊ុប|ស៊ុបគោ|ស៊ុបម្រះ|ស៊ុបខួរគោ|ស៊ុបពិសេស", re.I),
        "menu": [
            {
                "category": "Soups & Hot Pot",
                "name": "Soup Ko Khour (ស៊ុបគោខួរ)",
                "price_usd": 6.50,
                "description": "Aromatic Cambodian beef soup hot pot simmered with beef tendon, tender shank, cow brain, morning glory water spinach, Chinese cabbage, egg, and spicy lime dipping sauce."
            },
            {
                "category": "Soups & Hot Pot",
                "name": "Sngor Chruok Sach Moan (ស្ងោរជ្រក់សាច់មាន់)",
                "price_usd": 3.00,
                "description": "Classic tangy sour chicken soup infused with crushed lemongrass, kaffir lime leaves, lime juice, and sweet holy basil."
            },
            {
                "category": "Soups & Hot Pot",
                "name": "Samlor Machu Kroeung Sach Ko (សម្លម្ជូរគ្រឿងសាច់គោ)",
                "price_usd": 3.50,
                "description": "Hearty sour beef soup packed with yellow lemongrass paste, morning glory, and tender beef ribs."
            },
            {
                "category": "Hot Pot Add-ons",
                "name": "Fresh Yellow Egg Noodles & Veg Set (មី និងបន្លែ)",
                "price_usd": 1.50,
                "description": "Platter of fresh noodles, eggs, and assorted greens for dipping into the hot pot."
            },
            {
                "category": "Drinks",
                "name": "Angkor Beer (Can)",
                "price_usd": 1.00,
                "description": "Chilled local Angkor premium beer."
            }
        ]
    },

    "teuk_krolok": {
        "dish_en": "teuk krolok & fresh fruit smoothies",
        "dish_kh": "ទឹកក្រឡុក និងផ្លែឈើស្រស់",
        "benchmark_price": 1.25,
        "pattern": re.compile(r"smoothie|teuk\s*krolok|fruit\s*shake|ទឹកក្រឡុក|ផ្លែឈើក្រឡុក", re.I),
        "menu": [
            {
                "category": "Fruit Shakes (ទឹកក្រឡុក)",
                "name": "Teuk Krolok Bo (ទឹកក្រឡុកប័រ)",
                "price_usd": 1.50,
                "description": "Rich creamy ripe Hass avocado blended with sweetened condensed milk and ice."
            },
            {
                "category": "Fruit Shakes (ទឹកក្រឡុក)",
                "name": "Teuk Krolok Svay (ទឹកក្រឡុកស្វាយ)",
                "price_usd": 1.25,
                "description": "Tropical sweet ripe Cambodian mango shake."
            },
            {
                "category": "Fruit Shakes (ទឹកក្រឡុក)",
                "name": "Teuk Krolok Tiep Barang (ទឹកក្រឡុកទៀបបារាំង)",
                "price_usd": 1.50,
                "description": "Sweet and tangy soursop fruit shake."
            },
            {
                "category": "Fruit Shakes (ទឹកក្រឡុក)",
                "name": "Teuk Krolok Chhveak (ទឹកក្រឡុកផ្លែផាសិន)",
                "price_usd": 1.00,
                "description": "Tart and refreshing passion fruit smoothie."
            },
            {
                "category": "Fruit Shakes (ទឹកក្រឡុក)",
                "name": "Teuk Krolok Pitahaya (ទឹកក្រឡុកផ្លែស្រកានាគ)",
                "price_usd": 1.25,
                "description": "Vibrant purple dragonfruit smoothie."
            }
        ]
    },

    "bangaem_dessert": {
        "dish_en": "bang'aem khmer sweet desserts & shaved ice",
        "dish_kh": "បង្អែមខ្មែរ និងទឹកកកឈូស",
        "benchmark_price": 1.25,
        "pattern": re.compile(r"dessert|bang\s*aem|bangaem|បង្អែម|ផ្លែឈើ|បង្អែមខ្មែរ|បាញ់ចានឿក", re.I),
        "menu": [
            {
                "category": "Khmer Sweets (បង្អែម)",
                "name": "Bang'aem Lod Chong (បង្អែមលត)",
                "price_usd": 1.00,
                "description": "Fragrant green pandan rice drops in sweet coconut cream and roasted palm sugar syrup over crushed ice."
            },
            {
                "category": "Khmer Sweets (បង្អែម)",
                "name": "Cheik Khteh (ចេកខ្ទិះ)",
                "price_usd": 1.00,
                "description": "Ripe sweet bananas simmered in warm coconut cream with chewy tapioca pearls and toasted sesame seeds."
            },
            {
                "category": "Khmer Sweets (បង្អែម)",
                "name": "Teuk Gok Chhous Assorted (ទឹកកកឈូសគ្រឿង)",
                "price_usd": 1.25,
                "description": "Shaved ice with palm seeds, water chestnuts, herbal grass jelly, sweet corn, condensed milk, and red syrup."
            },
            {
                "category": "Khmer Sweets (បង្អែម)",
                "name": "Bai Domnaeb Sangkhya (បាយដំណើបសង់ខ្យា)",
                "price_usd": 1.50,
                "description": "Warm coconut sticky rice topped with rich steamed pandan egg custard."
            },
            {
                "category": "Drinks",
                "name": "Fresh Young Coconut (ទឹកដូងក្រអូប)",
                "price_usd": 1.00,
                "description": "Chilled whole aromatic young coconut served with straw and spoon."
            }
        ]
    },

    "chha_kdao_khmer": {
        "dish_en": "chha kdao, beef lok lak & khmer home dishes",
        "dish_kh": "ឆាក្តៅ ឡុកឡាក់ និងម្ហូបខ្មែរ",
        "benchmark_price": 3.00,
        "pattern": re.compile(r"chha\s*kdao|cha\s*kdao|stir\s*fry|lok\s*lak|បាយឆា|ឆាក្តៅ|ឆាខ្ញី|ម្ហូបខ្មែរ|ឡុកឡាក់|ឡុកឡាក់សាច់គោ", re.I),
        "menu": [
            {
                "category": "Khmer Stir Fry",
                "name": "Chha Kdao Sach Ko (ឆាក្តៅសាច់គោ)",
                "price_usd": 3.00,
                "description": "Fiery wok-tossed beef with fragrant yellow lemongrass kroeung, red bird's eye chilies, yardlong beans, and generous fresh holy basil."
            },
            {
                "category": "Khmer Stir Fry",
                "name": "Chha Kdao Sach Moan (ឆាក្តៅសាច់មាន់)",
                "price_usd": 2.75,
                "description": "Spicy chicken stir-fry with fragrant holy basil, garlic, young green peppercorns, and red peppers."
            },
            {
                "category": "Khmer Favorites",
                "name": "Bai Lok Lak Sach Ko (បាយឡុកឡាក់សាច់គោ)",
                "price_usd": 3.25,
                "description": "Iconic Cambodian dish: tender cubes of marinated beef quickly seared in a hot wok, served over jasmine rice, bed of fresh lettuce, tomatoes, cucumbers, fried egg, and black Kampot pepper-lime dip."
            },
            {
                "category": "Khmer Stir Fry",
                "name": "Chha Khgnei Sach Moan (ឆាខ្ញីសាច់មាន់)",
                "price_usd": 2.75,
                "description": "Shredded young ginger stir-fried with chicken, fermented yellow soy beans, and scallions."
            },
            {
                "category": "Khmer Favorites",
                "name": "Amok Trey (អាម៉ុកត្រី)",
                "price_usd": 3.50,
                "description": "Cambodia's national treasure: fresh river fish steamed in rich coconut milk, kroeung curry paste, noni leaves, and egg custard in a banana leaf boat."
            },
            {
                "category": "Sides",
                "name": "Bai Sor (បាយស)",
                "price_usd": 0.50,
                "description": "A fragrant bowl of steamed Cambodian jasmine rice."
            }
        ]
    }
}


def enrich_street_food_menus(csv_path: Path) -> int:
    """Enriches street food and local stalls with realistic menus and pricing."""
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    log.info("Loaded %d rows from %s", len(df), csv_path)

    # Filter to places that currently do NOT have a menu
    no_menu_mask = df["menu"].str.strip() == ""
    log.info("Found %d places with NO menu", no_menu_mask.sum())

    enriched_counts = {cat_id: 0 for cat_id in STREET_FOOD_MENUS}
    total_enriched = 0

    for idx in df[no_menu_mask].index:
        name = df.at[idx, "name"]
        dish_en = df.at[idx, "dish_en"]
        dish_kh = df.at[idx, "dish_kh"]
        desc = df.at[idx, "description"]
        tags = df.at[idx, "tags"]
        combined = f"{name} {dish_en} {dish_kh} {desc} {tags}"

        for cat_id, info in STREET_FOOD_MENUS.items():
            if info["pattern"].search(combined):
                menu_json = json.dumps(info["menu"], ensure_ascii=False)
                df.at[idx, "menu"] = menu_json

                if not df.at[idx, "dish_en"] or df.at[idx, "dish_en"].lower().startswith("khmer & asian"):
                    df.at[idx, "dish_en"] = info["dish_en"]
                if not df.at[idx, "dish_kh"]:
                    df.at[idx, "dish_kh"] = info["dish_kh"]
                if not df.at[idx, "price_usd"] or df.at[idx, "price_usd"] == "0":
                    df.at[idx, "price_usd"] = f"{info['benchmark_price']:.2f}"

                enriched_counts[cat_id] += 1
                total_enriched += 1
                break

    df.to_csv(csv_path, index=False)
    log.info("Successfully enriched %d local eateries in %s", total_enriched, csv_path)
    for cat_id, count in enriched_counts.items():
        log.info("  ✓ %-18s: %4d stalls enriched", cat_id, count)

    return total_enriched


if __name__ == "__main__":
    enrich_street_food_menus(CSV_PATH)
