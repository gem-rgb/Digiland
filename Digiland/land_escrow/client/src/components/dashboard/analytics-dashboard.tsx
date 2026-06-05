import React, { useState, useCallback } from 'react';
import {
  BarChart3,
  Eye,
  MousePointerClick,
  MessageSquare,
  TrendingUp,
  DollarSign,
  ShieldAlert,
  Users,
  ArrowUpRight,
  ArrowDownRight,
  MapPin,
  CreditCard,
  PieChart,
  Activity,
  Loader2,
  ChevronDown,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Separator } from '../ui/separator.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MetricCard {
  label: string;
  value: string | number;
  change?: number; // percentage change, positive = up
  icon?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent';
}

export interface CampaignRow {
  id: string;
  name: string;
  status: string;
  impressions: number;
  clicks: number;
  ctr: number;
  spend: string;
  roi: number;
}

export interface CountyPerformance {
  county: string;
  listings: number;
  views: number;
  inquiries: number;
  revenue: string;
}

export interface FeeRevenue {
  fee_type: string;
  label: string;
  amount: string;
  percentage: number;
}

export interface BuyerSegment {
  segment: string;
  label: string;
  count: number;
  percentage: number;
  avg_budget: string;
}

export interface FraudRiskBucket {
  risk_level: string;
  label: string;
  count: number;
  percentage: number;
  color: string;
}

export interface TransactionVolume {
  month: string;
  transactions: number;
  volume: string;
}

export interface SellerAnalyticsData {
  metrics: MetricCard[];
  revenue_over_time?: Array<{ month: string; revenue: string; transactions: number }>;
  campaigns: CampaignRow[];
  top_counties: CountyPerformance[];
  revenue_breakdown: FeeRevenue[];
}

export interface AdminAnalyticsData {
  platform_metrics: MetricCard[];
  revenue_by_fee: FeeRevenue[];
  fraud_distribution: FraudRiskBucket[];
  buyer_segments: BuyerSegment[];
  transaction_volumes: TransactionVolume[];
}

export interface AnalyticsDashboardProps {
  /** Mode: seller or admin */
  mode: 'seller' | 'admin';
  /** Seller analytics data (required when mode=seller) */
  sellerData?: SellerAnalyticsData;
  /** Admin analytics data (required when mode=admin) */
  adminData?: AdminAnalyticsData;
  /** API base URL for fetching data */
  apiBaseUrl?: string;
  /** Loading state */
  loading?: boolean;
  /** Additional class name */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const kshFormatter = new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
});

function formatKES(value: string | number): string {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (Number.isFinite(parsed)) return `KES ${kshFormatter.format(parsed)}`;
  return `KES ${value}`;
}

function formatNumber(value: string | number): string {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (Number.isFinite(parsed)) return kshFormatter.format(parsed);
  return String(value);
}

/* ------------------------------------------------------------------ */
/*  Metric Card Component                                              */
/* ------------------------------------------------------------------ */

