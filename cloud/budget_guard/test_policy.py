import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location("budget_policy", Path(__file__).parent / "policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class BudgetGuardTests(unittest.TestCase):
    def message(self, cost):
        return {"budgetDisplayName": "MotoMedic lifetime INR800", "currencyCode": "INR", "budgetAmount": 800, "costAmount": cost}
    def test_boundary(self):
        self.assertFalse(policy.should_stop(self.message("639.99")))
        self.assertTrue(policy.should_stop(self.message("640")))
        self.assertTrue(policy.should_stop(self.message("900")))
    def test_authorized_expansion_configuration(self):
        # The current recorded budget (cloud/deployment_status.json): INR3,120, guard INR2,960.
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {"BUDGET_DISPLAY_NAME": "MotoMedic lifetime INR3120", "BUDGET_INR": "3120", "STOP_INR": "2960"}):
            expanded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(expanded)
        message = {"budgetDisplayName": "MotoMedic lifetime INR3120", "currencyCode": "INR", "budgetAmount": 3120, "costAmount": "2959.99"}
        self.assertFalse(expanded.should_stop(message))
        message["costAmount"] = "2960"
        self.assertTrue(expanded.should_stop(message))
        with self.assertRaises(ValueError): expanded.should_stop(self.message(640))
    def test_other_budgets_rejected(self):
        for key, value in [("budgetDisplayName", "Other project"), ("currencyCode", "USD"), ("budgetAmount", 1000)]:
            message = self.message(1000)
            message[key] = value
            with self.assertRaises(ValueError): policy.should_stop(message)
    def test_invalid_values_rejected(self):
        for cost in ["NaN", "Infinity", "-1"]:
            with self.assertRaises(ValueError): policy.should_stop(self.message(cost))
if __name__ == "__main__": unittest.main()
