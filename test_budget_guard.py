import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location("budget_policy", Path(__file__).parent / "cloud/budget_guard/policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class BudgetGuardTests(unittest.TestCase):
    def message(self, cost):
        return {"budgetDisplayName": "MotoMedic lifetime INR800", "currencyCode": "INR", "budgetAmount": 800, "costAmount": cost}
    def test_boundary(self):
        self.assertFalse(policy.should_stop(self.message("639.99")))
        self.assertTrue(policy.should_stop(self.message("640")))
        self.assertTrue(policy.should_stop(self.message("900")))
    def test_other_budgets_rejected(self):
        for key, value in [("budgetDisplayName", "Other project"), ("currencyCode", "USD"), ("budgetAmount", 1000)]:
            message = self.message(1000)
            message[key] = value
            with self.assertRaises(ValueError): policy.should_stop(message)
    def test_invalid_values_rejected(self):
        for cost in ["NaN", "Infinity", "-1"]:
            with self.assertRaises(ValueError): policy.should_stop(self.message(cost))
if __name__ == "__main__": unittest.main()