function MetricCardComponent({ metric }: { metric: MetricCard }) {
  const toneColors: Record<string, string> = {
    default: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400',
    success: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
    warning: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
    danger: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400',
    accent: 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-400',
  };

  return (
    <Card className="bg-white/92 dark:bg-slate-800/90 transition-all hover:shadow-soft">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
              {metric.label}
            </div>
            <div className="text-2xl font-black tracking-tight text-foreground">
              {typeof metric.value === 'number' ? formatNumber(metric.value) : metric.value}
            </div>
          </div>
          {metric.icon && (
            <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl', toneColors[metric.tone || 'default'])}>
              {metric.icon}
            </div>
          )}
        </div>
        {metric.change != null && (
          <div className="mt-2 flex items-center gap-1.5">
            {metric.change >= 0 ? (
              <ArrowUpRight className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
            )}
            <span
              className={cn(
                'text-xs font-semibold',
                metric.change >= 0
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-rose-600 dark:text-rose-400'
              )}
            >
              {Math.abs(metric.change)}% from last period
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Simple Bar Chart Placeholder                                       */
/* ------------------------------------------------------------------ */

function BarChartPlaceholder({
  data,
  labelKey,
  valueKey,
  formatValue,
  title,
  subtitle,
  color = '#059669',
}: {
  data: Array<Record<string, any>>;
  labelKey: string;
  valueKey: string;
  formatValue?: (v: any) => string;
  title?: string;
  subtitle?: string;
  color?: string;
}) {
  if (!data.length) return null;

  const maxVal = Math.max(...data.map((d) => Number(d[valueKey]) || 0));
  const safeMax = maxVal || 1;

  return (
    <Card className="bg-white/92 dark:bg-slate-800/90">
      {(title || subtitle) && (
        <CardHeader className="pb-2">
          {title && <CardTitle className="text-base">{title}</CardTitle>}
          {subtitle && <CardDescription>{subtitle}</CardDescription>}
        </CardHeader>
      )}
      <CardContent className="space-y-3">
        {data.map((item, i) => {
          const val = Number(item[valueKey]) || 0;
          const pct = (val / safeMax) * 100;
          return (
            <div key={i} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-foreground truncate max-w-[60%]">{item[labelKey]}</span>
                <span className="font-bold text-foreground">
                  {formatValue ? formatValue(val) : formatNumber(val)}
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-muted/60 dark:bg-slate-700/40 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Donut Chart Placeholder                                            */
/* ------------------------------------------------------------------ */

function DonutChartPlaceholder({
  segments,
  title,
  subtitle,
}: {
  segments: Array<{ label: string; value: number; color: string; percentage: number }>;
  title?: string;
  subtitle?: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  let cumulativePercent = 0;

  const conicSegments = segments.map((s) => {
    const start = cumulativePercent;
    cumulativePercent += s.percentage;
    return `${s.color} ${start}% ${cumulativePercent}%`;
  });

  return (
    <Card className="bg-white/92 dark:bg-slate-800/90">
      {(title || subtitle) && (
        <CardHeader className="pb-2">
          {title && <CardTitle className="text-base">{title}</CardTitle>}
          {subtitle && <CardDescription>{subtitle}</CardDescription>}
        </CardHeader>
      )}
      <CardContent>
        <div className="flex flex-col items-center gap-6 sm:flex-row">
          <div
            className="relative h-44 w-44 shrink-0 rounded-full"
            style={{
              background: `conic-gradient(${conicSegments.join(', ')})`,
            }}
          >
            <div className="absolute inset-4 flex items-center justify-center rounded-full bg-white dark:bg-slate-800">
              <div className="text-center">
                <div className="text-lg font-black text-foreground">{formatNumber(total)}</div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Total</div>
              </div>
            </div>
          </div>
          <div className="space-y-2.5 w-full">
            {segments.map((s, i) => (
              <div key={i} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                  <span className="text-sm text-foreground">{s.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-foreground">{s.percentage.toFixed(1)}%</span>
                  <span className="text-xs text-muted-foreground">({formatNumber(s.value)})</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Seller Dashboard                                                   */
/* ------------------------------------------------------------------ */

function SellerDashboard({ data }: { data: SellerAnalyticsData }) {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Key metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.metrics.map((m, i) => (
          <MetricCardComponent key={m.label + i} metric={m} />
        ))}
      </div>

      {/* Revenue over time */}
      {data.revenue_over_time && data.revenue_over_time.length > 0 && (
        <BarChartPlaceholder
          data={data.revenue_over_time}
          labelKey="month"
          valueKey="revenue"
          formatValue={(v) => formatKES(v)}
          title="Revenue Over Time"
          subtitle="Monthly revenue from your listings"
          color="#059669"
        />
      )}

      {/* Campaign performance table */}
      {data.campaigns.length > 0 && (
        <Card className="bg-white/92 dark:bg-slate-800/90">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              Campaign Performance
            </CardTitle>
            <CardDescription>Active and recent ad campaigns</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full text-left">
              <thead className="border-b border-border/70 bg-muted/50 text-xs uppercase tracking-[0.24em] text-muted-foreground dark:bg-slate-700/30">
                <tr>
                  <th className="px-5 py-4">Campaign</th>
                  <th className="px-5 py-4">Status</th>
                  <th className="px-5 py-4 text-right">Impressions</th>
                  <th className="px-5 py-4 text-right">Clicks</th>
                  <th className="px-5 py-4 text-right">CTR</th>
                  <th className="px-5 py-4 text-right">Spend</th>
                  <th className="px-5 py-4 text-right">ROI</th>
                </tr>
              </thead>
              <tbody>
                {data.campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-4 font-semibold text-foreground">{c.name}</td>
                    <td className="px-5 py-4">
                      <Badge tone={c.status === 'Active' ? 'success' : c.status === 'Paused' ? 'warning' : 'muted'}>
                        {c.status}
                      </Badge>
                    </td>
                    <td className="px-5 py-4 text-right text-sm text-muted-foreground">{formatNumber(c.impressions)}</td>
                    <td className="px-5 py-4 text-right text-sm text-muted-foreground">{formatNumber(c.clicks)}</td>
                    <td className="px-5 py-4 text-right text-sm font-semibold text-foreground">{c.ctr.toFixed(2)}%</td>
                    <td className="px-5 py-4 text-right text-sm font-semibold text-foreground">{formatKES(c.spend)}</td>
                    <td className="px-5 py-4 text-right">
                      <span className={cn('text-sm font-bold', c.roi >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400')}>
                        {c.roi >= 0 ? '+' : ''}{c.roi.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Top performing counties */}
      {data.top_counties.length > 0 && (
        <BarChartPlaceholder
          data={data.top_counties}
          labelKey="county"
          valueKey="views"
          title="Top Performing Counties"
          subtitle="Views by county for your listings"
          color="#10b981"
        />
      )}

      {/* Revenue breakdown */}
      {data.revenue_breakdown.length > 0 && (
        <DonutChartPlaceholder
          title="Revenue Breakdown"
          subtitle="Revenue by fee category"
          segments={data.revenue_breakdown.map((f, i) => ({
            label: f.label,
            value: Number(f.amount?.replace(/,/g, '')) || 0,
            color: ['#059669', '#d97706', '#0284c7', '#dc2626', '#7c3aed', '#0891b2'][i % 6],
            percentage: f.percentage,
          }))}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Admin Dashboard                                                    */
/* ------------------------------------------------------------------ */

function AdminDashboard({ data }: { data: AdminAnalyticsData }) {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Platform-wide metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.platform_metrics.map((m, i) => (
          <MetricCardComponent key={m.label + i} metric={m} />
        ))}
      </div>

      {/* Revenue by fee type */}
      {data.revenue_by_fee.length > 0 && (
        <DonutChartPlaceholder
          title="Revenue by Fee Type"
          subtitle="Platform revenue breakdown"
          segments={data.revenue_by_fee.map((f, i) => ({
            label: f.label,
            value: Number(f.amount?.replace(/,/g, '')) || 0,
            color: ['#059669', '#d97706', '#0284c7', '#dc2626', '#7c3aed'][i % 5],
            percentage: f.percentage,
          }))}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Fraud risk distribution */}
        {data.fraud_distribution.length > 0 && (
          <Card className="bg-white/92 dark:bg-slate-800/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                Fraud Risk Distribution
              </CardTitle>
              <CardDescription>User accounts by risk level</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.fraud_distribution.map((bucket, i) => (
                <div key={i} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className="h-3 w-3 rounded-full" style={{ backgroundColor: bucket.color }} />
                      <span className="font-medium text-foreground">{bucket.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{formatNumber(bucket.count)} users</span>
                      <span className="font-bold text-foreground">{bucket.percentage.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted/60 dark:bg-slate-700/40 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${bucket.percentage}%`,
                        backgroundColor: bucket.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Buyer segment breakdown */}
        {data.buyer_segments.length > 0 && (
          <Card className="bg-white/92 dark:bg-slate-800/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Users className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                Buyer Segments
              </CardTitle>
              <CardDescription>Active buyer categories on the platform</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.buyer_segments.map((seg, i) => (
                <div key={i} className="rounded-2xl border border-border/60 bg-muted/30 p-3.5 dark:bg-slate-700/20">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-foreground">{seg.label}</span>
                    <Badge tone="outline" className="text-[10px]">{seg.count} buyers</Badge>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{seg.percentage.toFixed(1)}% of all buyers</span>
                    <span>Avg. budget: {formatKES(seg.avg_budget)}</span>
                  </div>
                  <div className="mt-2 h-1.5 w-full rounded-full bg-muted/60 dark:bg-slate-700/40 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                      style={{ width: `${seg.percentage}%` }}
                    />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Transaction volume trends */}
      {data.transaction_volumes.length > 0 && (
        <BarChartPlaceholder
          data={data.transaction_volumes}
          labelKey="month"
          valueKey="transactions"
          title="Transaction Volume Trends"
          subtitle="Monthly transaction count"
          color="#059669"
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function AnalyticsDashboard({
  mode,
  sellerData,
  adminData,
  loading = false,
  className,
}: AnalyticsDashboardProps) {
  if (loading) {
    return (
      <div className={cn('space-y-6', className)}>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="animate-pulse bg-white/92 dark:bg-slate-800/90">
              <CardContent className="p-5">
                <div className="h-4 w-24 rounded bg-muted" />
                <div className="mt-3 h-8 w-32 rounded bg-muted" />
                <div className="mt-2 h-3 w-20 rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="animate-pulse bg-white/92 dark:bg-slate-800/90">
          <CardContent className="p-6">
            <div className="h-64 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
          {mode === 'seller' ? <BarChart3 className="h-5 w-5" /> : <Activity className="h-5 w-5" />}
        </div>
        <div>
          <h2 className="text-xl font-black tracking-tight text-foreground">
            {mode === 'seller' ? 'Seller Analytics' : 'Platform Analytics'}
          </h2>
          <p className="text-sm text-muted-foreground">
            {mode === 'seller'
              ? 'Performance metrics for your listings and campaigns'
              : 'Platform-wide metrics and administrative insights'}
          </p>
        </div>
      </div>

      {mode === 'seller' && sellerData ? (
        <SellerDashboard data={sellerData} />
      ) : mode === 'admin' && adminData ? (
        <AdminDashboard data={adminData} />
      ) : (
        <Card className="bg-white/92 dark:bg-slate-800/90">
          <CardContent className="p-8 text-center">
            <BarChart3 className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            <div className="text-lg font-bold text-foreground">No analytics data available</div>
            <p className="mt-2 text-sm text-muted-foreground">
              Analytics will appear once there is sufficient activity.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Default Data Factories (for demo/fallback)                         */
/* ------------------------------------------------------------------ */

export function createDefaultSellerData(): SellerAnalyticsData {
  return {
    metrics: [
      { label: 'Total Views', value: '12,483', change: 14.2, icon: <Eye className="h-4 w-4" />, tone: 'default' },
      { label: 'Total Clicks', value: '3,291', change: 8.7, icon: <MousePointerClick className="h-4 w-4" />, tone: 'accent' },
      { label: 'Inquiries', value: '284', change: -3.1, icon: <MessageSquare className="h-4 w-4" />, tone: 'warning' },
      { label: 'Click Rate', value: '26.4%', change: 2.1, icon: <TrendingUp className="h-4 w-4" />, tone: 'success' },
    ],
    revenue_over_time: [
      { month: 'Jan', revenue: '145,000', transactions: 3 },
      { month: 'Feb', revenue: '220,000', transactions: 5 },
      { month: 'Mar', revenue: '180,000', transactions: 4 },
      { month: 'Apr', revenue: '310,000', transactions: 7 },
      { month: 'May', revenue: '290,000', transactions: 6 },
      { month: 'Jun', revenue: '420,000', transactions: 9 },
    ],
    campaigns: [
      { id: '1', name: 'Nairobi Land Promo', status: 'Active', impressions: 24500, clicks: 1820, ctr: 7.4, spend: '45,000', roi: 180 },
      { id: '2', name: 'Kiambu County Spotlight', status: 'Active', impressions: 12300, clicks: 940, ctr: 7.6, spend: '22,000', roi: 142 },
      { id: '3', name: 'Nakuru Spring Sale', status: 'Paused', impressions: 8900, clicks: 560, ctr: 6.3, spend: '15,000', roi: 95 },
    ],
    top_counties: [
      { county: 'Nairobi', listings: 45, views: 5200, inquiries: 120, revenue: '1,250,000' },
      { county: 'Kiambu', listings: 32, views: 3800, inquiries: 89, revenue: '890,000' },
      { county: 'Nakuru', listings: 28, views: 2100, inquiries: 54, revenue: '620,000' },
      { county: 'Machakos', listings: 19, views: 1500, inquiries: 32, revenue: '410,000' },
    ],
    revenue_breakdown: [
      { fee_type: 'platform', label: 'Platform Fee', amount: '380,000', percentage: 45 },
      { fee_type: 'escrow', label: 'Escrow Fee', amount: '190,000', percentage: 22 },
      { fee_type: 'promotion', label: 'Promotion Revenue', amount: '152,000', percentage: 18 },
      { fee_type: 'processing', label: 'Processing Fee', amount: '130,000', percentage: 15 },
    ],
  };
}

export function createDefaultAdminData(): AdminAnalyticsData {
  return {
    platform_metrics: [
      { label: 'Total Users', value: '8,432', change: 12.4, icon: <Users className="h-4 w-4" />, tone: 'default' },
      { label: 'Active Listings', value: '2,156', change: 8.1, icon: <MapPin className="h-4 w-4" />, tone: 'accent' },
      { label: 'Total Revenue', value: 'KES 12.4M', change: 22.3, icon: <DollarSign className="h-4 w-4" />, tone: 'success' },
      { label: 'Fraud Alerts', value: '23', change: -15.8, icon: <ShieldAlert className="h-4 w-4" />, tone: 'warning' },
    ],
    revenue_by_fee: [
      { fee_type: 'platform', label: 'Platform Fee (4%)', amount: '4,960,000', percentage: 40 },
      { fee_type: 'escrow', label: 'Escrow Fee (2%)', amount: '2,480,000', percentage: 20 },
      { fee_type: 'processing', label: 'Processing Fee', amount: '2,108,000', percentage: 17 },
      { fee_type: 'promotion', label: 'Ad Revenue', amount: '1,860,000', percentage: 15 },
      { fee_type: 'verification', label: 'Verification Fee', amount: '992,000', percentage: 8 },
    ],
    fraud_distribution: [
      { risk_level: 'low', label: 'Low Risk', count: 7800, percentage: 82.5, color: '#059669' },
      { risk_level: 'medium', label: 'Medium Risk', count: 1200, percentage: 12.7, color: '#d97706' },
      { risk_level: 'high', label: 'High Risk', count: 350, percentage: 3.7, color: '#ef4444' },
      { risk_level: 'critical', label: 'Critical', count: 82, percentage: 0.9, color: '#7f1d1d' },
    ],
    buyer_segments: [
      { segment: 'individual', label: 'Individual Buyers', count: 4200, percentage: 58, avg_budget: '850,000' },
      { segment: 'joint', label: 'Joint Buyers', count: 1800, percentage: 25, avg_budget: '2,400,000' },
      { segment: 'investor', label: 'Investors', count: 840, percentage: 12, avg_budget: '5,600,000' },
      { segment: 'corporate', label: 'Corporate', count: 360, percentage: 5, avg_budget: '12,000,000' },
    ],
    transaction_volumes: [
      { month: 'Jan', transactions: 120, volume: '1,800,000' },
      { month: 'Feb', transactions: 145, volume: '2,175,000' },
      { month: 'Mar', transactions: 132, volume: '1,980,000' },
      { month: 'Apr', transactions: 178, volume: '2,670,000' },
      { month: 'May', transactions: 195, volume: '2,925,000' },
      { month: 'Jun', transactions: 224, volume: '3,360,000' },
    ],
  };
}

export default AnalyticsDashboard;
