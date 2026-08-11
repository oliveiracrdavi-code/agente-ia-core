# Deploy remoto (Oracle Cloud Free Tier) — 24GB RAM, sempre ativo, de graça

Segunda tentativa na Oracle, agora com um cartão de **débito comum**
(não pré-pago) que tenha função crédito — isso costuma passar na
verificação deles, diferente do pré-pago que é rejeitado sempre. CPF é
exigido mas você já confirmou que não tem problema com isso.

Se essa tentativa falhar de novo, o plano B (Render + Koyeb, já documentado
em `DEPLOY-RENDER.md`) continua de pé — sem risco, só com o "dormir"
ocasional.

Passos **[VOCÊ]** só você pode fazer.

## 0. O banco (Supabase) já está pronto

Reaproveitamos a mesma URI de conexão que você já configurou.

## 1. [VOCÊ] Criar a conta Oracle Cloud

1. Vá em https://www.oracle.com/cloud/free/
2. No formulário de pagamento, use o cartão de **débito com função
   crédito** (na função "crédito", não "débito", se a maquininha/site
   perguntar).
3. Vai pedir CPF — preenche normal, você confirmou que não é problema.
4. **Se for rejeitado de novo**: não insiste, me avisa e seguimos direto
   pro plano B (Render + Koyeb), sem gastar mais tempo nisso.

## 2. [VOCÊ] Criar a VM

1. Console: **Compute → Instances → Create Instance**.
2. Shape: **VM.Standard.A1.Flex** (ARM, Always Free) — 4 OCPU, 24GB RAM.
3. Imagem: **Ubuntu 22.04 (ARM)**.
4. Baixe a chave SSH gerada.
5. Anote o **IP público**.

Se a região não tiver capacidade ARM disponível no momento, tenta outra
região ou tenta de novo mais tarde — é falta de capacidade da Oracle, não
erro seu.

## 3. [VOCÊ] Abrir as portas

**VCN → Security Lists → Add Ingress Rules** — libere TCP `8080`, `8000`,
`22`.

## 4. [VOCÊ] Entrar na VM e instalar Docker

```bash
ssh -i sua-chave.key ubuntu@SEU_IP_PUBLICO
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

## 5. [VOCÊ] Copiar o projeto pra VM

```bash
scp -r -i sua-chave.key C:\Users\olive\agente-ia-core ubuntu@SEU_IP:~/agente-ia-core
```

(ou `git clone` de um repositório GitHub, se preferir — mais simples se
já tiver o código lá por causa do Render.)

## 6. [VOCÊ] Criar o `.env`

Dentro de `~/agente-ia-core` na VM:

```
EVOLUTION_ADMIN_API_KEY=gere-uma-chave-nova-aqui
SUPABASE_DB_URL=postgresql://postgres.vpvcctqiwudibuccrfbi:SUA_SENHA@aws-0-ca-central-1.pooler.supabase.com:5432/postgres
GROQ_API_KEY=sua-chave-groq-real
DASHBOARD_API_KEY=escolha-uma-chave-secreta-sua
CORS_ALLOW_ORIGIN_REGEX=http://localhost:\d+
```

## 7. Subir a stack

```bash
cd ~/agente-ia-core
docker compose -f docker-compose.oracle.yml up -d --build
```

## 8. Testar

```bash
curl http://SEU_IP_PUBLICO:8000/health
curl http://SEU_IP_PUBLICO:8080
```

Se os dois responderem, está tudo no ar — sempre ativo, sem dormir, sem
custo. Depois disso criamos um agente de verdade, escaneamos o QR pelo
dashboard (que hospedamos em seguida) e testamos com uma mensagem real
no WhatsApp.

---

## 9. Stack completa (dashboard + criador de SaaS) -- sem perder nada

Oracle acessível de novo -- migração da stack inteira (não só o agente
WhatsApp). O que **não pode se perder**: os 14 projetos reais já criados
em `C:\Users\olive\saas-projects`, o `.env` do `saas-creator-core`
(chaves), `clientes_notas.json` e `cost_log.md` (histórico de custo real).
Tudo isso fica fora do container em bind mount -- sobrevive a
rebuild/restart.

### 9.1 [VOCÊ] Copiar o estado real pra VM (antes de subir os containers)

```bash
# do seu PC Windows, com a VM já com Docker instalado (passo 4)
scp -r -i sua-chave.key "C:\Users\olive\saas-projects" ubuntu@SEU_IP:~/agente-ia-core/saas-projects
scp -r -i sua-chave.key "C:\Users\olive\super-dashboard" ubuntu@SEU_IP:~/super-dashboard
scp -r -i sua-chave.key "C:\Users\olive\saas-creator-core" ubuntu@SEU_IP:~/saas-creator-core

