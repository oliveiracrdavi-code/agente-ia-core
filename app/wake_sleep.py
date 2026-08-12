"""Orquestrador de liga/desliga do PC do Davi -- roda AQUI (Render, sempre
ativo) porque o saas-creator-core só existe no PC dele (Claude Code CLI
precisa do login/assinatura local, não tem como rodar num servidor sem
API key separada -- decisão do Davi em 2026-08-11).

Fluxo:
1. Dashboard manda POST /desktop/heartbeat enquanto uma aba que depende do
   saas-creator-core (Chat/SaaS Creator/Pesquisa/Vendedor IA) tá aberta.
   Cada heartbeat manda o pacote mágico de nome (inofensivo se o PC já tá
   acordado) e atualiza `last_heartbeat`.
2. Um loop em background (`_watchdog_loop`) roda a cada 60s: se faz mais
   de 30 minutos sem heartbeat, checa `/pc/status` do PC (se alcançável).
   - Claude ocupado (build rodando) -> não faz nada, espera.
   - Claude livre pela primeira vez desde que ficou ocioso -> começa a
     contar mais 1h de graça antes de mandar dormir.
   - Já tava livre há mais de 1h -> manda `/pc/dormir`.
   - PC inalcançável (já dormindo, ou porta ainda não liberada no
     roteador) -> não faz nada, não tem o que dormir.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time

import httpx

logger = logging.getLogger("agente-ia-core.wake_sleep")

# Mesmo MAC/host de app/wol.py no saas-creator-core -- ver esse arquivo
# pra detalhe completo de como o pacote mágico funciona e o que precisa
# tá configurado no roteador de casa do Davi.
DAVI_PC_MAC = "D8:43:AE:BA:57:2F"
DAVI_HOME_HOST = os.environ.get("DAVI_HOME_HOST", "177.99.74.42")
WOL_PORT = 9

LOCAL_BACKEND_URL = os.environ.get("LOCAL_BACKEND_URL", f"http://{DAVI_HOME_HOST}:8001")
_DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "")

IDLE_BEFORE_CHECK_SECONDS = 30 * 60  # #1 -- 30min sem heartbeat antes de sequer cogitar dormir
GRACE_AFTER_BUSY_SECONDS = 60 * 60  # #2 -- mais 1h depois que o Claude termina de construir
POLL_INTERVAL_SECONDS = 60

# Desligado por padrão até o Davi confirmar que o resto do sistema tá
# pronto -- pedido explícito dele em 2026-08-11 (não remover a feature,
# só não disparar sozinha ainda). Liga com POST /desktop/auto-sleep
# {"enabled": true}.
_auto_sleep_enabled = os.environ.get("AUTO_SLEEP_ENABLED", "false").lower() == "true"


def set_auto_sleep_enabled(enabled: bool) -> None:
    global _auto_sleep_enabled
    _auto_sleep_enabled = enabled


def is_auto_sleep_enabled() -> bool:
    return _auto_sleep_enabled

_state = {
    "last_heartbeat": None,  # float | None
    "became_free_at": None,  # float | None -- quando viu busy=False pela 1a vez ociosa
    "ever_busy_this_idle": False,
}


def _build_magic_packet(mac_address: str) -> bytes:
    mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
    return b"\xff" * 6 + mac_bytes * 16


def send_wake_on_lan() -> None:
    packet = _build_magic_packet(DAVI_PC_MAC)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (DAVI_HOME_HOST, WOL_PORT))


async def heartbeat() -> dict:
    was_idle = _state["last_heartbeat"] is None or (
        time.time() - _state["last_heartbeat"] > IDLE_BEFORE_CHECK_SECONDS
    )
    _state["last_heartbeat"] = time.time()
    if was_idle:
        # PC pode tá dormindo -- manda acordar. Sem custo se já tava
        # ligado (o pacote é ignorado por qualquer PC já acordado).
        try:
            send_wake_on_lan()
        except Exception as exc:
            logger.warning("falha mandando WoL no heartbeat: %s", exc)
        _state["became_free_at"] = None
        _state["ever_busy_this_idle"] = False
    return {"status": "ok"}


async def _local_pc_status() -> dict | None:
    headers = {"x-dashboard-key": _DASHBOARD_API_KEY} if _DASHBOARD_API_KEY else {}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(f"{LOCAL_BACKEND_URL}/pc/status", headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None  # inalcançável -- provavelmente já dormindo, ou roteador não liberou a porta ainda


async def _local_pc_sleep() -> bool:
    headers = {"x-dashboard-key": _DASHBOARD_API_KEY} if _DASHBOARD_API_KEY else {}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.post(f"{LOCAL_BACKEND_URL}/pc/dormir", headers=headers)
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("falha mandando /pc/dormir: %s", exc)
        return False


async def _watchdog_tick() -> None:
    last_hb = _state["last_heartbeat"]
    if not _auto_sleep_enabled:
        return  # feature desligada -- só o wake por heartbeat continua ativo

    if last_hb is None:
        return  # nunca visitou -- nada pra fazer

    idle_seconds = time.time() - last_hb
    if idle_seconds < IDLE_BEFORE_CHECK_SECONDS:
        return  # ainda dentro da janela normal de uso

    status = await _local_pc_status()
    if status is None:
        return  # inalcançável -- nada a dormir

    if status.get("busy"):
        _state["ever_busy_this_idle"] = True
        _state["became_free_at"] = None
        return  # Claude ainda construindo algo -- espera

    if _state["became_free_at"] is None:
        _state["became_free_at"] = time.time()  # primeira vez livre desde que ficou ocioso
        return

    grace_elapsed = time.time() - _state["became_free_at"]
    if grace_elapsed >= GRACE_AFTER_BUSY_SECONDS:
        if await _local_pc_sleep():
            logger.info("PC do Davi mandado dormir (ocioso + livre por %.0fs)", grace_elapsed)
            _state["last_heartbeat"] = None
            _state["became_free_at"] = None
            _state["ever_busy_this_idle"] = False


async def _watchdog_loop() -> None:
    while True:
        try:
            await _watchdog_tick()
        except Exception as exc:
            logger.warning("watchdog tick falhou: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_watchdog() -> None:
    asyncio.create_task(_watchdog_loop())


def get_state() -> dict:
    last_hb = _state["last_heartbeat"]
    return {
        "last_heartbeat_ago_seconds": (time.time() - last_hb) if last_hb else None,
        "became_free_at_ago_seconds": (
            time.time() - _state["became_free_at"] if _state["became_free_at"] else None
        ),
        "ever_busy_this_idle": _state["ever_busy_this_idle"],
        "auto_sleep_enabled": _auto_sleep_enabled,
    }
