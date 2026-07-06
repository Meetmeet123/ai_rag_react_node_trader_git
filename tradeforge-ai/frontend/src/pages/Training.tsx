import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Cpu,
  Play,
  Square,
  RotateCcw,
  Zap,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Database,
  Loader2,
  PlayCircle,
  PauseCircle,
  ArrowLeftRight,
  Box,
} from 'lucide-react';
import {
  fetchTrainingStatus,
  fetchTrainingJobs,
  fetchModelVersions,
  triggerTraining,
  startAutoTraining,
  stopAutoTraining,
  rollbackModel,
  activateModelVersion,
  archiveModelVersion,
} from '@/lib/api';
import type { TrainingStatusResponse, TrainingJob, ModelVersion } from '@/types/api';

interface StatusCardProps {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  subtext?: string;
  accent?: 'cyan' | 'green' | 'red' | 'amber' | 'slate';
}

const accentMap = {
  cyan: 'text-[#22D3EE] bg-[rgba(34,211,238,0.12)]',
  green: 'text-[#10B981] bg-[rgba(16,185,129,0.12)]',
  red: 'text-[#EF4444] bg-[rgba(239,68,68,0.12)]',
  amber: 'text-[#F59E0B] bg-[rgba(245,158,11,0.12)]',
  slate: 'text-[#94A3B8] bg-[#1A1A25]',
};

