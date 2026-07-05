import { useState } from 'react';
import { Download, FileText, Check } from 'lucide-react';

export default function ExportReport() {
  const [reportType, setReportType] = useState('Summary');
  const [format, setFormat] = useState('PDF');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeMetrics, setIncludeMetrics] = useState(true);
  const [includeTrades, setIncludeTrades] = useState(true);
  const [includeDrawdown, setIncludeDrawdown] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [done, setDone] = useState(false);

  const handleGenerate = () => {
    setGenerating(true);
    setDone(false);
    setTimeout(() => {
      setGenerating(false);
      setDone(true);
    }, 2000);
  };

  const reportTypes = ['Summary', 'Detailed', 'Trade Journal', 'Custom'];
  const formats = ['PDF', 'CSV', 'Excel'];

  return (
    <div className="max-w-[600px] mx-auto">
      <div className="bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[8px] p-6 space-y-5">
        <div className="flex items-center gap-2 mb-2">
          <FileText size={18} className="text-[#22D3EE]" />
          <h3 className="text-[16px] font-semibold text-[#F1F5F9]">Export Report</h3>
        </div>

        {/* Report Type */}
        <div>
          <label className="text-[12px] text-[#64748B] font-medium block mb-2">Report Type</label>
          <div className="flex gap-2 flex-wrap">
            {reportTypes.map(t => (
              <button
                key={t}
                onClick={() => setReportType(t)}
                className={`px-3 py-1.5 rounded-[6px] text-[12px] font-medium transition-all ${
                  reportType === t
                    ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE] border border-[rgba(34,211,238,0.20)]'
                    : 'bg-[#06060A] text-[#94A3B8] border border-[rgba(255,255,255,0.06)] hover:text-[#F1F5F9]'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Format */}
        <div>
          <label className="text-[12px] text-[#64748B] font-medium block mb-2">Format</label>
          <div className="flex gap-2">
            {formats.map(f => (
              <button
                key={f}
                onClick={() => setFormat(f)}
                className={`px-4 py-1.5 rounded-[6px] text-[12px] font-medium transition-all ${
                  format === f
                    ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE] border border-[rgba(34,211,238,0.20)]'
                    : 'bg-[#06060A] text-[#94A3B8] border border-[rgba(255,255,255,0.06)] hover:text-[#F1F5F9]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Include */}
        <div>
          <label className="text-[12px] text-[#64748B] font-medium block mb-2">Include</label>
          <div className="space-y-2">
            {[
              { key: 'charts', label: 'Charts', value: includeCharts, set: setIncludeCharts },
              { key: 'metrics', label: 'Metrics', value: includeMetrics, set: setIncludeMetrics },
              { key: 'trades', label: 'Trade List', value: includeTrades, set: setIncludeTrades },
              { key: 'drawdown', label: 'Drawdown', value: includeDrawdown, set: setIncludeDrawdown },
            ].map(item => (
              <label key={item.key} className="flex items-center gap-2.5 cursor-pointer group">
                <div
                  className={`w-4 h-4 rounded-[4px] border flex items-center justify-center transition-all ${
                    item.value
                      ? 'bg-[#22D3EE] border-[#22D3EE]'
                      : 'bg-transparent border-[rgba(255,255,255,0.14)] group-hover:border-[rgba(255,255,255,0.25)]'
                  }`}
                  onClick={() => item.set(!item.value)}
                >
                  {item.value && <Check size={10} className="text-[#030305]" strokeWidth={3} />}
                </div>
                <span className="text-[13px] text-[#94A3B8] group-hover:text-[#F1F5F9] transition-colors">{item.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Preview section */}
        <div className="bg-[#06060A] rounded-[6px] p-3 border border-[rgba(255,255,255,0.04)]">
          <h4 className="text-[11px] text-[#64748B] font-medium mb-2">Preview</h4>
          <div className="space-y-1.5">
            <div className="flex justify-between text-[11px]">
              <span className="text-[#475569]">Report Type</span>
              <span className="text-[#94A3B8]">{reportType}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[#475569]">Format</span>
              <span className="text-[#94A3B8]">{format}</span>
            </div>
            <div className="flex justify-between text-[11px]">
              <span className="text-[#475569]">Sections</span>
              <span className="text-[#94A3B8]">
                {[includeCharts && 'Charts', includeMetrics && 'Metrics', includeTrades && 'Trades', includeDrawdown && 'Drawdown']
                  .filter(Boolean).join(', ') || 'None selected'}
              </span>
            </div>
          </div>
        </div>

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="w-full h-12 flex items-center justify-center gap-2 bg-[#22D3EE] text-[#030305] text-[14px] font-semibold rounded-[6px] hover:brightness-110 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {generating ? (
            <>
              <div className="w-4 h-4 border-2 border-[#030305] border-t-transparent rounded-full animate-spin" />
              Generating...
            </>
          ) : done ? (
            <>
              <Check size={16} />
              Download Ready
            </>
          ) : (
            <>
              <Download size={16} />
              Generate Report
            </>
          )}
        </button>

        {generating && (
          <div className="w-full h-1 bg-[#06060A] rounded-full overflow-hidden">
            <div className="h-full bg-[#22D3EE] rounded-full animate-[loading_2s_ease-in-out_infinite]" style={{ width: '60%' }} />
          </div>
        )}
      </div>
    </div>
  );
}
