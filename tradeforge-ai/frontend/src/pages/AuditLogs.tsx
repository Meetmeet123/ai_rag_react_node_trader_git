import { useEffect, useState, useCallback, Fragment } from 'react';
import { toast } from 'sonner';
import { ShieldAlert, ChevronDown, ChevronUp } from 'lucide-react';
import { fetchAuditLogs } from '@/lib/api';
import type { AuditLog, AuditLogListResponse } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const ACTION_OPTIONS = ['All', 'POST', 'PUT', 'PATCH', 'DELETE'];
const LIMIT = 20;

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('All');
  const [resourceFilter, setResourceFilter] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    try {
      const response: AuditLogListResponse = await fetchAuditLogs({
        limit: LIMIT,
        offset,
        action: actionFilter === 'All' ? undefined : actionFilter,
        resource: resourceFilter.trim() || undefined,
      });
      setLogs(response.logs ?? []);
      setTotal(response.total ?? 0);
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Failed to load audit logs';
      toast.error(message);
      setLogs([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [offset, actionFilter, resourceFilter]);

  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadLogs]);

  useEffect(() => {
    setExpandedId(null);
  }, [offset]);

  const handleActionChange = (value: string) => {
    setActionFilter(value);
    setOffset(0);
  };

  const handleResourceChange = (value: string) => {
    setResourceFilter(value);
    setOffset(0);
  };

  const toggleExpanded = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const formatDetails = (details: Record<string, unknown> | null | undefined) => {
    if (!details) return 'No details';
    try {
      return JSON.stringify(details, null, 2);
    } catch {
      return String(details);
    }
  };

  const getStatusVariant = (statusCode?: number | null) => {
    if (!statusCode) return 'secondary';
    if (statusCode >= 200 && statusCode < 300) return 'default';
    if (statusCode >= 400) return 'destructive';
    return 'secondary';
  };

  const totalPages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;
  const canGoPrevious = offset > 0;
  const canGoNext = offset + LIMIT < total;

  return (
    <div className="min-h-full -m-4 md:-m-6 p-4 md:p-6 bg-[#030305]">
      <Card className="bg-[#12121A] border-[rgba(255,255,255,0.06)] text-[#F1F5F9]">
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-6 w-6 text-[#22D3EE]" />
            <CardTitle className="text-xl font-semibold text-[#F1F5F9]">Audit Logs</CardTitle>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <Select value={actionFilter} onValueChange={handleActionChange}>
              <SelectTrigger className="w-[140px] bg-[#0D0D14] border-[rgba(255,255,255,0.08)] text-[#F1F5F9]">
                <SelectValue placeholder="Action" />
              </SelectTrigger>
              <SelectContent className="bg-[#0D0D14] border-[rgba(255,255,255,0.08)] text-[#F1F5F9]">
                {ACTION_OPTIONS.map((action) => (
                  <SelectItem
                    key={action}
                    value={action}
                    className="focus:bg-[rgba(34,211,238,0.12)] focus:text-[#22D3EE]"
                  >
                    {action === 'All' ? 'All Actions' : action}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="text"
              placeholder="Search resource..."
              value={resourceFilter}
              onChange={(e) => handleResourceChange(e.target.value)}
              className="w-full sm:w-[220px] bg-[#0D0D14] border-[rgba(255,255,255,0.08)] text-[#F1F5F9] placeholder:text-[#475569]"
            />
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="w-8 h-8 border-2 border-[#22D3EE] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : logs.length === 0 ? (
            <div className="flex items-center justify-center h-64 text-[#64748B]">
              No audit logs found.
            </div>
          ) : (
            <>
              <div className="rounded-md border border-[rgba(255,255,255,0.06)] overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="border-b border-[rgba(255,255,255,0.06)] hover:bg-transparent">
                      <TableHead className="text-[#94A3B8] font-medium">Timestamp</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">User</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">Role</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">Action</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">Resource</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">Resource ID</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">Status</TableHead>
                      <TableHead className="text-[#94A3B8] font-medium">IP Address</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => (
                      <Fragment key={log.id}>
                        <TableRow
                          onClick={() => toggleExpanded(log.id)}
                          className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(34,211,238,0.05)] cursor-pointer"
                        >
                          <TableCell className="text-[#F1F5F9] whitespace-nowrap">
                            <div className="flex items-center gap-1">
                              {expandedId === log.id ? (
                                <ChevronUp size={14} className="text-[#64748B]" />
                              ) : (
                                <ChevronDown size={14} className="text-[#64748B]" />
                              )}
                              {formatTimestamp(log.timestamp)}
                            </div>
                          </TableCell>
                          <TableCell className="text-[#F1F5F9]">{log.username}</TableCell>
                          <TableCell>
                            <Badge
                              variant={log.role === 'admin' ? 'default' : 'secondary'}
                              className="capitalize text-[11px]"
                            >
                              {log.role}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-[#F1F5F9]">{log.action}</TableCell>
                          <TableCell className="text-[#F1F5F9]">{log.resource}</TableCell>
                          <TableCell className="text-[#94A3B8]">
                            {log.resource_id || '-'}
                          </TableCell>
                          <TableCell>
                            <Badge variant={getStatusVariant(log.status_code)} className="text-[11px]">
                              {log.status_code ?? '-'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-[#94A3B8]">
                            {log.ip_address || '-'}
                          </TableCell>
                        </TableRow>
                        {expandedId === log.id && (
                          <TableRow className="border-0 hover:bg-transparent">
                            <TableCell colSpan={8} className="bg-[#0D0D14] p-0">
                              <div className="p-4">
                                <h4 className="text-[13px] font-medium text-[#F1F5F9] mb-2">
                                  Details
                                </h4>
                                {log.user_agent && (
                                  <p className="text-[12px] text-[#64748B] mb-2">
                                    <span className="text-[#94A3B8]">User Agent:</span> {log.user_agent}
                                  </p>
                                )}
                                <pre className="text-[12px] text-[#94A3B8] bg-[#06060A] rounded-[4px] p-3 overflow-x-auto border border-[rgba(255,255,255,0.06)]">
                                  {formatDetails(log.details)}
                                </pre>
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex items-center justify-between mt-4">
                <span className="text-[13px] text-[#64748B]">
                  Showing {Math.min(offset + 1, total)} - {Math.min(offset + LIMIT, total)} of {total}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOffset((prev) => Math.max(0, prev - LIMIT))}
                    disabled={!canGoPrevious}
                    className="bg-[#0D0D14] border-[rgba(255,255,255,0.08)] text-[#F1F5F9] hover:bg-[#1A1A25] disabled:opacity-40"
                  >
                    Previous
                  </Button>
                  <span className="text-[13px] text-[#64748B]">
                    Page {currentPage} of {totalPages || 1}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setOffset((prev) => prev + LIMIT)}
                    disabled={!canGoNext}
                    className="bg-[#0D0D14] border-[rgba(255,255,255,0.08)] text-[#F1F5F9] hover:bg-[#1A1A25] disabled:opacity-40"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
