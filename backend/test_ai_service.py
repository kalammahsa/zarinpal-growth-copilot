"""Unit tests for the AI explanation boundary."""

import json
import os
import unittest
from unittest.mock import patch

from ai_service import AIBusinessAdvisor, confidence_from_insights


class _FakeResponse:
    output_text = "  بر اساس داده‌های موجود، نرخ موفقیت پرداخت نیازمند توجه است.  "


class _FakeResponses:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeResponse()


class _FakeClient:
    def __init__(self) -> None:
        self.responses = _FakeResponses()


class AIBusinessAdvisorTest(unittest.TestCase):
    def test_missing_api_key_uses_existing_insights_without_a_client(self) -> None:
        insights = [
            {
                "title": "افت تبدیل",
                "problem": "نرخ تبدیل کاهش یافته است.",
                "impact": "بخشی از فروش در معرض ریسک است.",
                "action": "مسیر پرداخت را بررسی کنید.",
                "confidence": "high",
            }
        ]

        with patch.dict(os.environ, {}, clear=True):
            advisor = AIBusinessAdvisor()
            answer = advisor.answer("چرا فروش کم شده؟", {}, insights)

        self.assertTrue(advisor.is_demo_mode)
        self.assertIn(insights[0]["title"], answer)
        self.assertIn(insights[0]["action"], answer)

    def test_sends_only_structured_existing_results(self) -> None:
        client = _FakeClient()
        advisor = AIBusinessAdvisor(client=client, model="test-model")
        analytics = {"overview": {"conversion_rate": 72.5}}
        insights = [{"type": "conversion_drop", "confidence": "high"}]

        answer = advisor.answer("چرا فروش من کم شده؟", analytics, insights)

        self.assertEqual(
            answer, "بر اساس داده‌های موجود، نرخ موفقیت پرداخت نیازمند توجه است."
        )
        sent = json.loads(client.responses.kwargs["input"])
        self.assertEqual(sent["analytics"], analytics)
        self.assertEqual(sent["insights"], insights)
        self.assertEqual(sent["question"], "چرا فروش من کم شده؟")
        self.assertFalse(client.responses.kwargs["store"])
        self.assertIn("هیچ شاخص، عدد یا علت جدیدی محاسبه یا حدس نزنید", client.responses.kwargs["instructions"])

    def test_confidence_is_derived_from_existing_insights(self) -> None:
        self.assertEqual(confidence_from_insights([]), "low")
        self.assertEqual(
            confidence_from_insights(
                [{"confidence": "high"}, {"confidence": "medium"}]
            ),
            "medium",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
