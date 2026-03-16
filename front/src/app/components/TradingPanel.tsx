import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTrading } from '../context/TradingContext';
import { Play, Pause, X, Plus, Trash2, ChevronDown, Wallet, TrendingUp, DollarSign, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tooltip from '@radix-ui/react-tooltip';
import { createTrading, deleteTradingInstance, fetchAccounts, fetchPositions, fetchTrades, startTradingInstance, stopTradingInstance, updateTradingInstance } from '../api/client';
import { mapBackendAccountToTradingAccount } from '../api/trading-mappers';

// ─── Types ─────────────────────────────────────────────────────────────────
interface PMBuilderAccount {
  id: string;
  name: string;
  totalFunds: number;
  positionFunds: number;
  availableFunds: number;
}

interface TradingAccount {
  id: string;
  mode: 'real' | 'simulation';
  strategyKey: string;
  strategyName: string;
  strategyConfig: Record<string, number>;
  strategyParams: { retracement: number };
  initialBalance: number;
  sports: string[];
  totalAssets: number;
  availableCash: number;
  marketValue: number;
  todayProfit: number;
  totalProfit: number;
  winRate: number;
  isRunning: boolean;
  positionCount: number;
  pmAccountId?: string;
  // Risk params
  maxPositions: number;
  maxFundUsageRate: number;
  maxSingleAmount: number;
}

interface Position {
  id: string;
  orderId: string;
  matchName: string;
  teamName: string;
  amount: number;
  shares: number;
  entryPrice: number;
  currentPrice: number;
  profit: number;
  profitPercent: number;
  timestamp: number;
}

interface TradeRecord {
  id: number;
  orderId: string;
  strategy: string;
  side: string;
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  amount: number;
  profit: number;
  profitRate: number;
  timestamp: number;
}

const MOCK_TRADE_RECORDS: TradeRecord[] = [
  { id:  1, orderId: 'ORD-20260311-001', strategy: 'R001', side: 'Man Utd',     entryPrice: 0.625, exitPrice: 0.650, quantity: 500, amount: 312.50, profit:  47.30, profitRate:  15.14, timestamp: Date.now() - 86400000*2 },
  { id:  2, orderId: 'ORD-20260311-002', strategy: 'S001', side: 'Arsenal',     entryPrice: 0.580, exitPrice: 0.570, quantity: 200, amount: 145.00, profit:  -8.70, profitRate:  -6.00, timestamp: Date.now() - 86400000*2 + 3600000 },
  { id:  3, orderId: 'ORD-20260311-003', strategy: 'S002', side: 'Real Madrid', entryPrice: 0.650, exitPrice: 0.700, quantity: 800, amount: 520.00, profit:  83.20, profitRate:  16.00, timestamp: Date.now() - 86400000*2 + 7200000 },
  { id:  4, orderId: 'ORD-20260311-004', strategy: 'R001', side: 'Celtics',     entryPrice: 0.420, exitPrice: 0.455, quantity: 600, amount: 252.00, profit:  21.00, profitRate:   8.33, timestamp: Date.now() - 86400000*2 + 10800000 },
  { id:  5, orderId: 'ORD-20260311-005', strategy: 'S001', side: 'Barcelona',   entryPrice: 0.510, exitPrice: 0.490, quantity: 400, amount: 204.00, profit: -20.40, profitRate:  -8.00, timestamp: Date.now() - 86400000*1 },
  { id:  6, orderId: 'ORD-20260312-001', strategy: 'R001', side: 'Lakers',      entryPrice: 0.480, exitPrice: 0.510, quantity: 350, amount: 168.00, profit:  17.85, profitRate:  10.63, timestamp: Date.now() - 86400000*1 + 3600000 },
  { id:  7, orderId: 'ORD-20260312-002', strategy: 'S002', side: 'Warriors',    entryPrice: 0.390, exitPrice: 0.375, quantity: 700, amount: 273.00, profit: -27.30, profitRate:  -8.33, timestamp: Date.now() - 86400000*1 + 7200000 },
  { id:  8, orderId: 'ORD-20260312-003', strategy: 'S001', side: 'PSG',         entryPrice: 0.710, exitPrice: 0.740, quantity: 450, amount: 319.50, profit:  43.65, profitRate:  13.66, timestamp: Date.now() - 86400000*1 + 10800000 },
  { id:  9, orderId: 'ORD-20260312-004', strategy: 'R001', side: 'Bayern',      entryPrice: 0.550, exitPrice: 0.565, quantity: 600, amount: 330.00, profit:  16.50, profitRate:   5.00, timestamp: Date.now() - 43200000 },
  { id: 10, orderId: 'ORD-20260312-005', strategy: 'S002', side: 'Man City',    entryPrice: 0.620, exitPrice: 0.600, quantity: 300, amount: 186.00, profit: -18.60, profitRate:  -5.00, timestamp: Date.now() - 36000000 },
  { id: 11, orderId: 'ORD-20260313-001', strategy: 'S001', side: 'Knicks',      entryPrice: 0.450, exitPrice: 0.488, quantity: 800, amount: 360.00, profit:  57.60, profitRate:  16.00, timestamp: Date.now() - 21600000 },
  { id: 12, orderId: 'ORD-20260313-002', strategy: 'R001', side: 'Liverpool',   entryPrice: 0.680, exitPrice: 0.695, quantity: 250, amount: 170.00, profit:  10.50, profitRate:   6.18, timestamp: Date.now() - 14400000 },
  { id: 13, orderId: 'ORD-20260313-003', strategy: 'S002', side: 'Suns',        entryPrice: 0.530, exitPrice: 0.515, quantity: 500, amount: 265.00, profit: -19.87, profitRate:  -7.50, timestamp: Date.now() - 10800000 },
  { id: 14, orderId: 'ORD-20260313-004', strategy: 'R001', side: 'Juventus',    entryPrice: 0.420, exitPrice: 0.458, quantity: 900, amount: 378.00, profit:  68.04, profitRate:  18.00, timestamp: Date.now() - 7200000 },
  { id: 15, orderId: 'ORD-20260313-005', strategy: 'S001', side: 'Heat',        entryPrice: 0.600, exitPrice: 0.590, quantity: 300, amount: 180.00, profit:  -9.00, profitRate:  -3.33, timestamp: Date.now() - 3600000 },
];

// ─── Mock PM Builder Accounts ──────────────────────────────────────────────
const PM_BUILDER_ACCOUNTS: PMBuilderAccount[] = [
  { id: 'PM001', name: 'Builder Account Alpha',   totalFunds: 500000,  positionFunds: 375000, availableFunds: 125000 },
  { id: 'PM002', name: 'Builder Account Beta',    totalFunds: 200000,  positionFunds: 112500, availableFunds: 87500  },
  { id: 'PM003', name: 'Crypto Builder Pro',      totalFunds: 1000000, positionFunds: 660000, availableFunds: 340000 },
  { id: 'PM004', name: 'Sports Arb Builder',      totalFunds: 80000,   positionFunds: 32000,  availableFunds: 48000  },
];

const fmt = (n: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtK = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(1)}K` : n.toFixed(0);

const SPORT_OPTIONS = ['足球', '篮球'];

const STRATEGY_OPTIONS = [
  { value: 'prematch_gap_retracement', label: '开赛前价差回撤' },
  { value: 'live_first_goal_retracement', label: '足球首球回撤' },
];

// ─── Shared Risk Params Section ────────────────────────────────────────────
interface RiskParamsProps {
  maxPositions: string;
  maxFundUsageRate: string;
  maxSingleAmount: string;
  onChange: (field: string, value: string) => void;
}
const RiskParamsSection = ({ maxPositions, maxFundUsageRate, maxSingleAmount, onChange }: RiskParamsProps) => (
  <div className="space-y-3">
    <div className="flex items-center gap-2 pt-1">
      <div className="flex-1 h-px bg-gray-200" />
      <span className="text-[10px] text-gray-400 uppercase tracking-wider whitespace-nowrap">风险参数</span>
      <div className="flex-1 h-px bg-gray-200" />
    </div>
    <div className="grid grid-cols-3 gap-3">
      <div>
        <label className="text-[10px] text-gray-500 block mb-1.5">最大持仓数</label>
        <input
          type="number"
          min="0"
          value={maxPositions}
          onChange={e => onChange('maxPositions', e.target.value)}
          className="w-full border border-gray-200 bg-gray-50 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
          placeholder="0"
        />
        <div className="text-[9px] text-gray-400 mt-1">0 = 不限</div>
      </div>
      <div>
        <label className="text-[10px] text-gray-500 block mb-1.5">最大使用率 %</label>
        <input
          type="number"
          min="0"
          max="100"
          value={maxFundUsageRate}
          onChange={e => onChange('maxFundUsageRate', e.target.value)}
          className="w-full border border-gray-200 bg-gray-50 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
          placeholder="0"
        />
        <div className="text-[9px] text-gray-400 mt-1">0 = 不限</div>
      </div>
      <div>
        <label className="text-[10px] text-gray-500 block mb-1.5">单笔上限 $</label>
        <input
          type="number"
          min="0"
          value={maxSingleAmount}
          onChange={e => onChange('maxSingleAmount', e.target.value)}
          className="w-full border border-gray-200 bg-gray-50 rounded-md px-2.5 py-1.5 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
          placeholder="0"
        />
        <div className="text-[9px] text-gray-400 mt-1">0 = 不限</div>
      </div>
    </div>
  </div>
);

// ─── Component ─────────────────────────────────────────────────────────────
export const TradingPanel = () => {
  const { isSimulation, setSimulationMode } = useTrading();

  const [accounts, setAccounts] = useState<TradingAccount[]>([]);
  const [positionRows, setPositionRows] = useState<any[]>([]);
  const [tradeRows, setTradeRows] = useState<any[]>([]);

  const loadTradingData = useCallback(async () => {
    const [accountsData, positionsData, tradesData] = await Promise.all([
      fetchAccounts(),
      fetchPositions(),
      fetchTrades(),
    ]);
    setAccounts(accountsData.map((row) => mapBackendAccountToTradingAccount(row)));
    setPositionRows(positionsData);
    setTradeRows(tradesData);
  }, []);

  useEffect(() => {
    let disposed = false;
    const load = async () => {
      try {
        await loadTradingData();
        if (disposed) return;
      } catch {
        if (!disposed) {
          setAccounts([]);
          setPositionRows([]);
          setTradeRows([]);
        }
      }
    };
    void load();
    const timer = setInterval(() => {
      void load();
    }, 5000);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [loadTradingData]);

  // ── Dialog visibility ──
  const [showAddDialog, setShowAddDialog]       = useState(false);
  const [showEditDialog, setShowEditDialog]     = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showStopDialog, setShowStopDialog]     = useState(false);
  const [showPositions, setShowPositions]       = useState(false);
  const [showTradeLogs, setShowTradeLogs]       = useState(false);
  const [currentAccountId, setCurrentAccountId]   = useState<string | null>(null);
  const [hoveredAccountId, setHoveredAccountId]   = useState<string | null>(null);
  // Trade records search & pagination
  const [tradeSearch, setTradeSearch] = useState('');
  const [tradePage, setTradePage]     = useState(1);
  const TRADE_PAGE_SIZE = 8;

  // ── Add form ──
  const defaultAddForm = {
    strategy: STRATEGY_OPTIONS[0].value,
    retracement: '2',
    initialBalance: '10000',
    sports: ['足球', '篮球'] as string[],
    pmAccountId: '',
    maxPositions: '0',
    maxFundUsageRate: '0',
    maxSingleAmount: '0',
  };
  const [addForm, setAddForm] = useState(defaultAddForm);

  // ── Edit form ──
  const [editForm, setEditForm] = useState({
    retracement: '2',
    maxPositions: '0',
    maxFundUsageRate: '0',
    maxSingleAmount: '0',
  });

  const viewPositions: Position[] = useMemo(
    () =>
      positionRows.map((pos: any) => ({
        id: pos.id,
        orderId: pos.id,
        matchName: pos.match_name,
        teamName: pos.match_name?.split(' vs ')[0] || '',
        amount: Number(pos.amount || 0),
        shares: Number(pos.amount || 0),
        entryPrice: Number(pos.entry_price || 0),
        currentPrice: Number(pos.current_price || 0),
        profit: Number(pos.pnl || 0),
        profitPercent: Number(pos.amount || 0) > 0 ? (Number(pos.pnl || 0) / Number(pos.amount || 1)) * 100 : 0,
        timestamp: Date.now(),
      })),
    [positionRows]
  );

  const viewTrades: TradeRecord[] = useMemo(
    () =>
      tradeRows.map((rec: any, index: number) => ({
        id: index + 1,
        orderId: rec.id ?? `T${index + 1}`,
        strategy: 'S001',
        side: rec.action ?? '',
        entryPrice: Number(rec.price || 0),
        exitPrice: Number(rec.price || 0),
        quantity: Number(rec.amount || 0),
        amount: Number(rec.amount || 0),
        profit: Number(rec.profit || 0),
        profitRate: Number(rec.amount || 0) > 0 ? (Number(rec.profit || 0) / Number(rec.amount || 1)) * 100 : 0,
        timestamp: Date.now(),
      })),
    [tradeRows]
  );

  // ── Handlers ──
  const handleAddAccount = async () => {
    if (!isSimulation) {
      return;
    }
    const retracement = (parseFloat(addForm.retracement) || 0) / 100;
    const initialBalance = parseFloat(addForm.initialBalance) || 10000;
    const affectSports = addForm.sports
      .map((sport) => (sport === '足球' ? 'football' : sport === '篮球' ? 'basketball' : ''))
      .filter((sport): sport is string => sport.length > 0);
    const strategyParams: Record<string, number> = {
      initial_balance: initialBalance,
      max_drawdown: retracement,
      trade_amount: Math.max(1, parseFloat(addForm.maxSingleAmount) || 100),
    };
    if (addForm.strategy === 'prematch_gap_retracement') {
      strategyParams.entry_spread_threshold = 0.25;
    }
    await createTrading({
      strategy_name: addForm.strategy,
      strategy_params: strategyParams,
      affect_sports: affectSports,
      mode: 'simulation',
    }).then((created) => startTradingInstance(created.trading_id));
    await loadTradingData();
    setShowAddDialog(false);
  };

  const handleUpdateAccount = async () => {
    if (!currentAccountId || !currentAccount) {
      return;
    }
    const nextStrategyParams: Record<string, number> = {
      ...currentAccount.strategyConfig,
    };
    const retracement = (parseFloat(editForm.retracement) || currentAccount.strategyParams.retracement) / 100;
    const maxSingleAmount =
      Math.max(1, parseFloat(editForm.maxSingleAmount) || currentAccount.maxSingleAmount || Number(currentAccount.strategyConfig.trade_amount) || 100);
    if (currentAccount.strategyKey === 'retracement') {
      nextStrategyParams.retracement = retracement;
    } else {
      nextStrategyParams.max_drawdown = retracement;
    }
    nextStrategyParams.trade_amount = maxSingleAmount;
    await updateTradingInstance(currentAccountId, {
      strategy_params: nextStrategyParams,
    });
    await loadTradingData();
    setShowEditDialog(false);
    setCurrentAccountId(null);
  };

  const handleDeleteAccount = async () => {
    if (!currentAccountId) return;
    await deleteTradingInstance(currentAccountId);
    await loadTradingData();
    setShowDeleteDialog(false);
    setCurrentAccountId(null);
  };

  const handleToggleAccount = async (id: string) => {
    await startTradingInstance(id);
    await loadTradingData();
  };

  const handleOpenAddDialog = () => {
    if (!isSimulation) {
      return;
    }
    setAddForm(defaultAddForm);
    setShowAddDialog(true);
  };

  const handleOpenEditDialog = (account: TradingAccount) => {
    setCurrentAccountId(account.id);
    setEditForm({
      retracement: account.strategyParams.retracement.toString(),
      maxPositions: account.maxPositions.toString(),
      maxFundUsageRate: account.maxFundUsageRate.toString(),
      maxSingleAmount: account.maxSingleAmount.toString(),
    });
    setShowEditDialog(true);
  };

  const handleConfirmStop = async () => {
    if (currentAccountId) {
      await stopTradingInstance(currentAccountId);
      await loadTradingData();
    }
    setShowStopDialog(false);
    setCurrentAccountId(null);
  };

  const filteredAccounts = accounts.filter(a =>
    isSimulation ? a.mode === 'simulation' : a.mode === 'real'
  );

  const getProfitColor = (profit: number) =>
    profit >= 0 ? 'text-red-500' : 'text-green-600';

  const toggleSportAdd = (sport: string) => {
    setAddForm(prev => ({
      ...prev,
      sports: prev.sports.includes(sport)
        ? prev.sports.filter(s => s !== sport)
        : [...prev.sports, sport],
    }));
  };

  const selectedPMAccount = PM_BUILDER_ACCOUNTS.find(p => p.id === addForm.pmAccountId);
  const currentAccount    = accounts.find(a => a.id === currentAccountId);

  return (
    <Tooltip.Provider>
      <div className="flex flex-col h-full bg-gray-50 text-sm overflow-hidden">

        {/* ── Header ───────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between p-3 border-b border-l border-gray-200 bg-white">
          <h2 className="text-gray-900 font-bold text-base">交易</h2>
          <div className="flex items-center gap-1">
            <div className="flex bg-gray-100 rounded-md p-0.5">
              <button
                onClick={() => setSimulationMode(false)}
                className={clsx(
                  'px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer',
                  !isSimulation ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                )}
              >真实</button>
              <button
                onClick={() => setSimulationMode(true)}
                className={clsx(
                  'px-2.5 py-1 rounded text-xs font-medium transition-all cursor-pointer',
                  isSimulation ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                )}
              >模拟</button>
            </div>
            <button
              onClick={handleOpenAddDialog}
              disabled={!isSimulation}
              className={clsx(
                "p-1.5 rounded-md transition-colors text-gray-500",
                isSimulation ? "cursor-pointer hover:bg-gray-100 hover:text-[#10b981]" : "cursor-not-allowed opacity-40"
              )}
              title={isSimulation ? "添加交易账户" : "真实交易暂未开放"}
            >
              <Plus size={16} />
            </button>
          </div>
        </div>

        {/* ── Account Cards ─────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto custom-scrollbar pl-2 pr-3 pt-2 pb-2 space-y-2">
          <div className="space-y-2">
            {filteredAccounts.map(account => (
              <div key={account.id} className="bg-white border border-gray-200 rounded-md p-3">

                {/* Card header */}
                <div className="flex justify-between items-center mb-3">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <div
                      className="relative group/delete"
                      onMouseEnter={() => setHoveredAccountId(account.id)}
                      onMouseLeave={() => setHoveredAccountId(null)}
                    >
                      <span className={clsx(
                        'px-2 py-0.5 rounded text-xs font-bold whitespace-nowrap',
                        account.mode === 'real'
                          ? 'bg-green-50 text-green-600 border border-green-200'
                          : 'bg-blue-50 text-blue-600 border border-blue-200'
                      )}>
                        {account.id}
                      </span>
                      {hoveredAccountId === account.id && (
                        <button
                          onClick={() => { setCurrentAccountId(account.id); setShowDeleteDialog(true); }}
                          className="absolute -top-1 -right-1 bg-red-500 hover:bg-red-600 text-white rounded-full p-0.5 cursor-pointer transition-colors shadow-md"
                        >
                          <Trash2 size={10} />
                        </button>
                      )}
                    </div>

                    <Tooltip.Root>
                      <Tooltip.Trigger
                        onClick={() => handleOpenEditDialog(account)}
                        className="text-xs text-gray-700 font-medium truncate cursor-pointer hover:text-gray-900 transition-colors flex-1 text-left bg-transparent border-none p-0 min-w-0"
                      >
                        {account.strategyName}
                      </Tooltip.Trigger>
                      <Tooltip.Portal>
                        <Tooltip.Content
                          className="bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg max-w-xs z-50"
                          sideOffset={5}
                        >
                          {account.strategyName}
                          <Tooltip.Arrow className="fill-gray-900" />
                        </Tooltip.Content>
                      </Tooltip.Portal>
                    </Tooltip.Root>
                  </div>

                  <button
                    onClick={() => {
                      if (account.isRunning) {
                        setCurrentAccountId(account.id);
                        setShowStopDialog(true);
                      } else {
                        handleToggleAccount(account.id);
                      }
                    }}
                    className={clsx(
                      'transition-transform active:scale-95 rounded-full p-1.5 cursor-pointer shadow-sm border border-gray-100 flex-shrink-0',
                      account.isRunning
                        ? 'bg-red-50 text-red-500 hover:bg-red-100'
                        : 'bg-[#10b981]/10 text-[#10b981] hover:bg-[#10b981]/20'
                    )}
                  >
                    {account.isRunning
                      ? <Pause fill="currentColor" size={16} />
                      : <Play  fill="currentColor" size={16} className="ml-0.5" />}
                  </button>
                </div>

                {/* Stats */}
                <div className="space-y-1.5 mb-3">
                  {/* 总资产 with available cash */}
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">总资产</span>
                    <span className="text-gray-900 font-bold font-mono">
                      ${fmt(account.totalAssets)}
                      <span className="text-gray-400 font-normal"> (${fmt(account.availableCash)})</span>
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">总市值</span>
                    <span className="text-gray-900 font-mono">${fmt(account.marketValue)}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">今日收益</span>
                    <span className={clsx('font-bold font-mono', getProfitColor(account.todayProfit))}>
                      {account.todayProfit >= 0 ? '+' : ''}${Math.abs(account.todayProfit).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      {' '}({((account.todayProfit / account.initialBalance) * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">总收益</span>
                    <span className={clsx('font-bold font-mono', getProfitColor(account.totalProfit))}>
                      {account.totalProfit >= 0 ? '+' : ''}${Math.abs(account.totalProfit).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      {' '}({((account.totalProfit / account.initialBalance) * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">胜率</span>
                    <span className="text-gray-900 font-bold">{account.winRate}%</span>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex gap-2 pt-2 border-t border-gray-100">
                  <button
                    onClick={() => { setCurrentAccountId(account.id); setShowPositions(true); }}
                    className="flex-1 bg-gray-50 hover:bg-gray-100 text-gray-700 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer border border-gray-200"
                  >
                    持仓({account.positionCount})
                  </button>
                  <button
                    onClick={() => { setCurrentAccountId(account.id); setShowTradeLogs(true); }}
                    className="flex-1 bg-gray-50 hover:bg-gray-100 text-gray-700 py-1.5 rounded text-xs font-medium transition-colors cursor-pointer border border-gray-200"
                  >
                    交易记录
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ════════════════════════════════════════════════════════════════
            ADD DIALOG — Real mode
        ════════════════════════════════════════════════════════════════ */}
        <Dialog.Root open={showAddDialog && !isSimulation} onOpenChange={v => !v && setShowAddDialog(false)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl p-5 w-[460px] max-h-[90vh] overflow-y-auto z-50 custom-scrollbar">
              <div className="flex justify-between items-center mb-5">
                <Dialog.Title className="text-base font-bold text-gray-900">
                  添加真实交易账户
                </Dialog.Title>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer">
                  <X size={18} />
                </Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">配置新的真实交易账户</Dialog.Description>

              <div className="space-y-4">
                {/* 交易编号 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">交易编号</label>
                  <input
                    type="text"
                    value={`R${String(accounts.filter(a => a.mode === 'real').length + 1).padStart(3, '0')}`}
                    disabled
                    className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 cursor-not-allowed"
                  />
                </div>

                {/* PM Builder账户选择 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">PM Builder 账户</label>
                  <div className="relative">
                    <select
                      value={addForm.pmAccountId}
                      onChange={e => setAddForm(p => ({ ...p, pmAccountId: e.target.value }))}
                      className="w-full border border-gray-200 bg-white rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none cursor-pointer appearance-none pr-8"
                    >
                      <option value="">— 请选择账户 —</option>
                      {PM_BUILDER_ACCOUNTS.map(pm => (
                        <option key={pm.id} value={pm.id}>{pm.name}</option>
                      ))}
                    </select>
                    <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                {/* PM账户资金信息 */}
                {selectedPMAccount && (
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-2">
                    <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">账户资金概��</div>
                    <div className="grid grid-cols-3 gap-2">
                      <div className="text-center bg-white border border-gray-100 rounded-md py-2 px-1">
                        <div className="flex justify-center mb-1"><Wallet size={12} className="text-gray-400" /></div>
                        <div className="text-[10px] text-gray-400 mb-0.5">总资金</div>
                        <div className="text-xs font-bold text-gray-800 font-mono">${fmtK(selectedPMAccount.totalFunds)}</div>
                      </div>
                      <div className="text-center bg-white border border-gray-100 rounded-md py-2 px-1">
                        <div className="flex justify-center mb-1"><TrendingUp size={12} className="text-blue-400" /></div>
                        <div className="text-[10px] text-gray-400 mb-0.5">持仓资金</div>
                        <div className="text-xs font-bold text-blue-600 font-mono">${fmtK(selectedPMAccount.positionFunds)}</div>
                      </div>
                      <div className="text-center bg-white border border-gray-100 rounded-md py-2 px-1">
                        <div className="flex justify-center mb-1"><DollarSign size={12} className="text-[#10b981]" /></div>
                        <div className="text-[10px] text-gray-400 mb-0.5">可用资金</div>
                        <div className="text-xs font-bold text-[#10b981] font-mono">${fmtK(selectedPMAccount.availableFunds)}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 策略选择 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">策略选择</label>
                  <div className="relative">
                    <select
                      value={addForm.strategy}
                      onChange={e => setAddForm(p => ({ ...p, strategy: e.target.value }))}
                      className="w-full border border-gray-200 bg-white rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none cursor-pointer appearance-none pr-8"
                    >
                      {STRATEGY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                {/* 回撤值 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">回撤值 (%)</label>
                  <input
                    type="number"
                    value={addForm.retracement}
                    onChange={e => setAddForm(p => ({ ...p, retracement: e.target.value }))}
                    className="w-full border border-gray-200 bg-gray-50 rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
                    placeholder="2"
                  />
                  <div className="text-[10px] text-gray-400 mt-1">当价格从最高点回撤达到此百分比时卖出</div>
                </div>

                {/* 适用比赛 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">适用比赛</label>
                  <div className="flex flex-wrap gap-2">
                    {SPORT_OPTIONS.map(sport => (
                      <button
                        key={sport}
                        onClick={() => toggleSportAdd(sport)}
                        className={clsx(
                          'px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer border',
                          addForm.sports.includes(sport)
                            ? 'bg-[#10b981] text-white border-[#10b981]'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-[#10b981]'
                        )}
                      >{sport}</button>
                    ))}
                  </div>
                </div>

                {/* Risk params */}
                <RiskParamsSection
                  maxPositions={addForm.maxPositions}
                  maxFundUsageRate={addForm.maxFundUsageRate}
                  maxSingleAmount={addForm.maxSingleAmount}
                  onChange={(field, value) => setAddForm(p => ({ ...p, [field]: value }))}
                />

                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => setShowAddDialog(false)}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded-md text-xs transition-colors cursor-pointer"
                  >取消</button>
                  <button
                    onClick={handleAddAccount}
                    disabled={!addForm.pmAccountId}
                    className={clsx(
                      'flex-1 py-2 rounded-md text-xs transition-colors cursor-pointer text-white',
                      addForm.pmAccountId
                        ? 'bg-[#10b981] hover:bg-[#0ea571]'
                        : 'bg-gray-300 cursor-not-allowed'
                    )}
                  >添加</button>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ════════════════════════════════════════════════════════════════
            ADD DIALOG — Simulation mode
        ════════════════════════════════════════════════════════════════ */}
        <Dialog.Root open={showAddDialog && isSimulation} onOpenChange={v => !v && setShowAddDialog(false)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl p-5 w-[440px] max-h-[90vh] overflow-y-auto z-50 custom-scrollbar">
              <div className="flex justify-between items-center mb-5">
                <Dialog.Title className="text-base font-bold text-gray-900">
                  添加模拟交易账户
                </Dialog.Title>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer">
                  <X size={18} />
                </Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">配置新的模拟交易账户</Dialog.Description>

              <div className="space-y-4">
                {/* 交易编号 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">交易编号</label>
                  <input
                    type="text"
                    value={`S${String(accounts.filter(a => a.mode === 'simulation').length + 1).padStart(3, '0')}`}
                    disabled
                    className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 cursor-not-allowed"
                  />
                </div>

                {/* 初始资金 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">初始资金 ($)</label>
                  <input
                    type="number"
                    value={addForm.initialBalance}
                    onChange={e => setAddForm(p => ({ ...p, initialBalance: e.target.value }))}
                    className="w-full border border-gray-200 bg-gray-50 rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
                    placeholder="100000"
                  />
                </div>

                {/* 策略选择 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">策略选择</label>
                  <div className="relative">
                    <select
                      value={addForm.strategy}
                      onChange={e => setAddForm(p => ({ ...p, strategy: e.target.value }))}
                      className="w-full border border-gray-200 bg-white rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none cursor-pointer appearance-none pr-8"
                    >
                      {STRATEGY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  </div>
                </div>

                {/* 回撤值 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">回撤值 (%)</label>
                  <input
                    type="number"
                    value={addForm.retracement}
                    onChange={e => setAddForm(p => ({ ...p, retracement: e.target.value }))}
                    className="w-full border border-gray-200 bg-gray-50 rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
                    placeholder="2"
                  />
                  <div className="text-[10px] text-gray-400 mt-1">当价格从最高点回撤达到此百分比时卖出</div>
                </div>

                {/* 适用比赛 */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">适用比赛</label>
                  <div className="flex flex-wrap gap-2">
                    {SPORT_OPTIONS.map(sport => (
                      <button
                        key={sport}
                        onClick={() => toggleSportAdd(sport)}
                        className={clsx(
                          'px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer border',
                          addForm.sports.includes(sport)
                            ? 'bg-[#10b981] text-white border-[#10b981]'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-[#10b981]'
                        )}
                      >{sport}</button>
                    ))}
                  </div>
                </div>

                {/* Risk params */}
                <RiskParamsSection
                  maxPositions={addForm.maxPositions}
                  maxFundUsageRate={addForm.maxFundUsageRate}
                  maxSingleAmount={addForm.maxSingleAmount}
                  onChange={(field, value) => setAddForm(p => ({ ...p, [field]: value }))}
                />

                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => setShowAddDialog(false)}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded-md text-xs transition-colors cursor-pointer"
                  >取消</button>
                  <button
                    onClick={handleAddAccount}
                    className="flex-1 bg-[#10b981] hover:bg-[#0ea571] text-white py-2 rounded-md text-xs transition-colors cursor-pointer"
                  >添加</button>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ════════════════════════════════════════════════════════════════
            EDIT DIALOG
        ════════════════════════════════════════════════════════════════ */}
        <Dialog.Root open={showEditDialog} onOpenChange={setShowEditDialog}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl p-5 w-[440px] max-h-[90vh] overflow-y-auto z-50 custom-scrollbar">
              <div className="flex justify-between items-center mb-5">
                <Dialog.Title className="text-base font-bold text-gray-900">策略配置 — {currentAccountId}</Dialog.Title>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer"><X size={18} /></Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">修改交易账户的策略参数配置</Dialog.Description>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">交易编号</label>
                  <input type="text" value={currentAccountId || ''} disabled
                    className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 cursor-not-allowed" />
                </div>

                {/* Show PM account info for real accounts */}
                {currentAccount?.mode === 'real' && currentAccount.pmAccountId && (() => {
                  const pm = PM_BUILDER_ACCOUNTS.find(p => p.id === currentAccount.pmAccountId);
                  if (!pm) return null;
                  return (
                    <div>
                      <label className="text-xs text-gray-500 block mb-1.5">PM Builder 账户</label>
                      <div className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500">{pm.name}</div>
                      <div className="bg-gray-50 border border-gray-200 rounded-md p-3 mt-2 grid grid-cols-3 gap-2">
                        <div className="text-center">
                          <div className="text-[10px] text-gray-400">总资金</div>
                          <div className="text-xs font-bold text-gray-700 font-mono">${fmtK(pm.totalFunds)}</div>
                        </div>
                        <div className="text-center">
                          <div className="text-[10px] text-gray-400">持仓资金</div>
                          <div className="text-xs font-bold text-blue-600 font-mono">${fmtK(pm.positionFunds)}</div>
                        </div>
                        <div className="text-center">
                          <div className="text-[10px] text-gray-400">可用资金</div>
                          <div className="text-xs font-bold text-[#10b981] font-mono">${fmtK(pm.availableFunds)}</div>
                        </div>
                      </div>
                    </div>
                  );
                })()}

                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">策略</label>
                  <input type="text" value={currentAccount?.strategyName || ''} disabled
                    className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 cursor-not-allowed" />
                </div>

                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">回撤值 (%)</label>
                  <input
                    type="number"
                    value={editForm.retracement}
                    onChange={e => setEditForm(p => ({ ...p, retracement: e.target.value }))}
                    className="w-full border border-gray-200 bg-gray-50 rounded-md px-3 py-2 text-xs text-gray-900 focus:border-[#10b981] focus:outline-none"
                    placeholder="2"
                  />
                  <div className="text-[10px] text-gray-400 mt-1">当价格从最高点回撤达到此百分比时卖出</div>
                </div>

                <div>
                  <label className="text-xs text-gray-500 block mb-1.5">初始资金 ($)</label>
                  <input type="text" value={`$${fmt(currentAccount?.initialBalance ?? 0)}`} disabled
                    className="w-full border border-gray-200 bg-gray-100 rounded-md px-3 py-2 text-xs text-gray-500 cursor-not-allowed" />
                </div>

                {/* Risk params */}
                <RiskParamsSection
                  maxPositions={editForm.maxPositions}
                  maxFundUsageRate={editForm.maxFundUsageRate}
                  maxSingleAmount={editForm.maxSingleAmount}
                  onChange={(field, value) => setEditForm(p => ({ ...p, [field]: value }))}
                />

                <div className="flex gap-2 pt-2">
                  <button onClick={() => setShowEditDialog(false)}
                    className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded-md text-xs transition-colors cursor-pointer">取消</button>
                  <button onClick={handleUpdateAccount}
                    className="flex-1 bg-[#10b981] hover:bg-[#0ea571] text-white py-2 rounded-md text-xs transition-colors cursor-pointer">保存</button>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ── Delete Dialog ─────────────────────────────────────────────── */}
        <Dialog.Root open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl p-5 w-[380px] z-50">
              <div className="flex justify-between items-center mb-5">
                <Dialog.Title className="text-base font-bold text-gray-900">确认删除</Dialog.Title>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer"><X size={18} /></Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">确认删除交易账户操作</Dialog.Description>
              <p className="text-sm text-gray-600 mb-6">
                确定要删除交易账户 <span className="font-bold text-gray-900">{currentAccountId}</span> 吗？此操作无法撤销。
              </p>
              <div className="flex gap-2">
                <button onClick={() => setShowDeleteDialog(false)}
                  className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded-md text-xs transition-colors cursor-pointer">取消</button>
                <button onClick={handleDeleteAccount}
                  className="flex-1 bg-red-500 hover:bg-red-600 text-white py-2 rounded-md text-xs transition-colors cursor-pointer">确认删除</button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ── Stop Dialog ────────────────────────────────────────���──────── */}
        <Dialog.Root open={showStopDialog} onOpenChange={setShowStopDialog}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl p-5 w-[380px] z-50">
              <div className="flex justify-between items-center mb-5">
                <Dialog.Title className="text-base font-bold text-gray-900">确认停止</Dialog.Title>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer"><X size={18} /></Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">确认停止交易账户运行</Dialog.Description>
              <p className="text-sm text-gray-600 mb-6">
                确定要停止交易账户 <span className="font-bold text-gray-900">{currentAccountId}</span> 吗？停止后将不再自动交易。
              </p>
              <div className="flex gap-2">
                <button onClick={() => setShowStopDialog(false)}
                  className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-600 py-2 rounded-md text-xs transition-colors cursor-pointer">取消</button>
                <button onClick={handleConfirmStop}
                  className="flex-1 bg-red-500 hover:bg-red-600 text-white py-2 rounded-md text-xs transition-colors cursor-pointer">确认停止</button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ── Positions Dialog ──────────────────────────────────────────── */}
        <Dialog.Root open={showPositions} onOpenChange={setShowPositions}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl w-[820px] h-[78vh] z-50 flex flex-col">
              <div className="flex justify-between items-center px-5 pt-5 pb-3 border-b border-gray-100 flex-shrink-0">
                <div>
                  <Dialog.Title className="text-base font-bold text-gray-900">持仓详情 — {currentAccountId}</Dialog.Title>
                  <p className="text-[11px] text-gray-400 mt-0.5">{viewPositions.length} 个持仓中</p>
                </div>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer"><X size={18} /></Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">查看交易账户的当前持仓信息</Dialog.Description>
              <div className="flex-1 overflow-y-auto custom-scrollbar">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                    <tr className="text-gray-400">
                      <th className="px-4 py-2.5 text-left font-medium">订单编号</th>
                      <th className="px-3 py-2.5 text-left font-medium">比赛</th>
                      <th className="px-3 py-2.5 text-left font-medium">队伍</th>
                      <th className="px-3 py-2.5 text-right font-medium">买入价</th>
                      <th className="px-3 py-2.5 text-right font-medium">现价</th>
                      <th className="px-3 py-2.5 text-right font-medium">份额</th>
                      <th className="px-3 py-2.5 text-right font-medium">投入 $</th>
                      <th className="px-4 py-2.5 text-right font-medium">浮动盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    {viewPositions.map(pos => {
                      const isProfit = pos.profit >= 0;
                      const profitColor = isProfit ? 'text-red-500' : 'text-green-600';
                      return (
                        <tr key={pos.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                          <td className="px-4 py-2.5">
                            <span className="font-mono text-[11px] text-gray-500">{pos.orderId}</span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-gray-700 font-medium whitespace-nowrap">{pos.matchName}</span>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-gray-600">{pos.teamName}</span>
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono text-blue-600">{pos.entryPrice.toFixed(3)}</td>
                          <td className="px-3 py-2.5 text-right font-mono text-orange-600">{pos.currentPrice.toFixed(3)}</td>
                          <td className="px-3 py-2.5 text-right text-gray-600">{pos.shares.toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right text-gray-700 font-mono">${pos.amount.toFixed(2)}</td>
                          <td className={clsx('px-4 py-2.5 text-right font-medium whitespace-nowrap', profitColor)}>
                            {isProfit ? '+' : ''}${Math.abs(pos.profit).toFixed(2)}
                            <span className="ml-1 text-[10px]">({isProfit ? '+' : ''}{pos.profitPercent.toFixed(1)}%)</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {/* Footer summary */}
              <div className="px-5 py-3 border-t border-gray-100 bg-gray-50 flex items-center justify-between flex-shrink-0 text-xs">
                <span className="text-gray-500">总投入: <span className="font-bold text-gray-700 font-mono">${viewPositions.reduce((s, p) => s + p.amount, 0).toFixed(2)}</span></span>
                <span className="text-gray-500">总浮盈: {(() => {
                  const total = viewPositions.reduce((s, p) => s + p.profit, 0);
                  return <span className={clsx('font-bold font-mono', total >= 0 ? 'text-red-500' : 'text-green-600')}>{total >= 0 ? '+' : ''}${total.toFixed(2)}</span>;
                })()}</span>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        {/* ── Trade Records Dialog ──────────────────────────────────────── */}
        <Dialog.Root open={showTradeLogs} onOpenChange={v => { setShowTradeLogs(v); if (v) { setTradeSearch(''); setTradePage(1); } }}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-gray-900/50 z-50 backdrop-blur-sm" />
            <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white border border-gray-200 rounded-lg shadow-2xl w-[960px] h-[80vh] z-50 flex flex-col">
              {/* Header */}
              <div className="flex justify-between items-center px-5 pt-5 pb-3 border-b border-gray-100 flex-shrink-0">
                <div>
                  <Dialog.Title className="text-base font-bold text-gray-900">交易记录 — {currentAccountId}</Dialog.Title>
                  <p className="text-[11px] text-gray-400 mt-0.5">仅显示已完成订单</p>
                </div>
                <Dialog.Close className="text-gray-400 hover:text-gray-600 cursor-pointer"><X size={18} /></Dialog.Close>
              </div>
              <Dialog.Description className="sr-only">查看交易账户的已完成交易记录</Dialog.Description>

              {/* Search bar */}
              <div className="px-5 py-3 border-b border-gray-100 flex-shrink-0">
                <div className="relative w-80">
                  <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  <input
                    type="text"
                    placeholder="搜索订单编号或时间（如 ORD- 或 2026-03）"
                    value={tradeSearch}
                    onChange={e => { setTradeSearch(e.target.value); setTradePage(1); }}
                    className="w-full pl-8 pr-3 py-1.5 border border-gray-200 rounded-md text-xs text-gray-700 bg-gray-50 focus:outline-none focus:border-[#10b981] placeholder-gray-400"
                  />
                </div>
              </div>

              {/* Table + pagination */}
              {(() => {
                const q = tradeSearch.trim().toLowerCase();
                const filtered = viewTrades.filter(r => {
                  if (!q) return true;
                  const dateStr = new Date(r.timestamp).toLocaleString();
                  return r.orderId.toLowerCase().includes(q) || dateStr.toLowerCase().includes(q);
                });
                const totalPages = Math.max(1, Math.ceil(filtered.length / TRADE_PAGE_SIZE));
                const safePage   = Math.min(tradePage, totalPages);
                const paged      = filtered.slice((safePage - 1) * TRADE_PAGE_SIZE, safePage * TRADE_PAGE_SIZE);
                const pageNums   = Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(p => p === 1 || p === totalPages || Math.abs(p - safePage) <= 1)
                  .reduce<(number | '...')[]>((acc, p, idx, arr) => {
                    if (idx > 0 && typeof arr[idx-1] === 'number' && (p as number) - (arr[idx-1] as number) > 1) acc.push('...');
                    acc.push(p);
                    return acc;
                  }, []);
                return (
                  <>
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                      {paged.length > 0 ? (
                        <table className="w-full text-xs">
                          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                            <tr className="text-gray-400">
                              <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">订单编号</th>
                              <th className="px-3 py-2.5 text-left font-medium">策略</th>
                              <th className="px-3 py-2.5 text-left font-medium">方向</th>
                              <th className="px-3 py-2.5 text-right font-medium">成本</th>
                              <th className="px-3 py-2.5 text-right font-medium">卖出价</th>
                              <th className="px-3 py-2.5 text-right font-medium">数量</th>
                              <th className="px-3 py-2.5 text-right font-medium">金额</th>
                              <th className="px-3 py-2.5 text-right font-medium">收益</th>
                              <th className="px-4 py-2.5 text-right font-medium whitespace-nowrap">成交时间</th>
                            </tr>
                          </thead>
                          <tbody>
                            {paged.map(rec => {
                              const isProfit = rec.profit >= 0;
                              const profitColor = isProfit ? 'text-red-500' : 'text-green-600';
                              const d = new Date(rec.timestamp);
                              const dateStr = `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
                              return (
                                <tr key={rec.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                                  <td className="px-4 py-2.5">
                                    <span className="font-mono text-[11px] text-gray-500 whitespace-nowrap">{rec.orderId}</span>
                                  </td>
                                  <td className="px-3 py-2.5">
                                    <span className={clsx('font-mono font-semibold text-[11px]', rec.strategy.startsWith('R') ? 'text-green-600' : 'text-blue-500')}>
                                      {rec.strategy}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2.5">
                                    <span className="text-[11px] text-gray-700 font-medium whitespace-nowrap">{rec.side}</span>
                                  </td>
                                  <td className="px-3 py-2.5 text-right text-gray-500 font-mono">{rec.entryPrice.toFixed(3)}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-700 font-mono">{rec.exitPrice.toFixed(3)}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-600">{rec.quantity}</td>
                                  <td className="px-3 py-2.5 text-right text-gray-600 font-mono">${rec.amount.toFixed(2)}</td>
                                  <td className={clsx('px-3 py-2.5 text-right font-medium whitespace-nowrap', profitColor)}>
                                    {isProfit ? '+' : ''}{rec.profit.toFixed(2)}({isProfit ? '+' : ''}{rec.profitRate.toFixed(2)}%)
                                  </td>
                                  <td className="px-4 py-2.5 text-right text-gray-400 font-mono text-[11px] whitespace-nowrap">{dateStr}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      ) : (
                        <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                          {tradeSearch ? '未找到匹配的记录' : '暂无交易记录'}
                        </div>
                      )}
                    </div>
                    {/* Pagination footer */}
                    <div className="px-5 py-3 border-t border-gray-100 bg-gray-50 flex items-center justify-between flex-shrink-0 text-xs">
                      <span className="text-gray-400">
                        共 <span className="text-gray-700 font-medium">{filtered.length}</span> 条{tradeSearch ? ' (已过滤)' : ''}，
                        第 <span className="text-gray-700 font-medium">{safePage}</span> / {totalPages} 页
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setTradePage(p => Math.max(1, p - 1))}
                          disabled={safePage === 1}
                          className="p-1 rounded border border-gray-200 text-gray-500 disabled:opacity-30 disabled:cursor-not-allowed hover:enabled:bg-gray-100 cursor-pointer transition-colors"
                        >
                          <ChevronLeft size={13} />
                        </button>
                        {pageNums.map((p, i) =>
                          p === '...' ? (
                            <span key={`dots-${i}`} className="px-1 text-gray-400 text-xs">…</span>
                          ) : (
                            <button
                              key={p}
                              onClick={() => setTradePage(p as number)}
                              className={clsx(
                                'min-w-[26px] h-[26px] rounded border text-[11px] cursor-pointer transition-colors',
                                safePage === p
                                  ? 'bg-[#10b981] text-white border-[#10b981]'
                                  : 'border-gray-200 text-gray-600 hover:bg-gray-100'
                              )}
                            >{p}</button>
                          )
                        )}
                        <button
                          onClick={() => setTradePage(p => Math.min(totalPages, p + 1))}
                          disabled={safePage === totalPages}
                          className="p-1 rounded border border-gray-200 text-gray-500 disabled:opacity-30 disabled:cursor-not-allowed hover:enabled:bg-gray-100 cursor-pointer transition-colors"
                        >
                          <ChevronRight size={13} />
                        </button>
                      </div>
                    </div>
                  </>
                );
              })()}
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

      </div>
    </Tooltip.Provider>
  );
};
