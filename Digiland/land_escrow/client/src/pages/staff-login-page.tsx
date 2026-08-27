import React, { useState } from 'react';
import {
  ShieldCheck,
  Lock,
  Mail,
  KeyRound,
  UserCheck,
  Scale,
  Briefcase,
  AlertCircle,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Building2,
} from 'lucide-react';
import { Button } from '../components/ui/button.js';
import { Input } from '../components/ui/input.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card.js';
import { Badge } from '../components/ui/badge.js';

interface StaffLoginPageProps {
  onLoginSuccess?: (userData: any, tokens: any) => void;
  onNavigateToApp?: () => void;
}

export const StaffLoginPage: React.FC<StaffLoginPageProps> = ({
  onLoginSuccess,
  onNavigateToApp,
}) => {
  const [staffRole, setStaffRole] = useState<'Agent' | 'Lawyer'>('Agent');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/auth/login/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Digiland-Portal': 'staff',
        },
        body: JSON.stringify({
          email,
          password,
          mfa_code: mfaCode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Authentication failed');
      }

      if (onLoginSuccess) {
        onLoginSuccess(data.user || { email, role: staffRole }, data);
      } else {
        window.location.href = '/parcels/';
      }
    } catch (err: any) {
      setError(err.message || 'Invalid credentials or staff partition access denied.');
    } finally {
      setLoading(false);
    }
  };

  const fillQuickDemo = (role: 'Agent' | 'Lawyer') => {
    setStaffRole(role);
    if (role === 'Agent') {
      setEmail('agent@digiland.co.ke');
      setPassword('AgentPass123!');
      setLicenseNumber('EARB/2026/0491');
    } else {
      setEmail('lawyer@digiland.co.ke');
      setPassword('LawyerPass123!');
      setLicenseNumber('LSK/2026/1842');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-white relative overflow-hidden">
      {/* Background glow effects */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[800px] rounded-full bg-emerald-600/10 blur-[150px]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[400px] w-[400px] rounded-full bg-purple-600/10 blur-[120px]" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold uppercase tracking-widest mb-4">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          staff.digiland.co.ke • Staff Portal
        </div>

        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          Digiland Staff Workspace
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          Dedicated security portal for registered Real Estate Agents, Advocates, and Land Officials.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <Card className="bg-slate-900/90 border-slate-800 shadow-2xl backdrop-blur-xl rounded-2xl text-slate-100">
          
          {/* Dual Role Selector Tab */}
          <div className="grid grid-cols-2 p-1.5 bg-slate-950/80 rounded-t-2xl border-b border-slate-800">
            <button
              type="button"
              onClick={() => setStaffRole('Agent')}
              className={`py-3 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 ${
                staffRole === 'Agent'
                  ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-950/50'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <Briefcase className="w-4 h-4" />
              <span>Agent Portal</span>
            </button>

            <button
              type="button"
              onClick={() => setStaffRole('Lawyer')}
              className={`py-3 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 ${
                staffRole === 'Lawyer'
                  ? 'bg-purple-600 text-white shadow-lg shadow-purple-950/50'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <Scale className="w-4 h-4" />
              <span>Advocate Desk</span>
            </button>
          </div>

          <CardContent className="p-6 sm:p-8 space-y-6">
            
            {/* Quick Demo Pre-fill Pill for testing */}
            <div className="flex items-center justify-between text-xs bg-slate-950/60 p-2.5 rounded-xl border border-slate-800">
              <span className="text-slate-400">Quick Test Credentials:</span>
              <button
                type="button"
                onClick={() => fillQuickDemo(staffRole)}
                className="text-emerald-400 hover:text-emerald-300 font-bold hover:underline"
              >
                Auto-fill {staffRole} Demo
              </button>
            </div>

            {error && (
              <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/30 text-red-300 text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div>{error}</div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Official Email Address
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <Input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={staffRole === 'Agent' ? 'agent@company.co.ke' : 'advocate@lawfirm.co.ke'}
                    className="pl-9 bg-slate-950 border-slate-800 text-white placeholder-slate-500 text-sm py-2.5 rounded-xl focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <Input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="pl-9 bg-slate-950 border-slate-800 text-white placeholder-slate-500 text-sm py-2.5 rounded-xl focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  {staffRole === 'Agent' ? 'EARB Agent License No. (Optional)' : 'LSK Advocate Practicing No. (Optional)'}
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Building2 className="w-4 h-4" />
                  </div>
                  <Input
                    type="text"
                    value={licenseNumber}
                    onChange={(e) => setLicenseNumber(e.target.value)}
                    placeholder={staffRole === 'Agent' ? 'EARB/2026/XXXX' : 'P105/XXXX/2026'}
                    className="pl-9 bg-slate-950 border-slate-800 text-white placeholder-slate-500 text-sm py-2.5 rounded-xl focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-1.5">
                  MFA Authenticator Code (If Enabled)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <KeyRound className="w-4 h-4" />
                  </div>
                  <Input
                    type="text"
                    maxLength={6}
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    placeholder="6-digit code e.g. 123456"
                    className="pl-9 bg-slate-950 border-slate-800 text-white placeholder-slate-500 text-sm py-2.5 rounded-xl focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 tracking-widest font-mono"
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                className={`w-full py-3 rounded-xl font-bold text-white shadow-lg flex items-center justify-center gap-2 ${
                  staffRole === 'Agent'
                    ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-950/50'
                    : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-950/50'
                }`}
              >
                {loading ? (
                  <span>Authenticating Staff...</span>
                ) : (
                  <>
                    <span>Sign In to {staffRole} Desk</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </Button>
            </form>

            <div className="pt-4 border-t border-slate-800 text-center space-y-3">
              <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Protected by Digiland Audit Security Protocol</span>
              </div>

              {onNavigateToApp && (
                <div>
                  <button
                    type="button"
                    onClick={onNavigateToApp}
                    className="text-xs text-slate-400 hover:text-emerald-400 transition"
                  >
                    Buyer or Seller? Return to App Portal
                  </button>
                </div>
              )}
            </div>

          </CardContent>
        </Card>
      </div>
    </div>
  );
};
