from loguru import logger
import httpx
from app.core.config import settings

SUMMARY_PROMPT = """Ты эксперт анализа конференций. Составь структурированное резюме на языке: {language}.
Включи: краткое описание тем, ключевые решения, задачи и предложения (реализованы ли), важные факты.

Материалы:
{content}"""

QA_SYSTEM = """Ты ИИ-ассистент, анализирующий материалы конференции.
Отвечай ТОЛЬКО на основе предоставленного контекста.
Если информации нет — так и скажи. Для вопросов о предложениях/решениях — чётко укажи, было ли озвучено и что с ним стало."""


class LLMService:
    def _call(self, system: str, user: str) -> str:
        r = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": settings.OLLAMA_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
            },
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

    def summarize(self, transcripts: list[str], notes: list[str], attachments: list[str], language: str = "ru") -> str:
        parts = []
        if transcripts:
            parts.append("## Транскрипты\n" + "\n---\n".join(transcripts))
        if notes:
            parts.append("## Заметки\n" + "\n---\n".join(notes))
        if attachments:
            parts.append("## Файлы\n" + "\n---\n".join(attachments))
        if not parts:
            return "Нет материалов для резюме."
        content = "\n\n".join(parts)
        if len(content) > 16000:
            content = content[:16000] + "\n\n[...обрезано...]"
        return self._call("Ты эксперт по анализу конференций.", SUMMARY_PROMPT.format(language=language, content=content))

    def answer_question(self, question: str, context_chunks: list[str]) -> tuple[str, float]:
        if not context_chunks:
            return "В материалах нет релевантной информации.", 0.0
        context = "\n\n---\n\n".join(context_chunks[:10])
        if len(context) > 12000:
            context = context[:12000] + "\n\n[...обрезано...]"
        answer = self._call(QA_SYSTEM, f"Контекст:\n\n{context}\n\n---\n\nВопрос: {question}")
        low = ["не упоминается", "нет информации", "не найдено", "не указано"]
        confidence = 0.3 if any(p in answer.lower() for p in low) else 0.85
        return answer, confidence


llm_service = LLMService()
