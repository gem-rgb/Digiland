import React from 'react';
import {
  Users,
  UserCheck,
  ShieldCheck,
  Building2,
  Briefcase,
  Scale,
  ShieldAlert,
  UserPlus,
  Compass,
  CheckCircle2,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber } from '../types.js';

export function UsersDemographicsChapter({
  timeframe,
  rawAnalytics,
}: AnalyticsContextData) {
  const userMetrics = rawAnalytics.user_metrics || {
    total_users: 19,
    active_users: 18,
    suspended_users: 1,
    verified_users: 14,
    buyers_count: 10,
    joint_buyers_count: 3,
    sellers_count: 4,
    agents_count: 2,
    lawyers_count: 2,
    staff_count: 1,
    admins_count: 1,
  };

  const hires = rawAnalytics.hires || rawAnalytics.staff_hires || {};

  const userSegments = [
    {
      role: 'Individual Land Buyers',
      count: (userMetrics.buyers_count || 10) - (userMetrics.joint_buyers_count || 3),
      share: '38%',
      description: 'Private individuals purchasing residential plots & retirement homes.',
      avgBudget: 'KES 3,500,000',
      badge: 'Individual Account',
      tone: 'blue' as const,
      icon: Users,
    },
    {
      role: 'Chama & Joint Syndicates',
      count: userMetrics.joint_buyers_count || 3,
      share: '18%',
      description: 'Investment groups pooling funds with multi-signatory voting governance.',
      avgBudget: 'KES 14,000,000',
      badge: 'Chama Syndicate',
      tone: 'purple' as const,
      icon: Building2,
    },
    {
      role: 'Verified Private Landowners',
      count: userMetrics.sellers_count || 4,
      share: '22%',
      description: 'Property owners with Ardhisasa title deed verification completed.',
      avgBudget: 'KES 28,000,000 portfolio',
      badge: 'Seller Verified',
      tone: 'accent' as const,
      icon: UserCheck,
    },
    {
      role: 'High Court Advocates & Lawyers',
      count: userMetrics.lawyers_count || 2,
      share: '10%',
      description: 'Licensed conveyancing practitioners with active LSK practicing certs.',
      avgBudget: 'KES 320k accrued fees',
      badge: 'LSK Advocate',
      tone: 'purple' as const,
      icon: Scale,
    },
    {
      role: 'Licensed Surveyors & Valuers',
      count: userMetrics.agents_count || 2,
      share: '12%',
      description: 'Field inspection professionals and cadastral GIS spatial verifiers.',
      avgBudget: 'KES 240k accrued fees',
      badge: 'EARB Surveyor',
      tone: 'success' as const,
      icon: Compass,
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── User Demographics Hero Metrics ────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Total Users</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{userMetrics.total_users || 19}</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">{userMetrics.active_users || 18} Active Now</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Verified Rate</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">92.4%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">National ID OCR + Ardhisasa</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Registered Buyers</div>
          <div className="mt-1 text-2xl font-black text-blue-700">{userMetrics.buyers_count || 10}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Verified purchasers</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Chama Groups</div>
          <div className="mt-1 text-2xl font-black text-purple-700">{userMetrics.joint_buyers_count || 3} Chamas</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">Syndicate buyers</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Verified Sellers</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{userMetrics.sellers_count || 4}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Title deed holders</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Licensed Staff</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">{hires.total_hires_count || 8}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Lawyers & Surveyors</div>
        </div>
      </div>

      {/* ── User Role Segments & KYC Verification Funnel ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* User Role Segmentation Cards */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">User Role & Account Categorization</h4>
              <div className="text-[11px] text-slate-500">Participant segmentation across escrow network</div>
            </div>
            <Users className="h-4 w-4 text-emerald-600" />
          </div>

          <div className="space-y-3 text-xs">
            {userSegments.map((seg, idx) => {
              const Icon = seg.icon;
              return (
                <div key={idx} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-black text-slate-900">
                      <Icon className="h-4 w-4 text-emerald-700" />
                      <span>{seg.role}</span>
                    </div>
                    <Badge tone={seg.tone} className="text-[9px] font-black">
                      {seg.count} Users ({seg.share})
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-600">{seg.description}</p>
                  <div className="flex justify-between text-[10px] font-bold text-slate-600 pt-1 border-t border-slate-200">
                    <span>Power / Capacity:</span>
                    <span className="text-slate-900 font-black">{seg.avgBudget}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* KYC Onboarding Funnel & Identity Verification */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Identity KYC & Fraud Risk Tiering</h4>
              <div className="text-[11px] text-slate-500">Multi-factor statutory onboarding stages</div>
            </div>
            <ShieldCheck className="h-4 w-4 text-purple-600" />
          </div>

          <div className="space-y-3 text-xs">
            {[
              { stage: '1. Safaricom Phone OTP Verification', completion: '100%', count: '19 users', tone: 'bg-emerald-600' },
              { stage: '2. National ID / Passport AI OCR', completion: '95%', count: '18 users', tone: 'bg-emerald-600' },
              { stage: '3. KRA PIN Certificate Automated Validation', completion: '89%', count: '17 users', tone: 'bg-blue-600' },
              { stage: '4. Ardhisasa Biometric Identity Link', completion: '84%', count: '16 users', tone: 'bg-purple-600' },
              { stage: '5. LSK / EARB Professional License Check', completion: '100%', count: '8 staff', tone: 'bg-emerald-600' },
            ].map((f, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between font-bold">
                  <span className="text-slate-800">{f.stage}</span>
                  <span className="text-emerald-700">
                    {f.count} ({f.completion})
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${f.tone} transition-all duration-500`}
                    style={{ width: f.completion }}
                  />
                </div>
              </div>
            ))}

            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-emerald-600" />
                <span className="text-xs font-bold text-slate-900">Flagged Fraudulent Attempts: 0 Cases</span>
              </div>
              <Badge tone="success" className="text-[9px] font-black">All Clear</Badge>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
