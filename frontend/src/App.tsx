import { AlertCircle, AlertTriangle, Calendar, ChevronDown, ChevronRight, DollarSign, Plus, ShoppingBag, Sparkles, Target, TrendingUp, Upload } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { Area, AreaChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type TabType = 'dashboard' | 'transactions' | 'pluggy' | 'categories' | 'budgets' | 'goals' | 'provisions' | 'purchase-validator';

interface Transaction {
  id?: number;
  date: string;
  title: string;
  amount: number;
  category: string;
  card_source?: string;
  payment_method?: string;
  is_fixed?: number;
  is_income?: number;
  parent_id?: number;
  is_summary?: number;
  tags?: string;
}

interface DashboardData {
  total_income: number;
  total_expense: number;
  balance: number;
  current_salary?: number;
  fixed_expense_total?: number;
  projected_balance?: number;
  previous_balance?: number;
  carryover_balance?: number;
  residual_debt?: number;
  expenses_by_category: Record<string, number>;
  ring_fenced_provisions_total?: number;
  available_to_spend?: number;
}

interface SalaryPlan {
  id?: number;
  effective_date?: string;
  gross_amount: number;
  net_amount?: number;
}

interface Provision {
  id: number;
  title: string;
  amount: number;
  category: string;
  start_date: string;
  end_date?: string;
  frequency: string;
  is_income: number;
  payment_method?: string;
  status: string;
}

interface Budget {
  id: number;
  month: string;
  category: string;
  limit_amount: number;
  spent: number;
  remaining: number;
  percentage: number;
}

interface Goal {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline: string;
  category?: string;
  status: string;
  progress: number;
}

interface Card {
  id: number;
  name: string;
  closing_day: number;
  due_day: number;
  is_active?: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('finance_auth_token') || '');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authRequired, setAuthRequired] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [authError, setAuthError] = useState('');
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [monthlySummary, setMonthlySummary] = useState<{ month: string; income: number; expense: number; balance: number; projected_balance?: number; carryover_balance?: number; residual_debt?: number }[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7));
  const [showAllMonths, setShowAllMonths] = useState(false);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [salaryPlan, setSalaryPlan] = useState<SalaryPlan | null>(null);
  const [provisions, setProvisions] = useState<Provision[]>([]);
  const [salaryInput, setSalaryInput] = useState<{ effective_date: string; gross_amount: string; net_amount: string }>({ effective_date: new Date().toISOString().slice(0, 10), gross_amount: '', net_amount: '' });
  const [newProvision, setNewProvision] = useState<{ title: string; amount: string; category: string; start_date: string; end_date: string; frequency: 'once' | 'weekly' | 'monthly' | 'yearly'; payment_method: string; current_amount: string; target_amount: string }>({ title: '', amount: '', category: 'Outros', start_date: new Date().toISOString().slice(0, 10), end_date: '', frequency: 'monthly', payment_method: 'Pix', current_amount: '0', target_amount: '' });
  const [newTransaction, setNewTransaction] = useState<{ date: string; title: string; amount: string; category: string; type: 'expense' | 'income'; payment_method: string; is_fixed: boolean; tags: string }>({ date: new Date().toISOString().slice(0, 10), title: '', amount: '', category: 'Outros', type: 'expense', payment_method: 'Manual', is_fixed: false, tags: '' });
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [newGoal, setNewGoal] = useState<{ name: string; target_amount: string; deadline: string }>({ name: '', target_amount: '', deadline: '' });
  const [goalContributions, setGoalContributions] = useState<Record<number, string>>({});
  const [newBudget, setNewBudget] = useState<{ category: string; limit_amount: string }>({ category: 'Outros', limit_amount: '' });
  const [newCategory, setNewCategory] = useState<{ name: string; color: string }>({ name: '', color: '#3b82f6' });
  const [transactionFilterMonth, setTransactionFilterMonth] = useState(new Date().toISOString().slice(0, 7));
  const [transactionFilterCategory, setTransactionFilterCategory] = useState('');
  const [transactionFilterPaymentMethod, setTransactionFilterPaymentMethod] = useState('');
  const [transactionFilterFixed, setTransactionFilterFixed] = useState('all');
  const [expandedParents, setExpandedParents] = useState<number[]>([]);

  // New features state variables
  const [mtdAnalytics, setMtdAnalytics] = useState<any | null>(null);
  const [categoryRules, setCategoryRules] = useState<{ id: number; pattern: string; category: string; rule_type: string; tags?: string }[]>([]);
  const [newCategoryRule, setNewCategoryRule] = useState<{ pattern: string; category: string; rule_type: string; tags: string }>({ pattern: '', category: 'Alimentação', rule_type: 'contains', tags: '' });
  const [purchaseSimulations, setPurchaseSimulations] = useState<any[]>([]);
  const [newSimulationInput, setNewSimulationInput] = useState<{ title: string; amount: string; installments: string; start_date: string; category: string }>({ title: '', amount: '', installments: '1', start_date: new Date().toISOString().slice(0, 10), category: 'Compras' });
  const [purchaseCalendarInput, setPurchaseCalendarInput] = useState<{ month: string; amount: string; installments: string; payment_method: string }>({ month: new Date().toISOString().slice(0, 7), amount: '', installments: '1', payment_method: 'cash' });
  const [simulationResult, setSimulationResult] = useState<any | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [forecastingData, setForecastingData] = useState<{ month: string; projected_income: number; projected_expense: number; projected_net: number; projected_net_worth: number }[]>([]);
  const [depositWithdrawModal, setDepositWithdrawModal] = useState<{ open: boolean; provisionId: number | null; type: 'deposit' | 'withdraw'; amount: string }>({ open: false, provisionId: null, type: 'deposit', amount: '' });
  const [pluggyStatus, setPluggyStatus] = useState<any | null>(null);
  const [pluggyAccounts, setPluggyAccounts] = useState<any[]>([]);
  const [pluggyAccountAliases, setPluggyAccountAliases] = useState<{ account_id: string; alias: string; transaction_count?: number }[]>([]);
  const [pluggyAliasInput, setPluggyAliasInput] = useState<{ account_id: string; alias: string }>({ account_id: '', alias: '' });
  const [pluggySyncInput, setPluggySyncInput] = useState<{ item_ids: string; account_type: string; date_from: string; date_to: string }>({ item_ids: '', account_type: '', date_from: `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-01`, date_to: new Date().toISOString().slice(0, 10) });
  const [pluggyStatusMessage, setPluggyStatusMessage] = useState('');

  const fetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const headers = new Headers(init.headers || {});
    if (authToken) {
      headers.set('Authorization', `Bearer ${authToken}`);
    }
    const response = await window.fetch(input, { ...init, headers });
    if (response.status === 401) {
      localStorage.removeItem('finance_auth_token');
      setAuthToken('');
      setAuthMode('login');
      setAuthRequired(true);
    }
    return response;
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await window.fetch(`${API_BASE}/api/auth/${authMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAuthError(data.detail || 'Erro ao autenticar.');
        return;
      }
      localStorage.setItem('finance_auth_token', data.token);
      setAuthToken(data.token);
      setAuthRequired(true);
    } catch (err) {
      setAuthError('Erro ao conectar com o backend.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('finance_auth_token');
    setAuthToken('');
  };

  const fetchTransactions = async () => {
    try {
      const params = new URLSearchParams();
      if (transactionFilterMonth) params.append('month', transactionFilterMonth);
      if (transactionFilterCategory) params.append('category', transactionFilterCategory);
      if (transactionFilterPaymentMethod) params.append('payment_method', transactionFilterPaymentMethod);
      if (transactionFilterFixed === 'sim') params.append('is_fixed', '1');
      if (transactionFilterFixed === 'nao') params.append('is_fixed', '0');

      const url = `${API_BASE}/api/transactions?${params.toString()}`;
      const res = await fetch(url);
      const data = await res.json();
      setTransactions(data);
    } catch (err) {
      console.error('Erro ao buscar transações:', err);
    }
  };

  // Exemplo de componente para gerenciar cartões
const [cards, setCards] = useState<Card[]>([]);
const [newCard, setNewCard] = useState({ name: '', closing_day: 1, due_day: 1 });

const fetchCards = async () => {
    const res = await fetch(`${API_BASE}/api/cards`);
    const data = await res.json();
    setCards(data);
};

const handleAddCard = async (e: React.FormEvent) => {
    e.preventDefault();
    await fetch(`${API_BASE}/api/cards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCard)
    });
    setNewCard({ name: '', closing_day: 1, due_day: 1 });
    fetchCards();
};

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const headers = authToken ? { Authorization: `Bearer ${authToken}` } : undefined;
        const res = await window.fetch(`${API_BASE}/api/auth/status`, { headers });
        const data = await res.json();
        if (!data.has_user || (authToken && !data.authenticated)) {
          localStorage.removeItem('finance_auth_token');
          setAuthToken('');
        }
        setAuthRequired(true);
        setAuthMode(data.has_user ? 'login' : 'register');
      } catch (err) {
        setAuthRequired(true);
      } finally {
        setAuthChecked(true);
      }
    };
    checkAuth();
  }, [authToken]);

  const fetchDashboard = async () => {
    setLoadingDashboard(true);
    try {
      const dashboardUrl = showAllMonths ? `${API_BASE}/api/dashboard` : `${API_BASE}/api/dashboard?month=${selectedMonth}`;
      const [dashboardRes, monthlyRes] = await Promise.all([
        fetch(dashboardUrl),
        fetch(`${API_BASE}/api/monthly-summary`),
      ]);

      const dashboard = await dashboardRes.json();
      const monthly = await monthlyRes.json() as Record<string, { income: number; expense: number; balance: number; projected_balance?: number; carryover_balance?: number; residual_debt?: number }>;

      setDashboardData(dashboard);
      setMonthlySummary(
        Object.entries(monthly)
          .map(([month, values]) => ({
            month,
            income: values.income,
            expense: values.expense,
            balance: values.balance,
            projected_balance: values.projected_balance ?? values.income - values.expense,
            carryover_balance: values.carryover_balance ?? values.balance,
            residual_debt: values.residual_debt ?? 0,
          }))
          .sort((a, b) => a.month.localeCompare(b.month))
      );
    } catch (err) {
      console.error('Erro ao buscar dashboard:', err);
      setDashboardData(null);
      setMonthlySummary([]);
    } finally {
      setLoadingDashboard(false);
    }
  };

  const fetchBudgets = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/budgets?month=${selectedMonth}`);
      const data = await res.json();
      setBudgets(data);
    } catch (err) {
      console.error('Erro ao buscar orçamentos:', err);
    }
  };

  const fetchGoals = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/goals`);
      const data = await res.json();
      setGoals(data);
    } catch (err) {
      console.error('Erro ao buscar metas:', err);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/categories`);
      const data = await res.json();
      const names = data.map((item: { name: string }) => item.name);
      setCategories(names);
      if (!names.includes(newTransaction.category)) {
        setNewTransaction(prev => ({ ...prev, category: names[0] || 'Outros' }));
      }
      if (!names.includes(newBudget.category)) {
        setNewBudget(prev => ({ ...prev, category: names[0] || 'Outros' }));
      }
    } catch (err) {
      console.error('Erro ao buscar categorias:', err);
    }
  };

  const fetchSalaryPlan = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/salary-plan`);
      const data = await res.json();
      setSalaryPlan(data);
      setSalaryInput(prev => ({
        ...prev,
        effective_date: data.effective_date || prev.effective_date,
        gross_amount: data.gross_amount?.toString() || '',
        net_amount: data.net_amount?.toString() || ''
      }));
    } catch (err) {
      console.error('Erro ao buscar plano de salário:', err);
    }
  };

  const fetchProvisions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/provisions`);
      const data = await res.json();
      setProvisions(data);
    } catch (err) {
      console.error('Erro ao buscar provisões:', err);
    }
  };

  const fetchMtdAnalytics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/mtd-analytics?month=${selectedMonth}`);
      const data = await res.json();
      setMtdAnalytics(data);
    } catch (err) {
      console.error('Erro ao buscar MTD analytics:', err);
    }
  };

  const fetchCategoryRules = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/category-rules`);
      const data = await res.json();
      setCategoryRules(data);
    } catch (err) {
      console.error('Erro ao buscar regras de categorização:', err);
    }
  };

  const fetchPurchaseSimulations = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/purchase-simulations`);
      const data = await res.json();
      setPurchaseSimulations(data);
    } catch (err) {
      console.error('Erro ao buscar simulações:', err);
    }
  };

  const fetchForecasting = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/forecasting?months=12&start_month=${selectedMonth}`);
      const data = await res.json();
      setForecastingData(data);
    } catch (err) {
      console.error('Erro ao buscar forecasting:', err);
    }
  };

  const fetchPluggyStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/pluggy/status`);
      const data = await res.json();
      setPluggyStatus(data);
    } catch (err) {
      console.error('Erro ao buscar status Pluggy:', err);
    }
  };

  const fetchPluggyAccounts = async () => {
    setPluggyStatusMessage('Buscando contas Pluggy...');
    try {
      const params = new URLSearchParams();
      if (pluggySyncInput.item_ids) params.append('item_ids', pluggySyncInput.item_ids);
      if (pluggySyncInput.account_type) params.append('account_type', pluggySyncInput.account_type);
      const res = await fetch(`${API_BASE}/api/pluggy/accounts?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) {
        setPluggyStatusMessage(data.detail || 'Erro ao buscar contas Pluggy');
        return;
      }
      setPluggyAccounts(Array.isArray(data) ? data : data.results || data.items || data.data || []);
      setPluggyStatusMessage('Contas carregadas.');
    } catch (err) {
      setPluggyStatusMessage('Erro ao conectar com Pluggy.');
    }
  };

  const fetchPluggyAccountAliases = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/pluggy/account-aliases`);
      const data = await res.json();
      setPluggyAccountAliases(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Erro ao buscar aliases Pluggy:', err);
    }
  };

  const handleSavePluggyAlias = async (e: React.FormEvent) => {
    e.preventDefault();
    setPluggyStatusMessage('Salvando apelido da conta...');
    try {
      const res = await fetch(`${API_BASE}/api/pluggy/account-aliases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: pluggyAliasInput.account_id.trim(),
          alias: pluggyAliasInput.alias.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPluggyStatusMessage(data.detail || 'Erro ao salvar apelido.');
        return;
      }
      setPluggyStatusMessage(`Apelido salvo: ${data.alias}. Transacoes atualizadas: ${data.updated_transactions}.`);
      setPluggyAliasInput({ account_id: '', alias: '' });
      fetchPluggyAccountAliases();
      fetchPluggyAccounts();
      fetchTransactions();
      fetchDashboard();
    } catch (err) {
      setPluggyStatusMessage('Erro ao conectar com o backend.');
    }
  };

  const handleDeletePluggyAlias = async (accountId: string) => {
    try {
      await fetch(`${API_BASE}/api/pluggy/account-aliases/${accountId}`, { method: 'DELETE' });
      fetchPluggyAccountAliases();
      fetchTransactions();
      fetchDashboard();
    } catch (err) {
      console.error('Erro ao remover alias Pluggy:', err);
    }
  };

  const handlePluggySync = async (accountIds?: string[], itemId?: string) => {
    setPluggyStatusMessage('Sincronizando transações Pluggy...');
    try {
      const requestedItemIds = itemId ? [itemId] : pluggySyncInput.item_ids.split(',').map(item => item.trim()).filter(Boolean);
      const res = await fetch(`${API_BASE}/api/pluggy/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_ids: requestedItemIds.length ? requestedItemIds : null,
          account_ids: accountIds && accountIds.length ? accountIds : null,
          account_type: pluggySyncInput.account_type || null,
          date_from: pluggySyncInput.date_from || null,
          date_to: pluggySyncInput.date_to || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPluggyStatusMessage(data.detail || 'Erro ao sincronizar Pluggy');
        return;
      }
      setPluggyStatusMessage(`Sincronizado: ${data.total_inserted} novas transações, ${data.total_skipped} ignoradas.`);
      fetchTransactions();
      fetchDashboard();
      fetchBudgets();
      fetchMtdAnalytics();
    } catch (err) {
      setPluggyStatusMessage('Erro ao conectar com Pluggy.');
    }
  };

  const handleFundProvision = async (provId: number, amount: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/provisions/${provId}/fund`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount })
      });
      if (res.ok) {
        fetchProvisions();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao depositar na provisão:', err);
    }
  };

  const handleWithdrawProvision = async (provId: number, amount: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/provisions/${provId}/withdraw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount })
      });
      if (res.ok) {
        fetchProvisions();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao retirar da provisão:', err);
    }
  };

  const handleAddCategoryRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/category-rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pattern: newCategoryRule.pattern,
          category: newCategoryRule.category,
          rule_type: newCategoryRule.rule_type,
          tags: newCategoryRule.tags || null
        })
      });
      if (res.ok) {
        setNewCategoryRule(prev => ({ ...prev, pattern: '', tags: '' }));
        fetchCategoryRules();
      }
    } catch (err) {
      console.error('Erro ao adicionar regra:', err);
    }
  };

  const handleDeleteCategoryRule = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/category-rules/${id}`, { method: 'DELETE' });
      fetchCategoryRules();
    } catch (err) {
      console.error('Erro ao deletar regra:', err);
    }
  };

  const handleValidatePurchase = async (e: React.FormEvent) => {
    e.preventDefault();
    setSimulating(true);
    try {
      const res = await fetch(`${API_BASE}/api/purchase-simulations/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newSimulationInput.title,
          amount: parseFloat(newSimulationInput.amount),
          installments: parseInt(newSimulationInput.installments),
          start_date: newSimulationInput.start_date,
          category: newSimulationInput.category
        })
      });
      const data = await res.json();
      setSimulationResult(data);
    } catch (err) {
      console.error('Erro ao validar compra:', err);
    } finally {
      setSimulating(false);
    }
  };

  const handleSaveSimulation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/purchase-simulations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newSimulationInput.title,
          amount: parseFloat(newSimulationInput.amount),
          installments: parseInt(newSimulationInput.installments),
          start_date: newSimulationInput.start_date,
          category: newSimulationInput.category
        })
      });
      if (res.ok) {
        setNewSimulationInput({ title: '', amount: '', installments: '1', start_date: new Date().toISOString().slice(0, 10), category: 'Compras' });
        setSimulationResult(null);
        fetchPurchaseSimulations();
      }
    } catch (err) {
      console.error('Erro ao salvar simulação:', err);
    }
  };

  const handleConfirmSimulation = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/purchase-simulations/${id}/confirm`, { method: 'POST' });
      if (res.ok) {
        fetchPurchaseSimulations();
        fetchTransactions();
        fetchDashboard();
        fetchForecasting();
      }
    } catch (err) {
      console.error('Erro ao confirmar simulação:', err);
    }
  };

  const handleDeleteSimulation = async (id: number) => {
    try {
      await fetch(`${API_BASE}/api/purchase-simulations/${id}`, { method: 'DELETE' });
      fetchPurchaseSimulations();
    } catch (err) {
      console.error('Erro ao excluir simulação:', err);
    }
  };

  useEffect(() => {
    if (!authChecked || (authRequired && !authToken)) {
      return;
    }
    fetchTransactions();
    fetchDashboard();
    fetchBudgets();
    fetchGoals();
    fetchCategories();
    fetchSalaryPlan();
    fetchProvisions();
    fetchCards();
    fetchMtdAnalytics();
    fetchCategoryRules();
    fetchPurchaseSimulations();
    fetchForecasting();
    fetchPluggyStatus();
    fetchPluggyAccountAliases();
  }, [authChecked, authRequired, authToken, selectedMonth, showAllMonths, transactionFilterMonth, transactionFilterCategory, transactionFilterPaymentMethod, transactionFilterFixed]);

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFiles || uploadFiles.length === 0) return;
    const formData = new FormData();
    const endpoint = uploadFiles.length === 1 ? '/api/upload' : '/api/upload-batch';
    if (uploadFiles.length === 1) {
      formData.append('file', uploadFiles[0]);
    } else {
      Array.from(uploadFiles).forEach(item => formData.append('files', item));
    }

    setUploadStatus(`Processando ${uploadFiles.length} arquivo${uploadFiles.length > 1 ? 's' : ''}...`);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (res.ok) {
        setUploadStatus(`Importado: ${(uploadFiles.length === 1 ? data.inserted : data.total_inserted) ?? 0} novas transações`);
        setUploadFiles(null);
        setTimeout(() => {
          fetchTransactions();
          fetchDashboard();
        }, 500);
      } else {
        setUploadStatus(`✗ Erro: ${data.detail}`);
      }
    } catch (err) {
      setUploadStatus('✗ Erro ao conectar');
    }
  };

  const handleAddTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    const selectedCard = cards.find(card => card.name === newTransaction.payment_method);
    const category = newTransaction.type === 'income' && newTransaction.category === 'Outros' ? 'Renda' : newTransaction.category;
    const payload = {
      date: newTransaction.date,
      title: newTransaction.title,
      amount: parseFloat(newTransaction.amount),
      category,
      card_source: selectedCard ? selectedCard.name : newTransaction.payment_method,
      payment_method: selectedCard ? 'Cartão' : newTransaction.payment_method,
      is_fixed: newTransaction.type === 'income' ? 0 : (newTransaction.is_fixed ? 1 : 0),
      is_income: newTransaction.type === 'income' ? 1 : 0,
    };

    try {
      const res = await fetch(`${API_BASE}/api/transactions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setNewTransaction({ date: new Date().toISOString().slice(0, 10), title: '', amount: '', category: newTransaction.type === 'income' ? 'Renda' : categories[0] || 'Outros', type: newTransaction.type, payment_method: 'Manual', is_fixed: false, tags: '' });
        fetchTransactions();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao adicionar transação:', err);
    }
  };

  const handleEditTransaction = (tx: Transaction) => {
    setEditingTransaction(tx);
  };

  const handleMoveTransactionNextMonth = async (tx: Transaction) => {
    try {
      const res = await fetch(`${API_BASE}/api/transactions/${tx.id}/move-next-month`, {
        method: 'POST',
      });
      if (res.ok) {
        fetchTransactions();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao mover transação para o próximo mês:', err);
    }
  };

  const handleClearTransactionFilters = () => {
    setTransactionFilterMonth(new Date().toISOString().slice(0, 7));
    setTransactionFilterCategory('');
    setTransactionFilterPaymentMethod('');
    setTransactionFilterFixed('all');
  };

  const toggleParentExpansion = (parentId: number) => {
    setExpandedParents(prev =>
      prev.includes(parentId) ? prev.filter(id => id !== parentId) : [...prev, parentId]
    );
  };

  const handleCancelEdit = () => {
    setEditingTransaction(null);
  };

  const handleDeleteTransaction = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir esta transação? Esta ação não pode ser desfeita.')) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/transactions/${id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        fetchTransactions();
        fetchDashboard();
        if (activeTab === 'budgets') {
          fetchBudgets();
        }
      } else {
        console.error('Erro ao excluir transação');
        alert('Erro ao excluir transação. Tente novamente.');
      }
    } catch (err) {
      console.error('Erro ao conectar:', err);
      alert('Erro ao conectar com o servidor.');
    }
  };

  const handleUpdateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTransaction?.id) {
      return;
    }

    const payload = {
      date: editingTransaction.date,
      title: editingTransaction.title,
      amount: editingTransaction.amount,
      category: editingTransaction.category,
      card_source: editingTransaction.card_source || 'Manual',
      payment_method: editingTransaction.payment_method || 'Manual',
      is_fixed: editingTransaction.is_fixed ? 1 : 0,
      is_income: editingTransaction.is_income ? 1 : 0,
    };

    try {
      const res = await fetch(`${API_BASE}/api/transactions/${editingTransaction.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setEditingTransaction(null);
        fetchTransactions();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao atualizar transação:', err);
    }
  };

  const handleAddBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/budgets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          month: selectedMonth,
          category: newBudget.category,
          limit_amount: parseFloat(newBudget.limit_amount),
        }),
      });
      if (res.ok) {
        setNewBudget({ category: categories[0] || 'Outros', limit_amount: '' });
        fetchBudgets();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao salvar orçamento:', err);
    }
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/api/categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCategory),
      });
      if (res.ok) {
        setNewCategory({ name: '', color: '#3b82f6' });
        fetchCategories();
      }
    } catch (err) {
      console.error('Erro ao criar categoria:', err);
    }
  };

  const handleAddGoalContribution = async (goalId: number) => {
    const amount = parseFloat(goalContributions[goalId] || '0');
    if (!amount || amount <= 0) return;
    try {
      const res = await fetch(`${API_BASE}/api/goals/${goalId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ add_amount: amount }),
      });
      if (res.ok) {
        setGoalContributions(prev => ({ ...prev, [goalId]: '' }));
        fetchGoals();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao atualizar meta:', err);
    }
  };

  const handleAddGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: newGoal.name,
      target_amount: parseFloat(newGoal.target_amount),
      deadline: newGoal.deadline,
      status: 'active',
    };

    try {
      const res = await fetch(`${API_BASE}/api/goals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setNewGoal({ name: '', target_amount: '', deadline: '' });
        fetchGoals();
      }
    } catch (err) {
      console.error('Erro ao adicionar meta:', err);
    }
  };

  const handleSetSalaryPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        effective_date: salaryInput.effective_date,
        gross_amount: parseFloat(salaryInput.gross_amount),
        net_amount: salaryInput.net_amount ? parseFloat(salaryInput.net_amount) : null,
      };
      const res = await fetch(`${API_BASE}/api/salary-plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        fetchSalaryPlan();
        fetchDashboard();
      }
    } catch (err) {
      console.error('Erro ao salvar renda atual:', err);
    }
  };

  const handleAddProvision = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        title: newProvision.title,
        amount: parseFloat(newProvision.amount),
        category: newProvision.category,
        start_date: newProvision.start_date,
        end_date: newProvision.end_date || null,
        frequency: newProvision.frequency,
        is_income: 0,
        payment_method: newProvision.payment_method,
        status: 'active',
      };
      const res = await fetch(`${API_BASE}/api/provisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setNewProvision({ title: '', amount: '', category: categories[0] || 'Outros', start_date: new Date().toISOString().slice(0, 10), end_date: '', frequency: 'monthly', payment_method: 'Pix', current_amount: '0', target_amount: '' });
        fetchProvisions();
      }
    } catch (err) {
      console.error('Erro ao adicionar provisão:', err);
    }
  };

  const handleDeleteProvision = async (id: number) => {
    try {
      const res = await fetch(`${API_BASE}/api/provisions/${id}`, { method: 'DELETE' });
      if (res.ok) {
        fetchProvisions();
      }
    } catch (err) {
      console.error('Erro ao excluir provisão:', err);
    }
  };

  const chartData = dashboardData ? Object.entries(dashboardData.expenses_by_category).map(([name, value]) => ({ name, value })) : [];
  const COLORS = ['#f87171', '#fb923c', '#fbbf24', '#a3e635', '#22d3ee', '#a78bfa', '#f472b6'];
  const selectedPurchaseCard = cards.find(card => card.id.toString() === purchaseCalendarInput.payment_method);
  const purchaseAmount = parseFloat(purchaseCalendarInput.amount) || 0;
  const purchaseInstallments = Math.max(parseInt(purchaseCalendarInput.installments, 10) || 1, 1);
  const forecastByMonth = forecastingData.reduce<Record<string, { projected_income: number; projected_net_worth: number }>>((acc, item) => {
    acc[item.month] = item;
    return acc;
  }, {});

  const formatMonth = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  const addMonths = (date: Date, count: number) => new Date(date.getFullYear(), date.getMonth() + count, 1);
  const daysInMonth = (month: string) => new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate();
  const monthLabel = (month: string) => new Date(`${month}-01T00:00:00`).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });

  const cardDueDateForPurchase = (purchaseDate: Date, card: Card) => {
    const billMonth = purchaseDate.getDate() <= card.closing_day
      ? new Date(purchaseDate.getFullYear(), purchaseDate.getMonth(), 1)
      : new Date(purchaseDate.getFullYear(), purchaseDate.getMonth() + 1, 1);
    const lastDay = new Date(billMonth.getFullYear(), billMonth.getMonth() + 1, 0).getDate();
    return new Date(billMonth.getFullYear(), billMonth.getMonth(), Math.min(card.due_day, lastDay));
  };

  const evaluatePurchaseDay = (day: number) => {
    const amount = purchaseAmount;
    const installments = selectedPurchaseCard ? purchaseInstallments : 1;
    const installmentAmount = installments > 0 ? amount / installments : amount;
    const purchaseDate = new Date(`${purchaseCalendarInput.month}-${String(day).padStart(2, '0')}T00:00:00`);
    const firstDueDate = selectedPurchaseCard ? cardDueDateForPurchase(purchaseDate, selectedPurchaseCard) : purchaseDate;
    const firstDueMonth = formatMonth(firstDueDate);
    const paymentMonths = Array.from({ length: installments }, (_, index) => formatMonth(addMonths(firstDueDate, index)));
    const impactedMonths = forecastingData
      .filter(item => item.month >= firstDueMonth)
      .map(item => item.month);
    const monthsToCheck = impactedMonths.length ? impactedMonths : paymentMonths;
    let worstBalance = Number.POSITIVE_INFINITY;

    monthsToCheck.forEach(month => {
      const forecast = forecastByMonth[month];
      const baseBalance = forecast?.projected_net_worth ?? (dashboardData?.carryover_balance ?? 0);
      const installmentsDue = paymentMonths.filter(paymentMonth => paymentMonth <= month).length;
      const simulatedBalance = baseBalance - (installmentsDue * installmentAmount);
      worstBalance = Math.min(worstBalance, simulatedBalance);
    });

    if (!Number.isFinite(worstBalance)) {
      worstBalance = (dashboardData?.carryover_balance ?? 0) - amount;
    }

    const incomeRef = forecastByMonth[firstDueMonth]?.projected_income ?? dashboardData?.total_income ?? 0;
    const marginPct = incomeRef > 0 ? (worstBalance / incomeRef) * 100 : 0;
    const status = worstBalance < 0 ? 'bad' : marginPct < 10 ? 'warn' : 'good';

    return {
      day,
      status,
      firstDueMonth,
      firstDueDate: firstDueDate.toISOString().slice(0, 10),
      installmentAmount,
      worstBalance,
      paymentMonths,
      marginPct,
    };
  };

  const purchaseCalendarDays = Array.from({ length: daysInMonth(purchaseCalendarInput.month) }, (_, index) => evaluatePurchaseDay(index + 1));
  const bestPurchaseDay = purchaseCalendarDays.reduce((best, item) => item.worstBalance > best.worstBalance ? item : best, purchaseCalendarDays[0]);
  const worstPurchaseDay = purchaseCalendarDays.reduce((worst, item) => item.worstBalance < worst.worstBalance ? item : worst, purchaseCalendarDays[0]);

  if (!authChecked) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <p className="text-sm text-slate-400">Carregando...</p>
      </div>
    );
  }

  if (authRequired && !authToken) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
        <div className="w-full max-w-sm rounded-lg border border-slate-700 bg-slate-900 p-6">
          <h1 className="text-xl font-bold">{authMode === 'register' ? 'Criar acesso' : 'Entrar'}</h1>
          <p className="mt-1 text-sm text-slate-400">
            {authMode === 'register' ? 'Cadastre o primeiro usuario para proteger seus dados.' : 'Acesse para ver suas informacoes financeiras.'}
          </p>
          <form onSubmit={handleAuthSubmit} className="mt-6 space-y-4">
            <input
              type="email"
              value={authEmail}
              onChange={e => setAuthEmail(e.target.value)}
              placeholder="email"
              required
              className="w-full rounded border border-slate-600 bg-slate-950 p-3 text-sm focus:border-blue-400 focus:outline-none"
            />
            <input
              type="password"
              value={authPassword}
              onChange={e => setAuthPassword(e.target.value)}
              placeholder="senha"
              required
              minLength={6}
              className="w-full rounded border border-slate-600 bg-slate-950 p-3 text-sm focus:border-blue-400 focus:outline-none"
            />
            {authError && <p className="text-sm text-red-300">{authError}</p>}
            <button type="submit" className="w-full rounded bg-blue-600 py-3 text-sm font-bold text-white hover:bg-blue-500">
              {authMode === 'register' ? 'CRIAR ACESSO' : 'ENTRAR'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-100 font-sans">
      <header className="bg-slate-950 border-b border-slate-700/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">Finance App</h1>
            <p className="text-xs text-slate-400 mt-1">Gestor Financeiro Local</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-xs text-emerald-400 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              Backend Conectado
            </div>
            {authToken && (
              <button type="button" onClick={handleLogout} className="rounded border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800">
                Sair
              </button>
            )}
          </div>
        </div>
        <nav className="max-w-7xl mx-auto px-6 flex gap-1 border-t border-slate-700/50 overflow-x-auto">
          {[
            { id: 'dashboard', label: 'Dashboard', icon: DollarSign },
            { id: 'transactions', label: 'Transações', icon: Plus },
            { id: 'pluggy', label: 'Pluggy', icon: Upload },
            { id: 'categories', label: 'Categorias', icon: TrendingUp },
            { id: 'budgets', label: 'Orçamentos', icon: Calendar },
            { id: 'goals', label: 'Metas', icon: Target },
            { id: 'provisions', label: 'Provisões', icon: AlertCircle },
            { id: 'purchase-validator', label: 'Calendario de Compra', icon: ShoppingBag },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition ${activeTab === tab.id ? 'border-blue-400 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-300'
                }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-2xl font-semibold">Dashboard</h2>
                <p className="text-sm text-slate-400 mt-1">Resumo por mês, tendência e agrupamento por categoria.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_auto] items-center">
                <div className="flex items-center gap-3">
                  <label className="text-xs uppercase tracking-[0.2em] text-slate-500">Mês</label>
                  <input
                    type="month"
                    value={selectedMonth}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSelectedMonth(e.target.value)}
                    disabled={showAllMonths}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setShowAllMonths(prev => !prev)}
                  className="inline-flex items-center justify-center rounded bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500"
                >
                  {showAllMonths ? 'Exibir mês selecionado' : 'Exibir todo o histórico'}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-6 gap-4">
              <div className="bg-slate-800/50 border border-slate-700 p-5 rounded-lg">
                <p className="text-slate-400 text-xs font-semibold uppercase">Renda do Mes</p>
                <p className="text-2xl font-bold text-cyan-400 mt-2">R$ {(dashboardData?.total_income ?? 0).toFixed(2)}</p>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-5 rounded-lg">
                <p className="text-slate-400 text-xs font-semibold uppercase">Despesas do Mês</p>
                <p className="text-2xl font-bold text-red-400 mt-2">R$ {(dashboardData?.total_expense ?? 0).toFixed(2)}</p>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-5 rounded-lg">
                <p className="text-slate-400 text-xs font-semibold uppercase">Saldo Geral (Lançado)</p>
                <p className={`text-2xl font-bold mt-2 ${(dashboardData?.balance ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  R$ {(dashboardData?.balance ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-5 rounded-lg">
                <p className="text-slate-400 text-xs font-semibold uppercase">Saldo Acumulado</p>
                <p className={`text-2xl font-bold mt-2 ${(dashboardData?.carryover_balance ?? dashboardData?.balance ?? 0) >= 0 ? 'text-sky-400' : 'text-red-400'}`}>
                  R$ {(dashboardData?.carryover_balance ?? dashboardData?.balance ?? 0).toFixed(2)}
                </p>
                {(dashboardData?.residual_debt ?? 0) > 0 && (
                  <p className="text-xs text-red-300 mt-1">Divida residual: R$ {(dashboardData?.residual_debt ?? 0).toFixed(2)}</p>
                )}
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-5 rounded-lg">
                <p className="text-slate-400 text-xs font-semibold uppercase">Saldo Reservado (Provisões)</p>
                <p className="text-2xl font-bold text-orange-400 mt-2">R$ {(dashboardData?.ring_fenced_provisions_total ?? 0).toFixed(2)}</p>
              </div>
              <div className="bg-slate-800/50 border-2 border-emerald-500/30 p-5 rounded-lg bg-slate-900/50">
                <p className="text-emerald-400 text-xs font-semibold uppercase flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  Disponível para Gastar
                </p>
                <p className={`text-3xl font-black mt-2 ${(dashboardData?.available_to_spend ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  R$ {(dashboardData?.available_to_spend ?? 0).toFixed(2)}
                </p>
              </div>
            </div>

            {/* Health & MTD Analytics Dashboard */}
            {mtdAnalytics && (
              <div className="bg-slate-800/40 border border-slate-700/80 p-6 rounded-lg space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-bold flex items-center gap-2 text-blue-400">
                      <Sparkles size={18} /> Saúde Financeira do Mês
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">Métricas em tempo real (Month-to-Date) e projeções baseadas no seu ritmo de gastos.</p>
                  </div>
                  <div className="flex flex-wrap gap-4 text-xs">
                    <div className="bg-slate-900/80 px-3 py-2 rounded border border-slate-700/60">
                      <span className="text-slate-400">Burn Rate (Discrecionário):</span>{" "}
                      <span className="font-bold text-orange-400">R$ {mtdAnalytics.burn_rate.toFixed(2)} / dia</span>
                    </div>
                    <div className="bg-slate-900/80 px-3 py-2 rounded border border-slate-700/60">
                      <span className="text-slate-400">Gasto Projetado Variável:</span>{" "}
                      <span className="font-bold text-slate-200">R$ {mtdAnalytics.projected_var_spend.toFixed(2)}</span>
                    </div>
                    <div className="bg-slate-900/80 px-3 py-2 rounded border border-slate-700/60">
                      <span className="text-slate-400">Saldo Final Projetado:</span>{" "}
                      <span className={`font-bold ${mtdAnalytics.projected_balance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        R$ {mtdAnalytics.projected_balance.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Progress toward end-of-month projected budget */}
                <div className="bg-slate-900/40 p-4 rounded-lg border border-slate-700/30">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Previsão total de saídas (Variável + Fixo):</span>
                    <span className="font-semibold text-slate-200">R$ {mtdAnalytics.total_projected_expense.toFixed(2)} de R$ {mtdAnalytics.total_projected_income.toFixed(2)} previsto</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${mtdAnalytics.total_projected_expense > mtdAnalytics.total_projected_income ? 'bg-red-500' : 'bg-blue-500'}`}
                      style={{ width: `${Math.min((mtdAnalytics.total_projected_expense / (mtdAnalytics.total_projected_income || 1)) * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Dynamic Insights Alerts */}
                {mtdAnalytics.alerts && mtdAnalytics.alerts.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                    {mtdAnalytics.alerts.map((alert: any, i: number) => (
                      <div
                        key={i}
                        className={`flex items-start gap-3 p-3 rounded-md text-xs border ${alert.type === 'warning'
                          ? 'bg-red-950/20 border-red-500/20 text-red-300'
                          : 'bg-emerald-950/20 border-emerald-500/20 text-emerald-300'
                          }`}
                      >
                        <AlertTriangle size={16} className={alert.type === 'warning' ? 'text-red-400 flex-shrink-0 mt-0.5' : 'text-emerald-400 flex-shrink-0 mt-0.5'} />
                        <p>{alert.message}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-6">
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold">Tendência Mensal</h3>
                  <span className="text-xs text-slate-500">Últimos meses</span>
                </div>
                {monthlySummary.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={monthlySummary} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
                      <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fill: '#cbd5e1', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#cbd5e1', fontSize: 12 }} />
                      <Tooltip formatter={(value: number) => `R$ ${value.toFixed(2)}`} />
                      <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: 12 }} />
                      <Line type="monotone" dataKey="income" stroke="#22c55e" strokeWidth={2} name="Renda" />
                      <Line type="monotone" dataKey="expense" stroke="#ef4444" strokeWidth={2} name="Despesa" />
                      <Line type="monotone" dataKey="balance" stroke="#38bdf8" strokeWidth={2} name="Balanço" />
                      <Line type="monotone" dataKey="carryover_balance" stroke="#a78bfa" strokeWidth={2} name="Saldo Acumulado" />
                      <Line type="monotone" dataKey="projected_balance" stroke="#facc15" strokeWidth={2} name="Balanço Projetado" strokeDasharray="4 4" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-slate-400 text-center py-16">Sem histórico suficiente para mostrar tendência.</p>
                )}
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <h3 className="text-lg font-semibold mb-4">Despesas por Categoria</h3>
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={chartData} cx="50%" cy="50%" labelLine={false} label={({ name, value }) => `${name}: R$ ${value.toFixed(0)}`} outerRadius={100} fill="#8884d8" dataKey="value">
                        {chartData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `R$ ${Number(value).toFixed(2)}`} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-slate-400 text-center py-16">Sem despesas para este período.</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <h3 className="text-lg font-semibold mb-4">Agrupamento por Categoria</h3>
                {Object.entries(dashboardData?.expenses_by_category || {}).length > 0 ? (
                  <div className="space-y-3">
                    {Object.entries(dashboardData.expenses_by_category)
                      .sort(([, a], [, b]) => b - a)
                      .map(([category, amount]) => (
                        <div key={category} className="flex justify-between items-center gap-4">
                          <span className="text-slate-200">{category}</span>
                          <span className="text-slate-400">R$ {(amount as number).toFixed(2)}</span>
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="text-slate-400">Nenhuma categoria com despesas neste período.</p>
                )}
              </div>
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <h3 className="text-lg font-semibold mb-4">Resumo do período</h3>
                <div className="space-y-3 text-sm text-slate-300">
                  <div className="flex justify-between"><span>Total de meses acompanhados</span><span>{monthlySummary.length}</span></div>
                  <div className="flex justify-between"><span>Mês atual</span><span>{showAllMonths ? 'Todos' : selectedMonth}</span></div>
                  <div className="flex justify-between"><span>Maior despesa</span><span>R$ {chartData.length > 0 ? Math.max(...chartData.map(item => item.value)).toFixed(2) : '0.00'}</span></div>
                </div>
              </div>
            </div>

            {/* Future Timeline & Net Worth Forecasting */}
            {forecastingData && forecastingData.length > 0 && (
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                      <TrendingUp size={18} className="text-blue-400" /> Projeção de Patrimônio Líquido (12 Meses)
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">Evolução estimada com base nos salários cadastrados e provisões recorrentes ativas.</p>
                  </div>
                  <span className="text-xs text-blue-400 font-semibold bg-blue-500/10 px-2 py-1 rounded">Horizonte de 12 meses</span>
                </div>
                <div className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={forecastingData} margin={{ top: 10, right: 16, left: -6, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorNetWorth" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.01} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fill: '#cbd5e1', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#cbd5e1', fontSize: 12 }} />
                      <Tooltip formatter={(value: number) => `R$ ${value.toFixed(2)}`} />
                      <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: 12 }} />
                      <Area type="monotone" dataKey="projected_net_worth" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorNetWorth)" name="Patrimônio Líquido" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1">
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg sticky top-24">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Plus size={18} /> Nova Movimentacao
                </h3>
                <form onSubmit={handleAddTransaction} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Data</label>
                    <input
                      type="date"
                      value={newTransaction.date}
                      onChange={e => setNewTransaction({ ...newTransaction, date: e.target.value })}
                      required
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Descrição</label>
                    <input
                      type="text"
                      value={newTransaction.title}
                      onChange={e => setNewTransaction({ ...newTransaction, title: e.target.value })}
                      placeholder={newTransaction.type === 'income' ? 'Ex: Trabalho extra, venda de item' : 'Ex: Mercado'}
                      required
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Tipo</label>
                      <select
                        value={newTransaction.type}
                        onChange={e => {
                          const type = e.target.value as 'expense' | 'income';
                          setNewTransaction({
                            ...newTransaction,
                            type,
                            category: type === 'income' ? 'Renda' : newTransaction.category,
                            is_fixed: type === 'income' ? false : newTransaction.is_fixed,
                          });
                        }}
                        className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                      >
                        <option value="expense">Despesa</option>
                        <option value="income">Ganho pontual</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Valor (R$)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={newTransaction.amount}
                        onChange={e => setNewTransaction({ ...newTransaction, amount: e.target.value })}
                        placeholder="0.00"
                        required
                        className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Via</label>
                      <select
                        value={newTransaction.payment_method}
                        onChange={e => setNewTransaction({ ...newTransaction, payment_method: e.target.value })}
                        className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                      >
                        <option value="Manual">Manual</option>
                        <option value="Pix">Pix</option>
                        <option value="Cartão">Cartão</option>
                        {cards.map(card => (
                          <option key={card.id} value={card.name}>{card.name}</option>
                        ))}
                        <option value="Outro">Outro</option>
                      </select>
                    </div>
                    <div className="flex items-end gap-3">
                      {newTransaction.type === 'expense' && (
                        <label className="flex items-center gap-2 text-xs text-slate-400">
                          <input
                            type="checkbox"
                            checked={newTransaction.is_fixed}
                            onChange={e => setNewTransaction({ ...newTransaction, is_fixed: e.target.checked })}
                            className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-blue-500"
                          />
                          Gasto fixo
                        </label>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Categoria</label>
                    <select
                      value={newTransaction.category}
                      onChange={e => setNewTransaction({ ...newTransaction, category: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      {(categories.length ? categories : ['Alimentação', 'Transporte', 'Moradia', 'Utilities', 'Saúde', 'Educação', 'Lazer', 'Compras', 'Renda', 'Outros']).map(category => (
                        <option key={category} value={category}>{category}</option>
                      ))}
                    </select>
                  </div>
                  <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded transition">
                    {newTransaction.type === 'income' ? 'SALVAR GANHO' : 'SALVAR DESPESA'}
                  </button>
                </form>

                <div className="mt-6 pt-6 border-t border-slate-700">
                  <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <Upload size={16} /> Importar CSV/PDF
                  </h4>
                  <form onSubmit={handleFileUpload} className="space-y-3">
                    <input
                      type="file"
                      accept=".csv,.pdf"
                      multiple
                      onChange={e => setUploadFiles(e.target.files)}
                      className="text-xs w-full"
                    />
                    <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded transition text-xs">
                      PROCESSAR IMPORTAÇÃO
                    </button>
                  </form>
                  {uploadStatus && <p className="text-xs mt-2 text-emerald-400">{uploadStatus}</p>}
                </div>

                <div className="mt-6 pt-6 border-t border-slate-700">
                  <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <Calendar size={16} /> Cartões
                  </h4>
                  <form onSubmit={handleAddCard} className="space-y-3">
                    <input
                      type="text"
                      value={newCard.name}
                      onChange={e => setNewCard({ ...newCard, name: e.target.value })}
                      placeholder="Nome do cartão"
                      required
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <label className="text-xs text-slate-400">
                        Fechamento
                        <input
                          type="number"
                          min={1}
                          max={31}
                          value={newCard.closing_day}
                          onChange={e => setNewCard({ ...newCard, closing_day: parseInt(e.target.value, 10) || 1 })}
                          className="mt-1 w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        />
                      </label>
                      <label className="text-xs text-slate-400">
                        Vencimento
                        <input
                          type="number"
                          min={1}
                          max={31}
                          value={newCard.due_day}
                          onChange={e => setNewCard({ ...newCard, due_day: parseInt(e.target.value, 10) || 1 })}
                          className="mt-1 w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        />
                      </label>
                    </div>
                    <button type="submit" className="w-full bg-slate-700 hover:bg-slate-600 text-white font-bold py-2 rounded transition text-xs">
                      SALVAR CARTÃO
                    </button>
                  </form>
                  <div className="mt-3 space-y-2">
                    {cards.map(card => (
                      <div key={card.id} className="flex items-center justify-between rounded border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs">
                        <span className="font-semibold text-slate-200">{card.name}</span>
                        <span className="text-slate-400">Fecha {card.closing_day} • Vence {card.due_day}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-3">
              {editingTransaction && (
                <div className="bg-slate-800/60 border border-slate-600 p-6 rounded-lg mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">Editando transação</h3>
                    <button
                      type="button"
                      onClick={handleCancelEdit}
                      className="text-xs text-slate-300 hover:text-slate-100"
                    >
                      Cancelar
                    </button>
                  </div>
                  <form onSubmit={handleUpdateTransaction} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Data</label>
                        <input
                          type="date"
                          value={editingTransaction.date}
                          onChange={e => setEditingTransaction({ ...editingTransaction, date: e.target.value })}
                          required
                          className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Valor (R$)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={editingTransaction.amount}
                          onChange={e => setEditingTransaction({ ...editingTransaction, amount: parseFloat(e.target.value) || 0 })}
                          required
                          className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1">Descrição</label>
                      <input
                        type="text"
                        value={editingTransaction.title}
                        onChange={e => setEditingTransaction({ ...editingTransaction, title: e.target.value })}
                        required
                        className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                      />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Categoria</label>
                        <select
                          value={editingTransaction.category}
                          onChange={e => setEditingTransaction({ ...editingTransaction, category: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        >
                          {(categories.length ? categories : ['Outros']).map(category => (
                            <option key={category} value={category}>{category}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 mb-1">Via</label>
                        <select
                          value={editingTransaction.payment_method || 'Manual'}
                          onChange={e => setEditingTransaction({ ...editingTransaction, payment_method: e.target.value })}
                          className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        >
                          <option value="Manual">Manual</option>
                          <option value="Pix">Pix</option>
                          <option value="Cartão">Cartão</option>
                          <option value="Outro">Outro</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-slate-400">
                        <input
                          type="checkbox"
                          checked={Boolean(editingTransaction.is_fixed)}
                          onChange={e => setEditingTransaction({ ...editingTransaction, is_fixed: e.target.checked ? 1 : 0 })}
                          className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-blue-500"
                        />
                        Gasto fixo
                      </label>
                      <button type="submit" className="ml-auto bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded transition text-xs">
                        SALVAR ALTERAÇÕES
                      </button>
                    </div>
                  </form>
                </div>
              )}
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-4">
                  <h3 className="text-lg font-semibold">Histórico de Transações</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 w-full md:w-auto">
                    <input
                      type="month"
                      value={transactionFilterMonth}
                      onChange={e => setTransactionFilterMonth(e.target.value)}
                      className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                    <select
                      value={transactionFilterCategory}
                      onChange={e => setTransactionFilterCategory(e.target.value)}
                      className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      <option value="">Todas categorias</option>
                      {(categories.length ? categories : ['Outros']).map(category => (
                        <option key={category} value={category}>{category}</option>
                      ))}
                    </select>
                    <select
                      value={transactionFilterPaymentMethod}
                      onChange={e => setTransactionFilterPaymentMethod(e.target.value)}
                      className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      <option value="">Todas vias</option>
                      <option value="Manual">Manual</option>
                      <option value="Pix">Pix</option>
                      <option value="Cartão">Cartão</option>
                      <option value="Outro">Outro</option>
                    </select>
                    <select
                      value={transactionFilterFixed}
                      onChange={e => setTransactionFilterFixed(e.target.value)}
                      className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      <option value="all">Todos</option>
                      <option value="sim">Fixos</option>
                      <option value="nao">Não fixos</option>
                    </select>
                    <button
                      type="button"
                      onClick={handleClearTransactionFilters}
                      className="bg-slate-700 border border-slate-600 text-slate-100 px-3 py-2 rounded text-xs font-semibold hover:bg-slate-600"
                    >
                      Limpar filtros
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="border-b border-slate-600">
                      <tr className="text-slate-400">
                        <th className="text-left py-2">Data</th>
                        <th className="text-left py-2">Descrição</th>
                        <th className="text-left py-2">Categoria</th>
                        <th className="text-left py-2">Via</th>
                        <th className="text-center py-2">Fixo</th>
                        <th className="text-right py-2">Valor</th>
                        <th className="text-right py-2">Ações</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                      {(() => {
                        const childMap: Record<number, Transaction[]> = {};
                        transactions.forEach(tx => {
                          if (tx.parent_id) {
                            childMap[tx.parent_id] = childMap[tx.parent_id] || [];
                            childMap[tx.parent_id].push(tx);
                          }
                        });
                        const parentTransactions = transactions
                          .filter(tx => !tx.parent_id)
                          .sort((a, b) => b.date.localeCompare(a.date));

                        return parentTransactions.flatMap((tx, idx) => {
                          const children = tx.id ? childMap[tx.id] || [] : [];
                          const isExpanded = tx.id ? expandedParents.includes(tx.id) : false;
                          const rows: React.ReactNode[] = [
                            <tr key={`parent-${tx.id}-${idx}`} className="hover:bg-slate-700/30">
                              <td className="py-2">
                                <div className="flex items-center gap-2">
                                  {children.length > 0 ? (
                                    <button
                                      type="button"
                                      onClick={() => tx.id && toggleParentExpansion(tx.id)}
                                      className="text-slate-400 hover:text-slate-100"
                                    >
                                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                    </button>
                                  ) : (
                                    <span className="w-4" />
                                  )}
                                  <span>{tx.date}</span>
                                </div>
                              </td>
                              <td className="py-2 font-semibold">{tx.title}</td>
                              <td className="py-2">{tx.category}</td>
                              <td className="py-2">{tx.card_source || tx.payment_method || 'Manual'}</td>
                              <td className="py-2 text-center">{tx.is_fixed ? 'Sim' : 'Não'}</td>
                              <td className={`py-2 text-right font-semibold ${tx.amount < 0 ? 'text-green-400' : 'text-red-400'}`}>
                                R$ {tx.amount.toFixed(2)}
                              </td>
                              <td className="py-2 text-right space-x-2 whitespace-nowrap">
                                <button
                                  type="button"
                                  onClick={() => handleEditTransaction(tx)}
                                  className="text-blue-400 hover:text-blue-200 text-xs font-semibold"
                                >
                                  Editar
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteTransaction(tx.id!)}
                                  className="text-red-400 hover:text-red-200 text-xs font-semibold"
                                >
                                  Excluir
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleMoveTransactionNextMonth(tx)}
                                  className="text-orange-400 hover:text-orange-200 text-xs font-semibold"
                                >
                                  Não pago
                                </button>
                              </td>
                            </tr>
                          ];
                          if (isExpanded) {
                            const sortedChildren = children.sort((a, b) => b.date.localeCompare(a.date));
                            rows.push(
                              ...sortedChildren.map(child => (
                                <tr key={`child-${child.id}`} className="bg-slate-900/80 hover:bg-slate-700/30">
                                  <td className="py-2 pl-8 text-slate-300">{child.date}</td>
                                  <td className="py-2 text-slate-300">{child.title}</td>
                                  <td className="py-2 text-slate-300">{child.category}</td>
                                  <td className="py-2 text-slate-300">{child.card_source || child.payment_method || 'Manual'}</td>
                                  <td className="py-2 text-center text-slate-300">{child.is_fixed ? 'Sim' : 'Não'}</td>
                                  <td className="py-2 text-right font-semibold text-slate-300">R$ {child.amount.toFixed(2)}</td>
                                  <td className="py-2 text-right whitespace-nowrap">
                                    <button
                                      type="button"
                                      onClick={() => handleEditTransaction(child)}
                                      className="text-blue-400 hover:text-blue-200 text-xs font-semibold mr-2"
                                    >
                                      Editar
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteTransaction(child.id!)}
                                      className="text-red-400 hover:text-red-200 text-xs font-semibold"
                                    >
                                      Excluir
                                    </button>
                                  </td>
                                </tr>
                              ))
                            );
                          }
                          return rows;
                        });
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'pluggy' && (
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Pluggy</h3>
              <div className="mb-4 rounded border border-slate-700 bg-slate-900/70 p-3 text-xs text-slate-300">
                <div className="flex justify-between"><span>Configuração</span><span className={pluggyStatus?.configured ? 'text-emerald-400' : 'text-red-400'}>{pluggyStatus?.configured ? 'OK' : 'Pendente'}</span></div>
                <div className="mt-1 flex justify-between"><span>Item IDs</span><span className={pluggyStatus?.has_item_ids ? 'text-emerald-400' : 'text-slate-400'}>{pluggyStatus?.has_item_ids ? `${pluggyStatus.item_ids_count || 1} configurado(s)` : 'Opcional'}</span></div>
              </div>
              <div className="space-y-3">
                <input
                  type="text"
                  value={pluggySyncInput.item_ids}
                  onChange={e => setPluggySyncInput({ ...pluggySyncInput, item_ids: e.target.value })}
                  placeholder="Item IDs separados por virgula (opcional se PLUGGY_ITEM_IDS estiver no Docker)"
                  className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                />
                <div className="grid grid-cols-2 gap-3">
                  <select
                    value={pluggySyncInput.account_type}
                    onChange={e => setPluggySyncInput({ ...pluggySyncInput, account_type: e.target.value })}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  >
                    <option value="">Todas contas</option>
                    <option value="BANK">Banco</option>
                    <option value="CREDIT">Crédito</option>
                  </select>
                  <button type="button" onClick={fetchPluggyAccounts} className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded transition text-xs">
                    BUSCAR CONTAS
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="date"
                    value={pluggySyncInput.date_from}
                    onChange={e => setPluggySyncInput({ ...pluggySyncInput, date_from: e.target.value })}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="date"
                    value={pluggySyncInput.date_to}
                    onChange={e => setPluggySyncInput({ ...pluggySyncInput, date_to: e.target.value })}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <button type="button" onClick={() => handlePluggySync()} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded transition text-xs">
                  SINCRONIZAR PERÍODO
                </button>
                {pluggyStatusMessage && <p className="text-xs text-slate-300">{pluggyStatusMessage}</p>}
              </div>

              <div className="mt-6 border-t border-slate-700 pt-5">
                <h4 className="text-sm font-semibold mb-3">Apelidos de contas</h4>
                <form onSubmit={handleSavePluggyAlias} className="space-y-3">
                  <input
                    type="text"
                    value={pluggyAliasInput.account_id}
                    onChange={e => setPluggyAliasInput({ ...pluggyAliasInput, account_id: e.target.value })}
                    placeholder="Account ID Pluggy"
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <div className="grid grid-cols-[1fr_auto] gap-3">
                    <input
                      type="text"
                      value={pluggyAliasInput.alias}
                      onChange={e => setPluggyAliasInput({ ...pluggyAliasInput, alias: e.target.value })}
                      placeholder="Ex: Itau, Nubank"
                      required
                      className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                    <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2 rounded transition text-xs">
                      SALVAR
                    </button>
                  </div>
                </form>
                <div className="mt-4 space-y-2">
                  {pluggyAccountAliases.length > 0 ? pluggyAccountAliases.map(item => (
                    <div key={item.account_id} className="rounded border border-slate-700 bg-slate-900/70 p-3 text-xs">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-100">{item.alias}</p>
                          <p className="mt-1 break-all text-slate-500">{item.account_id}</p>
                          <p className="mt-1 text-slate-400">{item.transaction_count || 0} transacoes vinculadas</p>
                        </div>
                        <button type="button" onClick={() => handleDeletePluggyAlias(item.account_id)} className="text-red-400 hover:text-red-200 font-semibold">
                          Remover
                        </button>
                      </div>
                    </div>
                  )) : (
                    <p className="text-xs text-slate-400">Nenhum apelido cadastrado.</p>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Contas conectadas</h3>
              {pluggyAccounts.length > 0 ? (
                <div className="space-y-3">
                  {pluggyAccounts.map(account => (
                    <div key={account.id} className="rounded border border-slate-700 bg-slate-900/70 p-4 text-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-semibold text-slate-100">{account.alias || account.name || account.marketingName || account.number || account.id}</p>
                          {account.alias && <p className="text-xs text-slate-400">{account.name || account.marketingName || account.number || account.id}</p>}
                          <p className="text-xs text-slate-400">{account.type || '-'} • {account.subtype || account.currencyCode || 'BRL'}</p>
                          <p className="mt-1 break-all text-xs text-slate-500">Conta: {account.id}</p>
                          {account.itemId && <p className="mt-1 text-xs text-slate-500">Item: {account.itemId}</p>}
                          {account.balance !== undefined && <p className="mt-1 text-xs text-slate-300">Saldo: R$ {Number(account.balance).toFixed(2)}</p>}
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <button
                            type="button"
                            onClick={() => setPluggyAliasInput({ account_id: account.id, alias: account.alias || account.name || account.marketingName || '' })}
                            className="text-xs font-semibold text-blue-400 hover:text-blue-200"
                          >
                            Renomear
                          </button>
                          <button type="button" onClick={() => handlePluggySync([account.id], account.itemId)} className="text-xs font-semibold text-emerald-400 hover:text-emerald-200">
                            Sincronizar
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-sm">Nenhuma conta carregada.</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'budgets' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-semibold">Orçamentos - {selectedMonth}</h3>
              <input
                type="month"
                value={selectedMonth}
                onChange={e => setSelectedMonth(e.target.value)}
                className="bg-slate-800 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
              />
            </div>
            <form onSubmit={handleAddBudget} className="grid gap-3 rounded-lg border border-slate-700 bg-slate-800/50 p-4 md:grid-cols-[1fr_1fr_auto]">
              <select
                value={newBudget.category}
                onChange={e => setNewBudget({ ...newBudget, category: e.target.value })}
                className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
              >
                {(categories.length ? categories : ['Outros']).map(category => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
              <input
                type="number"
                step="0.01"
                value={newBudget.limit_amount}
                onChange={e => setNewBudget({ ...newBudget, limit_amount: e.target.value })}
                placeholder="Limite mensal (R$)"
                required
                className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
              />
              <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2 rounded transition text-xs">
                SALVAR LIMITE
              </button>
            </form>
            {budgets.length > 0 ? (
              <div className="grid gap-4">
                {budgets.map(budget => (
                  <div key={budget.id} className="bg-slate-800/50 border border-slate-700 p-4 rounded-lg">
                    <div className="flex justify-between mb-2">
                      <span className="font-semibold">{budget.category}</span>
                      <span className={`text-sm font-bold ${budget.percentage > 100 ? 'text-red-400' : 'text-green-400'}`}>
                        {budget.percentage.toFixed(0)}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-2">
                      <div className={`h-2 rounded-full transition ${budget.percentage > 100 ? 'bg-red-500' : 'bg-green-500'}`} style={{ width: `${Math.min(budget.percentage, 100)}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-slate-400 mt-2">
                      <span>Gasto: R$ {budget.spent.toFixed(2)}</span>
                      <span>Limite: R$ {budget.limit_amount.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-400 text-center py-8">Nenhum orçamento configurado</p>
            )}
          </div>
        )}

        {activeTab === 'goals' && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1">
              <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg sticky top-24">
                <h4 className="text-lg font-semibold mb-4">Nova Meta</h4>
                <form onSubmit={handleAddGoal} className="space-y-4">
                  <input
                    type="text"
                    placeholder="Nome da meta"
                    value={newGoal.name}
                    onChange={e => setNewGoal({ ...newGoal, name: e.target.value })}
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="Valor alvo"
                    value={newGoal.target_amount}
                    onChange={e => setNewGoal({ ...newGoal, target_amount: e.target.value })}
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="date"
                    value={newGoal.deadline}
                    onChange={e => setNewGoal({ ...newGoal, deadline: e.target.value })}
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded transition">
                    CRIAR
                  </button>
                </form>
              </div>
            </div>

            <div className="lg:col-span-3">
              {goals.length > 0 ? (
                <div className="grid gap-4">
                  {goals.map(goal => (
                    <div key={goal.id} className="bg-slate-800/50 border border-slate-700 p-4 rounded-lg">
                      <div className="flex justify-between mb-2">
                        <span className="font-semibold">{goal.name}</span>
                        <span className="text-xs font-bold text-blue-400">{goal.progress.toFixed(0)}%</span>
                      </div>
                      <div className="w-full bg-slate-700 rounded-full h-2">
                        <div className="h-2 bg-blue-500 rounded-full" style={{ width: `${Math.min(goal.progress, 100)}%` }} />
                      </div>
                      <div className="flex justify-between text-xs text-slate-400 mt-2">
                        <span>R$ {goal.current_amount.toFixed(2)} de R$ {goal.target_amount.toFixed(2)}</span>
                        <span>Prazo: {goal.deadline}</span>
                      </div>
                      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                        <input
                          type="number"
                          step="0.01"
                          value={goalContributions[goal.id] || ''}
                          onChange={e => setGoalContributions(prev => ({ ...prev, [goal.id]: e.target.value }))}
                          placeholder="Adicionar valor guardado"
                          className="flex-1 bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                        />
                        <button
                          type="button"
                          onClick={() => handleAddGoalContribution(goal.id)}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2 rounded transition text-xs"
                        >
                          ADICIONAR
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-center py-8">Nenhuma meta criada</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'purchase-validator' && (
          <div className="space-y-6">
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                <div>
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <ShoppingBag size={18} className="text-blue-400" /> Calendario de Compra
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">Cores calculadas pelo saldo projetado, fechamento do cartao e quantidade de parcelas.</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <input
                    type="month"
                    value={purchaseCalendarInput.month}
                    onChange={e => setPurchaseCalendarInput({ ...purchaseCalendarInput, month: e.target.value })}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={purchaseCalendarInput.amount}
                    onChange={e => setPurchaseCalendarInput({ ...purchaseCalendarInput, amount: e.target.value })}
                    placeholder="Valor da compra"
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="number"
                    min={1}
                    value={purchaseCalendarInput.installments}
                    onChange={e => setPurchaseCalendarInput({ ...purchaseCalendarInput, installments: e.target.value })}
                    placeholder="Parcelas"
                    disabled={!selectedPurchaseCard}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400 disabled:opacity-50"
                  />
                  <select
                    value={purchaseCalendarInput.payment_method}
                    onChange={e => setPurchaseCalendarInput({ ...purchaseCalendarInput, payment_method: e.target.value })}
                    className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  >
                    <option value="cash">Pix / debito / dinheiro</option>
                    {cards.map(card => (
                      <option key={card.id} value={card.id.toString()}>{card.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <div className="rounded border border-emerald-500/30 bg-emerald-950/20 p-3">
                  <p className="text-xs uppercase font-semibold text-emerald-300">Melhor dia</p>
                  <p className="text-2xl font-bold text-emerald-300 mt-1">{bestPurchaseDay?.day ?? '-'}</p>
                  <p className="text-xs text-slate-300 mt-1">Pior saldo: R$ {(bestPurchaseDay?.worstBalance ?? 0).toFixed(2)}</p>
                </div>
                <div className="rounded border border-red-500/30 bg-red-950/20 p-3">
                  <p className="text-xs uppercase font-semibold text-red-300">Pior dia</p>
                  <p className="text-2xl font-bold text-red-300 mt-1">{worstPurchaseDay?.day ?? '-'}</p>
                  <p className="text-xs text-slate-300 mt-1">Pior saldo: R$ {(worstPurchaseDay?.worstBalance ?? 0).toFixed(2)}</p>
                </div>
                <div className="rounded border border-slate-700 bg-slate-900/70 p-3">
                  <p className="text-xs uppercase font-semibold text-slate-300">Referencia</p>
                  <p className="text-sm font-semibold text-slate-100 mt-1">{selectedPurchaseCard ? `${selectedPurchaseCard.name}: fecha ${selectedPurchaseCard.closing_day}, vence ${selectedPurchaseCard.due_day}` : 'Pagamento imediato'}</p>
                  <p className="text-xs text-slate-400 mt-1">Parcela usada: R$ {(selectedPurchaseCard ? purchaseAmount / purchaseInstallments : purchaseAmount).toFixed(2)}</p>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-3 text-xs">
                <span className="inline-flex items-center gap-2 text-slate-300"><span className="h-3 w-3 rounded bg-emerald-500"></span>Bom</span>
                <span className="inline-flex items-center gap-2 text-slate-300"><span className="h-3 w-3 rounded bg-yellow-500"></span>Apertado</span>
                <span className="inline-flex items-center gap-2 text-slate-300"><span className="h-3 w-3 rounded bg-red-500"></span>Evitar</span>
              </div>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold capitalize">{monthLabel(purchaseCalendarInput.month)}</h3>
                <span className="text-xs text-slate-400">{selectedPurchaseCard ? `${purchaseInstallments}x no cartao` : 'a vista'}</span>
              </div>
              <div className="grid grid-cols-7 gap-2 text-center text-xs text-slate-400 mb-2">
                {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab'].map(day => <span key={day}>{day}</span>)}
              </div>
              <div className="grid grid-cols-7 gap-2">
                {Array.from({ length: new Date(`${purchaseCalendarInput.month}-01T00:00:00`).getDay() }, (_, index) => (
                  <div key={`empty-${index}`} className="aspect-square rounded border border-transparent" />
                ))}
                {purchaseCalendarDays.map(item => (
                  <div
                    key={item.day}
                    className={`group relative aspect-square rounded border p-2 text-left transition ${
                      item.status === 'good'
                        ? 'border-emerald-500/30 bg-emerald-950/30 hover:bg-emerald-900/40'
                        : item.status === 'warn'
                          ? 'border-yellow-500/30 bg-yellow-950/30 hover:bg-yellow-900/40'
                          : 'border-red-500/30 bg-red-950/30 hover:bg-red-900/40'
                    }`}
                  >
                    <div className="flex h-full flex-col justify-between">
                      <span className="text-sm font-bold text-slate-100">{item.day}</span>
                      <span className="text-[10px] text-slate-300">R$ {item.worstBalance.toFixed(0)}</span>
                    </div>
                    <div className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-56 -translate-x-1/2 rounded border border-slate-600 bg-slate-950 p-3 text-left text-xs shadow-xl group-hover:block">
                      <p className="font-semibold text-slate-100">Compra dia {item.day}</p>
                      <p className="mt-1 text-slate-300">1a cobranca: {item.firstDueDate}</p>
                      <p className="text-slate-300">Parcela: R$ {item.installmentAmount.toFixed(2)}</p>
                      <p className="text-slate-300">Pior saldo: R$ {item.worstBalance.toFixed(2)}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'purchase-validator' && false && (
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Simular compra</h3>
              <form onSubmit={handleValidatePurchase} className="space-y-4">
                <input
                  type="text"
                  value={newSimulationInput.title}
                  onChange={e => setNewSimulationInput({ ...newSimulationInput, title: e.target.value })}
                  placeholder="Nome da compra"
                  required
                  className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                />
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="number"
                    step="0.01"
                    value={newSimulationInput.amount}
                    onChange={e => setNewSimulationInput({ ...newSimulationInput, amount: e.target.value })}
                    placeholder="Valor total"
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <input
                    type="number"
                    min={1}
                    value={newSimulationInput.installments}
                    onChange={e => setNewSimulationInput({ ...newSimulationInput, installments: e.target.value })}
                    placeholder="Parcelas"
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="date"
                    value={newSimulationInput.start_date}
                    onChange={e => setNewSimulationInput({ ...newSimulationInput, start_date: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                  <select
                    value={newSimulationInput.category}
                    onChange={e => setNewSimulationInput({ ...newSimulationInput, category: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  >
                    {(categories.length ? categories : ['Compras']).map(category => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                </div>
                <button type="submit" disabled={simulating} className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-bold py-2 rounded transition text-xs">
                  {simulating ? 'SIMULANDO...' : 'SIMULAR'}
                </button>
              </form>

              {simulationResult && (
                <div className={`mt-6 rounded-lg border p-4 text-sm ${simulationResult.decision === 'GREEN' ? 'border-emerald-500/40 bg-emerald-950/20' : simulationResult.decision === 'YELLOW' ? 'border-yellow-500/40 bg-yellow-950/20' : 'border-red-500/40 bg-red-950/20'}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-bold">{simulationResult.decision}</span>
                    <span>Parcela: R$ {simulationResult.installment_amount?.toFixed(2)}</span>
                  </div>
                  <p className="mt-2 text-slate-300">{simulationResult.reason}</p>
                  <button type="button" onClick={handleSaveSimulation} className="mt-4 w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded transition text-xs">
                    SALVAR SIMULAÇÃO
                  </button>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Simulações salvas</h3>
              {purchaseSimulations.length > 0 ? (
                <div className="space-y-3">
                  {purchaseSimulations.map(sim => (
                    <div key={sim.id} className="rounded border border-slate-700 bg-slate-900/70 p-4 text-sm">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-semibold text-slate-100">{sim.title}</p>
                          <p className="text-xs text-slate-400">R$ {Number(sim.amount).toFixed(2)} em {sim.installments}x • {sim.start_date}</p>
                        </div>
                        <div className="flex gap-2">
                          <button type="button" onClick={() => handleConfirmSimulation(sim.id)} className="text-xs font-semibold text-emerald-400 hover:text-emerald-200">
                            Confirmar
                          </button>
                          <button type="button" onClick={() => handleDeleteSimulation(sim.id)} className="text-xs font-semibold text-red-400 hover:text-red-200">
                            Excluir
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-400 text-sm">Nenhuma simulação salva.</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'provisions' && (
          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
              <h3 className="text-lg font-semibold mb-4">Renda atual</h3>
              <form onSubmit={handleSetSalaryPlan} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Data de referência</label>
                  <input
                    type="date"
                    value={salaryInput.effective_date}
                    onChange={e => setSalaryInput({ ...salaryInput, effective_date: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Renda mensal bruta (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={salaryInput.gross_amount}
                    onChange={e => setSalaryInput({ ...salaryInput, gross_amount: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Renda líquida (R$)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={salaryInput.net_amount}
                    onChange={e => setSalaryInput({ ...salaryInput, net_amount: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded transition">
                  Salvar renda atual
                </button>
              </form>

              {salaryPlan && salaryPlan.gross_amount > 0 && (
                <div className="mt-6 rounded-lg border border-slate-700 bg-slate-900/80 p-4 text-sm text-slate-300">
                  <p><span className="font-semibold text-slate-100">Renda atual:</span> R$ {salaryPlan.gross_amount.toFixed(2)}</p>
                  <p className="mt-1"><span className="font-semibold text-slate-100">Líquido:</span> R$ {salaryPlan.net_amount?.toFixed(2) ?? '0.00'}</p>
                  <p className="mt-1"><span className="font-semibold text-slate-100">Referência:</span> {salaryPlan.effective_date || '-'}</p>
                </div>
              )}
            </div>

            <div className="bg-slate-800/50 border border-slate-700 p-6 rounded-lg">
              <h3 className="text-lg font-semibold mb-4">Gastos fixos</h3>
              <form onSubmit={handleAddProvision} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">Nome do gasto</label>
                  <input
                    type="text"
                    value={newProvision.title}
                    onChange={e => setNewProvision({ ...newProvision, title: e.target.value })}
                    placeholder="Ex: Assinatura, Aluguel"
                    required
                    className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Valor (R$)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={newProvision.amount}
                      onChange={e => setNewProvision({ ...newProvision, amount: e.target.value })}
                      required
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Categoria</label>
                    <select
                      value={newProvision.category}
                      onChange={e => setNewProvision({ ...newProvision, category: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      {(categories.length ? categories : ['Alimentação', 'Transporte', 'Moradia', 'Utilities', 'Saúde', 'Educação', 'Lazer', 'Compras', 'Renda', 'Outros']).map(category => (
                        <option key={category} value={category}>{category}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Método</label>
                    <select
                      value={newProvision.payment_method}
                      onChange={e => setNewProvision({ ...newProvision, payment_method: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      <option value="Pix">Pix</option>
                      <option value="Cartão">Cartão</option>
                      <option value="Débito">Débito</option>
                      <option value="Boleto">Boleto</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Frequência</label>
                    <select
                      value={newProvision.frequency}
                      onChange={e => setNewProvision({ ...newProvision, frequency: e.target.value as 'once' | 'weekly' | 'monthly' | 'yearly' })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    >
                      <option value="monthly">Mensal</option>
                      <option value="weekly">Semanal</option>
                      <option value="yearly">Anual</option>
                      <option value="once">Única</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Início</label>
                    <input
                      type="date"
                      value={newProvision.start_date}
                      onChange={e => setNewProvision({ ...newProvision, start_date: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">Término (opcional)</label>
                    <input
                      type="date"
                      value={newProvision.end_date}
                      onChange={e => setNewProvision({ ...newProvision, end_date: e.target.value })}
                      className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                    />
                  </div>
                </div>
                <button type="submit" className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded transition">
                  Salvar gasto fixo
                </button>
              </form>

              <div className="mt-8">
                <h4 className="text-sm font-semibold mb-3">Gastos fixos ativos</h4>
                {provisions.filter(item => item.is_income === 0 && item.status === 'active').length > 0 ? (
                  <div className="space-y-3">
                    {provisions.filter(item => item.is_income === 0 && item.status === 'active').map(prov => (
                      <div key={prov.id} className="rounded-lg border border-slate-700 bg-slate-900/80 p-4 text-sm text-slate-300">
                        <div className="flex justify-between items-start gap-4">
                          <div>
                            <p className="font-semibold text-slate-100">{prov.title}</p>
                            <p className="text-slate-400 text-xs">{prov.category} • {prov.frequency} • {prov.payment_method || 'Pix'}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleDeleteProvision(prov.id)}
                            className="text-xs text-red-400 hover:text-red-200"
                          >Excluir</button>
                        </div>
                        <div className="mt-3 flex justify-between text-slate-300 text-sm">
                          <span>R$ {prov.amount.toFixed(2)}</span>
                          <span>{prov.start_date}{prov.end_date ? ` → ${prov.end_date}` : ''}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400">Nenhum gasto fixo cadastrado.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'categories' && (
          <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Categorias</h3>
              <form onSubmit={handleAddCategory} className="space-y-3">
                <input
                  type="text"
                  value={newCategory.name}
                  onChange={e => setNewCategory({ ...newCategory, name: e.target.value })}
                  placeholder="Nova categoria"
                  required
                  className="w-full bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                />
                <div className="grid grid-cols-[auto_1fr] gap-3">
                  <input
                    type="color"
                    value={newCategory.color}
                    onChange={e => setNewCategory({ ...newCategory, color: e.target.value })}
                    className="h-9 w-12 rounded border border-slate-600 bg-slate-900"
                  />
                  <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded transition text-xs">
                    CRIAR CATEGORIA
                  </button>
                </div>
              </form>
              <div className="mt-6 grid gap-2">
                {(categories.length ? categories : ['Outros']).map(category => (
                  <div key={category} className="rounded border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-200">
                    {category}
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
              <h3 className="text-lg font-semibold mb-4">Regras automáticas</h3>
              <form onSubmit={handleAddCategoryRule} className="grid gap-3 md:grid-cols-[1fr_0.8fr_0.7fr_auto]">
                <input
                  type="text"
                  value={newCategoryRule.pattern}
                  onChange={e => setNewCategoryRule({ ...newCategoryRule, pattern: e.target.value })}
                  placeholder="Texto na descrição"
                  required
                  className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                />
                <select
                  value={newCategoryRule.category}
                  onChange={e => setNewCategoryRule({ ...newCategoryRule, category: e.target.value })}
                  className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                >
                  {(categories.length ? categories : ['Outros']).map(category => (
                    <option key={category} value={category}>{category}</option>
                  ))}
                </select>
                <select
                  value={newCategoryRule.rule_type}
                  onChange={e => setNewCategoryRule({ ...newCategoryRule, rule_type: e.target.value })}
                  className="bg-slate-900 border border-slate-600 p-2 rounded text-xs focus:outline-none focus:border-blue-400"
                >
                  <option value="contains">Contém</option>
                  <option value="regex">Regex</option>
                </select>
                <button type="submit" className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4 py-2 rounded transition text-xs">
                  SALVAR
                </button>
              </form>
              <div className="mt-6 space-y-2">
                {categoryRules.length > 0 ? categoryRules.map(rule => (
                  <div key={rule.id} className="flex items-center justify-between gap-3 rounded border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs">
                    <div>
                      <span className="font-semibold text-slate-100">{rule.pattern}</span>
                      <span className="text-slate-400"> → {rule.category}</span>
                    </div>
                    <button type="button" onClick={() => handleDeleteCategoryRule(rule.id)} className="text-red-400 hover:text-red-200 font-semibold">
                      Excluir
                    </button>
                  </div>
                )) : (
                  <p className="text-slate-400 text-sm">Nenhuma regra criada.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'categories' && false && (
          <div className="text-center py-12">
            <p className="text-slate-400">Seção em desenvolvimento</p>
          </div>
        )}
      </main>
    </div>
  );
}
