from pydantic import BaseModel


class Product(BaseModel):
    internal_id: int
    title: str
    price: float
    old_price: float = 0.0
    discount: str = ""
    category: str = ""
    in_stock: bool = True
    rating: float = 0.0
    review_count: int = 0
    slug: str = ""
    description: str = ""
    weight: str = ""
    unit: str = ""
    image_url: str = ""
    brand: str = ""


class CartItem(BaseModel):
    internal_id: int
    title: str
    quantity: int
    price: float
