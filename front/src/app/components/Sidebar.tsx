import React, { useEffect, useMemo, useState } from 'react';
import { useTrading, Match, HISTORY_MATCHES } from '../context/TradingContext';
import { Search, Filter, Settings, History } from 'lucide-react';
import { clsx } from 'clsx';
import { motion } from 'motion/react';
import { groupMatchesByStatus } from '../api/trading-mappers';

export const Sidebar = () => {
  const { matches, selectMatch, selectedMatchId, collectorSettings, updateCollectorSettings } = useTrading();
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilter, setShowFilter] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [selectedSport, setSelectedSport] = useState<string>('All');
  const [showHistory, setShowHistory] = useState(false);
  
  // Settings State with volume thresholds and collection interval
  const [settings, setSettings] = useState({
    football: true,
    basketball: true,
    tennis: true,
    nba: true,
    ncaa: true,
    premierLeague: true,
    laLiga: true,
    footballVol: 50,
    basketballVol: 100,
    tennisVol: 30,
    nbaVol: 120,
    ncaaVol: 80,
    premierLeagueVol: 60,
    laLigaVol: 55,
    collectionInterval: 15
  });

  useEffect(() => {
    setSettings((prev) => ({
      ...prev,
      collectionInterval: collectorSettings.collection_interval_minutes,
      footballVol: collectorSettings.football_volume_threshold_k,
      basketballVol: collectorSettings.basketball_volume_threshold_k,
    }));
  }, [collectorSettings]);

  const sourceList = showHistory ? HISTORY_MATCHES : matches;

  const filteredMatches = sourceList.filter(match => {
    const matchesSearch = match.teamA.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          match.teamB.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSport = selectedSport === 'All' || match.sport === selectedSport;
    const passVolume =
      (match.sport === 'Football' && match.volume >= settings.footballVol * 1000) ||
      (match.sport === 'Basketball' && match.volume >= settings.basketballVol * 1000) ||
      (match.sport !== 'Football' && match.sport !== 'Basketball');
    return matchesSearch && matchesSport && passVolume;
  });

  const groupedMatches = useMemo(() => groupMatchesByStatus(filteredMatches), [filteredMatches]);

  return (
    <div className="flex flex-col h-full bg-gray-50 text-sm relative">
      
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-r border-gray-200 bg-white">
        <div className="flex items-center gap-2">
          <h2 className="text-gray-900 font-bold text-base">比赛</h2>
          {showHistory && (
            <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-medium">历史</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button 
            onClick={() => {
              setShowHistory(!showHistory);
              setShowFilter(false);
              setShowSettings(false);
            }}
            title="历史比赛"
            className={clsx(
              "p-1.5 rounded-md transition-colors cursor-pointer",
              showHistory ? "bg-[#10b981]/20 text-[#10b981]" : "hover:bg-gray-100 text-gray-500"
            )}
          >
            <History size={16} />
          </button>
          <button 
            onClick={() => {
              setShowFilter(!showFilter);
              setShowSettings(false);
            }}
            className={clsx(
              "p-1.5 rounded-md transition-colors cursor-pointer",
              showFilter ? "bg-[#10b981]/20 text-[#10b981]" : "hover:bg-gray-100 text-gray-500"
            )}
          >
            <Filter size={16} />
          </button>
          <button 
            onClick={() => {
              setShowSettings(!showSettings);
              setShowFilter(false);
            }}
            className={clsx(
              "p-1.5 rounded-md transition-colors cursor-pointer",
              showSettings ? "bg-[#10b981]/20 text-[#10b981]" : "hover:bg-gray-100 text-gray-500"
            )}
          >
            <Settings size={16} />
          </button>
        </div>
      </div>

      {/* Filter Popup */}
      {showFilter && (
        <div className="absolute top-14 left-3 right-3 bg-white border border-gray-200 rounded-md shadow-xl p-3 z-50">
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
              <input 
                type="text"
                placeholder="搜索比赛..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-md pl-8 pr-3 py-1.5 text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#10b981]"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 block mb-2">体育项目</label>
              <div className="flex flex-wrap gap-2">
                {['All', 'Football', 'Basketball', 'Tennis'].map(sport => (
                  <button
                    key={sport}
                    onClick={() => setSelectedSport(sport)}
                    className={clsx(
                      "px-3 py-1 rounded-md text-xs font-medium cursor-pointer transition-colors",
                      selectedSport === sport 
                        ? "bg-[#10b981] text-white" 
                        : "bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100"
                    )}
                  >
                    {sport === 'All' ? '全部' : sport === 'Football' ? '足球' : sport === 'Basketball' ? '篮球' : '网球'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Settings Popup */}
      {showSettings && (
        <div className="absolute top-14 left-3 right-3 bg-white border border-gray-200 rounded-md shadow-xl p-4 z-50 max-w-md">
          <div className="text-sm font-bold text-gray-900 mb-4">数据采集设置</div>
          
          <div className="space-y-4 max-h-96 overflow-y-auto custom-scrollbar pr-2">
            {/* Collection Interval */}
            <div className="pb-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <label className="text-sm text-gray-800 font-medium">采集间隔</label>
                <div className="flex items-center gap-1">
                  <input 
                    type="number"
                    min="1"
                    value={settings.collectionInterval}
                    onChange={(e) => setSettings({...settings, collectionInterval: parseInt(e.target.value) || 1})}
                    className="w-16 bg-gray-50 border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-900 focus:outline-none focus:border-[#10b981]"
                  />
                  <span className="text-xs text-gray-500">分钟</span>
                </div>
              </div>
            </div>

            {/* Football */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={settings.football}
                    onChange={(e) => setSettings({...settings, football: e.target.checked})}
                    className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white"
                  />
                  <span className="text-sm text-gray-800 font-medium">足球</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-500">Vol $</span>
                  <input 
                    type="number" min="0" value={settings.footballVol}
                    onChange={(e) => setSettings({...settings, footballVol: parseInt(e.target.value) || 0})}
                    className="w-18 bg-gray-50 border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-900 focus:outline-none focus:border-[#10b981]"
                  />
                  <span className="text-xs text-gray-500">K</span>
                </div>
              </div>
              <div className="pl-6 space-y-2 border-l border-gray-200 ml-2">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={settings.premierLeague} onChange={(e) => setSettings({...settings, premierLeague: e.target.checked})} className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white w-3 h-3" />
                    <span className="text-xs text-gray-600">英超</span>
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={settings.laLiga} onChange={(e) => setSettings({...settings, laLiga: e.target.checked})} className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white w-3 h-3" />
                    <span className="text-xs text-gray-600">西甲</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Basketball */}
            <div className="pt-3 border-t border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={settings.basketball}
                    onChange={(e) => setSettings({...settings, basketball: e.target.checked})}
                    className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white"
                  />
                  <span className="text-sm text-gray-800 font-medium">篮球</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-500">Vol $</span>
                  <input 
                    type="number" min="0" value={settings.basketballVol}
                    onChange={(e) => setSettings({...settings, basketballVol: parseInt(e.target.value) || 0})}
                    className="w-18 bg-gray-50 border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-900 focus:outline-none focus:border-[#10b981]"
                  />
                  <span className="text-xs text-gray-500">K</span>
                </div>
              </div>
              <div className="pl-6 space-y-2 border-l border-gray-200 ml-2">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={settings.nba} onChange={(e) => setSettings({...settings, nba: e.target.checked})} className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white w-3 h-3" />
                    <span className="text-xs text-gray-600">NBA</span>
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={settings.ncaa} onChange={(e) => setSettings({...settings, ncaa: e.target.checked})} className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white w-3 h-3" />
                    <span className="text-xs text-gray-600">NCAA</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Tennis */}
            <div className="pt-3 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={settings.tennis}
                    onChange={(e) => setSettings({...settings, tennis: e.target.checked})}
                    className="rounded border-gray-300 text-[#10b981] focus:ring-[#10b981] bg-white"
                  />
                  <span className="text-sm text-gray-800 font-medium">网球</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-500">Vol $</span>
                  <input 
                    type="number" min="0" value={settings.tennisVol}
                    onChange={(e) => setSettings({...settings, tennisVol: parseInt(e.target.value) || 0})}
                    className="w-18 bg-gray-50 border border-gray-200 rounded px-2 py-0.5 text-xs text-gray-900 focus:outline-none focus:border-[#10b981]"
                  />
                  <span className="text-xs text-gray-500">K</span>
                </div>
              </div>
            </div>
          </div>
          
          <button
            onClick={() => {
              void updateCollectorSettings({
                collection_interval_minutes: settings.collectionInterval,
                football_volume_threshold_k: settings.footballVol,
                basketball_volume_threshold_k: settings.basketballVol,
              });
              setShowSettings(false);
            }}
            className="w-full mt-4 bg-[#10b981] hover:bg-[#0ea571] text-white text-xs py-2 rounded-md transition-colors cursor-pointer"
          >
            保存设置
          </button>
        </div>
      )}

      {/* Match List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2 bg-gray-50">
        {filteredMatches.length === 0 && (
          <div className="text-center text-gray-400 text-xs pt-8">暂无比赛数据</div>
        )}
        {groupedMatches.live.length > 0 && (
          <>
            <div className="px-1 pt-1 pb-0.5 text-[10px] font-bold text-red-500 uppercase">Live</div>
            {groupedMatches.live.map(match => (
              <MatchItem
                key={match.id}
                match={match}
                isSelected={selectedMatchId === match.id}
                onClick={() => selectMatch(match.id)}
              />
            ))}
          </>
        )}
        {groupedMatches.pre.length > 0 && (
          <>
            <div className="px-1 pt-2 pb-0.5 text-[10px] font-bold text-gray-500 uppercase">Pre</div>
            {groupedMatches.pre.map(match => (
              <MatchItem
                key={match.id}
                match={match}
                isSelected={selectedMatchId === match.id}
                onClick={() => selectMatch(match.id)}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
};

const MatchItem = ({ match, isSelected, onClick }: { match: Match; isSelected: boolean; onClick: () => void }) => {
  const isLive = match.status === 'Live';
  const isFinished = match.status === 'Finished';
  
  const formatWsTime = (date: Date) => {
    const h = date.getHours().toString().padStart(2, '0');
    const m = date.getMinutes().toString().padStart(2, '0');
    const s = date.getSeconds().toString().padStart(2, '0');
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    return `${h}:${m}:${s}.${ms}`;
  };

  // Always show match start time next to sport icon
  const formatStartTime = (date: Date) => {
    const mo = (date.getMonth() + 1).toString().padStart(2, '0');
    const d = date.getDate().toString().padStart(2, '0');
    const h = date.getHours().toString().padStart(2, '0');
    const m = date.getMinutes().toString().padStart(2, '0');
    return `${mo}-${d} ${h}:${m}`;
  };

  const getSportIcon = () => {
    if (match.sport === 'Football') return <div className="w-3.5 h-3.5 flex items-center justify-center text-[11px]">⚽</div>;
    if (match.sport === 'Basketball') return <div className="w-3.5 h-3.5 flex items-center justify-center text-[11px]">🏀</div>;
    return <div className="w-3.5 h-3.5 flex items-center justify-center text-[11px]">🎾</div>;
  };
  
  return (
    <div 
      onClick={onClick}
      className={clsx(
        "rounded-md p-2 border cursor-pointer transition-all relative bg-white text-gray-800",
        isSelected ? "border-[#10b981] shadow-md" : "border-gray-200 hover:border-gray-300"
      )}
    >
      {/* Top Row: Status and Start Time */}
      <div className="flex justify-between items-center mb-1.5">
        <div className="flex items-center gap-1.5">
          {isLive ? (
            <>
              <motion.div 
                animate={{ opacity: [1, 0.2, 1] }} 
                transition={{ repeat: Infinity, duration: 1.5 }}
                className="w-1.5 h-1.5 rounded-full bg-red-500"
              />
              <span className="text-[11px] font-bold text-red-500 tracking-wide leading-none">Live</span>
            </>
          ) : isFinished ? (
            <span className="text-[11px] font-bold text-gray-400 tracking-wide leading-none">End</span>
          ) : (
            <span className="text-[11px] font-bold text-gray-500 tracking-wide leading-none">PRE</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-[#10b981] font-medium text-[11px] [&_svg]:stroke-none [&_svg]:fill-current">
          {getSportIcon()}
          <span>{formatStartTime(match.startTime)}</span>
        </div>
      </div>

      {/* Middle Row: Teams and Score */}
      <div className="flex justify-between items-center mb-1.5 px-1">
        <div className="flex-1 text-sm font-bold text-gray-900 truncate leading-tight">
          {match.teamA.shortName}
        </div>
        <div className="px-3 text-sm font-bold flex items-center gap-1.5">
          <span className="text-gray-700">{match.scoreA}</span>
          <span className="text-gray-400">-</span>
          <span className="text-gray-700">{match.scoreB}</span>
        </div>
        <div className="flex-1 text-sm font-bold text-gray-900 truncate text-right leading-tight">
          {match.teamB.shortName}
        </div>
      </div>

      {/* Bottom Row: Probabilities */}
      <div className="flex justify-between items-center gap-1.5 mb-1.5">
        <div className="flex-1 text-center bg-gray-50 border border-gray-200 rounded-md py-0.5">
          <span className="text-blue-500 font-medium text-xs leading-none">{(match.marketA.bid * 100).toFixed(0)}%</span>
        </div>
        {match.marketDraw && (
          <div className="flex-1 text-center bg-gray-50 border border-gray-200 rounded-md py-0.5">
            <span className="text-gray-600 font-medium text-xs leading-none">{(match.marketDraw.bid * 100).toFixed(0)}%</span>
          </div>
        )}
        <div className="flex-1 text-center bg-gray-50 border border-gray-200 rounded-md py-0.5">
          <span className="text-orange-500 font-medium text-xs leading-none">{(match.marketB.bid * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Footer: Volume and Time */}
      <div className="flex justify-between items-center text-[10px] text-gray-400 leading-none">
        <span><span className="text-gray-300">ML:</span>${(match.volume / 1000).toFixed(2)}k <span className="text-gray-300 mx-0.5">/</span> ${(match.volume * 3.8 / 1000).toFixed(2)}k</span>
        <span className="font-mono">{formatWsTime(match.wsTime)}</span>
      </div>
    </div>
  );
};
