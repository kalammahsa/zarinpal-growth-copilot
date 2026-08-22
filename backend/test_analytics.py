"""Small integration test using merchant M31 from the real dataset."""

import unittest

from analytics import MerchantAnalytics


class MerchantAnalyticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merchant_id = "M31"
        cls.analytics = MerchantAnalytics()

    def test_business_overview(self) -> None:
        result = self.analytics.get_business_overview(self.merchant_id)
        self.assertGreater(result["total_sessions"], 0)
        self.assertEqual(
            result["successful_payments"] + result["failed_sessions"]
            + self.analytics.get_payment_health(self.merchant_id)[
                "paid_not_verified_count"
            ],
            result["total_sessions"],
        )
        self.assertGreaterEqual(result["verified_gmv"], 0)
        self.assertGreaterEqual(result["at_risk_gmv"], 0)

    def test_payment_health(self) -> None:
        result = self.analytics.get_payment_health(self.merchant_id)
        self.assertEqual(
            sum(result["status_distribution"].values()),
            self.analytics.get_business_overview(self.merchant_id)["total_sessions"],
        )
        for metric in (
            "retry_rate",
            "retry_success_rate",
            "first_attempt_success_rate",
        ):
            self.assertGreaterEqual(result[metric], 0.0)
            self.assertLessEqual(result[metric], 100.0)

    def test_data_period_covers_merchant_sessions(self) -> None:
        result = self.analytics.get_data_period(self.merchant_id)
        self.assertTrue(result["start_date"])
        self.assertTrue(result["end_date"])
        self.assertLessEqual(result["start_date"], result["end_date"])
        self.assertEqual(
            result["session_count"],
            self.analytics.get_business_overview(self.merchant_id)["total_sessions"],
        )

    def test_revenue_analysis(self) -> None:
        result = self.analytics.get_revenue_analysis(self.merchant_id)
        self.assertTrue(result["gmv_by_day"])
        self.assertTrue(result["successful_payment_trend"])
        self.assertTrue(result["failed_payment_trend"])
        self.assertTrue(result["top_categories_by_gmv"])

    def test_customer_analysis(self) -> None:
        result = self.analytics.get_customer_analysis(self.merchant_id)
        self.assertGreater(result["unique_customers"], 0)
        self.assertLessEqual(result["repeat_customers"], result["unique_customers"])
        self.assertGreaterEqual(result["repeat_rate"], 0.0)
        self.assertLessEqual(result["repeat_customer_revenue_share"], 100.0)

    def test_psp_analysis(self) -> None:
        result = self.analytics.get_psp_analysis(self.merchant_id)
        self.assertTrue(result)
        for psp in result:
            self.assertGreater(psp["transaction_count"], 0)
            self.assertAlmostEqual(
                psp["success_rate"] + psp["failure_rate"], 100.0, places=1
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
