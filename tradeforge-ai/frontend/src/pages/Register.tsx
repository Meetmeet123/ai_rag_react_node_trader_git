import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { Eye, EyeOff, Lock, Mail, User } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [form, setForm] = useState({
    email: '',
    username: '',
    full_name: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const update = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!form.email.trim() || !form.username.trim() || !form.password) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (form.password !== form.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (form.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        email: form.email.trim(),
        username: form.username.trim(),
        password: form.password,
        full_name: form.full_name.trim() || undefined,
      });
      navigate('/app', { replace: true });
    } catch (err) {
      const message =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: string }).detail)
          : 'Registration failed. Please try again.';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#030305] px-4 py-8">
      <div className="w-full max-w-[420px] bg-[#0A0A0F] border border-[rgba(255,255,255,0.06)] rounded-[12px] p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[rgba(34,211,238,0.12)] mb-4">
            <User className="w-6 h-6 text-[#22D3EE]" />
          </div>
          <h1 className="text-[24px] font-semibold text-[#F1F5F9]">Create account</h1>
          <p className="mt-2 text-[14px] text-[#64748B]">
            Start building trading strategies with AI
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-[13px] font-medium text-[#94A3B8] mb-1.5">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
              <input
                data-testid="register-email"
                type="email"
                value={form.email}
                onChange={(e) => update('email', e.target.value)}
                placeholder="you@example.com"
                className="w-full h-10 pl-10 pr-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[14px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-[13px] font-medium text-[#94A3B8] mb-1.5">Username</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
              <input
                data-testid="register-username"
                type="text"
                value={form.username}
                onChange={(e) => update('username', e.target.value)}
                placeholder="trader123"
                className="w-full h-10 pl-10 pr-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[14px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-[13px] font-medium text-[#94A3B8] mb-1.5">
              Full Name <span className="text-[#475569]">(optional)</span>
            </label>
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => update('full_name', e.target.value)}
              placeholder="John Doe"
              className="w-full h-10 px-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[14px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
            />
          </div>

          <div>
            <label className="block text-[13px] font-medium text-[#94A3B8] mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
              <input
                data-testid="register-password"
                type={showPassword ? 'text' : 'password'}
                value={form.password}
                onChange={(e) => update('password', e.target.value)}
                placeholder="••••••••"
                className="w-full h-10 pl-10 pr-10 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[14px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
                required
                minLength={6}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#F1F5F9]"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-[13px] font-medium text-[#94A3B8] mb-1.5">
              Confirm Password
            </label>
            <input
              data-testid="register-confirm-password"
              type={showPassword ? 'text' : 'password'}
              value={form.confirmPassword}
              onChange={(e) => update('confirmPassword', e.target.value)}
              placeholder="••••••••"
              className="w-full h-10 px-3 bg-[#06060A] border border-[rgba(255,255,255,0.06)] rounded-[6px] text-[14px] text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#22D3EE] transition-all"
              required
            />
          </div>

          <button
            data-testid="register-submit"
            type="submit"
            disabled={isSubmitting}
            className="w-full h-10 bg-[#22D3EE] text-[#030305] text-[14px] font-semibold rounded-[6px] hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        {/* Footer */}
        <p className="mt-6 text-center text-[13px] text-[#64748B]">
          Already have an account?{' '}
          <Link to="/login" className="text-[#22D3EE] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
