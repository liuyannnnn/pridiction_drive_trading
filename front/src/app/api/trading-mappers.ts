export interface TradingPanelAccount {
  id: string;
  mode: "real" | "simulation";
  strategyName: string;
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
  retracement: number;
  total_assets: number;
  available_cash: number;
  position_count: number;
  is_running: boolean;
}): TradingPanelAccount {
  return {
    id: row.id,
    mode: row.mode,
    strategyName: row.strategy_name,
    strategyParams: { retracement: Number((row.retracement * 100).toFixed(2)) },
    initialBalance: row.total_assets,
    sports: ["足球", "篮球"],
    totalAssets: row.total_assets,
    availableCash: row.available_cash,
    marketValue: Math.max(0, row.total_assets - row.available_cash),
    todayProfit: 0,
    totalProfit: 0,
    winRate: 0,
    isRunning: row.is_running,
    positionCount: row.position_count,
    maxPositions: 0,
    maxFundUsageRate: 0,
    maxSingleAmount: 0,
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
