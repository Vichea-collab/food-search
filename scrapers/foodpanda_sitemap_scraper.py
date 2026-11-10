"""
Foodpanda Cambodia Sitemap Scraper (Nationwide Coverage)
Source: https://www.foodpanda.com.kh/adventure-map/adventure-map-restaurant-0.xml
Extracts: restaurants across all 25 provinces/cities of Cambodia
(Siem Reap, Battambang, Sihanoukville, Kampot, Phnom Penh, Kandal, etc.)
with bilingual URLs, estimated prices, ordering channels, and contact links.
"""

import re
import csv
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests
try:                               # scrapers/robots.py: obey robots.txt and the site's crawl delay
    from scrapers import robots
except ImportError:
    import robots

logger = logging.getLogger(__name__)

SITEMAP_URL = "https://www.foodpanda.com.kh/adventure-map/adventure-map-restaurant-0.xml"

# Nationwide Cambodia Province & City mapping from slug keywords
PROVINCE_PATTERNS = [
    (re.compile(r"siem-reap|siemreap|angkor|pub-street|wat-bo", re.I), "Siem Reap"),
    (re.compile(r"battambang|bat-dambang", re.I), "Battambang"),
    (re.compile(r"sihanoukville|sihanouk|kampong-som|koh-rong", re.I), "Preah Sihanouk"),
    (re.compile(r"kampot|chhouk", re.I), "Kampot"),
    (re.compile(r"kep\b|krab", re.I), "Kep"),
    (re.compile(r"ta-khmau|kandal|ang-snuol|kiensvay", re.I), "Kandal"),
    (re.compile(r"kampong-cham|tbong-khmum|suong", re.I), "Kampong Cham"),
    (re.compile(r"poipet|poi-pet|banteay-meanchey|sisophon", re.I), "Banteay Meanchey"),
    (re.compile(r"bavet|svay-rieng", re.I), "Svay Rieng"),
    (re.compile(r"koh-kong|smach-meanchey", re.I), "Koh Kong"),
    (re.compile(r"pursat", re.I), "Pursat"),
    (re.compile(r"kampong-chhnang", re.I), "Kampong Chhnang"),
    (re.compile(r"kampong-speu", re.I), "Kampong Speu"),
    (re.compile(r"kratie", re.I), "Kratie"),
    (re.compile(r"takeo|doun-keo", re.I), "Takeo"),
    (re.compile(r"prey-veng", re.I), "Prey Veng"),
    (re.compile(r"stung-treng", re.I), "Stung Treng"),
    (re.compile(r"mondulkiri|senmonorom", re.I), "Mondulkiri"),
    (re.compile(r"ratanakiri|banlung", re.I), "Ratanakiri"),
    (re.compile(r"preah-vihear", re.I), "Preah Vihear"),
    (re.compile(r"oddar-meanchey|samraong", re.I), "Oddar Meanchey"),
    (re.compile(r"pailin", re.I), "Pailin"),
    # Phnom Penh Khans / landmarks
    (re.compile(r"bkk|boeung-keng-kang|boeng-keng-kang", re.I), "Boeung Keng Kang"),
    (re.compile(r"toul-tom-poung|russian-market|chamkar-mon|chamkarmon|bassac", re.I), "Chamkar Mon"),
    (re.compile(r"daun-penh|doun-penh|phsar-thmei|psar-thmei|riverside|sisowath|wat-phnom|kandal-market", re.I), "Daun Penh"),
    (re.compile(r"toul-kork|tuol-kouk|tuol-kork", re.I), "Toul Kork"),
    (re.compile(r"sen-sok|sensok|phnom-penh-thmey|pp-thmey|aeon-2", re.I), "Sen Sok"),
    (re.compile(r"chroy-changvar|chroy-changva", re.I), "Chroy Changvar"),
    (re.compile(r"mean-chey|meanchey|steung-mean-chey|aeon-3", re.I), "Mean Chey"),
    (re.compile(r"chbar-ampov|chbar-ompov|boeng-snor", re.I), "Chbar Ampov"),
    (re.compile(r"prampir-makara|7-makara|olympic", re.I), "Prampir Makara"),
    (re.compile(r"russey-keo|toul-sangke", re.I), "Russey Keo"),
    (re.compile(r"pou-senchey|por-senchey|tang-krasang", re.I), "Pou Senchey"),
    (re.compile(r"dangkao", re.I), "Dangkao"),
    (re.compile(r"prek-pnov|preaek-pnov", re.I), "Prek Pnov"),
    (re.compile(r"kamboul", re.I), "Kamboul"),
    (re.compile(r"phnom-penh", re.I), "Phnom Penh"),
]

