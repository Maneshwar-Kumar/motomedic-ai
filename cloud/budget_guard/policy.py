from decimal import Decimal

BUDGET_NAME = "MotoMedic lifetime INR800"
BUDGET_INR = Decimal("800")
STOP_INR = Decimal("640")


def should_stop(message):
    if message.get("budgetDisplayName") != BUDGET_NAME or message.get("currencyCode") != "INR":
        raise ValueError("Unexpected budget notification")
    amount = Decimal(str(message["budgetAmount"]))
    cost = Decimal(str(message["costAmount"]))
    if not amount.is_finite() or not cost.is_finite() or amount != BUDGET_INR or cost < 0:
        raise ValueError("Invalid budget amounts")
    return cost >= STOP_INR
