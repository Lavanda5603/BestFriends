import json
import numpy as np
from pathlib import Path
from typing import Optional
from loguru import logger
from app.core.config import settings


class VectorIndex:
    def __init__(self, index_path: str, dim: int):
        import faiss
        self.path = Path(index_path)
        self.meta_path = self.path.with_suffix(".meta.json")
        self.dim = dim
        if self.path.exists():
            self.index = faiss.read_index(str(self.path))
            self.meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {}
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.index = faiss.IndexFlatIP(dim)
            self.meta = {}

    def add(self, vec: np.ndarray, meta: dict) -> int:
        v = self._norm(vec).reshape(1, -1)
        idx = self.index.ntotal
        self.index.add(v)
        self.meta[str(idx)] = meta
        self._save()
        return idx

    def search(self, vec: np.ndarray, top_k: int) -> list[dict]:
        if self.index.ntotal == 0:
            return []
        q = self._norm(vec).reshape(1, -1)
        scores, ids = self.index.search(q, min(top_k, self.index.ntotal))
        return [
            {"score": float(s), "faiss_id": int(i), **self.meta.get(str(i), {})}
            for s, i in zip(scores[0], ids[0]) if i != -1
        ]

    def _norm(self, v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def _save(self):
        import faiss
        faiss.write_index(self.index, str(self.path))
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False))


class TextEmbeddingModel:
    _model = None

    def _load(self):
        if not self._model:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading text embeddings: {settings.TEXT_EMBEDDING_MODEL}")
            TextEmbeddingModel._model = SentenceTransformer(settings.TEXT_EMBEDDING_MODEL)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._load().encode(texts, normalize_embeddings=True, batch_size=32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


class ImageEmbeddingModel:
    _siglip = None
    _siglip_proc = None
    _blip = None
    _blip_proc = None

    def _load_siglip(self):
        if not self._siglip:
            from transformers import AutoProcessor, AutoModel
            logger.info(f"Loading SigLIP: {settings.IMAGE_EMBEDDING_MODEL}")
            ImageEmbeddingModel._siglip_proc = AutoProcessor.from_pretrained(settings.IMAGE_EMBEDDING_MODEL)
            ImageEmbeddingModel._siglip = AutoModel.from_pretrained(settings.IMAGE_EMBEDDING_MODEL)
        return self._siglip, self._siglip_proc

    def _load_blip(self):
        if not self._blip:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            logger.info(f"Loading BLIP: {settings.BLIP_MODEL}")
            ImageEmbeddingModel._blip_proc = BlipProcessor.from_pretrained(settings.BLIP_MODEL)
            ImageEmbeddingModel._blip = BlipForConditionalGeneration.from_pretrained(settings.BLIP_MODEL)
        return self._blip, self._blip_proc

    def embed_image(self, img_bytes: bytes) -> np.ndarray:
        import torch
        from PIL import Image
        import io
        model, proc = self._load_siglip()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        inputs = proc(images=img, return_tensors="pt")
        with torch.no_grad():
            v = model.get_image_features(**inputs)[0].numpy().astype(np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def embed_text(self, text: str) -> np.ndarray:
        import torch
        model, proc = self._load_siglip()
        inputs = proc(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            v = model.get_text_features(**inputs)[0].numpy().astype(np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def caption(self, img_bytes: bytes) -> str:
        import torch
        from PIL import Image
        import io
        blip, proc = self._load_blip()
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        inputs = proc(img, return_tensors="pt")
        with torch.no_grad():
            out = blip.generate(**inputs, max_new_tokens=80)
        return proc.decode(out[0], skip_special_tokens=True)


class SearchEngine:
    def __init__(self):
        self.text_idx = VectorIndex(settings.FAISS_TEXT_INDEX_PATH, dim=384)  # bge-small
        self.img_idx = VectorIndex(settings.FAISS_IMAGE_INDEX_PATH, dim=768)  # siglip-base
        self.text_model = TextEmbeddingModel()
        self.img_model = ImageEmbeddingModel()

    def index_text(self, text: str, entity_type: str, entity_id: str, conference_id: str, conference_title: str) -> int:
        return self.text_idx.add(self.text_model.embed_one(text), {
            "entity_type": entity_type, "entity_id": entity_id,
            "conference_id": conference_id, "conference_title": conference_title,
            "snippet": text[:300],
        })

    def index_image(self, img_bytes: bytes, entity_id: str, conference_id: str, conference_title: str) -> tuple[str, int, int]:
        cap = self.img_model.caption(img_bytes)
        text_id = self.text_idx.add(self.text_model.embed_one(cap), {
            "entity_type": "image", "entity_id": entity_id,
            "conference_id": conference_id, "conference_title": conference_title, "snippet": cap,
        })
        img_id = self.img_idx.add(self.img_model.embed_image(img_bytes), {
            "entity_type": "image", "entity_id": entity_id,
            "conference_id": conference_id, "conference_title": conference_title, "caption": cap,
        })
        return cap, text_id, img_id

    def search_text(self, query: str, top_k: int = 10, conference_id: Optional[str] = None) -> list[dict]:
        results = self.text_idx.search(self.text_model.embed_one(query), top_k * 3)
        if conference_id:
            results = [r for r in results if r.get("conference_id") == conference_id]
        return results[:top_k]

    def search_images(self, query: str, top_k: int = 10, conference_id: Optional[str] = None) -> list[dict]:
        results = self.img_idx.search(self.img_model.embed_text(query), top_k * 3)
        if conference_id:
            results = [r for r in results if r.get("conference_id") == conference_id]
        return results[:top_k]

    def get_context(self, question: str, top_k: int = 10, conference_id: Optional[str] = None) -> list[dict]:
        return self.search_text(question, top_k=top_k, conference_id=conference_id)


search_engine = SearchEngine()
