"""Webhook principal -- recebe evento da Evolution API, roteia texto/áudio,
chama o LLM do agente, responde no mesmo modo (texto ou áudio).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

# Tem que rodar antes de importar audio/evolution -- audio.py lê as chaves
# como constante de módulo no import, load_dotenv() depois seria tarde
# demais. python-dotenv era dependência mas nunca era chamado -- .env
# ficava decorativo, achado real ao debugar por que EVOLUTION_ADMIN_API_KEY
# não estava chegando no processo.
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import audio, evolution, stats
from .auth import require_dashboard_key
from .config import (
    AgentConfig, create_agent_config, get_raw_config, list_agents,
    list_agents_detailed, load_agent_config,
)
from .llm.router import chat_completion


def _within_business_hours(cfg: AgentConfig) -> bool:
    """#25 -- se não configurado, sempre dentro do horário (comportamento
    atual preservado, feature é opt-in)."""
    if not cfg.business_hours_start or not cfg.business_hours_end:
        return True
    now = datetime.now().strftime("%H:%M")
    return cfg.business_hours_start <= now <= cfg.business_hours_end

logger = logging.getLogger("agente-ia-core")
app = FastAPI(title="Agente IA Core")


@app.on_event("startup")
async def _preload_tts_if_needed() -> None:
    """Faz o handshake inicial com o Space de TTS em background se algum
    agente já usa modo áudio/ambos -- sem isso, a primeira mensagem de
    áudio pagaria esse custo (poucos segundos, mas evitável)."""
    uses_audio = False
    for name in list_agents():
        try:
            if load_agent_config(name).mode in ("audio", "both"):
                uses_audio = True
                break
        except (FileNotFoundError, ValueError):
            continue
    if uses_audio:
        logger.info("Pré-carregando modelo de TTS em background (agente com modo áudio detectado)...")
        asyncio.create_task(asyncio.to_thread(audio.preload_tts_model))

# Local: libera qualquer localhost. Remoto: CORS_ALLOW_ORIGIN_REGEX no
# .env (ex: o domínio/IP real do dashboard).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=os.environ.get("CORS_ALLOW_ORIGIN_REGEX", r"http://localhost:\d+"),
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateAgentRequest(BaseModel):
    name: str
    system_prompt: str
    mode: str  # text | audio | both
    llm_provider: str
    llm_api_key: str
    llm_model: str = "openai/gpt-4o-mini"
    evolution_instance: str
    # Local (venv no host): "localhost". Remoto (tudo no mesmo Docker):
    # "http://evolution-api:8080" via EVOLUTION_BASE_URL no .env.
    evolution_base_url: str = os.environ.get("EVOLUTION_BASE_URL", "http://localhost:8080")
    evolution_api_key: str = ""
    client: str = ""
    project: str = ""


@app.get("/health")
async def health():
    return {"status": "ok", "agents": list_agents()}


class TTSRequest(BaseModel):
    text: str


@app.post("/tts", dependencies=[Depends(require_dashboard_key)])
async def text_to_speech(req: TTSRequest):
    """Voz do Jarvis (aba do dashboard) -- edge-tts (voz Antonio), não a
    TTS do navegador."""
    audio_bytes = await audio.synthesize(req.text)
    return Response(content=audio_bytes, media_type="audio/mpeg")


@app.get("/agents", dependencies=[Depends(require_dashboard_key)])
async def list_all_agents():
    """Divisão por cliente/projeto -- retorna todos os agentes com essas tags."""
    return {"agents": list_agents_detailed()}


@app.post("/agents", dependencies=[Depends(require_dashboard_key)])
async def create_agent(req: CreateAgentRequest):
    try:
        create_agent_config(req.name, req.model_dump(exclude={"name"}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cfg = load_agent_config(req.name)
    try:
        await evolution.create_instance(cfg)
    except Exception as exc:
        # Config local já foi salvo -- Davi ainda pode tentar buscar o QR
        # de novo depois (ex: se o Evolution API caiu nesse instante).
        return {"status": "created", "name": req.name, "evolution_warning": str(exc)}
    return {"status": "created", "name": req.name}


@app.get("/agents/{name}/qrcode", dependencies=[Depends(require_dashboard_key)])
async def qrcode(name: str):
    cfg = load_agent_config(name)
    qr = await evolution.get_qr_code(cfg)
    return {"qrcode_base64": qr}


@app.get("/agents/{name}/health", dependencies=[Depends(require_dashboard_key)])
async def agent_health(name: str):
    """#23 -- monitor de saúde real: consulta a Evolution API de verdade,
    não assume conectado só porque o agente existe."""
    cfg = load_agent_config(name)
    state = await evolution.get_connection_state(cfg)
    s = stats.get_stats(name)
    return {"name": name, "connection_state": state, **s}


@app.get("/agents/{name}/conversas", dependencies=[Depends(require_dashboard_key)])
async def agent_conversation(name: str, sender: str | None = None, limit: int = 50):
    """#22 -- histórico real de conversa (o que o agente e o cliente
    trocaram de verdade, não simulado)."""
    return {"messages": stats.get_conversation(name, sender, limit)}


class DuplicateAgentRequest(BaseModel):
    new_name: str
    new_evolution_instance: str
    client: str = ""


@app.post("/agents/{name}/duplicar", dependencies=[Depends(require_dashboard_key)])
async def duplicate_agent(name: str, req: DuplicateAgentRequest):
    """#24 -- clona a config de um agente existente pra um cliente novo,
    trocando só nome/instância/cliente. Não provisiona a instância na
    Evolution API sozinho -- isso o Davi confirma explicitamente na tela
    de criação, igual um agente novo."""
    try:
        raw = get_raw_config(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"agente '{name}' não encontrado")
    raw["evolution_instance"] = req.new_evolution_instance
    if req.client:
        raw["client"] = req.client
    try:
        create_agent_config(req.new_name, raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "created", "name": req.new_name, "cloned_from": name}


@app.get("/atividade", dependencies=[Depends(require_dashboard_key)])
async def atividade_geral():
    """Agrega estatísticas de todos os agentes -- alimenta a aba
    Atividade do dashboard (#49: 'o que mudou hoje')."""
    out = []
    for name in list_agents():
        s = stats.get_stats(name)
        if s["total_in"] > 0 or s["total_out"] > 0:
            out.append({"agent": name, **s})
    out.sort(key=lambda a: a["last_message_at"] or 0, reverse=True)
    return {"agentes": out}


@app.post("/webhook/{agent_name}")
async def webhook(agent_name: str, request: Request):
    cfg = load_agent_config(agent_name)
    payload = await request.json()

    message = payload.get("data", {}).get("message", {})
    key = payload.get("data", {}).get("key", {})
    sender = key.get("remoteJid", "")
    if not sender:
        raise HTTPException(status_code=400, detail="No sender in payload")
    if key.get("fromMe"):
        # Mensagem que o próprio agente mandou (inclui quando o número do
        # agente manda mensagem pra si mesmo, testando) -- sem isso, o
        # bot ficaria respondendo às próprias mensagens em loop.
        return {"status": "ignored", "reason": "message sent by the agent itself"}

    # Texto direto, ou transcrição se veio áudio
    incoming_was_audio = False
    if "conversation" in message:
        user_text = message["conversation"]
    elif "audioMessage" in message and cfg.mode in ("audio", "both"):
        # Achado real testando com áudio de verdade: o campo "base64" fica
        # em message["base64"] (irmão de "audioMessage"), não dentro de
        # audioMessage -- a estrutura documentada não deixa isso óbvio.
        audio_b64 = message.get("base64", "") or message.get("audioMessage", {}).get("base64", "")
        if not audio_b64:
            logger.warning("Audio sem base64 -- message keys: %s", list(message.keys()))
            raise HTTPException(status_code=400, detail="Audio message with no base64 payload")
        user_text = await audio.transcribe(base64.b64decode(audio_b64))
        incoming_was_audio = True
    else:
        return {"status": "ignored", "reason": "unsupported message type for this agent's mode"}

    # #27 (estatísticas) + #26 (escalonamento) -- loga toda mensagem real
    # recebida, independente do que acontece depois.
    escalated = stats.log_message(agent_name, sender, "in", user_text, incoming_was_audio)
    if escalated:
        logger.warning("ESCALONAMENTO: agente=%s sender=%s texto=%r", agent_name, sender, user_text)

    # #25 -- modo horário comercial: responde com a mensagem de ausência
    # configurada em vez de chamar o LLM (evita custo de token fora do
    # expediente e evita prometer algo que só será resolvido depois).
    if not _within_business_hours(cfg):
        stats.log_message(agent_name, sender, "out", cfg.business_hours_message)
        await evolution.send_text(cfg, sender, cfg.business_hours_message)
        return {"status": "ok", "reason": "outside business hours"}

    reply_text = await chat_completion(
        provider=cfg.llm_provider,
        api_key=cfg.llm_api_key,
        model=cfg.llm_model,
        system_prompt=cfg.system_prompt,
        user_text=user_text,
    )
    stats.log_message(agent_name, sender, "out", reply_text)

    # "audio" -- sempre responde em áudio. "both" -- espelha o formato que
    # o cliente usou (achado real: antes só mandava texto no modo "both",
    # mesmo quando o cliente mandava áudio).
    reply_as_audio = cfg.mode == "audio" or (cfg.mode == "both" and incoming_was_audio)
    if reply_as_audio:
        reply_audio = await audio.synthesize(reply_text)
        await evolution.send_audio(cfg, sender, reply_audio)
    else:
        await evolution.send_text(cfg, sender, reply_text)

    return {"status": "ok"}
