import { Routes, Route, Navigate } from 'react-router';
import Home from './pages/Home';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Strategies from './pages/Strategies';
import Backtest from './pages/Backtest';
import PaperTrading from './pages/PaperTrading';
import LiveTrading from './pages/LiveTrading';
import Brokers from './pages/Brokers';
import Analytics from './pages/Analytics';
import Training from './pages/Training';
import AIChat from './pages/AIChat';
import Settings from './pages/Settings';
import AuditLogs from './pages/AuditLogs';
import LiveApprovals from './pages/admin/LiveApprovals';
import Login from './pages/Login';
import Register from './pages/Register';
import { useAuth } from './contexts/AuthContext';

function AdminAuditLogs() {
  const { user } = useAuth();
  if (user?.role !== 'admin') {
    return <Navigate to="/app" replace />;
  }
  return <AuditLogs />;
}

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
        <Route path="/app/brokers" element={<Brokers />} />
        <Route path="/app/analytics" element={<Analytics />} />
        <Route path="/app/training" element={<Training />} />
        <Route path="/app/ai" element={<AIChat />} />
        <Route path="/app/settings" element={<Settings />} />
        <Route path="/app/admin/audit-logs" element={<AdminAuditLogs />} />
        <Route path="/app/admin/live-approvals" element={<LiveApprovals />} />
      </Route>
    </Routes>
  );
}
