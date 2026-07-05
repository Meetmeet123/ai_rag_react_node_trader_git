import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import StrategyListPanel from './strategies/StrategyListPanel';
import StrategyToolbar from './strategies/StrategyToolbar';
import StrategyEditor from './strategies/StrategyEditor';
import { MOCK_STRATEGIES } from './strategies/mockData';
import type { SavedStrategy } from './strategies/types';

export default function Strategies() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<SavedStrategy[]>(MOCK_STRATEGIES);
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_STRATEGIES[0]?.id ?? null);

  const selectedStrategy = strategies.find((s) => s.id === selectedId) ?? null;

  const handleSelect = useCallback((strategy: SavedStrategy) => {
    setSelectedId(strategy.id);
  }, []);

  const handleNew = useCallback(() => {
    const newStrategy: SavedStrategy = {
      id: `new_${Date.now()}`,
      name: 'Untitled Strategy',
      description: '',
      instrument: 'NIFTY 50',
      segment: 'Stocks',
      status: 'draft',
      lastModified: 'Just now',
      entryConditions: [],
      exitConditions: [],
      stopLoss: { type: 'fixed', value: 1.0 },
      target: { type: 'fixed', value: 2.0 },
      positionSizing: { type: 'percent', value: 10 },
      timeframe: '1D',
    };
    setStrategies((prev) => [newStrategy, ...prev]);
    setSelectedId(newStrategy.id);
  }, []);

  const handleUpdate = useCallback((updated: SavedStrategy) => {
    setStrategies((prev) =>
      prev.map((s) => (s.id === updated.id ? { ...updated, lastModified: 'Just now' } : s))
    );
  }, []);

  const handleSave = useCallback(() => {
    if (!selectedStrategy) return;
    setStrategies((prev) =>
      prev.map((s) =>
        s.id === selectedStrategy.id ? { ...s, status: 'active' as const, lastModified: 'Just now' } : s
      )
    );
  }, [selectedStrategy]);

  const handleDuplicate = useCallback(() => {
    if (!selectedStrategy) return;
    const dup: SavedStrategy = {
      ...selectedStrategy,
      id: `dup_${Date.now()}`,
      name: `${selectedStrategy.name} (Copy)`,
      status: 'draft',
      lastModified: 'Just now',
    };
    setStrategies((prev) => [dup, ...prev]);
    setSelectedId(dup.id);
  }, [selectedStrategy]);

  const handleDelete = useCallback(() => {
    if (!selectedStrategy) return;
    setStrategies((prev) => prev.filter((s) => s.id !== selectedStrategy.id));
    setSelectedId(null);
  }, [selectedStrategy]);

  const handleBacktest = useCallback(() => {
    if (!selectedStrategy) return;
    navigate('/app/backtest');
  }, [navigate, selectedStrategy]);

  const handlePaperTrade = useCallback(() => {
    if (!selectedStrategy) return;
    setStrategies((prev) =>
      prev.map((s) =>
        s.id === selectedStrategy.id ? { ...s, status: 'paper' as const, lastModified: 'Just now' } : s
      )
    );
  }, [selectedStrategy]);

  const handleDeploy = useCallback(() => {
    if (!selectedStrategy) return;
    setStrategies((prev) =>
      prev.map((s) =>
        s.id === selectedStrategy.id ? { ...s, status: 'active' as const, lastModified: 'Just now' } : s
      )
    );
  }, [selectedStrategy]);

  return (
    <div className="flex flex-col h-full -m-4 md:-m-6">
      {/* Toolbar */}
      <StrategyToolbar
        strategy={selectedStrategy}
        onSave={handleSave}
        onDuplicate={handleDuplicate}
        onDelete={handleDelete}
        onBacktest={handleBacktest}
        onPaperTrade={handlePaperTrade}
        onDeploy={handleDeploy}
        onNameChange={(name) => selectedStrategy && handleUpdate({ ...selectedStrategy, name })}
        onSegmentChange={(segment) => selectedStrategy && handleUpdate({ ...selectedStrategy, segment })}
      />

      {/* Main workspace */}
      <div className="flex flex-1 overflow-hidden">
        {/* Strategy list sidebar */}
        <StrategyListPanel
          strategies={strategies}
          selectedId={selectedId}
          onSelect={handleSelect}
          onNew={handleNew}
        />

        {/* Strategy editor */}
        <div className="flex-1 flex overflow-hidden">
          <StrategyEditor strategy={selectedStrategy} onUpdate={handleUpdate} />
        </div>
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="h-7 shrink-0 bg-[#06060A] border-t border-[rgba(255,255,255,0.06)] flex items-center justify-center px-4">
        <span className="text-[11px] text-[#475569]">
          Ctrl+S: Save &nbsp;|&nbsp; Ctrl+B: Backtest &nbsp;|&nbsp; Delete: Remove &nbsp;|&nbsp; Drag: Reorder
        </span>
      </div>
    </div>
  );
}
