import { GitBranch, Settings, Play, BarChart3, Check } from 'lucide-react';
import type { BacktestStep } from './types';

interface StepDef {
  key: BacktestStep;
  label: string;
  icon: typeof GitBranch;
}

const STEPS: StepDef[] = [
  { key: 1, label: 'Select', icon: GitBranch },
  { key: 2, label: 'Configure', icon: Settings },
  { key: 3, label: 'Run', icon: Play },
  { key: 4, label: 'Results', icon: BarChart3 },
];

interface BacktestWizardProps {
  currentStep: BacktestStep;
}

export default function BacktestWizard({ currentStep }: BacktestWizardProps) {
  return (
    <div className="h-14 shrink-0 bg-[#06060A] border-b border-[rgba(255,255,255,0.06)] flex items-center justify-center px-4">
      <div className="flex items-center gap-0">
        {STEPS.map((step, index) => {
          const isCompleted = currentStep > step.key;
          const isActive = currentStep === step.key;
          const Icon = step.icon;

          return (
            <div key={step.key} className="flex items-center">
              {/* Connector */}
              {index > 0 && (
                <div className="w-10 h-[2px] mx-1">
                  <div
                    className={`h-full transition-all duration-300 ${
                      isCompleted ? 'bg-[#10B981]' : 'bg-[rgba(255,255,255,0.06)]'
                    }`}
                  />
                </div>
              )}

              {/* Step */}
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center border-2 transition-all duration-200 ${
                    isCompleted
                      ? 'bg-[#10B981] border-[#10B981]'
                      : isActive
                      ? 'border-[#22D3EE] text-[#22D3EE] shadow-[0_0_8px_rgba(34,211,238,0.20)]'
                      : 'border-[rgba(255,255,255,0.10)] text-[#475569]'
                  }`}
                >
                  {isCompleted ? (
                    <Check size={14} className="text-white" />
                  ) : (
                    <Icon size={12} />
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium transition-colors ${
                    isCompleted
                      ? 'text-[#10B981]'
                      : isActive
                      ? 'text-[#22D3EE]'
                      : 'text-[#475569]'
                  }`}
                >
                  {step.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
