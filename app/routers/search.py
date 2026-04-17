import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.schemas import SearchRequest, SearchResponse, SearchResult, AIAnswerRequest, AIAnswerResponse
from app.search.engine import search_engine
from app.services.llm import llm_service

router = APIRouter(prefix="/search", tags=["Search"])

def _to_result(r: dict) -> SearchResult:
    return SearchResult(
        entity_type=r.get("entity_type", ""),
        entity_id=uuid.UUID(r["entity_id"]),
        conference_id=uuid.UUID(r["conference_id"]),
        conference_title=r.get("conference_title", ""),
        score=r["score"],
        snippet=r.get("snippet") or r.get("caption"),
        caption=r.get("caption"),
    )

@router.post("/", response_model=SearchResponse)
async def search(body: SearchRequest):
    cid = str(body.conference_id) if body.conference_id else None
    if body.mode == "image":
        raw = search_engine.search_images(body.query, body.top_k, cid)
    else:
        raw = search_engine.search_text(body.query, body.top_k, cid)
    return SearchResponse(query=body.query, mode=body.mode, results=[_to_result(r) for r in raw])

@router.post("/ai-answer", response_model=AIAnswerResponse)
async def ai_answer(body: AIAnswerRequest):
    cid = str(body.conference_id) if body.conference_id else None
    context = search_engine.get_context(body.question, top_k=10, conference_id=cid)
    snippets = [r.get("snippet", "") for r in context if r.get("snippet")]
    answer, confidence = llm_service.answer_question(body.question, snippets)
    return AIAnswerResponse(
        question=body.question, answer=answer,
        sources=[_to_result(r) for r in context], confidence=confidence,
    )