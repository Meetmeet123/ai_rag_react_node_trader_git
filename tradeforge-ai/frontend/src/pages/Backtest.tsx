import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import BacktestWizard from './backtest/BacktestWizard';
import Step1_StrategySelect from './backtest/Step1_StrategySelect';
import Step2_Parameters from './backtest/Step2_Parameters';
import Step3_Running from './backtest/Step3_Running';
import Step4_Results from './backtest/Step4_Results';
import type { BacktestStep, BacktestConfig } from './backtest/types';
import { DEFAULT_CONFIG, MOCK_RESULT } from './backtest/mockData';

export default function Backtest() {
  const navigate = useNavigate();
  const [step, setStep] = useState<BacktestStep>(1);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [config, setConfig] = useState<BacktestConfig>(DEFAULT_CONFIG);

  const handleSelectStrategy = useCallback((id: string) => {
    setSelectedStrategyId(id);
    setConfig((prev) => ({ ...prev, strategyId: id }));
    setStep(2);
  }, []);

  const handleNewStrategy = useCallback(() => {
    navigate('/app/strategies');
  }, [navigate]);

  const handleRun = useCallback(() => {
    setStep(3);
  }, []);

  const handleComplete = useCallback(() => {
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
          />
        )}

        {step === 3 && (
          <Step3_Running
            onComplete={handleComplete}
            symbol={config.symbol}
            startDate={config.startDate}
            endDate={config.endDate}
          />
        )}

        {step === 4 && (
          <Step4_Results
            result={MOCK_RESULT}
            onBack={handleBack}
            onPaperTrade={handlePaperTrade}
          />
        )}
      </div>
    </div>
  );
}
