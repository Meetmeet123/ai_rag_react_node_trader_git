import { useEffect, useRef, useState } from 'react';
import {
  GitBranch,
  History,
  Shield,
  Zap,
  Lock,
  BarChart3,
  Check,
  PlayCircle,
  Sparkles,
} from 'lucide-react';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

/* ─── count-up hook ─── */
function useCountUp(target: number, duration: number, start: boolean) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf: number;
    const startTime = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.floor(eased * target));
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, start]);
  return value;
}

/* ─── Section: Hero ─── */
function HeroSection() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <section className="relative min-h-[100dvh] flex items-center overflow-hidden">
      {/* Background */}
      <div
        className="absolute inset-0 bg-[#030305]"
        style={{
          backgroundImage:
            'url(/hero-bg-grid.svg), radial-gradient(ellipse 80% 50% at 50% -20%, rgba(34,211,238,0.08), transparent)',
          backgroundPosition: 'center',
          backgroundSize: 'cover, auto',
          backgroundRepeat: 'no-repeat',
          opacity: 0.3,
        }}
      />

      <div className="relative z-10 max-w-[1440px] mx-auto px-6 py-24 w-full">
        <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-8">
          {/* Left Content */}
          <div className="flex-1 lg:max-w-[55%]">
            {/* Badge */}
            <div
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[rgba(34,211,238,0.12)] text-[#22D3EE] text-[12px] font-semibold mb-6 transition-all duration-500 ${
                visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
              }`}
            >
              <Sparkles size={14} />
              Now with Paper Trading
            </div>

            {/* Headline */}
            <h1 className="font-display text-[36px] sm:text-[42px] lg:text-[48px] font-bold text-[#F1F5F9] leading-[1.1] tracking-tight">
              {['Build, Test & Deploy', 'Trading Strategies with', 'AI-Powered Precision'].map(
                (line, i) => (
                  <span
                    key={i}
                    className={`block transition-all duration-500 ${
                      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
                    }`}
                    style={{ transitionDelay: `${400 + i * 100}ms` }}
                  >
                    {line}
                  </span>
                )
              )}
            </h1>

            {/* Subheadline */}
            <p
              className={`mt-4 text-[16px] text-[#94A3B8] max-w-[520px] leading-relaxed transition-all duration-500 ${
                visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
              }`}
              style={{ transitionDelay: '700ms' }}
            >
              TradeForge AI is India's most advanced algorithmic trading platform. Build custom
              strategies with a visual formula editor, backtest on 10+ years of historical data, and
              deploy to live markets — all in one terminal.
            </p>

            {/* CTAs */}
            <div
              className={`mt-8 flex flex-wrap items-center gap-3 transition-all duration-500 ${
                visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'
              }`}
              style={{ transitionDelay: '900ms' }}
            >
              <a
                href="/app"
                className="inline-flex items-center gap-2 px-6 py-3 bg-[#22D3EE] text-[#030305] text-[16px] font-semibold rounded-[4px] hover:brightness-110 transition-all duration-200 hover:shadow-[0_0_20px_rgba(34,211,238,0.15)] active:scale-[0.98]"
              >
                Start Building Free
              </a>
              <button className="inline-flex items-center gap-2 px-6 py-3 border border-[rgba(255,255,255,0.10)] text-[#F1F5F9] text-[16px] font-medium rounded-[4px] hover:bg-[#12121A] hover:border-[rgba(255,255,255,0.14)] transition-all duration-200">
                <PlayCircle size={18} />
                Watch Demo
              </button>
            </div>

            {/* Trust bar */}
            <div
              className={`mt-10 flex flex-wrap items-center gap-6 transition-all duration-500 ${
                visible ? 'opacity-100' : 'opacity-0'
              }`}
              style={{ transitionDelay: '1100ms' }}
            >
              <span className="text-[12px] text-[#64748B]">Trusted by 12,000+ traders</span>
              <div className="flex items-center gap-4">
                {['NSE', 'BSE', 'MCX', 'CDS'].map((exchange) => (
                  <span
                    key={exchange}
                    className="text-[12px] font-semibold text-[#64748B] opacity-40 tracking-wider"
                  >
                    {exchange}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right: UI Mockup */}
          <div
            className={`flex-1 lg:max-w-[45%] flex justify-center lg:justify-end transition-all duration-700 ${
              visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-10'
            }`}
            style={{ transitionDelay: '600ms' }}
          >
            <div className="animate-float w-full max-w-[600px]" style={{ perspective: '1000px' }}>
              <img
                src="/hero-ui-mockup.png"
                alt="TradeForge AI Dashboard"
                className="w-[110%] max-w-none rounded-[12px] shadow-[0_32px_64px_rgba(0,0,0,0.50)]"
                style={{ transform: 'rotateY(-5deg) rotateX(2deg)' }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ─── Section: Stats Bar ─── */
function StatsSection() {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const traders = useCountUp(12000, 1500, inView);
  const trades = useCountUp(847, 1500, inView);
  const years = useCountUp(10, 1500, inView);
  const latency = useCountUp(50, 1500, inView);

  const stats = [
    { value: `${traders.toLocaleString()}+`, label: 'Active Traders' },
    { value: `\u20B9${trades} Cr`, label: 'Trades Executed' },
    { value: `${years}+ Years`, label: 'Historical Data' },
    { value: `< ${latency}ms`, label: 'Order Latency' },
  ];

  return (
    <section ref={ref} className="w-full bg-[#0A0A0F] border-y border-[rgba(255,255,255,0.06)]">
      <div className="max-w-[1440px] mx-auto px-6 h-20 flex items-center">
        <div className="grid grid-cols-2 md:grid-cols-4 w-full">
          {stats.map((stat, i) => (
            <div
              key={stat.label}
              className={`flex flex-col items-center justify-center ${
                i < stats.length - 1 ? 'md:border-r border-[rgba(255,255,255,0.06)]' : ''
              } ${i === 0 || i === 1 ? 'border-b md:border-b-0 border-[rgba(255,255,255,0.06)]' : ''} py-3`}
            >
              <span className="font-mono text-[24px] sm:text-[28px] font-semibold text-[#F1F5F9]">
                {stat.value}
              </span>
              <span
                className={`text-[12px] text-[#64748B] mt-0.5 transition-opacity duration-500 ${
                  inView ? 'opacity-100' : 'opacity-0'
                }`}
                style={{ transitionDelay: `${200 + i * 200}ms` }}
              >
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Section: Features ─── */
const features = [
  {
    icon: GitBranch,
    title: 'Visual Strategy Builder',
    desc: 'Drag-and-drop formula editor with 50+ technical indicators. Build complex entry, exit, and risk rules without writing code.',
    image: '/feature-strategy-builder.png',
  },
  {
    icon: History,
    title: 'Backtesting Engine',
    desc: 'Test strategies on 10+ years of historical NSE/BSE data. See equity curves, drawdowns, Sharpe ratio, and win rates.',
    image: '/feature-backtest.png',
  },
  {
    icon: Shield,
    title: 'Paper Trading',
    desc: 'Deploy strategies with \u20B910 lakh virtual capital. Test in real market conditions with zero risk before going live.',
    image: '/feature-strategy-builder.png',
  },
  {
    icon: Zap,
    title: 'Live Trading',
    desc: 'Execute strategies in real-time with sub-50ms order placement. Integrate with Angel One, Zerodha, and more.',
    image: '/feature-live-trading.png',
  },
  {
    icon: Lock,
    title: 'Risk Management',
    desc: 'Stop-loss, trailing stops, position sizing, and daily loss limits. Protect your capital with institutional-grade controls.',
    image: '/feature-backtest.png',
  },
  {
    icon: BarChart3,
    title: 'Advanced Analytics',
    desc: 'Deep performance reports, trade journals, P&L heatmaps, and exportable insights to refine your edge.',
    image: '/feature-live-trading.png',
  },
];

function FeaturesSection() {
  const ref = useRef<HTMLDivElement>(null);
  const [visibleItems, setVisibleItems] = useState<Set<number>>(new Set());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number(entry.target.getAttribute('data-index'));
            setVisibleItems((prev) => new Set(prev).add(idx));
          }
        });
      },
      { threshold: 0.1 }
    );
    const cards = ref.current?.querySelectorAll('[data-index]');
    cards?.forEach((card) => observer.observe(card));
    return () => observer.disconnect();
  }, []);

  return (
    <section id="features" className="w-full bg-[#030305] py-24">
      <div ref={ref} className="max-w-[1440px] mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-[12px] font-semibold text-[#22D3EE] tracking-[0.15em] uppercase">
            FEATURES
          </span>
          <h2 className="mt-3 font-display text-[28px] font-semibold text-[#F1F5F9]">
            Everything You Need to Trade Smarter
          </h2>
          <p className="mt-3 text-[16px] text-[#94A3B8] max-w-[640px] mx-auto">
            From strategy creation to live execution — one platform for the entire trading lifecycle
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                data-index={i}
                className={`bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[16px] p-6 transition-all duration-300 hover:border-[rgba(255,255,255,0.10)] hover:bg-[#1A1A25] ${
                  visibleItems.has(i)
                    ? 'opacity-100 translate-y-0'
                    : 'opacity-0 translate-y-4'
                }`}
                style={{ transitionDelay: `${i * 80}ms` }}
              >
                {/* Icon */}
                <div className="w-10 h-10 rounded-full bg-[rgba(34,211,238,0.12)] flex items-center justify-center mb-4">
                  <Icon size={20} className="text-[#22D3EE]" />
                </div>

                {/* Title */}
                <h3 className="text-[18px] font-semibold text-[#F1F5F9] mb-2">{feature.title}</h3>

                {/* Description */}
                <p className="text-[14px] text-[#94A3B8] leading-relaxed mb-5">{feature.desc}</p>

                {/* Image */}
                <div className="h-[200px] sm:h-[240px] rounded-[8px] overflow-hidden bg-[#06060A]">
                  <img
                    src={feature.image}
                    alt={feature.title}
                    className="w-full h-full object-cover"
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ─── Section: How It Works ─── */
const steps = [
  {
    num: '1',
    title: 'Build',
    desc: 'Create your strategy using our visual formula editor with 50+ indicators',
  },
  {
    num: '2',
    title: 'Backtest',
    desc: 'Run simulations on 10+ years of historical market data',
  },
  {
    num: '3',
    title: 'Paper Trade',
    desc: 'Deploy with virtual capital to validate in real market conditions',
  },
  {
    num: '4',
    title: 'Go Live',
    desc: 'Connect your broker and execute with sub-50ms latency',
  },
];

function HowItWorksSection() {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.2 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="how-it-works" ref={ref} className="w-full bg-[#0A0A0F] py-24">
      <div className="max-w-[1440px] mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-[12px] font-semibold text-[#22D3EE] tracking-[0.15em] uppercase">
            HOW IT WORKS
          </span>
          <h2 className="mt-3 font-display text-[28px] font-semibold text-[#F1F5F9]">
            From Idea to Execution in 4 Steps
          </h2>
        </div>

        {/* Steps */}
        <div className="relative flex flex-col md:flex-row items-start md:items-center justify-center gap-8 md:gap-0">
          {steps.map((step, i) => (
            <div key={step.num} className="flex items-center md:flex-col md:items-center flex-1 relative">
              {/* Connecting line (desktop) */}
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-6 left-[calc(50%+24px)] right-[calc(-50%+24px)] h-px border-t border-dashed border-[rgba(255,255,255,0.06)]" />
              )}

              {/* Number Circle */}
              <div
                className={`w-12 h-12 rounded-full border-2 border-[#22D3EE] bg-[#0A0A0F] flex items-center justify-center shrink-0 z-10 transition-all duration-500 ${
                  inView ? 'scale-100' : 'scale-0'
                }`}
                style={{ transitionDelay: `${i * 200}ms`, transitionTimingFunction: 'cubic-bezier(0.34,1.56,0.64,1)' }}
              >
                <span className="text-[18px] font-bold text-[#22D3EE]">{step.num}</span>
              </div>

              {/* Text */}
              <div
                className={`ml-5 md:ml-0 md:mt-4 md:text-center transition-all duration-500 ${
                  inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'
                }`}
                style={{ transitionDelay: `${i * 200 + 100}ms` }}
              >
                <h3 className="text-[15px] font-semibold text-[#F1F5F9]">{step.title}</h3>
                <p className="text-[13px] text-[#94A3B8] max-w-[200px] md:mx-auto mt-1">
                  {step.desc}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Section: Screenshots Showcase ─── */
function ShowcaseSection() {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.15 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const screenshots = [
    { image: '/feature-strategy-builder.png', caption: 'Visual Strategy Builder' },
    { image: '/feature-backtest.png', caption: 'Backtesting & Analytics' },
    { image: '/feature-live-trading.png', caption: 'Live Trading Terminal' },
  ];

  return (
    <section ref={ref} className="w-full bg-[#030305] py-24">
      <div className="max-w-[1440px] mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-[12px] font-semibold text-[#22D3EE] tracking-[0.15em] uppercase">
            PLATFORM PREVIEW
          </span>
          <h2 className="mt-3 font-display text-[28px] font-semibold text-[#F1F5F9]">
            Built for Serious Traders
          </h2>
        </div>

        {/* Screenshot Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {screenshots.map((shot, i) => (
            <div
              key={shot.caption}
              className={`group relative bg-[#12121A] border border-[rgba(255,255,255,0.06)] rounded-[12px] overflow-hidden transition-all duration-500 hover:border-[rgba(255,255,255,0.10)] ${
                inView ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-6'
              }`}
              style={{ transitionDelay: `${i * 100}ms` }}
            >
              <div className="aspect-[4/3] overflow-hidden">
                <img
                  src={shot.image}
                  alt={shot.caption}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              {/* Bottom Overlay */}
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#12121A] via-[#12121A]/80 to-transparent pt-12 pb-4 px-4">
                <span className="text-[14px] font-medium text-[#F1F5F9]">{shot.caption}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Section: Pricing ─── */
const plans = [
  {
    name: 'Starter',
    price: '\u20B90',
    period: '/month',
    features: [
      '3 Active Strategies',
      'Basic Backtesting (1 year data)',
      'Paper Trading (\u20B91L virtual)',
      'NSE Cash & F&O',
      'Community Support',
    ],
    cta: 'Get Started Free',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '\u20B92,999',
    period: '/month',
    badge: 'MOST POPULAR',
    features: [
      '25 Active Strategies',
      'Advanced Backtesting (10+ years)',
      'Paper Trading (\u20B910L virtual)',
      'All Segments (Stocks, F&O, Commodity)',
      'Broker Integration (Angel, Zerodha, Fyers)',
      'Risk Management Suite',
      'Priority Support',
    ],
    cta: 'Start Pro Trial',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    features: [
      'Unlimited Strategies',
      'API Access',
      'Custom Indicators',
      'Multi-Account Management',
      'Dedicated Account Manager',
      'SLA & Onboarding',
    ],
    cta: 'Contact Sales',
    highlighted: false,
  },
];

function PricingSection() {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.15 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="pricing" ref={ref} className="w-full bg-[#0A0A0F] py-24">
      <div className="max-w-[1440px] mx-auto px-6">
        {/* Section Header */}
        <div className="text-center mb-16">
          <span className="text-[12px] font-semibold text-[#22D3EE] tracking-[0.15em] uppercase">
            PRICING
          </span>
          <h2 className="mt-3 font-display text-[28px] font-semibold text-[#F1F5F9]">
            Start Free, Scale as You Grow
          </h2>
          <p className="mt-3 text-[16px] text-[#94A3B8]">
            All plans include our visual strategy builder and backtesting engine
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-[1120px] mx-auto">
          {plans.map((plan, i) => (
            <div
              key={plan.name}
              className={`relative bg-[#12121A] border rounded-[12px] p-6 transition-all duration-500 hover:border-[rgba(255,255,255,0.10)] ${
                plan.highlighted
                  ? 'border-[rgba(34,211,238,0.40)] animate-glow-pulse'
                  : 'border-[rgba(255,255,255,0.06)]'
              } ${inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'}`}
              style={{ transitionDelay: `${i * 80}ms` }}
            >
              {/* Badge */}
              {plan.badge && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="px-3 py-1 bg-[#22D3EE] text-[#030305] text-[11px] font-bold rounded-full">
                    {plan.badge}
                  </span>
                </div>
              )}

              {/* Plan Name */}
              <h3
                className={`text-[18px] font-semibold mt-2 ${
                  plan.highlighted ? 'text-[#22D3EE]' : 'text-[#F1F5F9]'
                }`}
              >
                {plan.name}
              </h3>

              {/* Price */}
              <div className="mt-3 flex items-baseline gap-1">
                <span className="font-display text-[36px] font-bold text-[#F1F5F9]">
                  {plan.price}
                </span>
                {plan.period && (
                  <span className="text-[14px] text-[#64748B]">{plan.period}</span>
                )}
              </div>

              {/* Features */}
              <ul className="mt-6 flex flex-col gap-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5">
                    <Check size={16} className="text-[#10B981] shrink-0 mt-0.5" />
                    <span className="text-[14px] text-[#94A3B8]">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button
                className={`mt-6 w-full py-2.5 text-[14px] font-semibold rounded-[4px] transition-all duration-200 active:scale-[0.98] ${
                  plan.highlighted
                    ? 'bg-[#22D3EE] text-[#030305] hover:brightness-110 hover:shadow-[0_0_20px_rgba(34,211,238,0.15)]'
                    : 'border border-[rgba(255,255,255,0.10)] text-[#F1F5F9] hover:bg-[#1A1A25] hover:border-[rgba(255,255,255,0.14)]'
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─── Section: CTA ─── */
function CTASection() {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true);
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section ref={ref} className="w-full bg-[#030305] py-24">
      <div
        className={`max-w-[640px] mx-auto px-6 text-center transition-all duration-600 ${
          inView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}
      >
        <h2 className="font-display text-[28px] font-semibold text-[#F1F5F9]">
          Ready to Forge Your Trading Edge?
        </h2>
        <p className="mt-4 text-[16px] text-[#94A3B8] max-w-[560px] mx-auto">
          Join 12,000+ traders building and deploying strategies on TradeForge AI
        </p>
        <div className="mt-8">
          <a
            href="/app"
            className="inline-flex items-center px-8 py-3.5 bg-[#22D3EE] text-[#030305] text-[16px] font-semibold rounded-[4px] hover:brightness-110 transition-all duration-200 hover:shadow-[0_0_30px_rgba(34,211,238,0.20)] active:scale-[0.98]"
          >
            Start Building Free
          </a>
        </div>
        <p className="mt-4 text-[12px] text-[#64748B]">No credit card required</p>
      </div>
    </section>
  );
}

/* ─── Home Page ─── */
export default function Home() {
  return (
    <div className="min-h-[100dvh]">
      <Navbar />
      <HeroSection />
      <StatsSection />
      <FeaturesSection />
      <HowItWorksSection />
      <ShowcaseSection />
      <PricingSection />
      <CTASection />
      <Footer />
    </div>
  );
}
