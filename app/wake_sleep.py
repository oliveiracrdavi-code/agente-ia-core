"""Orquestrador de liga/desliga do PC do Davi -- roda AQUI (Render, sempre
ativo) porque o saas-creator-core só existe no PC dele (Claude Code CLI
precisa do login/assinatura local, não tem como rodar num servidor sem
API key separada -- decisão do Davi em 2026-08-11).

Fluxo (reescrito em 2026-08-12 -- pedido explícito do Davi antes de ir
dormir: janela única de 1h, contando os DOIS sinais de atividade juntos,
não 30min+1h separados como na versão anterior):
1. Dashboard manda POST /desktop/heartbeat enquanto uma aba que depende do
   saas-creator-core (Chat/SaaS Creator/Pesquisa/Vendedor IA) tá aberta.
   Cada heartbeat conta como atividade E manda o pacote mágico de
   propósito (inofensivo se o PC já tá acordado).
2. `/pc/status` local diz se tem QUALQUER claude.exe rodando -- cobre
   tanto um build disparado pelo saas-creator-core quanto a PRÓPRIA
   sessão interativa do Claude Code do Davi (ele pediu que isso conte
   como atividade também, não só builds).
3. Um loop em background (`_watchdog_loop`) roda a cada 60s: se faz mais
   de 1h desde a última vez que QUALQUER UM dos dois sinais esteve ativo
   (heartbeat recente OU claude.exe rodando), manda `/pc/dormir`.
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

IDLE_SECONDS_BEFORE_SLEEP = 60 * 60  # 1h sem heartbeat E sem claude.exe rodando
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
    "last_activity": None,  # float | None -- max(last_heartbeat, ultima vez que claude.exe apareceu rodando)
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
        time.time() - _state["last_heartbeat"] > IDLE_SECONDS_BEFORE_SLEEP
    )
    now = time.time()
    _state["last_heartbeat"] = now
    _state["last_activity"] = now
    if was_idle:
        # PC pode ta dormindo -- manda acordar. Sem custo se ja tava
        # ligado (o pacote e ignorado por qualquer PC ja acordado).
        try:
            send_wake_on_lan()
        except Exception as exc:
            logger.warning("falha mandando WoL no heartbeat: %s", exc)
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
    if not _auto_sleep_enabled:
        return  # feature desligada -- só o wake por heartbeat continua ativo

    status = await _local_pc_status()
    if status is None:
        return  # inalcançável -- provavelmente já dormindo, nada a fazer

    if status.get("busy"):
        _state["last_activity"] = time.time()
        return

    last_activity = _state["last_activity"]
    if last_activity is None:
        return  # nunca viu atividade nenhuma ainda -- nada a fazer

    idle_seconds = time.time() - last_activity
    if idle_seconds >= IDLE_SECONDS_BEFORE_SLEEP:
        if await _local_pc_sleep():
            logger.info("PC do Davi mandado dormir (ocioso ha %.0fs, sem heartbeat nem claude.exe)", idle_seconds)
            _state["last_heartbeat"] = None
            _state["last_activity"] = None


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
    last_activity = _state["last_activity"]
    last_hb = _state["last_heartbeat"]
    return {
        "last_heartbeat_ago_seconds": (time.time() - last_hb) if last_hb else None,
        "last_activity_ago_seconds": (time.time() - last_activity) if last_activity else None,
        "auto_sleep_enabled": _auto_sleep_enabled,
    }
