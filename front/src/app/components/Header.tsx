import React, { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';

export const Header = () => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-14 bg-white border-b border-gray-200 flex items-center px-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-gradient-to-br from-[#10b981] to-[#059669] rounded-lg flex items-center justify-center">
          <Activity className="w-5 h-5 text-white" strokeWidth={2.5} />
        </div>
        <div className="flex flex-col">
          <h1 className="text-lg font-bold text-gray-900 leading-none">预测驱动交易系统</h1>
          <p className="text-xs text-gray-500 leading-none mt-0.5">Pridiction Drive Trading Platform</p>
        </div>
      </div>
      
      <div className="ml-auto flex items-center gap-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#10b981]"></div>
            <span className="text-xs text-gray-600">PolyMarket已连接</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-[#10b981]"></div>
            <span className="text-xs text-gray-600">GoalServe已连接</span>
          </div>
        </div>
        <div className="text-sm text-gray-500 font-mono tabular-nums">
          {currentTime.toLocaleString('zh-CN', { 
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
          })}
        </div>
      </div>
    </div>
  );
};