import { Github, Linkedin, MessageCircle } from 'lucide-react';

const productLinks = [
  { label: 'Strategy Builder', href: '#' },
  { label: 'Backtesting', href: '#' },
  { label: 'Paper Trading', href: '#' },
  { label: 'Live Trading', href: '#' },
  { label: 'Analytics', href: '#' },
];

const resourceLinks = [
  { label: 'Documentation', href: '#' },
  { label: 'API Reference', href: '#' },
  { label: 'Blog', href: '#' },
  { label: 'Changelog', href: '#' },
  { label: 'Community', href: '#' },
];

const companyLinks = [
  { label: 'About', href: '#' },
  { label: 'Careers', href: '#' },
  { label: 'Legal', href: '#' },
  { label: 'Privacy', href: '#' },
  { label: 'Terms', href: '#' },
];

export default function Footer() {
  return (
    <footer className="bg-[#0A0A0F] border-t border-[rgba(255,255,255,0.06)]">
      <div className="max-w-[1440px] mx-auto px-6 py-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10">
          {/* Brand */}
          <div>
            <a href="/" className="flex items-center gap-2 mb-4">
              <img src="/icon-logo.svg" alt="" className="w-6 h-6" />
              <span className="font-display text-[18px] font-semibold text-[#F1F5F9]">
                TradeForge <span className="text-[#22D3EE]">AI</span>
              </span>
            </a>
            <p className="text-[13px] text-[#94A3B8] leading-relaxed mb-5">
              India's most advanced algorithmic trading platform. Build, test, and deploy strategies with precision.
            </p>
            <div className="flex items-center gap-3">
              <a href="#" className="w-8 h-8 flex items-center justify-center rounded-[4px] bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
                <MessageCircle size={14} />
              </a>
              <a href="#" className="w-8 h-8 flex items-center justify-center rounded-[4px] bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
                <Linkedin size={14} />
              </a>
              <a href="#" className="w-8 h-8 flex items-center justify-center rounded-[4px] bg-[#12121A] border border-[rgba(255,255,255,0.06)] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#1A1A25] transition-all">
                <Github size={14} />
              </a>
            </div>
          </div>

          {/* Product */}
          <div>
            <h4 className="text-[13px] font-semibold text-[#F1F5F9] uppercase tracking-wider mb-4">
              Product
            </h4>
            <ul className="flex flex-col gap-2.5">
              {productLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="text-[13px] font-semibold text-[#F1F5F9] uppercase tracking-wider mb-4">
              Resources
            </h4>
            <ul className="flex flex-col gap-2.5">
              {resourceLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="text-[13px] font-semibold text-[#F1F5F9] uppercase tracking-wider mb-4">
              Company
            </h4>
            <ul className="flex flex-col gap-2.5">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-[13px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="border-t border-[rgba(255,255,255,0.06)]">
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-[12px] text-[#64748B]">
            &copy; 2025 TradeForge AI, Mumbai, India. All rights reserved.
          </p>
          <p className="text-[12px] text-[#475569]">
            v1.0.0
          </p>
        </div>
      </div>
    </footer>
  );
}