function StatusCard({ icon: Icon, label, value, subtext, accent = 'slate' }: StatusCardProps) {
  return (
    <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-4">
      <div className="flex items-start justify-between">
        <div className={`w-8 h-8 rounded-[6px] flex items-center justify-center ${accentMap[accent]}`}>
          <Icon size={18} />
        </div>
        {subtext && (
          <span className="text-[11px] text-[#64748B]">{subtext}</span>
        )}
      </div>
      <div className="mt-3">
        <div className="text-[13px] text-[#64748B] font-medium">{label}</div>
        <div className="text-[18px] font-semibold text-[#F1F5F9] mt-0.5 truncate">{value}</div>
      </div>
    </div>
  );
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatNumber(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPnl(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const prefix = value >= 0 ? '+' : '';
  return `${prefix}₹${Math.abs(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getJobStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
      return 'text-[#10B981] bg-[rgba(16,185,129,0.15)]';
    case 'running':
      return 'text-[#22D3EE] bg-[rgba(34,211,238,0.15)]';
    case 'failed':
      return 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]';
    case 'pending':
      return 'text-[#F59E0B] bg-[rgba(245,158,11,0.15)]';
    default:
      return 'text-[#64748B] bg-[#06060A]';
  }
}

function getModelStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'active':
      return 'text-[#10B981] bg-[rgba(16,185,129,0.15)]';
    case 'archived':
      return 'text-[#64748B] bg-[#06060A]';
    case 'failed':
      return 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]';
    case 'pending':
      return 'text-[#F59E0B] bg-[rgba(245,158,11,0.15)]';
    default:
      return 'text-[#94A3B8] bg-[#1A1A25]';
  }
}

export default function Training() {
  const [status, setStatus] = useState<TrainingStatusResponse | null>(null);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  const setAction = (key: string, value: boolean) => {
    setActionLoading((prev) => ({ ...prev, [key]: value }));
  };

  const loadAll = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [statusRes, jobsRes, modelsRes] = await Promise.all([
        fetchTrainingStatus(),
        fetchTrainingJobs(50),
        fetchModelVersions(),
      ]);
      setStatus(statusRes);
      setJobs(jobsRes.jobs ?? []);
      setModels(modelsRes.versions ?? []);
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to load training data';
      setError(message);
      if (!silent) toast.error(message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const interval = setInterval(() => loadAll({ silent: true }), 5000);
    return () => clearInterval(interval);
  }, [loadAll]);

  const handleTriggerTraining = async () => {
    setAction('trigger', true);
    try {
      const res = await triggerTraining();
      toast.success(res.message || 'Training triggered');
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to trigger training';
      toast.error(message);
    } finally {
      setAction('trigger', false);
    }
  };

  const handleStartAuto = async () => {
    setAction('startAuto', true);
    try {
      const res = await startAutoTraining();
      toast.success(res.message || 'Auto-training started');
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to start auto-training';
      toast.error(message);
    } finally {
      setAction('startAuto', false);
    }
  };

  const handleStopAuto = async () => {
    setAction('stopAuto', true);
    try {
      const res = await stopAutoTraining();
      toast.success(res.message || 'Auto-training stopped');
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to stop auto-training';
      toast.error(message);
    } finally {
      setAction('stopAuto', false);
    }
  };

  const handleRollback = async () => {
    setAction('rollback', true);
    try {
      const res = await rollbackModel();
      toast.success(
        res.message ||
          (res.new_active_version ? `Rolled back to ${res.new_active_version}` : 'Rollback complete'),
      );
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to rollback model';
      toast.error(message);
    } finally {
      setAction('rollback', false);
    }
  };

  const handleActivate = async (id: string) => {
    setAction(`activate-${id}`, true);
    try {
      const res = await activateModelVersion(id);
      toast.success(res.message || `Activated ${res.activated_version || id}`);
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to activate model version';
      toast.error(message);
    } finally {
      setAction(`activate-${id}`, false);
    }
  };

  const handleArchive = async (id: string) => {
    setAction(`archive-${id}`, true);
    try {
      const res = await archiveModelVersion(id);
      if (res.success) {
        toast.success(res.message || 'Model archived');
      } else {
        toast.info(res.message || 'Archive not available');
      }
      loadAll({ silent: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to archive model version';
      toast.error(message);
    } finally {
      setAction(`archive-${id}`, false);
    }
  };

  const isAutoRunning = status?.is_running ?? false;
  const currentJobId = status?.current_job_id;
  const activeModelName = status?.active_model_name ?? status?.active_model_version_id ?? '—';

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-bold text-[#F1F5F9]">Training & Models</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">
            Manage model training jobs, registry versions, and auto-training schedules.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleTriggerTraining}
            disabled={actionLoading['trigger']}
            className="h-8 px-3 flex items-center gap-1.5 bg-[#22D3EE] text-[#030305] text-[12px] font-semibold rounded-[6px] hover:brightness-110 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {actionLoading['trigger'] ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            Trigger Training Now
          </button>
          <button
            onClick={handleStartAuto}
            disabled={actionLoading['startAuto'] || isAutoRunning}
            className="h-8 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[12px] font-medium rounded-[6px] hover:bg-[#1A1A25] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {actionLoading['startAuto'] ? <Loader2 size={14} className="animate-spin" /> : <PlayCircle size={14} />}
            Start Auto-Training
          </button>
          <button
            onClick={handleStopAuto}
            disabled={actionLoading['stopAuto'] || !isAutoRunning}
            className="h-8 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[12px] font-medium rounded-[6px] hover:bg-[#1A1A25] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {actionLoading['stopAuto'] ? <Loader2 size={14} className="animate-spin" /> : <PauseCircle size={14} />}
            Stop Auto-Training
          </button>
          <button
            onClick={handleRollback}
            disabled={actionLoading['rollback']}
            className="h-8 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[12px] font-medium rounded-[6px] hover:bg-[#1A1A25] transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {actionLoading['rollback'] ? <Loader2 size={14} className="animate-spin" /> : <ArrowLeftRight size={14} />}
            Rollback to Previous
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[rgba(239,68,68,0.10)] border border-[rgba(239,68,68,0.20)] rounded-[8px] text-[13px] text-[#EF4444]">
          <AlertTriangle size={16} />
          {error}
        </div>
      )}

      {/* Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatusCard
          icon={Activity}
          label="Auto-Training"
          value={isAutoRunning ? 'Running' : 'Stopped'}
          subtext={status ? `Interval: ${status.interval_minutes}m` : undefined}
          accent={isAutoRunning ? 'green' : 'slate'}
        />
        <StatusCard
          icon={Cpu}
          label="Current Job"
          value={currentJobId ? `${currentJobId.slice(0, 12)}…` : 'Idle'}
          subtext={currentJobId ? 'Active' : 'No job running'}
          accent={currentJobId ? 'cyan' : 'slate'}
        />
        <StatusCard
          icon={Box}
          label="Active Model"
          value={activeModelName}
          subtext={status?.active_model_version_id ? status.active_model_version_id.slice(0, 12) : undefined}
          accent={status?.active_model_version_id ? 'green' : 'slate'}
        />
        <StatusCard
          icon={Clock}
          label="Next Scheduled Run"
          value={formatDateTime(status?.next_scheduled_run)}
          accent="cyan"
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] flex items-center justify-center text-[#10B981] bg-[rgba(16,185,129,0.12)]">
            <CheckCircle size={16} />
          </div>
          <div>
            <div className="text-[11px] text-[#64748B]">Completed Jobs</div>
            <div className="text-[16px] font-semibold text-[#F1F5F9]">
              {status?.total_jobs_completed ?? '—'}
            </div>
          </div>
        </div>
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] flex items-center justify-center text-[#EF4444] bg-[rgba(239,68,68,0.12)]">
            <XCircle size={16} />
          </div>
          <div>
            <div className="text-[11px] text-[#64748B]">Failed Jobs</div>
            <div className="text-[16px] font-semibold text-[#F1F5F9]">
              {status?.total_jobs_failed ?? '—'}
            </div>
          </div>
        </div>
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-[6px] flex items-center justify-center text-[#F59E0B] bg-[rgba(245,158,11,0.12)]">
            <AlertTriangle size={16} />
          </div>
          <div>
            <div className="text-[11px] text-[#64748B]">Consecutive Failures</div>
            <div className="text-[16px] font-semibold text-[#F1F5F9]">
              {status?.consecutive_failures ?? '—'}
            </div>
          </div>
        </div>
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-3 flex items-center gap-3">
          <div
            className={`w-8 h-8 rounded-[6px] flex items-center justify-center ${
              status?.circuit_breaker_open
                ? 'text-[#EF4444] bg-[rgba(239,68,68,0.12)]'
                : 'text-[#10B981] bg-[rgba(16,185,129,0.12)]'
            }`}
          >
            <Zap size={16} />
          </div>
          <div>
            <div className="text-[11px] text-[#64748B]">Circuit Breaker</div>
            <div className={`text-[16px] font-semibold ${status?.circuit_breaker_open ? 'text-[#EF4444]' : 'text-[#10B981]'}`}>
              {status?.circuit_breaker_open ? 'Open' : 'Closed'}
            </div>
          </div>
        </div>
      </div>

      {/* Model Versions Table */}
      <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
        <div className="h-10 flex items-center justify-between px-4 border-b border-[rgba(255,255,255,0.06)]">
          <div className="flex items-center gap-2">
            <Database size={14} className="text-[#22D3EE]" />
            <span className="text-[15px] font-semibold text-[#F1F5F9]">Model Versions</span>
            <span className="text-[11px] text-[#64748B]">{models.length} versions</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          {loading && models.length === 0 ? (
            <div className="p-8 flex items-center justify-center text-[#64748B]">
              <Loader2 size={18} className="animate-spin mr-2" />
              Loading model versions…
            </div>
          ) : models.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-[#64748B]">
              No model versions found.
            </div>
          ) : (
            <table className="w-full">
              <thead className="sticky top-0 bg-[#06060A]">
                <tr>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Version</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Status</th>
                  <th className="text-center px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Active</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Epochs</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Final Loss</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Backtest PnL</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">F1</th>
                  <th className="text-center px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <tr
                    key={model.version_id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="text-[13px] font-medium text-[#F1F5F9]">
                          {model.version_name}
                        </span>
                        <span className="text-[10px] font-mono text-[#64748B]">{model.version_id.slice(0, 12)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span
                        className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${getModelStatusColor(
                          model.status,
                        )}`}
                      >
                        {model.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-center whitespace-nowrap">
                      {model.is_active ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10B981]">
                          <CheckCircle size={12} /> Active
                        </span>
                      ) : (
                        <span className="text-[11px] text-[#64748B]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {model.epochs ?? '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {formatNumber(model.final_loss)}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right text-[12px] font-mono font-medium whitespace-nowrap ${
                        model.backtest_pnl === null || model.backtest_pnl === undefined
                          ? 'text-[#94A3B8]'
                          : model.backtest_pnl >= 0
                            ? 'text-[#10B981]'
                            : 'text-[#EF4444]'
                      }`}
                    >
                      {formatPnl(model.backtest_pnl)}
                    </td>
                    <td className="px-4 py-2.5 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {formatNumber(model.f1_score)}
                    </td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => handleActivate(model.version_id)}
                          disabled={model.is_active || actionLoading[`activate-${model.version_id}`]}
                          className="h-7 px-2 flex items-center gap-1 rounded-[4px] text-[11px] font-medium text-[#22D3EE] bg-[rgba(34,211,238,0.10)] hover:bg-[rgba(34,211,238,0.18)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {actionLoading[`activate-${model.version_id}`] ? (
                            <Loader2 size={11} className="animate-spin" />
                          ) : (
                            <Play size={11} />
                          )}
                          Activate
                        </button>
                        <button
                          onClick={() => handleArchive(model.version_id)}
                          disabled={actionLoading[`archive-${model.version_id}`]}
                          className="h-7 px-2 flex items-center gap-1 rounded-[4px] text-[11px] font-medium text-[#64748B] bg-[#1A1A25] hover:bg-[rgba(239,68,68,0.15)] hover:text-[#EF4444] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {actionLoading[`archive-${model.version_id}`] ? (
                            <Loader2 size={11} className="animate-spin" />
                          ) : (
                            <Square size={11} />
                          )}
                          Archive
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Training Jobs Section */}
      <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
        <div className="h-10 flex items-center justify-between px-4 border-b border-[rgba(255,255,255,0.06)]">
          <div className="flex items-center gap-2">
            <RotateCcw size={14} className="text-[#22D3EE]" />
            <span className="text-[15px] font-semibold text-[#F1F5F9]">Training Jobs</span>
            <span className="text-[11px] text-[#64748B]">{jobs.length} jobs</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          {loading && jobs.length === 0 ? (
            <div className="p-8 flex items-center justify-center text-[#64748B]">
              <Loader2 size={18} className="animate-spin mr-2" />
              Loading training jobs…
            </div>
          ) : jobs.length === 0 ? (
            <div className="p-8 text-center text-[13px] text-[#64748B]">
              No training jobs found.
            </div>
          ) : (
            <table className="w-full">
              <thead className="sticky top-0 bg-[#06060A]">
                <tr>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Job ID</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Status</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Trigger</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Samples</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Epochs</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Loss</th>
                  <th className="text-center px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Deployed</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#64748B] whitespace-nowrap">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.job_id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <td className="px-4 py-2 whitespace-nowrap">
                      <span className="text-[12px] font-mono text-[#F1F5F9]">{job.job_id.slice(0, 16)}</span>
                    </td>
                    <td className="px-4 py-2 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${getJobStatusColor(
                          job.status,
                        )}`}
                      >
                        {job.status.toLowerCase() === 'running' && (
                          <Loader2 size={10} className="animate-spin" />
                        )}
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-[12px] text-[#94A3B8] whitespace-nowrap">
                      {job.trigger_reason || '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {job.sample_count ?? '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {job.epochs ?? '—'}
                    </td>
                    <td className="px-4 py-2 text-right text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {formatNumber(job.final_loss)}
                    </td>
                    <td className="px-4 py-2 text-center whitespace-nowrap">
                      {job.deployed ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#10B981]">
                          <CheckCircle size={12} /> Yes
                        </span>
                      ) : (
                        <span className="text-[11px] text-[#64748B]">No</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-[12px] font-mono text-[#94A3B8] whitespace-nowrap">
                      {formatDateTime(job.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
