"""Deterministic merchant analytics built from prepared session data."""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_PATH = PROJECT_ROOT / "data" / "sessions.parquet"
DEFAULT_ATTEMPTS_PATH = PROJECT_ROOT / "data" / "other-challenge_data.csv.gz"


class MerchantAnalytics:
    """Provide merchant metrics without counting payment retries as new sessions."""

    def __init__(
        self,
        sessions_path: Path = DEFAULT_SESSIONS_PATH,
        attempts_path: Path = DEFAULT_ATTEMPTS_PATH,
    ) -> None:
        self.sessions_path = Path(sessions_path)
        self.attempts_path = Path(attempts_path)
        if not self.sessions_path.exists():
            raise FileNotFoundError(f"Session dataset not found: {self.sessions_path}")

        # Load the prepared, one-row-per-session dataset exactly once per engine.
        self._sessions = pd.read_parquet(self.sessions_path)
        self._sessions["created_at"] = pd.to_datetime(
            self._sessions["created_at"], errors="coerce"
        )
        self._attempts: pd.DataFrame = None  # type: ignore[assignment]

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        """Return a stable percentage and avoid division-by-zero errors."""
        return round((numerator / denominator) * 100, 2) if denominator else 0.0

    def _merchant_sessions(self, merchant_id: str) -> pd.DataFrame:
        merchant = self._sessions[
            self._sessions["merchant_key"] == merchant_id
        ].copy()
        if merchant.empty:
            raise ValueError(f"Unknown merchant_id: {merchant_id}")
        return merchant

    def _load_attempts(self) -> pd.DataFrame:
        """Lazily load attempt-only fields needed by customer and PSP analysis."""
        if self._attempts is None:
            if not self.attempts_path.exists():
                raise FileNotFoundError(
                    f"Attempt dataset not found: {self.attempts_path}"
                )
            self._attempts = pd.read_csv(
                self.attempts_path,
                compression="gzip",
                usecols=[
                    "session_key",
                    "merchant_key",
                    "payer_card_key",
                    "psp_code",
                    "try_status",
                ],
            )
        return self._attempts

    def get_business_overview(self, merchant_id: str) -> Dict[str, Any]:
        sessions = self._merchant_sessions(merchant_id)
        verified = sessions["session_status"] == "Verified"
        not_verified = ~verified
        total = len(sessions)
        successful = int(verified.sum())
        verified_gmv = int(sessions.loc[verified, "amount"].sum())

        return {
            "total_sessions": total,
            "successful_payments": successful,
            # GMV counts only sessions whose final session outcome is Verified.
            "verified_gmv": verified_gmv,
            "conversion_rate": self._percentage(successful, total),
            "average_successful_payment": round(
                verified_gmv / successful, 2
            ) if successful else 0.0,
            "failed_sessions": int((sessions["session_status"] == "Failed").sum()),
            # This is payment volume at risk, not realized or "lost" revenue.
            "at_risk_gmv": int(sessions.loc[not_verified, "amount"].sum()),
        }

    def get_data_period(self, merchant_id: str) -> Dict[str, Any]:
        """Return the exact observed date range behind merchant aggregates."""
        sessions = self._merchant_sessions(merchant_id)
        dates = sessions["created_at"].dropna()
        return {
            "start_date": dates.min().date().isoformat() if not dates.empty else None,
            "end_date": dates.max().date().isoformat() if not dates.empty else None,
            "session_count": int(len(sessions)),
        }

    def get_payment_health(self, merchant_id: str) -> Dict[str, Any]:
        sessions = self._merchant_sessions(merchant_id)
        retried = sessions["has_retry"].astype(bool)
        verified = sessions["session_status"] == "Verified"
        total = len(sessions)
        retry_count = int(retried.sum())

        status_distribution = {
            str(status): int(count)
            for status, count in sessions["session_status"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        }

        return {
            "status_distribution": status_distribution,
            "retry_rate": self._percentage(retry_count, total),
            # Of sessions with multiple attempt rows, how many finally verified?
            "retry_success_rate": self._percentage(
                int((retried & verified).sum()), retry_count
            ),
            # A single-attempt verified session succeeded without needing a retry.
            "first_attempt_success_rate": self._percentage(
                int((~retried & verified).sum()), total
            ),
            "paid_not_verified_count": int(
                (sessions["session_status"] == "Paid").sum()
            ),
        }

    def get_revenue_analysis(self, merchant_id: str) -> Dict[str, List[Dict[str, Any]]]:
        sessions = self._merchant_sessions(merchant_id)
        sessions = sessions.dropna(subset=["created_at"]).copy()
        sessions["date"] = sessions["created_at"].dt.strftime("%Y-%m-%d")
        verified = sessions[sessions["session_status"] == "Verified"]
        failed = sessions[sessions["session_status"] == "Failed"]

        gmv_by_day = (
            verified.groupby("date", sort=True)["amount"].sum().reset_index(name="gmv")
        )
        successful_trend = (
            verified.groupby("date", sort=True).size().reset_index(name="count")
        )
        failed_trend = failed.groupby("date", sort=True).size().reset_index(name="count")
        categories = (
            verified.groupby(["category_id", "category_title"], as_index=False)
            ["amount"]
            .sum()
            .rename(columns={"amount": "gmv"})
            .sort_values(["gmv", "category_id"], ascending=[False, True])
            .head(10)
        )

        return {
            "gmv_by_day": self._records(gmv_by_day),
            "successful_payment_trend": self._records(successful_trend),
            "failed_payment_trend": self._records(failed_trend),
            "top_categories_by_gmv": self._records(categories),
        }

    @staticmethod
    def _records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert pandas/numpy scalars into ordinary JSON-friendly Python values."""
        records: List[Dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            records.append(
                {
                    key: value.item() if hasattr(value, "item") else value
                    for key, value in row.items()
                }
            )
        return records

    def get_customer_analysis(self, merchant_id: str) -> Dict[str, Any]:
        sessions = self._merchant_sessions(merchant_id)
        attempts = self._load_attempts()
        merchant_attempts = attempts[
            (attempts["merchant_key"] == merchant_id)
            & attempts["payer_card_key"].notna()
        ][["session_key", "payer_card_key"]]

        # One customer/session pair prevents retry attempts inflating repeat behavior.
        customer_sessions = merchant_attempts.drop_duplicates("session_key")
        counts = customer_sessions.groupby("payer_card_key")["session_key"].nunique()
        unique_customers = len(counts)
        repeat_cards = counts[counts > 1].index
        repeat_customers = len(repeat_cards)

        session_customers = sessions.merge(
            customer_sessions, on="session_key", how="inner", validate="one_to_one"
        )
        verified = session_customers[
            session_customers["session_status"] == "Verified"
        ]
        total_revenue = int(verified["amount"].sum())
        repeat_revenue = int(
            verified.loc[verified["payer_card_key"].isin(repeat_cards), "amount"].sum()
        )

        return {
            "unique_customers": unique_customers,
            "repeat_customers": repeat_customers,
            "repeat_rate": self._percentage(repeat_customers, unique_customers),
            # Revenue share is based on Verified GMV with an identifiable card.
            "repeat_customer_revenue_share": self._percentage(
                repeat_revenue, total_revenue
            ),
        }

    def get_psp_analysis(self, merchant_id: str) -> List[Dict[str, Any]]:
        self._merchant_sessions(merchant_id)  # Validate the merchant consistently.
        attempts = self._load_attempts()
        routed = attempts[
            (attempts["merchant_key"] == merchant_id) & attempts["psp_code"].notna()
        ].copy()
        routed["is_success"] = routed["try_status"] == "Verified"

        grouped = routed.groupby("psp_code", sort=True)["is_success"].agg(
            transaction_count="size", successful_count="sum"
        )
        result: List[Dict[str, Any]] = []
        for psp_code, row in grouped.iterrows():
            count = int(row["transaction_count"])
            successes = int(row["successful_count"])
            result.append(
                {
                    "psp_code": str(psp_code),
                    # PSP transaction count is routed attempt count, not sessions.
                    "transaction_count": count,
                    "success_rate": self._percentage(successes, count),
                    "failure_rate": self._percentage(count - successes, count),
                }
            )
        return result
