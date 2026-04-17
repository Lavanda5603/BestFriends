import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import Attachment, Conference
from app.schemas.schemas import AttachmentResponse, TranslateRequest, TaskStatusResponse
from app.services.storage import storage_service

router = APIRouter(prefix="/conferences/{conference_id}/attachments", tags=["Attachments"])

@router.post("/", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(conference_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not await db.get(Conference, conference_id):
        raise HTTPException(404, "Conference not found")
    data = await file.read()
    path = storage_service.upload_file(data, file.filename, file.content_type, prefix=f"attachments/{conference_id}")
    att = Attachment(conference_id=conference_id, original_filename=file.filename,
                     storage_path=path, mime_type=file.content_type, file_size=len(data))
    db.add(att)
    await db.commit()
    await db.refresh(att)
    from app.workers.tasks import extract_document_text
    extract_document_text.delay(str(att.id))
    return att

@router.get("/", response_model=list[AttachmentResponse])
async def list_attachments(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Attachment).where(Attachment.conference_id == conference_id))
    return r.scalars().all()

@router.delete("/{attachment_id}", status_code=204)
async def delete_attachment(conference_id: uuid.UUID, attachment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    att = await db.get(Attachment, attachment_id)
    if not att or att.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    storage_service.delete_file(att.storage_path)
    await db.delete(att)
    await db.commit()

@router.post("/{attachment_id}/translate", response_model=TaskStatusResponse)
async def translate_attachment(conference_id: uuid.UUID, attachment_id: uuid.UUID, body: TranslateRequest, db: AsyncSession = Depends(get_db)):
    att = await db.get(Attachment, attachment_id)
    if not att or att.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    from app.workers.tasks import translate_entity
    t = translate_entity.delay("attachment", str(attachment_id), body.target_language)
    return TaskStatusResponse(task_id=t.id, status="queued")