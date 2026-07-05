import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import StrategyListPanel from './strategies/StrategyListPanel';
import StrategyToolbar from './strategies/StrategyToolbar';
import StrategyEditor from './strategies/StrategyEditor';
import IndicatorPalette from './strategies/IndicatorPalette';
import { apiToSaved, savedToApiRequest } from './strategies/adapter';
import type { SavedStrategy, Condition } from './strategies/types';
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
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<'entry' | 'exit' | 'risk' | 'params'>('entry');

  const selectedStrategy = strategies.find((s) => s.id === selectedId) ?? null;

  const withActionLoading = (key: string, fn: () => Promise<unknown>) => async () => {
    setActionLoading((prev) => ({ ...prev, [key]: true }));
    try {
      await fn();
    } finally {
      setActionLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

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
    setActiveTab('entry');
  }, []);

  const handleNew = useCallback(async () => {
    try {
      const apiStrategy = await createStrategy({
        name: 'Untitled Strategy',
        instrument: 'NIFTY50',
        segment: 'equity',
        timeframe: '1d',
      });
      const saved = apiToSaved(apiStrategy);
      setStrategies((prev) => [saved, ...prev]);
      setSelectedId(saved.id);
      setActiveTab('entry');
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
        return saved;
      } catch (err) {
        const message =
          err && typeof err === 'object' && 'detail' in err
            ? String((err as { detail: string }).detail)
            : 'Failed to update strategy';
        toast.error(message);
        throw err;
      }
    },
    [],
  );

  const handleUpdate = useCallback(
    (updated: SavedStrategy) => {
      setStrategies((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...updated, lastModified: 'Just now' } : s))
      );
    },
    [],
  );

  const validateStrategy = (strategy: SavedStrategy): string | null => {
    if (!strategy.name.trim()) return 'Strategy name is required';
    if (!strategy.instrument.trim()) return 'Instrument is required';
    if (strategy.stopLoss.value < 0) return 'Stop loss value must be non-negative';
    if (strategy.target.value < 0) return 'Target value must be non-negative';
    if (strategy.positionSizing.value <= 0) return 'Position sizing value must be positive';
    return null;
  };

  const handleSave = useCallback(async () => {
    if (!selectedStrategy) return;
    const validationError = validateStrategy(selectedStrategy);
    if (validationError) {
      toast.error(validationError);
      return;
    }
    await withActionLoading('save', async () => {
      await persistUpdate(selectedStrategy);
      toast.success('Strategy saved');
    })();
  }, [selectedStrategy, persistUpdate]);

  const handleDuplicate = useCallback(async () => {
    if (!selectedStrategy) return;
    await withActionLoading('duplicate', async () => {
      const apiStrategy = await duplicateStrategy(selectedStrategy.id);
      const saved = apiToSaved(apiStrategy);
      setStrategies((prev) => [saved, ...prev]);
      setSelectedId(saved.id);
      toast.success('Strategy duplicated');
    })();
  }, [selectedStrategy]);

  const handleDelete = useCallback(async () => {
    if (!selectedStrategy) return;
    await withActionLoading('delete', async () => {
      await deleteStrategy(selectedStrategy.id);
      setStrategies((prev) => prev.filter((s) => s.id !== selectedStrategy.id));
      setSelectedId(null);
      toast.success('Strategy deleted');
    })();
  }, [selectedStrategy]);

  const handleBacktest = useCallback(() => {
    if (!selectedStrategy) return;
    navigate(`/app/backtest?strategyId=${encodeURIComponent(selectedStrategy.id)}`);
  }, [navigate, selectedStrategy]);

  const handlePaperTrade = useCallback(async () => {
    if (!selectedStrategy) return;
    await withActionLoading('deploy', async () => {
      await deployStrategy(selectedStrategy.id, 'paper');
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'paper' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy deployed to paper trading');
    })();
  }, [selectedStrategy]);

  const handleDeploy = useCallback(async () => {
    if (!selectedStrategy) return;
    await withActionLoading('deploy', async () => {
      await deployStrategy(selectedStrategy.id, 'live');
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'active' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy deployed to live trading');
    })();
  }, [selectedStrategy]);

  const handleStop = useCallback(async () => {
    if (!selectedStrategy) return;
    await withActionLoading('stop', async () => {
      await stopStrategy(selectedStrategy.id);
      setStrategies((prev) =>
        prev.map((s) => (s.id === selectedStrategy.id ? { ...s, status: 'draft' as const, lastModified: 'Just now' } : s))
      );
      toast.success('Strategy stopped');
    })();
  }, [selectedStrategy]);

  const handleIndicatorSelect = useCallback(
    (indicator: { name: string; shortName: string; category: string; description: string; params: { name: string; default: number }[] }) => {
      if (!selectedStrategy) return;
      const params = indicator.params.length > 0 ? `(${indicator.params.map((p) => p.default).join(',')})` : '';
      const newCondition: Condition = {
        id: `c_${Date.now()}`,
        indicator: `${indicator.shortName}${params}`,
        operator: 'crosses_above',
        value: 'Price',
        valueType: 'indicator',
      };
      const field = activeTab === 'exit' ? 'exitConditions' : 'entryConditions';
      const existing = selectedStrategy[field];
      const conditionWithLogic = existing.length > 0 ? { ...newCondition, logic: 'AND' as const } : newCondition;
      handleUpdate({ ...selectedStrategy, [field]: [...existing, conditionWithLogic] });
      toast.info(`Added ${indicator.shortName} to ${field === 'entryConditions' ? 'entry' : 'exit'} rules`);
    },
    [activeTab, selectedStrategy, handleUpdate]
  );

  return (
    <div className="flex flex-col h-full -m-4 md:-m-6">
      {/* Toolbar */}
      <StrategyToolbar
        strategy={selectedStrategy}
        isLoading={actionLoading}
        onSave={handleSave}
        onDuplicate={handleDuplicate}
        onDelete={handleDelete}
        onBacktest={handleBacktest}
        onPaperTrade={handlePaperTrade}
        onDeploy={handleDeploy}
        onStop={handleStop}
        onNameChange={(name) => selectedStrategy && handleUpdate({ ...selectedStrategy, name })}
        onSegmentChange={(segment) => selectedStrategy && handleUpdate({ ...selectedStrategy, segment: segment as SavedStrategy['segment'] })}
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

          {/* Indicator palette */}
          <IndicatorPalette onSelect={handleIndicatorSelect} />

          {/* Strategy editor */}
          <div className="flex-1 flex overflow-hidden">
            <StrategyEditor
              strategy={selectedStrategy}
              onUpdate={handleUpdate}
              activeTab={activeTab}
              onActiveTabChange={setActiveTab}
            />
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