# Baseline meal price and bilingual dish mapping based on culinary category
# A label is only a guess from the name: name no specific dish the name does not show (a 'rice' shop was labelled
# lok lak before, which put 50 places that never said so on top of every lok lak search).
CUISINE_MAPPINGS = [
    (re.compile(r"no?m[-_ ]?b[ao]nh[-_ ]?ch[o|u]k|so?mlo?r[-_ ]?khmer", re.I), "Nom Banh Chok (Khmer Noodle Soup)", "នំបញ្ចុក និងសម្លខ្មែរ", "2.25"),
    (re.compile(r"num[-_ ]?pang|numpang|baguette|sandwich|chrouk[-_ ]?kvai|chruk[-_ ]?kvai", re.I), "Num Pang (Cambodian Baguettes & Sandwiches)", "នំប៉័ងសាច់ប៉ាតេ និងសាច់ជ្រូកខ្វៃ", "2.00"),
    (re.compile(r"banh[-_ ]?chhe?a?v|banh[-_ ]?chao", re.I), "Banh Chhev (Crispy Stuffed Rice Crepes)", "បាញ់ឆែវ", "2.50"),
    (re.compile(r"lo?rt[-_ ]?ch?ha?|mi[-_ ]?cha", re.I), "Lort Cha & Fried Noodles", "លតឆា និងមីឆា", "2.25"),
    (re.compile(r"bok[-_ ]?l[ah]ong|tam[-_ ]?tam|papaya[-_ ]?salad", re.I), "Bok Lhong (Spicy Papaya Salad & Street Food)", "បុកល្ហុង និងគ្រឿងក្លែម", "2.50"),
    (re.compile(r"cha[-_ ]?kda[vo]|chha[-_ ]?kdao", re.I), "Cha Kdao (Spicy Holy Basil Stir-Fry)", "ឆាក្តៅ និងម្ហូបខ្មែរ", "3.00"),
    (re.compile(r"mi[-_ ]?sour|mee[-_ ]?sour", re.I), "Mi Sour (Khmer Glass Noodle Soup)", "មីសួរ និងស៊ុប", "2.50"),
    (re.compile(r"mi[-_ ]?hel|mee[-_ ]?hal|spicy[-_ ]?noodle", re.I), "Spicy Level Noodles (Mi Hel)", "មីហឹរ ៧ កម្រិត", "2.75"),
    (re.compile(r"bay[-_ ]?m[oa]i?n|bai[-_ ]?moan|chicken[-_ ]?rice", re.I), "Hainanese & Khmer Chicken Rice", "បាយមាន់ និងបាយមាន់ស្រែ", "2.50"),
    (re.compile(r"bay[-_ ]?sach|bai[-_ ]?sach", re.I), "Bai Sach Chrouk (Grilled Pork & Rice)", "បាយសាច់ជ្រូក", "2.00"),
    (re.compile(r"lok[-_ ]?lak", re.I), "Beef Lok Lak", "ឡុកឡាក់សាច់គោ", "4.50"),
    (re.compile(r"amok", re.I), "Fish Amok & Traditional Khmer Curries", "អាម៉ុកត្រី និងការីខ្មែរ", "5.00"),
    (re.compile(r"pt[eh]s[-_ ]?bay|ptah[-_ ]?bay|louk[-_ ]?bay|mho?b[-_ ]?kamo?ng|bay[-_ ]?bak", re.I), "Khmer Made-to-Order Rice Dishes", "បាយកុម្ម៉ង់ និងម្ហូបខ្មែរ", "2.75"),
    (re.compile(r"kuy[-_ ]?teav|kuyteav|noodle|ramen|pho\b|mee\b|soup[-_ ]?mee|udon", re.I), "Noodles & Soup", "គុយទាវ និងមី", "2.50"),
    (re.compile(r"pizza|pasta|spaghetti|italian", re.I), "Pizza & Italian Cuisine", "ភីហ្សា និងម្ហូបអ៊ីតាលី", "7.50"),
    (re.compile(r"burger|fries|crispy[-_ ]?chicken|fried[-_ ]?chicken|kfc|lotteria|texas[-_ ]?chicken|potato[-_ ]?corner|vons[-_ ]?chicken", re.I), "Burgers & Fried Chicken", "ប៊ឺហ្គឺ និងមាន់បំពងស្រួយ", "4.50"),
    (re.compile(r"kfae|kafe|kofi|koffee|coffee|cafe|espresso|latte|cappuccino|starbucks|amazon|brown[-_ ]?coffee|tube[-_ ]?coffee|arabica", re.I), "Coffee & Beverages", "កាហ្វេ និងភេសជ្ជៈ", "2.25"),
    (re.compile(r"matcha|chagee|boba|tea\b|bubble|milk[-_ ]?tea|cha[-_ ]?tra[-_ ]?mue|an[-_ ]?cha|dakasi|koi|gong[-_ ]?cha|mixue", re.I), "Bubble Tea & Specialty Teas", "តែគុជ ម៉ាតឆា និងតែផ្លែឈើ", "2.00"),
    (re.compile(r"yogurt|smoothie|shake|juice|fruit|acai|milkh", re.I), "Fresh Juices, Smoothies & Yogurt", "ទឹកក្រឡុក ទឹកផ្លែឈើស្រស់ និងយ៉ាអួ", "2.25"),
    (re.compile(r"bakery|bread|cake|pastry|dessert|donut|tous[-_ ]?les[-_ ]?jours|breadtalk|bakehouse|castella|gato|croissant", re.I), "Bakery, Pastries & Cakes", "នំប៉័ង បង្អែម និងនំខេក", "2.50"),
    (re.compile(r"ice[-_ ]?cream|gelato|bingsoo|bingsu|swensen|dairy[-_ ]?queen", re.I), "Ice Cream & Bingsu", "ការ៉េម ប៊ីងស៊ូ និងបង្អែមត្រជាក់", "2.50"),
    (re.compile(r"bbq|grill|barbecue|roast|sach[-_ ]?ang|moo[-_ ]?kata|buffet", re.I), "BBQ & Grilled Meats", "សាច់អាំង និងម្ហូបក្លែម", "5.50"),
    (re.compile(r"sushi|japanese|bento|teriyaki|sashimi", re.I), "Japanese Cuisine & Sushi", "ម្ហូបជប៉ុន និងស៊ូស៊ី", "8.00"),
    (re.compile(r"korean|kimchi|bibimbap|tteokbokki|samgyeopsal|k[-_ ]?bbq", re.I), "Korean Cuisine", "ម្ហូបកូរ៉េ", "7.50"),
    (re.compile(r"dim[-_ ]?sum|bao\b|dumpling|chinese|peking[-_ ]?duck|chongqing|szechuan", re.I), "Chinese Dim Sum & Dishes", "ម្ហូបចិន ឌីមសាំ និងគាវ", "6.00"),
    (re.compile(r"seafood|crab|prawn|fish|kampot[-_ ]?crab|lobster|salmon|shrimp", re.I), "Seafood Dishes", "គ្រឿងសមុទ្រស្រស់ៗ", "8.50"),
    (re.compile(r"hot[-_ ]?pot|hotpot|shabu|soup|suki", re.I), "Hot Pot & Soup", "ស៊ុប និងស៊ុបឆ្នាំងដី", "7.50"),
    (re.compile(r"rice|bay[-_ ]?sach|bay[-_ ]?chhar|fried[-_ ]?rice|curry", re.I), "Khmer Rice Dishes & Daily Specials", "ម្ហូបបាយ និងម្ហូបខ្មែរ", "2.75"),
    (re.compile(r"street[-_ ]?food|snack|meatball|changret|prahit", re.I), "Khmer Street Food & Snacks", "អាហារសម្រន់តាមផ្លូវ និងប្រហិត", "1.75"),
    (re.compile(r"vegetarian|vegan|plant[-_ ]?based", re.I), "Vegetarian Food", "ម្ហូបបួស និងអាហារសុខភាព", "3.50"),
]

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

    # Western, Fast Food & Bakery
    (re.compile(r"burger|ប៊ឺហ្គឺ|fast\s*food", re.I),
     "Classic Cheeseburger, Crispy Fried Chicken Burger, Seasoned French Fries, Onion Rings",
     "ប៊ឺហ្គឺសាច់គោឈីស ប៊ឺហ្គឺមាន់បំពងស្រួយ និងដំឡូងបារាំងបំពង"),
    (re.compile(r"fried\s*chicken|crispy\s*chicken|មាន់បំពង", re.I),
     "Crispy Fried Chicken (Original / Spicy), Chicken Tenders, Fries, Coleslaw",
     "មាន់បំពងស្រួយរសជាតិហឹរ សាច់មាន់បន្ទះ និងដំឡូងបំពង"),
    (re.compile(r"pizza|pasta|spaghetti|ភីហ្សា|ម្ហូបអ៊ីតាលី|italian", re.I),
     "Wood-Fired Pizza (Margherita, Pepperoni), Creamy Pasta Carbonara, Spaghetti Bolognese",
     "ភីហ្សាដុតភ្លើងអុស ភីហ្សាភិបភើរ៉ូនី ប៉ាស្តាកាបូណារ៉ា និងស្ប៉ាហ្គេតទី"),
    (re.compile(r"bakery|cake|pastry|bread|croissant|dessert|នំប៉័ង|នំ|នំខេក", re.I),
     "French Butter Croissants, Fresh Baguettes, Chocolate Mousse Cake, Fruit Danish, Egg Tarts",
     "នំប៉័ងបារាំង ក្រូសង់ប៊័រ នំខេកសូកូឡា និងនំដេនីសផ្លែឈើ"),
    (re.compile(r"ice\s*cream|gelato|bingsoo|bingsu|ការ៉េម", re.I),
     "Artisan Gelato, Mango Bingsu (Korean Shaved Snow Ice), Waffle Sundae Bowls",
     "ការ៉េមជេឡាតូ ប៊ីងស៊ូផ្លែស្វាយ និងការ៉េមកែវធំ"),

    # BBQ & Hot Pot
    (re.compile(r"bbq|barbecue|grill|សាច់អាំង|sach\s*ko\s*jakak", re.I),
     "Grilled Beef Skewers (Sach Ko Ang), BBQ Pork Ribs, Grilled Chicken Wings, Pickled Papaya",
     "សាច់គោចាក់កាក់អាំង ឆ្អឹងជំនីជ្រូកអាំង និងជ្រក់ល្ហុង"),
    (re.compile(r"hot\s*pot|suki|soup|ស៊ុប|shabu", re.I),
     "Claypot Suki Soup, Seafood Shabu Shabu, Sliced Australian Beef Hot Pot, Fresh Greens",
     "ស៊ុបឆ្នាំងដី ស៊ុបស៊ូគីគ្រឿងសមុទ្រ និងស៊ុបសាច់គោស្លាយ"),

    # International & Specialty
    (re.compile(r"seafood|crab|shrimp|fish|គ្រឿងសមុទ្រ|ក្តាម|បង្គា|ត្រី", re.I),
     "Stir-Fried Crab with Fresh Kampot Green Peppercorns, Grilled River Prawns, Steamed Fish with Ginger",
     "ក្តាមថ្មឆាម្រេចខ្ចីកំពត បង្គាទន្លេអាំង និងត្រីចំហុយមីសួរខ្ញី"),
    (re.compile(r"sushi|japanese|sashimi|ម្ហូបជប៉ុន", re.I),
     "Fresh Salmon Sashimi, Spicy Tuna Roll, Chicken Teriyaki Bento, Tonkotsu Ramen",
     "សាស៊ីមីសាល់ម៉ុង ស៊ូស៊ី បាយប្រអប់តេរីយ៉ាគី និងរ៉ាមេន"),
    (re.compile(r"korean|kimchi|k-bbq|ម្ហូបកូរ៉េ", re.I),
     "Korean Grilled Pork Belly (Samgyeopsal), Stone-Bowl Bibimbap, Tteokbokki, Kimchi Jjigae",
     "សាច់ជ្រូកបីជាន់អាំងកូរ៉េ បាយឆាថ្មប៊ីប៊ីមបាប់ តុកបុកគី និងស៊ុបគីមឈី"),
    (re.compile(r"chinese|dim\s*sum|ម្ហូបចិន", re.I),
     "Steamed Pork Dumplings (Siu Mai), BBQ Pork Buns (Char Siu Bao), Peking Duck, Chow Mein",
     "ឌីមសាំគាវសាច់ជ្រូក នំប៉ាវសាច់ក្រហម ទាខ្វៃ និងមីឆាចិន"),
    (re.compile(r"indian|curry|ម្ហូបឥណ្ឌា", re.I),
     "Butter Chicken Curry, Lamb Biryani with Raita, Garlic Naan, Vegetable Samosas",
     "ការីមាន់ប៊័រ បាយប៊ីរយ៉ានីសាច់ចៀម នំប៉័ងណាន និងសារម៉ូសា"),
    (re.compile(r"vegetarian|vegan|ម្ហូបបួស", re.I),
     "Tofu & Vegetable Stir-Fry, Fresh Spring Rolls with Peanut Dip, Vegetarian Amok, Garden Salad",
     "ឆាតៅហ៊ូបន្លែស្រស់ គួងបួសទឹកជ្រលក់សណ្តែកដី អាម៉ុកបួស និងសាឡាដ"),
]

