import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  Send,
  Bot,
  User,
  AlertCircle,
  Save,
  Play,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Spinner } from '@/components/ui/spinner';
import {
  analyzeBacktest,
  createStrategy,
  explainStrategy,
  fetchRAGStatus,
  generateStrategyFromPrompt,
  parseStrategyPrompt,
  runBacktest,
  sendChatMessage,
} from '@/lib/api';
import type {
  ChatMessage,
  ChatResponse,
  GenerateStrategyResponse,
  RAGStatusResponse,
  StrategyCreateRequest,
  StrategySuggestion,
} from '@/types/api';

const PROMPT_SUGGESTIONS = [
  'Generate an RSI mean-reversion strategy for NIFTY50',
  'Analyze my latest backtest',
  'Explain a moving-average crossover strategy',
  'What is the current market regime for RELIANCE?',
];

const EXAMPLE_STRATEGY_OBJECT = {
  name: 'Moving Average Crossover',
  instrument: 'NIFTY50',
  segment: 'equity',
  timeframe: '1d',
  entry_conditions: [{ indicator: 'sma_20', operator: 'crosses_above', value: 'sma_50' }],
  exit_conditions: [{ indicator: 'sma_20', operator: 'crosses_below', value: 'sma_50' }],
  risk_params: {
    stop_loss: { type: 'percent', value: 2 },
    target: { type: 'percent', value: 6 },
    position_sizing: { type: 'percent_of_capital', value: 10 },
  },
};

function formatDateInput(date: Date): string {
  return date.toISOString().split('T')[0];
}

function getDefaultBacktestDates(): { startDate: string; endDate: string } {
  const end = new Date();
  const start = new Date();
  start.setFullYear(end.getFullYear() - 1);
  return { startDate: formatDateInput(start), endDate: formatDateInput(end) };
}

function normalizeStrategyResponse(
  strategy: Record<string, unknown>,
  originalPrompt: string,
): StrategySuggestion {
  const riskParams =
    strategy && typeof strategy === 'object'
      ? (strategy.risk_params as Record<string, unknown> | undefined)
      : undefined;

  return {
    name: String(strategy?.name ?? 'AI Generated Strategy'),
    description: strategy?.description ? String(strategy.description) : undefined,
    instrument: String(strategy?.instrument ?? 'NIFTY50'),
    segment: strategy?.segment ? String(strategy.segment) : undefined,
    timeframe: strategy?.timeframe ? String(strategy.timeframe) : undefined,
    entry_conditions: Array.isArray(strategy?.entry_conditions)
      ? strategy.entry_conditions
      : undefined,
    exit_conditions: Array.isArray(strategy?.exit_conditions)
      ? strategy.exit_conditions
      : undefined,
    stop_loss: riskParams?.stop_loss as Record<string, unknown> | undefined,
    target: riskParams?.target as Record<string, unknown> | undefined,
    position_sizing: riskParams?.position_sizing as Record<string, unknown> | undefined,
    nl_prompt: originalPrompt,
    definition: strategy as Record<string, unknown>,
  };
}

function strategySuggestionToCreateRequest(suggestion: StrategySuggestion): StrategyCreateRequest {
  return {
    name: suggestion.name,
    description: suggestion.description,
    instrument: suggestion.instrument,
    segment: suggestion.segment,
    timeframe: suggestion.timeframe,
    entry_conditions: suggestion.entry_conditions,
    exit_conditions: suggestion.exit_conditions,
    stop_loss: suggestion.stop_loss,
    target: suggestion.target,
    position_sizing: suggestion.position_sizing,
    definition: suggestion.definition,
    nl_prompt: suggestion.nl_prompt,
  };
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'detail' in err) {
    return String((err as { detail: string }).detail);
  }
  if (err instanceof Error) {
    return err.message;
  }
  return 'Something went wrong. Please try again.';
}

interface StrategyCardProps {
  response: GenerateStrategyResponse;
  originalPrompt: string;
  savedId: string | null;
  onSave: (id: string) => void;
  onBacktest: (id: string) => void;
  loading: 'save' | 'backtest' | null;
}

