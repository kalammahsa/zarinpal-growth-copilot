# Five-Minute Hackathon Demo

## Before presenting

Start the backend:

    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

Start the frontend in a second terminal:

    python -m http.server 5500 --directory frontend --bind 127.0.0.1

Open http://127.0.0.1:5500, select M31, and keep a 390px mobile viewport ready. Without an OpenAI key, describe the advisor honestly as demo mode: it explains existing insights locally.

## 0:00–0:45 — The merchant problem

**Say**

“Payment logs show attempts, not decisions. Retries can inflate counts, and a dashboard full of metrics still leaves a merchant asking: what should I do?”

“Growth Copilot converts attempts into one record per actual payment journey, then shows at most three actions—each traceable to real calculations.”

**Show**

- Persian RTL landing view.
- Merchant selector.
- Exact historical date range and number of payment journeys behind the screen.
- First action visible without visiting a technical report.

## 0:45–1:30 — Opportunity score

**Say**

“This is an opportunity score, not a vague health score. It is the percentage of observed payment amount attached to sessions that did not finish as Verified.”

“A higher score means more payment value needs attention. It does not claim that the amount is lost or guaranteed recoverable.”

**Show**

- Score and status.
- Open **What is this score?**
- Point to the real numerator and denominator explanation.

## 1:30–2:45 — From insight to action

**Say**

“The engine runs five deterministic detectors and returns the top three, ranked by financial impact, confidence, and business importance.”

“The first card tells the owner the opportunity, impact estimate, and concrete next action.”

**Show**

- First opportunity title.
- Impact estimate and cautious wording.
- Recommended action.
- Click **Copy action**.

## 2:45–3:45 — Trust and traceability

**Say**

“Recommendations without evidence are just opinions. Every card exposes why it appears and exactly how it was calculated.”

**Show**

- Open **Why am I seeing this?**
- Open **View calculation method**.
- Point to metric, formula, current result, comparison baseline, sample size, and filters.

“These values come from pandas calculations over the supplied dataset. AI does not calculate them.”

## 3:45–4:25 — Grounded explanation

Ask: “Why is this opportunity important?”

**Say**

“The advisor is intentionally constrained: it explains existing analytics and ranked insights, but cannot invent a new number or unsupported root cause.”

If demo mode summarizes the insight, state that limitation openly.

## 4:25–5:00 — Mobile and close

**Show**

- Switch to a 390px viewport.
- Confirm score, top action, explanation, and calculation controls remain usable.
- Switch merchant once to show the in-place loading state and fresh results.

**Close**

“The product’s value is not more charts. It is a short path from noisy payment attempts to a trustworthy next action: session-correct metrics, prioritized opportunities, and a calculation trail a merchant can audit.”

## Recovery plan

- API unavailable: the Persian error state gives one retry action.
- Merchant switch: current content stays visible with an updating indicator.
- No insights: the product says no detector crossed its threshold; it does not claim perfect health.
- No trend data: the chart has a dedicated empty state.
- Advisor unavailable: actions and calculation traces still work without AI.
