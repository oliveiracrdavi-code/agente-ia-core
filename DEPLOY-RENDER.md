# Deploy remoto (Render + Koyeb) — 100% grátis, sem cartão, sem CPF, sem dormir

Depois de Oracle (rejeita débito/pré-pago/virtual + exige CPF) e Google
Cloud (pediu uma cobrança real na verificação), esse é o caminho sem
risco nenhum de cobrança. Os dois provedores "dormem" depois de um tempo
sem uso — mas isso é resolvido de verdade com um "ping" automático
gratuito (passo 4) que nunca deixa o tempo de inatividade chegar no
limite. Na prática, pra quem vai vender isso com garantia de
funcionamento: fica sempre ativo, de verdade, sem nunca dormir e sem
nunca pagar nada.

Passos **[VOCÊ]** só você pode fazer.

## 0. O banco (Supabase) já está pronto

Você já configurou isso — a URI de conexão que você me mandou vai ser
usada no passo 2.

## 1. [VOCÊ] Colocar o código no GitHub

O Render precisa puxar o código de um repositório Git.

1. Se ainda não tem, crie uma conta em https://github.com (grátis, sem
   cartão).
2. Crie um repositório novo, pode ser **privado**, chamado
   `agente-ia-core`.
3. Suba o código da pasta `C:\Users\olive\agente-ia-core` pra esse
   repositório (se não souber usar `git` pela linha de comando, o GitHub
   Desktop, https://desktop.github.com, faz isso com poucos cliques —
   me avisa se quiser que eu te guie por aí em vez do terminal).

## 2. [VOCÊ] Evolution API no Koyeb

1. Crie conta em https://www.koyeb.com (sem cartão, login com GitHub
   funciona).
2. **Create App → Docker** (não "GitHub" — vamos usar a imagem pronta).
3. No campo da imagem, cole: `docker.io/evoapicloud/evolution-api:latest`
4. Configure a porta: **8080**.
5. Em **Environment variables**, adicione:
   ```
   AUTHENTICATION_API_KEY=gere-uma-chave-nova-aqui
   DATABASE_ENABLED=true
   DATABASE_PROVIDER=postgresql
   DATABASE_CONNECTION_URI=postgresql://postgres.vpvcctqiwudibuccrfbi:SUA_SENHA@aws-0-ca-central-1.pooler.supabase.com:5432/postgres
   DATABASE_CONNECTION_CLIENT_NAME=evolution_exchange
   ```
6. Deploy. Quando terminar, o Koyeb te dá uma URL pública tipo
   `https://algo-random.koyeb.app` — **anota essa URL**, vamos usar no
   próximo passo.

## 3. [VOCÊ] agente-ia-core no Render

1. Crie conta em https://render.com (sem cartão, login com GitHub
   funciona).
2. **New → Web Service**, conecte o repositório `agente-ia-core` do
   GitHub.
3. Environment: **Docker** (o Render detecta o `Dockerfile` sozinho).
4. Em **Environment Variables**, adicione:
   ```
   EVOLUTION_ADMIN_API_KEY=a-mesma-chave-que-voce-gerou-no-koyeb
   EVOLUTION_BASE_URL=https://algo-random.koyeb.app
   WEBHOOK_BASE_URL=https://SEU-APP.onrender.com
   GROQ_API_KEY=sua-chave-groq-real
   DASHBOARD_API_KEY=escolha-uma-chave-secreta-sua
   CORS_ALLOW_ORIGIN_REGEX=http://localhost:\d+
   ```
   `WEBHOOK_BASE_URL` você só sabe depois do primeiro deploy (o Render
   mostra a URL final tipo `https://agente-ia-core.onrender.com`) —
   pode deployar uma vez, pegar a URL, voltar em Environment Variables
   e completar esse campo, redeploy automático.
5. Deploy.

   Nota sobre voz: a resposta em áudio usa **edge-tts** (voz Antonio,
   Microsoft Edge) — não precisa de chave nem variável de ambiente
   extra, e cabe tranquilo nos 512MB do Render free tier. Não é a voz
   clonada do Chatterbox de antes (esse exigia RAM que o free tier não
   tem); testado e funcionando, mas é uma voz "de prateleira", não uma
   clonagem da voz de referência.

## 4. [VOCÊ] Configurar o ping automático (essencial — resolve o "dormir")

O Render dorme depois de ~15 min sem tráfego, o Koyeb depois de ~1h. Um
ping a cada 5 minutos nos dois nunca deixa esse tempo passar — na
prática, os dois ficam sempre ativos, sem nunca dormir de verdade.

1. Vá em https://cron-job.org, crie conta (grátis, sem cartão).
2. **Create cronjob** — configure:
   - Título: `keep-alive agente-ia-core`
   - URL: `https://SEU-APP.onrender.com/health`
   - Execution schedule: **every 5 minutes**
3. Repita, criando um segundo cronjob:
   - Título: `keep-alive evolution-api`
   - URL: `https://algo-random.koyeb.app` (a URL do Koyeb, raiz mesmo)
   - Execution schedule: **every 5 minutes**

Pronto — a partir daqui os dois serviços nunca mais dormem de verdade.

## 5. Testar

```bash
curl https://SEU-APP.onrender.com/health
curl https://algo-random.koyeb.app
```

Se os dois responderem, tá tudo no ar. Cria um agente pelo dashboard
(quando o dashboard também estiver hospedado) ou direto via `curl` no
endpoint `/agents` do Render, escaneia o QR, e testa mandando uma
mensagem de verdade pelo WhatsApp.

## Sobre confiabilidade pra vender com garantia

Com o ping ativo, isso fica equivalente na prática a uma hospedagem
sempre-ativa — mas vale ser honesto com você: se o cron-job.org ficar
fora do ar por um momento (raro, mas pode acontecer com qualquer serviço
gratuito), o app pode dormir uma vez até o próximo ping. Pra um produto
que você vai vender, se em algum momento quiser eliminar até esse risco
residual, um VPS pago de poucos reais por mês remove essa dependência
por completo — mas não é necessário pra começar.

## Sobre o resto do sistema

Dashboard e criador de SaaS ficam pra depois, com a mesma lógica (Render
ou Vercel) — o essencial agora é ter o agente de WhatsApp respondendo
sozinho, sem depender do seu PC.
