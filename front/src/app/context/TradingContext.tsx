import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import { CollectorSettings, fetchCollectorSettings, fetchMatches, saveCollectorSettings, startSimulation, stopSimulation } from "../api/client";
import { mapBackendMatchToUiMatch } from "../api/mappers";
import { applyWsTickToMatches } from "../api/trading-mappers";

export interface Team {
  id: string;
  name: string;
  shortName: string;
}

export interface Market {
  bid: number;
  ask: number;
}

export interface Match {
  id: string;
  sport: "Football" | "Basketball" | "Tennis";
  league: string;
  teamA: Team;
  teamB: Team;
  scoreA: number;
  scoreB: number;
  period: string;
  clock: string;
  status: "Live" | "Scheduled" | "Finished";
  startTime: Date;
  wsTime: Date;
  marketA: Market;
  marketB: Market;
  marketDraw?: Market;
  history: { time: number; probabilityA: number }[];
  volume: number;
}

export interface Position {
  id: string;
  matchId: string;
  teamId: string;
  amount: number;
  entryPrice: number;
  timestamp: number;
  type: "Buy" | "Sell";
}

export interface TradeLog {
  id: string;
  timestamp: number;
  message: string;
  type: "Info" | "Order" | "Alert" | "Error";
}

export interface TradingStrategy {
  name: string;
  retracement: number;
}

interface TradingContextType {
  matches: Match[];
  historyMatches: Match[];
  selectedMatchId: string | null;
  selectMatch: (id: string) => void;
  balance: number;
  positions: Position[];
  tradeLogs: TradeLog[];
  placeOrder: (matchId: string, teamId: string, amount: number, side: "Buy" | "Sell") => void;
  isSimulation: boolean;
  setSimulationMode: (isSim: boolean) => void;
  resetBalance: (amount: number) => void;
  walletConnected: boolean;
  connectWallet: () => void;
  isRunning: boolean;
  startTrading: (initialBalance: number) => void;
  stopTrading: () => void;
  strategy: TradingStrategy;
  updateStrategy: (strategy: TradingStrategy) => void;
  collectorSettings: CollectorSettings;
  updateCollectorSettings: (settings: CollectorSettings) => Promise<void>;
}

const TradingContext = createContext<TradingContextType | undefined>(undefined);

const INITIAL_MATCHES: Match[] = [];

export const HISTORY_MATCHES: Match[] = [];

