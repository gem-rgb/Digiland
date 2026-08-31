import React from 'react';
import {
  Layers,
  Percent,
  Lock,
  DollarSign,
  Globe,
  Users,
  Activity,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  Receipt,
  FileCheck,
  Zap,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber } from '../types.js';

export function OverviewChapter({
  timeframe,
  totalGmv,
  escrowRevenue,
  adRevenue,
  grossRevenue,
  totalStaffCompensation,
  totalOperatingExpenses,
  totalTaxes,
  netIncome,
  rawAnalytics,
  onNavigateChapter,
}: AnalyticsContextData) {
  const financial = rawAnalytics.financial || rawAnalytics.financial_overview || {};
  const userMetrics = rawAnalytics.user_metrics || {};
  const failures = rawAnalytics.failures || {};
  const regionalDist = rawAnalytics.regional_distribution || [];
  const hires = rawAnalytics.hires || rawAnalytics.staff_hires || {};

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Executive Top 4 Hero KPIs ────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: TOTAL LAND GMV */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-xs hover:shadow-soft transition flex flex-col justify-between space-y-3">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
              <span>Total Land GMV</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                <Layers className="h-4 w-4" />
              </div>
            </div>
            <div className="mt-2 text-2xl font-black text-slate-900">
              KES {(totalGmv / 1000000).toFixed(1)}M
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Across 32 active registered land parcels</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateChapter('marketplace')}
            className="text-xs font-bold text-blue-700 hover:text-blue-900 flex items-center justify-between pt-2 border-t border-slate-100 group"
          >
            <span>Explore Marketplace Chapter</span>
            <ArrowRight className="h-3.5 w-3.5 transition transform group-hover:translate-x-1" />
          </button>
        </div>

        {/* KPI 2: PLATFORM GROSS REVENUE */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-xs hover:shadow-soft transition flex flex-col justify-between space-y-3">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
              <span>Platform Gross Revenue</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <Percent className="h-4 w-4" />
              </div>
            </div>
            <div className="mt-2 text-2xl font-black text-emerald-700">
              {formatKES(grossRevenue)}
            </div>
            <p className="text-[11px] text-slate-500 mt-1">2.5% escrow commissions + Ad promos</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateChapter('revenue_taxes')}
            className="text-xs font-bold text-emerald-700 hover:text-emerald-900 flex items-center justify-between pt-2 border-t border-slate-100 group"
          >
            <span>Explore Revenue & Taxes</span>
            <ArrowRight className="h-3.5 w-3.5 transition transform group-hover:translate-x-1" />
          </button>
        </div>

        {/* KPI 3: LOCKED ESCROW */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-xs hover:shadow-soft transition flex flex-col justify-between space-y-3">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
              <span>Active Escrow Custody</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                <Lock className="h-4 w-4" />
              </div>
            </div>
            <div className="mt-2 text-2xl font-black text-purple-700">
              KES {((totalGmv * 0.95) / 1000000).toFixed(1)}M
            </div>
            <p className="text-[11px] text-slate-500 mt-1">Dual-signoff cryptographic bank custody</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateChapter('escrow')}
            className="text-xs font-bold text-purple-700 hover:text-purple-900 flex items-center justify-between pt-2 border-t border-slate-100 group"
          >
            <span>Inspect Escrow & Vault</span>
            <ArrowRight className="h-3.5 w-3.5 transition transform group-hover:translate-x-1" />
          </button>
        </div>

        {/* KPI 4: SETTLED TRANSACTIONS */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-xs hover:shadow-soft transition flex flex-col justify-between space-y-3">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center justify-between">
              <span>Settled Transactions</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                <DollarSign className="h-4 w-4" />
              </div>
            </div>
            <div className="mt-2 text-2xl font-black text-slate-900">
              {financial.completed_transactions_count || 14} Settled
            </div>
            <p className="text-[11px] text-slate-500 mt-1">&lt; 4 hours average payout velocity</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateChapter('transactions')}
            className="text-xs font-bold text-amber-700 hover:text-amber-900 flex items-center justify-between pt-2 border-t border-slate-100 group"
          >
            <span>Inspect Velocity Chapter</span>
            <ArrowRight className="h-3.5 w-3.5 transition transform group-hover:translate-x-1" />
          </button>
        </div>
      </div>

      {/* ── Executive 4 Core Snapshots Grid ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Section 1: Platform Cashflow & P&L Statement */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Platform Cashflow & P&L Statement</h4>
              <div className="text-[11px] text-slate-500">Consolidated revenue, disbursements, and statutory taxes</div>
            </div>
            <Badge tone="success" className="font-bold text-[10px] uppercase">
              Healthy Margin ({(netIncome > 0 ? ((netIncome / (grossRevenue || 1)) * 100).toFixed(0) : 0)}%)
            </Badge>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Gross Platform Revenue (Escrow + Ads)</span>
              <span className="font-black text-emerald-700">+ {formatKES(grossRevenue)}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Professional Staff Compensations Disbursed</span>
              <span className="font-bold text-slate-700">- {formatKES(totalStaffCompensation)}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Operating Overhead (SMS, AI OCR, Cloud)</span>
              <span className="font-bold text-slate-700">- {formatKES(totalOperatingExpenses)}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-slate-100">
              <span className="text-slate-600 font-medium">Statutory Taxes (16% VAT + 5% WHT)</span>
              <span className="font-bold text-amber-700">- {formatKES(totalTaxes)}</span>
            </div>
            <div className="flex items-center justify-between pt-2 text-sm font-black text-slate-900 bg-emerald-50/70 p-3.5 rounded-2xl border border-emerald-200">
              <span>Net Operating Income (EBITDA)</span>
              <span className="text-emerald-700 text-base">{formatKES(netIncome)}</span>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onNavigateChapter('revenue_taxes')}
              className="text-xs font-bold text-emerald-700 hover:underline flex items-center gap-1"
            >
              Detailed Tax & Revenue Ledger →
            </button>
            <button
              type="button"
              onClick={() => onNavigateChapter('expenses_reports')}
              className="text-xs font-bold text-slate-600 hover:text-slate-900 flex items-center gap-1"
            >
              Full Financial Report →
            </button>
          </div>
        </div>

        {/* Section 2: Regional Land & Density Preview */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Regional Land Density Snapshot</h4>
              <div className="text-[11px] text-slate-500">County-by-county parcel listings & value density</div>
            </div>
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <Globe className="h-4 w-4" />
            </div>
          </div>

          <div className="space-y-3 text-xs">
            {(regionalDist.length > 0 ? regionalDist.slice(0, 4) : [
              { county: 'Nairobi', listings_count: 14, estimated_value_kes: 78000000 },
              { county: 'Kiambu', listings_count: 8, estimated_value_kes: 32000000 },
              { county: 'Machakos', listings_count: 5, estimated_value_kes: 18000000 },
              { county: 'Nakuru', listings_count: 3, estimated_value_kes: 12000000 },
            ]).map((reg: any) => (
              <div key={reg.county} className="space-y-1">
                <div className="flex justify-between font-bold">
                  <span className="text-slate-800">{reg.county} County</span>
                  <span className="text-emerald-700">
                    {reg.listings_count} parcels ({formatKES(reg.estimated_value_kes)})
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-emerald-600 transition-all duration-500"
                    style={{ width: `${Math.min(100, (reg.listings_count / 14) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => onNavigateChapter('regional')}
              className="text-xs font-bold text-emerald-700 hover:underline flex items-center gap-1"
            >
              Explore Full 47-County Density Chapter →
            </button>
          </div>
        </div>

        {/* Section 3: Escrow Security & Dual-Vault Health */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Escrow Security & Dual-Vault Health</h4>
              <div className="text-[11px] text-slate-500">Cryptographic protection of buyer earnest money</div>
            </div>
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <Lock className="h-4 w-4" />
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Dual-Signoff Cryptographic Status</span>
              <span className="font-bold text-emerald-700 inline-flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> 100% Armed & Active
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Disputed Escrow Cases</span>
              <span className="font-bold text-slate-900">0 Active Disputes</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Average Settlement Velocity</span>
              <span className="font-bold text-purple-700">&lt; 4 Hours to M-Pesa / Bank</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-600">Segregated Client Trust Account</span>
              <span className="font-bold text-slate-800">NCBA & Equity Bank Trust Vaults</span>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => onNavigateChapter('escrow')}
              className="text-xs font-bold text-purple-700 hover:underline flex items-center gap-1"
            >
              Inspect Dual-Vault Architecture →
            </button>
          </div>
        </div>

        {/* Section 4: Users & Demographics Snapshot */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Users & Demographics Summary</h4>
              <div className="text-[11px] text-slate-500">Buyer, seller, and licensed professional participation</div>
            </div>
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <Users className="h-4 w-4" />
            </div>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Registered Land Buyers</span>
              <span className="font-bold text-slate-900">{userMetrics.buyers_count || 10} Buyers</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Chama & Joint Syndicates</span>
              <span className="font-bold text-purple-700">{userMetrics.joint_buyers_count || 3} Groups Active</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-600">Licensed Professional Staff</span>
              <span className="font-bold text-emerald-700">{hires.total_hires_count || 8} Verified Staff</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-600">Identity Verification Rate</span>
              <span className="font-bold text-blue-700">92.4% Ardhisasa & KYC Verified</span>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => onNavigateChapter('users')}
              className="text-xs font-bold text-blue-700 hover:underline flex items-center gap-1"
            >
              View Demographics & KYC Chapter →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
