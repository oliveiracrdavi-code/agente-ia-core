"""Log de mensagens por agente -- fundação real pras funções #22 (histórico
de conversa), #23 (indiretamente, via 'última mensagem quando'), #26
(escalonamento) e #27 (estatísticas). Um arquivo JSONL por agente --
simples, sem banco, dá pra fazer append e ler sem lock complicado porque
cada linha é atômica.
"""

from __future__ import annotations

import json
import os
import time

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "conversas")
os.makedirs(_LOG_DIR, exist_ok=True)

# Palavras que sugerem frustração real -- gatilho de escalonamento (#26).
# Lista pequena e direta, não tenta ser um classificador de sentimento.
_ESCALATION_KEYWORDS = [
    "quero falar com uma pessoa", "quero falar com um humano", "isso não resolve",
    "péssimo atendimento", "cancelar", "processo", "reclamação", "reclamar",
    "não é isso que eu pedi", "já falei isso", "você não está entendendo",
]


def _log_path(agent_name: str) -> str:
    return os.path.join(_LOG_DIR, f"{agent_name}.jsonl")


def log_message(agent_name: str, sender: str, direction: str, text: str, is_audio: bool = False) -> bool:
    """direction: 'in' (cliente -> agente) ou 'out' (agente -> cliente).
    Retorna True se a mensagem acionou o gatilho de escalonamento."""
    escalate = direction == "in" and any(kw in text.lower() for kw in _ESCALATION_KEYWORDS)
    entry = {
        "ts": time.time(), "sender": sender, "direction": direction,
        "text": text, "is_audio": is_audio, "escalate": escalate,
    }
    with open(_log_path(agent_name), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return escalate


def get_conversation(agent_name: str, sender: str | None = None, limit: int = 50) -> list[dict]:
    path = _log_path(agent_name)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if sender and entry["sender"] != sender:
                continue
            out.append(entry)
    return out[-limit:]


def get_stats(agent_name: str) -> dict:
    path = _log_path(agent_name)
    if not os.path.exists(path):
        return {"total_in": 0, "total_out": 0, "last_message_at": None, "pending_escalations": 0}
    total_in = total_out = escalations = 0
    last_ts = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry["direction"] == "in":
                total_in += 1
            else:
                total_out += 1
            if entry.get("escalate"):
                escalations += 1
            last_ts = entry["ts"]
    return {
        "total_in": total_in, "total_out": total_out,
        "last_message_at": last_ts, "pending_escalations": escalations,
    }