export const TradingProvider = ({ children }: { children: ReactNode }) => {
  const [matches, setMatches] = useState<Match[]>(INITIAL_MATCHES);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [balance, setBalance] = useState(10000);
  const [positions, setPositions] = useState<Position[]>([]);
  const [tradeLogs, setTradeLogs] = useState<TradeLog[]>([]);
  const [isSimulation, setIsSimulation] = useState(true);
  const [walletConnected, setWalletConnected] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [strategy, setStrategy] = useState<TradingStrategy>({ name: "首分买入，回撤卖出", retracement: 0.05 });
  const [collectorSettings, setCollectorSettings] = useState<CollectorSettings>({
    collection_interval_minutes: 5,
    football_volume_threshold_k: 50,
    basketball_volume_threshold_k: 100,
  });

  const addLog = (message: string, type: TradeLog["type"]) => {
    setTradeLogs((prev) => [{ id: Math.random().toString(), timestamp: Date.now(), message, type }, ...prev].slice(0, 100));
  };

  const loadMatches = useCallback(async () => {
    try {
      const backendRows = await fetchMatches();
      const mapped = backendRows.map(mapBackendMatchToUiMatch);
      setMatches(mapped);
      if (!selectedMatchId && mapped.length > 0) {
        setSelectedMatchId(mapped[0].id);
      }
    } catch (error) {
      addLog(`拉取比赛数据失败: ${String(error)}`, "Error");
    }
  }, [selectedMatchId]);

  useEffect(() => {
    let stopped = false;
    const load = async () => {
      try {
        const settings = await fetchCollectorSettings();
        if (!stopped) {
          setCollectorSettings(settings);
        }
      } catch {}
      if (!stopped) {
        await loadMatches();
      }
    };
    void load();
    const timer = setInterval(() => {
      if (!stopped) {
        void loadMatches();
      }
    }, 5000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [loadMatches]);

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/api/v1/ws/market");
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed?.topic !== "market.tick" || !parsed?.payload?.match_id) {
          return;
        }
        setMatches((prev) =>
          applyWsTickToMatches(prev, {
            match_id: parsed.payload.match_id,
            bid: Number(parsed.payload.bid),
            ask: Number(parsed.payload.ask),
            ts_utc: parsed.payload.ts_utc,
          })
        );
      } catch {}
    };
    return () => {
      ws.close();
    };
  }, []);

  const placeOrder = (matchId: string, teamId: string, amount: number, side: "Buy" | "Sell") => {
    const match = matches.find((m) => m.id === matchId);
    if (!match) {
      return;
    }
    if (side === "Buy") {
      if (balance < amount) {
        addLog("余额不足", "Error");
        return;
      }
      const price = teamId === "teamB" ? match.marketB.ask : match.marketA.ask;
      setBalance((prev) => prev - amount);
      setPositions((prev) => [
        ...prev,
        { id: Math.random().toString(), matchId, teamId, amount, entryPrice: price, timestamp: Date.now(), type: "Buy" },
      ]);
      addLog(`买入 ${amount} 份额 @ ${(price * 100).toFixed(1)}%`, "Order");
      return;
    }
    const target = positions.find((p) => p.matchId === matchId && p.teamId === teamId);
    if (!target) {
      addLog("无可卖出持仓", "Alert");
      return;
    }
    const price = teamId === "teamB" ? match.marketB.bid : match.marketA.bid;
    const pnl = (price - target.entryPrice) * (target.amount / Math.max(target.entryPrice, 0.000001));
    setBalance((prev) => prev + target.amount + pnl);
    setPositions((prev) => prev.filter((p) => p.id !== target.id));
    addLog(`卖出 ${target.amount} 份额 @ ${(price * 100).toFixed(1)}%, 收益 ${pnl.toFixed(2)}`, "Order");
  };

  const connectWallet = () => {
    setWalletConnected(true);
    addLog("钱包已连接", "Info");
  };

  const setSimulationMode = (isSim: boolean) => {
    setIsSimulation(isSim);
    addLog(isSim ? "已切换至模拟交易" : "已切换至真实交易", isSim ? "Info" : "Alert");
  };

  const startTrading = (initialBalance: number) => {
    setIsRunning(true);
    setBalance(initialBalance);
    void startSimulation(initialBalance, strategy.retracement)
      .then(() => addLog("自动交易已启动", "Info"))
      .catch((error) => addLog(`启动失败: ${String(error)}`, "Error"));
  };

  const stopTrading = () => {
    setIsRunning(false);
    void stopSimulation()
      .then(() => addLog("自动交易已停止", "Info"))
      .catch((error) => addLog(`停止失败: ${String(error)}`, "Error"));
  };

  const updateStrategy = (newStrategy: TradingStrategy) => {
    setStrategy(newStrategy);
    addLog(`策略已更新: ${newStrategy.name}`, "Info");
  };

  const updateCollectorSettings = async (settings: CollectorSettings) => {
    try {
      const saved = await saveCollectorSettings(settings);
      setCollectorSettings(saved);
      await loadMatches();
      addLog("采集设置已更新", "Info");
    } catch (error) {
      addLog(`采集设置保存失败: ${String(error)}`, "Error");
    }
  };

  return (
    <TradingContext.Provider
      value={{
        matches,
        historyMatches: HISTORY_MATCHES,
        selectedMatchId,
        selectMatch: setSelectedMatchId,
        balance,
        positions,
        tradeLogs,
        placeOrder,
        isSimulation,
        setSimulationMode,
        resetBalance: setBalance,
        walletConnected,
        connectWallet,
        isRunning,
        startTrading,
        stopTrading,
        strategy,
        updateStrategy,
        collectorSettings,
        updateCollectorSettings,
      }}
    >
      {children}
    </TradingContext.Provider>
  );
};

export const useTrading = () => {
  const context = useContext(TradingContext);
  if (!context) {
    throw new Error("useTrading must be used within a TradingProvider");
  }
  return context;
};
