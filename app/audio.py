"""Speech-to-text (customer audio) and text-to-speech (agent audio reply).

STT via Groq's Whisper endpoint (tier gratuito real, sem cartão). TTS via
a API pública do Hugging Face Space oficial da Resemble AI
(ResembleAI/Chatterbox-Multilingual-TTS-pt-br) -- mesmo modelo aprovado
pelo Davi ("idêntico a português nativo"), mas chamado remotamente em vez
de rodar local. Decisão real: a VM de hospedagem alvo só tem 1GB de RAM,
insuficiente pra carregar o Chatterbox localmente (~2GB+ com torch) --
chamar a API do Space resolve isso sem pagar nada. Precisa de um
HF_TOKEN grátis (huggingface.co/settings/tokens) pra ter cota própria de
GPU -- sem token, usa a cota compartilhada entre todo mundo, que estoura
rápido (achado real testando com uso repetido).

Ambos STT/TTS são opcionais -- um agente em modo "text" nunca chama isso.
"""

from __future__ import annotations

import asyncio
import os

import httpx
from gradio_client import Client, handle_file

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

_HF_SPACE = os.environ.get(
    "CHATTERBOX_HF_SPACE", "ResembleAI/Chatterbox-Multilingual-TTS-pt-br"
)
# Sem token, o Space usa uma cota de GPU compartilhada entre TODOS os
# usuários anônimos -- estoura rápido com uso real. Um token pessoal
# (grátis, huggingface.co/settings/tokens) dá uma cota própria bem maior.
_HF_TOKEN = os.environ.get("HF_TOKEN", "")
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_PT_BR_REF_AUDIO = os.path.join(_ASSETS_DIR, "pt_br_ref.wav")

_client: Client | None = None


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


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(_HF_SPACE, token=_HF_TOKEN or None)
    return _client


def preload_tts_client() -> None:
    """Chamado no startup do servidor -- o handshake inicial do
    gradio_client com o Space leva alguns segundos, melhor pagar esse
    custo uma vez no boot do que na primeira mensagem de um cliente."""
    try:
        _get_client()
    except Exception:
        # Se o Space estiver fora do ar no boot, não derruba o servidor --
        # só tenta de novo na próxima mensagem de áudio real.
        pass


def _synthesize_sync(text: str) -> bytes:
    client = _get_client()
    result_path = client.predict(
        text_input=text,
        audio_prompt_path_input=handle_file(_PT_BR_REF_AUDIO),
        exaggeration_input=0.5,
        temperature_input=0.8,
        seed_num_input=0,
        cfgw_input=0.5,
        api_name="/generate_tts_audio",
    )
    with open(result_path, "rb") as f:
        return f.read()


async def synthesize(text: str, voice: str | None = None) -> bytes:
    # gradio_client.predict é bloqueante (rede) -- roda numa thread pra
    # não travar o event loop do FastAPI.
    return await asyncio.to_thread(_synthesize_sync, text)