def get_signature_items(text: str) -> tuple[str, str]:
    for pat, sig_en, sig_kh in CATEGORY_SIGNATURE_ITEMS:
        if pat.search(text):
            return sig_en, sig_kh
    return (
        "Khmer Made-to-Order Dishes: Beef Lok Lak, Pork with Rice, Fried Rice, Stir-Fried Morning Glory",
        "បាយម្ហូបកុម្ម៉ង់ ឡុកឡាក់សាច់គោ បាយសាច់ជ្រូក បាយឆា និងឆាត្រកួន"
    )

def parse_slug(slug: str) -> tuple[str, str, str, str, str, str]:
    """Parse vendor slug into (clean_name, area, price_usd, dish_en, dish_kh, tags)."""
    parts = slug.split("-")
    if len(parts) > 1 and len(parts[-1]) in [4, 5] and parts[-1].isalnum() and not parts[-1].isdigit():
        parts = parts[:-1]
    
    slug_str = "-".join(parts)
    
    # Infer province/area
    area = "Phnom Penh"
    for pat, area_name in PROVINCE_PATTERNS:
        if pat.search(slug_str):
            area = area_name
            break

    # Infer estimated price, dish_en, dish_kh
    price = "2.75"
    dish_en = "Khmer & Asian Made-to-Order Dishes"
    dish_kh = "បាយម្ហូបកុម្ម៉ង់ និងម្ហូបខ្មែរ"
    for pat, d_en, d_kh, p in CUISINE_MAPPINGS:
        if pat.search(slug_str):
            dish_en = d_en
            dish_kh = d_kh
            price = p
            break

    # Clean name
    clean_parts = [p.capitalize() for p in parts if p.lower() not in ["pandasend", "express"]]
    name = " ".join(clean_parts) or slug_str.replace("-", " ").title()

    # Tags
    tags = ["restaurant", "foodpanda", "delivery", "takeaway"]
    s_lower = slug_str.lower()
    for cat in ["coffee", "cafe", "tea", "bubble_tea", "pizza", "burger", "bakery", "noodles", "bbq", "seafood", "vegetarian"]:
        # a whole word of the address: "kuy-teav" is not "tea" (QA 10 Nov: 35 noodle shops were tagged tea)
        if re.search(rf"(?<![a-z]){re.escape(cat.replace('_', '-'))}(?![a-z])", s_lower):
            tags.append(cat)

    return name, area, price, dish_en, dish_kh, ";".join(dict.fromkeys(tags))

