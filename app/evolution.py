"""Thin client for Evolution API -- send text/audio, fetch instance QR code."""

from __future__ import annotations

import os

import httpx

from .config import AgentConfig

# Pra onde a Evolution API manda o webhook de mensagem recebida. Local com
# Docker Desktop no Windows: "host.docker.internal" alcança o host de fora
# do container. Em deploy remoto (tudo no mesmo compose), trocar pro nome
# do serviço no docker-compose (ex: "http://agente-ia-core:8000").
WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "http://host.docker.internal:8000")


async def send_text(cfg: AgentConfig, to: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"{cfg.evolution_base_url}/message/sendText/{cfg.evolution_instance}",
            headers={"apikey": cfg.evolution_api_key},
            json={"number": to, "text": text},
        )


async def send_audio(cfg: AgentConfig, to: str, audio_bytes: bytes) -> None:
    import base64
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"{cfg.evolution_base_url}/message/sendWhatsAppAudio/{cfg.evolution_instance}",
            headers={"apikey": cfg.evolution_api_key},
            json={"number": to, "audio": base64.b64encode(audio_bytes).decode()},
        )


async def create_instance(cfg: AgentConfig) -> None:
    """Provisiona a instância no Evolution API. Sem isso, o QR code nunca
    existe -- create_agent só gravava o config.yaml local antes, o Davi
    pediu 'só precisando escanear um QR code', então isso precisa ser
    automático, não um passo manual via curl."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{cfg.evolution_base_url}/instance/create",
            headers={"apikey": cfg.evolution_api_key},
            json={
                "instanceName": cfg.evolution_instance,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS",
            },
        )
        # 403/409 == instância já existe (recriação de um agente existente,
        # ex: reenviar QR depois de desconectar) -- não é um erro real aqui.
        if resp.status_code not in (200, 201, 403, 409):
            resp.raise_for_status()

    await set_webhook(cfg)


async def set_webhook(cfg: AgentConfig) -> None:
    """Sem isso, a Evolution API nunca avisa o agente que chegou mensagem
    -- achado real auditando o fluxo, nunca tinha sido configurado."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{cfg.evolution_base_url}/webhook/set/{cfg.evolution_instance}",
            headers={"apikey": cfg.evolution_api_key},
            json={
                "webhook": {
                    "enabled": True,
                    "url": f"{WEBHOOK_BASE_URL}/webhook/{cfg.evolution_instance}",
                    "events": ["MESSAGES_UPSERT"],
                    # Sem isso, mensagens de áudio chegam no webhook sem o
                    # conteúdo (só metadados) -- achado real testando com
                    # uma mensagem de voz de verdade, dava 400 por faltar
                    # o base64 do áudio. Nota: o campo no REQUEST se chama
                    # "base64", mesmo a resposta da API devolvendo esse
                    # mesmo campo como "webhookBase64" -- nomes diferentes
                    # pro mesmo campo, achado testando direto.
                    "base64": True,
                }
            },
        )
        resp.raise_for_status()


async def get_qr_code(cfg: AgentConfig) -> str:
    """Returns a base64 QR code image string for pairing this instance."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{cfg.evolution_base_url}/instance/connect/{cfg.evolution_instance}",
            headers={"apikey": cfg.evolution_api_key},
        )
        resp.raise_for_status()
        return resp.json().get("base64", "")
