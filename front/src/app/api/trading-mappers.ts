export interface TradingPanelAccount {
  id: string;
  mode: "real" | "simulation";
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
  maxPositions: number;
  maxFundUsageRate: number;
  maxSingleAmount: number;
}


const SPORT_LABELS: Record<string, string> = {
  football: "足球",
  basketball: "篮球",
};

const STRATEGY_LABELS: Record<string, string> = {
  prematch_gap_retracement: "开赛前价差回撤",
  live_first_goal_retracement: "足球首球回撤",
};


export function groupMatchesByStatus<T extends { status: string }>(rows: T[]): { live: T[]; pre: T[] } {
  return {
    live: rows.filter((item) => item.status === "Live"),
    pre: rows.filter((item) => item.status !== "Live"),
  };
}


export function mapBackendAccountToTradingAccount(row: {
  id: string;
  mode: "real" | "simulation";
  strategy_name: string;
  strategy_params?: Record<string, unknown>;
  retracement: number;
  initial_balance?: number;
  affect_sports?: string[];
  total_assets: number;
  available_cash: number;
  position_count: number;
  win_rate?: number;
  is_running: boolean;
}): TradingPanelAccount {
  const rawStrategyParams = row.strategy_params ?? {};
  const numericStrategyParams = Object.fromEntries(
    Object.entries(rawStrategyParams)
      .filter(([, value]) => typeof value === "number")
      .map(([key, value]) => [key, Number(value)])
  );
  return {
    id: row.id,
    mode: row.mode,
    strategyKey: row.strategy_name,
    strategyName: STRATEGY_LABELS[row.strategy_name] ?? row.strategy_name,
    strategyConfig: numericStrategyParams,
    strategyParams: { retracement: Number((row.retracement * 100).toFixed(2)) },
    initialBalance: Number(row.initial_balance ?? row.total_assets),
    sports: (row.affect_sports ?? []).map((item) => SPORT_LABELS[item] ?? item),
    totalAssets: row.total_assets,
    availableCash: row.available_cash,
    marketValue: Math.max(0, row.total_assets - row.available_cash),
    todayProfit: 0,
    totalProfit: Number((row.total_assets - Number(row.initial_balance ?? row.total_assets)).toFixed(2)),
    winRate: Number(((row.win_rate ?? 0) * 100).toFixed(2)),
    isRunning: row.is_running,
    positionCount: row.position_count,
    maxPositions: 0,
    maxFundUsageRate: 0,
    maxSingleAmount: Number(numericStrategyParams.trade_amount ?? 0),
  };
}


export function applyWsTickToMatches<T extends {
  id: string;
  marketA: { bid: number; ask: number };
  marketB: { bid: number; ask: number };
  wsTime: Date;
}>(rows: T[], tick: { match_id: string; bid: number; ask: number; ts_utc: string }): T[] {
  return rows.map((row) => {
    if (row.id !== tick.match_id) {
      return row;
    }
    const awayBid = Math.max(0, 1 - tick.bid);
    return {
      ...row,
      marketA: { bid: tick.bid, ask: tick.ask },
      marketB: { bid: awayBid, ask: Math.min(0.99, awayBid + 0.02) },
      wsTime: new Date(tick.ts_utc),
    };
  });
}
