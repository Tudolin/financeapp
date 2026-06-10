# Finance App - Gestor Financeiro Local

Aplicativo local de controle financeiro pessoal, feito com FastAPI, React, TypeScript e SQLite. O foco do app e centralizar transacoes, cartoes, renda, previsoes mensais, orcamentos e dados importados/sincronizados, mantendo tudo no seu ambiente local.

## Funcionalidades

### Dashboard

- KPIs por mes: renda do mes, despesas, saldo do mes, saldo acumulado, saldo reservado e disponivel para gastar.
- Saldo acumulado com carregamento do residual entre meses.
- Divida residual quando o saldo acumulado fica negativo.
- Grafico de tendencia mensal com renda, despesa, balanco e saldo acumulado.
- Distribuicao de despesas por categoria.
- Saude financeira do mes com burn rate, gasto variavel projetado e alertas por categoria.
- Projecao de patrimonio liquido para 12 meses, alinhada ao mes selecionado no dashboard.

### Transacoes

- Cadastro manual de despesas.
- Cadastro manual de ganho pontual, como trabalho extra ou venda de item.
- Edicao, exclusao e movimentacao de transacoes nao pagas para o mes seguinte.
- Filtros por mes, categoria, via de pagamento e fixo/nao fixo.
- Agrupamento de transacoes relacionadas quando existe `parent_id`.
- Importacao de arquivos:
  - CSV Nubank.
  - PDF Itau.
  - Upload individual ou em lote.
- Tratamento de estornos, pagamentos de fatura e sinais de cartao.

### Pluggy

- Sincronizacao de contas conectadas pela API Pluggy.
- Busca de contas por `item_id`, tipo de conta e periodo.
- Sincronizacao por conta ou por periodo.
- Dedupe por `external_id` e `account_id`.
- Apelidos de contas Pluggy:
  - Mapeia `account_id` para nomes como `Nubank geral`, `gold`, `itau`, etc.
  - Aplica o nome em transacoes ja sincronizadas.
  - Usa o nome automaticamente nas proximas sincronizacoes.
  - Tambem captura nomes vindos da Pluggy quando ainda nao existe apelido manual.

### Cartoes

- Cadastro de cartoes com dia de fechamento e dia de vencimento.
- Uso dos dados de fechamento/vencimento para calcular competencia de compras.
- Cartoes podem ser usados em transacoes manuais e no calendario de compra.

### Calendario de Compra

- Substitui o simulador simples por um calendario mensal.
- Informa valor, parcelas e forma de pagamento.
- Para cartao, calcula a primeira cobranca com base no fechamento e vencimento.
- Para Pix/debito/dinheiro, considera impacto imediato.
- Colore os dias:
  - Verde: bom.
  - Amarelo: apertado.
  - Vermelho: evitar.
- Mostra melhor dia, pior dia, parcela usada e pior saldo projetado.

### Orcamentos

- Limites mensais por categoria.
- Calculo de gasto, restante e percentual usado.
- Gastos de cartao com credito/estorno sao tratados no total da categoria.

### Metas

- Criacao de metas financeiras com valor alvo e prazo.
- Progresso automatico.
- Adicao de aportes.
- Exclusao e atualizacao de status.

### Provisoes e renda atual

- Cadastro de renda mensal atual, com valor bruto e liquido.
- Cadastro de gastos fixos/provisoes recorrentes ou pontuais.
- Frequencias: unica, semanal, mensal e anual.
- Saldo reservado por provisoes.
- Deposito e retirada de saldo de provisoes via API.

### Categorias e regras automaticas

- Categorias padrao para renda, despesas, investimentos, dividas e outros grupos.
- Criacao de novas categorias.
- Regras automaticas por texto ou regex para categorizar transacoes.

## Arquitetura

```text
finance-app/
  backend/
    main.py              FastAPI app e endpoints
    requirements.txt     Dependencias Python
    Dockerfile           Container do backend
    data/                SQLite local quando rodando fora do volume Docker
    migrations/          Scripts SQL auxiliares
  frontend/
    src/
      App.tsx            Aplicacao React principal
      main.tsx           Entrada React
      index.css          Tailwind/base styles
    package.json
    vite.config.ts
    Dockerfile
  docker-compose.yml
```

## Tecnologias

### Backend

- FastAPI
- SQLite
- Pandas
- PDFPlumber
- Requests
- Uvicorn

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts
- Lucide React

## Banco de dados

O banco principal e SQLite.

Tabelas principais:

- `transactions`: transacoes de renda e despesa.
- `cards`: cartoes e regras de fechamento/vencimento.
- `categories`: categorias.
- `budgets`: orcamentos mensais.
- `goals`: metas financeiras.
- `provisions`: provisoes/gastos recorrentes.
- `salary_plan`: renda atual.
- `category_rules`: regras automaticas de categoria.
- `purchase_simulations`: simulacoes antigas/confirmacoes de compra.
- `pluggy_sync_log`: historico de sincronizacao Pluggy.
- `pluggy_account_aliases`: apelidos de contas Pluggy.

