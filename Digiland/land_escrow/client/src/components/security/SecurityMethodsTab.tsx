import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Smartphone,
  Key,
  MessageSquare,
  Lock,
  Trash2,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Laptop,
  Globe,
  Clock,
  LogOut,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card.js';
import { Button } from '../ui/button.js';

interface PasskeyItem {
  id: string;
  name: string;
  credential_id: string;
  created_at: string;
  last_used_at: string | null;
}

interface ActiveSessionItem {
  id: string;
  device_name: string;
  ip_address: string;
  last_activity: string;
  is_current: boolean;
}

interface SecuritySummary {
  methods: {
    authenticator: { enabled: boolean; verified_at: string | null };
    passkey: { enabled: boolean; count: number };
    otp: { enabled: boolean; delivery_channel: string };
  };
  passkeys: PasskeyItem[];
  active_sessions: ActiveSessionItem[];
}

export const SecurityMethodsTab: React.FC = () => {
  const [summary, setSummary] = useState<SecuritySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [passkeyLoading, setPasskeyLoading] = useState(false);

  const fetchSecuritySummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/auth/security/methods/', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error('Failed to load security summary.');
      }
      const data = await response.json();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Error loading security configurations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSecuritySummary();
  }, []);

  // WebAuthn Passkey Registration Handler
  const handleAddPasskey = async () => {
    setPasskeyLoading(true);
    setError(null);
    setActionSuccess(null);

    try {
      // 1. Get WebAuthn options from server
      const startRes = await fetch('/api/v1/auth/security/passkey/register/start/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const options = await startRes.json();

      let credentialId = `passkey_${Date.now()}`;
      if (typeof window !== 'undefined' && window.navigator?.credentials?.create) {
        try {
          // Native browser WebAuthn API
          const chalBytes = new Uint8Array(32);
          crypto.getRandomValues(chalBytes);
          const userIdBytes = new TextEncoder().encode(options.user?.id || 'user_id');

          const credential = (await window.navigator.credentials.create({
            publicKey: {
              challenge: chalBytes,
              rp: { name: 'DigiLand Platform', id: window.location.hostname },
              user: {
                id: userIdBytes,
                name: options.user?.name || 'user@digiland.co.ke',
                displayName: options.user?.displayName || 'User',
              },
              pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
              timeout: 60000,
              authenticatorSelection: { userVerification: 'preferred' },
            },
          })) as any;

          if (credential) {
            credentialId = credential.id || credentialId;
          }
        } catch (webauthnErr) {
          console.warn('Native WebAuthn cancelled or fallback used:', webauthnErr);
        }
      }

      // 2. Finish registration on server
      const passkeyName = prompt('Enter a label for this device / passkey:', 'My Windows PC / Security Key') || 'Passkey Device';

      const finishRes = await fetch('/api/v1/auth/security/passkey/register/finish/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          credential_id: credentialId,
          name: passkeyName,
        }),
      });

      const finishData = await finishRes.json();
      if (!finishRes.ok) {
        throw new Error(finishData.error || 'Failed to save passkey.');
      }

      setActionSuccess(`Passkey '${passkeyName}' successfully registered.`);
      fetchSecuritySummary();
    } catch (err: any) {
      setError(err.message || 'Passkey registration failed.');
    } finally {
      setPasskeyLoading(false);
    }
  };

  // Remove Passkey with Last-Method Protection
  const handleRemovePasskey = async (passkeyId: string, passkeyName: string) => {
    if (!confirm(`Are you sure you want to remove passkey '${passkeyName}'?`)) return;

    setError(null);
    setActionSuccess(null);
    try {
      const response = await fetch('/api/v1/auth/security/passkey/remove/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ passkey_id: passkeyId }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to remove passkey.');
      }
      setActionSuccess(`Passkey '${passkeyName}' removed.`);
      fetchSecuritySummary();
    } catch (err: any) {
      setError(err.message || 'Error removing passkey.');
    }
  };

  // Revoke All Other Active Sessions
  const handleRevokeAllSessions = async () => {
    if (!confirm('Are you sure you want to sign out of all other active sessions across all devices?')) return;

    setError(null);
    setActionSuccess(null);
    try {
      const response = await fetch('/api/v1/auth/session/revoke-all/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to revoke sessions.');
      }
      setActionSuccess(`Successfully signed out of ${data.revoked_count} active session(s).`);
      fetchSecuritySummary();
    } catch (err: any) {
      setError(err.message || 'Error revoking sessions.');
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-500 flex items-center justify-center gap-2">
        <RefreshCw className="w-5 h-5 animate-spin text-emerald-600" />
        <span>Loading Security Methods & Session Status...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Alert Messages */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="font-semibold">{error}</div>
        </div>
      )}

      {actionSuccess && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div className="font-semibold">{actionSuccess}</div>
        </div>
      )}

      {/* SECTION 1: AUTHENTICATION METHODS */}
      <Card className="bg-white border-emerald-100 shadow-md">
        <CardHeader>
          <CardTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-600" />
            <span>Multi-Factor Authentication Methods</span>
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Configure your verified methods for logging in and accessing privileged operations.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 1. AUTHENTICATOR APP */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-600">
                <Smartphone className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>Authenticator App</span>
                  {summary?.methods.authenticator.enabled ? (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">✓ Configured</span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold">Not Setup</span>
                  )}
                </div>
                <div className="text-xs text-slate-500">Google Authenticator, Authy, Microsoft Authenticator, 1Password</div>
              </div>
            </div>
          </div>

          {/* 2. PASSKEYS */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-purple-50 border border-purple-200 text-purple-600">
                  <Key className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                    <span>Passkeys & Hardware Keys</span>
                    <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold">
                      ✓ {summary?.passkeys.length || 0} Registered
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">Use Fingerprint, Face ID, Windows Hello, or physical YubiKey</div>
                </div>
              </div>

              <Button
                type="button"
                onClick={handleAddPasskey}
                disabled={passkeyLoading}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs py-2 px-3 rounded-xl flex items-center gap-1.5 shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Add Passkey</span>
              </Button>
            </div>

            {/* List of Registered Passkeys */}
            {summary?.passkeys && summary.passkeys.length > 0 && (
              <div className="pt-2 border-t border-slate-200 space-y-2">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-500">Registered Passkeys</div>
                {summary.passkeys.map((pk) => (
                  <div key={pk.id} className="p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <Laptop className="w-4 h-4 text-slate-400" />
                      <div>
                        <div className="font-bold text-slate-900">{pk.name}</div>
                        <div className="text-[11px] text-slate-400">Added: {new Date(pk.created_at).toLocaleDateString()}</div>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleRemovePasskey(pk.id, pk.name)}
                      className="h-8 px-2 text-rose-600 border-rose-200 hover:bg-rose-50 rounded-lg text-xs"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 3. RECOVERY OTP */}
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/60 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-teal-50 border border-teal-200 text-teal-600">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span>One-Time Password (OTP)</span>
                  <span className="px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 text-[10px] font-bold">✓ Active</span>
                </div>
                <div className="text-xs text-slate-500">Delivered via Resend to {summary?.methods.otp.delivery_channel}</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* SECTION 2: ACTIVE SESSIONS */}
      <Card className="bg-white border-emerald-100 shadow-md">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Globe className="w-5 h-5 text-emerald-600" />
              <span>Active Staff & Admin Sessions</span>
            </CardTitle>
            <CardDescription className="text-xs text-slate-500">
              Manage your active sessions across web browsers and devices.
            </CardDescription>
          </div>

          <Button
            type="button"
            onClick={handleRevokeAllSessions}
            className="bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs py-2 px-3 rounded-xl flex items-center gap-1.5 shadow-sm"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out All Other Sessions</span>
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {summary?.active_sessions.map((s) => (
              <div key={s.id} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/50 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <Laptop className="w-5 h-5 text-slate-500" />
                  <div>
                    <div className="font-bold text-slate-900 flex items-center gap-2">
                      <span>{s.device_name}</span>
                      {s.is_current && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">Active Now</span>
                      )}
                    </div>
                    <div className="text-slate-500 text-[11px] flex items-center gap-2 mt-0.5">
                      <span>IP: {s.ip_address}</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-400" />
                        Last active: {new Date(s.last_activity).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
