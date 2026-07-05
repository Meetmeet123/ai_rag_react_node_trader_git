import { useState } from 'react';
import {
  User,
  Link,
  Shield,
  GitBranch,
  Bell,
  Settings as SettingsIcon,
} from 'lucide-react';
import AccountSettings from './settings/AccountSettings';
import BrokerAPISettings from './settings/BrokerAPISettings';
import RiskManagementSettings from './settings/RiskManagementSettings';
import StrategyDefaults from './settings/StrategyDefaults';
import NotificationSettings from './settings/NotificationSettings';
import PreferenceSettings from './settings/PreferenceSettings';

interface SettingsTab {
  id: string;
  label: string;
  icon: React.ElementType;
  component: React.ElementType;
}

const tabs: SettingsTab[] = [
  { id: 'account', label: 'Account', icon: User, component: AccountSettings },
  { id: 'brokers', label: 'Brokers', icon: Link, component: BrokerAPISettings },
  { id: 'risk', label: 'Risk Management', icon: Shield, component: RiskManagementSettings },
  { id: 'strategies', label: 'Strategies', icon: GitBranch, component: StrategyDefaults },
  { id: 'notifications', label: 'Notifications', icon: Bell, component: NotificationSettings },
  { id: 'platform', label: 'Platform', icon: SettingsIcon, component: PreferenceSettings },
];

export default function Settings() {
  const [activeTab, setActiveTab] = useState('account');

  const activeTabData = tabs.find((t) => t.id === activeTab) || tabs[0];
  const ActiveComponent = activeTabData.component;

  return (
    <div className="flex h-full">
      {/* Settings Sidebar */}
      <aside className="shrink-0 w-[200px] bg-[#12121A] border-r border-[rgba(255,255,255,0.06)] overflow-y-auto">
        <nav className="py-2">
          {tabs.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative flex items-center gap-2.5 w-full h-10 px-4 transition-all duration-150 ${
                  active
                    ? 'bg-[rgba(34,211,238,0.12)] text-[#22D3EE]'
                    : 'text-[#64748B] hover:bg-[#1A1A25] hover:text-[#94A3B8]'
                }`}
              >
                {active && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[#22D3EE] rounded-r-full" />
                )}
                <tab.icon size={18} className="shrink-0" />
                <span className="text-[13px] font-medium">{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Settings Content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <ActiveComponent />
      </div>
    </div>
  );
}