Quando roda via Docker, os dados persistem no volume `local_sqlite_data`, montado em `/app/data`.

## Como rodar

### Com Docker

```bash
cd finance-app
docker compose up --build
```

Acesse:

- Frontend: http://localhost:3000
- API: http://localhost:8000
- Docs da API: http://localhost:8000/docs

### Desenvolvimento local sem Docker

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Configuracao Pluggy

Variaveis aceitas no `docker-compose.yml` ou no ambiente:

```bash
PLUGGY_BASE_URL=https://api.pluggy.ai
PLUGGY_CLIENT_ID=
PLUGGY_CLIENT_SECRET=
PLUGGY_API_KEY=
PLUGGY_ITEM_IDS=
PLUGGY_ITEM_ID=
```

Voce pode usar:

- `PLUGGY_API_KEY` diretamente; ou
- `PLUGGY_CLIENT_ID` + `PLUGGY_CLIENT_SECRET` para obter chave temporaria.

Na aba Pluggy:

1. Busque contas conectadas.
2. Renomeie contas com apelidos.
3. Escolha periodo.
4. Sincronize todas ou uma conta especifica.

## Endpoints principais

### Dashboard e analises

- `GET /api/dashboard?month=YYYY-MM`
- `GET /api/monthly-summary`
- `GET /api/mtd-analytics?month=YYYY-MM`
- `GET /api/forecasting?months=12&start_month=YYYY-MM`

### Transacoes

- `GET /api/transactions`
- `POST /api/transactions`
- `PUT /api/transactions/{tx_id}`
- `DELETE /api/transactions/{tx_id}`
- `POST /api/transactions/{tx_id}/move-next-month`

### Importacao

- `POST /api/upload`
- `POST /api/upload-batch`

### Pluggy

- `GET /api/pluggy/status`
- `GET /api/pluggy/accounts`
- `POST /api/pluggy/sync`
- `GET /api/pluggy/account-aliases`
- `POST /api/pluggy/account-aliases`
- `DELETE /api/pluggy/account-aliases/{account_id}`

### Cartoes

- `GET /api/cards`
- `POST /api/cards`
- `PUT /api/cards/{card_id}`

### Planejamento

- `GET /api/salary-plan`
- `POST /api/salary-plan`
- `GET /api/provisions`
- `POST /api/provisions`
- `DELETE /api/provisions/{prov_id}`
- `POST /api/provisions/{prov_id}/fund`
- `POST /api/provisions/{prov_id}/withdraw`

### Orcamentos, metas e categorias

- `GET /api/budgets`
- `POST /api/budgets`
- `GET /api/goals`
- `POST /api/goals`
- `PUT /api/goals/{goal_id}`
- `DELETE /api/goals/{goal_id}`
- `GET /api/categories`
- `POST /api/categories`
- `GET /api/category-rules`
- `POST /api/category-rules`
- `DELETE /api/category-rules/{rule_id}`

## Fluxos de uso

### Registrar ganho pontual

1. Abra Transacoes.
2. Escolha tipo `Ganho pontual`.
3. Informe descricao, valor e categoria.
4. Salve.

O valor entra como renda do mes e soma com a renda mensal cadastrada.

### Renomear conta Pluggy

1. Abra Pluggy.
2. Busque as contas conectadas.
3. Clique em `Renomear` ou cole o `Account ID Pluggy`.
4. Informe o apelido.
5. Salve.

As transacoes antigas daquela conta sao atualizadas e as proximas sincronizacoes ja usam o apelido.

### Escolher melhor dia para compra

1. Abra Calendario de Compra.
2. Informe mes, valor, parcelas e cartao/forma de pagamento.
3. Use as cores do calendario para escolher o melhor dia.

## Comandos uteis

Build do frontend:

```bash
docker compose run --rm frontend npm run build
```

Validar backend:

```bash
python -m py_compile backend/main.py
```

Ver containers:

```bash
docker compose ps
```

Backup rapido do banco no container:

```bash
docker compose exec backend python -c "import shutil; shutil.copy('/app/data/finance.db','/app/data/finance.backup.db')"
```

## Privacidade

Os dados ficam locais no SQLite. A unica integracao externa opcional e a Pluggy, quando configurada e acionada para buscar/sincronizar contas.

## Observacoes

- O saldo residual positivo ou negativo e carregado entre meses nos resumos e na projecao.
- Ganhos pontuais nao substituem salario; eles somam com a renda mensal cadastrada.
- Faturas/cartoes dependem do fechamento e vencimento cadastrados em Cartoes.
- A cor do calendario de compra e uma simulacao baseada no saldo projetado, nao uma garantia financeira.
