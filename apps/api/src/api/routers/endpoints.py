from fastapi import APIRouter, HTTPException, Depends
from typing import List
from api.schemas.schemas import (
    CompanyResponse, CompanyCreate,
    FinancialFactResponse, FinancialFactCorrectionRequest,
    ChatMessage, ChatSessionRequest
)

api_router = APIRouter()

# Companies Router
@api_router.get("/companies", response_model=List[CompanyResponse], tags=["Companies"])
async def get_companies():
    # Placeholder returning mock data
    return []

@api_router.post("/companies", response_model=CompanyResponse, tags=["Companies"])
async def create_company(payload: CompanyCreate):
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Financial Facts Router
@api_router.get("/facts/{company_id}", response_model=List[FinancialFactResponse], tags=["Facts"])
async def get_financial_facts(company_id: int):
    return []

@api_router.post("/facts/{fact_id}/correct", response_model=FinancialFactResponse, tags=["Facts"])
async def correct_financial_fact(fact_id: int, payload: FinancialFactCorrectionRequest):
    # This will trigger synchronous recalculations via MetricCalculationService
    raise HTTPException(status_code=501, detail="Not implemented yet")


# Copilot Agent Router
@api_router.post("/copilot/chat", tags=["Copilot"])
async def copilot_chat(payload: ChatSessionRequest):
    # This will route to the LangGraph copilot agent
    return {"answer": "I am the Credit Underwriting Copilot. Please ask questions about corporate filings.", "citations": []}
