import React from "react";
import { TradingProvider } from "./context/TradingContext";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { MatchDetail } from "./components/MatchDetail";
import { TradingPanel } from "./components/TradingPanel";

function App() {
  return (
    <TradingProvider>
      <div className="min-h-screen w-screen bg-gray-50 text-gray-900 flex flex-col overflow-y-auto">
        <Header />
        <div className="flex-1 grid grid-cols-[340px_1fr_340px]">
          <Sidebar />
          <MatchDetail />
          <TradingPanel />
        </div>
        <footer className="bg-white border-t border-gray-200">
          <div className="grid grid-cols-[340px_1fr_340px]">
            <div className="px-4 py-3 text-xs text-gray-500 border-gray-200">
              © 2026 PolyMarket Trading System
            </div>
            <div className="px-4 py-3 text-xs text-gray-500 text-center border-gray-200">
              实时数据采集中 | 由 GoalServe 提供赛事数据
            </div>
            <div className="px-4 py-3 text-xs text-gray-500 text-right">
              v1.0.0
            </div>
          </div>
        </footer>
      </div>
    </TradingProvider>
  );
}

export default App;