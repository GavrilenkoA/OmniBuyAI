from .config import DAILY_CALORIES, DAILY_PROTEINS, DAILY_FATS, DAILY_CARBS
from .models import NutritionSummary, Product


def calculate_nutrition(
    products_with_qty: list[tuple[Product, int]],
    days: int,
    people: int,
) -> NutritionSummary:
    total_cal = sum(p.calories * qty for p, qty in products_with_qty)
    total_prot = sum(p.proteins * qty for p, qty in products_with_qty)
    total_fat = sum(p.fats * qty for p, qty in products_with_qty)
    total_carb = sum(p.carbs * qty for p, qty in products_with_qty)

    divisor = max(days * people, 1)

    return NutritionSummary(
        total_calories=round(total_cal, 1),
        total_proteins=round(total_prot, 1),
        total_fats=round(total_fat, 1),
        total_carbs=round(total_carb, 1),
        per_person_per_day_calories=round(total_cal / divisor, 1),
        per_person_per_day_proteins=round(total_prot / divisor, 1),
        per_person_per_day_fats=round(total_fat / divisor, 1),
        per_person_per_day_carbs=round(total_carb / divisor, 1),
    )


def check_balance(nutrition: NutritionSummary) -> dict:
    ppd_cal = nutrition.per_person_per_day_calories
    ppd_prot = nutrition.per_person_per_day_proteins
    ppd_fat = nutrition.per_person_per_day_fats
    ppd_carb = nutrition.per_person_per_day_carbs

    issues = []

    if ppd_cal < DAILY_CALORIES * 0.8:
        issues.append(f"Мало калорий: {ppd_cal:.0f} (норма ~{DAILY_CALORIES})")
    elif ppd_cal > DAILY_CALORIES * 1.2:
        issues.append(f"Много калорий: {ppd_cal:.0f} (норма ~{DAILY_CALORIES})")

    if ppd_prot < DAILY_PROTEINS[0]:
        issues.append(f"Мало белка: {ppd_prot:.0f}г (норма {DAILY_PROTEINS[0]}-{DAILY_PROTEINS[1]}г)")
    elif ppd_prot > DAILY_PROTEINS[1]:
        issues.append(f"Много белка: {ppd_prot:.0f}г (норма {DAILY_PROTEINS[0]}-{DAILY_PROTEINS[1]}г)")

    if ppd_fat < DAILY_FATS[0]:
        issues.append(f"Мало жиров: {ppd_fat:.0f}г (норма {DAILY_FATS[0]}-{DAILY_FATS[1]}г)")
    elif ppd_fat > DAILY_FATS[1]:
        issues.append(f"Много жиров: {ppd_fat:.0f}г (норма {DAILY_FATS[0]}-{DAILY_FATS[1]}г)")

    if ppd_carb < DAILY_CARBS[0]:
        issues.append(f"Мало углеводов: {ppd_carb:.0f}г (норма {DAILY_CARBS[0]}-{DAILY_CARBS[1]}г)")
    elif ppd_carb > DAILY_CARBS[1]:
        issues.append(f"Много углеводов: {ppd_carb:.0f}г (норма {DAILY_CARBS[0]}-{DAILY_CARBS[1]}г)")

    return {
        "balanced": len(issues) == 0,
        "issues": issues,
    }
