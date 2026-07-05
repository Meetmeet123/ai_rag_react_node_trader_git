import { Routes, Route } from 'react-router';
import Home from './pages/Home';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Strategies from './pages/Strategies';
import Backtest from './pages/Backtest';
import PaperTrading from './pages/PaperTrading';
import LiveTrading from './pages/LiveTrading';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';

export default function App() {
  return (
    <Routes>
      {/* Landing page - no layout */}
      <Route path="/" element={<Home />} />

      {/* Auth pages */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* App pages - with shell layout and auth guard */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/app" element={<Dashboard />} />
        <Route path="/app/strategies" element={<Strategies />} />
        <Route path="/app/backtest" element={<Backtest />} />
        <Route path="/app/paper" element={<PaperTrading />} />
        <Route path="/app/live" element={<LiveTrading />} />
        <Route path="/app/analytics" element={<Analytics />} />
        <Route path="/app/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
