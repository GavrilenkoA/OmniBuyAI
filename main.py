import logging
import sys

from omnibuyai import GroceryAgent

logging.basicConfig(level=logging.INFO, format="%(message)s")


def print_results(result: dict):
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

    # cart is {internal_id: quantity} — need product info for display
    agent = GroceryAgent()
    agent._ensure_loaded()
    product_map = {p.internal_id: p for p in agent.products}

    for pid, qty in result["cart"].items():
        p = product_map.get(pid)
        name = p.title if p else f"ID:{pid}"
        price = p.price if p else 0
        print(f"  [{pid}] {name} x{qty} — {price * qty:.2f}₽")

    print(f"\n  💰 ИТОГО: {result['total_price']:.2f}₽")

    print("\n" + "=" * 60)
    print("📦 КОРЗИНА ДЛЯ API")
    print("=" * 60)
    print(f"  {result['cart']}")
    print()


def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("🔍 Введите запрос: ")

    if not query.strip():
        print("Пустой запрос.")
        return

    print(f"\n🚀 Запрос: {query}\n")

    agent = GroceryAgent()

    # Clarification loop
    conversation_history: list[dict] = []

    while True:
        result = agent.clarify(query, conversation_history or None)

        if result["status"] == "ready":
            params = result["params"]
            break

        question = result["question"]
        print(f"\n💬 {question}")
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": question})

        answer = input("👤 ")
        if not answer.strip():
            params = {"days": 3, "people": 2, "preferences": "сбалансированное питание"}
            break

        query = answer
        conversation_history.append({"role": "user", "content": answer})

    result = agent.execute(params)
    print_results(result)


if __name__ == "__main__":
    main()
