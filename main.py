import os
import sys

from omnibuyai.agent import GroceryAgent
from omnibuyai.scraper import generate_test_data
from omnibuyai.config import DATA_DIR


def print_results(result: dict):
    params = result["params"]
    days = params.get("days", 3)
    people = params.get("people", 2)

    print("\n" + "=" * 60)
    print("📋 ПЛАН ПИТАНИЯ")
    print("=" * 60)

    for day_plan in result["meal_plan"]:
        print(f"\n--- День {day_plan['day']} ---")
        for meal in day_plan["meals"]:
            meal_name = {
                "breakfast": "🌅 Завтрак",
                "lunch": "☀️ Обед",
                "dinner": "🌙 Ужин",
            }.get(meal["meal_type"], meal["meal_type"])
            print(f"  {meal_name}: {', '.join(meal['dishes'])}")

    print("\n" + "=" * 60)
    print("🛒 КОРЗИНА")
    print("=" * 60)

    for item in result["cart"]:
        total = item["price"] * item["quantity"]
        print(f"  [{item['id']:3d}] {item['name']} x{item['quantity']} — {total:.2f}₽")

    print(f"\n  💰 ИТОГО: {result['total_price']:.2f}₽")

    print("\n" + "=" * 60)
    print("⚖️  КБЖУ (на человека в день)")
    print("=" * 60)
    n = result["nutrition"]
    print(f"  Калории:  {n['per_person_per_day_calories']:.0f} ккал")
    print(f"  Белки:    {n['per_person_per_day_proteins']:.0f} г")
    print(f"  Жиры:     {n['per_person_per_day_fats']:.0f} г")
    print(f"  Углеводы: {n['per_person_per_day_carbs']:.0f} г")

    balance = result["balance"]
    if balance["balanced"]:
        print("\n  ✅ Питание сбалансировано!")
    else:
        print("\n  ⚠️  Замечания:")
        for issue in balance["issues"]:
            print(f"    - {issue}")

    print("\n" + "=" * 60)
    print("📦 СПИСОК ID ДЛЯ КОРЗИНЫ API")
    print("=" * 60)
    cart_api = [{"id": item["id"], "quantity": item["quantity"]} for item in result["cart"]]
    print(f"  {cart_api}")
    print()


def main():
    # Generate test data if not present
    if not os.path.exists(os.path.join(DATA_DIR, "info_product.csv")):
        print("📥 Генерация тестовых данных...")
        generate_test_data()

    # Get user query
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("🔍 Введите запрос (например: 'Собери продукты на 3 дня для 2 человек'): ")

    if not query.strip():
        query = "Собери продукты на 3 дня для 2 человек, сбалансированное питание"

    print(f"\n🚀 Запрос: {query}\n")

    agent = GroceryAgent()
    result = agent.run(query)
    print_results(result)


if __name__ == "__main__":
    main()
