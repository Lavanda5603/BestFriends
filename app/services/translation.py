from typing import Optional
from loguru import logger
from app.core.config import settings

OPUS_MODELS: dict = {}


class TranslationService:
    def translate(self, text: str, target_language: str, source_language: Optional[str] = None) -> str:
        if not text or not text.strip():
            return text
        if settings.TRANSLATION_PROVIDER == "opus":
            return self._translate_opus(text, target_language, source_language)
        return self._translate_argos(text, target_language, source_language)

    def _translate_argos(self, text: str, target: str, source: Optional[str] = None) -> str:
        try:
            from argostranslate import translate
            installed = translate.get_installed_languages()
            codes = {l.code: l for l in installed}
            src_lang = codes.get(source) if source else None
            tgt_lang = codes.get(target)
            if not tgt_lang:
                logger.warning(f"Argos: target lang '{target}' not installed")
                return text
            if src_lang:
                tr = src_lang.get_translation(tgt_lang)
                if tr:
                    return tr.translate(text)
            for code, lang in codes.items():
                if code == target:
                    continue
                tr = lang.get_translation(tgt_lang)
                if tr:
                    return tr.translate(text)
            return text
        except Exception as e:
            logger.error(f"Argos error: {e}")
            return text

    def _translate_opus(self, text: str, target: str, source: Optional[str] = None) -> str:
        try:
            from transformers import MarianMTModel, MarianTokenizer
            src = source or "ru"
            key = f"{src}-{target}"
            if key not in OPUS_MODELS:
                model_name = f"Helsinki-NLP/opus-mt-{src}-{target}"
                logger.info(f"Loading opus-mt: {model_name}")
                OPUS_MODELS[key] = (
                    MarianTokenizer.from_pretrained(model_name),
                    MarianMTModel.from_pretrained(model_name),
                )
            tokenizer, model = OPUS_MODELS[key]
            inputs = tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=512)
            translated = model.generate(**inputs)
            return tokenizer.decode(translated[0], skip_special_tokens=True)
        except Exception as e:
            logger.error(f"Opus-mt error: {e}, falling back to argos")
            return self._translate_argos(text, target, source)

    def install_argos_package(self, source: str, target: str):
        try:
            from argostranslate import package
            package.update_package_index()
            available = package.get_available_packages()
            pkg = next((p for p in available if p.from_code == source and p.to_code == target), None)
            if pkg:
                package.install_from_path(pkg.download())
                logger.info(f"Installed argos: {source}->{target}")
        except Exception as e:
            logger.error(f"Argos install error: {e}")


translation_service = TranslationService()
