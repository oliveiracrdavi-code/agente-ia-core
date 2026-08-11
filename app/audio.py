"""Speech-to-text (customer audio) and text-to-speech (agent audio reply).

STT via Groq's Whisper endpoint (tier gratuito real, sem cartão). TTS via
edge-tts (motor de voz do Microsoft Edge, gratuito e sem limite/conta) --
troca do Chatterbox local: o Chatterbox exigia RAM que o Render free
tier (512MB) não tem. edge-tts não clona a voz de referência do Davi
como o Chatterbox fazia, mas roda sem peso nenhum no servidor.

Ambos STT/TTS são opcionais -- um agente em modo "text" nunca chama isso.
"""

from __future__ import annotations

import os

import edge_tts
import httpx

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

DEFAULT_TTS_VOICE = "pt-BR-AntonioNeural"


async def transcribe(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set -- cannot transcribe customer audio")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": (filename, audio_bytes)},
            data={"model": "whisper-large-v3-turbo"},
        )
        resp.raise_for_status()
        return resp.json()["text"]


def preload_tts_model() -> None:
    """Mantido por compatibilidade com o startup do servidor -- edge-tts
    não tem modelo pra pré-carregar (é uma chamada de rede), então isso
    agora é um no-op."""
    pass


async def synthesize(text: str, voice: str | None = None) -> bytes:
    communicate = edge_tts.Communicate(text, voice or DEFAULT_TTS_VOICE)
    chunks = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.extend(chunk["data"])
    return bytes(chunks)
