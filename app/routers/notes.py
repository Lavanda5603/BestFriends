import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import Note, Conference
from app.schemas.schemas import NoteCreate, NoteUpdate, NoteResponse, TranslateRequest, TaskStatusResponse
from app.search.engine import search_engine

router = APIRouter(prefix="/conferences/{conference_id}/notes", tags=["Notes"])

@router.post("/", response_model=NoteResponse, status_code=201)
async def create_note(conference_id: uuid.UUID, data: NoteCreate, db: AsyncSession = Depends(get_db)):
    if not await db.get(Conference, conference_id):
        raise HTTPException(404, "Conference not found")
    note = Note(conference_id=conference_id, **data.model_dump())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    search_engine.index_text(note.content, "note", str(note.id), str(conference_id), "")
    return note

@router.get("/", response_model=list[NoteResponse])
async def list_notes(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Note).where(Note.conference_id == conference_id))
    return r.scalars().all()

@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(conference_id: uuid.UUID, note_id: uuid.UUID, data: NoteUpdate, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note or note.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(note, k, v)
    await db.commit()
    await db.refresh(note)
    return note

@router.delete("/{note_id}", status_code=204)
async def delete_note(conference_id: uuid.UUID, note_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note or note.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    await db.delete(note)
    await db.commit()

@router.post("/{note_id}/translate", response_model=TaskStatusResponse)
async def translate_note(conference_id: uuid.UUID, note_id: uuid.UUID, body: TranslateRequest, db: AsyncSession = Depends(get_db)):
    note = await db.get(Note, note_id)
    if not note or note.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    from app.workers.tasks import translate_entity
    t = translate_entity.delay("note", str(note_id), body.target_language)
    return TaskStatusResponse(task_id=t.id, status="queued")