function StrategyCard({
  response,
  originalPrompt,
  savedId,
  onSave,
  onBacktest,
  loading,
}: StrategyCardProps) {
  const navigate = useNavigate();
  const strategy = useMemo(
    () => normalizeStrategyResponse(response.strategy, originalPrompt),
    [response.strategy, originalPrompt],
  );

  const handleSave = async () => {
    if (savedId) {
      onSave(savedId);
      return;
    }
    try {
      const created = await createStrategy(strategySuggestionToCreateRequest(strategy));
      toast.success(`Strategy "${created.name}" saved`);
      onSave(created.id);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleBacktest = async () => {
    let id = savedId;
    if (!id) {
      try {
        const created = await createStrategy(strategySuggestionToCreateRequest(strategy));
        id = created.id;
        onSave(created.id);
        toast.success(`Strategy "${created.name}" saved`);
      } catch (err) {
        toast.error(getErrorMessage(err));
        return;
      }
    }
    onBacktest(id);
  };

  return (
    <div className="mt-3 rounded-[6px] border border-[rgba(34,211,238,0.18)] bg-[rgba(34,211,238,0.06)] p-4">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={16} className="text-[#22D3EE]" />
        <h4 className="text-sm font-semibold text-[#F1F5F9]">
          Generated Strategy: {strategy.name}
        </h4>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div className="text-[#64748B]">
          Instrument: <span className="text-[#94A3B8]">{strategy.instrument}</span>
        </div>
        <div className="text-[#64748B]">
          Timeframe: <span className="text-[#94A3B8]">{strategy.timeframe ?? 'N/A'}</span>
        </div>
        <div className="text-[#64748B]">
          Confidence:{' '}
          <span className="text-[#94A3B8]">
            {typeof response.confidence === 'number' ? `${(response.confidence * 100).toFixed(1)}%` : 'N/A'}
          </span>
        </div>
        <div className="text-[#64748B]">
          Status:{' '}
          <span className="text-[#94A3B8]">{savedId ? 'Saved' : 'Draft'}</span>
        </div>
      </div>

      {response.reasoning && (
        <div className="mb-3 text-xs text-[#94A3B8] leading-relaxed">
          <span className="text-[#64748B] font-medium">Reasoning:</span> {response.reasoning}
        </div>
      )}

      {response.generated_code && (
        <div className="mb-3 rounded-[4px] bg-[#06060A] border border-[rgba(255,255,255,0.06)] p-3 overflow-x-auto">
          <pre className="text-[11px] text-[#94A3B8] font-mono whitespace-pre-wrap">
            {response.generated_code}
          </pre>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="h-8 border-[rgba(34,211,238,0.25)] bg-[rgba(34,211,238,0.08)] text-[#22D3EE] hover:bg-[rgba(34,211,238,0.14)] hover:text-[#22D3EE]"
          onClick={handleSave}
          disabled={loading === 'save'}
        >
          {loading === 'save' ? <Spinner className="mr-1.5" /> : <Save size={14} className="mr-1.5" />}
          {savedId ? 'Saved' : 'Save Strategy'}
        </Button>
        <Button
          size="sm"
          className="h-8 bg-[#22D3EE] text-[#030305] hover:bg-[#67E8F9]"
          onClick={handleBacktest}
          disabled={loading === 'backtest'}
        >
          {loading === 'backtest' ? <Spinner className="mr-1.5" /> : <Play size={14} className="mr-1.5" />}
          Backtest Strategy
        </Button>
        {savedId && (
          <button
            onClick={() => navigate('/app/strategies')}
            className="text-xs text-[#22D3EE] hover:underline flex items-center gap-1"
          >
            View strategies <ArrowRight size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

interface AssistantMessageProps {
  message: ChatMessage;
  allMessages: ChatMessage[];
  onSaveStrategy: (messageIndex: number, id: string) => void;
  onBacktestResult: (result: Record<string, unknown>) => void;
}

function AssistantMessage({ message, allMessages, onSaveStrategy, onBacktestResult }: AssistantMessageProps) {
  const [saveLoading, setSaveLoading] = useState<'save' | 'backtest' | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [backtestId, setBacktestId] = useState<string | null>(null);
  const navigate = useNavigate();

  const strategyResponse = message.strategyResponse;
  const originalPrompt = message.originalPrompt ?? '';

  const handleSave = (id: string) => {
    setSavedId(id);
    onSaveStrategy(allMessages.indexOf(message), id);
  };

  const handleBacktest = async (strategyId: string) => {
    setSaveLoading('backtest');
    try {
      const { startDate, endDate } = getDefaultBacktestDates();
      const result = await runBacktest({
        strategy_id: strategyId,
        start_date: startDate,
        end_date: endDate,
        initial_capital: 1_000_000,
      });
      setBacktestId(result.id);
      onBacktestResult(result as unknown as Record<string, unknown>);
      toast.success('Backtest started successfully');
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaveLoading(null);
    }
  };

  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-8 h-8 rounded-[6px] bg-[rgba(34,211,238,0.12)] flex items-center justify-center border border-[rgba(34,211,238,0.18)]">
        <Bot size={18} className="text-[#22D3EE]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-[#64748B] mb-1">TradeForge AI</div>
        <div className="prose prose-invert prose-sm max-w-none text-[#E2E8F0]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        {strategyResponse && (
          <StrategyCard
            response={strategyResponse}
            originalPrompt={originalPrompt}
            savedId={savedId}
            onSave={handleSave}
            onBacktest={handleBacktest}
            loading={saveLoading}
          />
        )}
        {backtestId && (
          <div className="mt-2 flex items-center gap-2 text-xs text-[#22D3EE]">
            <CheckCircle2 size={14} />
            <span>Backtest submitted.</span>
            <button
              onClick={() => navigate('/app/backtest')}
              className="hover:underline flex items-center gap-1"
            >
              View backtests <ArrowRight size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIChat() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        "Hello! I'm your TradeForge AI trading assistant. Ask me to generate a strategy, explain a strategy, analyze a backtest, or anything about market regimes and trading ideas.",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ragStatus, setRagStatus] = useState<RAGStatusResponse | null>(null);
  const [lastBacktestResult, setLastBacktestResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchRAGStatus()
      .then(setRagStatus)
      .catch(() => {
        setRagStatus({ initialized: false, queries_served: 0, total_query_time_ms: 0 });
      });
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading, error]);

  const addMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => {
      const next = [...prev, message];
      // Keep roughly the last 10 conversation turns (20 messages) in memory.
      if (next.length > 20) {
        return next.slice(-20);
      }
      return next;
    });
  }, []);

  const buildContext = useCallback((): ChatMessage[] => {
    return messages.slice(-20);
  }, [messages]);

  const isGenerateIntent = useCallback((text: string): boolean => {
    const lower = text.toLowerCase();
    return (
      lower.startsWith('/generate') ||
      (lower.includes('generate') && lower.includes('strategy')) ||
      (lower.includes('create') && lower.includes('strategy')) ||
      (lower.includes('build') && lower.includes('strategy'))
    );
  }, []);

  const handleNormalChat = async (text: string): Promise<ChatResponse> => {
    return sendChatMessage({ message: text, context: buildContext() });
  };

  const handleGenerateStrategy = async (text: string): Promise<ChatResponse & { strategyResponse?: GenerateStrategyResponse; originalPrompt?: string }> => {
    const cleanPrompt = text.replace(/^\/generate\s*/i, '').trim();
    const response = await generateStrategyFromPrompt({ prompt: cleanPrompt || text });

    let content = `**${response.strategy && typeof response.strategy === 'object' && 'name' in response.strategy ? String(response.strategy.name) : 'Strategy'}**\n\n`;
    if (response.reasoning) {
      content += `${response.reasoning}\n\n`;
    }
    content += `Confidence: ${typeof response.confidence === 'number' ? `${(response.confidence * 100).toFixed(1)}%` : 'N/A'}`;

    return {
      response: content,
      model_loaded: true,
      strategyResponse: response,
      originalPrompt: cleanPrompt || text,
    };
  };

  const handleExplainStrategy = async (text: string): Promise<ChatResponse> => {
    const cleanPrompt = text.replace(/^\/explain\s*/i, '').trim();
    let strategyObject: Record<string, unknown> = EXAMPLE_STRATEGY_OBJECT;

    try {
      const parsed = await parseStrategyPrompt(cleanPrompt || text);
      strategyObject = {
        name: parsed.name,
        description: parsed.description,
        instrument: parsed.instrument,
        segment: parsed.segment,
        timeframe: parsed.timeframe,
        indicators: parsed.indicators,
        entry_conditions: parsed.entry_conditions,
        exit_conditions: parsed.exit_conditions,
        risk_params: parsed.risk_params,
        generated_code: parsed.generated_code,
        validation: parsed.validation,
      };
    } catch {
      // Fall back to the example object if parsing fails.
    }

    const explanation = await explainStrategy({ strategy: strategyObject });
    return {
      response: explanation.explanation,
      model_loaded: true,
    };
  };

  const handleAnalyzeBacktest = async (text: string): Promise<ChatResponse> => {
    if (!lastBacktestResult) {
      return handleNormalChat(
        `${text}\n\n(Please run a backtest first so I can analyze the results.)`,
      );
    }
    const analysis = await analyzeBacktest({ results: lastBacktestResult });
    setLastBacktestResult(null);
    return {
      response: `**Backtest Analysis**\n\n${analysis.analysis}\n\n**Metrics Summary**\n\n${analysis.metrics_summary}`,
      model_loaded: true,
    };
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };
    addMessage(userMessage);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const trimmed = text.trim();
      let response: ChatResponse & {
        strategyResponse?: GenerateStrategyResponse;
        originalPrompt?: string;
      };

      if (trimmed.toLowerCase().startsWith('/explain')) {
        response = await handleExplainStrategy(trimmed);
      } else if (trimmed.toLowerCase().startsWith('/analyze')) {
        response = await handleAnalyzeBacktest(trimmed);
      } else if (isGenerateIntent(trimmed)) {
        response = await handleGenerateStrategy(trimmed);
      } else {
        response = await handleNormalChat(trimmed);
      }

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        strategyResponse: response.strategyResponse,
        originalPrompt: response.originalPrompt,
      };
      addMessage(assistantMessage);
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    sendMessage(suggestion);
  };

  const handleSaveStrategy = (messageIndex: number, id: string) => {
    setMessages((prev) => {
      const next = [...prev];
      next[messageIndex] = { ...next[messageIndex], strategySavedId: id };
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full min-h-[calc(100vh-48px-32px-48px)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[6px] bg-[rgba(34,211,238,0.12)] flex items-center justify-center border border-[rgba(34,211,238,0.18)]">
            <Sparkles size={20} className="text-[#22D3EE]" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-[#F1F5F9]">TradeForge AI</h1>
            <p className="text-xs text-[#64748B]">AI trading assistant with RAG-powered context</p>
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-[4px] border border-[rgba(255,255,255,0.06)] bg-[#0A0A0F]">
          <span
            className={`w-2 h-2 rounded-full ${
              ragStatus?.initialized ? 'bg-[#10B981]' : 'bg-[#64748B]'
            }`}
          />
          <span className="text-xs text-[#94A3B8]">
            RAG {ragStatus?.initialized ? 'Ready' : 'Offline'}
          </span>
          {typeof ragStatus?.queries_served === 'number' && (
            <span className="text-xs text-[#64748B]">· {ragStatus.queries_served} queries</span>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto pr-2 space-y-6 min-h-0"
      >
        {messages.map((message, index) =>
          message.role === 'user' ? (
            <div key={index} className="flex gap-3 justify-end">
              <div className="max-w-[85%] md:max-w-[70%]">
                <div className="rounded-[12px] rounded-tr-[4px] bg-[rgba(34,211,238,0.10)] border border-[rgba(34,211,238,0.16)] px-4 py-3">
                  <p className="text-sm text-[#F1F5F9] whitespace-pre-wrap">{message.content}</p>
                </div>
                <div className="text-[10px] text-[#64748B] mt-1 text-right">
                  {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </div>
              </div>
              <div className="shrink-0 w-8 h-8 rounded-[6px] bg-[#1A1A25] flex items-center justify-center border border-[rgba(255,255,255,0.06)]">
                <User size={18} className="text-[#94A3B8]" />
              </div>
            </div>
          ) : (
            <div key={index}>
              <AssistantMessage
                message={message}
                allMessages={messages}
                onSaveStrategy={handleSaveStrategy}
                onBacktestResult={setLastBacktestResult}
              />
            </div>
          ),
        )}

        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 w-8 h-8 rounded-[6px] bg-[rgba(34,211,238,0.12)] flex items-center justify-center border border-[rgba(34,211,238,0.18)]">
              <Bot size={18} className="text-[#22D3EE]" />
            </div>
            <div className="flex items-center gap-2 text-sm text-[#94A3B8]">
              <Spinner className="text-[#22D3EE]" />
              Thinking...
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-[4px] border border-[rgba(239,68,68,0.25)] bg-[rgba(239,68,68,0.08)] p-3">
            <AlertCircle size={16} className="text-[#EF4444] shrink-0 mt-0.5" />
            <p className="text-sm text-[#F1F5F9]">{error}</p>
          </div>
        )}
      </div>

      {/* Suggestions */}
      <div className="py-3">
        <div className="flex flex-wrap gap-2">
          {PROMPT_SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSuggestionClick(suggestion)}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded-full border border-[rgba(255,255,255,0.08)] bg-[#0A0A0F] text-[#94A3B8] hover:bg-[#1A1A25] hover:text-[#F1F5F9] hover:border-[rgba(34,211,238,0.25)] transition-all disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="rounded-[6px] border border-[rgba(255,255,255,0.08)] bg-[#0A0A0F] p-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask TradeForge AI... (Shift+Enter for new line)"
          disabled={loading}
          className="min-h-[80px] resize-none border-0 bg-transparent text-[#F1F5F9] placeholder:text-[#475569] focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none"
        />
        <div className="flex items-center justify-between mt-2">
          <div className="text-[10px] text-[#64748B]">
            Tip: Use <kbd className="px-1 py-0.5 rounded bg-[#1A1A25] text-[#94A3B8]">/explain</kbd>{' '}
            or <kbd className="px-1 py-0.5 rounded bg-[#1A1A25] text-[#94A3B8]">/analyze</kbd>{' '}
            shortcuts
          </div>
          <Button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="h-9 bg-[#22D3EE] text-[#030305] hover:bg-[#67E8F9] disabled:opacity-50"
          >
            {loading ? <Spinner className="mr-1.5" /> : <Send size={16} className="mr-1.5" />}
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
