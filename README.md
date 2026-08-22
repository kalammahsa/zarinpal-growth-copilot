# Zarinpal Growth Copilot

Zarinpal Growth Copilot turns retry-heavy payment logs into a short, Persian RTL action brief for merchant owners:

1. How much payment value needs attention?
2. Which three opportunities matter most?
3. What should the merchant do next?
4. Why is the recommendation shown, and how was it calculated?

All metrics, scores, rankings, and impact estimates are calculated deterministically from the supplied dataset. The optional AI advisor only explains those existing results; it does not create metrics or diagnose unsupported causes.

## What judges should try

1. Open http://127.0.0.1:5500 and select merchant M31.
2. Read the opportunity score. It is the observed share of payment amount attached to non-Verified sessions—not a health score or predicted revenue.
3. Open **Why am I seeing this?** on the first opportunity.
4. Open **View calculation method** to inspect its metric, formula, current value, baseline, sample size, and filters.
5. Copy the recommended action or ask the advisor why that opportunity matters.
6. Switch to a mobile viewport and repeat the same flow.

## Product principles

- **Actionability:** at most three opportunities, ranked by financial impact, confidence, and business importance.
- **Traceability:** every insight includes reason, calculation, and source_metrics.
- **Visible scope:** the dashboard states the exact merchant date range and payment count behind every aggregate.
- **No inflated counts:** raw attempts are reduced to one row per payment session_key.
- **Careful financial language:** non-verified amount is at-risk GMV, never guaranteed lost or recoverable revenue.
- **Non-technical UX:** recommendations lead; supporting metrics and formulas use progressive disclosure.

## Architecture

    Attempt-level CSV
        → prepare_data.py
        → one row per payment session
        → deterministic pandas analytics
        → rule-based insight engine
        → FastAPI
        → Persian mobile-first action brief
        → optional grounded AI explanation

The frontend uses plain HTML, CSS, and JavaScript. The backend uses FastAPI and pandas.

## Run locally

### 1. Install

    cd D:\Mahsa\Projects\zarinpal-demo
    python -m pip install -r backend\requirements.txt

The prepared data/sessions.parquet is included. To rebuild it:

    python backend\prepare_data.py

### 2. Start the API

    # Optional: $env:OPENAI_API_KEY = "your-key"
    # Optional: $env:OPENAI_MODEL = "your-model-id"
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

Without an API key, the advisor runs in demo mode and summarizes only existing deterministic insights.

### 3. Start the frontend

In a second terminal:

    python -m http.server 5500 --directory frontend --bind 127.0.0.1

Open http://127.0.0.1:5500. API docs are at http://127.0.0.1:8000/docs.

## Deterministic methodology

### Session-correct analytics

- Successful payment: final session_status equals Verified.
- Verified GMV: sum of amounts from successful sessions.
- Payment success rate: verified sessions divided by all sessions.
- At-risk GMV: sum of amounts from sessions not ending in Verified.
- Retry metrics count payment sessions, not raw attempts.
- Customer identity uses available payer_card_key values.
- PSP analysis is attempt-based and requires routed attempts with a psp_code.

### Opportunity score

    at-risk GMV ÷ (verified GMV + at-risk GMV) × 100

The API returns the numerator, denominator, result, meaning, and source metrics. A higher score means more observed payment value requires attention. It is not a prediction, merchant ranking, or promise of recovered revenue.

### Insight detectors

1. Conversion below the observed portfolio baseline.
2. At-risk GMV above the observed portfolio 75th percentile.
3. Retry opportunity based on the merchant's observed retry-success rate.
4. Statistically weak PSP route with adequate sample size.
5. Retention opportunity when repeat customers contribute disproportionately to identifiable verified GMV.

Every insight contains a title, impact, reason, action, complete calculation trace, and source metrics. Legacy response fields remain for compatibility.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Service and advisor mode |
| GET | /api/merchants | Available merchant IDs |
| GET | /api/merchant/{merchant_id}/dashboard | Score, analytics, trends, and ranked insights |
| POST | /api/merchant/{merchant_id}/ai/chat | Grounded explanation of existing results |
| GET | /docs | Interactive API documentation |

## Tests

    python backend\test_analytics.py
    python backend\test_insights.py
    python backend\test_ai_service.py

The analytics and insight suites use real merchant M31; insight values are not fabricated.
