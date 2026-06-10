# Deploy do Backend no Render

O banco Neon ja foi migrado. No Render, suba apenas o backend como Web Service.

## Opcao recomendada: Blueprint

1. Suba este repositorio para o GitHub.
2. No Render, escolha **New > Blueprint**.
3. Selecione este repositorio.
4. O Render vai ler o arquivo `render.yaml`.
5. Preencha as variaveis marcadas como secret:
   - `DATABASE_URL`: URL do Postgres Neon com `sslmode=require`.
   - `CORS_ORIGINS`: URL do frontend em producao. Exemplo: `https://seu-frontend.vercel.app`.
   - `PLUGGY_CLIENT_ID`, `PLUGGY_CLIENT_SECRET`, `PLUGGY_API_KEY` e `PLUGGY_ITEM_IDS`, se for usar Pluggy em producao.
6. O `AUTH_SECRET` sera gerado automaticamente pelo Render.

## Opcao manual

Crie um **Web Service** com:

- Runtime: Docker
- Root Directory: `backend`
- Health Check Path: `/api/health`

Variaveis obrigatorias:

- `DATABASE_URL`
- `AUTH_SECRET`
- `CORS_ORIGINS`

Variaveis opcionais:

- `PLUGGY_BASE_URL`
- `PLUGGY_CLIENT_ID`
- `PLUGGY_CLIENT_SECRET`
- `PLUGGY_API_KEY`
- `PLUGGY_ITEM_IDS`

Depois do deploy, teste:

```text
https://SEU-BACKEND.onrender.com/api/health
https://SEU-BACKEND.onrender.com/api/auth/status
```

Quando publicar o frontend, configure nele:

```text
VITE_API_URL=https://SEU-BACKEND.onrender.com
```