# estado solto que fica FORA do container (histórico/config real, não código)
ssh -i sua-chave.key ubuntu@SEU_IP "mkdir -p ~/agente-ia-core/saas-creator-core-state"
scp -i sua-chave.key "C:\Users\olive\saas-creator-core\.env" ubuntu@SEU_IP:~/agente-ia-core/saas-creator-core-state/.env-backup
scp -i sua-chave.key "C:\Users\olive\saas-creator-core\clientes_notas.json" ubuntu@SEU_IP:~/agente-ia-core/saas-creator-core-state/clientes_notas.json
scp -i sua-chave.key "C:\Users\olive\saas-creator-core\cost_log.md" ubuntu@SEU_IP:~/agente-ia-core/saas-creator-core-state/cost_log.md
```

`saas-creator-core` e `super-dashboard` viram pastas **irmãs** de
`agente-ia-core` na VM (`~/agente-ia-core`, `~/super-dashboard`,
`~/saas-creator-core`) -- é o que o `docker-compose.oracle.yml`
atualizado espera (`build: ../saas-creator-core`, `../super-dashboard`).

Se a `scp` de `saas-projects` for grande/lenta (node_modules dos 14
projetos), prefira `rsync` (retoma se cair):

```bash
rsync -avz --progress -e "ssh -i sua-chave.key" \
  --exclude 'node_modules' --exclude '.next' \
  "C:\Users\olive\saas-projects\" ubuntu@SEU_IP:~/agente-ia-core/saas-projects/
```

(sem `node_modules`/`.next` porque `preview.py` já reinstala isso na VM
via junction/npm install quando o preview roda de novo -- copiar
economiza tempo e evita binário Windows indo pra Linux por engano.)

### 9.2 [VOCÊ] Completar o `.env` da VM

Abra o `.env-backup` copiado, confira as chaves (`DEEPSEEK_API_KEY`,
`MINIMAX_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_FALLBACK_MODEL`,
`CORS_ALLOW_ORIGIN_REGEX`) e cole os valores reais no `.env` principal em
`~/agente-ia-core/.env`, junto com o resto (`EVOLUTION_ADMIN_API_KEY`,
`SUPABASE_DB_URL`, `GROQ_API_KEY`, `DASHBOARD_API_KEY`), mais:

```
VM_PUBLIC_IP=SEU_IP_PUBLICO
```

### 9.3 [VOCÊ] Login do Claude Code dentro do container -- gotcha real

O `saas-creator-core` chama a CLI `claude` pra construir/editar os
projetos. Na sua máquina Windows ela já está logada (sessão interativa);
dentro do container Linux ela **nasce deslogada** -- sem isso todo build
falha silenciosamente (fica preso nos retries do gate de verificação).

```bash
cd ~/agente-ia-core
docker compose -f docker-compose.oracle.yml run --rm saas-creator-core claude /login
```

Segue o fluxo (abre um link, você autentica no navegador). Isso grava a
sessão no volume nomeado `claude-cli-auth`, que persiste entre
restarts/rebuilds -- só precisa fazer esse login **uma vez**.

### 9.4 [VOCÊ] Abrir mais portas

Mesmo passo 3, adicionando `3000` (dashboard) e `8500` (saas-creator-core)
na Security List, além das `8080`/`8000`/`22` já liberadas.

### 9.5 Subir a stack inteira

```bash
cd ~/agente-ia-core
docker compose -f docker-compose.oracle.yml up -d --build
```

### 9.6 Testar

```bash
curl http://SEU_IP_PUBLICO:8500/projects   # deve listar os 14 projetos migrados
curl http://SEU_IP_PUBLICO:3000
```

Se `/projects` devolver os mesmos slugs de antes (`academia-crossfit`,
`padaria-pao-nosso`, etc.), a migração não perdeu nada. Dashboard some do
`localhost:3000` do Windows e passa a valer o `http://SEU_IP_PUBLICO:3000`
-- daí sim dá pra desligar o PC sem o site cair.
