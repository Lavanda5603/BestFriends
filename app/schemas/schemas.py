from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class ConferenceCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    date: Optional[datetime] = None
    language: str = Field("ru", max_length=10)


class ConferenceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    date: Optional[datetime] = None
    language: Optional[str] = None


class ConferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description: Optional[str]
    date: Optional[datetime]
    language: str
    summary: Optional[str]
    summary_status: str
    created_at: datetime
    updated_at: datetime


class ConferenceListResponse(BaseModel):
    items: List[ConferenceResponse]
    total: int
    page: int
    page_size: int


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class MediaFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conference_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size: int
    duration_seconds: Optional[float]
    transcript: Optional[str]
    transcript_segments: Optional[List[Any]]
    translated_transcript: Optional[str]
    translation_language: Optional[str]
    transcript_status: str
    created_at: datetime


class TranscribeRequest(BaseModel):
    language: Optional[str] = None


class TranslateRequest(BaseModel):
    target_language: str = Field(..., description="ISO 639-1 code: en, ru, de, fr...")


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)
    language: Optional[str] = None


class NoteUpdate(BaseModel):
    content: Optional[str] = None


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conference_id: uuid.UUID
    content: str
    language: Optional[str]
    translated_content: Optional[str]
    translation_language: Optional[str]
    created_at: datetime
    updated_at: datetime


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conference_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size: int
    extracted_text: Optional[str]
    translated_text: Optional[str]
    translation_language: Optional[str]
    extraction_status: str
    created_at: datetime


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conference_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size: int
    caption: Optional[str]
    index_status: str
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    conference_id: Optional[uuid.UUID] = None
    mode: str = Field("text", description="text | image | ai")
    top_k: int = Field(10, ge=1, le=50)


class SearchResult(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    conference_id: uuid.UUID
    conference_title: str
    score: float
    snippet: Optional[str] = None
    image_url: Optional[str] = None
    caption: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: List[SearchResult]


class AIAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conference_id: Optional[uuid.UUID] = None


class AIAnswerResponse(BaseModel):
    question: str
    answer: str
    sources: List[SearchResult]
    confidence: Optional[float] = None


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class SummaryRequest(BaseModel):
    include_transcripts: bool = True
    include_notes: bool = True
    include_attachments: bool = True
    language: Optional[str] = None


class SummaryResponse(BaseModel):
    conference_id: uuid.UUID
    summary: str
    status: str
