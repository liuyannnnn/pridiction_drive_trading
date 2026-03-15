import { describe, expect, it } from "vitest";
import { mapBackendMatchToUiMatch } from "./mappers";


describe("mapBackendMatchToUiMatch", () => {
  it("maps backend football match to UI schema", () => {
    const row = {
      match_id: "pm_football_001",
      sport: "football",
      league: "Premier League",
      team_home: "Arsenal",
      team_away: "Chelsea",
      start_time_utc: "2026-03-15T10:00:00Z",
      status: "live",
      moneyline_volume: 120000,
      total_volume: 300000,
      latest_ts_utc: "2026-03-15T10:01:00Z",
    };
    const ui = mapBackendMatchToUiMatch(row);
    expect(ui.id).toBe("pm_football_001");
    expect(ui.sport).toBe("Football");
    expect(ui.teamA.name).toBe("Arsenal");
    expect(ui.teamB.name).toBe("Chelsea");
    expect(ui.status).toBe("Live");
    expect(ui.volume).toBe(120000);
  });
});
