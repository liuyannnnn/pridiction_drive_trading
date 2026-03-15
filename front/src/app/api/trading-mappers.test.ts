import { describe, expect, it } from "vitest";
import { applyWsTickToMatches, groupMatchesByStatus, mapBackendAccountToTradingAccount } from "./trading-mappers";


describe("groupMatchesByStatus", () => {
  it("groups matches into live and pre", () => {
    const rows = [
      { id: "m1", status: "Live" },
      { id: "m2", status: "Scheduled" },
      { id: "m3", status: "Live" },
    ] as any[];
    const grouped = groupMatchesByStatus(rows);
    expect(grouped.live.map((m) => m.id)).toEqual(["m1", "m3"]);
    expect(grouped.pre.map((m) => m.id)).toEqual(["m2"]);
  });
});


describe("mapBackendAccountToTradingAccount", () => {
  it("maps backend account payload to panel account schema", () => {
    const row = {
      id: "S001",
      mode: "simulation",
      strategy_name: "首分买入，回撤卖出",
      retracement: 0.05,
      total_assets: 1200.0,
      available_cash: 800.0,
      position_count: 2,
      is_running: true,
    };
    const mapped = mapBackendAccountToTradingAccount(row as any);
    expect(mapped.id).toBe("S001");
    expect(mapped.totalAssets).toBe(1200.0);
    expect(mapped.availableCash).toBe(800.0);
    expect(mapped.positionCount).toBe(2);
    expect(mapped.isRunning).toBe(true);
  });
});


describe("applyWsTickToMatches", () => {
  it("updates target match market and ws time", () => {
    const now = Date.now();
    const source = [
      {
        id: "pm_football_001",
        marketA: { bid: 0.5, ask: 0.52 },
        marketB: { bid: 0.48, ask: 0.5 },
        wsTime: new Date(now - 1000),
      },
    ] as any[];
    const updated = applyWsTickToMatches(source, {
      match_id: "pm_football_001",
      bid: 0.61,
      ask: 0.63,
      ts_utc: new Date(now).toISOString(),
    });
    expect(updated[0].marketA.bid).toBe(0.61);
    expect(updated[0].marketA.ask).toBe(0.63);
    expect(updated[0].marketB.bid).toBeCloseTo(0.39);
  });
});
