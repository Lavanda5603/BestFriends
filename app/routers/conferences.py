import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.models import Conference
from app.schemas.schemas import (
    ConferenceCreate, ConferenceUpdate, ConferenceResponse, ConferenceListResponse,
    SummaryRequest, SummaryResponse, TaskStatusResponse,
)

router = APIRouter(prefix="/conferences", tags=["Conferences"])


@router.post("/", response_model=ConferenceResponse, status_code=201)
async def create_conference(data: ConferenceCreate, db: AsyncSession = Depends(get_db)):
    conf = Conference(**data.model_dump())
    db.add(conf)
    await db.commit()
    await db.refresh(conf)
    return conf


@router.get("/", response_model=ConferenceListResponse)
async def list_conferences(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Conference))
    r = await db.execute(select(Conference).order_by(Conference.created_at.desc()).offset((page-1)*page_size).limit(page_size))
    return ConferenceListResponse(items=r.scalars().all(), total=total, page=page, page_size=page_size)


@router.get("/{conference_id}", response_model=ConferenceResponse)
async def get_conference(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    conf = await db.get(Conference, conference_id)
    if not conf:
        raise HTTPException(404, "Conference not found")
    return conf


@router.patch("/{conference_id}", response_model=ConferenceResponse)
async def update_conference(conference_id: uuid.UUID, data: ConferenceUpdate, db: AsyncSession = Depends(get_db)):
    conf = await db.get(Conference, conference_id)
    if not conf:
        raise HTTPException(404, "Conference not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(conf, k, v)
    await db.commit()
    await db.refresh(conf)
    return conf


@router.delete("/{conference_id}", status_code=204)
async def delete_conference(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    conf = await db.get(Conference, conference_id)
    if not conf:
        raise HTTPException(404, "Conference not found")
    await db.delete(conf)
    await db.commit()


@router.post("/{conference_id}/summarize", response_model=TaskStatusResponse)
async def summarize_conference(conference_id: uuid.UUID, body: SummaryRequest, db: AsyncSession = Depends(get_db)):
    conf = await db.get(Conference, conference_id)
    if not conf:
        raise HTTPException(404, "Conference not found")
    from app.workers.tasks import summarize_conference as task
    t = task.delay(str(conference_id), body.include_transcripts, body.include_notes, body.include_attachments, body.language or conf.language)
    return TaskStatusResponse(task_id=t.id, status="queued")


@router.get("/{conference_id}/summary", response_model=SummaryResponse)
async def get_summary(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    conf = await db.get(Conference, conference_id)
    if not conf:
        raise HTTPException(404, "Conference not found")
    return SummaryResponse(conference_id=conference_id, summary=conf.summary or "", status=conf.summary_status.value)
