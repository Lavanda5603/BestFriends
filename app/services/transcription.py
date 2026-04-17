import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger
from app.core.config import settings


class TranscriptionService:
    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is None:
            logger.info(f"Loading Whisper: {settings.WHISPER_MODEL}")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                compute_type="int8" if settings.WHISPER_DEVICE == "cpu" else "float16",
            )
        return self._model

    def transcribe(self, audio_data: bytes, language: Optional[str] = None) -> dict:
        model = self._load_model()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        try:
            segments_iter, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True,
                word_timestamps=True,
            )
            seg_list = [
                {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()}
                for s in segments_iter
            ]
            return {
                "text": " ".join(s["text"] for s in seg_list),
                "language": info.language,
                "segments": seg_list,
            }
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def extract_audio_from_video(self, video_data: bytes) -> bytes:
        import subprocess
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as inp,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out,
        ):
            inp.write(video_data)
            inp_path, out_path = inp.name, out.name
        try:
            subprocess.run(
                ["ffmpeg", "-i", inp_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", out_path, "-y"],
                check=True, capture_output=True,
            )
            return Path(out_path).read_bytes()
        finally:
            Path(inp_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)


transcription_service = TranscriptionService()
