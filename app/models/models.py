import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.core.database import Base


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Conference(Base):
    __tablename__ = "conferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(10), default="ru")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_status: Mapped[ProcessingStatus] = mapped_column(SAEnum(ProcessingStatus), default=ProcessingStatus.PENDING)

    media_files: Mapped[list["MediaFile"]] = relationship("MediaFile", back_populates="conference", cascade="all, delete-orphan")
    notes: Mapped[list["Note"]] = relationship("Note", back_populates="conference", cascade="all, delete-orphan")
    attachments: Mapped[list["Attachment"]] = relationship("Attachment", back_populates="conference", cascade="all, delete-orphan")
    images: Mapped[list["Image"]] = relationship("Image", back_populates="conference", cascade="all, delete-orphan")


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column()
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list | None] = mapped_column(JSON)  # [{start, end, text}]
    translated_transcript: Mapped[str | None] = mapped_column(Text)
    translation_language: Mapped[str | None] = mapped_column(String(10))
    transcript_status: Mapped[ProcessingStatus] = mapped_column(SAEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conference: Mapped["Conference"] = relationship("Conference", back_populates="media_files")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    translated_content: Mapped[str | None] = mapped_column(Text)
    translation_language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    conference: Mapped["Conference"] = relationship("Conference", back_populates="notes")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text)
    translation_language: Mapped[str | None] = mapped_column(String(10))
    extraction_status: Mapped[ProcessingStatus] = mapped_column(SAEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conference: Mapped["Conference"] = relationship("Conference", back_populates="attachments")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conferences.id", ondelete="CASCADE"))
    original_filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    faiss_text_id: Mapped[int | None] = mapped_column(Integer)
    faiss_image_id: Mapped[int | None] = mapped_column(Integer)
    index_status: Mapped[ProcessingStatus] = mapped_column(SAEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conference: Mapped["Conference"] = relationship("Conference", back_populates="images")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(200), index=True)
    task_name: Mapped[str] = mapped_column(String(200))
    entity_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
