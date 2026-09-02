import React from 'react';
import { AlertTriangle, Clock, ShieldAlert, LogOut, RefreshCw } from 'lucide-react';
import { Button } from './button.js';

interface SessionTimeoutModalProps {
  isOpen: boolean;
  remainingSeconds: number;
  onExtendSession: () => void;
  onSignOut: () => void;
}

export const SessionTimeoutModal: React.FC<SessionTimeoutModalProps> = ({
  isOpen,
  remainingSeconds,
  onExtendSession,
  onSignOut,
}) => {
  if (!isOpen) return null;

  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const formattedTime = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 text-slate-100 rounded-2xl max-w-md w-full p-6 sm:p-8 shadow-2xl space-y-6 relative overflow-hidden">
        {/* Glow accent */}
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center gap-3">
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-400 shrink-0">
            <Clock className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-extrabold text-white">Your session is about to expire</h3>
            <p className="text-xs text-slate-400">DigiLand Privileged Security Policy</p>
          </div>
        </div>

        <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 text-sm text-slate-300 space-y-2">
          <p>
            You have been inactive for a while. For your security, your privileged DigiLand session will automatically sign out in:
          </p>
          <div className="text-2xl font-mono font-extrabold text-amber-400 tracking-wider text-center py-2 bg-slate-900/90 rounded-lg border border-amber-500/20">
            {formattedTime}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={onSignOut}
            className="flex-1 border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-300 hover:text-white py-2.5 rounded-xl font-bold flex items-center justify-center gap-2 text-xs"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out Now</span>
          </Button>

          <Button
            type="button"
            onClick={onExtendSession}
            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white py-2.5 rounded-xl font-bold shadow-lg shadow-emerald-950/50 flex items-center justify-center gap-2 text-xs"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Continue Session</span>
          </Button>
        </div>
      </div>
    </div>
  );
};
