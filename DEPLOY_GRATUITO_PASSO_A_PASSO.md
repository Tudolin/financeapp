# Deploy gratuito - Frontend, Backend e Banco online

Este guia descreve um caminho pratico para publicar o Finance App usando:

- Frontend: Vercel
- Backend: Render
- Banco de dados: Neon Postgres

Objetivo: sair do SQLite local e preparar uma base online que possa ser consumida tanto pelo frontend web quanto por um app mobile iOS no futuro.

## Visao geral da arquitetura

```text
Usuario no navegador
  -> Frontend React/Vite na Vercel
  -> Backend FastAPI no Render
  -> Banco Postgres no Neon

Futuro app iOS
  -> Mesmo Backend FastAPI
  -> Mesmo Banco Postgres
```

## Fase 0 - Preparar o repositorio

Antes de subir qualquer coisa, organize o projeto em um repositorio Git.

1. Entre na pasta do projeto:

```bash
cd "d:\Projetos\organizador financeiro\finance-app"
```

2. Inicialize Git, se ainda nao existir:

```bash
git init
```

3. Crie um `.gitignore` se ainda nao existir:

```gitignore
backend/data/
*.db
*.sqlite
*.sqlite3
__pycache__/
.env
.env.local
node_modules/
frontend/dist/
```

4. Garanta que chaves locais nao vao para o Git:

- `api_key.json`
- `.env`
- bancos `.db`
- arquivos de fatura pessoais

5. Commit inicial:

```bash
git add .
git commit -m "Preparar app financeiro para deploy"
```

6. Suba para GitHub.

Voce pode criar o repositorio no GitHub e depois rodar:

```bash
git remote add origin https://github.com/SEU_USUARIO/finance-app.git
git branch -M main
git push -u origin main
```

## Fase 1 - Criar banco online no Neon

1. Acesse https://neon.com.
2. Crie uma conta.
3. Crie um projeto novo, por exemplo:

```text
finance-app
```

4. Escolha a regiao mais proxima possivel.
5. Copie a connection string do Neon.

