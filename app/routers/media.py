import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import MediaFile, Conference
from app.schemas.schemas import MediaFileResponse, TranscribeRequest, TranslateRequest, TaskStatusResponse
from app.services.storage import storage_service

router = APIRouter(prefix="/conferences/{conference_id}/media", tags=["Media"])

@router.post("/", response_model=MediaFileResponse, status_code=201)
async def upload_media(conference_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not await db.get(Conference, conference_id):
        raise HTTPException(404, "Conference not found")
    data = await file.read()
    path = storage_service.upload_file(data, file.filename, file.content_type, prefix=f"media/{conference_id}")
    mf = MediaFile(conference_id=conference_id, original_filename=file.filename,
                   storage_path=path, mime_type=file.content_type, file_size=len(data))
    db.add(mf)
    await db.commit()
    await db.refresh(mf)
    return mf

@router.get("/", response_model=list[MediaFileResponse])
async def list_media(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(MediaFile).where(MediaFile.conference_id == conference_id))
    return r.scalars().all()

@router.get("/{media_id}", response_model=MediaFileResponse)
async def get_media(conference_id: uuid.UUID, media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    mf = await db.get(MediaFile, media_id)
    if not mf or mf.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    return mf

@router.delete("/{media_id}", status_code=204)
async def delete_media(conference_id: uuid.UUID, media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    mf = await db.get(MediaFile, media_id)
    if not mf or mf.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    storage_service.delete_file(mf.storage_path)
    await db.delete(mf)
    await db.commit()

@router.post("/{media_id}/transcribe", response_model=TaskStatusResponse)
async def transcribe(conference_id: uuid.UUID, media_id: uuid.UUID, body: TranscribeRequest, db: AsyncSession = Depends(get_db)):
    mf = await db.get(MediaFile, media_id)
    if not mf or mf.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    from app.workers.tasks import transcribe_media
    t = transcribe_media.delay(str(media_id), body.language)
    return TaskStatusResponse(task_id=t.id, status="queued")

@router.post("/{media_id}/translate", response_model=TaskStatusResponse)
async def translate_media(conference_id: uuid.UUID, media_id: uuid.UUID, body: TranslateRequest, db: AsyncSession = Depends(get_db)):
    mf = await db.get(MediaFile, media_id)
    if not mf or mf.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    from app.workers.tasks import translate_entity
    t = translate_entity.delay("media", str(media_id), body.target_language)
    return TaskStatusResponse(task_id=t.id, status="queued")

@router.get("/{media_id}/url")
async def get_media_url(conference_id: uuid.UUID, media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    mf = await db.get(MediaFile, media_id)
    if not mf or mf.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    return {"url": storage_service.get_presigned_url(mf.storage_path)}