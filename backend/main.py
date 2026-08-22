"""FastAPI application for the Zarinpal Growth Copilot analytics backend."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    # Used when Uvicorn imports this file as backend.main.
    from .analytics import MerchantAnalytics
    from .ai_service import (
        AIBusinessAdvisor,
        AIServiceConfigurationError,
        AIServiceError,
        confidence_from_insights,
    )
    from .insight_engine import InsightEngine
except ImportError:
    # Used when this file is run from inside the backend directory.
    from analytics import MerchantAnalytics
    from ai_service import (
        AIBusinessAdvisor,
        AIServiceConfigurationError,
        AIServiceError,
        confidence_from_insights,
    )
    from insight_engine import InsightEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create one shared analytics engine for the lifetime of the API process."""
    analytics = MerchantAnalytics()
    app.state.analytics = analytics
    app.state.insight_engine = InsightEngine(analytics)
    app.state.ai_advisor = AIBusinessAdvisor()
    app.state.merchant_ids = sorted(
        str(value) for value in analytics._sessions["merchant_key"].unique()
    )
    yield


app = FastAPI(
    title="Zarinpal Growth Copilot API",
    description="Merchant payment analytics built from session-level data.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow a locally served frontend to use the API regardless of its dev-server port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_analytics(request: Request) -> MerchantAnalytics:
    """Return the engine initialized once during application startup."""
    return request.app.state.analytics


def ensure_merchant_exists(request: Request, merchant_id: str) -> None:
    """Return a clear HTTP 404 before running a merchant analysis."""
    if merchant_id not in request.app.state.merchant_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Merchant '{merchant_id}' was not found.",
        )


class AIChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AIChatResponse(BaseModel):
    answer: str
    supporting_insights: List[Dict[str, Any]]
    confidence: str


@app.get("/health", tags=["System"])
def health(request: Request) -> Dict[str, str]:
    return {
        "status": "ok",
        "ai_mode": "demo" if request.app.state.ai_advisor.is_demo_mode else "openai",
    }


@app.get("/api/merchants", tags=["Merchants"])
def get_merchants(request: Request) -> List[str]:
    """Return every merchant identifier available in the prepared dataset."""
    return request.app.state.merchant_ids


@app.get("/api/merchant/{merchant_id}/dashboard", tags=["Merchants"])
def get_merchant_dashboard(request: Request, merchant_id: str) -> Dict[str, Any]:
    """Combine all deterministic analytics needed by the merchant dashboard."""
    ensure_merchant_exists(request, merchant_id)
    analytics = get_analytics(request)

    try:
        return {
            "merchant_id": merchant_id,
            "data_period": analytics.get_data_period(merchant_id),
            "overview": analytics.get_business_overview(merchant_id),
            "opportunity_score": (
                request.app.state.insight_engine.get_merchant_opportunity_score(
                    merchant_id
                )
            ),
            "payment_health": analytics.get_payment_health(merchant_id),
            "revenue": analytics.get_revenue_analysis(merchant_id),
            "customers": analytics.get_customer_analysis(merchant_id),
            "psp": analytics.get_psp_analysis(merchant_id),
            "insights": request.app.state.insight_engine.get_top_insights(merchant_id),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post(
    "/api/merchant/{merchant_id}/ai/chat",
    response_model=AIChatResponse,
    tags=["AI Advisor"],
)
def chat_with_ai_advisor(
    request: Request, merchant_id: str, payload: AIChatRequest
) -> AIChatResponse:
    """Explain existing analytics and insights in concise Persian."""
    ensure_merchant_exists(request, merchant_id)
    analytics = get_analytics(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be blank.")
    try:
        analytics_context = {
            "overview": analytics.get_business_overview(merchant_id),
            "payment_health": analytics.get_payment_health(merchant_id),
            "revenue": analytics.get_revenue_analysis(merchant_id),
            "customers": analytics.get_customer_analysis(merchant_id),
            "psp": analytics.get_psp_analysis(merchant_id),
        }
        insights = request.app.state.insight_engine.get_top_insights(merchant_id)
        answer = request.app.state.ai_advisor.answer(
            question, analytics_context, insights
        )
        return AIChatResponse(
            answer=answer,
            supporting_insights=insights,
            confidence=confidence_from_insights(insights),
        )
    except AIServiceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
