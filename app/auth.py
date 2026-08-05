"""Proteção mínima pra quando isso sai do localhost e vira um IP público
(deploy remoto pedido pelo Davi) -- sem isso, qualquer um na internet
poderia criar agentes de WhatsApp usando a instância Evolution dele. Se
DASHBOARD_API_KEY não estiver setada (uso 100% local), não exige nada --
mantém o comportamento local de sempre. Nota: /webhook/{agent} fica de
fora dessa checagem -- é a própria Evolution API chamando, não o dashboard.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

_DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "")


async def require_dashboard_key(x_dashboard_key: str = Header(default="")) -> None:
    if not _DASHBOARD_API_KEY:
        return
    if x_dashboard_key != _DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Chave do dashboard inválida ou ausente")
