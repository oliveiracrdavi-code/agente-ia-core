# agente-ia-core

Motor de agente de WhatsApp (FastAPI). Um agente = uma instância Evolution
API + `agents/<nome>/config.yaml` (file-based, sem banco). Fluxo real:
`app/main.py:webhook()` recebe evento da Evolution API → roteia texto/áudio
→ `app/config.py:load_agent_config()` carrega o agente certo → responde via
`app/evolution.py:send_text()`/`send_audio()`.

## Arquitetura (nós centrais, ver `graphify-out/GRAPH_REPORT.md` pra grafo completo)
- `app/main.py` -- `webhook()` (10 edges, o hub real), `create_agent()`, `list_agents()`, `qrcode()`, `health()`
- `app/evolution.py` -- thin client Evolution API: `AgentConfig`, `get_qr_code()`, `send_text()`, `send_audio()`
- `app/config.py` -- `create_agent_config()`/`load_agent_config()`, grava/lê `agents/<nome>/config.yaml`
- `app/audio.py` -- `transcribe()` (STT via Groq Whisper) e `synthesize()` (TTS via edge-tts, voz Antonio -- trocado do Chatterbox local pra caber no Render free tier 512MB, sem clonagem de voz)

## Coisas que NÃO são óbvias lendo o código
- TTS local roda sequencial e é o gargalo de latência (~9s+ por resposta via Claude CLI subprocess do `saas-creator-core/app/claude_chat.py`). Ver `super-dashboard/app/jarvis/page.tsx` `speak()` pro pipelining sentença-a-sentença que já mitiga isso.
- `webhook()` é o cross-community bridge do projeto (betweenness 0.233) -- qualquer mudança de roteamento passa por ele.
- Sem banco de dados: tudo é arquivo (`agents/<nome>/config.yaml` + logs). Deliberado, não uma limitação a corrigir.

## Economia de tokens neste projeto
Antes de ler `app/main.py` inteiro pra achar uma rota, use `graphify-out/GRAPH_REPORT.md` (já mapeado) ou `graphify query` -- é mais barato que grep + read em arquivo grande. Rode `graphify` de novo só se o código mudou desde 2026-08-03.
