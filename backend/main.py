# backend/main.py - corrigido

import os
import re
import db_compat as sqlite3
import unicodedata
import base64
import hashlib
import hmac
import json
import secrets
import pandas as pd
import pdfplumber
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
from pydantic import BaseModel


def parse_cors_origins() -> List[str]:
    raw_origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_URL") or ""
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


app = FastAPI(title="Local Finance API")

# Configuração do CORS para o React acessar
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if not path.startswith("/api") or path in PUBLIC_API_PATHS:
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    payload = decode_auth_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "Login necessario"})
    request.state.user = payload
    return await call_next(request)

DEFAULT_DB_PATH = "/app/data/finance.db" if os.path.isdir("/app") else os.path.join(os.path.dirname(__file__), "data", "finance.db")
DB_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
PLUGGY_BASE_URL = os.getenv("PLUGGY_BASE_URL", "https://api.pluggy.ai").rstrip("/")
AUTH_SECRET = os.getenv("AUTH_SECRET") or os.getenv("SECRET_KEY") or "local-dev-secret-change-me"
PLUGGY_API_KEY_CACHE = {"value": "", "expires_at": None}
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/register",
}


def password_hash(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(password_hash(password, salt), stored_hash)


def token_signature(payload: str) -> str:
    digest = hmac.new(AUTH_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_auth_token(user: dict) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({
        "id": user["id"],
        "email": user["email"],
    }).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{payload}.{token_signature(payload)}"


def decode_auth_token(token: str) -> Optional[dict]:
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(token_signature(payload), signature):
            return None
        padded = payload + "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return None


def users_count() -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0] or 0
        conn.close()
        return count
    except Exception:
        return 0


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip().strip('"').strip("'")

# Categorias padrão do sistema
DEFAULT_CATEGORIES = [
    "Alimentação", "Transporte", "Moradia", "Utilities", "Saúde",
    "Educação", "Lazer", "Compras", "Seguros", "Investimentos",
    "Dívidas", "Pessoal", "Negócio", "Renda", "Outros"
]

CATEGORY_KEYWORDS = {
    "Alimentação": ["supermercado", "restaurante", "padaria", "ifood", "uber eats", "fast food", "marmita", "lanche", "delivery"],
    "Transporte": ["uber", "99", "gasolina", "combustivel", "combustível", "ônibus", "onibus", "metrô", "metro", "táxi", "taxi", "pedágio", "pedagio", "estacionamento", "rodoviária", "localiza", "rappi"],
    "Moradia": ["aluguel", "condomínio", "condominio", "água", "agua", "luz", "energia", "internet", "telefone", "telefonia", "iptu", "condominio", "saneamento"],
    "Utilities": ["internet", "telefone", "telefonia", "energia", "água", "agua", "luz", "condominio", "apple", "applecombill"],
    "Saúde": ["farmácia", "farmacia", "hospital", "clinica", "consulta", "medicamento", "remedio", "remédio", "dentista", "exame", "saúde", "saude", "academia"],
    "Educação": ["curso", "faculdade", "escola", "cursinho", "livro", "educacao", "educação", "treinamento", "seminario", "seminário"],
    "Lazer": ["cinema", "show", "viagem", "hotel", "bar", "restaurante", "passeio", "teatro", "netflix", "spotify", "parque"],
    "Compras": ["loja", "shopping", "roupa", "sapato", "e-commerce", "amazon", "amazonprime", "amazonprimebr", "amazon retail", "mercadolivre", "melimais", "compra", "supermercado", "desconto"],
    "Seguros": ["seguro", "apólice", "apolice", "insurance"],
    "Investimentos": ["investimento", "tesouro", "ações", "acoes", "fii", "crypto", "bitcoin", "cdb", "renda fixa", "fundo", "dividendo"],
    "Dívidas": ["boleto", "financiamento", "emprestimo", "parcelado", "prestacao", "parcela", "divida", "dívida", "cartão", "cartao", "parcelamento", "fatura"],
    "Pessoal": ["salao", "salão", "barbearia", "beleza", "cosmetico", "cosmético", "academia", "presente", "hobby"],
    "Renda": ["salário", "salario", "pagamento", "recebido", "deposito", "depósito", "freelancer", "recibo", "provento", "dividendo", "aluguel recebido", "renda", "reembolso"]
}

REFUND_KEYWORDS = ["estorno", "reembolso"]
CARD_CREDIT_KEYWORDS = [
    "estorno",
    "credito de",
    "crédito de",
    "desconto de antecipacao",
    "desconto de antecipação",
    "reembolso",
]
CARD_PAYMENT_KEYWORDS = [
    "pagamento recebido",
    "pagamento",
]
CARD_IMPORT_SKIP_KEYWORDS = [
    "pagamento recebido",
    "valor pendente",
    "parcelamento de fatura",
    "fatura",
]

INCOME_KEYWORDS = ["salário", "salario", "pagamento", "recebido", "deposito", "depósito", "freelancer", "recibo", "provento", "dividendo", "aluguel recebido", "renda", "reembolso"]

EXPENSE_KEYWORDS = [
    "mercado", "supermercado", "restaurante", "gasolina", "aluguel", "conta", "boleto", "farmacia", "consult", "cartao", "cartão",
    "academia", "pagamento", "passagem", "iptu", "condominio", "condomínio", "seguro"
]


def is_card_credit(title: str) -> bool:
    text = normalize_text(title)
    return any(keyword_match(text, keyword) for keyword in CARD_CREDIT_KEYWORDS)


def is_card_payment(title: str) -> bool:
    text = normalize_text(title)
    return any(keyword_match(text, keyword) for keyword in CARD_PAYMENT_KEYWORDS)


def is_card_import_metadata(title: str) -> bool:
    text = normalize_text(title)
    return any(keyword_match(text, keyword) for keyword in CARD_IMPORT_SKIP_KEYWORDS)


def refund_match_key(title: str) -> str:
    text = title or ""
    quoted = re.findall(r'"([^"]+)"', text)
    if quoted:
        return normalize_text(quoted[0])
    paren = re.findall(r'\(([^)]+)\)', text)
    if paren:
        return normalize_text(paren[-1])
    text = re.sub(r'\bestorno de\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bcr[eé]dito de\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bcompra\b', '', text, flags=re.IGNORECASE)
    return normalize_text(text)


def remove_refund_pairs(entries):
    charges = []
    refunds = []
    for entry in entries:
        if entry["amount"] < 0:
            refunds.append(entry)
        else:
            charges.append(entry)

    removed_charge_indexes = set()
    for refund in refunds:
        target_amount = abs(refund["amount"])
        refund_key = refund_match_key(refund["title"])
        best_index = None
        for idx, charge in enumerate(charges):
            if idx in removed_charge_indexes:
                continue
            if abs(charge["amount"] - target_amount) >= 0.01:
                continue
            charge_key = refund_match_key(charge["title"])
            if refund_key and charge_key and (refund_key in charge_key or charge_key in refund_key):
                best_index = idx
                break
            if normalize_text(refund["title"]) == normalize_text(charge["title"]):
                best_index = idx
                break
        if best_index is not None:
            removed_charge_indexes.add(best_index)

    return [entry for idx, entry in enumerate(charges) if idx not in removed_charge_indexes]


def is_known_card_source(source: Optional[str]) -> bool:
    if not source:
        return False
    normalized = normalize_text(source)
    return normalized not in {"manual", "pix", "dinheiro", "debito", "debito", "boleto", "outro"}


def repair_card_transaction_signs(cursor):
    cursor.execute(
        "SELECT id, title, amount, date, card_source, payment_method FROM transactions WHERE is_summary = 0"
    )
    rows = cursor.fetchall()
    card_rows = [
        row for row in rows
        if is_known_card_source(row[4]) or is_known_card_source(row[5])
    ]
    ids_to_delete = set()
    for row in card_rows:
        tx_id, title, amount, date, card_source, payment_method = row
        if is_card_payment(title or ""):
            ids_to_delete.add(tx_id)

    refund_rows = [
        row for row in card_rows
        if is_card_credit(row[1] or "") and not is_card_payment(row[1] or "")
    ]
    charge_rows = [
        row for row in card_rows
        if row[0] not in ids_to_delete and not is_card_credit(row[1] or "")
    ]
    for refund in refund_rows:
        refund_id, refund_title, refund_amount, refund_date, refund_card, _ = refund
        refund_key = refund_match_key(refund_title or "")
        ids_to_delete.add(refund_id)
        for charge in charge_rows:
            charge_id, charge_title, charge_amount, charge_date, charge_card, _ = charge
            if charge_id in ids_to_delete:
                continue
            if refund_card != charge_card:
                continue
            if abs((refund_amount or 0) - (charge_amount or 0)) >= 0.01:
                continue
            charge_key = refund_match_key(charge_title or "")
            if refund_key and charge_key and (refund_key in charge_key or charge_key in refund_key):
                ids_to_delete.add(refund_id)
                ids_to_delete.add(charge_id)
                break

    for row in card_rows:
        tx_id, title, amount, date, card_source, payment_method = row
        normalized_title = normalize_text(title or "")
        if normalized_title == "conte contabilidade" and abs((amount or 0) - 249.0) < 0.01:
            ids_to_delete.add(tx_id)

    for tx_id in ids_to_delete:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))

    cursor.execute(
        "SELECT id, title, card_source, payment_method, is_income FROM transactions WHERE is_summary = 0"
    )
    rows = cursor.fetchall()
    for row in rows:
        tx_id, title, card_source, payment_method, current_is_income = row
        if not (is_known_card_source(card_source) or is_known_card_source(payment_method)):
            continue

        corrected_is_income = 1 if is_card_credit(title or "") else 0
        if current_is_income != corrected_is_income:
            cursor.execute(
                "UPDATE transactions SET is_income = ? WHERE id = ?",
                (corrected_is_income, tx_id)
            )

    cursor.execute(
        "SELECT id, title, category, card_source, payment_method, is_income FROM transactions WHERE is_summary = 0 AND category = 'Renda'"
    )
    rows = cursor.fetchall()
    for row in rows:
        tx_id, title, category, card_source, payment_method, current_is_income = row
        if current_is_income == 1:
            continue
        if not (is_known_card_source(card_source) or is_known_card_source(payment_method)):
            continue
        raw_title = (title or "").lower()
        normalized_title = normalize_text(title or "")
        corrected_category = "Dívidas" if "renegocia" in raw_title or "pend" in raw_title or "pendencias" in normalized_title else "Outros"
        cursor.execute(
            "UPDATE transactions SET category = ? WHERE id = ?",
            (corrected_category, tx_id)
        )

    cursor.execute(
        "SELECT id, title, category, card_source, payment_method, is_income FROM transactions WHERE is_summary = 0 AND category = 'Outros'"
    )
    rows = cursor.fetchall()
    for row in rows:
        tx_id, title, category, card_source, payment_method, current_is_income = row
        if current_is_income == 1:
            continue
        if not (is_known_card_source(card_source) or is_known_card_source(payment_method)):
            continue
        raw_title = (title or "").lower()
        normalized_title = normalize_text(title or "")
        if "renegocia" in raw_title or "pend" in raw_title or "pendencias" in normalized_title:
            cursor.execute(
                "UPDATE transactions SET category = ? WHERE id = ?",
                ("Dívidas", tx_id)
            )


def normalize_text(text: str) -> str:
    normalized = re.sub(r'[^0-9a-zA-Z]+', ' ', text.lower())
    return normalized.strip()


def keyword_match(text: str, keyword: str) -> bool:
    normalized = normalize_text(keyword)
    if not normalized:
        return False
    return re.search(r"\b" + re.escape(normalized) + r"\b", text) is not None


