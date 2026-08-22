"""Turn deterministic merchant analytics into evidence-backed business insights."""

from math import sqrt
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from .analytics import MerchantAnalytics
except ImportError:
    from analytics import MerchantAnalytics


Insight = Dict[str, Any]
RankedInsight = Tuple[Insight, float, int, int]


class InsightEngine:
    """Detect and rank business opportunities without inventing causal claims."""

    _CONFIDENCE_RANK = {"low": 1, "medium": 2, "high": 3}

    def __init__(self, analytics: MerchantAnalytics) -> None:
        self.analytics = analytics
        sessions = analytics._sessions
        verified = sessions["session_status"] == "Verified"

        # Portfolio benchmarks are calculated from the real prepared dataset once.
        self._portfolio_conversion_rate = round(float(verified.mean() * 100), 2)
        merchant_at_risk = (
            sessions.assign(at_risk_amount=sessions["amount"].where(~verified, 0))
            .groupby("merchant_key")["at_risk_amount"]
            .sum()
        )
        self._high_at_risk_threshold = float(merchant_at_risk.quantile(0.75))

    @staticmethod
    def _insight(
        insight_type: str,
        title: str,
        problem: str,
        impact: str,
        cause: str,
        action: str,
        confidence: str,
        evidence: Dict[str, Any],
        calculation: Dict[str, Any],
    ) -> Insight:
        calculation_trace = dict(calculation)
        metric = str(calculation_trace.get("metric", "")).strip()
        formula = str(calculation_trace.get("formula", "")).strip()
        current = str(calculation_trace.get("current_period", "")).strip()
        baseline = str(calculation_trace.get("baseline", "")).strip()
        calculation_trace["explanation"] = (
            f"{metric} با فرمول «{formula}» محاسبه شده است. "
            f"نتیجه فعلی {current} و مبنای مقایسه {baseline} است."
        )
        calculation_trace["result"] = current
        calculation_trace["comparison"] = baseline

        return {
            "type": insight_type,
            "title": title,
            "problem": problem,
            "impact": impact,
            "cause": cause,
            "reason": cause,
            "action": action,
            "confidence": confidence,
            "evidence": evidence,
            "source_metrics": dict(evidence),
            "calculation": calculation_trace,
        }

    def get_merchant_opportunity_score(self, merchant_id: str) -> Dict[str, Any]:
        """Measure the observed share of payment amount that is not yet verified.

        The score contains no model output or arbitrary weighting. A higher value
        means a larger share of the merchant's observed payment amount is attached
        to sessions whose final status is not Verified.
        """
        overview = self.analytics.get_business_overview(merchant_id)
        verified_gmv = int(overview["verified_gmv"])
        at_risk_gmv = int(overview["at_risk_gmv"])
        total_observed_gmv = verified_gmv + at_risk_gmv
        value = (
            round((at_risk_gmv / total_observed_gmv) * 100, 2)
            if total_observed_gmv
            else 0.0
        )

        return {
            "value": value,
            "unit": "percent",
            "meaning": (
                "سهم مبلغ پرداخت‌های غیر Verified از کل مبلغ پرداخت‌های مشاهده‌شده؛ "
                "این مقدار درآمد ازدست‌رفته یا درآمد تضمین‌شده نیست."
            ),
            "calculation": {
                "metric": "امتیاز فرصت پذیرنده",
                "formula": (
                    "مبلغ پرداخت‌های غیر Verified ÷ کل مبلغ پرداخت‌های مشاهده‌شده × ۱۰۰"
                ),
                "explanation": (
                    f"{at_risk_gmv:,} ریال مبلغ در معرض ریسک بر "
                    f"{total_observed_gmv:,} ریال کل مبلغ مشاهده‌شده تقسیم شده است."
                ),
                "numerator": at_risk_gmv,
                "denominator": total_observed_gmv,
                "result": value,
            },
            "source_metrics": {
                "verified_gmv": verified_gmv,
                "at_risk_gmv": at_risk_gmv,
                "total_observed_gmv": total_observed_gmv,
                "total_sessions": int(overview["total_sessions"]),
            },
        }

    @staticmethod
    def _comparison_confidence(
        successes: int, total: int, baseline_rate: float
    ) -> str:
        """Grade confidence from the binomial distance to an observed baseline."""
        if total == 0 or baseline_rate <= 0 or baseline_rate >= 100:
            return "low"
        probability = baseline_rate / 100
        standard_error = sqrt(probability * (1 - probability) / total)
        if standard_error == 0:
            return "low"
        z_score = ((successes / total) - probability) / standard_error
        if z_score <= -2.576:
            return "high"
        if z_score <= -1.96:
            return "medium"
        return "low"

    def detect_conversion_drop(self, merchant_id: str) -> Optional[Insight]:
        overview = self.analytics.get_business_overview(merchant_id)
        merchant_rate = float(overview["conversion_rate"])
        baseline = self._portfolio_conversion_rate
        if merchant_rate >= baseline:
            return None

        confidence = self._comparison_confidence(
            int(overview["successful_payments"]),
            int(overview["total_sessions"]),
            baseline,
        )
        return self._insight(
            "conversion_drop",
            "نرخ موفقیت پرداخت کاهش یافته",
            "بخشی از پرداخت‌ها به نتیجه موفق نرسیده‌اند",
            f"{overview['at_risk_gmv']:,} ریال مبلغ در sessionهای غیر Verified قرار دارد",
            "داده‌ها علت قطعی را مشخص نمی‌کنند؛ نرخ موفقیت از خط مبنای کل پایین‌تر است",
            "بررسی مسیر پرداخت و PSP",
            confidence,
            {
                "merchant_conversion_rate": merchant_rate,
                "portfolio_baseline_rate": baseline,
                "conversion_gap_percentage_points": round(baseline - merchant_rate, 2),
                "at_risk_gmv": int(overview["at_risk_gmv"]),
                "total_sessions": int(overview["total_sessions"]),
            },
            {
                "metric": "نرخ موفقیت پرداخت",
                "formula": "تعداد پرداخت‌های موفق ÷ تعداد کل پرداخت‌ها × ۱۰۰",
                "current_period": f"{merchant_rate}%",
                "baseline": f"{baseline}% میانگین کل پذیرندگان",
                "sample_size": f"{int(overview['total_sessions']):,} پرداخت",
                "filters": [
                    f"پذیرنده: {merchant_id}",
                    "هر خرید فقط یک‌بار شمرده شده است",
                    "فقط وضعیت Verified به‌عنوان پرداخت موفق شمرده شده است",
                ],
            },
        )

    def detect_revenue_leakage(self, merchant_id: str) -> Optional[Insight]:
        overview = self.analytics.get_business_overview(merchant_id)
        at_risk = int(overview["at_risk_gmv"])
        if at_risk <= self._high_at_risk_threshold:
            return None

        return self._insight(
            "revenue_leakage",
            "مبلغ قابل توجهی در معرض ریسک است",
            "حجم مبلغ sessionهای غیر Verified نسبت به بیشتر پذیرندگان بالا است",
            f"{at_risk:,} ریال مبلغ در معرض ریسک قرار دارد",
            "این مبلغ از sessionهای غیر Verified محاسبه شده و درآمد از دست‌رفته نیست",
            "اولویت‌بندی بررسی sessionهای با مبلغ بالا و وضعیت غیر Verified",
            "high",
            {
                "at_risk_gmv": at_risk,
                "portfolio_75th_percentile_at_risk_gmv": int(
                    self._high_at_risk_threshold
                ),
                "benchmark": "portfolio_75th_percentile",
            },
            {
                "metric": "مبلغ در معرض ریسک",
                "formula": "جمع مبلغ پرداخت‌هایی که وضعیت آن‌ها Verified نیست",
                "current_period": f"{at_risk:,} ریال",
                "baseline": f"{int(self._high_at_risk_threshold):,} ریال؛ مرز ۲۵٪ بالای پذیرندگان",
                "sample_size": f"{int(overview['total_sessions']):,} پرداخت",
                "filters": [
                    f"پذیرنده: {merchant_id}",
                    "هر خرید فقط یک‌بار شمرده شده است",
                    "وضعیت پرداخت برابر Verified نیست",
                ],
            },
        )

    def detect_retry_opportunity(self, merchant_id: str) -> Optional[Insight]:
        overview = self.analytics.get_business_overview(merchant_id)
        health = self.analytics.get_payment_health(merchant_id)
        failed = int(overview["failed_sessions"])
        recovery_rate = float(health["retry_success_rate"])
        if failed == 0 or recovery_rate <= 0:
            return None

        # This is a data-derived potential, not a promise of recovered revenue.
        recoverable_sessions = round(failed * recovery_rate / 100)
        potential_amount = round(
            recoverable_sessions * float(overview["average_successful_payment"])
        )
        retry_sample_size = int(
            self.analytics._merchant_sessions(merchant_id)["has_retry"].sum()
        )
        return self._insight(
            "retry_opportunity",
            "فرصت بازیابی پرداخت با تلاش مجدد وجود دارد",
            "بخشی از پرداخت‌های ناموفق قابلیت بازیابی دارند",
            f"بر اساس نرخ بازیابی فعلی، حدود {recoverable_sessions:,} session ظرفیت بازیابی دارد",
            "sessionهای دارای retry در داده واقعی نرخ موفقیت قابل اندازه‌گیری داشته‌اند",
            "طراحی پیام و مسیر تلاش مجدد برای پرداخت‌های ناموفق",
            "medium",
            {
                "failed_sessions": failed,
                "observed_retry_success_rate": recovery_rate,
                "estimated_recoverable_sessions": recoverable_sessions,
                "estimated_at_risk_gmv_opportunity": potential_amount,
                "estimate_basis": "failed_sessions × observed retry success rate",
            },
            {
                "metric": "ظرفیت بازیابی با تلاش دوباره",
                "formula": "تعداد پرداخت‌های ناموفق × نرخ موفقیت واقعی پرداخت‌های دارای تلاش دوباره",
                "current_period": f"حدود {recoverable_sessions:,} پرداخت؛ برآورد مبلغ {potential_amount:,} ریال",
                "baseline": f"نرخ بازیابی مشاهده‌شده: {recovery_rate}%",
                "sample_size": f"{retry_sample_size:,} پرداخت دارای تلاش دوباره",
                "filters": [
                    f"پذیرنده: {merchant_id}",
                    "پرداخت نهایی با وضعیت Failed",
                    "پرداخت دارای بیش از یک تلاش برای محاسبه نرخ بازیابی",
                ],
            },
        )

    def detect_psp_problem(self, merchant_id: str) -> Optional[Insight]:
        psp_rows = self.analytics.get_psp_analysis(merchant_id)
        total = sum(int(row["transaction_count"]) for row in psp_rows)
        if total == 0:
            return None

        successes = sum(
            round(int(row["transaction_count"]) * float(row["success_rate"]) / 100)
            for row in psp_rows
        )
        merchant_average = successes / total
        candidates: List[Tuple[float, Dict[str, Any]]] = []

        for row in psp_rows:
            sample = int(row["transaction_count"])
            rate = float(row["success_rate"]) / 100
            # A conventional minimum plus expected-count checks avoids small samples.
            enough_sample = (
                sample >= 30
                and sample * merchant_average >= 5
                and sample * (1 - merchant_average) >= 5
            )
            if not enough_sample or rate >= merchant_average:
                continue
            standard_error = sqrt(merchant_average * (1 - merchant_average) / sample)
            if standard_error == 0:
                continue
            z_score = (rate - merchant_average) / standard_error
            # Only report a PSP whose observed rate is below the 95% boundary.
            if z_score <= -1.96:
                candidates.append((z_score, row))

        if not candidates:
            return None
        z_score, worst = min(candidates, key=lambda item: (item[0], item[1]["psp_code"]))
        confidence = "high" if z_score <= -2.576 else "medium"
        merchant_average_percent = round(merchant_average * 100, 2)
        gap = round(merchant_average_percent - float(worst["success_rate"]), 2)

        return self._insight(
            "psp_problem",
            "نرخ موفقیت یک PSP پایین‌تر از میانگین پذیرنده است",
            f"نرخ موفقیت {worst['psp_code']} به‌طور معناداری پایین‌تر مشاهده شده است",
            f"اختلاف نرخ موفقیت این PSP با میانگین پذیرنده {gap} واحد درصد است",
            "داده‌ها فقط اختلاف عملکرد را نشان می‌دهند و علت فنی را مشخص نمی‌کنند",
            "بررسی فنی مسیر این PSP و مقایسه مسیریابی با PSPهای دیگر",
            confidence,
            {
                "psp_code": worst["psp_code"],
                "transaction_count": int(worst["transaction_count"]),
                "psp_success_rate": float(worst["success_rate"]),
                "merchant_psp_average_success_rate": merchant_average_percent,
                "gap_percentage_points": gap,
                "z_score": round(z_score, 2),
                "significance_level": 0.05,
            },
            {
                "metric": "نرخ موفقیت مسیر پرداخت",
                "formula": "تعداد تلاش‌های Verified در این مسیر ÷ کل تلاش‌های ارسال‌شده به این مسیر × ۱۰۰",
                "current_period": f"{float(worst['success_rate'])}% برای {worst['psp_code']}",
                "baseline": f"{merchant_average_percent}% میانگین همه مسیرهای این پذیرنده",
                "sample_size": f"{int(worst['transaction_count']):,} تلاش پرداخت",
                "filters": [
                    f"پذیرنده: {merchant_id}",
                    f"مسیر پرداخت: {worst['psp_code']}",
                    "فقط تلاش‌های دارای psp_code",
                    "حداقل ۳۰ تلاش و اختلاف معنادار در سطح ۹۵٪",
                ],
            },
        )

    def detect_customer_retention_opportunity(
        self, merchant_id: str
    ) -> Optional[Insight]:
        customers = self.analytics.get_customer_analysis(merchant_id)
        repeat_count = int(customers["repeat_customers"])
        repeat_rate = float(customers["repeat_rate"])
        revenue_share = float(customers["repeat_customer_revenue_share"])
        if repeat_count == 0 or revenue_share <= repeat_rate:
            return None

        overview = self.analytics.get_business_overview(merchant_id)
        repeat_gmv = round(int(overview["verified_gmv"]) * revenue_share / 100)
        return self._insight(
            "customer_retention_opportunity",
            "فرصت تقویت حفظ مشتری وجود دارد",
            "مشتریان تکراری سهم مهمی از درآمد دارند",
            f"{revenue_share}% از GMV تاییدشده قابل‌شناسایی به مشتریان تکراری مربوط است",
            "سهم درآمد مشتریان تکراری از سهم تعدادی آن‌ها بیشتر است",
            "تمرکز بر بازگشت مشتریان فعلی و پایش رفتار خرید مجدد",
            "medium",
            {
                "repeat_customers": repeat_count,
                "repeat_rate": repeat_rate,
                "repeat_customer_revenue_share": revenue_share,
                "repeat_customer_verified_gmv": repeat_gmv,
            },
            {
                "metric": "سهم مشتریان تکراری از مبلغ پرداخت موفق",
                "formula": "مبلغ پرداخت موفق مشتریان تکراری ÷ مبلغ پرداخت موفق مشتریان قابل‌شناسایی × ۱۰۰",
                "current_period": f"{revenue_share}% سهم از مبلغ پرداخت موفق",
                "baseline": f"{repeat_rate}% سهم مشتریان تکراری از تعداد مشتریان",
                "sample_size": f"{int(customers['unique_customers']):,} مشتری قابل‌شناسایی",
                "filters": [
                    f"پذیرنده: {merchant_id}",
                    "مشتری دارای شناسه کارت قابل‌شناسایی",
                    "مشتری تکراری دارای بیش از یک خرید",
                    "فقط پرداخت‌های Verified برای محاسبه مبلغ",
                ],
            },
        )

    def get_top_insights(self, merchant_id: str) -> List[Insight]:
        """Return at most three insights ranked by impact, confidence, importance."""
        detectors = [
            (self.detect_conversion_drop, 5),
            (self.detect_revenue_leakage, 4),
            (self.detect_retry_opportunity, 3),
            (self.detect_psp_problem, 2),
            (self.detect_customer_retention_opportunity, 1),
        ]
        ranked: List[RankedInsight] = []
        for detector, importance in detectors:
            insight = detector(merchant_id)
            if insight is None:
                continue
            evidence = insight["evidence"]
            financial_impact = float(
                evidence.get(
                    "at_risk_gmv",
                    evidence.get(
                        "estimated_at_risk_gmv_opportunity",
                        evidence.get("repeat_customer_verified_gmv", 0),
                    ),
                )
            )
            ranked.append(
                (
                    insight,
                    financial_impact,
                    self._CONFIDENCE_RANK[insight["confidence"]],
                    importance,
                )
            )

        ranked.sort(key=lambda item: (item[1], item[2], item[3]), reverse=True)
        return [item[0] for item in ranked[:3]]
