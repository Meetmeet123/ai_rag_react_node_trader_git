import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';

const navLinks = [
  { label: 'Features', href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'Docs', href: '#' },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 40);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.startsWith('#') && href.length > 1) {
      e.preventDefault();
      const el = document.querySelector(href);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
      setMobileOpen(false);
    }
  };

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 h-16 flex items-center transition-all duration-300 ${
        scrolled
          ? 'bg-[rgba(10,10,15,0.90)] backdrop-blur-md border-b border-[rgba(255,255,255,0.06)]'
          : 'bg-transparent'
      }`}
    >
      <div className="w-full max-w-[1440px] mx-auto px-6 flex items-center justify-between">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 shrink-0">
          <img src="/icon-logo.svg" alt="" className="w-6 h-6" />
          <span className="font-display text-[20px] font-semibold text-[#F1F5F9]">
            TradeForge <span className="text-[#22D3EE]">AI</span>
          </span>
        </a>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={(e) => handleNavClick(e, link.href)}
              className="text-[14px] font-medium text-[#94A3B8] hover:text-[#F1F5F9] transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* CTA Button */}
        <div className="hidden md:block">
          <a
            href="/app"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[#22D3EE] text-[#030305] text-[14px] font-semibold rounded-[4px] hover:brightness-110 transition-all duration-200 hover:shadow-[0_0_20px_rgba(34,211,238,0.15)] active:scale-[0.98]"
          >
            Get Started
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden w-10 h-10 flex items-center justify-center text-[#F1F5F9]"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="absolute top-16 left-0 right-0 bg-[rgba(10,10,15,0.97)] backdrop-blur-lg border-b border-[rgba(255,255,255,0.06)] md:hidden">
          <div className="px-6 py-4 flex flex-col gap-3">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={(e) => handleNavClick(e, link.href)}
                className="text-[14px] font-medium text-[#94A3B8] hover:text-[#F1F5F9] py-2 transition-colors"
              >
                {link.label}
              </a>
            ))}
            <a
              href="/app"
              className="mt-2 inline-flex items-center justify-center px-4 py-2.5 bg-[#22D3EE] text-[#030305] text-[14px] font-semibold rounded-[4px]"
            >
              Get Started
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
