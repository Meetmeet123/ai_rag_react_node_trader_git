import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { toast } from 'sonner';
import BacktestWizard from './backtest/BacktestWizard';
import Step1_StrategySelect from './backtest/Step1_StrategySelect';
import Step2_Parameters from './backtest/Step2_Parameters';
import Step3_Running from './backtest/Step3_Running';
import Step4_Results from './backtest/Step4_Results';

import type { BacktestStep, BacktestConfig, BacktestResult } from './backtest/types';
import type { Strategy } from '@/types/api';
import { DEFAULT_CONFIG } from './backtest/mockData';
import {
  fetchStrategies,
  fetchStrategy,
  runBacktest,
} from '@/lib/api';


export default function Backtest() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState<BacktestStep>(1);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [config, setConfig] = useState<BacktestConfig>(DEFAULT_CONFIG);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [strategiesError, setStrategiesError] = useState<string | null>(null);
  const [backtestId, setBacktestId] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const strategyIdFromQuery = searchParams.get('strategyId');

  // Load strategies on mount
  useEffect(() => {
    let mounted = true;
    setStrategiesLoading(true);
    fetchStrategies()
      .then((res) => {
        if (!mounted) return;
        setStrategies(res.strategies);
        setStrategiesError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        const message = err?.detail ? String(err.detail) : 'Failed to load strategies';
        setStrategiesError(message);
        toast.error(message);
      })
      .finally(() => {
        if (mounted) setStrategiesLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Pre-select strategy from query param
  useEffect(() => {
    if (!strategyIdFromQuery || strategies.length === 0) return;
    const strategy = strategies.find((s) => s.id === strategyIdFromQuery);
    if (strategy) {
      setSelectedStrategyId(strategy.id);
      setConfig((prev) => ({
        ...prev,
        strategyId: strategy.id,
        symbol: strategy.instrument,
        segment: strategy.segment || 'Stocks',
        timeframe: strategy.timeframe || '1D',
      }));
      setStep(2);
    }
  }, [strategyIdFromQuery, strategies]);

  const handleSelectStrategy = useCallback(async (id: string) => {
    setSelectedStrategyId(id);
    try {
      const strategy = await fetchStrategy(id);
      setConfig((prev) => ({
        ...prev,
        strategyId: strategy.id,
        symbol: strategy.instrument,
        segment: strategy.segment || 'Stocks',
        timeframe: strategy.timeframe || '1D',
      }));
      setStep(2);
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err
        ? String((err as { detail: string }).detail)
        : 'Failed to load strategy';
      toast.error(message);
    }
  }, []);

  const handleNewStrategy = useCallback(() => {
    navigate('/app/strategies');
  }, [navigate]);

  const handleRun = useCallback(async () => {
    if (!selectedStrategyId) {
      toast.error('Please select a strategy first');
      return;
    }
    setRunError(null);
    setResult(null);
    try {
      const payload = {
        strategy_id: selectedStrategyId,
        start_date: new Date(config.startDate).toISOString(),
        end_date: new Date(config.endDate).toISOString(),
        initial_capital: config.initialCapital,
        brokerage_per_order: config.brokerage,
        slippage_pct: config.slippage,
        position_sizing_type:
          config.positionSizing === 'fixed'
            ? 'fixed_qty'
            : config.positionSizing === 'risk'
              ? 'risk_based'
              : 'pct_capital',
        position_sizing_value: config.lotSize || 1,
        stop_loss_type: config.stopLossType === 'fixed' ? 'fixed_pct' : config.stopLossType === 'atr' ? 'atr' : 'fixed_pct',
        stop_loss_value: config.stopLossValue,
        target_type: config.targetType === 'fixed' ? 'fixed_pct' : config.targetType === 'rr' ? 'rr_based' : 'atr',
        target_value: config.targetValue,
        allow_short: true,
      };
      const run = await runBacktest(payload);
      setBacktestId(run.id);
      setStep(3);
    } catch (err) {
      const message = err && typeof err === 'object' && 'detail' in err
        ? String((err as { detail: string }).detail)
        : 'Failed to start backtest';
      setRunError(message);
      toast.error(message);
    }
  }, [selectedStrategyId, config]);

  const handleComplete = useCallback((btResult: BacktestResult) => {
    setResult(btResult);
    setStep(4);
  }, []);

  const handleBack = useCallback(() => {
    if (step === 4) {
      setStep(2);
    } else {
      setStep(Math.max(1, step - 1) as BacktestStep);
    }
  }, [step]);

  const handlePaperTrade = useCallback(() => {
    navigate('/app/paper');
  }, [navigate]);

  return (
    <div className="flex flex-col h-full -m-4 md:-m-6">
      {/* Stepper */}
      <BacktestWizard currentStep={step} />

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {step === 1 && (
          <Step1_StrategySelect
            strategies={strategies}
            isLoading={strategiesLoading}
            error={strategiesError}
            selectedId={selectedStrategyId}
            onSelect={handleSelectStrategy}
            onNew={handleNewStrategy}
          />
        )}

        {step === 2 && (
          <Step2_Parameters
            config={config}
            onChange={setConfig}
            onRun={handleRun}
            error={runError}
          />
        )}

        {step === 3 && backtestId && (
          <Step3_Running
            backtestId={backtestId}
            onComplete={handleComplete}
            onError={setRunError}
            symbol={config.symbol}
            startDate={config.startDate}
            endDate={config.endDate}
          />
        )}

        {step === 4 && result && (
          <Step4_Results
            result={result}
            onBack={handleBack}
            onPaperTrade={handlePaperTrade}
          />
        )}
      </div>
    </div>
  );
}
