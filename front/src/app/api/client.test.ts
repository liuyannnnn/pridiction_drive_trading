import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchLogs, fetchTrades, updateTradingInstance } from "./client";


function mockJsonResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  } as Response;
}


afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});


describe("fetchTrades", () => {
  it("passes match_id to the backend when match-scoped trades are requested", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await fetchTrades({ matchId: "match-a", limit: 50 });

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/api/v1/trades");
    expect(calledUrl.searchParams.get("match_id")).toBe("match-a");
    expect(calledUrl.searchParams.get("limit")).toBe("50");
  });
});


describe("fetchLogs", () => {
  it("passes match_id and limit to the backend when current-match logs are requested", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await fetchLogs({ matchId: "match-a", limit: 20 });

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/api/v1/logs");
    expect(calledUrl.searchParams.get("match_id")).toBe("match-a");
    expect(calledUrl.searchParams.get("limit")).toBe("20");
  });
});


describe("updateTradingInstance", () => {
  it("sends a PUT payload for partial strategy updates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockJsonResponse({ trading_id: "TRD-001", status: "running", mode: "simulation", strategy_name: "prematch_gap_retracement" }));
    vi.stubGlobal("fetch", fetchMock);

    await updateTradingInstance("TRD-001", {
      strategy_params: { max_drawdown: 0.07, trade_amount: 150 },
      affect_sports: ["basketball"],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8000/api/v1/tradings/TRD-001");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    });
    expect(fetchMock.mock.calls[0][1]?.body).toBe(
      JSON.stringify({
        strategy_params: { max_drawdown: 0.07, trade_amount: 150 },
        affect_sports: ["basketball"],
      })
    );
  });
});
