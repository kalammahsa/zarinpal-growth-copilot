# Zarinpal Growth Copilot

Zarinpal Growth Copilot turns retry-heavy payment logs into a short, Persian RTL action brief for merchant owners:

1. How much payment value needs attention?
2. Which three opportunities matter most?
3. What should the merchant do next?
4. Why is the recommendation shown, and how was it calculated?

All metrics, scores, rankings, and impact estimates are calculated deterministically from the supplied dataset. The optional AI advisor only explains those existing results; it does not create metrics or diagnose unsupported causes.

## Dataset setup

The challenge dataset is **not included in this repository**.

The `data/` directory is intentionally kept empty.

Before running the project, download the challenge dataset and place it at:

```text
data/other-challenge_data.csv.gz
```

Expected structure:

```text
zarinpal-growth-copilot/
├── backend/
├── frontend/
├── data/
│   └── other-challenge_data.csv.gz
├── README.md
└── DEMO_GUIDE.md
```

Then generate the session-level dataset by running:

```bash
python backend/prepare_data.py
```

This creates:

```text
data/sessions.parquet
```

The generated Parquet file is also **not committed to the repository** and can always be rebuilt from the challenge dataset.

---

## Quick Start

1. Place the challenge dataset in `data/other-challenge_data.csv.gz`.
2. Run `python backend/prepare_data.py`.
3. Start the backend and frontend using the commands below.
4. Open `http://127.0.0.1:5500` and select merchant `M31`.
5. Read the opportunity score. It is the observed share of payment amount attached to non-Verified sessions—not a health score or predicted revenue.
6. Open **Why am I seeing this?** on the first opportunity.
7. Open **View calculation method** to inspect its metric, formula, current value, baseline, sample size, and filters.
8. Copy the recommended action or ask the advisor why that opportunity matters.
9. Switch to a mobile viewport and repeat the same flow.

## Product principles

* **Actionability:** at most three opportunities, ranked by financial impact, confidence, and business importance.
* **Traceability:** every insight includes reason, calculation, and source metrics.
* **Visible scope:** the dashboard states the exact merchant date range and payment count behind every aggregate.
* **No inflated counts:** raw attempts are reduced to one row per payment `session_key`.
* **Careful financial language:** non-verified amount is at-risk GMV, never guaranteed lost or recoverable revenue.
* **Non-technical UX:** recommendations lead; supporting metrics and formulas use progressive disclosure.

## Architecture

```text
Attempt-level CSV
    ↓
prepare_data.py
    ↓
One row per payment session
    ↓
Deterministic pandas analytics
    ↓
Rule-based insight engine
    ↓
FastAPI
    ↓
Persian mobile-first action brief
    ↓
Optional grounded AI explanation
```

The frontend uses plain HTML, CSS, and JavaScript.

The backend uses FastAPI and pandas.

---

## Run locally

### 1. Install dependencies

From the project root:

```powershell
python -m pip install -r backend\requirements.txt
```

### 2. Add the challenge dataset

Place the downloaded dataset here:

```text
data/other-challenge_data.csv.gz
```

The repository does not contain the challenge dataset.

### 3. Prepare the data

Run:

```powershell
python backend\prepare_data.py
```

This reads the attempt-level compressed CSV and generates:

```text
data/sessions.parquet
```

The generated file contains one row per payment session and prevents retries from inflating business metrics.

### 4. Start the API

Optional OpenAI configuration:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "your-model-id"
```

Start FastAPI:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Without an API key, the advisor automatically runs in **Demo AI mode** and summarizes only existing deterministic insights.

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

### 5. Start the frontend

In a second terminal:

```powershell
python -m http.server 5500 --directory frontend --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:5500
```

---

## Deterministic methodology

### Session-correct analytics

* Successful payment: final `session_status` equals `Verified`.
* Verified GMV: sum of amounts from successful sessions.
* Payment success rate: verified sessions divided by all sessions.
* At-risk GMV: sum of amounts from sessions not ending in `Verified`.
* Retry metrics count payment sessions, not raw attempts.
* Customer identity uses available `payer_card_key` values.
* PSP analysis is attempt-based and requires routed attempts with a `psp_code`.

### Opportunity score

```text
at-risk GMV ÷ (verified GMV + at-risk GMV) × 100
```

The API returns the numerator, denominator, result, meaning, and source metrics.

A higher score means more observed payment value requires attention.

It is **not**:

* a prediction,
* a merchant ranking,
* a health score,
* or a promise of recovered revenue.

### Insight detectors

1. Conversion below the observed portfolio baseline.
2. At-risk GMV above the observed portfolio 75th percentile.
3. Retry opportunity based on the merchant's observed retry-success rate.
4. Statistically weak PSP route with adequate sample size.
5. Retention opportunity when repeat customers contribute disproportionately to identifiable verified GMV.

Every insight contains:

* title
* impact
* reason
* recommended action
* calculation trace
* source metrics

Legacy response fields remain for compatibility.

---

## AI Business Advisor

The AI layer does **not** calculate financial metrics.

The flow is:

```text
Merchant question
    ↓
Existing analytics
    ↓
Ranked deterministic insights
    ↓
AI explanation
```

When `OPENAI_API_KEY` is configured, the backend can use the OpenAI API to explain the existing results.

When no API key is available, the system automatically falls back to **Demo AI mode** and generates grounded responses only from existing insights.

The AI layer is therefore never the source of truth for business calculations.

---

## API

| Method | Endpoint                                | Purpose                                       |
| ------ | --------------------------------------- | --------------------------------------------- |
| GET    | `/health`                               | Service and advisor mode                      |
| GET    | `/api/merchants`                        | Available merchant IDs                        |
| GET    | `/api/merchant/{merchant_id}/dashboard` | Score, analytics, trends, and ranked insights |
| POST   | `/api/merchant/{merchant_id}/ai/chat`   | Grounded explanation of existing results      |
| GET    | `/docs`                                 | Interactive API documentation                 |

---

## Tests

Run:

```powershell
python backend\test_analytics.py
python backend\test_insights.py
python backend\test_ai_service.py
```

The analytics and insight suites use real merchant `M31`; insight values are not fabricated.

---

## Repository data policy

The following files are intentionally excluded from Git:

```text
data/other-challenge_data.csv.gz
data/sessions.parquet
```

Users must provide the challenge dataset themselves before running the project.

The `data/` directory may contain a `.gitkeep` file only so the empty directory remains visible in the repository.
