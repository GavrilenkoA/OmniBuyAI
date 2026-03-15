from collections import defaultdict

from .models import CartItem, Product


def build_cart(
    product_quantities: list[tuple[int, int]],
    products: list[Product],
) -> list[CartItem]:
    """Aggregate product selections into a deduplicated cart.

    Args:
        product_quantities: list of (internal_id, quantity) pairs
        products: full product catalog
    """
    product_map = {p.internal_id: p for p in products}
    aggregated: dict[int, int] = defaultdict(int)

    for pid, qty in product_quantities:
        aggregated[pid] += qty

    cart = []
    for pid, qty in sorted(aggregated.items()):
        p = product_map.get(pid)
        if p:
            cart.append(CartItem(internal_id=pid, title=p.title, quantity=qty, price=p.price))

    return cart
