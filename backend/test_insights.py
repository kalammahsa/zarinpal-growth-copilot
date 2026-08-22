"""Integration tests for insights generated from real merchant M31 data."""

import unittest

from analytics import MerchantAnalytics
from insight_engine import InsightEngine


class InsightEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merchant_id = "M31"
        cls.engine = InsightEngine(MerchantAnalytics())

    def test_top_insight_contract(self) -> None:
        insights = self.engine.get_top_insights(self.merchant_id)
        self.assertGreater(len(insights), 0)
        self.assertLessEqual(len(insights), 3)
        expected = {
            "type", "title", "problem", "impact", "cause",
            "reason", "action", "confidence", "evidence", "source_metrics",
            "calculation",
        }
        for insight in insights:
            self.assertEqual(set(insight), expected)
            self.assertTrue(insight["title"])
            self.assertIsInstance(insight["evidence"], dict)
            self.assertTrue({
                "metric", "formula", "current_period", "baseline", "sample_size",
                "filters", "explanation", "result", "comparison",
            }.issubset(insight["calculation"]))
            self.assertIsInstance(insight["calculation"]["filters"], list)
            self.assertEqual(insight["source_metrics"], insight["evidence"])
            self.assertEqual(insight["reason"], insight["cause"])
            self.assertTrue(insight["calculation"]["explanation"])

    def test_opportunity_score_uses_observed_payment_amounts(self) -> None:
        score = self.engine.get_merchant_opportunity_score(self.merchant_id)
        source = score["source_metrics"]
        expected_total = source["verified_gmv"] + source["at_risk_gmv"]
        expected_value = round(
            source["at_risk_gmv"] / expected_total * 100, 2
        ) if expected_total else 0.0

        self.assertEqual(source["total_observed_gmv"], expected_total)
        self.assertEqual(score["value"], expected_value)
        self.assertGreaterEqual(score["value"], 0.0)
        self.assertLessEqual(score["value"], 100.0)
        self.assertEqual(
            score["calculation"]["numerator"], source["at_risk_gmv"]
        )
        self.assertEqual(
            score["calculation"]["denominator"], source["total_observed_gmv"]
        )

    def test_conversion_uses_real_baseline(self) -> None:
        insight = self.engine.detect_conversion_drop(self.merchant_id)
        self.assertIsNotNone(insight)
        evidence = insight["evidence"]
        self.assertLess(
            evidence["merchant_conversion_rate"],
            evidence["portfolio_baseline_rate"],
        )

    def test_at_risk_wording_is_not_lost_revenue(self) -> None:
        insight = self.engine.detect_revenue_leakage(self.merchant_id)
        self.assertIsNotNone(insight)
        text = " ".join(str(value) for value in insight.values()).lower()
        self.assertIn("مبلغ در معرض ریسک", text)
        self.assertNotIn("lost revenue", text)

    def test_retry_and_psp_evidence(self) -> None:
        retry = self.engine.detect_retry_opportunity(self.merchant_id)
        psp = self.engine.detect_psp_problem(self.merchant_id)
        self.assertIsNotNone(retry)
        self.assertGreater(retry["evidence"]["failed_sessions"], 0)
        self.assertIsNotNone(psp)
        self.assertGreaterEqual(psp["evidence"]["transaction_count"], 30)
        self.assertGreater(
            psp["evidence"]["merchant_psp_average_success_rate"],
            psp["evidence"]["psp_success_rate"],
        )

    def test_customer_retention_is_evidence_based(self) -> None:
        insight = self.engine.detect_customer_retention_opportunity(self.merchant_id)
        self.assertIsNotNone(insight)
        self.assertGreater(
            insight["evidence"]["repeat_customer_revenue_share"],
            insight["evidence"]["repeat_rate"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
