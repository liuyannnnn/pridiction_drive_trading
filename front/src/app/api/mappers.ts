export interface BackendMatchCard {
  match_id: string;
  sport: "football" | "basketball";
  league: string;
  team_home: string;
  team_away: string;
  start_time_utc: string;
  status: "live" | "pre" | "finished";
  moneyline_volume: number;
  total_volume: number;
  latest_ts_utc: string;
}


export interface UiMatch {
  id: string;
  sport: "Football" | "Basketball";
  league: string;
  teamA: { id: string; name: string; shortName: string };
  teamB: { id: string; name: string; shortName: string };
  scoreA: number;
  scoreB: number;
  period: string;
  clock: string;
  status: "Live" | "Scheduled" | "Finished";
  startTime: Date;
  wsTime: Date;
  marketA: { bid: number; ask: number };
  marketB: { bid: number; ask: number };
  marketDraw?: { bid: number; ask: number };
  history: { time: number; probabilityA: number }[];
  volume: number;
}


export function mapBackendMatchToUiMatch(row: BackendMatchCard): UiMatch {
  const sport = row.sport === "football" ? "Football" : "Basketball";
  const status = row.status === "live" ? "Live" : row.status === "finished" ? "Finished" : "Scheduled";
  return {
    id: row.match_id,
    sport,
    league: row.league,
    teamA: { id: `${row.match_id}_home`, name: row.team_home, shortName: row.team_home },
    teamB: { id: `${row.match_id}_away`, name: row.team_away, shortName: row.team_away },
    scoreA: 0,
    scoreB: 0,
    period: status === "Live" ? "Live" : "",
    clock: status === "Live" ? "--:--" : "",
    status,
    startTime: new Date(row.start_time_utc),
    wsTime: new Date(row.latest_ts_utc),
    marketA: { bid: 0.5, ask: 0.52 },
    marketB: { bid: 0.48, ask: 0.5 },
    history: [],
    volume: row.moneyline_volume,
  };
}
