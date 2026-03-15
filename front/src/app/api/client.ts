import { BackendMatchCard } from "./mappers";


const API_BASE = "http://127.0.0.1:8000/api/v1";

export interface CollectorSettings {
  collection_interval_minutes: number;
  football_volume_threshold_k: number;
  basketball_volume_threshold_k: number;
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


export async function fetchAccounts(): Promise<any[]> {
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


export async function fetchTrades(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/trades`);
  if (!response.ok) {
    throw new Error(`trades request failed: ${response.status}`);
  }
  return response.json();
}


export async function fetchLogs(limit = 200): Promise<any[]> {
  const response = await fetch(`${API_BASE}/logs?limit=${limit}`);
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
