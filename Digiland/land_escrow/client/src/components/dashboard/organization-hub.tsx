import React, { useState } from 'react';
import {
  Building2,
  ShieldCheck,
  FileText,
  Users,
  Plus,
  ArrowRight,
  Landmark,
  Layers,
  CheckCircle2,
  Lock,
} from 'lucide-react';
import { DigitalCrownAvatar } from '../ui/digital-crown-avatar.js';
import { Button } from '../ui/button.js';
import { Badge } from '../ui/badge.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import type { AccountSummary, UserSummary } from '../../types.js';

interface OrganizationHubProps {
  initialAccount?: AccountSummary | null;
  currentUser?: UserSummary | null;
  csrfToken?: string;
}

export function OrganizationHub({ initialAccount, currentUser, csrfToken }: OrganizationHubProps) {
  const [account, setAccount] = useState<AccountSummary | null>(initialAccount || null);
  const members = account?.members || [];

  return (
    <div className="space-y-6 text-left">
      {/* 1. CORPORATE / INSTITUTIONAL HEADER */}
      <div className="rounded-3xl border border-indigo-200/80 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950 p-6 text-white shadow-xl relative overflow-hidden">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-[10px] font-black uppercase tracking-wider flex items-center gap-1.5">
                <Building2 className="h-3 w-3" />
                {account?.entity_type_display || 'Institutional Entity'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-white/10 text-slate-300 font-mono text-[10px] font-bold">
                Reg: {account?.registration_number || 'CPR/Verified'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 text-[10px] font-semibold">
                KRA PIN: {account?.tax_id_or_kra_pin || 'P05...Verified'}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-2">
              {account?.display_name || account?.legal_name || 'Organization Workspace'}
            </h1>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Institutional property management, verified corporate representatives, and compliant statutory land acquisition workspace.
            </p>
          </div>

          <div className="flex items-center gap-3 bg-white/5 backdrop-blur-md p-3 rounded-2xl border border-white/10 shrink-0">
            <div className="flex -space-x-3 overflow-hidden p-1">
              {members.map((m) => (
                <div key={m.id} className="relative">
                  <DigitalCrownAvatar
                    name={m.full_name || m.email || 'Representative'}
                    isOrganization={true}
                    roleTitle={m.role_display}
                    size="md"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 2. CORPORATE REPRESENTATIVES DIRECTORY */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="bg-white border-slate-200">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-600" /> Authorized Representatives
            </CardTitle>
            <CardDescription className="text-xs">
              Staff and legal counsel authorized to execute property actions on behalf of the organization.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-3">
            {members.map((m) => (
              <div key={m.id} className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <div className="flex items-center gap-3">
                  <DigitalCrownAvatar
                    name={m.full_name || m.email || 'Representative'}
                    isOrganization={true}
                    size="md"
                  />
                  <div>
                    <div className="font-bold text-xs text-slate-900">{m.full_name}</div>
                    <div className="text-[11px] text-slate-500">{m.email}</div>
                  </div>
                </div>
                <Badge tone="default" className="text-[10px] font-bold">
                  {m.role_display}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* STATUTORY LAND COMPLIANCE */}
        <Card className="bg-white border-slate-200">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" /> Statutory Compliance & Title Protection
            </CardTitle>
            <CardDescription className="text-xs">
              Kenyan Ministry of Lands & Ardhisasa compliance verification.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-3 text-xs text-slate-700">
            <div className="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 flex items-start gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Entity Verification Active</span>
                <p className="text-[11px] text-emerald-800 mt-0.5">
                  All property transactions require verified advocate signoff and direct statutory land registry registration.
                </p>
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 text-slate-800 flex items-start gap-2">
              <Lock className="h-4 w-4 text-slate-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Dual-Key Escrow Release</span>
                <p className="text-[11px] text-slate-600 mt-0.5">
                  Transactions above KES 5M require dual approval by Primary Representative and Finance Officer.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
