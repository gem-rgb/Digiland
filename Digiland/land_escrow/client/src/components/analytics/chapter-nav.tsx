import React from 'react';
import {
  BarChart3,
  Layers,
  Receipt,
  DollarSign,
  Lock,
  Globe,
  Users,
  Activity,
  RefreshCw,
  Download,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { Button } from '../ui/button.js';
import { AnalyticsChapterId, TimeframeOption } from './types.js';

interface ChapterNavProps {
  activeChapter: AnalyticsChapterId;
  onSelectChapter: (chapter: AnalyticsChapterId) => void;
  timeframe: TimeframeOption;
  onSelectTimeframe: (timeframe: TimeframeOption) => void;
  isRefreshing: boolean;
  onRefresh: () => void;
  onExport: () => void;
  copiedReport: boolean;
}

export const CHAPTERS_CONFIG: Array<{
  id: AnalyticsChapterId;
  number: string;
  label: string;
  shortLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  badge?: string;
}> = [
  {
    id: 'overview',
    number: '1',
    label: 'Executive Overview',
    shortLabel: 'Overview',
    icon: BarChart3,
    description: 'Consolidated executive KPIs, operating cashflow statement, and high-level platform health.',
  },
  {
    id: 'marketplace',
    number: '2',
    label: 'Marketplace & Listings',
    shortLabel: 'Marketplace',
    icon: Layers,
    description: 'Land inventory density, land use distribution, ad campaign performance, and pricing tiers.',
  },
  {
    id: 'revenue_taxes',
    number: '3',
    label: 'Revenue & Taxes',
    shortLabel: 'Revenue & Taxes',
    icon: Receipt,
    description: 'Monetization streams, 16% VAT, 5% Withholding Tax, Stamp Duty, and staff payouts.',
  },
  {
    id: 'transactions',
    number: '4',
    label: 'Transactions & Velocity',
    shortLabel: 'Transactions',
    icon: DollarSign,
    description: 'GMV transaction flow, deal velocity, M-Pesa vs Bank payout speeds, and completion rate.',
  },
  {
    id: 'escrow',
    number: '5',
    label: 'Escrow & Dual-Vault',
    shortLabel: 'Escrow & Vault',
    icon: Lock,
    description: 'Segregated trust custody, dual-signoff cryptographic security, and multi-sig milestone validation.',
  },
  {
    id: 'regional',
    number: '6',
    label: 'Properties & Regional Density',
    shortLabel: 'Regional Density',
    icon: Globe,
    description: 'County-by-county land inventory, valuation density, and regional buyer inquiry heatmaps.',
  },
  {
    id: 'users',
    number: '7',
    label: 'Users & Demographics',
    shortLabel: 'Users & Demographics',
    icon: Users,
    description: 'Buyer categories, Chama syndicates, verified landowners, and professional networks.',
  },
  {
    id: 'expenses_reports',
    number: '8',
    label: 'Financial Reports & Operating Expenses',
    shortLabel: 'Expenses & Reports',
    icon: Activity,
    description: 'Monthly infrastructure burn, SMS & AI compute costs, EBITDA P&L, and system SLA uptime.',
  },
];

export function ChapterNav({
  activeChapter,
  onSelectChapter,
  timeframe,
  onSelectTimeframe,
  isRefreshing,
  onRefresh,
  onExport,
  copiedReport,
}: ChapterNavProps) {
  const currentChapterObj = CHAPTERS_CONFIG.find((c) => c.id === activeChapter) || CHAPTERS_CONFIG[0];

  return (
    <div className="space-y-4">
      {/* ── Top Header & Global Actions Bar ───────────────────────────────── */}
      <div className="flex flex-col gap-4 rounded-3xl border border-slate-200/80 bg-white p-5 shadow-xs lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
            <span className="text-slate-400">Admin Command Centre</span>
            <ChevronRight className="h-3 w-3 text-slate-300" />
            <button
              type="button"
              onClick={() => onSelectChapter('overview')}
              className="text-emerald-700 hover:underline font-bold"
            >
              Executive Analytics
            </button>
            <ChevronRight className="h-3 w-3 text-slate-300" />
            <span className="font-black text-slate-800">
              Chapter {currentChapterObj.number}: {currentChapterObj.shortLabel}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-0.5">
            <h2 className="text-xl font-black tracking-tight text-slate-900 sm:text-2xl">
              {currentChapterObj.label}
            </h2>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-black uppercase text-emerald-800 border border-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Live Telemetry
            </span>
          </div>
          <p className="text-xs text-slate-500 max-w-2xl font-medium">
            {currentChapterObj.description}
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5 pt-2 lg:pt-0">
          {/* Timeframe Selector Pills */}
          <div className="flex items-center rounded-2xl border border-slate-200 bg-slate-100/70 p-1 text-xs font-bold shadow-inner">
            {(['30D', '90D', 'YTD', 'ALL'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onSelectTimeframe(t)}
                className={`rounded-xl px-3 py-1.5 transition-all duration-200 ${
                  timeframe === t
                    ? 'bg-white text-slate-900 shadow-xs font-black'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <Button
            type="button"
            variant="outline"
            onClick={onRefresh}
            className="h-9 rounded-2xl border-slate-200 bg-white hover:bg-slate-50 text-xs font-bold text-slate-700 shadow-xs"
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${isRefreshing ? 'animate-spin text-emerald-600' : ''}`} />
            Refresh
          </Button>

          <Button
            type="button"
            onClick={onExport}
            className="h-9 rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-xs transition-all hover:shadow"
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {copiedReport ? 'Report JSON Copied!' : 'Export Deck'}
          </Button>
        </div>
      </div>

      {/* ── Chapter Navigation Bar ────────────────────────────────────────── */}
      <div className="overflow-x-auto pb-1 -mx-2 px-2 scrollbar-thin">
        <div className="flex items-center gap-2 min-w-max border-b border-slate-200/80 pb-2">
          {CHAPTERS_CONFIG.map((chap) => {
            const Icon = chap.icon;
            const isActive = activeChapter === chap.id;
            return (
              <button
                key={chap.id}
                type="button"
                onClick={() => onSelectChapter(chap.id)}
                className={`group flex items-center gap-2 rounded-2xl px-4 py-2.5 text-xs font-black transition-all ${
                  isActive
                    ? 'bg-emerald-700 text-white shadow-md shadow-emerald-700/20'
                    : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-slate-200/70 shadow-xs'
                }`}
              >
                <div
                  className={`flex h-6 w-6 items-center justify-center rounded-xl transition ${
                    isActive ? 'bg-emerald-800 text-emerald-100' : 'bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-slate-800'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <span>
                  <span className="opacity-75 mr-1 font-semibold">{chap.number}.</span>
                  {chap.shortLabel}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
