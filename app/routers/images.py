import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import Image, Conference
from app.schemas.schemas import ImageResponse
from app.services.storage import storage_service

router = APIRouter(prefix="/conferences/{conference_id}/images", tags=["Images"])

@router.post("/", response_model=ImageResponse, status_code=201)
async def upload_image(conference_id: uuid.UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not await db.get(Conference, conference_id):
        raise HTTPException(404, "Conference not found")
    data = await file.read()
    path = storage_service.upload_file(data, file.filename, file.content_type, prefix=f"images/{conference_id}")
    img = Image(conference_id=conference_id, original_filename=file.filename,
                storage_path=path, mime_type=file.content_type, file_size=len(data))
    db.add(img)
    await db.commit()
    await db.refresh(img)
    from app.workers.tasks import index_image_task
    index_image_task.delay(str(img.id))
    return img

@router.get("/", response_model=list[ImageResponse])
async def list_images(conference_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Image).where(Image.conference_id == conference_id))
    return r.scalars().all()

@router.delete("/{image_id}", status_code=204)
async def delete_image(conference_id: uuid.UUID, image_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    img = await db.get(Image, image_id)
    if not img or img.conference_id != conference_id:
        raise HTTPException(404, "Not found")
    storage_service.delete_file(img.storage_path)
    await db.delete(img)
    await db.commit()