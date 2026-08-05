"""Minimal OpenAI-compatible LLM call -- works for OpenRouter, DeepSeek
official, or anything else exposing a /chat/completions endpoint, since
the agent's credential is BYOK (client pastes their own key + provider).
"""

from __future__ import annotations

import httpx

_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


async def chat_completion(
    *, provider: str, api_key: str, model: str, system_prompt: str, user_text: str,
    timeout: float = 60.0,
) -> str:
    base_url = _BASE_URLS.get(provider, provider)  # allow a raw base_url too
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
