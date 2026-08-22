"""Profile raw payment attempts and build a session-level Parquet dataset."""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "other-challenge_data.csv.gz"
OUTPUT_PATH = PROJECT_ROOT / "data" / "sessions.parquet"

SESSION_COLUMNS = [
    "session_key",
    "merchant_key",
    "amount",
    "category_id",
    "category_title",
    "session_status",
    "created_at",
    "verified_at",
    "verify_type",
]
DATE_COLUMNS = ["created_at", "try_created_at", "verified_at", "settled_at"]


def print_profile(df: pd.DataFrame) -> None:
    """Print a concise profile of the attempt-level source data."""
    print("\n=== Data profile ===")
    print(f"Rows: {len(df):,}")
    print(f"Columns ({len(df.columns)}): {', '.join(df.columns)}")

    print("\nData types:")
    print(df.dtypes.to_string())

    print("\nMissing values:")
    print(df.isna().sum().to_string())

    print(f"\nUnique merchants: {df['merchant_key'].nunique(dropna=True):,}")
    print(f"Unique sessions: {df['session_key'].nunique(dropna=True):,}")

    print("\nSession status distribution (attempt rows):")
    print(df["session_status"].value_counts(dropna=False).to_string())

    print("\nDate ranges:")
    for column in DATE_COLUMNS:
        if column not in df.columns:
            continue
        parsed = pd.to_datetime(df[column], errors="coerce")
        print(f"{column}: {parsed.min()} to {parsed.max()}")

    print("\n=== Dataset grain ===")
    print(
        "Each raw row is one payment attempt. A session_key can appear in "
        "multiple rows when a payment is retried, so business metrics must not "
        "be calculated directly from these raw attempt rows. Use the session-level "
        "output for session-based analysis."
    )


def validate_input(df: pd.DataFrame) -> None:
    """Fail clearly if required fields are missing or vary within a session."""
    required = set(SESSION_COLUMNS + ["try_seq"])
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    retained = [column for column in SESSION_COLUMNS if column != "session_key"]
    variation = df.groupby("session_key", sort=False)[retained].nunique(dropna=False)
    inconsistent = variation.gt(1).sum()
    inconsistent = inconsistent[inconsistent > 0]
    if not inconsistent.empty:
        details = ", ".join(
            f"{column} ({count:,} sessions)"
            for column, count in inconsistent.items()
        )
        raise ValueError(
            "Fields expected to be session-level vary within sessions: " + details
        )


def build_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse payment attempts to exactly one row per session_key."""
    retained = [column for column in SESSION_COLUMNS if column != "session_key"]
    aggregations = {column: "first" for column in retained}
    aggregations.update(
        attempt_count=("session_key", "size"),
        max_try_seq=("try_seq", "max"),
    )

    sessions = (
        df.groupby("session_key", as_index=False, sort=False, dropna=False)
        .agg(
            **{
                **{
                    column: (column, rule)
                    for column, rule in aggregations.items()
                    if isinstance(rule, str)
                },
                "attempt_count": aggregations["attempt_count"],
                "max_try_seq": aggregations["max_try_seq"],
            }
        )
    )
    sessions["has_retry"] = sessions["attempt_count"] > 1

    ordered_columns = SESSION_COLUMNS + ["attempt_count", "max_try_seq", "has_retry"]
    return sessions[ordered_columns]


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {INPUT_PATH}")

    print(f"Loading {INPUT_PATH} ...")
    attempts = pd.read_csv(INPUT_PATH, compression="gzip")
    print_profile(attempts)
    validate_input(attempts)

    for column in ("created_at", "verified_at"):
        attempts[column] = pd.to_datetime(attempts[column], errors="coerce")

    sessions = build_sessions(attempts)
    if len(sessions) != attempts["session_key"].nunique(dropna=False):
        raise RuntimeError("Session aggregation did not produce one row per session_key")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sessions.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(sessions):,} session rows to {OUTPUT_PATH}")
    print(f"Output columns: {', '.join(sessions.columns)}")


if __name__ == "__main__":
    main()
