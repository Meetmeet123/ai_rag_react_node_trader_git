import { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { ShieldAlert, CheckCircle, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { fetchPendingLiveApprovals, approveUserForLive } from '@/lib/api';
import type { User } from '@/types/api';

interface PendingApproval {
  user: User;
  requested_at: string;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function LiveApprovals() {
  const { user } = useAuth();
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const loadApprovals = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await fetchPendingLiveApprovals();
      setApprovals(data ?? []);
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to load approvals';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  const handleApprove = async (userId: string) => {
    setApprovingId(userId);
    try {
      const result = await approveUserForLive(userId);
      toast.success(result.message || 'User approved for live trading');
      await loadApprovals();
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to approve user';
      toast.error(message);
    } finally {
      setApprovingId(null);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4">
        <ShieldAlert className="w-10 h-10 text-[#F59E0B] mb-3" />
        <h2 className="text-[18px] font-semibold text-[#F1F5F9]">Admin Access Required</h2>
        <p className="text-[13px] text-[#64748B] mt-1">
          You must be an admin to review live-trading approval requests.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-[900px] mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-[20px] font-bold text-[#F1F5F9]">Live Trading Approvals</h1>
          <p className="text-[13px] text-[#64748B] mt-0.5">
            Review and approve user requests for real-broker live trading.
          </p>
        </div>
        <button
          onClick={loadApprovals}
          disabled={isLoading}
          className="h-8 px-3 flex items-center gap-1.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#F1F5F9] text-[12px] font-medium rounded-[6px] hover:bg-[#1A1A25] transition-all disabled:opacity-60"
        >
          {isLoading ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
          Refresh
        </button>
      </div>

      {isLoading && approvals.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-[#64748B]">
          <Loader2 size={20} className="animate-spin mr-2" />
          Loading approval requests…
        </div>
      ) : approvals.length === 0 ? (
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-8 text-center">
          <ShieldAlert className="w-8 h-8 text-[#64748B] mx-auto mb-2" />
          <p className="text-[14px] text-[#94A3B8]">No pending live-trading approvals.</p>
        </div>
      ) : (
        <div className="bg-[#0D0D14] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[#06060A]">
              <tr>
                <th className="text-left px-4 py-2.5 text-[11px] font-medium text-[#64748B]">User</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-medium text-[#64748B]">Email</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-medium text-[#64748B]">Requested At</th>
                <th className="text-right px-4 py-2.5 text-[11px] font-medium text-[#64748B]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {approvals.map(({ user: pendingUser, requested_at }) => (
                <tr
                  key={pendingUser.id}
                  className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                >
                  <td className="px-4 py-3 text-[13px] font-medium text-[#F1F5F9]">{pendingUser.username}</td>
                  <td className="px-4 py-3 text-[12px] text-[#94A3B8]">{pendingUser.email}</td>
                  <td className="px-4 py-3 text-[12px] font-mono text-[#94A3B8]">{formatDate(requested_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      data-testid={`approve-${pendingUser.id}`}
                      onClick={() => handleApprove(pendingUser.id)}
                      disabled={approvingId === pendingUser.id}
                      className="h-7 px-2.5 flex items-center gap-1.5 ml-auto rounded-[4px] text-[11px] font-medium text-[#10B981] bg-[rgba(16,185,129,0.10)] hover:bg-[rgba(16,185,129,0.18)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {approvingId === pendingUser.id ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : (
                        <CheckCircle size={11} />
                      )}
                      Approve
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
