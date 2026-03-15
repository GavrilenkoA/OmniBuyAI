from pydantic import BaseModel


class Product(BaseModel):
    id: int
    category: str
    name: str
    price: float
    calories: float = 0.0
    proteins: float = 0.0
    fats: float = 0.0
    carbs: float = 0.0
    description: str = ""
    compound: str = ""


class CartItem(BaseModel):
    id: int
    name: str
    quantity: int
    price: float


class Meal(BaseModel):
    meal_type: str  # breakfast / lunch / dinner
    dishes: list[str]
    product_ids: list[int]


class DayPlan(BaseModel):
    day: int
    meals: list[Meal]


class MealPlan(BaseModel):
    days: list[DayPlan]


class NutritionSummary(BaseModel):
    total_calories: float
    total_proteins: float
    total_fats: float
    total_carbs: float
    per_person_per_day_calories: float
    per_person_per_day_proteins: float
    per_person_per_day_fats: float
    per_person_per_day_carbs: float
