import { useMemo, useState } from 'react';
import { Search, ArrowUpDown, ChevronDown, ChevronRight } from 'lucide-react';
import type { AnalyticsTrade } from '@/types/api';
import { trades } from './data';

interface TradeRow {
  id: string;
  date: string;
  symbol: string;
  strategy: string;
  side: 'Long' | 'Short';
  entryPrice: number;
  exitPrice: number;
  qty: number;
  pnl: number;
  pnlPercent: number;
  holdingPeriod: string;
  notes: string;
  tags: string[];
}

function normalizeSide(side: string): 'Long' | 'Short' {
  const normalized = side.toLowerCase();
  if (normalized === 'buy' || normalized === 'long') return 'Long';
  return 'Short';
}

function formatHoldingPeriod(entry?: string, exit?: string): string {
  if (!entry || !exit) return '-';
  const diff = Math.ceil((new Date(exit).getTime() - new Date(entry).getTime()) / (1000 * 60 * 60 * 24));
  return diff <= 0 ? 'Same day' : `${diff} day${diff > 1 ? 's' : ''}`;
}

function normalizeAnalyticsTrades(items: AnalyticsTrade[]): TradeRow[] {
  return items.map(t => ({
    id: t.id,
    date: t.exit_time?.split('T')[0] || t.entry_time?.split('T')[0] || '',
    symbol: t.symbol,
    strategy: t.strategy_name,
    side: normalizeSide(t.side),
    entryPrice: t.entry_price,
    exitPrice: t.exit_price,
    qty: t.quantity,
    pnl: t.pnl,
    pnlPercent: t.pnl_pct,
    holdingPeriod: formatHoldingPeriod(t.entry_time, t.exit_time),
    notes: '',
    tags: [],
  }));
}

interface TradeJournalProps {
  trades?: AnalyticsTrade[];
}

