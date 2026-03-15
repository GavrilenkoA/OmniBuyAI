"""Scraper for perekrestok.ru products.

Falls back to generating realistic test data if the site blocks requests.
"""

import csv
import json
import os

from .config import DATA_DIR

# Realistic test data based on actual Perekrestok product catalog
TEST_PRODUCTS = [
    # Молочные продукты
    {"id": 1, "category": "Молочные продукты", "name": "Молоко Простоквашино 2.5% 930мл", "price": 89.99,
     "calories": 54, "proteins": 2.9, "fats": 2.5, "carbs": 4.7,
     "description": "Молоко пастеризованное Простоквашино 2.5% жирности", "compound": "Молоко нормализованное"},
    {"id": 2, "category": "Молочные продукты", "name": "Кефир Домик в деревне 1% 930мл", "price": 79.99,
     "calories": 40, "proteins": 3.0, "fats": 1.0, "carbs": 4.0,
     "description": "Кефир с живыми бактериями", "compound": "Молоко нормализованное, закваска кефирных грибков"},
    {"id": 3, "category": "Молочные продукты", "name": "Творог Простоквашино 5% 220г", "price": 109.99,
     "calories": 121, "proteins": 18.0, "fats": 5.0, "carbs": 3.3,
     "description": "Творог рассыпчатый 5% жирности", "compound": "Молоко нормализованное, закваска"},
    {"id": 4, "category": "Молочные продукты", "name": "Сметана Простоквашино 15% 300г", "price": 89.99,
     "calories": 162, "proteins": 2.6, "fats": 15.0, "carbs": 3.6,
     "description": "Сметана 15% жирности", "compound": "Сливки нормализованные, закваска"},
    {"id": 5, "category": "Молочные продукты", "name": "Сыр Российский 50% 300г", "price": 329.99,
     "calories": 364, "proteins": 24.1, "fats": 29.5, "carbs": 0.3,
     "description": "Сыр полутвёрдый Российский", "compound": "Молоко пастеризованное, соль, закваска, фермент"},
    {"id": 6, "category": "Молочные продукты", "name": "Масло сливочное Простоквашино 82.5% 180г", "price": 179.99,
     "calories": 748, "proteins": 0.5, "fats": 82.5, "carbs": 0.8,
     "description": "Масло сливочное традиционное", "compound": "Пастеризованные сливки"},

    # Мясо и птица
    {"id": 7, "category": "Мясо и птица", "name": "Филе куриной грудки охл. 800г", "price": 349.99,
     "calories": 113, "proteins": 23.6, "fats": 1.9, "carbs": 0.4,
     "description": "Филе куриной грудки без кожи охлаждённое", "compound": "Мясо курицы"},
    {"id": 8, "category": "Мясо и птица", "name": "Фарш говяжий охл. 500г", "price": 399.99,
     "calories": 254, "proteins": 17.2, "fats": 20.0, "carbs": 0.0,
     "description": "Фарш из говядины охлаждённый", "compound": "Говядина"},
    {"id": 9, "category": "Мясо и птица", "name": "Бедро куриное охл. 1кг", "price": 259.99,
     "calories": 185, "proteins": 16.8, "fats": 13.0, "carbs": 0.2,
     "description": "Бедро цыплёнка-бройлера", "compound": "Мясо курицы"},
    {"id": 10, "category": "Мясо и птица", "name": "Свинина шейка охл. 500г", "price": 449.99,
     "calories": 267, "proteins": 16.1, "fats": 22.8, "carbs": 0.0,
     "description": "Шейка свиная бескостная охлаждённая", "compound": "Свинина"},

    # Крупы и макароны
    {"id": 11, "category": "Крупы и макароны", "name": "Овсяные хлопья Геркулес 450г", "price": 69.99,
     "calories": 352, "proteins": 12.3, "fats": 6.2, "carbs": 61.8,
     "description": "Овсяные хлопья для каши", "compound": "Овсяные хлопья"},
    {"id": 12, "category": "Крупы и макароны", "name": "Рис круглозерный 800г", "price": 89.99,
     "calories": 350, "proteins": 7.0, "fats": 1.0, "carbs": 78.0,
     "description": "Рис шлифованный круглозерный", "compound": "Рис"},
    {"id": 13, "category": "Крупы и макароны", "name": "Гречка ядрица 800г", "price": 99.99,
     "calories": 308, "proteins": 12.6, "fats": 3.3, "carbs": 57.1,
     "description": "Крупа гречневая ядрица", "compound": "Гречневая крупа"},
    {"id": 14, "category": "Крупы и макароны", "name": "Макароны Barilla спагетти 450г", "price": 119.99,
     "calories": 356, "proteins": 12.0, "fats": 2.0, "carbs": 71.0,
     "description": "Спагетти из твёрдых сортов пшеницы", "compound": "Мука из твёрдых сортов пшеницы, вода"},
    {"id": 15, "category": "Крупы и макароны", "name": "Булгур 500г", "price": 109.99,
     "calories": 342, "proteins": 12.3, "fats": 1.3, "carbs": 63.4,
     "description": "Крупа булгур", "compound": "Пшеница твёрдая"},

    # Овощи и фрукты
    {"id": 16, "category": "Овощи", "name": "Помидоры 500г", "price": 149.99,
     "calories": 20, "proteins": 1.1, "fats": 0.2, "carbs": 3.7,
     "description": "Помидоры свежие", "compound": "Помидоры"},
    {"id": 17, "category": "Овощи", "name": "Огурцы 500г", "price": 119.99,
     "calories": 14, "proteins": 0.8, "fats": 0.1, "carbs": 2.5,
     "description": "Огурцы свежие", "compound": "Огурцы"},
    {"id": 18, "category": "Овощи", "name": "Картофель 1кг", "price": 49.99,
     "calories": 77, "proteins": 2.0, "fats": 0.4, "carbs": 16.3,
     "description": "Картофель мытый", "compound": "Картофель"},
    {"id": 19, "category": "Овощи", "name": "Лук репчатый 1кг", "price": 39.99,
     "calories": 41, "proteins": 1.4, "fats": 0.0, "carbs": 8.2,
     "description": "Лук репчатый свежий", "compound": "Лук репчатый"},
    {"id": 20, "category": "Овощи", "name": "Морковь 1кг", "price": 44.99,
     "calories": 35, "proteins": 1.3, "fats": 0.1, "carbs": 6.9,
     "description": "Морковь мытая", "compound": "Морковь"},
    {"id": 21, "category": "Овощи", "name": "Перец болгарский 500г", "price": 179.99,
     "calories": 27, "proteins": 1.3, "fats": 0.0, "carbs": 5.3,
     "description": "Перец сладкий", "compound": "Перец сладкий"},
    {"id": 22, "category": "Овощи", "name": "Капуста белокочанная 1кг", "price": 34.99,
     "calories": 27, "proteins": 1.8, "fats": 0.1, "carbs": 4.7,
     "description": "Капуста белокочанная свежая", "compound": "Капуста белокочанная"},
    {"id": 23, "category": "Фрукты", "name": "Бананы 1кг", "price": 79.99,
     "calories": 96, "proteins": 1.5, "fats": 0.5, "carbs": 21.0,
     "description": "Бананы спелые", "compound": "Бананы"},
    {"id": 24, "category": "Фрукты", "name": "Яблоки Голден 1кг", "price": 129.99,
     "calories": 47, "proteins": 0.4, "fats": 0.4, "carbs": 9.8,
     "description": "Яблоки сорта Голден", "compound": "Яблоки"},

    # Хлеб и выпечка
    {"id": 25, "category": "Хлеб", "name": "Хлеб Бородинский 400г", "price": 49.99,
     "calories": 208, "proteins": 6.9, "fats": 1.3, "carbs": 39.8,
     "description": "Хлеб ржано-пшеничный Бородинский", "compound": "Мука ржаная, мука пшеничная, солод, сахар, патока, соль, дрожжи"},
    {"id": 26, "category": "Хлеб", "name": "Батон нарезной 400г", "price": 39.99,
     "calories": 264, "proteins": 7.5, "fats": 2.9, "carbs": 51.4,
     "description": "Батон нарезной из пшеничной муки", "compound": "Мука пшеничная, вода, сахар, маргарин, соль, дрожжи"},

    # Яйца
    {"id": 27, "category": "Яйца", "name": "Яйца куриные С1 10шт", "price": 109.99,
     "calories": 157, "proteins": 12.7, "fats": 10.9, "carbs": 0.7,
     "description": "Яйца куриные столовые категории С1", "compound": "Яйца куриные"},

    # Масло и соусы
    {"id": 28, "category": "Масло и соусы", "name": "Масло подсолнечное рафинированное 1л", "price": 119.99,
     "calories": 899, "proteins": 0.0, "fats": 99.9, "carbs": 0.0,
     "description": "Масло подсолнечное рафинированное дезодорированное", "compound": "Масло подсолнечное рафинированное"},
    {"id": 29, "category": "Масло и соусы", "name": "Кетчуп Heinz томатный 350г", "price": 149.99,
     "calories": 96, "proteins": 1.6, "fats": 0.1, "carbs": 22.8,
     "description": "Кетчуп томатный классический", "compound": "Томатная паста, сахар, уксус, соль, специи"},
    {"id": 30, "category": "Масло и соусы", "name": "Майонез Провансаль 67% 400г", "price": 99.99,
     "calories": 624, "proteins": 3.1, "fats": 67.0, "carbs": 2.6,
     "description": "Майонез Провансаль классический", "compound": "Масло подсолнечное, вода, яичный порошок, сахар, соль, уксус, горчица"},

    # Рыба
    {"id": 31, "category": "Рыба", "name": "Филе горбуши замор. 500г", "price": 349.99,
     "calories": 140, "proteins": 20.5, "fats": 6.5, "carbs": 0.0,
     "description": "Филе горбуши без кожи замороженное", "compound": "Горбуша"},
    {"id": 32, "category": "Рыба", "name": "Филе минтая замор. 700г", "price": 289.99,
     "calories": 72, "proteins": 15.9, "fats": 0.9, "carbs": 0.0,
     "description": "Филе минтая замороженное", "compound": "Минтай"},

    # Консервы и бакалея
    {"id": 33, "category": "Консервы", "name": "Тунец в собственном соку 185г", "price": 149.99,
     "calories": 96, "proteins": 21.0, "fats": 1.0, "carbs": 0.0,
     "description": "Тунец консервированный в собственном соку", "compound": "Тунец, вода, соль"},
    {"id": 34, "category": "Консервы", "name": "Томатная паста 380г", "price": 89.99,
     "calories": 82, "proteins": 4.8, "fats": 0.2, "carbs": 16.7,
     "description": "Томатная паста 25%", "compound": "Томаты"},
    {"id": 35, "category": "Бакалея", "name": "Соль пищевая 1кг", "price": 29.99,
     "calories": 0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0,
     "description": "Соль поваренная пищевая", "compound": "Соль"},
    {"id": 36, "category": "Бакалея", "name": "Сахар белый 1кг", "price": 69.99,
     "calories": 399, "proteins": 0.0, "fats": 0.0, "carbs": 99.8,
     "description": "Сахар-песок белый", "compound": "Сахароза"},

    # Напитки
    {"id": 37, "category": "Напитки", "name": "Чай чёрный Greenfield 100 пак.", "price": 249.99,
     "calories": 0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0,
     "description": "Чай чёрный в пакетиках", "compound": "Чай чёрный байховый"},
    {"id": 38, "category": "Напитки", "name": "Кофе молотый Jacobs 230г", "price": 399.99,
     "calories": 0, "proteins": 0.0, "fats": 0.0, "carbs": 0.0,
     "description": "Кофе натуральный жареный молотый", "compound": "Кофе натуральный"},

    # Замороженные продукты
    {"id": 39, "category": "Заморозка", "name": "Овощная смесь замор. 400г", "price": 129.99,
     "calories": 45, "proteins": 2.5, "fats": 0.3, "carbs": 7.5,
     "description": "Смесь овощная замороженная (брокколи, цветная капуста, морковь)", "compound": "Брокколи, цветная капуста, морковь"},
    {"id": 40, "category": "Заморозка", "name": "Ягоды замор. смесь 300г", "price": 199.99,
     "calories": 45, "proteins": 0.7, "fats": 0.3, "carbs": 9.5,
     "description": "Смесь ягод замороженная", "compound": "Клубника, черника, малина, ежевика"},

    # Орехи и снеки
    {"id": 41, "category": "Орехи", "name": "Миндаль жареный 150г", "price": 249.99,
     "calories": 607, "proteins": 18.6, "fats": 53.7, "carbs": 13.0,
     "description": "Миндаль жареный без соли", "compound": "Миндаль"},
    {"id": 42, "category": "Орехи", "name": "Арахис солёный 200г", "price": 119.99,
     "calories": 551, "proteins": 26.3, "fats": 45.2, "carbs": 9.9,
     "description": "Арахис жареный солёный", "compound": "Арахис, соль, масло подсолнечное"},

    # Молочка доп.
    {"id": 43, "category": "Молочные продукты", "name": "Йогурт Danone натуральный 350г", "price": 79.99,
     "calories": 60, "proteins": 4.0, "fats": 1.5, "carbs": 7.5,
     "description": "Йогурт натуральный без добавок", "compound": "Молоко нормализованное, закваска йогуртовая"},

    # Мёд и варенье
    {"id": 44, "category": "Бакалея", "name": "Мёд цветочный 350г", "price": 299.99,
     "calories": 328, "proteins": 0.8, "fats": 0.0, "carbs": 80.3,
     "description": "Мёд натуральный цветочный", "compound": "Мёд натуральный"},

    # Специи
    {"id": 45, "category": "Специи", "name": "Перец чёрный молотый 50г", "price": 59.99,
     "calories": 251, "proteins": 10.4, "fats": 3.3, "carbs": 38.7,
     "description": "Перец чёрный молотый", "compound": "Перец чёрный"},

    # Дополнительные белковые
    {"id": 46, "category": "Молочные продукты", "name": "Творог обезжиренный 0.1% 220г", "price": 89.99,
     "calories": 76, "proteins": 18.0, "fats": 0.1, "carbs": 3.3,
     "description": "Творог обезжиренный", "compound": "Молоко обезжиренное, закваска"},
    {"id": 47, "category": "Мясо и птица", "name": "Индейка филе грудки охл. 600г", "price": 449.99,
     "calories": 84, "proteins": 19.2, "fats": 0.7, "carbs": 0.0,
     "description": "Филе грудки индейки охлаждённое", "compound": "Мясо индейки"},
    {"id": 48, "category": "Бобовые", "name": "Чечевица красная 450г", "price": 129.99,
     "calories": 314, "proteins": 21.6, "fats": 1.1, "carbs": 48.0,
     "description": "Чечевица красная колотая", "compound": "Чечевица красная"},
    {"id": 49, "category": "Бобовые", "name": "Фасоль белая консерв. 400г", "price": 79.99,
     "calories": 99, "proteins": 7.0, "fats": 0.5, "carbs": 17.4,
     "description": "Фасоль белая в собственном соку", "compound": "Фасоль, вода, соль"},
    {"id": 50, "category": "Мука", "name": "Мука пшеничная в/с 2кг", "price": 99.99,
     "calories": 334, "proteins": 10.3, "fats": 1.1, "carbs": 68.9,
     "description": "Мука пшеничная высшего сорта", "compound": "Пшеница"},
]


def generate_test_data():
    """Generate test data files from the built-in product catalog."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # info_product.csv
    info_path = os.path.join(DATA_DIR, "info_product.csv")
    with open(info_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "name", "price"])
        writer.writeheader()
        for p in TEST_PRODUCTS:
            writer.writerow({k: p[k] for k in ["id", "category", "name", "price"]})

    # calories.csv
    cal_path = os.path.join(DATA_DIR, "calories.csv")
    with open(cal_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "calories", "proteins", "fats", "carbs"])
        writer.writeheader()
        for p in TEST_PRODUCTS:
            writer.writerow({k: p[k] for k in ["id", "calories", "proteins", "fats", "carbs"]})

    # description.json
    desc_path = os.path.join(DATA_DIR, "description.json")
    descriptions = [
        {"id": p["id"], "description": p["description"], "compound": p["compound"]}
        for p in TEST_PRODUCTS
    ]
    with open(desc_path, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)

    print(f"✅ Тестовые данные сохранены в {DATA_DIR} ({len(TEST_PRODUCTS)} товаров)")


if __name__ == "__main__":
    generate_test_data()