Ela deve parecer com:

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
postgresql://neondb_owner:npg_sI6ld1MCKUzy@ep-broad-rain-ac82v84q.sa-east-1.aws.neon.tech/neondb?sslmode=require
```

Guarde essa URL. Ela sera usada como `DATABASE_URL`.

## Fase 2 - Adaptar backend de SQLite para Postgres

O backend atual usa `sqlite3` diretamente. Para deploy com banco online, o ideal e migrar para SQLAlchemy.

### 2.1 Instalar dependencias

No arquivo `backend/requirements.txt`, adicionar:

```txt
sqlalchemy
psycopg[binary]
alembic
```

Se quiser manter compatibilidade temporaria com SQLite local, SQLAlchemy permite usar os dois bancos.

### 2.2 Criar modulo de banco

Criar arquivo:

```text
backend/database.py
```

Exemplo base:

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/finance.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2.3 Criar models SQLAlchemy

Criar arquivo:

```text
backend/models.py
```

Modelar as tabelas atuais:

- `transactions`
- `cards`
- `categories`
- `provisions`
- `budgets`
- `goals`
- `salary_plan`
- `category_rules`
- `purchase_simulations`
- `pluggy_sync_log`
- `pluggy_account_aliases`

Comece pelas tabelas mais importantes:

1. `transactions`
2. `cards`
3. `salary_plan`
4. `provisions`
5. `pluggy_account_aliases`

Depois migre as demais.

### 2.4 Migrar endpoints gradualmente

Nao tente trocar tudo de uma vez se quiser reduzir risco.

Ordem recomendada:

1. `/api/categories`
2. `/api/cards`
3. `/api/salary-plan`
4. `/api/transactions`
5. `/api/dashboard`
6. `/api/monthly-summary`
7. `/api/pluggy/*`
8. Orcamentos, metas e provisoes

Enquanto migra, rode testes manuais no frontend.

### 2.5 Criar migrations com Alembic

Na pasta `backend`:

```bash
alembic init alembic
```

Editar `alembic/env.py` para usar o `DATABASE_URL` e os models.

Gerar primeira migration:

```bash
alembic revision --autogenerate -m "initial schema"
```

Aplicar no Neon:

```bash
set DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
alembic upgrade head
```

No PowerShell:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
alembic upgrade head
```

## Fase 3 - Migrar dados do SQLite para Postgres

Depois que o schema existir no Neon, exporte os dados do SQLite e importe no Postgres.

### 3.1 Criar script de migracao

Criar:

```text
backend/scripts/migrate_sqlite_to_postgres.py
```

Ideia do script:

1. Conectar no SQLite local.
2. Conectar no Postgres via `DATABASE_URL`.
3. Ler tabela por tabela.
4. Inserir preservando IDs quando fizer sentido.
5. Validar contagens.

Tabelas para migrar:

- `categories`
- `cards`
- `salary_plan`
- `transactions`
- `provisions`
- `budgets`
- `goals`
- `category_rules`
- `purchase_simulations`
- `pluggy_sync_log`
- `pluggy_account_aliases`

### 3.2 Validar contagens

Compare:

```sql
SELECT COUNT(*) FROM transactions;
SELECT COUNT(*) FROM cards;
SELECT COUNT(*) FROM provisions;
SELECT COUNT(*) FROM pluggy_account_aliases;
```

### 3.3 Validar saldos

Compare no app local e no app com Postgres:

- Dashboard do mes atual.
- Historico de transacoes.
- Pluggy aliases.
- Calendario de compra.
- Projecao de patrimonio.

## Fase 4 - Preparar backend para Render

### 4.1 Ajustar CORS

No backend, trocar CORS aberto por variavel:

```python
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Durante testes, pode permitir tambem localhost:

```python
allow_origins=[FRONTEND_URL, "http://localhost:3000"]
```

### 4.2 Garantir start command

Render pode rodar o backend com:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Se usar Docker, ajuste o `backend/Dockerfile` para respeitar `$PORT`.

Exemplo:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Fase 5 - Subir backend no Render

1. Acesse https://render.com.
2. Crie conta.
3. Clique em `New`.
4. Escolha `Web Service`.
5. Conecte o repositorio GitHub.
6. Selecione o projeto.
7. Configure:

```text
Name: finance-api
Root Directory: backend
Runtime: Python ou Docker
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Se usar Docker:

```text
Runtime: Docker
Root Directory: backend
```

8. Configure variaveis de ambiente:

```text
DATABASE_URL=postgresql://...
PLUGGY_BASE_URL=https://api.pluggy.ai
PLUGGY_CLIENT_ID=...
PLUGGY_CLIENT_SECRET=...
PLUGGY_API_KEY=...
PLUGGY_ITEM_IDS=...
FRONTEND_URL=https://SEU_FRONTEND.vercel.app
```

9. Deploy.
10. Teste:

```text
https://SEU_BACKEND.onrender.com/docs
https://SEU_BACKEND.onrender.com/api/dashboard
```

## Fase 6 - Preparar frontend para Vercel

O frontend ja usa:

```ts
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

Entao basta configurar `VITE_API_URL` na Vercel.

### 6.1 Conferir build local

```bash
cd frontend
npm install
npm run build
```

Ou via Docker:

```bash
docker compose run --rm frontend npm run build
```

## Fase 7 - Subir frontend na Vercel

1. Acesse https://vercel.com.
2. Crie conta.
3. Clique em `Add New Project`.
4. Importe o repositorio.
5. Configure:

```text
Framework Preset: Vite
Root Directory: frontend
Build Command: npm run build
Output Directory: dist
```

6. Variavel de ambiente:

```text
VITE_API_URL=https://SEU_BACKEND.onrender.com
```

7. Deploy.
8. Teste o app.

## Fase 8 - Ajustar CORS final

Depois que a Vercel gerar a URL final:

1. Copie a URL do frontend.
2. Va no Render.
3. Atualize:

```text
FRONTEND_URL=https://SEU_FRONTEND.vercel.app
```

4. Redeploy/restart do backend.

## Fase 9 - Checklist de validacao

No app publicado, testar:

- Abrir Dashboard.
- Selecionar meses diferentes.
- Ver saldo acumulado.
- Criar ganho pontual.
- Criar despesa manual.
- Editar transacao.
- Buscar transacoes por filtro.
- Buscar contas Pluggy.
- Renomear conta Pluggy.
- Sincronizar periodo Pluggy.
- Conferir se aliases aparecem no historico.
- Abrir Calendario de Compra.
- Trocar cartao e parcelas.
- Conferir cor dos dias.
- Criar orcamento.
- Criar meta.
- Criar provisao.

## Fase 10 - Preparar para mobile iOS

Depois que web + backend + banco online estiverem funcionando, crie o app mobile.

### 10.1 Estrutura recomendada

```text
finance-app/
  backend/
  frontend/
  mobile/
  shared/
```

### 10.2 Criar app Expo

```bash
npx create-expo-app mobile
```

### 10.3 Configurar API no mobile

Criar `.env` no mobile:

```text
EXPO_PUBLIC_API_URL=https://SEU_BACKEND.onrender.com
```

### 10.4 Primeiras telas mobile

Ordem recomendada:

1. Login.
2. Dashboard resumido.
3. Lista de transacoes.
4. Botao sincronizar.
5. Nova transacao.
6. Calendario de compra.
7. Pluggy.

### 10.5 Sincronizacao mobile

Comece simples:

```text
Botao sincronizar
  -> chama API
  -> baixa dados do Postgres
  -> atualiza estado local
```

Depois evolua para cache offline:

```text
SQLite local no celular
  -> guarda operacoes pendentes
  -> botao sincronizar envia pendencias
  -> baixa estado atualizado
```

## Fase 11 - Autenticacao

Antes de usar mobile de verdade, adicione login.

Opcoes:

1. Autenticacao propria no FastAPI com JWT.
2. Supabase Auth mantendo Neon como banco nao e ideal.
3. Migrar tudo para Supabase, usando Postgres + Auth no mesmo lugar.

Recomendacao pratica:

- Se quiser simplicidade no mobile: considerar Supabase para Auth + Postgres.
- Se quiser manter controle: FastAPI + JWT + tabela `users`.

Depois do login, adicionar `user_id` nas tabelas:

- `transactions`
- `cards`
- `budgets`
- `goals`
- `provisions`
- `salary_plan`
- `pluggy_account_aliases`
- `pluggy_sync_log`

## Fase 12 - Custos e limites

Com esta arquitetura:

- Vercel Hobby: frontend gratuito para uso pessoal.
- Render Web Service Free: backend gratuito, mas pode ter cold start.
- Neon Free: Postgres gratuito com limite de armazenamento e compute.

Pontos de atencao:

- Backend free pode dormir e demorar ao acordar.
- Banco free tem limites de storage/compute.
- Pluggy pode ter custos/limites proprios conforme sua conta.
- App iOS na App Store exige Apple Developer Program pago.

## Plano resumido

1. Migrar SQLite para SQLAlchemy.
2. Criar schema Postgres.
3. Criar Neon.
4. Migrar dados.
5. Subir backend no Render.
6. Subir frontend na Vercel.
7. Ajustar CORS.
8. Validar funcionalidades.
9. Adicionar autenticacao.
10. Criar app iOS com Expo.
11. Implementar sincronizacao mobile.