export default function TradeJournal({ trades: tradesProp }: TradeJournalProps) {
  const [search, setSearch] = useState('');
  const [sideFilter, setSideFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [editingNote, setEditingNote] = useState<string | null>(null);

  const allTrades = useMemo<TradeRow[]>(() => {
    if (tradesProp) return normalizeAnalyticsTrades(tradesProp);
    return trades.map(t => ({ ...t }));
  }, [tradesProp]);

  const filtered = allTrades.filter(t => {
    const matchesSearch = search === '' ||
      t.symbol.toLowerCase().includes(search.toLowerCase()) ||
      t.strategy.toLowerCase().includes(search.toLowerCase());
    const matchesSide = sideFilter === 'All' || t.side === sideFilter;
    const matchesStatus = statusFilter === 'All' ||
      (statusFilter === 'Win' ? t.pnl >= 0 : t.pnl < 0);
    return matchesSearch && matchesSide && matchesStatus;
  }).sort((a, b) => {
    const dateA = new Date(a.date).getTime();
    const dateB = new Date(b.date).getTime();
    return sortAsc ? dateA - dateB : dateB - dateA;
  });

  const updateNote = (id: string, note: string) => {
    setNotes(prev => ({ ...prev, [id]: note }));
    setEditingNote(null);
  };

  const exportCSV = () => {
    const headers = ['Date', 'Symbol', 'Strategy', 'Side', 'Entry', 'Exit', 'Qty', 'P&L', 'P&L%', 'Holding', 'Notes'];
    const rows = filtered.map(t => [
      t.date, t.symbol, t.strategy, t.side, t.entryPrice, t.exitPrice,
      t.qty, t.pnl, t.pnlPercent, t.holdingPeriod, notes[t.id] || t.notes,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'trade-journal.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-3">
      {/* Filter Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
          <input
            type="text"
            placeholder="Search symbol or strategy..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full h-8 pl-9 pr-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
          />
        </div>

        <select
          value={sideFilter}
          onChange={e => setSideFilter(e.target.value)}
          className="h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#94A3B8] focus:outline-none focus:border-[#22D3EE]"
        >
          <option value="All">All Sides</option>
          <option value="Long">Long</option>
          <option value="Short">Short</option>
        </select>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="h-8 px-2 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#94A3B8] focus:outline-none focus:border-[#22D3EE]"
        >
          <option value="All">All</option>
          <option value="Win">Win</option>
          <option value="Loss">Loss</option>
        </select>

        <button
          onClick={() => setSortAsc(!sortAsc)}
          className="h-8 px-2 flex items-center gap-1 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#12121A] transition-all"
        >
          <ArrowUpDown size={12} />
          {sortAsc ? 'Oldest' : 'Newest'}
        </button>

        <button
          onClick={exportCSV}
          className="h-8 px-3 flex items-center gap-1 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all ml-auto"
        >
          Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-[#06060A]">
            <tr>
              <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B] w-6" />
              <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B]">Date</th>
              <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B]">Symbol</th>
              <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B]">Strategy</th>
              <th className="text-center px-3 py-2 text-[11px] font-medium text-[#64748B]">Side</th>
              <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Entry</th>
              <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Exit</th>
              <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">Qty</th>
              <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">P&L</th>
              <th className="text-right px-3 py-2 text-[11px] font-medium text-[#64748B]">P&L%</th>
              <th className="text-center px-3 py-2 text-[11px] font-medium text-[#64748B]">Holding</th>
              <th className="text-left px-3 py-2 text-[11px] font-medium text-[#64748B]">Notes</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((trade) => (
              <>
                <tr
                  key={trade.id}
                  className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer"
                  onClick={() => setExpandedRow(expandedRow === trade.id ? null : trade.id)}
                >
                  <td className="px-3 py-1.5">
                    {expandedRow === trade.id
                      ? <ChevronDown size={12} className="text-[#64748B]" />
                      : <ChevronRight size={12} className="text-[#64748B]" />
                    }
                  </td>
                  <td className="px-3 py-1.5 text-[11px] font-mono text-[#94A3B8] whitespace-nowrap">{trade.date}</td>
                  <td className="px-3 py-1.5 text-[12px] font-mono font-semibold text-[#F1F5F9] whitespace-nowrap">{trade.symbol}</td>
                  <td className="px-3 py-1.5 text-[11px] text-[#94A3B8] whitespace-nowrap">{trade.strategy}</td>
                  <td className="px-3 py-1.5 text-center whitespace-nowrap">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-[4px] ${
                      trade.side === 'Long' ? 'text-[#10B981] bg-[rgba(16,185,129,0.15)]' : 'text-[#EF4444] bg-[rgba(239,68,68,0.15)]'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-[11px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">₹{trade.entryPrice.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-[11px] font-mono text-right text-[#F1F5F9] whitespace-nowrap">₹{trade.exitPrice.toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-[11px] font-mono text-right text-[#94A3B8] whitespace-nowrap">{trade.qty}</td>
                  <td className={`px-3 py-1.5 text-[11px] font-mono text-right font-semibold whitespace-nowrap ${
                    trade.pnl >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                  }`}>
                    {trade.pnl >= 0 ? '+' : ''}₹{trade.pnl.toLocaleString('en-IN')}
                  </td>
                  <td className={`px-3 py-1.5 text-[11px] font-mono text-right whitespace-nowrap ${
                    trade.pnlPercent >= 0 ? 'text-[#10B981]' : 'text-[#EF4444]'
                  }`}>
                    {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
                  </td>
                  <td className="px-3 py-1.5 text-[11px] font-mono text-center text-[#94A3B8] whitespace-nowrap">{trade.holdingPeriod}</td>
                  <td className="px-3 py-1.5 whitespace-nowrap min-w-[150px]">
                    {editingNote === trade.id ? (
                      <input
                        type="text"
                        autoFocus
                        defaultValue={notes[trade.id] || trade.notes}
                        onBlur={e => updateNote(trade.id, e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') updateNote(trade.id, e.currentTarget.value);
                          if (e.key === 'Escape') setEditingNote(null);
                        }}
                        className="w-full bg-[#06060A] border border-[rgba(255,255,255,0.10)] rounded-[4px] px-1.5 py-0.5 text-[11px] text-[#F1F5F9] focus:outline-none focus:border-[#22D3EE]"
                      />
                    ) : (
                      <button
                        onClick={e => {
                          e.stopPropagation();
                          setEditingNote(trade.id);
                        }}
                        className="text-[11px] text-left text-[#64748B] hover:text-[#F1F5F9] transition-colors truncate max-w-[140px] block"
                      >
                        {(notes[trade.id] || trade.notes) || '+ Add Note'}
                      </button>
                    )}
                  </td>
                </tr>
                {expandedRow === trade.id && (
                  <tr>
                    <td colSpan={12} className="px-4 py-3 bg-[#06060A]">
                      <div className="grid grid-cols-4 gap-4">
                        <div>
                          <span className="text-[10px] text-[#64748B] block mb-1">Entry Details</span>
                          <div className="text-[11px] font-mono text-[#F1F5F9]">₹{trade.entryPrice.toFixed(2)}</div>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#64748B] block mb-1">Exit Details</span>
                          <div className="text-[11px] font-mono text-[#F1F5F9]">₹{trade.exitPrice.toFixed(2)}</div>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#64748B] block mb-1">Quantity</span>
                          <div className="text-[11px] font-mono text-[#F1F5F9]">{trade.qty}</div>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#64748B] block mb-1">Holding Period</span>
                          <div className="text-[11px] font-mono text-[#F1F5F9]">{trade.holdingPeriod}</div>
                        </div>
                        {trade.tags.length > 0 && (
                          <div className="col-span-4">
                            <span className="text-[10px] text-[#64748B] block mb-1">Tags</span>
                            <div className="flex flex-wrap gap-1">
                              {trade.tags.map(tag => (
                                <span key={tag} className="px-1.5 py-0.5 bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-full text-[10px] text-[#94A3B8]">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
