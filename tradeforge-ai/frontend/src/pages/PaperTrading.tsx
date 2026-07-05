import VirtualCapitalHeader from './paper/VirtualCapitalHeader';
import StrategyDeploymentPanel from './paper/StrategyDeploymentPanel';
import ChartSignalsArea from './paper/ChartSignalsArea';
import VirtualCapitalCard from './paper/VirtualCapitalCard';
import SignalLog from './paper/SignalLog';
import PaperOrderBook from './paper/PaperOrderBook';

export default function PaperTrading() {
  return (
    <div className="flex flex-col h-full -m-4 md:-m-6">
      {/* Banner + Capital Summary */}
      <VirtualCapitalHeader />

      {/* Three-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Strategy List - 20% */}
        <div className="w-[20%] min-w-[180px] shrink-0 overflow-hidden">
          <StrategyDeploymentPanel />
        </div>

        {/* Center: Chart + Signals - 55% */}
        <div className="w-[55%] min-w-0 shrink-0 flex flex-col overflow-hidden">
          <ChartSignalsArea />
        </div>

        {/* Right: Virtual P&L Card + Controls - 25% */}
        <div className="w-[25%] min-w-[180px] shrink-0 overflow-y-auto">
          <VirtualCapitalCard />
        </div>
      </div>

      {/* Bottom: Signal Log + Order Book */}
      <div className="shrink-0">
        <SignalLog />
        <PaperOrderBook />
      </div>
    </div>
  );
}
