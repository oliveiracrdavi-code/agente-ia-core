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
