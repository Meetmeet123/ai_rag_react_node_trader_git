import { useState } from 'react';
import MarketTickerBar from './dashboard/MarketTickerBar';
import WatchlistPanel from './dashboard/WatchlistPanel';
import CandlestickChart from './dashboard/CandlestickChart';
import OrderPanel from './dashboard/OrderPanel';
import PositionsTable from './dashboard/PositionsTable';
import ActiveStrategiesPanel from './dashboard/ActiveStrategiesPanel';

export default function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState('RELIANCE');

  return (
    <div className="flex flex-col h-full gap-0">
      {/* Row 1: Market Ticker Strip */}
      <MarketTickerBar />

      {/* Row 2: Three-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Watchlist Panel (25%) */}
        <div className="w-[25%] min-w-[200px] h-full">
          <WatchlistPanel
            selectedSymbol={selectedSymbol}
            onSelectSymbol={setSelectedSymbol}
          />
        </div>

        {/* Center: Main Chart (50%) */}
        <div className="w-[50%] h-full">
          <CandlestickChart symbol={selectedSymbol} />
        </div>

        {/* Right: Order Panel (25%) */}
        <div className="w-[25%] min-w-[180px] h-full">
          <OrderPanel selectedSymbol={selectedSymbol} />
        </div>
      </div>

      {/* Row 3: Positions Table */}
      <PositionsTable />

      {/* Row 4: Active Strategies */}
      <ActiveStrategiesPanel />
    </div>
  );
}
