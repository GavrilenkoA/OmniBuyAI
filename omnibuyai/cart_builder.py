from collections import defaultdict

from .models import CartItem, Product


def build_cart(
    product_quantities: list[tuple[int, int]],
    products: list[Product],
) -> list[CartItem]:
    """Aggregate product selections into a deduplicated cart.

    Args:
        product_quantities: list of (product_id, quantity) pairs
        products: full product catalog
    """
    product_map = {p.id: p for p in products}
    aggregated: dict[int, int] = defaultdict(int)

    for pid, qty in product_quantities:
        aggregated[pid] += qty

    cart = []
    for pid, qty in sorted(aggregated.items()):
        p = product_map.get(pid)
        if p:
            cart.append(CartItem(id=pid, name=p.name, quantity=qty, price=p.price))

    return cart
