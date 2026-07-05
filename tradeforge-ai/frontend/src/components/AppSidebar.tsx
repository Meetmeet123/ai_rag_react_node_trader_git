import { useLocation, useNavigate } from 'react-router';
import {
  LayoutDashboard,
  GitBranch,
  History,
  Shield,
  Zap,
  BarChart3,
  Settings,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const topNavItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/app' },
  { icon: GitBranch, label: 'Strategies', path: '/app/strategies' },
  { icon: History, label: 'Backtest', path: '/app/backtest' },
  { icon: Shield, label: 'Paper Trading', path: '/app/paper' },
  { icon: Zap, label: 'Live Trading', path: '/app/live' },
  { icon: BarChart3, label: 'Analytics', path: '/app/analytics' },
];

const bottomNavItems = [
  { icon: Settings, label: 'Settings', path: '/app/settings' },
  { icon: HelpCircle, label: 'Help', path: '#' },
];

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export default function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    if (path === '/app') {
      return location.pathname === '/app' || location.pathname === '/app/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      className={`shrink-0 h-[calc(100vh-48px-32px)] bg-[#0D0D14] border-r border-[rgba(255,255,255,0.06)] flex flex-col transition-all duration-200 ${
        collapsed ? 'w-14' : 'w-[200px]'
      }`}
    >
      {/* Navigation Items */}
      <nav className="flex-1 py-2 flex flex-col gap-0.5 overflow-y-auto">
        {topNavItems.map((item) => {
          const active = isActive(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`relative flex items-center gap-3 h-10 mx-1.5 rounded-[4px] transition-all duration-150 group ${
                active
                  ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]'
                  : 'text-[#64748B] hover:bg-[#1A1A25] hover:text-[#94A3B8]'
              } ${collapsed ? 'justify-center px-0' : 'px-3'}`}
            >
              {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#22D3EE] rounded-r-full" />
              )}
              <item.icon size={20} className="shrink-0" />
              {!collapsed && (
                <span className="text-[13px] font-medium truncate">{item.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="py-2 flex flex-col gap-0.5 border-t border-[rgba(255,255,255,0.06)]">
        {bottomNavItems.map((item) => (
          <button
            key={item.label}
            onClick={() => item.path !== '#' && navigate(item.path)}
            className={`relative flex items-center gap-3 h-10 mx-1.5 rounded-[4px] transition-all duration-150 group ${
              isActive(item.path)
                ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]'
                : 'text-[#64748B] hover:bg-[#1A1A25] hover:text-[#94A3B8]'
            } ${collapsed ? 'justify-center px-0' : 'px-3'}`}
          >
            <item.icon size={20} className="shrink-0" />
            {!collapsed && (
              <span className="text-[13px] font-medium truncate">{item.label}</span>
            )}
          </button>
        ))}

        {/* Collapse Toggle */}
        <button
          onClick={onToggle}
          className="flex items-center justify-center h-8 mx-1.5 mt-1 rounded-[4px] text-[#64748B] hover:bg-[#1A1A25] hover:text-[#94A3B8] transition-all"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  );
}
