from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/conferences_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "conferences"
    MINIO_SECURE: bool = False

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "cpu"

    DEFAULT_LANGUAGE: str = "ru"
    TRANSLATION_PROVIDER: str = "argos"  # argos | opus

    TEXT_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    IMAGE_EMBEDDING_MODEL: str = "google/siglip-base-patch16-224"
    BLIP_MODEL: str = "Salesforce/blip-image-captioning-base"

    FAISS_TEXT_INDEX_PATH: str = "./storage/faiss_text.index"
    FAISS_IMAGE_INDEX_PATH: str = "./storage/faiss_image.index"

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
