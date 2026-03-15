import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { motion } from "motion/react";
import { clsx } from "clsx";
import { Maximize2, X } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { useTrading } from "../context/TradingContext";
import { fetchGoalserveMatchDetail, fetchLogs, fetchTicks, fetchTrades } from "../api/client";

// ─── Trade Record Types ────────────────────────────────────────────────
interface TradeRecord {
  id: number;
  strategy: string;
  status: "持仓" | "完成";
  side: string;        // team name
  entryPrice: number;  // 成本
  currentPrice: number; // 当前
  quantity: number;
  amount: number;
  profit: number;
  profitRate: number;
}

// ─── Component ────────────────────────────────────────────────────────
export const MatchDetail = () => {
  const { matches, historyMatches, selectedMatchId, tradeLogs: contextLogs } = useTrading();
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [backendTicks, setBackendTicks] = useState<Array<{ time: string; bid: number; ask: number }>>([]);
  const [backendTrades, setBackendTrades] = useState<any[]>([]);
  const [backendLogs, setBackendLogs] = useState<any[]>([]);
  const [goalserveDetail, setGoalserveDetail] = useState<any>(null);

  // Search live/scheduled + history matches
  const match = useMemo(
    () =>
      [...matches, ...historyMatches].find((m) => m.id === selectedMatchId),
    [matches, historyMatches, selectedMatchId]
  );

  useEffect(() => {
    if (!selectedMatchId) {
      return;
    }
    let disposed = false;
    const load = async () => {
      try {
        const [ticks, trades, logs, goalserve] = await Promise.all([
          fetchTicks(selectedMatchId),
          fetchTrades(),
          fetchLogs(200),
          fetchGoalserveMatchDetail(selectedMatchId),
        ]);
        if (disposed) {
          return;
        }
        setBackendTicks(ticks);
        setBackendTrades(trades);
        setBackendLogs(logs);
        setGoalserveDetail(goalserve);
      } catch {
        if (!disposed) {
          setBackendTicks([]);
          setBackendTrades([]);
          setBackendLogs([]);
          setGoalserveDetail(null);
        }
      }
    };
    void load();
    return () => {
      disposed = true;
    };
  }, [selectedMatchId]);

  // ECharts option — depends on match
  const chartOption = useMemo(() => {
    const useBackendHistory = backendTicks.length > 0;
    if (!match || (!useBackendHistory && match.history.length === 0)) return {};

    const teamAData = useBackendHistory
      ? backendTicks.map((h) => parseFloat((h.bid * 100).toFixed(2)))
      : match.history.map((h) => parseFloat((h.probabilityA * 100).toFixed(2)));
    const teamBData = useBackendHistory
      ? backendTicks.map((h) => parseFloat((Math.max(0, 1 - h.bid) * 100).toFixed(2)))
      : match.history.map((h) => {
          if (match.marketDraw) {
            return parseFloat(
              (Math.max(0, 1 - h.probabilityA - match.marketDraw.bid) * 100).toFixed(2)
            );
          }
          return parseFloat(((1 - h.probabilityA) * 100).toFixed(2));
        });
    const drawData = match.marketDraw
      ? match.history.map(() =>
          parseFloat((match.marketDraw!.bid * 100).toFixed(2))
        )
      : null;

    const xLabels = useBackendHistory
      ? backendTicks.map((_, i) => i.toString())
      : match.history.map((_, i) => i.toString());

    const series: any[] = [
      {
        name: match.teamA.shortName,
        type: "line",
        smooth: true,
        data: teamAData,
        symbol: "none",
        lineStyle: { color: "#3b82f6", width: 2.5 },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(59,130,246,0.20)" },
              { offset: 1, color: "rgba(59,130,246,0.02)" },
            ],
          },
        },
      },
    ];

    if (drawData) {
      series.push({
        name: "Draw",
        type: "line",
        smooth: true,
        data: drawData,
        symbol: "none",
        lineStyle: { color: "#9ca3af", width: 2 },
        areaStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(156,163,175,0.18)" },
              { offset: 1, color: "rgba(156,163,175,0.02)" },
            ],
          },
        },
      });
    }

    series.push({
      name: match.teamB.shortName,
      type: "line",
      smooth: true,
      data: teamBData,
      symbol: "none",
      lineStyle: { color: "#f97316", width: 2.5 },
      areaStyle: {
        color: {
          type: "linear", x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(249,115,22,0.20)" },
            { offset: 1, color: "rgba(249,115,22,0.02)" },
          ],
        },
      },
    });

    return {
      animation: false,
      grid: { top: 12, right: 12, bottom: 28, left: 44 },
      xAxis: {
        type: "category",
        data: xLabels,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        interval: 25,
        axisLabel: {
          formatter: "{value}%",
          color: "#9ca3af",
          fontSize: 11,
        },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#f3f4f6", type: "dashed" } },
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#fff",
        borderColor: "#e5e7eb",
        borderWidth: 1,
        textStyle: { color: "#374151", fontSize: 12 },
        formatter: (params: any[]) =>
          params
            .map((p: any) => `${p.marker}${p.seriesName}: <b>${p.value}%</b>`)
            .join("<br/>"),
      },
      legend: { show: false },
      series,
    };
  }, [match, backendTicks]);

  // Mock trade records
  const tradeRecords = useMemo((): TradeRecord[] => {
    if (!match) return [];
    if (backendTrades.length === 0) return [];
    return backendTrades.map((item, index) => ({
      id: index + 1,
      strategy: "S001",
      status: item.action === "buy" ? "持仓" : "完成",
      side: item.action === "buy" ? match.teamA.shortName : match.teamB.shortName,
      entryPrice: Number(item.price || 0),
      currentPrice: Number(item.price || 0),
      quantity: Number(item.amount || 0),
      amount: Number(item.amount || 0),
      profit: Number(item.profit || 0),
      profitRate: Number(item.amount || 0) > 0 ? (Number(item.profit || 0) / Number(item.amount || 1)) * 100 : 0,
    }));
  }, [match, backendTrades]);

  const tradeLogs = useMemo(() => {
    if (!match) return [];
    if (backendLogs.length > 0) {
      return backendLogs.slice(0, 200).map((log, index) => ({
        id: index + 1,
        timestamp: new Date(log.ts_utc).getTime(),
        tradeId: "S001",
        action: log.level,
        content: log.message,
      }));
    }
    if (contextLogs.length === 0) {
      return [
        { id: 1, timestamp: Date.now(), tradeId: "SYS", action: "信息", content: "等待策略日志..." },
      ];
    }
    return contextLogs.slice(0, 100).map((log, index) => ({
      id: index + 1,
      timestamp: log.timestamp,
      tradeId: "SYS",
      action: log.type,
      content: log.message,
    }));
  }, [match, contextLogs, backendLogs]);

  // Early return AFTER all hooks
  if (!match) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        选择比赛查看详情
      </div>
    );
  }

  const isLive = match.status === "Live";
  const isFinished = match.status === "Finished";
  const mlVolume = match.volume;
  const totalVolume = match.volume * 3.8;

  const formatTimestamp = (ts: number) => {
    const d = new Date(ts);
    return `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}.${String(d.getMilliseconds()).padStart(3,'0')}`;
  };

  const lastPoint = match.history[match.history.length - 1];
  const teamALast = lastPoint ? (lastPoint.probabilityA * 100).toFixed(1) : "—";
  const teamBLast = lastPoint
    ? match.marketDraw
      ? (Math.max(0, 1 - lastPoint.probabilityA - match.marketDraw.bid) * 100).toFixed(1)
      : ((1 - lastPoint.probabilityA) * 100).toFixed(1)
    : "—";

  // ─── Log rows helper ─────────────────────────────────────────────────
  const LogRow = ({ log }: { log: typeof tradeLogs[0] }) => (
    <div className="text-gray-300 leading-relaxed">
      <span className="text-gray-500">[{formatTimestamp(log.timestamp)}]</span>{" "}
      <span className={clsx("font-semibold", log.tradeId.startsWith("S") ? "text-blue-400" : "text-green-500")}>
        [{log.tradeId}]
      </span>{" "}
      <span className="text-gray-300">{log.action}:</span>{" "}
      <span className="text-gray-200">{log.content}</span>
    </div>
  );

  return (
    <div className="bg-gray-50 flex flex-col h-full overflow-y-auto custom-scrollbar">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="p-4 bg-white border-b border-gray-200 m-[0px]">
        {/* League row + total volume */}
        <div className="flex justify-between items-center mb-2">
          <div className="flex items-center gap-2">
            <span className="bg-gray-50 px-2 py-0.5 rounded-md text-xs font-medium text-gray-600 border border-gray-200">
              {match.sport === "Football" ? "⚽" : match.sport === "Basketball" ? "🏀" : "🎾"}{" "}{match.sport}
            </span>
            <span className="text-sm text-gray-500">{match.league}</span>
          </div>
          {/* Total volume top-right */}
          <span className="text-xs text-gray-500">
            Total Vol: <span className="text-gray-700 font-medium">${totalVolume.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
          </span>
        </div>

        {/* Status & clock */}
        <div className="flex justify-center items-center gap-3 mb-2">
          {isLive ? (
            <div className="flex items-center gap-1.5 bg-red-50 px-2 py-1 rounded-md border border-red-100">
              <motion.div animate={{ opacity: [1, 0.2, 1] }} transition={{ repeat: Infinity, duration: 1.5 }} className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-xs font-bold text-red-500">LIVE</span>
            </div>
          ) : isFinished ? (
            <div className="bg-gray-100 px-2 py-1 rounded-md border border-gray-200">
              <span className="text-xs font-bold text-gray-400">END</span>
            </div>
          ) : (
            <div className="bg-blue-50 px-2 py-1 rounded-md border border-blue-100">
              <span className="text-xs font-bold text-blue-500">PRE-MATCH</span>
            </div>
          )}
          <span className="text-sm text-[#10b981] font-medium">
            {isLive ? `${match.period} ${match.clock}` : match.startTime.toLocaleString()}
          </span>
        </div>

        {/* Score */}
        <div className="flex justify-center items-center gap-8 mb-3">
          <div className="flex-1 text-right">
            <div className="text-xl font-bold text-gray-900">{match.teamA.name}</div>
          </div>
          <div className="flex items-center justify-center gap-4 text-5xl font-black tracking-tighter">
            <span className="text-gray-900">{match.scoreA}</span>
            <span className="text-gray-300 text-3xl">-</span>
            <span className="text-gray-900">{match.scoreB}</span>
          </div>
          <div className="flex-1 text-left">
            <div className="text-xl font-bold text-gray-900">{match.teamB.name}</div>
          </div>
        </div>

        {/* Market boxes */}
        <div className="flex justify-between gap-3 mb-2 px-4">
          <div className="flex flex-col items-center">
            <div className="text-xl font-bold text-blue-500 mb-1">{(match.marketA.bid * 100).toFixed(1)}%</div>
            <div className="flex gap-3 text-xs text-gray-500">
              <span>Bid: {match.marketA.bid.toFixed(3)}</span>
              <span>Ask: {match.marketA.ask.toFixed(3)}</span>
            </div>
          </div>
          {match.marketDraw && (
            <div className="flex flex-col items-center">
              <div className="text-xl font-bold text-gray-700 mb-1">{(match.marketDraw.bid * 100).toFixed(1)}%</div>
              <div className="flex gap-3 text-xs text-gray-500">
                <span>Bid: {match.marketDraw.bid.toFixed(3)}</span>
                <span>Ask: {match.marketDraw.ask.toFixed(3)}</span>
              </div>
            </div>
          )}
          <div className="flex flex-col items-center">
            <div className="text-xl font-bold text-orange-500 mb-1">{(match.marketB.bid * 100).toFixed(1)}%</div>
            <div className="flex gap-3 text-xs text-gray-500">
              <span>Bid: {match.marketB.bid.toFixed(3)}</span>
              <span>Ask: {match.marketB.ask.toFixed(3)}</span>
            </div>
          </div>
        </div>

        {/* Poly info */}
        <div className="bg-gray-50 py-2 px-4 flex justify-between text-xs text-gray-400">
          <span>Poly: {match.teamA.shortName.toLowerCase()}_vs_{match.teamB.shortName.toLowerCase()}_2026_03</span>
          <span>Source: 12345678</span>
        </div>
      </div>

      {/* ── ECharts Chart ──────────────────────────────────────────────── */}
      <div className="p-4 bg-white border-b border-gray-200 mt-2">
        {match.history.length > 0 ? (
          <ReactECharts
            key={match.id}
            option={chartOption}
            style={{ height: "256px", width: "100%" }}
            notMerge={true}
            lazyUpdate={true}
          />
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-400 text-sm bg-gray-50 rounded-md">
            暂无历史数据
          </div>
        )}

        {/* Chart footer: ML volume (left) + legend (right) */}
        <div className="flex justify-between items-center mt-2 pt-2 border-t border-gray-100">
          <div className="text-xs text-gray-500">
            ML Vol: <span className="text-gray-700 font-medium">${(mlVolume / 1000).toFixed(1)}K</span>
          </div>
          <div className="flex gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-0.5 bg-blue-500 rounded"></div>
              <span className="text-xs text-gray-600">{match.teamA.shortName} {teamALast}%</span>
            </div>
            {match.marketDraw && (
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-0.5 bg-gray-400 rounded"></div>
                <span className="text-xs text-gray-600">Draw {(match.marketDraw.bid * 100).toFixed(1)}%</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-0.5 bg-orange-500 rounded"></div>
              <span className="text-xs text-gray-600">{match.teamB.shortName} {teamBLast}%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="p-4 bg-white border-b border-gray-200 mt-2">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">外部数据源（Goalserve）</h3>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2">
            <div className="text-gray-400 mb-1">更新时间</div>
            <div className="text-gray-700 font-medium">{goalserveDetail?.updated_at ? new Date(goalserveDetail.updated_at).toLocaleString() : match.wsTime.toLocaleString()}</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2">
            <div className="text-gray-400 mb-1">比分</div>
            <div className="text-gray-700 font-medium">{match.scoreA} - {match.scoreB}</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2">
            <div className="text-gray-400 mb-1">阵容</div>
            <div className="text-gray-700 font-medium">
              {goalserveDetail?.lineups?.map((x: any) => x.team).join(" / ") || `${match.teamA.shortName} / ${match.teamB.shortName}`}
            </div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-md p-2">
            <div className="text-gray-400 mb-1">赔率</div>
            <div className="text-gray-700 font-medium">
              {goalserveDetail?.odds
                ? `${goalserveDetail.odds.home} / ${goalserveDetail.odds.away}`
                : `${(match.marketA.ask * 100).toFixed(1)}% / ${(match.marketB.ask * 100).toFixed(1)}%`}
            </div>
          </div>
        </div>
      </div>

      {/* ── Trade Records ──────────────────────────────────────────────── */}
      <div className="bg-white border-b border-gray-200 mt-2">
        <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">交易记录</h3>
          <span className="text-[11px] text-gray-400">{tradeRecords.length} 条</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400">
                <th className="px-3 py-2 text-left font-medium">策略</th>
                <th className="px-3 py-2 text-left font-medium">状态</th>
                <th className="px-3 py-2 text-left font-medium">方向</th>
                <th className="px-3 py-2 text-right font-medium">成本</th>
                <th className="px-3 py-2 text-right font-medium">当前</th>
                <th className="px-3 py-2 text-right font-medium">数量</th>
                <th className="px-3 py-2 text-right font-medium">金额</th>
                <th className="px-3 py-2 text-right font-medium">收益</th>
              </tr>
            </thead>
            <tbody>
              {tradeRecords.map((rec) => {
                const isProfit = rec.profit >= 0;
                const profitColor = isProfit ? "text-red-500" : "text-green-600";
                return (
                  <tr key={rec.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-3 py-2">
                      <span className={clsx(
                        "font-mono font-semibold text-[11px]",
                        rec.strategy.startsWith("R") ? "text-green-600" : "text-blue-500"
                      )}>
                        {rec.strategy}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={clsx(
                        "px-1.5 py-0.5 rounded text-[10px] font-medium",
                        rec.status === "持仓"
                          ? "bg-blue-50 text-blue-600 border border-blue-100"
                          : "bg-gray-100 text-gray-500 border border-gray-200"
                      )}>
                        {rec.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-[11px] text-gray-700 font-medium whitespace-nowrap">
                        {rec.side}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500 font-mono">{rec.entryPrice.toFixed(3)}</td>
                    <td className="px-3 py-2 text-right text-gray-700 font-mono">{rec.currentPrice.toFixed(3)}</td>
                    <td className="px-3 py-2 text-right text-gray-600">{rec.quantity}</td>
                    <td className="px-3 py-2 text-right text-gray-600">${rec.amount.toFixed(2)}</td>
                    <td className={clsx("px-3 py-2 text-right font-medium whitespace-nowrap", profitColor)}>
                      {isProfit ? "+" : ""}{rec.profit.toFixed(2)}({isProfit ? "+" : ""}{rec.profitRate.toFixed(2)}%)
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Trade Logs ─────────────────────────────────────────────────── */}
      <div className="h-[400px] mt-2 px-0 pb-4 flex-shrink-0">
        <div className="h-full overflow-hidden flex flex-col bg-gray-900 border-2 border-gray-700 rounded-lg shadow-lg">
          <div className="px-4 py-2 border-b border-gray-700 bg-gray-800 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-gray-200">交易策略日志</h3>
            <button
              onClick={() => setShowLogsDialog(true)}
              className="text-gray-400 hover:text-gray-200 cursor-pointer transition-colors p-1 rounded hover:bg-gray-700"
            >
              <Maximize2 size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 bg-gray-900 custom-scrollbar">
            <div className="space-y-0.5 font-mono text-[11px]">
              {tradeLogs.map((log) => <LogRow key={log.id} log={log} />)}
            </div>
          </div>
        </div>
      </div>

      {/* ── Full-screen Logs Dialog ─────────────────────────────────────── */}
      <Dialog.Root open={showLogsDialog} onOpenChange={setShowLogsDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-gray-900/80 z-50 backdrop-blur-sm" />
          <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gray-900 border-2 border-gray-700 rounded-lg shadow-2xl w-[90vw] h-[90vh] z-50 flex flex-col">
            <div className="px-6 py-3 border-b border-gray-700 bg-gray-800 flex justify-between items-center">
              <Dialog.Title className="text-base font-semibold text-gray-200">
                交易策略日志 - 全屏查看
              </Dialog.Title>
              <Dialog.Close className="text-gray-400 hover:text-gray-200 cursor-pointer transition-colors">
                <X size={20} />
              </Dialog.Close>
            </div>
            <Dialog.Description className="sr-only">交易策略日志的全屏查看界面</Dialog.Description>
            <div className="flex-1 overflow-y-auto p-6 bg-gray-900 custom-scrollbar">
              <div className="space-y-1 font-mono text-sm">
                {tradeLogs.map((log) => <LogRow key={log.id} log={log} />)}
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
};
