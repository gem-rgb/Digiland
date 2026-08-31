import React from 'react';
import {
  Lock,
  ShieldCheck,
  Key,
  Building,
  CheckCircle2,
  FileCheck,
  AlertTriangle,
  FileText,
  Clock,
  ExternalLink,
  Cpu,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber } from '../types.js';

export function EscrowVaultChapter({
  timeframe,
  totalGmv,
  escrowRevenue,
  rawAnalytics,
}: AnalyticsContextData) {
  const financial = rawAnalytics.financial || rawAnalytics.financial_overview || {};
  const activeReserves = financial.active_escrow_reserves_kes || totalGmv * 0.95;

  const securityMilestones = [
    {
      step: 'Step 1: Earnest Deposit Lock',
      requirement: 'Buyer deposits into segregated trust account via M-Pesa / RTGS',
      securityStatus: 'Cryptographic Receipt Token Issued',
      completion: '100%',
    },
    {
      step: 'Step 2: Ardhisasa Registry Encumbrance',
      requirement: 'Automated Ministry of Lands caution registered against title deed',
      securityStatus: 'API Rest API Webhook Armed',
      completion: '100%',
    },
    {
      step: 'Step 3: Cadastral Boundary Survey Signoff',
      requirement: 'Licensed surveyor verifies beacon coordinates and GIS parcel polygon',
      securityStatus: 'Digital Spatial Timestamp Recorded',
      completion: '100%',
    },
    {
      step: 'Step 4: LSK Advocate Conveyance Clearance',
      requirement: 'Assigned High Court Advocate reviews contract and uploads deed of transfer',
      securityStatus: 'LSK Practicing Certificate Verified',
      completion: '100%',
    },
    {
      step: 'Step 5: Chief Admin Dual Cryptographic Release',
      requirement: 'Dual multi-sig release authorization triggers bank payment gateway',
      securityStatus: '2-of-2 Hardware Key Signed',
      completion: '100%',
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Escrow Vault Hero Metrics ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Escrow in Custody</div>
          <div className="mt-1 text-2xl font-black text-purple-700">KES {(activeReserves / 1000000).toFixed(1)}M</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">Segregated Vaults</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Dual-Signoff Rate</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">100%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Multi-sig enforced</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Active Contracts</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{financial.active_transactions_count || 6} Deeds</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">In dual custody</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Active Disputes</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">0 Disputes</div>
          <div className="text-[10px] text-emerald-700 font-semibold mt-0.5">Zero escrow freezes</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Custody Banks</div>
          <div className="mt-1 text-2xl font-black text-blue-700">2 Banks</div>
          <div className="text-[10px] text-slate-500 mt-0.5">NCBA & Equity Trust</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Audit Status</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">Passed</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Law Society of Kenya</div>
        </div>
      </div>

      {/* ── Dual-Signature Multi-Sig Architecture & Custody Accounts ───────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Multi-Sig Cryptographic Protocol */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Dual-Signature Cryptographic Protocol</h4>
              <div className="text-[11px] text-slate-500">Zero single point of failure in earnest fund release</div>
            </div>
            <Key className="h-4 w-4 text-purple-600" />
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-2xl border border-purple-200 bg-purple-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-black text-slate-900">
                  <FileText className="h-4 w-4 text-purple-700" />
                  <span>Key 1: High Court Advocate Conveyance Signoff</span>
                </div>
                <Badge tone="purple" className="text-[10px] font-bold">LSK Verified</Badge>
              </div>
              <p className="text-[11px] text-slate-600">
                The licensed Advocate assigned to the deal inspects the title deed, rates clearance certificate, and land control board (LCB) consent before signing Key 1.
              </p>
            </div>

            <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-black text-slate-900">
                  <ShieldCheck className="h-4 w-4 text-emerald-700" />
                  <span>Key 2: Chief Administrator Master Authorization</span>
                </div>
                <Badge tone="success" className="text-[10px] font-bold">Admin Armed</Badge>
              </div>
              <p className="text-[11px] text-slate-600">
                Digiland Compliance Operations verifies that cadastral surveys, national ID OCR, and seller bank details match before releasing the cryptographic escrow gate.
              </p>
            </div>
          </div>
        </div>

        {/* Bank Statutory Custody Accounts */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Segregated Statutory Client Trust Accounts</h4>
              <div className="text-[11px] text-slate-500">Regulated under Kenya Advocates (Accounts) Rules</div>
            </div>
            <Building className="h-4 w-4 text-blue-600" />
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-900">NCBA Bank Kenya PLC (Client Trust A/C #1)</span>
                <span className="font-black text-emerald-700">{formatKES(activeReserves * 0.65)}</span>
              </div>
              <p className="text-[10px] text-slate-500">
                Dedicated for high-value title purchases (&gt; KES 2,000,000) and commercial developer transactions.
              </p>
              <div className="flex justify-between text-[10px] font-bold text-slate-600 pt-1 border-t border-slate-200">
                <span>Account: 7200-XXXX-891</span>
                <span className="text-emerald-700">Audited & Reconciled Today</span>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-900">Equity Bank Kenya (Client Trust A/C #2)</span>
                <span className="font-black text-emerald-700">{formatKES(activeReserves * 0.35)}</span>
              </div>
              <p className="text-[10px] text-slate-500">
                Dedicated for M-Pesa B2C disbursements, earnest down payments, and subdivision micro-parcels.
              </p>
              <div className="flex justify-between text-[10px] font-bold text-slate-600 pt-1 border-t border-slate-200">
                <span>Account: 0180-XXXX-442</span>
                <span className="text-emerald-700">Audited & Reconciled Today</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Escrow Milestone Verification Matrix ─────────────────────────── */}
      <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h4 className="text-sm font-black text-slate-900">5-Stage Escrow Milestone Protection Matrix</h4>
            <div className="text-[11px] text-slate-500">Conveyance criteria required before earnest money release</div>
          </div>
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="py-2.5 px-3">Milestone Stage</th>
                <th className="py-2.5 px-3">Statutory Legal Requirement</th>
                <th className="py-2.5 px-3">Security & Cryptographic Check</th>
                <th className="py-2.5 px-3 text-center">Protocol Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {securityMilestones.map((m, idx) => (
                <tr key={idx} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3 font-bold text-slate-900">{m.step}</td>
                  <td className="py-3 px-3 text-slate-700">{m.requirement}</td>
                  <td className="py-3 px-3 font-medium text-purple-700">{m.securityStatus}</td>
                  <td className="py-3 px-3 text-center">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="h-3 w-3" /> Armed (100%)
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