def infer_category_and_income(title: str, amount: float, description: Optional[str] = None):
    value = abs(amount)
    text = normalize_text(f"{title} {description or ''}")
    category = "Outros"
    best_match_length = 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword_match(text, keyword):
                if len(keyword) > best_match_length:
                    category = cat
                    best_match_length = len(keyword)
                break

    is_income = None
    if amount < 0 or any(keyword_match(text, keyword) for keyword in REFUND_KEYWORDS):
        is_income = 1

    if is_income is None:
        if any(keyword_match(text, keyword) for keyword in INCOME_KEYWORDS):
            is_income = 1
        elif any(keyword_match(text, keyword) for keyword in EXPENSE_KEYWORDS):
            is_income = 0
        else:
            is_income = 0 if amount >= 0 else 1

    if category == "Renda" and is_income == 0:
        category = "Outros"

    if category == "Outros" and is_income == 1:
        category = "Renda"

    return {
        "category": category,
        "is_income": is_income,
        "amount": value
    }


def auto_categorize_transaction(title: str, amount: float, description: Optional[str] = None):
    category = None
    tags = None
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM category_rules")
        rules = cursor.fetchall()
        conn.close()
    except Exception:
        rules = []
        
    text = normalize_text(f"{title} {description or ''}")
    
    for rule in rules:
        pattern = rule['pattern'].lower()
        rule_type = rule['rule_type']
        
        matched = False
        if rule_type == 'regex':
            try:
                if re.search(pattern, text):
                    matched = True
            except re.error:
                pass
        else:  # contains
            if pattern in text:
                matched = True
                
        if matched:
            category = rule['category']
            tags = rule['tags']
            break
            
    inferred = infer_category_and_income(title, amount, description)
    return {
        "category": category or inferred["category"],
        "tags": tags,
        "is_income": inferred["is_income"],
        "amount": inferred["amount"]
    }


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela de transações generalizadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT DEFAULT 'Outros',
            card_source TEXT,
            payment_method TEXT DEFAULT 'Manual',
            is_fixed INTEGER DEFAULT 0,
            is_income INTEGER DEFAULT 0,
            parent_id INTEGER,
            is_summary INTEGER DEFAULT 0,
            description TEXT,
            tags TEXT,
            card_id INTEGER,
            original_date TEXT,
            effective_date TEXT,
            source TEXT DEFAULT 'manual',
            external_id TEXT,
            account_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            closing_day INTEGER NOT NULL DEFAULT 1,
            due_day INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de categorias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT DEFAULT '#3b82f6'
        )
    ''')
    
    # Tabela de provisões (despesas/renda futura) - CRIAR PRIMEIRO
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS provisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            start_date TEXT,
            end_date TEXT,
            frequency TEXT DEFAULT 'once',
            is_income INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT 'Pix',
            status TEXT DEFAULT 'active',
            current_amount REAL DEFAULT 0.0,
            target_amount REAL DEFAULT 0.0
        )
    ''')
    
    # Tabela de orçamentos mensais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            limit_amount REAL NOT NULL,
            UNIQUE(month, category)
        )
    ''')
    
    # Tabela de metas financeiras
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            deadline TEXT,
            category TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    # Tabela de salários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salary_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            effective_date TEXT,
            gross_amount REAL,
            net_amount REAL
        )
    ''')

    # Tabela de regras de categorização automática
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            category TEXT NOT NULL,
            rule_type TEXT DEFAULT 'contains',
            tags TEXT
        )
    ''')

    # Tabela de simulações de compra
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            installments INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            category TEXT DEFAULT 'Compras',
            status TEXT DEFAULT 'pending'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pluggy_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT,
            item_id TEXT,
            date_from TEXT,
            date_to TEXT,
            inserted_count INTEGER DEFAULT 0,
            skipped_count INTEGER DEFAULT 0,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pluggy_account_aliases (
            account_id TEXT PRIMARY KEY,
            alias TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # Atualiza schema existente (apenas para colunas que podem faltar em tabelas já existentes)
    cursor.execute("PRAGMA table_info(transactions)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'is_income' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_income INTEGER DEFAULT 0")
    if 'description' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN description TEXT")
    if 'payment_method' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN payment_method TEXT DEFAULT 'Manual'")
    if 'parent_id' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN parent_id INTEGER")
    if 'is_summary' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_summary INTEGER DEFAULT 0")
    if 'tags' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN tags TEXT")
    if 'card_id' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN card_id INTEGER")
    if 'original_date' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN original_date TEXT")
    if 'effective_date' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN effective_date TEXT")
    if 'source' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN source TEXT DEFAULT 'manual'")
    if 'external_id' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN external_id TEXT")
    if 'account_id' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN account_id TEXT")

    cursor.execute("PRAGMA table_info(cards)")
    card_columns = {row[1] for row in cursor.fetchall()}
    if 'closing_day' not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN closing_day INTEGER NOT NULL DEFAULT 1")
    if 'due_day' not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN due_day INTEGER NOT NULL DEFAULT 1")
    if 'is_active' not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN is_active INTEGER DEFAULT 1")
    if 'created_at' not in card_columns:
        cursor.execute("ALTER TABLE cards ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")

    repair_card_transaction_signs(cursor)
    
    # Inserir categorias padrão se não existirem
    for cat in DEFAULT_CATEGORIES:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
    
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()

# ============ MODELOS PYDANTIC ============

class AuthSchema(BaseModel):
    email: str
    password: str

class TransactionSchema(BaseModel):
    date: str
    title: str
    amount: float
    category: str = "Outros"
    card_source: Optional[str] = "Manual"
    payment_method: Optional[str] = "Manual"
    is_fixed: Optional[int] = 0
    is_income: Optional[int] = 0
    parent_id: Optional[int] = None
    is_summary: Optional[int] = 0
    description: Optional[str] = None
    tags: Optional[str] = None

class TransactionUpdateSchema(BaseModel):
    date: Optional[str] = None
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    card_source: Optional[str] = None
    payment_method: Optional[str] = None
    is_fixed: Optional[int] = None
    is_income: Optional[int] = None
    parent_id: Optional[int] = None
    is_summary: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[str] = None

class CategorySchema(BaseModel):
    name: str
    color: Optional[str] = "#3b82f6"

class ProvisionSchema(BaseModel):
    title: str
    amount: float
    category: str
    start_date: str
    end_date: Optional[str] = None
    frequency: str = "once"  # once, weekly, monthly, yearly
    is_income: int = 0
    payment_method: Optional[str] = "Pix"
    status: str = "active"
    current_amount: Optional[float] = 0.0
    target_amount: Optional[float] = 0.0

class SalaryPlanSchema(BaseModel):
    effective_date: Optional[str] = None
    gross_amount: float
    net_amount: Optional[float] = None

class BudgetSchema(BaseModel):
    month: str  # formato: YYYY-MM
    category: str
    limit_amount: float

class GoalSchema(BaseModel):
    name: str
    target_amount: float
    deadline: str
    category: Optional[str] = None
    status: str = "active"

class GoalUpdateSchema(BaseModel):
    current_amount: Optional[float] = None
    add_amount: Optional[float] = None
    status: Optional[str] = None

class DashboardSchema(BaseModel):
    total_income: float
    total_expense: float
    balance: float
    by_category: dict
    monthly_balance: dict
    expenses_by_category: dict

class CategoryRuleSchema(BaseModel):
    pattern: str
    category: str
    rule_type: str = "contains"
    tags: Optional[str] = None

class PurchaseSimulationSchema(BaseModel):
    title: str
    amount: float
    installments: int
    start_date: str
    category: Optional[str] = "Compras"

class FundSchema(BaseModel):
    amount: float

class PluggySyncSchema(BaseModel):
    item_id: Optional[str] = None
    item_ids: Optional[List[str]] = None
    account_ids: Optional[List[str]] = None
    account_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

class PluggyAccountAliasSchema(BaseModel):
    account_id: str
    alias: str

# ============ ENDPOINTS - TRANSAÇÕES ============

class CardSchema(BaseModel):
    name: str
    closing_day: int
    due_day: int


@app.get("/api/auth/status")
def auth_status(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "", 1).strip() if auth_header.startswith("Bearer ") else ""
    return {"has_user": users_count() > 0, "authenticated": bool(decode_auth_token(token))}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/auth/register")
def auth_register(payload: AuthSchema):
    email = payload.email.strip().lower()
    if not email or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Informe email e senha com pelo menos 6 caracteres")
    if users_count() > 0:
        raise HTTPException(status_code=403, detail="Usuario inicial ja cadastrado")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, password_hash(payload.password))
    )
    conn.commit()
    cursor.execute("SELECT id, email FROM users WHERE email = ?", (email,))
    user = dict(cursor.fetchone())
    conn.close()
    return {"token": create_auth_token(user), "user": user}


@app.post("/api/auth/login")
def auth_login(payload: AuthSchema):
    email = payload.email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha invalidos")
    user = {"id": row["id"], "email": row["email"]}
    return {"token": create_auth_token(user), "user": user}


def get_pluggy_api_key(force_auth: bool = False) -> str:
    api_key = env_value("PLUGGY_API_KEY")
    if api_key and not force_auth:
        if api_key.lower().startswith("bearer "):
            api_key = api_key.split(" ", 1)[1].strip()
        return api_key

    cached_key = PLUGGY_API_KEY_CACHE.get("value")
    expires_at = PLUGGY_API_KEY_CACHE.get("expires_at")
    if cached_key and expires_at and datetime.now() < expires_at:
        return cached_key

    client_id = env_value("PLUGGY_CLIENT_ID")
    client_secret = env_value("PLUGGY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="Configure PLUGGY_API_KEY or PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET")

    try:
        res = requests.post(
            f"{PLUGGY_BASE_URL}/auth",
            json={"clientId": client_id, "clientSecret": client_secret},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao autenticar na Pluggy: {exc}")

    if res.status_code >= 400:
        raise HTTPException(status_code=res.status_code, detail=res.text)

    data = res.json()
    api_key = data.get("apiKey") or data.get("accessToken") or data.get("token")
    if not api_key:
        raise HTTPException(status_code=502, detail="Resposta de autenticação da Pluggy sem apiKey")
    PLUGGY_API_KEY_CACHE["value"] = api_key
    PLUGGY_API_KEY_CACHE["expires_at"] = datetime.now() + timedelta(minutes=45)
    return api_key


def pluggy_request(path: str, params: Optional[dict] = None, method: str = "GET", payload: Optional[dict] = None):
    headers = {"X-API-KEY": get_pluggy_api_key()}
    url = f"{PLUGGY_BASE_URL}{path}"
    try:
        res = requests.request(method, url, params=params, json=payload, headers=headers, timeout=60)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar Pluggy: {exc}")
    if res.status_code in (401, 403) and env_value("PLUGGY_CLIENT_ID") and env_value("PLUGGY_CLIENT_SECRET"):
        PLUGGY_API_KEY_CACHE["value"] = ""
        headers = {"X-API-KEY": get_pluggy_api_key(force_auth=True)}
        try:
            res = requests.request(method, url, params=params, json=payload, headers=headers, timeout=60)
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Erro ao chamar Pluggy: {exc}")
    if res.status_code >= 400:
        raise HTTPException(status_code=res.status_code, detail=res.text)
    return res.json()


def pluggy_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("results") or data.get("items") or data.get("data") or []
    return []


def parse_pluggy_item_ids(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def configured_pluggy_item_ids(explicit_item_id: Optional[str] = None, explicit_item_ids: Optional[List[str]] = None) -> List[str]:
    item_ids: List[str] = []
    if explicit_item_id:
        item_ids.extend(parse_pluggy_item_ids(explicit_item_id))
    if explicit_item_ids:
        item_ids.extend([item.strip() for item in explicit_item_ids if item and item.strip()])
    if item_ids:
        return list(dict.fromkeys(item_ids))

    item_ids.extend(parse_pluggy_item_ids(env_value("PLUGGY_ITEM_IDS")))
    legacy_item_id = env_value("PLUGGY_ITEM_ID")
    if legacy_item_id:
        item_ids.append(legacy_item_id)
    return list(dict.fromkeys(item_ids))


def list_pluggy_accounts_for_item(item_id: str, account_type: Optional[str] = None) -> List[dict]:
    params = {"itemId": item_id}
    if account_type:
        params["type"] = account_type
    accounts = pluggy_items(pluggy_request("/accounts", params=params))
    normalized = []
    for account in accounts:
        if isinstance(account, dict):
            normalized.append({**account, "itemId": account.get("itemId") or item_id})
    return normalized


def pluggy_alias_map(cursor) -> dict:
    cursor.execute("SELECT account_id, alias FROM pluggy_account_aliases")
    return {row[0]: row[1] for row in cursor.fetchall()}


def pluggy_default_account_name(account: dict) -> str:
    return (
        account.get("name")
        or account.get("marketingName")
        or account.get("number")
        or account.get("id")
        or "Conta Pluggy"
    )


def upsert_pluggy_auto_alias(cursor, account: dict):
    account_id = account.get("id")
    if not account_id:
        return
    alias = pluggy_default_account_name(account)
    if not alias or alias == account_id:
        return
    cursor.execute("SELECT alias FROM pluggy_account_aliases WHERE account_id = ?", (account_id,))
    if cursor.fetchone():
        return
    cursor.execute(
        "INSERT INTO pluggy_account_aliases (account_id, alias, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (account_id, alias)
    )
    apply_pluggy_alias_to_transactions(cursor, account_id, alias)


def pluggy_account_alias(cursor, account_id: Optional[str]) -> Optional[str]:
    if not account_id:
        return None
    cursor.execute("SELECT alias FROM pluggy_account_aliases WHERE account_id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return row["alias"] if isinstance(row, sqlite3.Row) else row[0]


def apply_pluggy_alias_to_transactions(cursor, account_id: str, alias: str):
    cursor.execute(
        "UPDATE transactions SET card_source = ? WHERE source = 'pluggy' AND account_id = ?",
        (alias, account_id)
    )


def pluggy_category_name(tx: dict) -> Optional[str]:
    category = tx.get("category")
    if isinstance(category, dict):
        return category.get("description") or category.get("name")
    if isinstance(category, str):
        return category
    return None


PLUGGY_NEUTRAL_CATEGORY_KEYWORDS = [
    "credit card payment",
    "same person transfer",
    "transfer - internal",
    "cashback",
    "refund",
]

PLUGGY_NEUTRAL_TITLE_KEYWORDS = [
    "parcelamento de fatura",
    "credito de parcelamento",
    "credito parcelamento",
    "desconto de antecipacao",
    "estorno",
    "reembolso",
    "cashback",
    "pagamento recebido",
    "pagamento de fatura",
    "debito automatico fatura",
    "faturaitau",
    "entrada de parcelamento cartao",
    "entrada de parcelamento de cartao",
]

PLUGGY_LOCAL_CATEGORY_KEYWORDS = [
    ("Renda", ["salary", "salario", "pagto salario", "pagamento salario"]),
    ("Investimentos", ["proceeds", "dividends", "rendimentos", "investimentos"]),
    ("Alimentação", ["food", "restaurant", "groceries", "meal", "ifood", "delivery", "mercado", "supermercado", "padaria"]),
    ("Transporte", ["taxi", "ride-hailing", "transport", "uber", "99", "fuel", "gasolina", "combustivel"]),
    ("Moradia", ["housing", "rent", "condominio", "energia", "internet", "utilities", "habitacao"]),
    ("Saúde", ["health", "pharmacy", "doctor", "dentist", "wellness", "fitness", "farmacia", "dentista"]),
    ("Educação", ["education", "school", "course", "faculdade", "curso"]),
    ("Lazer", ["entertainment", "streaming", "video streaming", "music", "game", "bar", "cinema"]),
    ("Compras", ["shopping", "clothing", "electronics", "marketplace", "amazon", "mercadolivre"]),
    ("Dívidas", ["loans", "financing", "loan", "crediario", "refinan", "renegociacao"]),
]


def normalize_text(value: Optional[str]) -> str:
    text = str(value or "").casefold()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def pluggy_text_blob(tx: dict) -> str:
    return " ".join(
        normalize_text(value)
        for value in [
            pluggy_transaction_title(tx),
            tx.get("descriptionRaw"),
            pluggy_category_name(tx),
            tx.get("type"),
            tx.get("operationType"),
        ]
    )


def should_skip_pluggy_transaction(tx: dict, raw_amount: float) -> Optional[str]:
    title = normalize_text(pluggy_transaction_title(tx))
    category = normalize_text(pluggy_category_name(tx))
    blob = pluggy_text_blob(tx)

    if any(keyword in category for keyword in PLUGGY_NEUTRAL_CATEGORY_KEYWORDS):
        return "neutral_category"
    if any(keyword in blob for keyword in PLUGGY_NEUTRAL_TITLE_KEYWORDS):
        return "neutral_title"

    looks_like_transfer = "transfer" in category or "transferencia" in title or "pix recebido" in title
    looks_like_real_income = any(keyword in blob for keyword in ["salary", "salario", "rendimentos", "dividends", "investimentos"])
    if looks_like_transfer and not looks_like_real_income:
        return "income_transfer"

    return None


def pluggy_local_category(tx: dict, is_income: int) -> str:
    if is_income:
        blob = pluggy_text_blob(tx)
        if any(keyword in blob for keyword in ["rendimentos", "dividends", "investimentos", "proceeds"]):
            return "Investimentos"
        return "Renda"

    blob = pluggy_text_blob(tx)
    for local_category, keywords in PLUGGY_LOCAL_CATEGORY_KEYWORDS:
        if any(keyword in blob for keyword in keywords):
            return local_category
    inferred = auto_categorize_transaction(pluggy_transaction_title(tx), abs(float(tx.get("amount") or 0)))
    return inferred["category"] or "Outros"


def pluggy_transaction_title(tx: dict) -> str:
    merchant_name = tx.get("merchant", {}).get("name") if isinstance(tx.get("merchant"), dict) else None
    return (
        tx.get("description")
        or tx.get("descriptionRaw")
        or merchant_name
        or "Transação Pluggy"
    )


def pluggy_transaction_date(tx: dict) -> str:
    raw_date = tx.get("date") or tx.get("postedDate") or tx.get("createdAt") or datetime.now().strftime("%Y-%m-%d")
    return str(raw_date)[:10]


def pluggy_is_income(tx: dict, amount: float) -> int:
    blob = pluggy_text_blob(tx)
    if any(keyword in blob for keyword in ["salary", "salario", "pagto salario", "pagamento salario"]):
        return 1
    if any(keyword in blob for keyword in ["rendimentos", "dividends", "proceeds interests", "valor recebido de investimentos"]):
        return 1
    tx_type = str(tx.get("type") or tx.get("operationType") or "").upper()
    if tx_type in {"CREDIT", "INFLOW"}:
        return 1
    if tx_type in {"DEBIT", "OUTFLOW"}:
        return 0
    return 1 if amount > 0 else 0


def sync_pluggy_account_transactions(account_id: str, item_id: Optional[str], date_from: Optional[str], date_to: Optional[str]):
    inserted = 0
    skipped = 0
    after = None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    while True:
        params = {"accountId": account_id}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if after:
            params["after"] = after

        data = pluggy_request("/v2/transactions", params=params)
        transactions = pluggy_items(data)

        for tx in transactions:
            external_id = tx.get("id")
            if not external_id:
                skipped += 1
                continue

            cursor.execute(
                "SELECT id FROM transactions WHERE source = 'pluggy' AND external_id = ? AND account_id = ?",
                (external_id, account_id)
            )
            if cursor.fetchone():
                skipped += 1
                continue

            raw_amount = float(tx.get("amount") or 0)
            if raw_amount == 0:
                skipped += 1
                continue
            if should_skip_pluggy_transaction(tx, raw_amount):
                skipped += 1
                continue

            title = pluggy_transaction_title(tx)
            tx_date = pluggy_transaction_date(tx)
            is_income = pluggy_is_income(tx, raw_amount)
            amount = abs(raw_amount)
            category = pluggy_local_category(tx, is_income)
            display_account = pluggy_account_alias(cursor, account_id) or tx.get("accountId") or account_id

            cursor.execute(
                """INSERT INTO transactions
                (date, title, amount, category, card_source, payment_method, is_fixed, is_income,
                 description, tags, source, external_id, account_id)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'pluggy', ?, ?)""",
                (
                    tx_date,
                    title,
                    amount,
                    category or "Outros",
                    display_account,
                    "Pluggy",
                    is_income,
                    tx.get("descriptionRaw"),
                    pluggy_category_name(tx),
                    external_id,
                    account_id,
                )
            )
            inserted += 1

        after = (data.get("next") or data.get("nextCursor") or data.get("after")) if isinstance(data, dict) else None
        if not after or not transactions:
            break

    cursor.execute(
        "INSERT INTO pluggy_sync_log (account_id, item_id, date_from, date_to, inserted_count, skipped_count) VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, item_id, date_from, date_to, inserted, skipped)
    )
    conn.commit()
    conn.close()
    return {"account_id": account_id, "inserted": inserted, "skipped": skipped}


@app.get("/api/pluggy/status")
def pluggy_status():
    item_ids = configured_pluggy_item_ids()
    api_key = env_value("PLUGGY_API_KEY")
    client_id = env_value("PLUGGY_CLIENT_ID")
    client_secret = env_value("PLUGGY_CLIENT_SECRET")
    return {
        "configured": bool(api_key or (client_id and client_secret)),
        "has_api_key": bool(api_key),
        "has_client_credentials": bool(client_id and client_secret),
        "has_item_id": bool(item_ids),
        "has_item_ids": bool(item_ids),
        "item_ids_count": len(item_ids),
        "base_url": PLUGGY_BASE_URL,
    }


@app.get("/api/pluggy/accounts")
def pluggy_accounts(item_id: Optional[str] = None, item_ids: Optional[str] = None, account_type: Optional[str] = None):
    configured_ids = configured_pluggy_item_ids(item_id, parse_pluggy_item_ids(item_ids))
    if not configured_ids:
        raise HTTPException(status_code=400, detail="Informe item_ids ou configure PLUGGY_ITEM_IDS")

    accounts = []
    for configured_id in configured_ids:
        accounts.extend(list_pluggy_accounts_for_item(configured_id, account_type))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for account in accounts:
        upsert_pluggy_auto_alias(cursor, account)
    conn.commit()
    aliases = pluggy_alias_map(cursor)
    conn.close()

    for account in accounts:
        account_id = account.get("id")
        if account_id in aliases:
            account["alias"] = aliases[account_id]
    return {"results": accounts, "item_ids": configured_ids}


@app.get("/api/pluggy/account-aliases")
def get_pluggy_account_aliases():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.account_id, a.alias, COUNT(t.id) as transaction_count
        FROM pluggy_account_aliases a
        LEFT JOIN transactions t ON t.source = 'pluggy' AND t.account_id = a.account_id
        GROUP BY a.account_id, a.alias
        ORDER BY a.alias
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/pluggy/account-aliases")
def set_pluggy_account_alias(payload: PluggyAccountAliasSchema):
    account_id = payload.account_id.strip()
    alias = payload.alias.strip()
    if not account_id or not alias:
        raise HTTPException(status_code=400, detail="Informe account_id e alias")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pluggy_account_aliases (account_id, alias, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(account_id) DO UPDATE SET
            alias = excluded.alias,
            updated_at = CURRENT_TIMESTAMP
        """,
        (account_id, alias)
    )
    apply_pluggy_alias_to_transactions(cursor, account_id, alias)
    updated_transactions = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "success", "account_id": account_id, "alias": alias, "updated_transactions": updated_transactions}


@app.delete("/api/pluggy/account-aliases/{account_id}")
def delete_pluggy_account_alias(account_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pluggy_account_aliases WHERE account_id = ?", (account_id,))
    cursor.execute(
        "UPDATE transactions SET card_source = account_id WHERE source = 'pluggy' AND account_id = ?",
        (account_id,)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.post("/api/pluggy/sync")
def pluggy_sync(payload: PluggySyncSchema):
    item_ids = configured_pluggy_item_ids(payload.item_id, payload.item_ids)
    account_ids = payload.account_ids or []
    sync_targets = []

    if not account_ids:
        if not item_ids:
            raise HTTPException(status_code=400, detail="Informe account_ids ou configure PLUGGY_ITEM_IDS")
        for item_id in item_ids:
            for account in list_pluggy_accounts_for_item(item_id, payload.account_type):
                if account.get("id"):
                    sync_targets.append({"account_id": account["id"], "item_id": item_id})
    else:
        default_item_id = item_ids[0] if item_ids else None
        sync_targets = [{"account_id": account_id, "item_id": default_item_id} for account_id in account_ids]

    if not sync_targets:
        raise HTTPException(status_code=400, detail="Nenhuma conta Pluggy encontrada para sincronizar")

    results = [
        sync_pluggy_account_transactions(target["account_id"], target["item_id"], payload.date_from, payload.date_to)
        for target in sync_targets
    ]
    return {
        "status": "success",
        "total_inserted": sum(item["inserted"] for item in results),
        "total_skipped": sum(item["skipped"] for item in results),
        "results": results,
    }


@app.get("/api/cards")
def get_cards():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cards WHERE is_active = 1 ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/cards")
def add_card(card: CardSchema):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO cards (name, closing_day, due_day) VALUES (?, ?, ?)",
            (card.name, card.closing_day, card.due_day)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Cartão já existe")
    finally:
        conn.close()
    return {"status": "success"}

@app.put("/api/cards/{card_id}")
def update_card(card_id: int, card: CardSchema):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE cards SET name = ?, closing_day = ?, due_day = ? WHERE id = ?",
        (card.name, card.closing_day, card.due_day, card_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/transactions")
def get_transactions(
    month: Optional[str] = None,
    category: Optional[str] = None,
    payment_method: Optional[str] = None,
    is_fixed: Optional[int] = None
):
    """Retorna todas as transações ou filtradas por parâmetros"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM transactions"
    conditions = []
    params = []

    if month:
        conditions.append("date LIKE ?")
        params.append(f"{month}%")
    if category:
        conditions.append("category = ?")
        params.append(category)
    if payment_method:
        conditions.append("payment_method = ?")
        params.append(payment_method)
    if is_fixed is not None:
        conditions.append("is_fixed = ?")
        params.append(is_fixed)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY date DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    aliases = pluggy_alias_map(cursor)
    conn.close()
    transactions = []
    for row in rows:
        item = dict(row)
        account_id = item.get("account_id")
        if item.get("source") == "pluggy" and account_id in aliases:
            item["card_source"] = aliases[account_id]
        transactions.append(item)
    return transactions

@app.post("/api/transactions")
def add_transaction(tx: TransactionSchema):
    """Adiciona uma nova transação"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    category = tx.category
    tags = tx.tags
    is_income = tx.is_income
    amount = tx.amount
    
    if category == "Outros":
        inferred = auto_categorize_transaction(tx.title, tx.amount, tx.description)
        category = inferred["category"]
        tags = inferred["tags"] or tags
        is_income = inferred["is_income"]
        amount = inferred["amount"]
        
    cursor.execute(
        "INSERT INTO transactions (date, title, amount, category, card_source, payment_method, is_fixed, is_income, description, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tx.date, tx.title, amount, category, tx.card_source, tx.payment_method, tx.is_fixed, is_income, tx.description, tags)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: int, tx: TransactionUpdateSchema):
    """Edita uma transação existente"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    fields = []
    values = []
    if tx.date is not None:
        fields.append("date = ?")
        values.append(tx.date)
    if tx.title is not None:
        fields.append("title = ?")
        values.append(tx.title)
    if tx.amount is not None:
        fields.append("amount = ?")
        values.append(tx.amount)
    if tx.category is not None:
        fields.append("category = ?")
        values.append(tx.category)
    if tx.card_source is not None:
        fields.append("card_source = ?")
        values.append(tx.card_source)
    if tx.payment_method is not None:
        fields.append("payment_method = ?")
        values.append(tx.payment_method)
    if tx.is_fixed is not None:
        fields.append("is_fixed = ?")
        values.append(tx.is_fixed)
    if tx.is_income is not None:
        fields.append("is_income = ?")
        values.append(tx.is_income)
    if tx.description is not None:
        fields.append("description = ?")
        values.append(tx.description)
    if tx.tags is not None:
        fields.append("tags = ?")
        values.append(tx.tags)

    if fields:
        values.append(tx_id)
        cursor.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", tuple(values))
        conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/transactions/{tx_id}/move-next-month")
def move_transaction_next_month(tx_id: int):
    """Move uma transação para o próximo mês"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, parent_id, date FROM transactions WHERE id = ?", (tx_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    if row['parent_id']:
        tx_id = row['parent_id']

    cursor.execute("SELECT id, date FROM transactions WHERE id = ? OR parent_id = ?", (tx_id, tx_id))
    rows_to_move = cursor.fetchall()
    if not rows_to_move:
        conn.close()
        raise HTTPException(status_code=404, detail="Transações relacionadas não encontradas")

    for item in rows_to_move:
        try:
            current_date = datetime.strptime(item['date'][:10], "%Y-%m-%d").date()
        except ValueError:
            conn.close()
            raise HTTPException(status_code=400, detail="Data inválida")

        next_month = current_date.replace(day=28) + timedelta(days=4)
        target_month_first = next_month.replace(day=1)
        last_day_next_month = calendar.monthrange(target_month_first.year, target_month_first.month)[1]
        new_date = target_month_first.replace(day=min(current_date.day, last_day_next_month))
        cursor.execute("UPDATE transactions SET date = ? WHERE id = ?", (new_date.strftime("%Y-%m-%d"), item['id']))

    next_month = current_date.replace(day=28) + timedelta(days=4)
    target_month_first = next_month.replace(day=1)
    last_day_next_month = calendar.monthrange(target_month_first.year, target_month_first.month)[1]
    new_date = target_month_first.replace(day=min(current_date.day, last_day_next_month))

    cursor.execute("UPDATE transactions SET date = ? WHERE id = ?", (new_date.strftime("%Y-%m-%d"), tx_id))
    conn.commit()
    conn.close()
    return {"status": "success", "new_date": new_date.strftime("%Y-%m-%d")}

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: int):
    """Deleta uma transação"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ============ ENDPOINTS - CATEGORIAS ============

@app.get("/api/categories")
def get_categories():
    """Retorna todas as categorias"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/categories")
def add_category(cat: CategorySchema):
    """Adiciona uma nova categoria"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO categories (name, color) VALUES (?, ?)",
            (cat.name, cat.color)
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Categoria já existe")

# ============ ENDPOINTS - DASHBOARD & BALANÇO ============

def parse_date_str(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%d/%m/%Y")
        except ValueError:
            return None


def month_bounds(month: str):
    year = int(month[:4])
    month_num = int(month[5:7])
    start = datetime(year, month_num, 1)
    if month_num == 12:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, month_num + 1, 1) - timedelta(days=1)
    return start.date(), end.date()


def provision_occurrences_for_month(month: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM provisions WHERE status = 'active'")
    rows = cursor.fetchall()
    conn.close()

    start_month, end_month = month_bounds(month)
    occurrences = []

    for row in rows:
        start_date = parse_date_str(row['start_date'])
        if not start_date:
            continue
        end_date = parse_date_str(row['end_date']) if row['end_date'] else None
        frequency = (row['frequency'] or 'once').lower()
        amount = row['amount']
        if row['is_income'] == 1:
            amount = abs(amount)
        else:
            amount = -abs(amount)

        def is_within_range(dt):
            if dt < start_date.date():
                return False
            if end_date and dt > end_date.date():
                return False
            return start_month <= dt <= end_month

        if frequency == 'once':
            if is_within_range(start_date.date()):
                occurrences.append({
                    'title': row['title'],
                    'amount': amount,
                    'category': row['category'] or 'Outros',
                    'payment_method': row['payment_method'],
                    'date': start_date.strftime('%Y-%m-%d'),
                })
        elif frequency == 'monthly':
            try:
                occurrence = start_date.replace(year=start_month.year, month=start_month.month)
            except ValueError:
                continue
            if is_within_range(occurrence.date()):
                occurrences.append({
                    'title': row['title'],
                    'amount': amount,
                    'category': row['category'] or 'Outros',
                    'payment_method': row['payment_method'],
                    'date': occurrence.strftime('%Y-%m-%d'),
                })
        elif frequency == 'yearly':
            try:
                occurrence = start_date.replace(year=start_month.year)
            except ValueError:
                continue
            if is_within_range(occurrence.date()):
                occurrences.append({
                    'title': row['title'],
                    'amount': amount,
                    'category': row['category'] or 'Outros',
                    'payment_method': row['payment_method'],
                    'date': occurrence.strftime('%Y-%m-%d'),
                })
        elif frequency == 'weekly':
            current = start_date.date()
            while current <= end_month and (not end_date or current <= end_date.date()):
                if current >= start_month and current <= end_month:
                    occurrences.append({
                        'title': row['title'],
                        'amount': amount,
                        'category': row['category'] or 'Outros',
                        'payment_method': row['payment_method'],
                        'date': current.strftime('%Y-%m-%d'),
                    })
                current += timedelta(days=7)

    return occurrences


def transaction_totals_for_month(cursor, month: Optional[str] = None):
    if month:
        cursor.execute(
            "SELECT amount, is_income, title, card_source, payment_method FROM transactions "
            "WHERE date LIKE ? AND parent_id IS NULL AND is_summary = 0",
            (f"{month}%",)
        )
    else:
        cursor.execute(
            "SELECT amount, is_income, title, card_source, payment_method FROM transactions "
            "WHERE parent_id IS NULL AND is_summary = 0"
        )

    transaction_income = 0.0
    transaction_expense = 0.0
    card_credits = 0.0
    for row in cursor.fetchall():
        is_card = is_known_card_source(row['card_source']) or is_known_card_source(row['payment_method'])
        if row['is_income'] == 1 and is_card and is_card_payment(row['title'] or ""):
            continue
        if row['is_income'] == 1 and is_card:
            card_credits += row['amount'] or 0
        elif row['is_income'] == 1:
            transaction_income += row['amount'] or 0
        else:
            transaction_expense += row['amount'] or 0

    transaction_expense -= card_credits
    return transaction_income, transaction_expense


def provision_totals_for_month(month: str):
    occurrences = provision_occurrences_for_month(month)
    income = sum(occ['amount'] for occ in occurrences if occ['amount'] > 0)
    expense = sum(-occ['amount'] for occ in occurrences if occ['amount'] < 0)
    return income, expense


def carried_balance_before_month(cursor, month: str, current_salary: float):
    cursor.execute(
        """
        SELECT DISTINCT substr(date, 1, 7) as month
        FROM transactions
        WHERE parent_id IS NULL
          AND is_summary = 0
          AND substr(date, 1, 7) < ?
        ORDER BY month
        """,
        (month,)
    )
    months = [row['month'] for row in cursor.fetchall()]

    balance = 0.0
    for prev_month in months:
        tx_income, tx_expense = transaction_totals_for_month(cursor, prev_month)
        prov_income, prov_expense = provision_totals_for_month(prev_month)
        balance += (current_salary + tx_income + prov_income) - (tx_expense + prov_expense)

    return balance

@app.get("/api/dashboard")
def get_dashboard(month: Optional[str] = None):
    """Retorna resumo financeiro geral ou de um mês específico"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Buscar salário atual
    cursor.execute("SELECT gross_amount, net_amount FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    row_salary = cursor.fetchone()
    current_salary = 0
    if row_salary:
        current_salary = row_salary['net_amount'] if row_salary['net_amount'] is not None else (row_salary['gross_amount'] or 0)
    
    if month:
        where_clause = "WHERE date LIKE ? AND parent_id IS NULL"
        param = (f"{month}%",)
    else:
        where_clause = "WHERE parent_id IS NULL"
        param = ()
    
    # Total de renda e despesa (transações reais)
    tx_where_clause = where_clause + " AND is_summary = 0"
    cursor.execute(
        f"SELECT amount, is_income, title, card_source, payment_method FROM transactions {tx_where_clause}",
        param
    )
    transaction_income = 0.0
    transaction_expense = 0.0
    card_credits = 0.0
    for row in cursor.fetchall():
        is_card = is_known_card_source(row['card_source']) or is_known_card_source(row['payment_method'])
        if row['is_income'] == 1 and is_card and is_card_payment(row['title'] or ""):
            continue
        if row['is_income'] == 1 and is_card:
            card_credits += row['amount'] or 0
        elif row['is_income'] == 1:
            transaction_income += row['amount'] or 0
        else:
            transaction_expense += row['amount'] or 0
    transaction_expense -= card_credits
    
    # Se não tem transações de renda no mês, usa o salário cadastrado
    # Rendas lancadas manualmente sao ganhos extras; nao substituem o salario.
    
    # ========== Somar provisões ativas ==========
    cursor.execute("SELECT * FROM provisions WHERE status = 'active' AND is_income = 0")
    active_provisions = cursor.fetchall()
    
    provisions_expense = 0.0
    provisions_by_category = {}
    
    for prov in active_provisions:
        prov_start_date = prov['start_date']
        prov_end_date = prov['end_date']
        prov_frequency = prov['frequency'] or 'monthly'
        prov_amount = prov['amount']
        prov_category = prov['category'] or 'Outros'
        
        if month:
            # Verificar se a provisão se aplica ao mês específico
            year = int(month[:4])
            month_num = int(month[5:7])
            
            try:
                start_date = datetime.strptime(prov_start_date[:10], "%Y-%m-%d")
            except:
                start_date = datetime(year, month_num, 1)
            
            is_active_in_month = False
            
            if prov_frequency == 'once':
                if start_date.year == year and start_date.month == month_num:
                    is_active_in_month = True
            elif prov_frequency == 'monthly':
                if start_date.year < year or (start_date.year == year and start_date.month <= month_num):
                    if prov_end_date:
                        try:
                            end_date = datetime.strptime(prov_end_date[:10], "%Y-%m-%d")
                            if end_date.year > year or (end_date.year == year and end_date.month >= month_num):
                                is_active_in_month = True
                        except:
                            is_active_in_month = True
                    else:
                        is_active_in_month = True
            elif prov_frequency == 'yearly':
                if start_date.month == month_num:
                    is_active_in_month = True
            elif prov_frequency == 'weekly':
                is_active_in_month = True
            
            if is_active_in_month:
                provisions_expense += prov_amount
                provisions_by_category[prov_category] = provisions_by_category.get(prov_category, 0) + prov_amount
        else:
            # Sem mês específico, média mensal
            if prov_frequency == 'monthly':
                provisions_expense += prov_amount
                provisions_by_category[prov_category] = provisions_by_category.get(prov_category, 0) + prov_amount
            elif prov_frequency == 'yearly':
                provisions_expense += prov_amount / 12
                provisions_by_category[prov_category] = provisions_by_category.get(prov_category, 0) + (prov_amount / 12)
            elif prov_frequency == 'weekly':
                provisions_expense += prov_amount * 4.33
                provisions_by_category[prov_category] = provisions_by_category.get(prov_category, 0) + (prov_amount * 4.33)
    
    # Total de despesas (transações + provisões)
    total_expense = transaction_expense + provisions_expense
    total_income = current_salary + transaction_income
    
    # Se a renda das transações for 0 mas tem salário, usa o salário
    # Ganhos pontuais entram por cima do salario cadastrado.
    
    balance = total_income - total_expense

    previous_balance = 0.0
    if month:
        previous_balance = carried_balance_before_month(cursor, month, current_salary)

    balance_with_carryover = balance + previous_balance
    
    # Despesas por categoria (incluindo provisões)
    if month:
        cursor.execute(
            "SELECT category, title, is_income, card_source, payment_method, amount as total FROM transactions WHERE date LIKE ? AND parent_id IS NULL AND is_summary = 0",
            (f"{month}%",)
        )
    else:
        cursor.execute(
            "SELECT category, title, is_income, card_source, payment_method, amount as total FROM transactions WHERE parent_id IS NULL AND is_summary = 0"
        )
    expenses_by_category = {}
    for row in cursor.fetchall():
        category = row['category'] or 'Outros'
        is_card = is_known_card_source(row['card_source']) or is_known_card_source(row['payment_method'])
        if row['is_income'] == 1 and is_card and is_card_payment(row['title'] or ""):
            continue
        if row['is_income'] == 0:
            expenses_by_category[category] = expenses_by_category.get(category, 0) + (row['total'] or 0)
        elif is_card:
            expenses_by_category[category] = expenses_by_category.get(category, 0) - (row['total'] or 0)
    expenses_by_category = {cat: amount for cat, amount in expenses_by_category.items() if amount > 0.01}
    
    for cat, amount in provisions_by_category.items():
        expenses_by_category[cat] = expenses_by_category.get(cat, 0) + amount
    
    # Gastos fixos (transações fixas + provisões)
    if month:
        cursor.execute(
            "SELECT SUM(amount) as fixed_transaction_total FROM transactions WHERE is_fixed = 1 AND is_income = 0 AND date LIKE ? AND parent_id IS NULL",
            (f"{month}%",)
        )
    else:
        cursor.execute(
            "SELECT SUM(amount) as fixed_transaction_total FROM transactions WHERE is_fixed = 1 AND is_income = 0 AND parent_id IS NULL"
        )
    fixed_tx_row = cursor.fetchone()
    fixed_transaction_total = fixed_tx_row['fixed_transaction_total'] or 0
    
    fixed_expense_total = fixed_transaction_total + provisions_expense
    
    fixed_expenses_by_category = {}
    if month:
        cursor.execute(
            "SELECT category, SUM(amount) as total FROM transactions WHERE is_fixed = 1 AND is_income = 0 AND date LIKE ? AND parent_id IS NULL GROUP BY category",
            (f"{month}%",)
        )
    else:
        cursor.execute(
            "SELECT category, SUM(amount) as total FROM transactions WHERE is_fixed = 1 AND is_income = 0 AND parent_id IS NULL GROUP BY category"
        )
    for row in cursor.fetchall():
        category = row['category'] or 'Outros'
        fixed_expenses_by_category[category] = fixed_expenses_by_category.get(category, 0) + (row['total'] or 0)
    
    for cat, amount in provisions_by_category.items():
        fixed_expenses_by_category[cat] = fixed_expenses_by_category.get(cat, 0) + amount
    
    # Ring-fenced provisions
    cursor.execute("SELECT SUM(current_amount) FROM provisions WHERE status = 'active' AND is_income = 0")
    row_prov = cursor.fetchone()
    ring_fenced_total = row_prov[0] or 0.0
    available_to_spend = balance_with_carryover - ring_fenced_total
    
    conn.close()
    
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "expenses_by_category": expenses_by_category,
        "current_salary": current_salary,
        "fixed_expense_total": fixed_expense_total,
        "fixed_expenses_by_category": fixed_expenses_by_category,
        "projected_balance": total_income - total_expense,
        "previous_balance": previous_balance,
        "carryover_balance": balance_with_carryover,
        "residual_debt": abs(balance_with_carryover) if balance_with_carryover < 0 else 0.0,
        "ring_fenced_provisions_total": ring_fenced_total,
        "available_to_spend": available_to_spend
    }

def calculate_effective_date(original_date: str, closing_day: int, due_day: int) -> str:
    """
    Calcula a data de efeito (mês da fatura) baseado no dia de fechamento do cartão.
    Retorna data no formato YYYY-MM-DD (primeiro dia do mês de competência).
    """
    from datetime import datetime, timedelta
    dt = datetime.strptime(original_date, '%Y-%m-%d')
    
    # Se a compra for no dia de fechamento, considera como do mês atual? 
    # Tradicionalmente, compras no dia de fechamento entram na fatura do mês seguinte.
    # Ajuste conforme sua preferência.
    if dt.day <= closing_day:
        # Compra antes ou no fechamento -> fatura do mês atual (vencimento no próximo mês)
        # Mas para relatórios, queremos agrupar pelo mês da competência.
        # Vamos usar o mês da data original, mas armazenar também o mês da fatura.
        effective_month = dt.strftime('%Y-%m')
    else:
        # Compra após o fechamento -> fatura do mês seguinte
        next_month = dt.replace(day=1) + timedelta(days=32)
        effective_month = next_month.strftime('%Y-%m')
    
    # Retorna o primeiro dia do mês de competência
    return f"{effective_month}-01"

def calculate_billing_due_date(original_date: str, closing_day: int, due_day: int) -> str:
    """Return the card bill due date that should own this purchase."""
    dt = datetime.strptime(original_date, '%Y-%m-%d')
    if dt.day <= closing_day:
        bill_year = dt.year
        bill_month = dt.month
    else:
        next_month = dt.replace(day=1) + timedelta(days=32)
        bill_year = next_month.year
        bill_month = next_month.month

    last_day = calendar.monthrange(bill_year, bill_month)[1]
    return datetime(bill_year, bill_month, min(due_day, last_day)).strftime('%Y-%m-%d')

@app.get("/api/salary-plan")
def get_salary_plan():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"effective_date": None, "gross_amount": 0, "net_amount": 0}

@app.post("/api/salary-plan")
def set_salary_plan(plan: SalaryPlanSchema):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    effective_date = plan.effective_date or datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT id FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            "UPDATE salary_plan SET effective_date = ?, gross_amount = ?, net_amount = ? WHERE id = ?",
            (effective_date, plan.gross_amount, plan.net_amount, existing[0])
        )
    else:
        cursor.execute(
            "INSERT INTO salary_plan (effective_date, gross_amount, net_amount) VALUES (?, ?, ?)",
            (effective_date, plan.gross_amount, plan.net_amount)
        )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/monthly-summary")
def get_monthly_summary():
    """Retorna um resumo por mês"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                substr(date, 1, 7) as month,
                SUM(CASE WHEN is_income = 1 THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN is_income = 0 THEN amount ELSE 0 END) as expense
            FROM transactions
            WHERE parent_id IS NULL
            GROUP BY substr(date, 1, 7)
            ORDER BY month
        """)
        
        all_rows = cursor.fetchall()
        
        # Fetch current salary
        cursor.execute("SELECT gross_amount, net_amount FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
        row_salary = cursor.fetchone()
        current_salary = 0
        if row_salary:
            current_salary = row_salary['net_amount'] if row_salary['net_amount'] is not None else (row_salary['gross_amount'] or 0)
        
        # Buscar todas as provisões ativas
        cursor.execute("SELECT * FROM provisions WHERE status = 'active' AND is_income = 0")
        all_provisions = cursor.fetchall()
        
        result = {}

        running_balance = 0.0

        for row in all_rows:
            month = row['month']
            income = current_salary + (row['income'] or 0)
            expense = row['expense'] or 0
            previous_balance = running_balance
            
            # Adicionar despesas das provisões para este mês
            provisions_expense = 0
            year = int(month[:4])
            month_num = int(month[5:7])
            
            for prov in all_provisions:
                prov_start_date = prov['start_date']
                prov_end_date = prov['end_date']
                prov_frequency = prov['frequency'] or 'monthly'
                prov_amount = prov['amount']
                
                try:
                    start_date = datetime.strptime(prov_start_date[:10], "%Y-%m-%d")
                except:
                    continue
                
                is_active = False
                
                if prov_frequency == 'once':
                    if start_date.year == year and start_date.month == month_num:
                        is_active = True
                elif prov_frequency == 'monthly':
                    if start_date.year < year or (start_date.year == year and start_date.month <= month_num):
                        if prov_end_date:
                            try:
                                end_date = datetime.strptime(prov_end_date[:10], "%Y-%m-%d")
                                if end_date.year > year or (end_date.year == year and end_date.month >= month_num):
                                    is_active = True
                            except:
                                is_active = True
                        else:
                            is_active = True
                elif prov_frequency == 'yearly':
                    if start_date.month == month_num:
                        is_active = True
                
                if is_active:
                    provisions_expense += prov_amount
            
            total_expense = expense + provisions_expense
            month_balance = income - total_expense
            running_balance += month_balance
            result[month] = {
                "income": income,
                "expense": total_expense,
                "balance": month_balance,
                "planned_expense": provisions_expense,
                "projected_balance": month_balance,
                "previous_balance": previous_balance,
                "carryover_balance": running_balance,
                "residual_debt": abs(running_balance) if running_balance < 0 else 0.0
            }
        conn.close()
        return result
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/category-summary/{category}")
def get_category_summary(category: str, month: Optional[str] = None):
    """Retorna detalhes de gastos em uma categoria"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if month:
        cursor.execute(
            "SELECT * FROM transactions WHERE category = ? AND date LIKE ? AND is_income = 0 ORDER BY date DESC",
            (category, f"{month}%")
        )
    else:
        cursor.execute(
            "SELECT * FROM transactions WHERE category = ? AND is_income = 0 ORDER BY date DESC",
            (category,)
        )
    
    transactions = [dict(r) for r in cursor.fetchall()]
    total = sum(t['amount'] for t in transactions)
    
    conn.close()
    
    return {
        "category": category,
        "total": total,
        "count": len(transactions),
        "transactions": transactions
    }

# ============ ENDPOINTS - PROVISÕES ============

@app.get("/api/provisions")
def get_provisions(status: Optional[str] = "active"):
    """Retorna as provisões (despesas/renda futura)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM provisions WHERE status = ? ORDER BY start_date", (status,))
    else:
        cursor.execute("SELECT * FROM provisions ORDER BY start_date")
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/provisions")
def add_provision(prov: ProvisionSchema):
    """Adiciona uma nova provisão"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO provisions (title, amount, category, start_date, end_date, frequency, is_income, payment_method, status, current_amount, target_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (prov.title, prov.amount, prov.category, prov.start_date, prov.end_date, prov.frequency, prov.is_income, prov.payment_method, prov.status, prov.current_amount or 0.0, prov.target_amount or prov.amount)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/provisions/{prov_id}")
def delete_provision(prov_id: int):
    """Deleta uma provisão"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM provisions WHERE id = ?", (prov_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ============ ENDPOINTS - ORÇAMENTOS ============

@app.get("/api/budgets")
def get_budgets(month: Optional[str] = None):
    """Retorna orçamentos do mês"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if month:
        cursor.execute("SELECT * FROM budgets WHERE month = ? ORDER BY category", (month,))
    else:
        cursor.execute("SELECT * FROM budgets ORDER BY month, category")
    
    budgets = [dict(r) for r in cursor.fetchall()]
    
    # Comparar com gastos reais
    if month:
        cursor.execute(
            "SELECT category, title, amount, is_income, card_source, payment_method FROM transactions WHERE date LIKE ? AND parent_id IS NULL AND is_summary = 0",
            (f"{month}%",)
        )
    else:
        cursor.execute(
            "SELECT category, title, amount, is_income, card_source, payment_method FROM transactions WHERE parent_id IS NULL AND is_summary = 0"
        )

    spent = {}
    for row in cursor.fetchall():
        category = row['category'] or 'Outros'
        is_card = is_known_card_source(row['card_source']) or is_known_card_source(row['payment_method'])
        if row['is_income'] == 0:
            spent[category] = spent.get(category, 0) + (row['amount'] or 0)
        elif is_card and not is_card_payment(row['title'] or ""):
            spent[category] = spent.get(category, 0) - (row['amount'] or 0)
    spent = {cat: amount for cat, amount in spent.items() if amount > 0.01}
    conn.close()
    
    result = []
    for b in budgets:
        b['spent'] = spent.get(b['category'], 0)
        b['remaining'] = b['limit_amount'] - b['spent']
        b['percentage'] = (b['spent'] / b['limit_amount'] * 100) if b['limit_amount'] > 0 else 0
        result.append(b)
    
    return result

@app.post("/api/budgets")
def set_budget(budget: BudgetSchema):
    """Define um orçamento para uma categoria em um mês"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO budgets (month, category, limit_amount) VALUES (?, ?, ?)",
            (budget.month, budget.category, budget.limit_amount)
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

# ============ ENDPOINTS - METAS ============

@app.get("/api/goals")
def get_goals(status: Optional[str] = "active"):
    """Retorna as metas financeiras"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM goals WHERE status = ? ORDER BY deadline", (status,))
    else:
        cursor.execute("SELECT * FROM goals ORDER BY deadline")
    
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        goal = dict(row)
        goal['progress'] = (goal['current_amount'] / goal['target_amount'] * 100) if goal['target_amount'] > 0 else 0
        result.append(goal)
    
    return result

@app.post("/api/goals")
def add_goal(goal: GoalSchema):
    """Adiciona uma nova meta financeira"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goals (name, target_amount, deadline, category, status) VALUES (?, ?, ?, ?, ?)",
        (goal.name, goal.target_amount, goal.deadline, goal.category, goal.status)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.put("/api/goals/{goal_id}")
def update_goal(goal_id: int, payload: GoalUpdateSchema):
    """Atualiza o progresso de uma meta"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_amount, target_amount FROM goals WHERE id = ?", (goal_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Meta nÃ£o encontrada")

    current_amount, target_amount = row
    new_amount = current_amount or 0
    if payload.current_amount is not None:
        new_amount = payload.current_amount
    if payload.add_amount is not None:
        new_amount += payload.add_amount
    new_status = payload.status or ("completed" if target_amount and new_amount >= target_amount else "active")
    cursor.execute(
        "UPDATE goals SET current_amount = ?, status = ? WHERE id = ?",
        (new_amount, new_status, goal_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "current_amount": new_amount}

@app.delete("/api/goals/{goal_id}")
def delete_goal(goal_id: int):
    """Deleta uma meta"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# ============ ENDPOINTS - UPLOAD ============

def parse_decimal_amount(value):
    if value is None:
        return 0.0
    text = str(value).strip()
    if text == '' or text.lower() == 'nan':
        return 0.0
    negative = False
    if text.startswith('(') and text.endswith(')'):
        negative = True
        text = text[1:-1]
    text = text.replace('R$', '').replace('r$', '').replace('\xa0', '').replace(' ', '')
    if text.count(',') > 0 and text.count('.') > 0:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    else:
        text = text.replace('.', '').replace(',', '.')
    try:
        amount = float(text)
    except ValueError:
        amount = 0.0
    return -amount if negative else amount


def find_column(columns, aliases):
    for alias in aliases:
        for normalized, original in columns.items():
            if normalized == alias or alias in normalized:
                return original
    return None


# backend/main.py - adicione estas funções auxiliares no início do arquivo

def convert_date(date_str: str) -> str:
    """Converte DD/MM para YYYY-MM-DD"""
    try:
        parts = date_str.split('/')
        if len(parts) == 2:
            day, month = parts
            year = datetime.now().year
            # Se for mês futuro, usa ano anterior
            if int(month) > datetime.now().month:
                year -= 1
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        elif len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = 2000 + int(year)
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass
    return datetime.now().strftime("%Y-%m-%d")

def get_next_billing_date() -> str:
    """Retorna a data do próximo fechamento (dia 25 do mês atual ou próximo)"""
    today = datetime.now()
    if today.day > 25:
        next_month = today.month + 1
        year = today.year
        if next_month > 12:
            next_month = 1
            year += 1
        return f"{year}-{next_month:02d}-25"
    else:
        return f"{today.year}-{today.month:02d}-25"

def parse_brazilian_number(value_str: str) -> float:
    """Converte string de número no formato brasileiro para float"""
    if not value_str:
        return 0.0
    
    # Remove R$ e espaços
    cleaned = value_str.replace('R$', '').replace('r$', '').replace(' ', '').replace('\xa0', '')
    
    # Verifica negativo
    is_negative = False
    if cleaned.startswith('(') and cleaned.endswith(')'):
        is_negative = True
        cleaned = cleaned[1:-1]
    elif cleaned.startswith('-'):
        is_negative = True
        cleaned = cleaned[1:]
    
    # Converte formato brasileiro (1.234,56 -> 1234.56)
    if ',' in cleaned:
        cleaned = cleaned.replace('.', '')
        cleaned = cleaned.replace(',', '.')
    
    try:
        amount = float(cleaned)
    except:
        # Tenta extrair números
        import re
        numbers = re.findall(r'[\d,]+', cleaned)
        if numbers:
            amount = float(numbers[0].replace(',', '.'))
        else:
            amount = 0.0
    
    return -amount if is_negative else amount

# Substitua a função upload_file inteira
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename.lower()
    contents = await file.read()
    
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)
        
    parsed_entries = []

    try:
        if filename.endswith('.csv'):
            # Processar CSV Nubank
            df = None
            for sep in [',', ';', '\t']:
                try:
                    df = pd.read_csv(temp_path, sep=sep, engine='python', encoding='utf-8')
                    if len(df.columns) >= 3:
                        break
                except:
                    continue
            
            if df is None:
                raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo CSV")
            
            columns = {col.lower().strip(): col for col in df.columns}
            date_col = find_column(columns, ['date', 'data', 'data da transação', 'data da transacao', 'transaction date', 'posting date'])
            title_col = find_column(columns, ['title', 'titulo', 'description', 'descrição', 'descricao', 'histórico', 'historico', 'details', 'detalhes', 'lancamento'])
            amount_col = find_column(columns, ['amount', 'valor', 'value', 'montante'])

            if not date_col or not title_col or not amount_col:
                raise HTTPException(status_code=400, detail=f"Formato de CSV incompatível")

            for idx, row in df.iterrows():
                try:
                    title_value = str(row[title_col]).strip()
                    title_lower = title_value.lower()
                    try:
                        amount = parse_brazilian_number(str(row[amount_col]))
                        if amount == 0:
                            continue
                    except Exception as e:
                        print(f"Erro ao converter valor na linha {idx}: {e}")
                        continue
                    if 'Renegociação' in title_value or 'Parcelamento de Fatura' in title_value:
                        if amount < 0:
                            pass
                        else:
                            pass

                    if is_card_import_metadata(title_value):
                        continue
                    
                    # Parse da data
                    raw_date = str(row[date_col])
                    date_value = convert_date(raw_date)
                    
                    parsed_entries.append({
                        "date": date_value,
                        "title": title_value,
                        "amount": amount,
                        "card_source": "Nubank"
                    })
                    
                except Exception as e:
                    print(f"Erro na linha {idx}: {e}")
                    continue

            parsed_entries = remove_refund_pairs(parsed_entries)

        elif filename.endswith('.pdf'):
            import pdfplumber
            with pdfplumber.open(temp_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            
            # Extrair total da fatura
            total_match = re.search(r'fatura é:\s*R\$\s*([0-9,.]+)', full_text, re.IGNORECASE)
            total_fatura = parse_brazilian_number(total_match.group(1)) if total_match else 0
            
            # Padrão mais robusto para capturar compras
            # Formato: DATA (dd/mm) + ESTABELECIMENTO (letras, espaços, pontuação) + VALOR (com vírgula ou ponto)
            # Vamos procurar linhas que começam com dois números, barra, dois números, e depois um valor no final
            lines = full_text.split('\n')
            for line in lines:
                line = line.strip()
                # Verifica se a linha começa com padrão de data (dd/mm) e termina com número
                if re.match(r'^\d{2}/\d{2}\s+', line):
                    parts = line.split()
                    if len(parts) >= 3:
                        date_str = parts[0]
                        # O estabelecimento pode ter várias palavras, o último token é o valor
                        amount_str = parts[-1].replace('R$', '').strip()
                        establishment = ' '.join(parts[1:-1]).strip()
                        
                        # Ignorar linhas que contêm palavras-chave de metadados
                        if any(kw in establishment.upper() for kw in ['PARCELA', 'CREDITO', 'IOF', 'JUROS', 'MULTA', 'TOTAL', 'LANCAMENTOS', 'PAGAMENTOS']):
                            continue
                        if len(establishment) < 3:
                            continue
                        
                        amount = parse_brazilian_number(amount_str)
                        if amount == 0:
                            continue
                        
                        # Evita duplicatas muito próximas (ex: mesmo estabelecimento, mesmo valor, mesma data)
                        # Como medida simples, verifica se já não existe entrada igual nos últimos 5 segundos
                        parsed_entries.append({
                            "date": convert_date(date_str),
                            "title": establishment[:100],
                            "amount": amount,
                            "card_source": "Itaú"
                        })
            
            # Adiciona fatura resumo apenas se não for uma fatura com saldo zero
            if total_fatura > 0 and len(parsed_entries) > 0:
                parsed_entries.append({
                    "date": get_next_billing_date(),
                    "title": f"Fatura Itaú {total_fatura:.2f}",
                    "amount": -total_fatura,
                    "card_source": "Itaú",
                    "is_summary": 1
                })
        
        # Inserir no banco
        if parsed_entries:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            inserted_count = 0
            
            for entry in parsed_entries:
                # Verificar duplicata
                cursor.execute(
                    "SELECT id FROM transactions WHERE date = ? AND title = ? AND ABS(amount - ?) < 0.01",
                    (entry['date'], entry['title'], abs(entry['amount']))
                )
                if cursor.fetchone():
                    continue
                
                inferred = auto_categorize_transaction(entry['title'], entry['amount'])
                amount = abs(entry['amount'])

                card_name = entry.get('card_source')
                if not card_name:
                    if 'nubank' in filename:
                        card_name = 'Nubank'
                    elif 'itau' in filename or 'itaú' in filename:
                        card_name = 'Itaú'
                    else:
                        card_name = 'Dinheiro'

                is_income = 1 if is_known_card_source(card_name) and is_card_credit(entry['title']) else 0 if is_known_card_source(card_name) else inferred["is_income"]
                
                # Buscar dados do cartão
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT id, closing_day, due_day FROM cards WHERE name = ? AND is_active = 1", (card_name,))
                card_row = cursor.fetchone()
                if not card_row:
                    # Se não existir, criar um padrão
                    cursor.execute("INSERT OR IGNORE INTO cards (name, closing_day, due_day) VALUES (?, 25, 10)", (card_name,))
                    conn.commit()
                    cursor.execute("SELECT id, closing_day, due_day FROM cards WHERE name = ?", (card_name,))
                    card_row = cursor.fetchone()
                card_id, closing_day, due_day = card_row
                
                # Para cada transação, calcular a data de efeito
                for parsed_entry in parsed_entries:
                    effective_date = calculate_billing_due_date(parsed_entry['date'], closing_day, due_day)
                    parsed_entry['effective_date'] = effective_date
                    parsed_entry['card_id'] = card_id
                    parsed_entry['original_date'] = parsed_entry['date']
                
                # Inserir com os novos campos
                cursor.execute(
                    """INSERT INTO transactions 
                    (date, title, amount, category, card_source, payment_method, 
                        is_fixed, is_income, is_summary, tags, card_id, original_date, effective_date) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (entry['effective_date'], entry['title'], amount, inferred['category'],
                    entry.get('card_source', card_name), entry.get('card_source', card_name),
                    0, is_income, entry.get('is_summary', 0), inferred.get('tags'),
                    card_id, entry['original_date'], entry['effective_date'])
                )
                inserted_count += 1
            
            conn.commit()
            conn.close()
            os.remove(temp_path)
            return {"status": "success", "inserted": inserted_count, "total_found": len(parsed_entries)}
        
        os.remove(temp_path)
        raise HTTPException(status_code=400, detail="Nenhuma transação válida encontrada.")
    
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"Erro detalhado: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Novo endpoint para upload em lote
@app.post("/api/upload-batch")
async def upload_files(files: List[UploadFile] = File(...)):
    """Importa múltiplos arquivos CSV/PDF de uma vez"""
    results = []
    total_inserted = 0
    
    for file in files:
        try:
            # Processar cada arquivo
            result = await upload_file(file)  # Reutiliza a lógica existente
            if hasattr(result, 'body'):
                import json
                body = json.loads(result.body)
                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "inserted": body.get("inserted", 0)
                })
                total_inserted += body.get("inserted", 0)
            else:
                results.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": "Erro ao processar"
                })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "status": "completed",
        "total_inserted": total_inserted,
        "results": results
    }
    
# ============ ENDPOINTS - CATEGORY RULES (AUTOMATED) ============

@app.get("/api/category-rules")
def get_category_rules():
    """Retorna todas as regras de categorização"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM category_rules ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/category-rules")
def add_category_rule(rule: CategoryRuleSchema):
    """Adiciona uma nova regra de categorização"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO category_rules (pattern, category, rule_type, tags) VALUES (?, ?, ?, ?)",
        (rule.pattern, rule.category, rule.rule_type, rule.tags)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/category-rules/{rule_id}")
def delete_category_rule(rule_id: int):
    """Deleta uma regra de categorização"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}


# ============ ENDPOINTS - PROVISIONS ENVELOPE / SINKING FUNDS OPERATIONS ============

@app.post("/api/provisions/{prov_id}/fund")
def fund_provision(prov_id: int, payload: FundSchema):
    """Adiciona saldo à provisão (Envelope / Sinking Fund)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_amount, target_amount FROM provisions WHERE id = ?", (prov_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Provisão não encontrada")
    
    current_amount, target_amount = row
    new_amount = (current_amount or 0.0) + payload.amount
    
    cursor.execute("UPDATE provisions SET current_amount = ? WHERE id = ?", (new_amount, prov_id))
    conn.commit()
    conn.close()
    return {"status": "success", "current_amount": new_amount}

@app.post("/api/provisions/{prov_id}/withdraw")
def withdraw_provision(prov_id: int, payload: FundSchema):
    """Retira saldo da provisão (Envelope / Sinking Fund)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_amount FROM provisions WHERE id = ?", (prov_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Provisão não encontrada")
    
    current_amount = row[0] or 0.0
    new_amount = current_amount - payload.amount
    
    cursor.execute("UPDATE provisions SET current_amount = ? WHERE id = ?", (new_amount, prov_id))
    conn.commit()
    conn.close()
    return {"status": "success", "current_amount": new_amount}


# ============ ENDPOINTS - SAFE PURCHASE VALIDATOR & SIMULATIONS ============

def project_cash_flow_for_month(month: str, cursor, conn):
    # Get active salary
    cursor.execute("SELECT gross_amount, net_amount FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    row_salary = cursor.fetchone()
    salary = 0.0
    if row_salary:
        salary = row_salary[1] if row_salary[1] is not None else (row_salary[0] if row_salary[0] is not None else 0.0)
    
    # Get active provisions occurrences for that month
    occurrences = provision_occurrences_for_month(month)
    prov_income = sum(occ['amount'] for occ in occurrences if occ['amount'] > 0)
    prov_expense = sum(-occ['amount'] for occ in occurrences if occ['amount'] < 0)
    tx_income, tx_expense = transaction_totals_for_month(cursor, month)
    
    # Get fixed transactions for that month (e.g. is_fixed = 1)
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_income = 0 AND is_fixed = 1 AND parent_id IS NULL",
        (f"{month}%",)
    )
    fixed_tx_expense = cursor.fetchone()[0] or 0.0
    
    # Get regular transactions already scheduled for that month (excluding fixed)
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_income = 0 AND is_fixed = 0 AND parent_id IS NULL",
        (f"{month}%",)
    )
    scheduled_expense = cursor.fetchone()[0] or 0.0
    
    # Compute 3-month historical variable expenses average to project variable expenses if it's a future month
    today = datetime.now()
    curr_month_str = today.strftime("%Y-%m")
    
    historical_avg_var_spend = 0.0
    if month > curr_month_str:
        # Find 3 months prior to today
        past_months = []
        for i in range(1, 4):
            py = today.year
            pm_num = today.month - i
            while pm_num <= 0:
                pm_num += 12
                py -= 1
            past_months.append(f"{py}-{pm_num:02d}")
            
        placeholders = ",".join("?" for _ in past_months)
        cursor.execute(
            f"SELECT SUM(amount) FROM transactions "
            f"WHERE SUBSTR(date, 1, 7) IN ({placeholders}) AND is_income = 0 AND is_fixed = 0 AND parent_id IS NULL",
            tuple(past_months)
        )
        total_var = cursor.fetchone()[0] or 0.0
        historical_avg_var_spend = total_var / 3.0
        
    known_expense = tx_expense if tx_expense > 0 else fixed_tx_expense + scheduled_expense
    projected_income = salary + tx_income + prov_income
    projected_expense = prov_expense + (known_expense if known_expense > 0 else historical_avg_var_spend)
    
    return {
        "projected_income": projected_income,
        "projected_expense": projected_expense,
        "projected_net": projected_income - projected_expense
    }

@app.post("/api/purchase-simulations/validate")
def validate_purchase(sim: PurchaseSimulationSchema):
    """Simula o impacto de uma nova compra no fluxo de caixa futuro"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        start_dt = datetime.strptime(sim.start_date[:10], "%Y-%m-%d")
    except ValueError:
        try:
            start_dt = datetime.strptime(sim.start_date[:7], "%Y-%m").replace(day=1)
        except ValueError:
            start_dt = datetime.now()
        
    installment_val = sim.amount / sim.installments
    
    timeline = []
    overall_status = "GREEN"
    reasons = []
    
    num_months_to_simulate = max(sim.installments, 6)
    
    for i in range(num_months_to_simulate):
        py = start_dt.year
        pm_num = start_dt.month + i
        while pm_num > 12:
            pm_num -= 12
            py += 1
        month_str = f"{py}-{pm_num:02d}"
        
        flow = project_cash_flow_for_month(month_str, cursor, conn)
        new_inst = installment_val if i < sim.installments else 0.0
        
        post_purchase_balance = flow["projected_net"] - new_inst
        
        month_status = "GREEN"
        if post_purchase_balance < 0:
            month_status = "RED"
            overall_status = "RED"
            reasons.append(f"Déficit projetado em {month_str} (Balanço: -R$ {abs(post_purchase_balance):.2f})")
        elif post_purchase_balance < (flow["projected_income"] * 0.10):
            month_status = "YELLOW"
            if overall_status != "RED":
                overall_status = "YELLOW"
            margin = (post_purchase_balance / flow["projected_income"] * 100) if flow["projected_income"] > 0 else 0
            reasons.append(f"Margem de segurança apertada ({margin:.1f}%) em {month_str}")
            
        timeline.append({
            "month": month_str,
            "projected_income": flow["projected_income"],
            "projected_expense": flow["projected_expense"],
            "new_installment": new_inst,
            "projected_balance": post_purchase_balance,
            "status": month_status
        })
        
    conn.close()
    
    if overall_status == "GREEN":
        reason_summary = "Compra recomendada! Seu fluxo de caixa projetado suporta as parcelas sem comprometer o orçamento."
    elif overall_status == "YELLOW":
        reason_summary = f"Atenção: A compra é viável, mas reduzirá significativamente sua margem de segurança. Detalhes: {'; '.join(reasons[:2])}"
    else:
        reason_summary = f"Crítico: Compra não recomendada! Risco de saldo negativo detectado. Detalhes: {'; '.join(reasons[:2])}"
        
    return {
        "decision": overall_status,
        "reason": reason_summary,
        "installment_amount": installment_val,
        "timeline": timeline
    }

@app.post("/api/purchase-simulations")
def add_purchase_simulation(sim: PurchaseSimulationSchema):
    """Salva uma simulação de compra no banco de dados"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO purchase_simulations (title, amount, installments, start_date, category, status) VALUES (?, ?, ?, ?, ?, 'pending')",
        (sim.title, sim.amount, sim.installments, sim.start_date, sim.category)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/purchase-simulations")
def get_purchase_simulations():
    """Retorna todas as simulações pendentes"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM purchase_simulations WHERE status = 'pending' ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/purchase-simulations/{sim_id}")
def delete_purchase_simulation(sim_id: int):
    """Deleta uma simulação"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM purchase_simulations WHERE id = ?", (sim_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/purchase-simulations/{sim_id}/confirm")
def confirm_purchase_simulation(sim_id: int):
    """Confirma uma simulação, gerando transações futuras no banco de dados"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM purchase_simulations WHERE id = ?", (sim_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Simulação não encontrada")
        
    sim = dict(row)
    installment_val = sim['amount'] / sim['installments']
    
    # Parse start date
    try:
        start_dt = datetime.strptime(sim['start_date'][:10], "%Y-%m-%d")
    except ValueError:
        try:
            start_dt = datetime.strptime(sim['start_date'][:7], "%Y-%m").replace(day=1)
        except ValueError:
            start_dt = datetime.now()
            
    # Generate transactions
    for i in range(sim['installments']):
        py = start_dt.year
        pm_num = start_dt.month + i
        while pm_num > 12:
            pm_num -= 12
            py += 1
        # Keep same day of month or adjust if out of range
        try:
            target_date = datetime(py, pm_num, start_dt.day)
        except ValueError:
            # Handle end of month issues
            import calendar
            last_day = calendar.monthrange(py, pm_num)[1]
            target_date = datetime(py, pm_num, last_day)
            
        title = f"{sim['title']} ({i+1}/{sim['installments']})"
        
        cursor.execute(
            "INSERT INTO transactions (date, title, amount, category, card_source, payment_method, is_fixed, is_income) VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
            (target_date.strftime("%Y-%m-%d"), title, installment_val, sim['category'], 'Cartão', 'Cartão')
        )
        
    cursor.execute("UPDATE purchase_simulations SET status = 'confirmed' WHERE id = ?", (sim_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}


# ============ ENDPOINTS - NET WORTH & FORECASTING ============

@app.get("/api/forecasting")
def get_forecasting(months: Optional[int] = 12, start_month: Optional[str] = None):
    """Gera projeção de Patrimônio Líquido para os próximos N meses"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.now()
    start_month = start_month or today.strftime("%Y-%m")
    
    cursor.execute("SELECT gross_amount, net_amount FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    salary_row = cursor.fetchone()
    salary = 0.0
    if salary_row:
        salary = salary_row['net_amount'] if salary_row['net_amount'] is not None else (salary_row['gross_amount'] or 0.0)
        
    timeline = []
    cumulative_net_worth = carried_balance_before_month(cursor, start_month, salary)
    start_dt = datetime.strptime(f"{start_month}-01", "%Y-%m-%d")
    
    for i in range(months):
        py = start_dt.year
        pm_num = start_dt.month + i
        while pm_num > 12:
            pm_num -= 12
            py += 1
        month_str = f"{py}-{pm_num:02d}"
        
        flow = project_cash_flow_for_month(month_str, cursor, conn)
        cumulative_net_worth += flow["projected_net"]
        
        timeline.append({
            "month": month_str,
            "projected_income": flow["projected_income"],
            "projected_expense": flow["projected_expense"],
            "projected_net": flow["projected_net"],
            "projected_net_worth": cumulative_net_worth
        })
        
    conn.close()
    return timeline


# ============ ENDPOINTS - MTD ANALYTICS ============

@app.get("/api/mtd-analytics")
def get_mtd_analytics(month: Optional[str] = None):
    """Métricas de saúde e Burn Rate para o mês selecionado contra média de 3 meses"""
    if not month:
        month = datetime.now().strftime("%Y-%m-%d")[:7]
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Variable discretionary spending (is_fixed = 0)
    cursor.execute(
        "SELECT * FROM transactions WHERE date LIKE ? AND is_fixed = 0 AND parent_id IS NULL AND is_summary = 0",
        (f"{month}%",)
    )
    variable_txs = [dict(r) for r in cursor.fetchall()]
    total_card_var_spend = 0.0
    total_cash_var_spend = 0.0
    for tx in variable_txs:
        is_card = is_known_card_source(tx.get('card_source')) or is_known_card_source(tx.get('payment_method'))
        if tx.get('is_income') == 0:
            if is_card:
                total_card_var_spend += tx['amount']
            else:
                total_cash_var_spend += tx['amount']
        elif is_card and not is_card_payment(tx.get('title') or ""):
            total_card_var_spend -= tx['amount']
    total_var_spend = total_card_var_spend + total_cash_var_spend
    
    today = datetime.now()
    req_year = int(month[:4])
    req_month = int(month[5:7])
    _, num_days = calendar.monthrange(req_year, req_month)
    
    if req_year == today.year and req_month == today.month:
        days_elapsed = today.day
    elif req_year < today.year or (req_year == today.year and req_month < today.month):
        days_elapsed = num_days
    else:
        days_elapsed = 0
        
    burn_rate = total_cash_var_spend / days_elapsed if days_elapsed > 0 else 0.0
    projected_cash_var_spend = burn_rate * num_days
    projected_var_spend = total_card_var_spend + projected_cash_var_spend
    
    # Get active provisions/fixed expenses occurrences
    fixed_occurrences = provision_occurrences_for_month(month)
    prov_fixed_spend = sum(-occ['amount'] for occ in fixed_occurrences if occ['amount'] < 0)
    
    cursor.execute(
        "SELECT SUM(amount) FROM transactions WHERE date LIKE ? AND is_income = 0 AND is_fixed = 1 AND parent_id IS NULL AND is_summary = 0",
        (f"{month}%",)
    )
    tx_fixed_spend = cursor.fetchone()[0] or 0.0
    
    total_projected_fixed = prov_fixed_spend + tx_fixed_spend
    total_projected_expense = projected_var_spend + total_projected_fixed
    
    # Get active salary plan
    cursor.execute("SELECT gross_amount, net_amount FROM salary_plan ORDER BY effective_date DESC LIMIT 1")
    row_salary = cursor.fetchone()
    current_salary = 0
    if row_salary:
        current_salary = row_salary['net_amount'] if row_salary['net_amount'] is not None else (row_salary['gross_amount'] or 0)
    
    prov_income = sum(occ['amount'] for occ in fixed_occurrences if occ['amount'] > 0)
    cursor.execute(
        "SELECT amount, title, card_source, payment_method FROM transactions WHERE date LIKE ? AND is_income = 1 AND parent_id IS NULL AND is_summary = 0",
        (f"{month}%",)
    )
    actual_income = 0.0
    for row in cursor.fetchall():
        is_card = is_known_card_source(row['card_source']) or is_known_card_source(row['payment_method'])
        if not is_card:
            actual_income += row['amount'] or 0
    
    total_projected_income = current_salary + actual_income + prov_income
    projected_balance = total_projected_income - total_projected_expense
    
    # 2. Historical comparison: past 3 months
    past_months = []
    for i in range(1, 4):
        py = req_year
        pm_num = req_month - i
        while pm_num <= 0:
            pm_num += 12
            py -= 1
        past_months.append(f"{py}-{pm_num:02d}")
        
    placeholders = ",".join("?" for _ in past_months)
    cursor.execute(
        f"SELECT category, SUBSTR(date, 1, 7) as m, SUM(amount) as total "
        f"FROM transactions "
        f"WHERE SUBSTR(date, 1, 7) IN ({placeholders}) AND is_income = 0 AND parent_id IS NULL "
        f"GROUP BY category, m",
        tuple(past_months)
    )
    past_rows = cursor.fetchall()
    
    past_data = defaultdict(dict)
    for r in past_rows:
        past_data[r['category']][r['m']] = r['total']
        
    category_3m_avg = {}
    for cat, m_data in past_data.items():
        category_3m_avg[cat] = sum(m_data.values()) / 3.0
        
    cursor.execute(
        "SELECT category, title, amount, is_income, card_source, payment_method FROM transactions WHERE date LIKE ? AND parent_id IS NULL AND is_summary = 0",
        (f"{month}%",)
    )
    curr_rows = cursor.fetchall()
    curr_data = {}
    for r in curr_rows:
        category = r['category'] or 'Outros'
        is_card = is_known_card_source(r['card_source']) or is_known_card_source(r['payment_method'])
        if r['is_income'] == 0:
            curr_data[category] = curr_data.get(category, 0) + (r['amount'] or 0)
        elif is_card and not is_card_payment(r['title'] or ""):
            curr_data[category] = curr_data.get(category, 0) - (r['amount'] or 0)
    curr_data = {cat: amount for cat, amount in curr_data.items() if amount > 0.01}
    
    alerts = []
    for cat, curr_val in curr_data.items():
        avg_val = category_3m_avg.get(cat, 0.0)
        if avg_val > 50.0:
            diff_pct = ((curr_val - avg_val) / avg_val) * 100
            if diff_pct > 15:
                alerts.append({
                    "type": "warning",
                    "category": cat,
                    "message": f"Atenção: Os gastos com {cat} estão {diff_pct:.0f}% acima da média (R$ {curr_val:.2f} vs. média de R$ {avg_val:.2f})."
                })
            elif diff_pct < -15:
                alerts.append({
                    "type": "success",
                    "category": cat,
                    "message": f"Você está gastando {abs(diff_pct):.0f}% a menos com {cat} este mês (R$ {curr_val:.2f} vs. média de R$ {avg_val:.2f})."
                })
                
    conn.close()
    
    return {
        "month": month,
        "burn_rate": burn_rate,
        "days_elapsed": days_elapsed,
        "total_days": num_days,
        "projected_var_spend": projected_var_spend,
        "total_projected_fixed": total_projected_fixed,
        "total_projected_expense": total_projected_expense,
        "total_projected_income": total_projected_income,
        "projected_balance": projected_balance,
        "alerts": alerts,
        "category_3m_avg": category_3m_avg,
        "current_spend_by_category": curr_data
    }
