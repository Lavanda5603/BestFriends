from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import os

from app.core.database import engine, Base
from app.routers import conferences, media, notes, attachments, images, search
from app.routers.tasks import router as tasks_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    os.makedirs("storage", exist_ok=True)
    yield

app = FastAPI(title="Conference Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(conferences.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(attachments.router, prefix="/api/v1")
app.include_router(images.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")

# в main.py после создания app
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/health")
async def health():
    return {"status": "ok"}