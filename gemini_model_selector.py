"""
gemini_model_selector.py
Selecciona modelos Gemini disponibles para la API key actual,
priorizando calidad/costo para este caso de uso.
"""
from __future__ import annotations

import functools
import requests

_CHAT_PREFERENCE = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "models/gemini-2.0-flash",
    "models/gemini-flash-latest",
    "models/gemini-1.5-flash",
]

_EMBED_PREFERENCE = [
    "models/gemini-embedding-001",
    "models/gemini-embedding-2",
    "models/gemini-embedding-2-preview",
]


@functools.lru_cache(maxsize=8)
def _list_models(api_key: str) -> set[str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    models = data.get("models", [])
    return {m.get("name", "") for m in models}


def select_chat_model(api_key: str) -> str:
    try:
        available = _list_models(api_key)
        for candidate in _CHAT_PREFERENCE:
            if candidate in available:
                return candidate.replace("models/", "")
        # fallback genérico: cualquier gemini de texto
        for model in sorted(available):
            if "gemini" in model and "embedding" not in model:
                return model.replace("models/", "")
    except Exception:
        pass
    return "gemini-2.5-flash"


def select_embedding_model(api_key: str) -> str:
    try:
        available = _list_models(api_key)
        for candidate in _EMBED_PREFERENCE:
            if candidate in available:
                return candidate
    except Exception:
        pass
    return "models/gemini-embedding-001"
