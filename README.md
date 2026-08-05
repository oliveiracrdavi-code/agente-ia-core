# Agente IA Core

Motor real de agente de IA no WhatsApp — texto e áudio. Construído do zero
(2026-08-03), inspirado na arquitetura real encontrada em
`inematds/intelecto-testes` (WhatsApp → Evolution API → FastAPI → LLM),
mas com suporte a áudio desde o início, que o original não tinha.

## Arquitetura

```
WhatsApp <-> Evolution API <-> webhook (FastAPI, este projeto) <-> LLM
                                        |
                                  transcrição (áudio recebido)
                                        |
                                  texto-pra-fala (resposta em áudio, se configurado)
```

## Por que Evolution API, não Baileys direto (como o Hermes)
O Hermes é o assistente pessoal do Davi (self-chat, uma conta). Este
projeto é a base pra agentes de CLIENTES — precisa suportar múltiplas
instâncias de WhatsApp isoladas, uma por cliente/projeto. Evolution API
já resolve isso (multi-instância) sem reinventar.

## Configuração por agente (`agents/<nome>/config.yaml`)
- `system_prompt`: personalidade/função do agente
- `mode`: `text` | `audio` | `both`
- `llm_provider` + `llm_api_key`: credencial do cliente (BYOK)
- `evolution_instance`: nome da instância WhatsApp

## Status
MVP em construção (2026-08-03). Sem dashboard ainda — configuração por
arquivo YAML por enquanto. O dashboard web (Fase 2 do projeto maior) vem
depois, provisionando isso automaticamente.
