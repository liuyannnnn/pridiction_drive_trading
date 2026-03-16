import { BackendMatchCard } from "./mappers";


const API_BASE = "http://127.0.0.1:8000/api/v1";

export interface CollectorSettings {
  collection_interval_minutes: number;
  football_volume_threshold_k: number;
  basketball_volume_threshold_k: number;
}

export interface CollectorStatus {
  external_stream_enabled: boolean;
  external_stream_started: boolean;
  polymarket_ws_enabled: boolean;
  goalserve_ws_enabled: boolean;
  matches_count: number;
  last_tick_source: string | null;
  latest_tick_ts_utc: string | null;
}

export interface TradingCreatePayload {
  strategy_name: string;
  strategy_params: Record<string, unknown>;
  affect_sports: string[];
  mode: "simulation" | "real";
  account_alias?: string;
}

export interface TradingUpdatePayload {
  strategy_params?: Record<string, unknown>;
  affect_sports?: string[];
}

export interface BackendTradingAccount {
  id: string;
  mode: "simulation" | "real";
  strategy_name: string;
  strategy_params?: Record<string, unknown>;
  retracement: number;
  initial_balance: number;
  affect_sports: string[];
  total_assets: number;
  available_cash: number;
  position_count: number;
  win_rate: number;
  is_running: boolean;
}

export interface TradingSnapshot {
  trading_id: string;
  status: string;
  mode: "simulation" | "real";
  strategy_name: string;
  strategy_params?: Record<string, unknown>;
  affect_sports?: string[];
}


function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) {
      return;
    }
    query.set(key, String(value));
  });
  const suffix = query.toString();
  return suffix.length > 0 ? `?${suffix}` : "";
}


export async function fetchMatches(): Promise<BackendMatchCard[]> {
  const response = await fetch(`${API_BASE}/matches`);
  if (!response.ok) {
    throw new Error(`matches request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchTicks(matchId: string): Promise<Array<{ time: string; bid: number; ask: number }>> {
  const response = await fetch(`${API_BASE}/ticks?match_id=${encodeURIComponent(matchId)}&limit=200`);
  if (!response.ok) {
    throw new Error(`ticks request failed: ${response.status}`);
  }
  const rows = await response.json();
  return rows.map((item: any) => ({
    time: item.ts_utc,
    bid: Number(item.bid),
    ask: Number(item.ask),
  }));
}


export async function fetchAccounts(): Promise<BackendTradingAccount[]> {
  const response = await fetch(`${API_BASE}/accounts`);
  if (!response.ok) {
    throw new Error(`accounts request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchPositions(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/positions`);
  if (!response.ok) {
    throw new Error(`positions request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchTrades(params: { tradingId?: string; matchId?: string; limit?: number } = {}): Promise<any[]> {
  const response = await fetch(
    `${API_BASE}/trades${buildQuery({
      trading_id: params.tradingId,
      match_id: params.matchId,
      limit: params.limit,
    })}`
  );
  if (!response.ok) {
    throw new Error(`trades request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchLogs(params: { tradingId?: string; matchId?: string; limit?: number } = {}): Promise<any[]> {
  const response = await fetch(
    `${API_BASE}/logs${buildQuery({
      trading_id: params.tradingId,
      match_id: params.matchId,
      limit: params.limit ?? 200,
    })}`
  );
  if (!response.ok) {
    throw new Error(`logs request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchGoalserveMatchDetail(matchId: string): Promise<any> {
  const response = await fetch(`${API_BASE}/goalserve/match/${encodeURIComponent(matchId)}`);
  if (!response.ok) {
    throw new Error(`goalserve detail request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchCollectorSettings(): Promise<CollectorSettings> {
  const response = await fetch(`${API_BASE}/settings/collector`);
  if (!response.ok) {
    throw new Error(`collector settings request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchCollectorStatus(): Promise<CollectorStatus> {
  const response = await fetch(`${API_BASE}/collector/status`);
  if (!response.ok) {
    throw new Error(`collector status request failed: ${response.status}`);
  }
  return response.json();
}


export async function saveCollectorSettings(payload: CollectorSettings): Promise<CollectorSettings> {
  const response = await fetch(`${API_BASE}/settings/collector`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`save collector settings failed: ${response.status}`);
  }
  return response.json();
}


export async function startSimulation(initialBalance: number, retracement: number): Promise<{ running: boolean }> {
  const response = await fetch(`${API_BASE}/simulation/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initial_balance: initialBalance, retracement }),
  });
  if (!response.ok) {
    throw new Error(`start simulation failed: ${response.status}`);
  }
  return response.json();
}


export async function stopSimulation(): Promise<{ running: boolean }> {
  const response = await fetch(`${API_BASE}/simulation/stop`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`stop simulation failed: ${response.status}`);
  }
  return response.json();
}

export async function createTrading(payload: TradingCreatePayload): Promise<TradingSnapshot> {
  const response = await fetch(`${API_BASE}/tradings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`create trading failed: ${response.status}`);
  }
  return response.json();
}

export async function updateTradingInstance(tradingId: string, payload: TradingUpdatePayload): Promise<TradingSnapshot> {
  const response = await fetch(`${API_BASE}/tradings/${encodeURIComponent(tradingId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`update trading failed: ${response.status}`);
  }
  return response.json();
}

export async function startTradingInstance(tradingId: string): Promise<TradingSnapshot> {
  const response = await fetch(`${API_BASE}/tradings/${encodeURIComponent(tradingId)}/start`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`start trading failed: ${response.status}`);
  }
  return response.json();
}

export async function stopTradingInstance(tradingId: string): Promise<TradingSnapshot> {
  const response = await fetch(`${API_BASE}/tradings/${encodeURIComponent(tradingId)}/stop`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`stop trading failed: ${response.status}`);
  }
  return response.json();
}

export async function deleteTradingInstance(tradingId: string): Promise<{ deleted: boolean }> {
  const response = await fetch(`${API_BASE}/tradings/${encodeURIComponent(tradingId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`delete trading failed: ${response.status}`);
  }
  return response.json();
}
