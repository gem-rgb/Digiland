import React, { useState } from 'react';
import {
  Receipt,
  Percent,
  CheckCircle2,
  DollarSign,
  Briefcase,
  Scale,
  Download,
  Search,
  ExternalLink,
  ShieldCheck,
  Building2,
  Users,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { Button } from '../../ui/button.js';
import { AnalyticsContextData, formatKES, formatNumber, StaffLedgerEntry } from '../types.js';

export function RevenueTaxesChapter({
  timeframe,
  escrowRevenue,
  adRevenue,
  grossRevenue,
  totalStaffCompensation,
  totalTaxes,
  rawAnalytics,
}: AnalyticsContextData) {
  const [searchStaff, setSearchStaff] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');

  const taxes = rawAnalytics.taxes || rawAnalytics.tax_liability || {};
  const hires = rawAnalytics.hires || rawAnalytics.staff_hires || {};
  const staffLedger: StaffLedgerEntry[] = rawAnalytics.staff_ledger || [
    {
      id: '1',
      name: 'Advocate James Kariuki',
      email: 'kariuki@lawfirm.co.ke',
      phone: '+254 712 345 678',
      role: 'Lawyer',
      firm_or_agency: 'Kariuki & Associates Advocates',
      county: 'Nairobi',
      tasks_completed: 6,
      accrued_kes: 320000,
      paid_kes: 320000,
      balance_kes: 0,
      status: 'PAID',
      last_payout_date: 'Aug 24, 2026',
    },
    {
      id: '2',
      name: 'Surveyor John Mwangi',
      email: 'survey@geomatics.co.ke',
      phone: '+254 722 987 654',
      role: 'Surveyor',
      firm_or_agency: 'Geomatic Surveyors Kenya',
      county: 'Kiambu',
      tasks_completed: 4,
      accrued_kes: 180000,
      paid_kes: 180000,
      balance_kes: 0,
      status: 'PAID',
      last_payout_date: 'Aug 26, 2026',
    },
    {
      id: '3',
      name: 'Agent David Ochieng',
      email: 'david@agents.co.ke',
      phone: '+254 733 112 233',
      role: 'Agent',
      firm_or_agency: 'Apex Realty Valuers',
      county: 'Machakos',
      tasks_completed: 3,
      accrued_kes: 60000,
      paid_kes: 60000,
      balance_kes: 0,
      status: 'PAID',
      last_payout_date: 'Aug 28, 2026',
    },
  ];

  const vatTax = taxes.vat_16pct_kes || escrowRevenue * 0.16;
  const whtTax = taxes.withholding_tax_5pct_kes || totalStaffCompensation * 0.05;
  const stampDuty = taxes.stamp_duty_remitted_kes || escrowRevenue * 1.6;

  const filteredStaff = staffLedger.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchStaff.toLowerCase()) ||
      s.email.toLowerCase().includes(searchStaff.toLowerCase()) ||
      s.county.toLowerCase().includes(searchStaff.toLowerCase());
    const matchesRole = roleFilter === 'ALL' || s.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Core Revenue & Tax Hero Cards ─────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Gross Revenue</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">{formatKES(grossRevenue)}</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">+18.4% vs last period</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Escrow Fees (2.5%)</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{formatKES(escrowRevenue)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Core conveyancing</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Ad Promotions</div>
          <div className="mt-1 text-2xl font-black text-purple-700">{formatKES(adRevenue)}</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">Seller spotlight tiers</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">16% VAT (KRA)</div>
          <div className="mt-1 text-2xl font-black text-amber-700">{formatKES(vatTax)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">VAT on platform fees</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">5% WHT Accrued</div>
          <div className="mt-1 text-2xl font-black text-amber-700">{formatKES(whtTax)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Withholding on staff</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Stamp Duty (4%)</div>
          <div className="mt-1 text-2xl font-black text-blue-700">{formatKES(stampDuty)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Ministry of Lands</div>
        </div>
      </div>

      {/* ── Monetization Breakdown & Statutory Tax Schedule ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Streams Distribution */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Platform Monetization Distribution</h4>
              <div className="text-[11px] text-slate-500">Revenue attribution by monetization stream</div>
            </div>
            <Receipt className="h-4 w-4 text-emerald-600" />
          </div>

          <div className="space-y-3 text-xs">
            {[
              { label: 'Escrow Conveyancing Commissions (2.5%)', amount: escrowRevenue, share: '78%', color: 'bg-emerald-600' },
              { label: 'Promoted Listings & Spotlight Ads', amount: adRevenue, share: '14%', color: 'bg-purple-600' },
              { label: 'Title Deed AI Verification Fees', amount: escrowRevenue * 0.05, share: '5%', color: 'bg-blue-600' },
              { label: 'Digital Survey Cadastral Certification', amount: escrowRevenue * 0.03, share: '3%', color: 'bg-amber-600' },
            ].map((stream, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between font-bold">
                  <span className="text-slate-800">{stream.label}</span>
                  <span className="text-slate-900">
                    {formatKES(stream.amount)} ({stream.share})
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${stream.color} transition-all duration-500`}
                    style={{ width: stream.share }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Statutory Tax Compliance Matrix (KRA) */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Kenya Revenue Authority (KRA) Tax Compliance</h4>
              <div className="text-[11px] text-slate-500">Statutory deductions, PIN validations & iTax schedules</div>
            </div>
            <Scale className="h-4 w-4 text-amber-600" />
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">16% Value Added Tax (VAT)</div>
                <div className="text-[10px] text-slate-500">Remitted monthly by 20th • KRA ETIMS Active</div>
              </div>
              <span className="font-black text-amber-700">{formatKES(vatTax)}</span>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">5% Professional Withholding Tax (WHT)</div>
                <div className="text-[10px] text-slate-500">Deducted at source on Advocate & Surveyor payouts</div>
              </div>
              <span className="font-black text-amber-700">{formatKES(whtTax)}</span>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 flex items-center justify-between">
              <div>
                <div className="font-bold text-slate-900">4% Ministry of Lands Stamp Duty (Urban)</div>
                <div className="text-[10px] text-slate-500">Facilitated directly to Kenya Government Ardhisasa account</div>
              </div>
              <span className="font-black text-blue-700">{formatKES(stampDuty)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Professional Staff Compensation & Hires Ledger ────────────────── */}
      <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <h4 className="text-sm font-black text-slate-900 flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-emerald-600" />
              Professional Staff Compensation & Hires Ledger
            </h4>
            <div className="text-[11px] text-slate-500">
              Conveyance fees disbursed to Advocates, Surveyors & Field Inspection Agents
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-xl border border-slate-200 bg-slate-100 p-0.5 text-xs font-bold">
              {['ALL', 'Lawyer', 'Surveyor', 'Agent'].map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRoleFilter(r)}
                  className={`rounded-lg px-2.5 py-1 transition ${
                    roleFilter === r ? 'bg-white text-slate-900 shadow-xs font-black' : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {r === 'ALL' ? 'All Roles' : r}
                </button>
              ))}
            </div>

            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search staff..."
                value={searchStaff}
                onChange={(e) => setSearchStaff(e.target.value)}
                className="h-8 rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="py-2.5 px-3">Professional</th>
                <th className="py-2.5 px-3">Role</th>
                <th className="py-2.5 px-3">Firm / Agency</th>
                <th className="py-2.5 px-3">County</th>
                <th className="py-2.5 px-3 text-right">Tasks</th>
                <th className="py-2.5 px-3 text-right">Accrued KES</th>
                <th className="py-2.5 px-3 text-right">Disbursed</th>
                <th className="py-2.5 px-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredStaff.map((staff) => (
                <tr key={staff.id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3">
                    <div className="font-bold text-slate-900">{staff.name}</div>
                    <div className="text-[10px] text-slate-500">{staff.email}</div>
                  </td>
                  <td className="py-3 px-3">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[9px] font-black uppercase ${
                        staff.role === 'Lawyer'
                          ? 'bg-purple-100 text-purple-800'
                          : staff.role === 'Surveyor'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      {staff.role}
                    </span>
                  </td>
                  <td className="py-3 px-3 font-medium text-slate-700">{staff.firm_or_agency || 'Independent'}</td>
                  <td className="py-3 px-3 font-medium text-slate-700">{staff.county}</td>
                  <td className="py-3 px-3 text-right font-bold text-slate-900">{staff.tasks_completed}</td>
                  <td className="py-3 px-3 text-right font-black text-slate-900">{formatKES(staff.accrued_kes)}</td>
                  <td className="py-3 px-3 text-right font-black text-emerald-700">{formatKES(staff.paid_kes)}</td>
                  <td className="py-3 px-3 text-center">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="h-3 w-3" /> Disbursed
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
