"""Per-agent config loader -- agents/<name>/config.yaml.

Deliberately file-based for now (no dashboard yet, see README). The
dashboard (Fase 2 of the bigger project) will write these files
automatically instead of a human editing YAML by hand.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import yaml

_AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents")
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    mode: str  # "text" | "audio" | "both"
    llm_provider: str
    llm_api_key: str
    llm_model: str
    evolution_instance: str
    evolution_base_url: str
    evolution_api_key: str
    client: str = ""
    project: str = ""


def load_agent_config(name: str) -> AgentConfig:
    path = os.path.join(_AGENTS_DIR, name, "config.yaml")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No config for agent '{name}' at {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    required = ["system_prompt", "mode", "llm_provider", "llm_api_key", "evolution_instance"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"Agent '{name}' config missing required keys: {missing}")

    return AgentConfig(
        name=name,
        system_prompt=data["system_prompt"],
        mode=data["mode"],
        llm_provider=data["llm_provider"],
        llm_api_key=data["llm_api_key"],
        llm_model=data.get("llm_model", "openai/gpt-4o-mini"),
        evolution_instance=data["evolution_instance"],
        evolution_base_url=data.get("evolution_base_url", "http://localhost:8080"),
        evolution_api_key=data.get("evolution_api_key") or os.environ.get("EVOLUTION_ADMIN_API_KEY", ""),
        client=data.get("client", ""),
        project=data.get("project", ""),
    )


def create_agent_config(name: str, data: dict) -> None:
    """Write a new agents/<name>/config.yaml from a dashboard request.

    Validates the name against a safe slug pattern (no path traversal --
    this writes to disk from an HTTP request, so this check is load-bearing,
    not decorative) and the same required-keys check load_agent_config uses.
    """
    if not _SAFE_NAME.match(name):
        raise ValueError(
            "Agent name must be lowercase letters, digits, hyphens only (2-63 chars)"
        )
    required = ["system_prompt", "mode", "llm_provider", "llm_api_key", "evolution_instance"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")
    if data["mode"] not in ("text", "audio", "both"):
        raise ValueError("mode must be 'text', 'audio', or 'both'")

    agent_dir = os.path.join(_AGENTS_DIR, name)
    os.makedirs(agent_dir, exist_ok=True)
    with open(os.path.join(agent_dir, "config.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def list_agents() -> list[str]:
    if not os.path.isdir(_AGENTS_DIR):
        return []
    return [
        d for d in os.listdir(_AGENTS_DIR)
        if os.path.isfile(os.path.join(_AGENTS_DIR, d, "config.yaml"))
    ]


def list_agents_detailed() -> list[dict]:
    """Divisão por cliente/projeto que o Davi pediu -- lista todos os
    agentes com client/project pra agrupar na UI."""
    out = []
    for name in list_agents():
        try:
            cfg = load_agent_config(name)
            out.append({
                "name": cfg.name, "client": cfg.client, "project": cfg.project,
                "mode": cfg.mode,
            })
        except (FileNotFoundError, ValueError):
            continue
    return out
