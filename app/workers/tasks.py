from celery import Celery
from loguru import logger
from app.core.config import settings

celery_app = Celery(
    "conference_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    timezone="UTC", task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="tasks.transcribe_media", max_retries=3)
def transcribe_media(self, media_file_id: str, language: str = None):
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal
        from app.models.models import MediaFile, ProcessingStatus
        from app.services.transcription import transcription_service
        from app.services.storage import storage_service
        from app.search.engine import search_engine

        async def _run():
            async with AsyncSessionLocal() as db:
                row = await db.get(MediaFile, media_file_id)
                if not row:
                    return
                row.transcript_status = ProcessingStatus.PROCESSING
                await db.commit()
                try:
                    data = storage_service.download_file(row.storage_path)
                    if row.mime_type.startswith("video/"):
                        data = transcription_service.extract_audio_from_video(data)
                    result = transcription_service.transcribe(data, language=language)
                    row.transcript = result["text"]
                    row.transcript_segments = result["segments"]
                    row.transcript_status = ProcessingStatus.DONE
                    await db.commit()
                    chunks = [result["text"][i:i+500] for i in range(0, len(result["text"]), 500)]
                    for chunk in chunks:
                        if chunk.strip():
                            search_engine.index_text(chunk, "transcript", str(row.id), str(row.conference_id), "")
                except Exception as e:
                    row.transcript_status = ProcessingStatus.ERROR
                    await db.commit()
                    raise e

        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"transcribe_media failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="tasks.extract_document_text", max_retries=3)
def extract_document_text(self, attachment_id: str):
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal
        from app.models.models import Attachment, ProcessingStatus
        from app.services.storage import storage_service
        from app.services.document import document_service
        from app.search.engine import search_engine

        async def _run():
            async with AsyncSessionLocal() as db:
                row = await db.get(Attachment, attachment_id)
                if not row:
                    return
                row.extraction_status = ProcessingStatus.PROCESSING
                await db.commit()
                try:
                    data = storage_service.download_file(row.storage_path)
                    text = document_service.extract_text(data, row.mime_type, row.original_filename)
                    row.extracted_text = text or ""
                    row.extraction_status = ProcessingStatus.DONE
                    await db.commit()
                    if text:
                        for chunk in [text[i:i+500] for i in range(0, len(text), 500)]:
                            if chunk.strip():
                                search_engine.index_text(chunk, "attachment", str(row.id), str(row.conference_id), "")
                except Exception as e:
                    row.extraction_status = ProcessingStatus.ERROR
                    await db.commit()
                    raise e

        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"extract_document_text failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="tasks.translate_entity", max_retries=3)
def translate_entity(self, entity_type: str, entity_id: str, target_language: str):
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal
        from app.models.models import MediaFile, Note, Attachment
        from app.services.translation import translation_service

        model_map = {
            "media": (MediaFile, "transcript", "translated_transcript"),
            "note": (Note, "content", "translated_content"),
            "attachment": (Attachment, "extracted_text", "translated_text"),
        }
        if entity_type not in model_map:
            raise ValueError(f"Unknown entity_type: {entity_type}")
        Model, src_field, dst_field = model_map[entity_type]

        async def _run():
            async with AsyncSessionLocal() as db:
                row = await db.get(Model, entity_id)
                if not row:
                    return
                src = getattr(row, src_field, "") or ""
                if not src:
                    return
                setattr(row, dst_field, translation_service.translate(src, target_language))
                setattr(row, "translation_language", target_language)
                await db.commit()

        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"translate_entity failed: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="tasks.index_image", max_retries=3)
def index_image_task(self, image_id: str):
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal
        from app.models.models import Image, ProcessingStatus
        from app.services.storage import storage_service
        from app.search.engine import search_engine

        async def _run():
            async with AsyncSessionLocal() as db:
                row = await db.get(Image, image_id)
                if not row:
                    return
                row.index_status = ProcessingStatus.PROCESSING
                await db.commit()
                try:
                    data = storage_service.download_file(row.storage_path)
                    cap, text_id, img_id = search_engine.index_image(data, str(row.id), str(row.conference_id), "")
                    row.caption = cap
                    row.faiss_text_id = text_id
                    row.faiss_image_id = img_id
                    row.index_status = ProcessingStatus.DONE
                    await db.commit()
                except Exception as e:
                    row.index_status = ProcessingStatus.ERROR
                    await db.commit()
                    raise e

        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"index_image_task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="tasks.summarize_conference", max_retries=2)
def summarize_conference(self, conference_id: str, include_transcripts=True, include_notes=True, include_attachments=True, language="ru"):
    try:
        import asyncio
        from app.core.database import AsyncSessionLocal
        from app.models.models import Conference, MediaFile, Note, Attachment, ProcessingStatus
        from app.services.llm import llm_service
        from sqlalchemy import select

        async def _run():
            async with AsyncSessionLocal() as db:   # ← новый session внутри таски
                conf = await db.get(Conference, conference_id)
                if not conf:
                    return
                conf.summary_status = ProcessingStatus.PROCESSING
                await db.commit()                   # commit сразу

                try:
                    transcripts, notes, attachments = [], [], []
                    if include_transcripts:
                        r = await db.execute(select(MediaFile).where(MediaFile.conference_id == conference_id))
                        transcripts = [m.transcript for m in r.scalars() if m.transcript]
                    if include_notes:
                        r = await db.execute(select(Note).where(Note.conference_id == conference_id))
                        notes = [n.content for n in r.scalars()]
                    if include_attachments:
                        r = await db.execute(select(Attachment).where(Attachment.conference_id == conference_id))
                        attachments = [a.extracted_text for a in r.scalars() if a.extracted_text]

                    conf.summary = llm_service.summarize(transcripts, notes, attachments, language)
                    conf.summary_status = ProcessingStatus.DONE
                    await db.commit()
                except Exception as e:
                    conf.summary_status = ProcessingStatus.ERROR
                    await db.commit()
                    raise e

        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"summarize_conference failed: {exc}")
        raise self.retry(exc=exc, countdown=120)
