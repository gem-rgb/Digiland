import React from 'react';

export type AnalyticsChapterId =
  | 'overview'
  | 'marketplace'
  | 'revenue_taxes'
  | 'transactions'
  | 'escrow'
  | 'regional'
  | 'users'
  | 'expenses_reports';

export type TimeframeOption = '30D' | '90D' | 'YTD' | 'ALL';

export interface AnalyticsContextData {
  timeframe: TimeframeOption;
  multiplier: number;
  totalGmv: number;
  escrowRevenue: number;
  adRevenue: number;
  grossRevenue: number;
  totalStaffCompensation: number;
  totalOperatingExpenses: number;
  totalTaxes: number;
  netIncome: number;
  rawAnalytics: Record<string, any>;
  onNavigateChapter: (chapter: AnalyticsChapterId) => void;
}

export interface MetricSummary {
  label: string;
  value: string | number;
  subtext?: string;
  change?: number;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'purple' | 'blue';
  icon?: React.ComponentType<{ className?: string }>;
}

export interface StaffLedgerEntry {
  id: string;
  name: string;
  email: string;
  phone?: string;
  role: string;
  firm_or_agency?: string;
  county: string;
  tasks_completed: number;
  accrued_kes: number;
  paid_kes: number;
  balance_kes: number;
  status: 'PAID' | 'PENDING';
  last_payout_date?: string;
  disburse_url?: string;
}

export interface RegionalCountyData {
  county: string;
  listings_count: number;
  estimated_value_kes: number;
  avg_price_per_acre?: number;
  demand_score?: string;
}

export interface AdCampaignData {
  id: string;
  name: string;
  seller_name?: string;
  status: 'Active' | 'Paused' | 'Completed';
  impressions: number;
  clicks: number;
  ctr: number;
  spend_kes: number;
  roi_pct: number;
  tier?: string;
}

export const KES_FORMATTER = new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
});

export function formatKES(val: number | string): string {
  const num = typeof val === 'number' ? val : Number(String(val).replace(/,/g, ''));
  if (Number.isFinite(num)) {
    return `KES ${KES_FORMATTER.format(num)}`;
  }
  return `KES ${val}`;
}

export function formatNumber(val: number | string): string {
  const num = typeof val === 'number' ? val : Number(String(val).replace(/,/g, ''));
  if (Number.isFinite(num)) {
    return KES_FORMATTER.format(num);
  }
  return String(val);
}
