from decimal import Decimal


def required_margin(order_size: Decimal, price: Decimal, leverage: int) -> Decimal:
    if leverage <= 0:
        raise ValueError("Leverage must be greater than zero")
    return (order_size * price) / Decimal(leverage)
