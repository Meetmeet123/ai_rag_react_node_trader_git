import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Search, Bell, Circle, LogOut, User } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function AppTopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : user?.username?.slice(0, 2).toUpperCase() || 'T';

  return (
    <header className="h-12 shrink-0 bg-[#0A0A0F] border-b border-[rgba(255,255,255,0.06)] flex items-center px-4 z-40">
      <div className="flex items-center justify-between w-full">
        {/* Left: Logo */}
        <div className="flex items-center gap-2 shrink-0">
          <img src="/icon-logo.svg" alt="" className="w-6 h-6" />
          <span className="font-display text-[15px] font-semibold text-[#F1F5F9]">
            TradeForge
          </span>
          <span className="text-[11px] text-[#64748B] bg-[#12121A] px-1.5 py-0.5 rounded-[4px] ml-1">
            AI
          </span>
        </div>

        {/* Center: Search */}
        <div className="hidden md:flex items-center w-[320px]">
          <div className="relative w-full">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
            <input
              type="text"
              placeholder="Search strategies, symbols..."
              className="w-full h-8 pl-9 pr-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[13px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] focus:shadow-[0_0_0_2px_rgba(34,211,238,0.08)] transition-all"
            />
          </div>
        </div>

        {/* Right: Status, Notifications, User */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Market Status */}
          <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-[rgba(16,185,129,0.15)] rounded-full">
            <Circle size={6} className="text-[#10B981] fill-[#10B981]" />
            <span className="text-[11px] font-medium text-[#10B981]">Live</span>
          </div>

          {/* Notifications */}
          <button className="w-8 h-8 flex items-center justify-center rounded-[4px] text-[#64748B] hover:text-[#F1F5F9] hover:bg-[#12121A] transition-all relative">
            <Bell size={16} />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-[#EF4444] rounded-full" />
          </button>

          {/* User Menu */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="w-7 h-7 rounded-full bg-[#22D3EE] flex items-center justify-center text-[#030305] text-[11px] font-bold cursor-pointer hover:brightness-110 transition-all"
              title={user?.username || 'User'}
            >
              {initials}
            </button>

            {menuOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setMenuOpen(false)}
                />
                <div className="absolute right-0 top-9 z-50 w-56 bg-[#12121A] border border-[rgba(255,255,255,0.08)] rounded-[8px] shadow-xl py-2">
                  <div className="px-3 py-2 border-b border-[rgba(255,255,255,0.06)]">
                    <p className="text-[13px] font-medium text-[#F1F5F9]">
                      {user?.full_name || user?.username || 'Trader'}
                    </p>
                    <p className="text-[11px] text-[#64748B]">{user?.email}</p>
                  </div>

                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      navigate('/app/settings');
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-[#94A3B8] hover:bg-[rgba(255,255,255,0.04)] hover:text-[#F1F5F9] transition-colors"
                  >
                    <User size={14} />
                    Settings
                  </button>

                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-[13px] text-[#EF4444] hover:bg-[rgba(239,68,68,0.08)] transition-colors"
                  >
                    <LogOut size={14} />
                    Logout
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
