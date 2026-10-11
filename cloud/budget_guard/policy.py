from decimal import Decimal
import os

BUDGET_NAME = os.environ.get("BUDGET_DISPLAY_NAME", "MotoMedic lifetime INR800")
BUDGET_INR = Decimal(os.environ.get("BUDGET_INR", "800"))
STOP_INR = Decimal(os.environ.get("STOP_INR", "640"))
if not (BUDGET_INR.is_finite() and STOP_INR.is_finite() and 0 < STOP_INR < BUDGET_INR):
    raise ValueError("Invalid configured budget stop")


def should_stop(message):
    if message.get("budgetDisplayName") != BUDGET_NAME or message.get("currencyCode") != "INR":
        raise ValueError("Unexpected budget notification")
    amount = Decimal(str(message["budgetAmount"]))
    cost = Decimal(str(message["costAmount"]))
    if not amount.is_finite() or not cost.is_finite() or amount != BUDGET_INR or cost < 0:
        raise ValueError("Invalid budget amounts")
    return cost >= STOP_INR
