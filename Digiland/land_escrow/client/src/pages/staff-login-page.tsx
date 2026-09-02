import React, { useState } from 'react';
import {
  ShieldCheck,
  Lock,
  Mail,
  KeyRound,
  Scale,
  Briefcase,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Building2,
  Smartphone,
  Key,
  MessageSquare,
  ArrowLeft,
  RefreshCw,
} from 'lucide-react';
import { Button } from '../components/ui/button.js';
import { Input } from '../components/ui/input.js';
import { Card, CardContent } from '../components/ui/card.js';

interface StaffLoginPageProps {
  onLoginSuccess?: (userData: any, tokens: any) => void;
  onNavigateToApp?: () => void;
}

type AuthStage = 'credentials' | 'mfa_method_select' | 'mfa_verify';

interface MfaMethod {
  id: 'authenticator' | 'passkey' | 'otp';
  name: string;
  description: string;
  icon: string;
  configured: boolean;
}

export const StaffLoginPage: React.FC<StaffLoginPageProps> = ({
  onLoginSuccess,
  onNavigateToApp,
}) => {
  const [staffRole, setStaffRole] = useState<'Agent' | 'Lawyer'>('Agent');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');

  // Multi-Stage Auth State
  const [stage, setStage] = useState<AuthStage>('credentials');
  const [mfaToken, setMfaToken] = useState<string>('');
  const [availableMethods, setAvailableMethods] = useState<MfaMethod[]>([]);
  const [selectedMethod, setSelectedMethod] = useState<'authenticator' | 'passkey' | 'otp'>('authenticator');
  const [verificationCode, setVerificationCode] = useState('');
  const [otpSentMsg, setOtpSentMsg] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Stage 1: Password Authenticate
  const handleStage1Submit = async (e: React.FormEvent) => {
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
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Authentication failed');
      }

      if (data.mfa_required && data.mfa_token) {
        setMfaToken(data.mfa_token);
        // Fetch available MFA methods for user
        await fetchAvailableMethods(data.mfa_token);
        setStage('mfa_method_select');
      } else if (onLoginSuccess) {
        onLoginSuccess(data.user || { email, role: staffRole }, data);
      } else {
        const dest = staffRole === 'Agent' ? '/agent/dashboard/' : (staffRole === 'Surveyor' ? '/surveyor/dashboard/' : '/staff/dashboard/');
        window.location.href = dest;
      }
    } catch (err: any) {
      setError(err.message || 'Invalid credentials or staff partition access denied.');
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableMethods = async (token: string) => {
    try {
      const res = await fetch('/api/v1/auth/mfa/available-methods/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mfa_token: token }),
      });
      if (res.ok) {
        const data = await res.json();
        setAvailableMethods(data.methods || []);
        if (data.default_method) {
          setSelectedMethod(data.default_method);
        }
      }
    } catch (err) {
      console.warn('Failed to load available MFA methods:', err);
    }
  };

  // Stage 2: Method Selected -> Transition to Stage 3 or send OTP / trigger WebAuthn
  const handleSelectMethod = async (method: 'authenticator' | 'passkey' | 'otp') => {
    setSelectedMethod(method);
    setError(null);

    if (method === 'otp') {
      setLoading(true);
      try {
        const res = await fetch('/api/v1/auth/mfa/send-otp/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mfa_token: mfaToken }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to send OTP code');
        setOtpSentMsg(data.message || 'Code sent to your email.');
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    } else if (method === 'passkey') {
      if (typeof window !== 'undefined' && window.navigator?.credentials?.get) {
        try {
          const chalBytes = new Uint8Array(32);
          crypto.getRandomValues(chalBytes);
          const credential = await window.navigator.credentials.get({
            publicKey: {
              challenge: chalBytes,
              timeout: 60000,
              userVerification: 'preferred',
            },
          }) as any;

          if (credential) {
            handleVerifyWithCredential('passkey', credential.id || 'passkey_assertion');
            return;
          }
        } catch (passkeyErr) {
          console.warn('Native WebAuthn prompt cancelled or fallback used:', passkeyErr);
        }
      }
    }

    setStage('mfa_verify');
  };

  const handleVerifyWithCredential = async (method: string, codeOrCredential: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/auth/mfa/verify-challenge/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          challenge_token: mfaToken,
          method: method,
          code: codeOrCredential,
          credential: { id: codeOrCredential, rawId: codeOrCredential, type: 'public-key' },
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Verification failed');
      }

      if (onLoginSuccess) {
        onLoginSuccess(data.user || { email, role: staffRole }, data);
      } else {
        const dest = staffRole === 'Agent' ? '/agent/dashboard/' : (staffRole === 'Surveyor' ? '/surveyor/dashboard/' : '/staff/dashboard/');
        window.location.href = dest;
      }
    } catch (err: any) {
      setError(err.message || 'MFA verification failed. Check code and try again.');
    } finally {
      setLoading(false);
    }
  };

  // Stage 3: MFA Challenge Verification Submit
  const handleStage3Verify = async (e: React.FormEvent) => {
    e.preventDefault();
    handleVerifyWithCredential(selectedMethod, verificationCode);
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
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-900 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[800px] rounded-full bg-emerald-500/5 blur-[150px]" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center relative z-10">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold uppercase tracking-widest mb-4">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          staff.digiland.co.ke • Staff Portal
        </div>

        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
          Digiland Staff Workspace
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Dedicated Zero-Trust Portal for Registered Agents, Advocates, and Land Officials.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <Card className="bg-white border-emerald-100 shadow-xl shadow-emerald-950/5 rounded-2xl text-slate-900">

          {/* Role selector tab (Only on credentials stage) */}
          {stage === 'credentials' && (
            <div className="grid grid-cols-2 p-1.5 bg-slate-100/80 rounded-t-2xl border-b border-slate-200">
              <button
                type="button"
                onClick={() => setStaffRole('Agent')}
                className={`py-3 px-4 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 ${
                  staffRole === 'Agent'
                    ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white'
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
                    ? 'bg-purple-600 text-white shadow-md shadow-purple-600/20'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-white'
                }`}
              >
                <Scale className="w-4 h-4" />
                <span>Advocate Desk</span>
              </button>
            </div>
          )}

          <CardContent className="p-6 sm:p-8 space-y-6">

            {error && (
              <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/30 text-red-300 text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div>{error}</div>
              </div>
            )}

            {/* STAGE 1: CREDENTIALS INPUT */}
            {stage === 'credentials' && (
              <>
                <div className="flex items-center justify-between text-xs bg-emerald-50 p-2.5 rounded-xl border border-emerald-100">
                  <span className="text-slate-600 font-medium">Quick Test Credentials:</span>
                  <button
                    type="button"
                    onClick={() => fillQuickDemo(staffRole)}
                    className="text-emerald-700 hover:text-emerald-800 font-bold hover:underline"
                  >
                    Auto-fill {staffRole} Demo
                  </button>
                </div>

                <form onSubmit={handleStage1Submit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      Official Email Address
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                        <Mail className="w-4 h-4" />
                      </div>
                      <Input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder={staffRole === 'Agent' ? 'agent@company.co.ke' : 'advocate@lawfirm.co.ke'}
                        className="pl-9 bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400 text-sm py-2.5 rounded-xl focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      Password
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                        <Lock className="w-4 h-4" />
                      </div>
                      <Input
                        type="password"
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••••••"
                        className="pl-9 bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400 text-sm py-2.5 rounded-xl focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      {staffRole === 'Agent' ? 'EARB Agent License No. (Optional)' : 'LSK Advocate Practicing No. (Optional)'}
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                        <Building2 className="w-4 h-4" />
                      </div>
                      <Input
                        type="text"
                        value={licenseNumber}
                        onChange={(e) => setLicenseNumber(e.target.value)}
                        placeholder={staffRole === 'Agent' ? 'EARB/2026/XXXX' : 'P105/XXXX/2026'}
                        className="pl-9 bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400 text-sm py-2.5 rounded-xl focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className={`w-full py-3 rounded-xl font-bold text-white shadow-md flex items-center justify-center gap-2 ${
                      staffRole === 'Agent'
                        ? 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/20'
                        : 'bg-purple-600 hover:bg-purple-700 shadow-purple-600/20'
                    }`}
                  >
                    {loading ? (
                      <span>Authenticating Credentials...</span>
                    ) : (
                      <>
                        <span>Continue to Verification</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </Button>
                </form>
              </>
            )}

            {/* STAGE 2: MFA METHOD SELECTION */}
            {stage === 'mfa_method_select' && (
              <div className="space-y-4">
                <div className="text-center space-y-1">
                  <h3 className="text-xl font-extrabold text-slate-900">Verify Your Identity</h3>
                  <p className="text-xs text-slate-600">Select how you'd like to verify your DigiLand account.</p>
                </div>

                <div className="space-y-3 pt-2">
                  {availableMethods.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectMethod(m.id)}
                      className="w-full text-left p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:border-emerald-600 hover:bg-white transition flex items-center justify-between group shadow-xs"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-600 group-hover:scale-105 transition">
                          {m.id === 'authenticator' && <Smartphone className="w-5 h-5" />}
                          {m.id === 'passkey' && <Key className="w-5 h-5" />}
                          {m.id === 'otp' && <MessageSquare className="w-5 h-5" />}
                        </div>
                        <div>
                          <div className="text-sm font-bold text-slate-900">{m.name}</div>
                          <div className="text-xs text-slate-500">{m.description}</div>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 group-hover:translate-x-1 transition" />
                    </button>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => setStage('credentials')}
                  className="w-full py-2 text-xs text-slate-500 hover:text-slate-900 flex items-center justify-center gap-1 mt-4 font-medium"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Back to Sign In</span>
                </button>
              </div>
            )}

            {/* STAGE 3: MFA CHALLENGE VERIFICATION */}
            {stage === 'mfa_verify' && (
              <div className="space-y-4">
                <div className="text-center space-y-1">
                  <h3 className="text-xl font-extrabold text-slate-900">Enter Security Code</h3>
                  <p className="text-xs text-slate-600">
                    {selectedMethod === 'authenticator' && 'Enter the 6-digit code from Google Authenticator / Authy.'}
                    {selectedMethod === 'otp' && 'Enter the 6-digit code sent to your registered email.'}
                    {selectedMethod === 'passkey' && 'Perform passkey biometric or security key assertion.'}
                  </p>
                </div>

                {otpSentMsg && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl text-center font-medium">
                    {otpSentMsg}
                  </div>
                )}

                <form onSubmit={handleStage3Verify} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                      6-Digit Security Code
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                        <KeyRound className="w-4 h-4" />
                      </div>
                      <Input
                        type="text"
                        required
                        maxLength={6}
                        value={verificationCode}
                        onChange={(e) => setVerificationCode(e.target.value)}
                        placeholder="123456"
                        className="pl-9 bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400 text-sm py-2.5 rounded-xl focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 tracking-widest font-mono text-center text-lg"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-3 rounded-xl font-bold text-white shadow-md bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/20 flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <span>Verifying Security Code...</span>
                    ) : (
                      <>
                        <span>Verify & Sign In</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </Button>

                  <div className="flex items-center justify-between text-xs pt-2">
                    <button
                      type="button"
                      onClick={() => setStage('mfa_method_select')}
                      className="text-slate-500 hover:text-slate-900 flex items-center gap-1 font-medium"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      <span>Choose another method</span>
                    </button>

                    {selectedMethod === 'otp' && (
                      <button
                        type="button"
                        onClick={() => handleSelectMethod('otp')}
                        className="text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-bold"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Resend Code</span>
                      </button>
                    )}
                  </div>
                </form>
              </div>
            )}

            <div className="pt-4 border-t border-slate-800 text-center space-y-3">
              <div className="flex items-center justify-center gap-2 text-xs text-slate-400">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Protected by Digiland Audit Security Protocol</span>
              </div>

              {onNavigateToApp && stage === 'credentials' && (
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
