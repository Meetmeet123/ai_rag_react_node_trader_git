import { useState } from 'react';
import { Outlet } from 'react-router';
import AppTopBar from './AppTopBar';
import AppSidebar from './AppSidebar';
import AppBottomBar from './AppBottomBar';

export default function Layout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex flex-col h-[100dvh] bg-bg-void overflow-hidden">
      {/* Top Bar - 48px */}
      <AppTopBar />

      {/* Main Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <AppSidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((c) => !c)}
        />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto bg-[#030305] relative">
          <div className="min-h-full p-4 md:p-6">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Bottom Bar - 32px */}
      <AppBottomBar />
    </div>
  );
}
