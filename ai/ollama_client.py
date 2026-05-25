from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaError(RuntimeError):
    pass


def call_ollama_chat(
    messages: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = 120,
    temperature: float = 0.1,
) -> str:
    """
    Llama a Ollama usando la API nativa /api/chat.

    No requiere instalar dependencias externas. Usa solo la librería estándar.
    """
    model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)).rstrip("/")

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    request = urllib.request.Request(
        url=f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise OllamaError(f"No se pudo conectar con Ollama en {base_url}: {exc}") from exc
    except TimeoutError as exc:
        raise OllamaError("La validación con Ollama agotó el tiempo de espera.") from exc

    try:
        data = json.loads(raw)
        return data["message"]["content"]
    except Exception as exc:
        raise OllamaError(f"Respuesta inesperada de Ollama: {raw[:500]}") from exc
