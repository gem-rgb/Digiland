import React, { useState } from 'react';
import {
  DollarSign,
  Zap,
  Clock,
  CheckCircle2,
  TrendingUp,
  CreditCard,
  Building,
  ShieldCheck,
  Search,
  Filter,
  ArrowUpRight,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber } from '../types.js';

export function TransactionsChapter({
  timeframe,
  totalGmv,
  grossRevenue,
  rawAnalytics,
}: AnalyticsContextData) {
  const financial = rawAnalytics.financial || rawAnalytics.financial_overview || {};

  const pipelineStages = [
    { name: '1. Deposit In Vault', count: 8, valueKes: totalGmv * 0.25, timeAvg: '< 15 mins' },
    { name: '2. Ardhisasa Verification', count: 6, valueKes: totalGmv * 0.20, timeAvg: '2.4 hours' },
    { name: '3. Cadastral Site Survey', count: 5, valueKes: totalGmv * 0.18, timeAvg: '24 hours' },
    { name: '4. Advocate Conveyance', count: 4, valueKes: totalGmv * 0.15, timeAvg: '48 hours' },
    { name: '5. Dual Cryptographic Signoff', count: 3, valueKes: totalGmv * 0.12, timeAvg: '1.2 hours' },
    { name: '6. Settled & Disbursed', count: financial.completed_transactions_count || 14, valueKes: totalGmv, timeAvg: '< 4 hours' },
  ];

  const recentSettlements = [
    {
      id: 'TX-2026-089',
      parcel: 'NAIROBI/BLOCK-92/148',
      buyer: 'Evans Wanyonyi (Chama Syndicate)',
      seller: 'Karen Heights Ltd',
      amount_kes: 18500000,
      payout_rail: 'Bank RTGS',
      velocity: '1.8 hours',
      status: 'Settled',
      date: 'Aug 29, 2026',
    },
    {
      id: 'TX-2026-088',
      parcel: 'KIAMBU/RUIRU/312',
      buyer: 'Grace Muthoni',
      seller: 'Ruiru Greens Estates',
      amount_kes: 4200000,
      payout_rail: 'M-Pesa B2C',
      velocity: '8 mins',
      status: 'Settled',
      date: 'Aug 27, 2026',
    },
    {
      id: 'TX-2026-087',
      parcel: 'MACHAKOS/LUKENYA/45',
      buyer: 'Samuel Kipchoge',
      seller: 'Lukenya Ridge Farms',
      amount_kes: 3500000,
      payout_rail: 'M-Pesa B2C',
      velocity: '12 mins',
      status: 'Settled',
      date: 'Aug 25, 2026',
    },
    {
      id: 'TX-2026-086',
      parcel: 'NAKURU/LANGETA/88',
      buyer: 'Amani Investment Syndicate',
      seller: 'Rift Agri-Holdings',
      amount_kes: 12000000,
      payout_rail: 'Bank RTGS',
      velocity: '2.5 hours',
      status: 'Settled',
      date: 'Aug 23, 2026',
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Transaction Velocity Hero Metrics ─────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Total Settled GMV</div>
          <div className="mt-1 text-2xl font-black text-slate-900">KES {(totalGmv / 1000000).toFixed(1)}M</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">100% Guaranteed</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Payout Velocity</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">&lt; 4 Hours</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Average settlement</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Settlement Success</div>
          <div className="mt-1 text-2xl font-black text-blue-700">99.4%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Zero escrow defaults</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Active Deals</div>
          <div className="mt-1 text-2xl font-black text-purple-700">{financial.active_transactions_count || 6} Deals</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">In conveyancing</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Avg Deal Size</div>
          <div className="mt-1 text-2xl font-black text-slate-900">KES 4.8M</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Per parcel contract</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Dispute Rate</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">0.0%</div>
          <div className="text-[10px] text-emerald-700 font-semibold mt-0.5">Dual-signoff protected</div>
        </div>
      </div>

      {/* ── Transaction Pipeline Funnel & Payout Rails ────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Deal Velocity Funnel */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Deal Execution Stages & Milestone Velocity</h4>
              <div className="text-[11px] text-slate-500">Milestone completion times across escrow deals</div>
            </div>
            <Clock className="h-4 w-4 text-blue-600" />
          </div>

          <div className="space-y-3 text-xs">
            {pipelineStages.map((stage, idx) => (
              <div key={idx} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="font-bold text-slate-900">{stage.name}</div>
                  <div className="text-[10px] text-slate-500">{stage.count} deals in flight • Volume: {formatKES(stage.valueKes)}</div>
                </div>
                <div className="text-right">
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-black text-emerald-800">
                    <Zap className="h-3 w-3" /> {stage.timeAvg}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Payout Channels & Gateway Velocity */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Disbursement Rail Performance & Latency</h4>
              <div className="text-[11px] text-slate-500">M-Pesa B2C vs Commercial Bank settlement times</div>
            </div>
            <Zap className="h-4 w-4 text-amber-600" />
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-black text-slate-900">
                  <CreditCard className="h-4 w-4 text-emerald-700" />
                  <span>Safaricom M-Pesa B2C Bulk Gateway</span>
                </div>
                <Badge tone="success" className="font-black text-[10px]">Instant (&lt; 2 mins)</Badge>
              </div>
              <p className="text-[11px] text-slate-600">
                Automated payout for earnest fees, agent inspection allowances, and smaller seller payments up to KES 500,000.
              </p>
              <div className="flex justify-between text-[11px] font-bold text-emerald-800 pt-1 border-t border-emerald-200/60">
                <span>Success Rate: 99.8%</span>
                <span>Volume: 64% of disbursements</span>
              </div>
            </div>

            <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-black text-slate-900">
                  <Building className="h-4 w-4 text-blue-700" />
                  <span>Commercial Bank RTGS / EFT Wire</span>
                </div>
                <Badge tone="accent" className="font-black text-[10px]">Same-Day (&lt; 3.5 hrs)</Badge>
              </div>
              <p className="text-[11px] text-slate-600">
                Direct trust account transfer for high-value title purchases (&gt; KES 1M) directly to seller &amp; advocate client accounts.
              </p>
              <div className="flex justify-between text-[11px] font-bold text-blue-800 pt-1 border-t border-blue-200/60">
                <span>Success Rate: 100%</span>
                <span>Volume: 36% of disbursements</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Recent High-Value Settlements Ledger ──────────────────────────── */}
      <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h4 className="text-sm font-black text-slate-900">Recent High-Value Settlement Audit Trail</h4>
            <div className="text-[11px] text-slate-500">Verified transactions released under dual cryptographic authorization</div>
          </div>
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="py-2.5 px-3">Transaction ID</th>
                <th className="py-2.5 px-3">Parcel Reference</th>
                <th className="py-2.5 px-3">Buyer / Syndicate</th>
                <th className="py-2.5 px-3">Seller</th>
                <th className="py-2.5 px-3 text-right">Settled Amount</th>
                <th className="py-2.5 px-3">Rail</th>
                <th className="py-2.5 px-3">Velocity</th>
                <th className="py-2.5 px-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recentSettlements.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3 font-mono font-bold text-slate-900">{tx.id}</td>
                  <td className="py-3 px-3 font-bold text-emerald-700">{tx.parcel}</td>
                  <td className="py-3 px-3 font-medium text-slate-700">{tx.buyer}</td>
                  <td className="py-3 px-3 font-medium text-slate-700">{tx.seller}</td>
                  <td className="py-3 px-3 text-right font-black text-slate-900">{formatKES(tx.amount_kes)}</td>
                  <td className="py-3 px-3 font-semibold text-slate-700">{tx.payout_rail}</td>
                  <td className="py-3 px-3 font-bold text-emerald-700">{tx.velocity}</td>
                  <td className="py-3 px-3 text-center">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="h-3 w-3" /> {tx.status}
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