def scrape_foodpanda_restaurants(max_items: int = 1500) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"Fetching Foodpanda Cambodia sitemap: {SITEMAP_URL}")
    r = robots.get(SITEMAP_URL, headers=headers, timeout=25)
    soup = BeautifulSoup(r.content, "xml")
    
    urls = soup.find_all("url")
    print(f"Total restaurant entries in Foodpanda Cambodia sitemap: {len(urls)}")
    
    places = []
    seen_ids = set()

    for u in urls:
        loc_el = u.find("loc")
        if not loc_el:
            continue
        loc = loc_el.text.strip()
        
        m = re.search(r"/restaurant/([^/]+)/([^/]+)", loc)
        if not m:
            continue
        code_id, raw_slug = m.group(1), m.group(2)
        
        if code_id in seen_ids:
            continue
        seen_ids.add(code_id)

        # Bilingual URLs
        en_url = loc
        kh_url = loc
        for link in u.find_all("xhtml:link"):
            hreflang = link.get("hreflang", "")
            href = link.get("href", "")
            if "en" in hreflang:
                en_url = href
            elif "km" in hreflang:
                kh_url = href

        name, area, price, dish_en, dish_kh, tags = parse_slug(raw_slug)

        # Conversational description with ordering & price guidance
        desc_parts = [
            f"Foodpanda restaurant partner in {area}, Cambodia.",
            f"Serving {dish_en} ({dish_kh}).",
            # (no estimated price and no template "popular menu items": the chatbot must only state real facts)
            f"How to order: Order online via Foodpanda delivery app or takeaway. Contact / view full menu at {en_url}. អាចកុម្ម៉ង់ដឹកជូន ឬទៅយកផ្ទាល់តាមអេប Foodpanda។"
        ]

        places.append({
            "id": f"fp-{code_id}",
            "name": name,
            "dish_en": dish_en,
            "dish_kh": dish_kh,
            "description": " ".join(desc_parts),
            "tags": tags,
            "price_usd": "",  # facts only: not given by the source, so left empty (never a default) (the slug only suggests a typical price)
            "area": area,
            "lat": "",
            "lng": "",
            "rating": "",  # facts only: not given by the source, so left empty (never a default)
            "open_hour": "",
            "close_hour": "",
            "source": "foodpanda",
            "source_url": en_url,
            "date": "2026-11-05",
            "image_path": "",
            "phone_public": "",
            "page_url": kh_url,
        })

        if len(places) >= max_items:
            break

    return places

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Foodpanda Cambodia restaurants nationwide")
    parser.add_argument("--limit", type=int, default=3500, help="Max restaurants to collect nationwide")
    parser.add_argument("--output", type=str, default="data/scraped/foodpanda_places.csv", help="Output path")
    args = parser.parse_args()

    places = scrape_foodpanda_restaurants(max_items=args.limit)
    print(f"Scraped {len(places)} Foodpanda restaurants across Cambodia!")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if places:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(places[0].keys()))
            writer.writeheader()
            writer.writerows(places)
        print(f"Saved to {out_path}")
        # Print breakdown by province
        import collections
        area_counts = collections.Counter(p["area"] for p in places)
        print("\nBreakdown by Area / Province:")
        for a, count in area_counts.most_common(12):
            print(f"  {a}: {count}")
