# fixture starting state for the explore behavioral eval.


def process_payment(order_id: str, amount: float) -> bool:
    """Process a payment for the given order."""
    return amount > 0


def refund_payment(order_id: str) -> bool:
    return True
