import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import StrategyListPanel from './strategies/StrategyListPanel';
import StrategyToolbar from './strategies/StrategyToolbar';
import StrategyEditor from './strategies/StrategyEditor';
import { apiToSaved, savedToApiRequest } from './strategies/adapter';
import type { SavedStrategy } from './strategies/types';
import {
  createStrategy,
  deleteStrategy,
  deployStrategy,
  duplicateStrategy,
  fetchStrategies,
  stopStrategy,
  updateStrategy,
} from '@/lib/api';

export default function Strategies() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<SavedStrategy[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedStrategy = strategies.find((s) => s.id === selectedId) ?? null;

  const loadStrategies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetchStrategies();
      const mapped = response.strategies.map(apiToSaved);
      setStrategies(mapped);
      if (mapped.length > 0 && !selectedId) {
        setSelectedId(mapped[0].id);
      }
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to load strategies';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    loadStrategies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelect = useCallback((strategy: SavedStrategy) => {
    setSelectedId(strategy.id);
  }, []);

  const handleNew = useCallback(async () => {
    try {
      const apiStrategy = await createStrategy({
        name: 'Untitled Strategy',
        instrument: 'NIFTY50',
        segment: 'equity',
        timeframe: '1D',
      });
      const saved = apiToSaved(apiStrategy);
      setStrategies((prev) => [saved, ...prev]);
      setSelectedId(saved.id);
      toast.success('New strategy created');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to create strategy';
      toast.error(message);
    }
  }, []);

  const persistUpdate = useCallback(
    async (updated: SavedStrategy) => {
      try {
        const apiStrategy = await updateStrategy(updated.id, savedToApiRequest(updated));
        const saved = apiToSaved(apiStrategy);
        setStrategies((prev) => prev.map((s) => (s.id === saved.id ? saved : s)));
      } catch (err) {
        const message =
          err && typeof err === 'object' && 'detail' in err
            ? String((err as { detail: string }).detail)
            : 'Failed to update strategy';
        toast.error(message);
      }
    },
    [],
  );

  const handleUpdate = useCallback(
    (updated: SavedStrategy) => {
      setStrategies((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...updated, lastModified: 'Just now' } : s))
      );
      // Debounce or auto-save could go here; for now we save on explicit Save
    },
    [],
  );

  const handleSave = useCallback(async () => {
    if (!selectedStrategy) return;
    await persistUpdate(selectedStrategy);
    toast.success('Strategy saved');
  }, [selectedStrategy, persistUpdate]);

  const handleDuplicate = useCallback(async () => {
    if (!selectedStrategy) return;
    try {
      const apiStrategy = await duplicateStrategy(selectedStrategy.id);
      const saved = apiToSaved(apiStrategy);
      setStrategies((prev) => [saved, ...prev]);
      setSelectedId(saved.id);
      toast.success('Strategy duplicated');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to duplicate strategy';
      toast.error(message);
    }
  }, [selectedStrategy]);

  const handleDelete = useCallback(async () => {
    if (!selectedStrategy) return;
    try {
      await deleteStrategy(selectedStrategy.id);
      setStrategies((prev) => prev.filter((s) => s.id !== selectedStrategy.id));
      setSelectedId(null);
      toast.success('Strategy deleted');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to delete strategy';
      toast.error(message);
    }
  }, [selectedStrategy]);

  const handleBacktest = useCallback(() => {
    if (!selectedStrategy) return;
    navigate('/app/backtest');
  }, [navigate, selectedStrategy]);

  const handlePaperTrade = useCallback(async () => {
    if (!selectedStrategy) return;
    try {
      await deployStrategy(selectedStrategy.id, 'paper');
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'paper' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy deployed to paper trading');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to deploy strategy';
      toast.error(message);
    }
  }, [selectedStrategy]);

  const handleDeploy = useCallback(async () => {
    if (!selectedStrategy) return;
    try {
      await deployStrategy(selectedStrategy.id, 'live');
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'active' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy deployed to live trading');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to deploy strategy';
      toast.error(message);
    }
  }, [selectedStrategy]);

  const handleStop = useCallback(async () => {
    if (!selectedStrategy) return;
    try {
      await stopStrategy(selectedStrategy.id);
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'draft' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy stopped');
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to stop strategy';
      toast.error(message);
    }
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
        onStop={handleStop}
        onNameChange={(name) => selectedStrategy && handleUpdate({ ...selectedStrategy, name })}
        onSegmentChange={(segment) => selectedStrategy && handleUpdate({ ...selectedStrategy, segment })}
      />

      {/* Loading / Error states */}
      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-[#22D3EE] border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && !isLoading && (
        <div className="flex-1 flex items-center justify-center text-center px-4">
          <div>
            <p className="text-[#EF4444] text-[14px] mb-2">{error}</p>
            <button
              onClick={loadStrategies}
              className="px-4 py-2 bg-[#12121A] border border-[rgba(255,255,255,0.08)] text-[#F1F5F9] text-[13px] rounded-[4px] hover:bg-[#1A1A25]"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Main workspace */}
      {!isLoading && !error && (
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
      )}

      {/* Keyboard shortcuts hint */}
      <div className="h-7 shrink-0 bg-[#06060A] border-t border-[rgba(255,255,255,0.06)] flex items-center justify-center px-4">
        <span className="text-[11px] text-[#475569]">
          Ctrl+S: Save &nbsp;|&nbsp; Ctrl+B: Backtest &nbsp;|&nbsp; Delete: Remove &nbsp;|&nbsp; Drag: Reorder
        </span>
      </div>
    </div>
  );
}
