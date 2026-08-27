import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, ArrowLeft, ArrowDown, Banknote, BarChart3, Camera, CheckCircle2, CircleCheckBig, Clock3, Compass, ExternalLink, Eye, FileSignature, FileText, Gavel, Grid2X2, Heart, HelpCircle, Landmark, LayoutDashboard, Layers, Lock, Mail, MapPin, MessageSquare, Printer, ReceiptText, Search, ShieldAlert, ShieldCheck, Scale, Sparkles, Ticket, Upload, UserCheck, Users, WalletCards, ShoppingCart, Briefcase, Send, CheckCheck, Plus, X, Trash2, User, Phone, Info, CornerDownLeft, Filter, type LucideIcon } from 'lucide-react';
import type { FormEvent, ReactNode } from 'react';
import { readBootstrap } from './lib/bootstrap.js';
import { AppShell } from './components/layout/app-shell.js';
import { PublicShell } from './components/layout/public-shell.js';
import { PageHeader } from './components/layout/page-header.js';
import { FormRenderer } from './components/forms/serialized-form.js';
import { SignaturePad } from './components/forms/signature-pad.js';
import { PopupAdManager } from './components/ads/popup-ad-manager.js';
import { Input } from './components/ui/input.js';
import { Textarea } from './components/ui/textarea.js';
import { Badge } from './components/ui/badge.js';
import { Button } from './components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card.js';
import { Separator } from './components/ui/separator.js';
import type { ActionLink, CheckoutData, CommissionBoardData, CommissionSummary, CommissionStep, ParcelSummary, RecommendationParcelSummary } from './types.js';
import { cn } from './lib/utils.js';
import { SellerPromotionsPage } from './pages/seller-promotions-page.js';
import { PromotionTiersPage } from './pages/promotion-tiers-page.js';
import { SponsoredAdsPage } from './pages/sponsored-ads-page.js';
import { PaymentMethodSelector } from './components/checkout/payment-method-selector.js';
import { HeroShowcase } from './components/landing/hero-showcase.js';
import { AnimatedWalkthrough } from './components/landing/animated-walkthrough.js';
import { PremiumFooter } from './components/landing/premium-footer.js';
import { PriceEstimatorSection } from './components/landing/price-estimator-section.js';
import { AdminPeopleHubView, AdminKycDeskView, AdminAIEvaluationLabView } from './components/admin/admin-views.js';
import { PartitionProvider, usePartition, isRoleAllowedOnPartition, type Partition } from './lib/partition-context.js';
import { PartitionGuard } from './components/layout/partition-guard.js';
import { StaffLoginPage } from './pages/staff-login-page.js';

function PortalBar() {
  const { activePartition, setActivePartition } = usePartition();

  if (typeof window !== 'undefined') {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const params = new URLSearchParams(window.location.search);
    const hasPortalQuery = params.has('portal') || params.has('dev');
    if (!isLocal && !hasPortalQuery) {
      return null;
    }
  }

  const portals: { key: Partition; label: string; icon: string }[] = [
    { key: 'marketing', label: '🌐 Marketing (digiland.co.ke)', icon: '🌐' },
    { key: 'app', label: '📱 App (app.digiland.co.ke)', icon: '📱' },
    { key: 'staff', label: '👔 Staff (staff.digiland.co.ke)', icon: '👔' },
    { key: 'admin', label: '🛡️ Admin (admin.digiland.co.ke)', icon: '🛡️' },
  ];

  return (
    <div className="bg-slate-950 border-b border-emerald-900/60 py-2 px-4 text-xs flex flex-wrap items-center justify-between gap-2 z-50 relative">
      <div className="flex items-center gap-2 text-slate-400 font-medium">
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
        <span>Digiland Partition Architecture:</span>
        <span className="font-mono text-emerald-300 font-bold uppercase">[{activePartition} portal]</span>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        {portals.map((p) => {
          const isActive = activePartition === p.key;
          return (
            <button
              key={p.key}
              type="button"
              onClick={() => setActivePartition(p.key)}
              className={`px-3 py-1 rounded-lg font-semibold transition flex items-center gap-1.5 ${
                isActive
                  ? 'bg-emerald-600 text-white shadow-md shadow-emerald-950/40 ring-1 ring-emerald-400'
                  : 'bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-800'
              }`}
            >
              <span>{p.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const bootstrap = readBootstrap();
const kshFormatter = new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 2,
  minimumFractionDigits: 0,
});

function statusTone(status?: string) {
  if (!status) return 'muted';
  const value = status.toLowerCase();
  if (value.includes('verified') || value.includes('completed') || value.includes('signed') || value.includes('approved')) return 'success';
  if (value.includes('pending') || value.includes('initiated') || value.includes('under')) return 'warning';
  if (value.includes('fraud') || value.includes('reject') || value.includes('failed') || value.includes('disputed') || value.includes('reversed')) return 'danger';
  return 'muted';
}

function money(value: string | number) {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (Number.isFinite(parsed)) {
    return `KES ${kshFormatter.format(parsed)}`;
  }
  return `KES ${value}`;
}

function splitParagraphs(content: string) {
  return content
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
}

function PanelTitle({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <div className="text-sm font-bold uppercase tracking-[0.24em] text-emerald-700">{title}</div>
        {subtitle ? <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div> : null}
      </div>
      {action}
    </div>
  );
}

function StatusBadge({ label, tone }: { label: string; tone?: string }) {
  const toneMap: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'muted' | 'outline'> = {
    success: 'success',
    warning: 'warning',
    danger: 'danger',
    muted: 'muted',
    default: 'default',
    outline: 'outline',
  };
  return <Badge tone={toneMap[tone || 'default']}>{label}</Badge>;
}

function ListingCard({
  parcel,
  showMatchScore = false,
  className = '',
  compact = false,
  ctaLabel = 'View details',
}: {
  parcel: ParcelSummary & Partial<RecommendationParcelSummary> & { match_score?: number };
  showMatchScore?: boolean;
  className?: string;
  compact?: boolean;
  ctaLabel?: string;
}) {
  const promotionTone: 'default' | 'success' | 'warning' | 'danger' | 'muted' | 'outline' =
    parcel.promotion_tier === 'Elite' ? 'success' : parcel.promotion_tier === 'Pro' ? 'warning' : 'outline';
  const listingTone = statusTone(parcel.verification_status);
  const price = parcel.displayed_price || parcel.asking_price;
  const imageUrl = parcel.image_url || 'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=800&q=80';

  return (
    <Card className={cn('group overflow-hidden bg-white shadow-md border-slate-200/80 rounded-[1.75rem] hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1', parcel.is_promoted ? 'border-emerald-300 ring-2 ring-emerald-500/20' : '', className)}>
      <div className="relative aspect-[16/10] overflow-hidden bg-slate-900">
        <img 
          src={imageUrl} 
          alt={parcel.parcel_number} 
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105 opacity-90" 
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-black/30 pointer-events-none" />

        {/* Badges Overlay */}
        <div className="absolute left-3 top-3 flex flex-wrap items-center gap-1.5 z-10">
          {parcel.is_promoted ? <Badge tone="success" className="bg-emerald-600 text-white font-bold shadow">Featured</Badge> : null}
          {parcel.promotion_tier ? <Badge tone={promotionTone} className="font-semibold">{parcel.promotion_tier}</Badge> : null}
          {showMatchScore && parcel.match_score != null ? <Badge tone="success">{Math.round(parcel.match_score)}% match</Badge> : null}
          <span className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-[11px] font-extrabold text-white border border-white/20">
            {parcel.land_size || '1.0'} Acres
          </span>
        </div>

        <div className="absolute right-3 top-3 z-10">
          <StatusBadge label={parcel.status_badge || parcel.verification_status} tone={listingTone} />
        </div>

        {/* Bottom Image Price Overlay */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white z-10">
          <div className="flex items-center gap-1 text-xs font-medium text-slate-200 drop-shadow">
            <MapPin className="h-3.5 w-3.5 text-emerald-400" />
            <span>{parcel.county}, {parcel.constituency}</span>
          </div>
          {price ? (
            <div className="bg-emerald-700/90 backdrop-blur-md px-3 py-1 rounded-full text-xs font-black text-white shadow-md border border-emerald-400/30">
              KES {money(price)}
            </div>
          ) : null}
        </div>
      </div>

      <CardHeader className={cn('pb-2 pt-4 px-5 text-left', compact ? 'pb-2' : '')}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[10px] font-black uppercase tracking-[0.24em] text-emerald-700">Parcel Registry</div>
            <CardTitle className={cn('text-lg font-black text-slate-900', compact ? 'text-base' : '')}>Parcel {parcel.parcel_number}</CardTitle>
            <CardDescription className="text-xs text-slate-500 mt-0.5">
              {parcel.ward ? `${parcel.ward} Ward · ` : ''}{parcel.land_use_type || 'Agricultural / Residential'}
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className={cn('space-y-4 px-5 pb-5 pt-0 text-left', compact ? 'p-4 pt-0' : '')}>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Land Use</div>
            <div className="mt-0.5 font-bold text-slate-800 truncate">{parcel.land_use_type || 'General'}</div>
          </div>
          <div className="rounded-xl bg-slate-50 p-2.5 border border-slate-100">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Acreage</div>
            <div className="mt-0.5 font-bold text-slate-800 truncate">{parcel.land_size || 'N/A'} Acres</div>
          </div>
        </div>

        <a
          href={parcel.details_url}
          className="inline-flex h-11 w-full items-center justify-center rounded-full bg-emerald-700 hover:bg-emerald-800 text-xs font-bold text-white transition-all shadow-md gap-2 group-hover:bg-emerald-800"
        >
          <span>{parcel.manage_label || ctaLabel}</span>
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </a>
      </CardContent>
    </Card>
  );
}

function RecommendationSection({
  title,
  subtitle,
  items,
  emptyMessage,
  gridClassName = 'grid gap-4 md:grid-cols-2 xl:grid-cols-3',
  showMatchScore = false,
  ctaLabel = 'Open parcel',
}: {
  title: string;
  subtitle?: string;
  items: Array<ParcelSummary & Partial<RecommendationParcelSummary> & { match_score?: number }>;
  emptyMessage?: string;
  gridClassName?: string;
  showMatchScore?: boolean;
  ctaLabel?: string;
}) {
  if (!items.length) {
    return emptyMessage ? (
      <Card className="bg-white/92">
        <CardContent className="p-8 text-center text-sm text-muted-foreground">{emptyMessage}</CardContent>
      </Card>
    ) : null;
  }

  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-foreground">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-7 text-muted-foreground">{subtitle}</p> : null}
        </div>
        <Badge tone="outline">{items.length}</Badge>
      </div>
      <div className={gridClassName}>
        {items.map((parcel) => (
          <ListingCard key={parcel.parcel_number} parcel={parcel} showMatchScore={showMatchScore} compact ctaLabel={ctaLabel} />
        ))}
      </div>
    </section>
  );
}

function FeeBreakdownPanel({ checkout }: { checkout: CheckoutData }) {
  const feeBreakdown = checkout.fee_breakdown?.length
    ? checkout.fee_breakdown
    : [
        {
          key: 'land_price',
          label: 'Land Price',
          amount: checkout.land_price || checkout.agreed_price,
          description: 'The negotiated purchase price for the parcel.',
          included: true,
          tone: 'default' as const,
        },
        {
          key: 'platform_service_fee',
          label: checkout.fee_explanations?.['platform_service']?.label || 'Platform Service Fee',
          amount: checkout.platform_service_fee || '0',
          description: checkout.fee_explanations?.['platform_service']?.what || 'Covers platform operations and marketplace discovery.',
          note: checkout.fee_explanations?.['platform_service']?.why || 'Supports the marketplace and buyer discovery tools.',
          included: true,
          tone: 'warning' as const,
        },
        {
          key: 'escrow_fee',
          label: checkout.fee_explanations?.['escrow_holding']?.label || 'Escrow Fee',
          amount: checkout.escrow_fee || '0',
          description: checkout.fee_explanations?.['escrow_holding']?.what || 'Secure fund holding and settlement management.',
          note: checkout.fee_explanations?.['escrow_holding']?.why || 'Protects both buyer and seller during settlement.',
          included: true,
          tone: 'warning' as const,
        },
        {
          key: 'processing_fee',
          label: checkout.fee_explanations?.['payment_processing']?.label || 'Payment Processing Fee',
          amount: checkout.processing_fee || '0',
          description: checkout.fee_explanations?.['payment_processing']?.what || 'Payment gateway transaction costs.',
          note: checkout.fee_explanations?.['payment_processing']?.why || 'Covers payment processor fees for secure transfers.',
          included: true,
          tone: 'default' as const,
        },
        {
          key: 'legal_verification_fee',
          label: checkout.fee_explanations?.['verification']?.label || 'Verification Fee',
          amount: checkout.legal_verification_fee || '0',
          description: checkout.fee_explanations?.['verification']?.what || 'Document review and compliance verification.',
          note: checkout.include_legal_verification ? 'Selected' : 'Optional',
          included: Boolean(checkout.include_legal_verification),
          tone: 'default' as const,
        },
        {
          key: 'due_diligence_fee',
          label: checkout.fee_explanations?.['due_diligence']?.label || 'Due Diligence Fee',
          amount: checkout.due_diligence_fee || '0',
          description: checkout.fee_explanations?.['due_diligence']?.what || 'Legal document review and due diligence.',
          note: checkout.include_due_diligence ? 'Selected' : 'Optional',
          included: Boolean(checkout.include_due_diligence),
          tone: 'default' as const,
        },
        {
          key: 'total_payable',
          label: 'TOTAL PAYABLE',
          amount: checkout.total_payable || checkout.grand_total || checkout.agreed_price,
          description: 'Land price plus all selected service fees.',
          included: true,
          tone: 'success' as const,
        },
      ];
  if (!feeBreakdown.length) return null;

  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-foreground">Transparent fee breakdown</div>
        <Badge tone="outline">Itemized</Badge>
      </div>

      <div className="space-y-3">
        {feeBreakdown.map((line) => (
          <div
            key={line.key}
            className={cn(
              'rounded-3xl border p-4 shadow-sm',
              line.tone === 'success' ? 'border-emerald-200 bg-emerald-50/70' : 'border-stone-200 bg-white'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="font-semibold text-foreground">{line.label}</div>
                <div className="text-xs leading-6 text-muted-foreground">{line.description}</div>
                {line.note ? <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">{line.note}</div> : null}
              </div>
              <div className="text-right">
                <div className={cn('text-base font-black tracking-tight', line.tone === 'success' ? 'text-emerald-700' : 'text-foreground')}>
                  {money(line.amount)}
                </div>
                {line.included === false ? <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Optional</div> : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatGrid() {
  const stats = bootstrap.stats || [];
  if (!stats.length) return null;
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.label} className="border-border/70 bg-white/90">
          <CardContent className="p-5">
            <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">{stat.label}</div>
            <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{stat.value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ParcelGrid() {
  const parcels = bootstrap.parcels || [];
  if (!parcels.length) {
    return (
      <Card className="bg-white/90">
        <CardContent className="p-8 text-center">
          <Landmark className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <div className="text-lg font-bold text-foreground">{bootstrap.search_active ? `No parcels found for "${bootstrap.search_query || 'that search'}"` : 'No parcels found'}</div>
          <p className="mt-2 text-sm text-muted-foreground">{bootstrap.search_active ? 'Try a county, constituency, ward, parcel number, or a broader price range.' : 'Listings will appear here once parcels are uploaded and reviewed.'}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {parcels.map((parcel) => (
        <ListingCard key={parcel.parcel_number} parcel={parcel} />
      ))}
    </div>
  );
}

function TransactionTable() {
  const transactions = bootstrap.transactions || [];
  if (!transactions.length) {
    return (
      <Card className="bg-white/90">
        <CardContent className="p-8 text-center">
          <ReceiptText className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <div className="text-lg font-bold text-foreground">No transactions yet</div>
          <p className="mt-2 text-sm text-muted-foreground">Your recent escrow activity will appear here.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white/90">
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-left">
          <thead className="border-b border-border/70 bg-muted/50 text-xs uppercase tracking-[0.24em] text-muted-foreground">
            <tr>
              <th className="px-5 py-4">Transaction</th>
              <th className="px-5 py-4">Parcel</th>
              <th className="px-5 py-4">Role</th>
              <th className="px-5 py-4">Amount</th>
              <th className="px-5 py-4">Status</th>
              <th className="px-5 py-4">Date</th>
              <th className="px-5 py-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr key={tx.id} className="border-b border-border/60 last:border-0">
                <td className="px-5 py-4 font-semibold text-foreground">{tx.id.slice(0, 8).toUpperCase()}</td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{tx.parcel_number}</td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{tx.role_label}</td>
                <td className="px-5 py-4 font-semibold text-foreground">{money(tx.amount)}</td>
                <td className="px-5 py-4">
                  <StatusBadge label={tx.status} tone={tx.status_tone} />
                  {tx.is_joint_purchase ? <span className="ml-2 inline-flex items-center rounded-full bg-teal-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-teal-800">Joint</span> : null}
                </td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{tx.created_at}</td>
                <td className="px-5 py-4 text-right">
                  <a href={tx.action_url} className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-semibold text-foreground transition-colors hover:bg-muted">
                    {tx.action_label}
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function commissionCurrentStep(commission: CommissionSummary) {
  return commission.steps.find((step) => step.active) || commission.steps.find((step) => step.state === 'current') || commission.steps[0];
}

type CommissionAction = {
  label: string;
  href: string;
  tone?: 'default' | 'secondary' | 'outline' | 'ghost' | 'accent';
  method?: 'get' | 'post';
};

function actionButtonClass(tone: CommissionAction['tone'] = 'default') {
  switch (tone) {
    case 'secondary':
      return 'inline-flex h-10 items-center justify-center rounded-full bg-slate-900 px-4 text-sm font-semibold text-white transition-colors hover:bg-slate-800';
    case 'outline':
      return 'inline-flex h-10 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted';
    case 'ghost':
      return 'inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted';
    case 'accent':
      return 'inline-flex h-10 items-center justify-center rounded-full bg-emerald-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-emerald-700';
    default:
      return 'inline-flex h-10 items-center justify-center rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90';
  }
}

function CommissionStepRail({ commission }: { commission: CommissionSummary }) {
  const toneFor = (state: CommissionStep['state']) => {
    if (state === 'complete') return 'success';
    if (state === 'current') return 'warning';
    if (state === 'skipped') return 'muted';
    return 'outline';
  };

  return (
    <div className="space-y-3">
      {commission.steps.map((step, index) => (
        <div
          key={step.key}
          className={cn(
            'rounded-3xl border p-4 shadow-sm',
            step.state === 'complete'
              ? 'border-emerald-200 bg-emerald-50/60'
              : step.state === 'current'
                ? 'border-amber-200 bg-amber-50/70'
                : step.state === 'skipped'
                  ? 'border-border bg-muted/30 opacity-70'
                  : 'border-border bg-white'
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.28em] text-muted-foreground">Step {index + 1}</div>
              <div className="mt-1 font-semibold text-foreground">{step.label}</div>
            </div>
            <StatusBadge label={step.state} tone={toneFor(step.state)} />
          </div>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">{step.description}</p>
        </div>
      ))}
    </div>
  );
}

function CommissionDocumentChecklist({ commission }: { commission: CommissionSummary }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {commission.required_documents.map((requiredDoc) => {
        const uploadedDoc = commission.documents.find((document) => document.document_type === requiredDoc.key);
        const present = Boolean(uploadedDoc);
        const tone = uploadedDoc?.verification_status === 'Match' ? 'success' : present ? 'warning' : 'muted';
        return (
          <div
            key={requiredDoc.key}
            className={cn(
              'rounded-3xl border p-4 shadow-sm',
              present ? 'border-emerald-200 bg-emerald-50/60' : 'border-border bg-white'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-semibold text-foreground">{requiredDoc.title}</div>
                <div className="mt-1 text-xs leading-6 text-muted-foreground">{requiredDoc.description}</div>
              </div>
              <StatusBadge label={present ? (uploadedDoc?.verification_status || 'Present') : 'Missing'} tone={tone} />
            </div>
            <div className="mt-3 text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">
              {present ? `Uploaded ${uploadedDoc?.uploaded_at || ''}`.trim() : 'Awaiting upload'}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CommissionCard({
  commission,
  primaryAction,
  secondaryAction,
  footer,
}: {
  commission: CommissionSummary;
  primaryAction?: CommissionAction | null;
  secondaryAction?: CommissionAction | null;
  footer?: ReactNode;
}) {
  const currentStep = commissionCurrentStep(commission);

  const renderAction = (action?: CommissionAction | null) => {
    if (!action) return null;
    if (action.method === 'post') {
      return (
        <form method="post" action={action.href} className="inline-flex">
          <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
          <button type="submit" className={actionButtonClass(action.tone)}>
            {action.label}
          </button>
        </form>
      );
    }

    return (
      <a href={action.href} className={actionButtonClass(action.tone)}>
        {action.label}
      </a>
    );
  };

  return (
    <Card className="bg-white/92">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{commission.parcel.parcel_number}</CardTitle>
            <CardDescription>
              {commission.parcel.county}, {commission.parcel.constituency}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {commission.is_joint_purchase ? <Badge tone="outline">Joint</Badge> : null}
            <StatusBadge label={commission.status_label} tone={commission.status_tone} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl bg-muted/60 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Price</div>
            <div className="mt-1 text-sm font-semibold text-foreground">{money(commission.parcel.displayed_price || commission.parcel.asking_price || '0')}</div>
          </div>
          <div className="rounded-2xl bg-muted/60 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Documents</div>
            <div className="mt-1 text-sm font-semibold text-foreground">{commission.document_count} uploaded</div>
          </div>
          <div className="rounded-2xl bg-muted/60 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Current step</div>
            <div className="mt-1 text-sm font-semibold text-foreground">{currentStep?.label || commission.status_label}</div>
          </div>
        </div>

        {footer ? <div className="rounded-2xl border border-border bg-muted/30 p-3 text-sm leading-7 text-muted-foreground">{footer}</div> : null}

        <div className="flex flex-wrap gap-2">
          {renderAction(primaryAction)}
          {renderAction(secondaryAction)}
        </div>
      </CardContent>
    </Card>
  );
}

function CommissionListSection({
  title,
  subtitle,
  commissions,
  emptyMessage,
  mode,
  gridClassName = 'grid gap-4 xl:grid-cols-2',
}: {
  title: string;
  subtitle?: string;
  commissions: CommissionSummary[];
  emptyMessage?: string;
  mode: 'buyer' | 'agent-open' | 'agent-active' | 'lawyer';
  gridClassName?: string;
}) {
  if (!commissions.length) {
    if (!emptyMessage) return null;
    return (
      <Card className="bg-white/92">
        <CardContent className="p-8 text-center text-sm text-muted-foreground">{emptyMessage}</CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-black tracking-tight text-foreground">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-7 text-muted-foreground">{subtitle}</p> : null}
        </div>
        <Badge tone="outline">{commissions.length}</Badge>
      </div>
      <div className={gridClassName}>
        {commissions.map((commission) => {
          const currentStep = commissionCurrentStep(commission);
          let primaryAction: CommissionAction | null = null;
          let secondaryAction: CommissionAction | null = null;
          let footer: ReactNode = null;

          if (mode === 'buyer') {
            primaryAction = commission.transaction_url
              ? { label: 'Continue to payment', href: commission.transaction_url, tone: 'default' }
              : { label: 'Open commission', href: commission.detail_url, tone: 'outline' };
            secondaryAction = { label: 'View progress', href: commission.detail_url, tone: 'secondary' };
            footer = commission.accepted_by
              ? <>Accepted by <span className="font-semibold text-foreground">{commission.accepted_by.email}</span></>
              : 'Waiting for an agent to accept this commission.';
          } else if (mode === 'agent-open') {
            primaryAction = commission.can_accept
              ? { label: 'Accept job', href: commission.accept_url, tone: 'accent', method: 'post' }
              : { label: 'View details', href: commission.detail_url, tone: 'outline' };
            secondaryAction = { label: 'Open commission', href: commission.detail_url, tone: 'secondary' };
            footer = `Matched to ${commission.target_county}, ${commission.target_constituency}.`;
          } else if (mode === 'agent-active') {
            primaryAction = commission.steps_url
              ? { label: 'Continue steps', href: commission.steps_url, tone: 'default' }
              : { label: 'View details', href: commission.detail_url, tone: 'outline' };
            secondaryAction = commission.transaction_url
              ? { label: 'Continue to payment', href: commission.transaction_url, tone: 'secondary' }
              : { label: 'View progress', href: commission.detail_url, tone: 'secondary' };
            footer = currentStep ? `Current step: ${currentStep.label}.` : 'Tracking the active commission workflow.';
          } else {
            primaryAction = commission.review_url
              ? { label: 'Review documents', href: commission.review_url, tone: 'accent', method: 'post' }
              : { label: 'View details', href: commission.detail_url, tone: 'outline' };
            secondaryAction = { label: 'View progress', href: commission.detail_url, tone: 'secondary' };
            footer = commission.assigned_lawyer
              ? <>Assigned lawyer <span className="font-semibold text-foreground">{commission.assigned_lawyer.email}</span></>
              : 'Waiting for the lawyer review queue.';
          }

          return (
            <CommissionCard
              key={commission.id}
              commission={commission}
              primaryAction={primaryAction}
              secondaryAction={secondaryAction}
              footer={footer}
            />
          );
        })}
      </div>
    </section>
  );
}


function LegalCards(laws: NonNullable<typeof bootstrap.laws>) {
  return (
    <div className="space-y-4">
      {laws.map((law) => (
        <Card key={`${law.title}-${law.citation}`} className={law.required ? 'bg-white/92' : 'bg-white/88'}>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">{law.title}</CardTitle>
                <CardDescription>{law.citation}</CardDescription>
              </div>
              <StatusBadge label={law.required ? 'Core' : 'Conditional'} tone={law.required ? 'success' : 'warning'} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-7 text-foreground">{law.summary}</p>
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
              <span>Applies to: {law.applies_to}</span>
              <a href={law.official_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 font-semibold text-emerald-700 hover:text-emerald-800">
                Open official source
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function DashboardPage() {
  const role = bootstrap.user?.role || 'Buyer';
  const displayName = bootstrap.user?.full_name || (bootstrap.user?.email ? bootstrap.user.email.split('@')[0] : 'User');
  const isAdmin = role === 'Admin';
  const isAgent = role === 'Agent';
  const isLawyer = role === 'Lawyer';
  const isSeller = role === 'Seller';

  // Role-customized sub-channels
  const channelsByRole: Record<string, { id: string; name: string; icon: any; badge?: string }[]> = {
    Buyer: [
      { id: 'overview', name: 'overview', icon: LayoutDashboard },
      { id: 'parcels', name: 'marketplace', icon: Grid2X2 },
      { id: 'transactions', name: 'escrow-deposits', icon: ReceiptText },
      { id: 'legal', name: 'legal-clearance', icon: Scale },
    ],
    Seller: [
      { id: 'overview', name: 'overview', icon: LayoutDashboard },
      { id: 'parcels', name: 'my-parcels', icon: Grid2X2, badge: `${(bootstrap.parcels || []).length || ''}` },
      { id: 'promotions', name: 'promotions-ads', icon: Sparkles },
      { id: 'transactions', name: 'escrow-payouts', icon: ReceiptText },
      { id: 'legal', name: 'seller-laws', icon: Scale },
    ],
    Lawyer: [
      { id: 'overview', name: 'overview', icon: LayoutDashboard },
      { id: 'commissions', name: 'conveyancing-tasks', icon: Gavel, badge: `${(bootstrap.active_commissions || []).length || ''}` },
      { id: 'transactions', name: 'escrow-settlements', icon: ReceiptText },
      { id: 'legal', name: 'legal-acts-lcb', icon: Scale },
    ],
    Agent: [
      { id: 'overview', name: 'overview', icon: LayoutDashboard },
      { id: 'commissions', name: 'site-inspections', icon: Briefcase, badge: `${(bootstrap.active_commissions || []).length || ''}` },
      { id: 'parcels', name: 'parcel-listings', icon: Grid2X2 },
      { id: 'transactions', name: 'earned-commissions', icon: ReceiptText },
    ],
    Admin: [
      { id: 'overview', name: 'overview', icon: LayoutDashboard },
      { id: 'people', name: 'people-staff', icon: UserCheck, badge: `${(bootstrap.all_users || bootstrap.professionals || []).length || ''}` },
      { id: 'kyc', name: 'kyc-desk', icon: ShieldAlert, badge: `${(bootstrap.pending_agent_applications || []).length || ''}` },
      { id: 'ailab', name: 'ai-eval-lab', icon: Sparkles, badge: `${bootstrap.ai_evaluation?.accuracy_pct ? `${bootstrap.ai_evaluation.accuracy_pct}%` : ''}` },
      { id: 'transactions', name: 'escrow-settlements', icon: ReceiptText, badge: `${(bootstrap.transactions || []).length || ''}` },
      { id: 'analytics', name: 'analytics-suite', icon: BarChart3 },
      { id: 'parcels', name: 'all-parcels', icon: Grid2X2 },
      { id: 'legal', name: 'statutory-compliance', icon: Scale },
    ],
  };

  const channels = channelsByRole[role] || channelsByRole.Buyer;
  const [activeTab, setActiveTab] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const searchTab = new URLSearchParams(window.location.search).get('tab');
      const hashTab = window.location.hash.replace('#', '');
      return searchTab || hashTab || 'overview';
    }
    return 'overview';
  });

  useEffect(() => {
    const syncTab = () => {
      const searchTab = new URLSearchParams(window.location.search).get('tab');
      const hashTab = window.location.hash.replace('#', '');
      const target = searchTab || hashTab || 'overview';
      setActiveTab(target);
    };
    window.addEventListener('hashchange', syncTab);
    window.addEventListener('popstate', syncTab);
    return () => {
      window.removeEventListener('hashchange', syncTab);
      window.removeEventListener('popstate', syncTab);
    };
  }, []);

  const activeCommissions = bootstrap.active_commissions || bootstrap.commissions || [];
  const activeSpotlightCommission = (isAgent || isLawyer || isAdmin) ? activeCommissions[0] : null;
  const sellerParcels = bootstrap.parcels || [];
  const transactions = bootstrap.transactions || [];
  const recentTransactions = transactions.slice(0, 6);
  const rawStats = bootstrap.stats || [];

  // Filter stats so Buyer only sees buyer-relevant metrics (no "active commissions")
  const stats = useMemo(() => {
    return rawStats.filter((stat) => {
      if (role === 'Buyer' && stat.label.toLowerCase().includes('commission')) {
        return false;
      }
      return true;
    });
  }, [rawStats, role]);

  return (
    <div className="flex h-[calc(100vh-8rem)] min-h-[680px] flex-col overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-xl md:flex-row text-slate-900">
      {/* Left Sub-Sidebar: Role Workspace Channels */}
      <div className="flex w-full flex-col border-b border-slate-200/90 bg-slate-50 md:w-64 lg:w-72 md:border-r md:border-b-0 shrink-0">
        {/* Workspace Title Header */}
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-4 bg-white">
          <div className="flex items-center gap-2">
            <span className="font-black text-sm text-slate-900 tracking-wide">{role} Workspace</span>
          </div>
          <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-[9px] font-black uppercase text-emerald-700 border border-emerald-200">
            Live
          </span>
        </div>

        {/* Channels List */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
          <div>
            <div className="px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 flex items-center justify-between">
              <span>Modules</span>
              <span className="text-[9px] text-emerald-700 font-bold">{role}</span>
            </div>
            <div className="mt-1 space-y-0.5">
              {channels.map((channel) => {
                const isActive = activeTab === channel.id;
                const Icon = channel.icon;
                return (
                  <button
                    key={channel.id}
                    onClick={() => setActiveTab(channel.id)}
                    className={cn(
                      'flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-bold transition-all duration-150',
                      isActive
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200/80 shadow-xs'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    )}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className={cn('text-sm font-extrabold', isActive ? 'text-emerald-700' : 'text-slate-400')}>#</span>
                      <span className="truncate">{channel.name}</span>
                    </div>
                    {channel.badge && channel.badge !== '0' && (
                      <span className="rounded-full bg-emerald-100 px-1.5 py-0.2 text-[9px] font-black text-emerald-800">
                        {channel.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Quick Shortcuts Section */}
          <div>
            <div className="px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">
              Shortcuts
            </div>
            <div className="mt-1 space-y-1">
              <a
                href="/messages/"
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
              >
                <MessageSquare className="h-4 w-4 text-purple-600" />
                <span>Open Chat & DMs</span>
              </a>
              <a
                href="/transactions/"
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
              >
                <ReceiptText className="h-4 w-4 text-emerald-600" />
                <span>Escrow Ledger</span>
              </a>
              {isSeller && (
                <a
                  href="/seller/promotions/"
                  className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
                >
                  <Sparkles className="h-4 w-4 text-amber-600" />
                  <span>Promote Listing</span>
                </a>
              )}
            </div>
          </div>
        </div>

        {/* User Status Bar Footer */}
        <div className="border-t border-slate-200 p-3 bg-white flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-600 text-xs font-black text-white shrink-0 shadow-xs">
              {displayName.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 text-left">
              <div className="truncate text-xs font-bold text-slate-900">{displayName}</div>
              <div className="text-[10px] text-emerald-700 font-semibold capitalize">{role} Verified</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Main Dashboard Workspace Canvas */}
      <div className="flex flex-1 flex-col bg-slate-50/50 overflow-hidden">
        {/* Workspace Canvas Header */}
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-6 bg-white shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-xl font-extrabold text-emerald-600">#</span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-black text-slate-900 capitalize">
                  {channels.find((c) => c.id === activeTab)?.name || activeTab}
                </h3>
                <Badge tone="outline" className="bg-slate-100 text-[9px] uppercase font-bold py-0 text-slate-700 border-slate-200">
                  {role} Hub
                </Badge>
              </div>
            </div>
          </div>

          {/* Header Action Buttons */}
          <div className="flex items-center gap-2">
            {!isSeller && !isAdmin && !isAgent && !isLawyer && (
              <a href="/parcels/" className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-4 text-xs font-bold transition shadow-xs gap-1.5">
                <Grid2X2 className="h-3.5 w-3.5" /> Browse Parcels
              </a>
            )}
            {isSeller && (
              <a href="/parcels/upload/" className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-4 text-xs font-bold transition shadow-xs gap-1.5">
                <Plus className="h-3.5 w-3.5" /> List Parcel
              </a>
            )}
            {isAdmin ? (
              <>
                <button
                  type="button"
                  onClick={() => setActiveTab('people')}
                  className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-3.5 text-xs font-bold transition shadow-xs gap-1.5"
                >
                  <UserCheck className="h-3.5 w-3.5" /> People & Staff
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('kyc')}
                  className="hidden sm:inline-flex h-9 items-center justify-center rounded-xl border border-slate-300 bg-white hover:bg-slate-50 text-slate-800 px-3.5 text-xs font-bold transition gap-1.5"
                >
                  <ShieldAlert className="h-3.5 w-3.5 text-amber-600" /> KYC Desk
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('ailab')}
                  className="hidden md:inline-flex h-9 items-center justify-center rounded-xl border border-purple-200 bg-purple-50 hover:bg-purple-100 text-purple-800 px-3 text-xs font-bold transition gap-1.5"
                >
                  <Sparkles className="h-3.5 w-3.5 text-purple-600" /> AI Eval Lab
                </button>
                <a
                  href="/admin/"
                  target="_blank"
                  rel="noreferrer"
                  className="hidden lg:inline-flex h-9 items-center justify-center rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 px-3 text-xs font-bold transition gap-1"
                >
                  <ExternalLink className="h-3.5 w-3.5" /> Django Admin
                </a>
              </>
            ) : (isAgent || isLawyer) ? (
              <a href="/agent/approvals/" className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-4 text-xs font-bold transition shadow-xs gap-1.5">
                <Gavel className="h-3.5 w-3.5" /> Approvals Hub
              </a>
            ) : null}
            <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[10px] font-bold text-emerald-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Dual Escrow</span>
            </div>
          </div>
        </div>

        {/* Main Body Content Scrollable Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Hero Banner Card */}
              <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-r from-emerald-50 via-teal-50/50 to-white p-6 text-slate-900 shadow-sm relative overflow-hidden">
                <div className="absolute right-0 top-0 h-48 w-48 bg-emerald-200/40 rounded-full blur-3xl pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1 text-left">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 text-[10px] font-black uppercase tracking-wider">
                        {role} Verified
                      </span>
                      <span className="text-[11px] text-slate-500 font-semibold flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        Live Escrow Session
                      </span>
                    </div>
                    <h2 className="text-xl sm:text-2xl font-black tracking-tight text-slate-950">
                      Welcome back, {displayName}
                    </h2>
                    <p className="text-xs text-slate-600 max-w-xl font-medium leading-relaxed">
                      Real-time overview of your land escrow pipeline, legal clearances, and verified settlements across Kenya.
                    </p>
                  </div>
                </div>
              </div>

              {/* KPI Stats Row (Rafiki AI Light Aesthetic) */}
              {stats.length > 0 && (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {stats.map((stat) => (
                    <div
                      key={stat.label}
                      className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-xs transition hover:border-emerald-400 hover:shadow-md"
                    >
                      <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                        {stat.label}
                      </div>
                      <div className="mt-2 text-2xl font-black tracking-tight text-slate-950">
                        {stat.value}
                      </div>
                      <div className="mt-1 flex items-center gap-1 text-[10px] font-bold text-emerald-700">
                        <ShieldCheck className="h-3 w-3" />
                        <span>Escrow Protected</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Admin Specific Action & Operational Cards */}
              {isAdmin && (
                <div className="grid gap-4 md:grid-cols-3">
                  {/* People & Staff Provisioning Card */}
                  <div className="rounded-3xl border border-blue-200 bg-gradient-to-br from-blue-50/70 to-white p-5 text-left space-y-3 shadow-xs">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-black uppercase text-blue-800 border border-blue-200">
                        <Gavel className="h-3 w-3" /> People Hub
                      </span>
                      <span className="text-[10px] text-slate-500 font-bold">Direct & Invite Modes</span>
                    </div>
                    <h4 className="text-base font-black text-slate-900">People & Staff Hub</h4>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Manage all platform users, reassign roles, and provision verified Advocates (LSK Roll) and Licensed Agents (EARB).
                    </p>
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => setActiveTab('people')}
                        className="inline-flex h-9 items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-500 px-4 text-xs font-bold text-white shadow-xs transition gap-1.5"
                      >
                        <UserCheck className="h-3.5 w-3.5" />
                        Open People Hub →
                      </button>
                    </div>
                  </div>

                  {/* KYC Approvals & Identity Verification Card */}
                  <div className="rounded-3xl border border-amber-200 bg-gradient-to-br from-amber-50/70 to-white p-5 text-left space-y-3 shadow-xs">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-black uppercase text-amber-800 border border-amber-200">
                        <ShieldAlert className="h-3 w-3" /> Identity Desk
                      </span>
                      <span className="text-[10px] text-amber-700 font-bold">
                        {(bootstrap.pending_agent_applications || []).length} Pending
                      </span>
                    </div>
                    <h4 className="text-base font-black text-slate-900">KYC Verification Desk</h4>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Side-by-side inspection of National IDs, DCI Good Conduct certificates, and KRA PINs with AI telemetry.
                    </p>
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => setActiveTab('kyc')}
                        className="inline-flex h-9 items-center justify-center rounded-xl bg-amber-600 hover:bg-amber-500 px-4 text-xs font-bold text-white shadow-xs transition gap-1.5"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Review Pending KYC →
                      </button>
                    </div>
                  </div>

                  {/* AI Evaluation Benchmark Lab Card */}
                  <div className="rounded-3xl border border-purple-200 bg-gradient-to-br from-purple-50/70 to-white p-5 text-left space-y-3 shadow-xs">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-100 px-2.5 py-0.5 text-[10px] font-black uppercase text-purple-800 border border-purple-200">
                        <Sparkles className="h-3 w-3" /> AI Lab
                      </span>
                      <span className="text-[10px] text-purple-700 font-bold">
                        {bootstrap.ai_evaluation?.accuracy_pct || 100}% Accuracy
                      </span>
                    </div>
                    <h4 className="text-base font-black text-slate-900">AI Evaluation Suite</h4>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      Benchmark Laplacian blur, Tesseract OCR, and Canny edge analysis against ground-truth Kenyan documents.
                    </p>
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => setActiveTab('ailab')}
                        className="inline-flex h-9 items-center justify-center rounded-xl bg-purple-600 hover:bg-purple-500 px-4 text-xs font-bold text-white shadow-xs transition gap-1.5"
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                        Open AI Evaluation Lab →
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Spotlight Active Pipeline Card */}
              {activeSpotlightCommission && (
                <div className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-5 text-left shadow-xs relative overflow-hidden">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-black uppercase text-emerald-800">
                          Spotlight Workflow
                        </span>
                        <span className="text-xs text-slate-600 font-bold">Parcel {activeSpotlightCommission.parcel_number}</span>
                      </div>
                      <h4 className="text-base font-black text-slate-900">
                        {activeSpotlightCommission.status_display || activeSpotlightCommission.status}
                      </h4>
                      <p className="text-xs text-slate-600">
                        Assigned Agent: <strong className="text-slate-900">{activeSpotlightCommission.accepted_by?.full_name || 'Awaiting Agent'}</strong> · County: {activeSpotlightCommission.county || 'Kenya'}
                      </p>
                    </div>

                    <a
                      href={activeSpotlightCommission.detail_url || '/buyer/dashboard/'}
                      className="inline-flex h-10 items-center justify-center rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white px-5 text-xs font-bold transition shadow-xs whitespace-nowrap gap-1.5"
                    >
                      <span>Manage Pipeline</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </a>
                  </div>
                </div>
              )}

              {/* Recent Activity Stream */}
              <div className="rounded-3xl border border-slate-200 bg-white p-5 text-left space-y-4 shadow-sm">
                <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                  <div className="flex items-center gap-2">
                    <ReceiptText className="h-4 w-4 text-emerald-600" />
                    <h4 className="text-xs font-black uppercase tracking-wider text-slate-900">
                      Recent Escrow Activity
                    </h4>
                  </div>
                  <a href="/transactions/" className="text-[11px] font-bold text-emerald-700 hover:underline">
                    View full ledger →
                  </a>
                </div>

                {recentTransactions.length === 0 ? (
                  <div className="py-6 text-center text-xs text-slate-500">
                    No recent transaction events recorded yet.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {recentTransactions.map((tx: any) => (
                      <div key={tx.id} className="flex items-center justify-between py-3 gap-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                            <ReceiptText className="h-4 w-4" />
                          </div>
                          <div>
                            <div className="font-bold text-xs text-slate-900">Parcel {tx.parcel_number}</div>
                            <div className="text-[10px] text-slate-500 truncate max-w-xs sm:max-w-md">
                              Buyer: {tx.buyer_email}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <div className="font-black text-emerald-700 text-xs">KES {money(tx.amount)}</div>
                            <div className="text-[9px] text-slate-500 font-semibold uppercase">{tx.status}</div>
                          </div>
                          <a
                            href="/transactions/"
                            className="hidden sm:inline-flex h-7 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 px-3 text-[10px] font-bold text-slate-700 hover:bg-slate-100"
                          >
                            Details
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: COMMISSIONS & CONVEYANCING / KYC APPROVALS DESK */}
          {activeTab === 'commissions' && (
            <div className="space-y-6 text-left">
              {isAdmin ? (
                <>
                  {/* Admin KYC Header */}
                  <div className="rounded-3xl border border-amber-200 bg-amber-50/60 p-5 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="h-5 w-5 text-amber-600" />
                        <h4 className="text-sm font-black text-slate-900">Agent KYC & Identity Verification Queue</h4>
                      </div>
                      <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
                        {(bootstrap.pending_agent_applications || []).length} Pending Review
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 max-w-2xl">
                      Review statutory compliance documents submitted by field agent applicants before granting escrow inspection clearance.
                    </p>
                  </div>

                  {/* Applications Grid */}
                  {(!bootstrap.pending_agent_applications || bootstrap.pending_agent_applications.length === 0) ? (
                    <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center text-slate-500 space-y-3 shadow-sm">
                      <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600" />
                      <div className="text-sm font-bold text-slate-900">All agent applications are reviewed!</div>
                      <p className="text-xs text-slate-500 max-w-sm mx-auto">
                        No pending applicant KYC records currently awaiting administrative verification.
                      </p>
                    </div>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                      {bootstrap.pending_agent_applications.map((app: any) => (
                        <div key={app.id} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4 shadow-sm">
                          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                            <div className="flex items-center gap-3">
                              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700 font-black border border-amber-200">
                                {app.name?.charAt(0) || 'A'}
                              </div>
                              <div>
                                <div className="font-bold text-xs text-slate-900">{app.name || app.email}</div>
                                <div className="text-[10px] text-slate-500">{app.email}</div>
                                <div className="text-[10px] text-slate-500">{app.phone || 'No phone'}</div>
                              </div>
                            </div>
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[9px] font-black uppercase text-amber-800 border border-amber-200">
                              {app.kyc?.status || 'Pending'}
                            </span>
                          </div>

                          {/* Documents Row */}
                          <div className="space-y-1.5 text-xs">
                            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Attached Documents</div>
                            <div className="flex flex-wrap gap-2">
                              {app.kyc?.id_photo_url && (
                                <a
                                  href={app.kyc.id_photo_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100"
                                >
                                  <FileText className="h-3 w-3 text-blue-600" /> National ID Photo
                                </a>
                              )}
                              {app.kyc?.resume_url && (
                                <a
                                  href={app.kyc.resume_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100"
                                >
                                  <FileText className="h-3 w-3 text-purple-600" /> Resume / CV
                                </a>
                              )}
                              {app.kyc?.certificate_url && (
                                <a
                                  href={app.kyc.certificate_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100"
                                >
                                  <ShieldCheck className="h-3 w-3 text-emerald-600" /> DCI Good Conduct
                                </a>
                              )}
                              {app.kyc?.practicing_cert_url && (
                                <a
                                  href={app.kyc.practicing_cert_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-700 hover:bg-slate-100"
                                >
                                  <Scale className="h-3 w-3 text-amber-600" /> Practicing Certificate
                                </a>
                              )}
                            </div>
                          </div>

                          {/* Action Form Buttons */}
                          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                            <form method="POST" action={app.reject_url}>
                              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token} />
                              <button
                                type="submit"
                                className="h-8 rounded-xl border border-rose-200 bg-rose-50 px-3 text-[11px] font-bold text-rose-700 hover:bg-rose-100 transition"
                              >
                                Reject
                              </button>
                            </form>
                            <form method="POST" action={app.approve_url}>
                              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token} />
                              <button
                                type="submit"
                                className="h-8 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 text-[11px] font-bold text-white shadow-xs transition flex items-center gap-1.5"
                              >
                                <CheckCircle2 className="h-3.5 w-3.5" /> Approve & License
                              </button>
                            </form>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Individual Buyers Promotion Desk */}
                  {bootstrap.individual_buyers && bootstrap.individual_buyers.length > 0 && (
                    <div className="rounded-3xl border border-slate-200 bg-white p-5 space-y-4 shadow-sm">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                        <div className="flex items-center gap-2">
                          <Users className="h-4 w-4 text-emerald-600" />
                          <h4 className="text-xs font-black uppercase tracking-wider text-slate-900">
                            Buyer Account Upgrades (Individual → Joint)
                          </h4>
                        </div>
                        <span className="text-[11px] text-slate-500">
                          {bootstrap.individual_buyers.length} Individual Buyers
                        </span>
                      </div>

                      <div className="divide-y divide-slate-100">
                        {bootstrap.individual_buyers.slice(0, 10).map((buyer: any) => (
                          <div key={buyer.id} className="flex items-center justify-between py-2.5 gap-3">
                            <div>
                              <div className="font-bold text-xs text-slate-900">{buyer.name || buyer.email}</div>
                              <div className="text-[10px] text-slate-500">{buyer.email}</div>
                            </div>

                            <form method="POST" action={buyer.promote_to_joint_url}>
                              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token} />
                              <button
                                type="submit"
                                className="h-7 rounded-lg border border-purple-200 bg-purple-50 px-3 text-[10px] font-bold text-purple-700 hover:bg-purple-100 transition"
                              >
                                Upgrade to Joint
                              </button>
                            </form>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-black text-slate-900">Active Commissions & Conveyancing</h4>
                    <span className="text-xs text-slate-500">{activeCommissions.length} active records</span>
                  </div>
                  {activeCommissions.length === 0 ? (
                    <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center text-slate-500 space-y-3 shadow-sm">
                      <ShieldCheck className="mx-auto h-8 w-8 text-slate-400" />
                      <div className="text-sm font-bold text-slate-900">No active commissions currently in progress.</div>
                      <a href="/parcels/" className="inline-block font-bold text-xs text-emerald-700 hover:underline">
                        Explore available land parcels →
                      </a>
                    </div>
                  ) : (
                    <div className="grid gap-3 lg:grid-cols-2">
                      {activeCommissions.map((comm: any) => (
                        <div key={comm.id} className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 shadow-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-emerald-700">Parcel {comm.parcel?.parcel_number || comm.parcel_number}</span>
                            <Badge tone="accent" className="text-[9px]">{comm.status_label || comm.status}</Badge>
                          </div>
                          <div className="text-xs text-slate-600">
                            County: <strong>{comm.parcel?.county || comm.county || 'Kenya'}</strong> · Price: KES {money(comm.parcel?.displayed_price || comm.parcel?.asking_price || '0')}
                          </div>
                          <div className="pt-1 flex items-center justify-between">
                            <span className="text-[10px] text-slate-500">Dual-escrow verified</span>
                            <a href={comm.detail_url || '/buyer/dashboard/'} className="text-xs font-bold text-emerald-700 hover:underline">
                              View details →
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* TAB: ANALYTICS SUITE (ADMIN ONLY) */}
          {activeTab === 'analytics' && (
            <AdminAnalyticsView />
          )}

          {/* TAB 3: TRANSACTIONS & ESCROW SETTLEMENTS */}
          {activeTab === 'transactions' && (
            isAdmin ? (
              <AdminTransactionsManagementView />
            ) : (
              <div className="space-y-4 text-left">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-black text-slate-900">Escrow Ledger & Settlement Register</h4>
                  <a href="/transactions/" className="text-xs font-bold text-emerald-700 hover:underline">
                    Full Transaction Register →
                  </a>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-white p-4 divide-y divide-slate-100 shadow-sm">
                  {transactions.length === 0 ? (
                    <div className="py-8 text-center text-xs text-slate-500">No escrow transactions found.</div>
                  ) : (
                    transactions.map((tx: any) => (
                      <div key={tx.id} className="flex items-center justify-between py-3 gap-3">
                        <div>
                          <div className="font-bold text-xs text-slate-900">Parcel {tx.parcel_number}</div>
                          <div className="text-[10px] text-slate-500">Ref: {tx.id.substring(0, 8)}...</div>
                        </div>
                        <div className="text-right">
                          <div className="font-black text-emerald-700 text-xs">KES {money(tx.amount)}</div>
                          <div className="text-[9px] text-slate-500 uppercase font-semibold">{tx.status}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )
          )}

          {/* TAB 4: PARCELS & MARKETPLACE */}
          {activeTab === 'parcels' && (
            <div className="space-y-4 text-left">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-black text-slate-900">{isSeller ? 'My Listed Parcels' : 'Parcels & Listings'}</h4>
                <a href="/parcels/" className="text-xs font-bold text-emerald-700 hover:underline">
                  Open Marketplace →
                </a>
              </div>
              <ParcelGrid />
            </div>
          )}

          {/* TAB 5: LEGAL & CLEARANCES */}
          {activeTab === 'legal' && (
            <div className="space-y-4 text-left">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-black text-slate-900">Legal Statutes & Statutory Clearances</h4>
                <a href={isSeller ? '/seller/laws/' : '/escrow-acts/'} className="text-xs font-bold text-emerald-700 hover:underline">
                  Print A4 Brief →
                </a>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-white p-5 space-y-4 shadow-sm">
                <div className="text-xs text-slate-600 leading-relaxed font-medium">
                  Every land transaction in Digiland is governed under Kenyan land laws including the Land Registration Act No. 3 of 2012, Section 54 dual signatures, and LCB Consent under Land Control Act Cap 302.
                </div>
                <div className="flex flex-wrap gap-2 pt-2">
                  <a
                    href={isSeller ? '/seller/laws/' : '/escrow-acts/'}
                    className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200 px-4 text-xs font-bold transition hover:bg-emerald-100"
                  >
                    View Official Legal Checklist
                  </a>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: PROMOTIONS (SELLER / BUYER) */}
          {activeTab === 'promotions' && (
            <div className="space-y-4 text-left">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-black text-slate-900">
                  {isSeller ? 'Promotions & Boost Campaigns' : 'Featured Promotions & Exclusive Land Deals'}
                </h4>
                <a
                  href={isSeller ? '/seller/promotions/' : '/parcels/'}
                  className="text-xs font-bold text-emerald-700 hover:underline"
                >
                  {isSeller ? 'Promotions Hub →' : 'Browse All Marketplace Deals →'}
                </a>
              </div>

              {isSeller ? (
                <div className="rounded-3xl border border-amber-200 bg-amber-50/60 p-6 text-center space-y-3 shadow-sm">
                  <Sparkles className="mx-auto h-8 w-8 text-amber-600" />
                  <div className="text-sm font-bold text-slate-900">Boost your parcels to the top of Kenyan land buyer searches.</div>
                  <p className="text-xs text-slate-600 max-w-md mx-auto">
                    Sponsored cards, featured homepage badges, and high-priority WhatsApp/SMS notifications.
                  </p>
                  <a
                    href="/seller/promotions/"
                    className="inline-flex h-9 items-center justify-center rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold px-5 text-xs shadow-xs"
                  >
                    Manage Boost Campaigns
                  </a>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-6 text-left space-y-2 shadow-sm">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-black uppercase text-emerald-800 border border-emerald-200">
                        Buyer Exclusive
                      </span>
                      <span className="text-xs text-slate-500 font-semibold">Zero-Fraud Escrow Guarantee</span>
                    </div>
                    <h3 className="text-base font-black text-slate-900">Verified Title Deed Listings with Subsidized Legal Clearance</h3>
                    <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
                      All promoted parcels feature pre-verified Ministry of Lands search certificates, beacon survey validation, and discounted advocate conveyancing fees.
                    </p>
                  </div>
                  <ParcelGrid />
                </div>
              )}
            </div>
          )}

          {/* TAB: PEOPLE & PRIVILEGED STAFF (ADMIN ONLY) */}
          {(activeTab === 'people' || activeTab === 'professionals') && (
            <AdminPeopleHubView />
          )}

          {/* TAB: KYC & DOCUMENT VERIFICATION DESK (ADMIN ONLY) */}
          {(activeTab === 'kyc' || (activeTab === 'commissions' && isAdmin)) && (
            <AdminKycDeskView />
          )}

          {/* TAB: AI DOCUMENT VERIFICATION BENCHMARK LAB (ADMIN ONLY) */}
          {activeTab === 'ailab' && (
            <AdminAIEvaluationLabView />
          )}
        </div>
      </div>
    </div>
  );
}


function AdminStaffProvisioningView() {
  const [roleToCreate, setRoleToCreate] = useState<'Lawyer' | 'Agent'>('Lawyer');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('Digiland@2026');
  const [nationalId, setNationalId] = useState('');
  const [kraPin, setKraPin] = useState('');
  const [county, setCounty] = useState('Nairobi');

  // Lawyer specific
  const [lawFirmName, setLawFirmName] = useState('');
  const [lskNumber, setLskNumber] = useState('');
  const [practicingCert, setPracticingCert] = useState('');
  const [yearOfAdmission, setYearOfAdmission] = useState('2020');

  // Agent specific
  const [agencyName, setAgencyName] = useState('');
  const [earbNumber, setEarbNumber] = useState('');
  const [goodConductNumber, setGoodConductNumber] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [professionalsList, setProfessionalsList] = useState<any[]>(bootstrap.professionals || []);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<'All' | 'Lawyer' | 'Agent'>('All');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    setFormSuccess(null);

    const payload = {
      role: roleToCreate,
      full_name: fullName,
      email,
      phone_number: phone,
      password,
      national_id: nationalId,
      kra_pin: kraPin,
      county,
      law_firm_name: lawFirmName,
      lsk_number: lskNumber,
      practicing_cert_number: practicingCert,
      year_of_admission: yearOfAdmission,
      agency_name: agencyName,
      earb_number: earbNumber,
      good_conduct_number: goodConductNumber,
    };

    try {
      const resp = await fetch(bootstrap.provision_action || '/admin/staff/provision/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Failed to provision staff account');
      }

      setFormSuccess(data.message || `Successfully created and verified ${roleToCreate} account for ${fullName}!`);
      if (data.user) {
        setProfessionalsList((prev) => [data.user, ...prev]);
      }
      // Reset form fields
      setFullName('');
      setEmail('');
      setPhone('');
      setNationalId('');
      setKraPin('');
      setLawFirmName('');
      setLskNumber('');
      setPracticingCert('');
      setAgencyName('');
      setEarbNumber('');
      setGoodConductNumber('');
    } catch (err: any) {
      setFormError(err.message || 'An error occurred while provisioning professional.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerify = async (profId: string, verifyUrl: string) => {
    try {
      const resp = await fetch(verifyUrl || `/admin/staff/${profId}/verify/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
      });
      if (resp.ok) {
        setProfessionalsList((prev) =>
          prev.map((p) => (p.id === profId ? { ...p, is_verified: true, is_active: true } : p))
        );
      }
    } catch {
      // silent fail
    }
  };

  const handleToggleStatus = async (profId: string, toggleUrl: string) => {
    try {
      const resp = await fetch(toggleUrl || `/admin/staff/${profId}/toggle-status/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        setProfessionalsList((prev) =>
          prev.map((p) => (p.id === profId ? { ...p, is_active: data.is_active } : p))
        );
      }
    } catch {
      // silent fail
    }
  };

  const filtered = professionalsList.filter((p) => {
    if (roleFilter !== 'All' && p.role !== roleFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.email && p.email.toLowerCase().includes(q)) ||
        (p.county && p.county.toLowerCase().includes(q)) ||
        (p.firm_or_agency && p.firm_or_agency.toLowerCase().includes(q)) ||
        (p.lsk_number && p.lsk_number.toLowerCase().includes(q)) ||
        (p.earb_number && p.earb_number.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6 text-left">
      {/* Header Banner */}
      <div className="rounded-3xl border border-white/10 bg-gradient-to-r from-[#0c1427] via-[#0d1b2a] to-[#080d18] p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
              Admin Command Control Panel • Staff Authority
            </div>
            <h3 className="text-xl font-black text-white">Staff & Professional Onboarding & Verification</h3>
            <p className="text-xs text-slate-400 max-w-2xl">
              Directly provision, verify, and authorize Advocates / Conveyancing Lawyers and Licensed Real Estate Agents. Admin-verified staff accounts are pre-cleared for escrow conveyancing and site inspections without 2FA friction.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-center">
              <div className="text-[11px] font-bold text-slate-400">Total Staff & Pros</div>
              <div className="text-lg font-black text-white">{professionalsList.length}</div>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-2.5 text-center">
              <div className="text-[11px] font-bold text-emerald-400">Verified & Active</div>
              <div className="text-lg font-black text-emerald-400">
                {professionalsList.filter((p) => p.is_verified && p.is_active).length}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Provisioning Form Card */}
      <div className="rounded-3xl border border-white/10 bg-[#080c16] p-6 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-4">
          <div>
            <h4 className="text-base font-black text-white">Provision New Professional Account</h4>
            <p className="text-xs text-slate-400">Select the professional role and enter all statutory Kenyan credentials.</p>
          </div>

          {/* Role Switcher */}
          <div className="flex items-center rounded-2xl border border-white/15 bg-white/[0.03] p-1">
            <button
              type="button"
              onClick={() => {
                setRoleToCreate('Lawyer');
                setFormError(null);
                setFormSuccess(null);
              }}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-black transition-all ${
                roleToCreate === 'Lawyer'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Gavel className="h-4 w-4" />
              Conveyancing Lawyer / Advocate
            </button>
            <button
              type="button"
              onClick={() => {
                setRoleToCreate('Agent');
                setFormError(null);
                setFormSuccess(null);
              }}
              className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-black transition-all ${
                roleToCreate === 'Agent'
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 shadow-lg shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Briefcase className="h-4 w-4" />
              Licensed Real Estate Agent
            </button>
          </div>
        </div>

        {/* Feedback Alerts */}
        {formSuccess && (
          <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-xs text-emerald-300">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />
            <div>
              <span className="font-bold">Account Successfully Provisioned: </span>
              {formSuccess}
            </div>
          </div>
        )}

        {formError && (
          <div className="flex items-center gap-3 rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-300">
            <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
            <div>
              <span className="font-bold">Provisioning Error: </span>
              {formError}
            </div>
          </div>
        )}

        {/* Creation Form */}
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Full Legal Name */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">
                {roleToCreate === 'Lawyer' ? 'Advocate Full Legal Name *' : 'Agent Full Legal Name *'}
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={roleToCreate === 'Lawyer' ? 'e.g. Adv. Mwangi Kamau' : 'e.g. Grace Wanjiru Mutua'}
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* Email */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">Official Email Address *</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. partner@lawfirm.co.ke"
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* Mobile Phone */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">Mobile Phone Number (+254...) *</label>
              <input
                type="text"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+254712345678"
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* Initial Password */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">Initial Temporary Password *</label>
              <input
                type="text"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Digiland@2026"
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* National ID / Passport */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">National ID / Passport No. *</label>
              <input
                type="text"
                required
                value={nationalId}
                onChange={(e) => setNationalId(e.target.value)}
                placeholder="e.g. 28471920"
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* KRA PIN */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">KRA PIN Number *</label>
              <input
                type="text"
                required
                value={kraPin}
                onChange={(e) => setKraPin(e.target.value.toUpperCase())}
                placeholder="e.g. A009182374Z"
                className="h-10 w-full rounded-xl border border-white/15 bg-white/[0.04] px-3 text-xs text-white placeholder:text-slate-500 outline-none uppercase focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* County */}
            <div>
              <label className="block text-[11px] font-bold text-slate-400 mb-1">
                {roleToCreate === 'Lawyer' ? 'Primary Practice County *' : 'Assigned Operating County *'}
              </label>
              <select
                value={county}
                onChange={(e) => setCounty(e.target.value)}
                className="h-10 w-full rounded-xl border border-white/15 bg-[#0e1424] px-3 text-xs text-white outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              >
                {['Nairobi', 'Kiambu', 'Mombasa', 'Nakuru', 'Machakos', 'Kajiado', 'Uasin Gishu', 'Kisumu', 'Kilifi', 'Laikipia', 'Nyeri', 'Murang\'a', 'National'].map((c) => (
                  <option key={c} value={c} className="bg-[#0e1424] text-white">
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* LAWYER SPECIFIC FIELDS */}
            {roleToCreate === 'Lawyer' && (
              <>
                <div>
                  <label className="block text-[11px] font-bold text-blue-300 mb-1">Law Firm / Chambers Name *</label>
                  <input
                    type="text"
                    required
                    value={lawFirmName}
                    onChange={(e) => setLawFirmName(e.target.value)}
                    placeholder="e.g. Bowmans / Kaplan & Stratton Advocates"
                    className="h-10 w-full rounded-xl border border-blue-500/30 bg-blue-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-blue-300 mb-1">LSK Roll / Admission No. (P105/...) *</label>
                  <input
                    type="text"
                    required
                    value={lskNumber}
                    onChange={(e) => setLskNumber(e.target.value)}
                    placeholder="e.g. P105/18492/21"
                    className="h-10 w-full rounded-xl border border-blue-500/30 bg-blue-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-blue-300 mb-1">High Court Practicing Cert No. *</label>
                  <input
                    type="text"
                    required
                    value={practicingCert}
                    onChange={(e) => setPracticingCert(e.target.value)}
                    placeholder="e.g. HC/PC/2026/0491"
                    className="h-10 w-full rounded-xl border border-blue-500/30 bg-blue-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-blue-300 mb-1">Year of Admission to the Bar</label>
                  <input
                    type="text"
                    value={yearOfAdmission}
                    onChange={(e) => setYearOfAdmission(e.target.value)}
                    placeholder="e.g. 2018"
                    className="h-10 w-full rounded-xl border border-blue-500/30 bg-blue-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
                  />
                </div>
              </>
            )}

            {/* AGENT SPECIFIC FIELDS */}
            {roleToCreate === 'Agent' && (
              <>
                <div>
                  <label className="block text-[11px] font-bold text-emerald-300 mb-1">Agency / Brokerage Firm Name *</label>
                  <input
                    type="text"
                    required
                    value={agencyName}
                    onChange={(e) => setAgencyName(e.target.value)}
                    placeholder="e.g. HassConsult / Pam Golding Properties"
                    className="h-10 w-full rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-emerald-300 mb-1">EARB Registration Number *</label>
                  <input
                    type="text"
                    required
                    value={earbNumber}
                    onChange={(e) => setEarbNumber(e.target.value)}
                    placeholder="e.g. EARB/A-4921"
                    className="h-10 w-full rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-emerald-300 mb-1">DCI Certificate of Good Conduct No. *</label>
                  <input
                    type="text"
                    required
                    value={goodConductNumber}
                    onChange={(e) => setGoodConductNumber(e.target.value)}
                    placeholder="e.g. DCI/GCC/2026/9102"
                    className="h-10 w-full rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400"
                  />
                </div>
              </>
            )}
          </div>

          {/* Direct Verification Notice */}
          <div className="flex items-center gap-2.5 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs text-slate-300">
            <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
            <span>
              <strong className="text-emerald-300">Direct Admin Authority: </strong>
              This account will be created with pre-verified KYC status and active identity credentials. 2FA is skipped since verification is confirmed directly by the Admin.
            </span>
          </div>

          {/* Submit Action */}
          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              disabled={isSubmitting}
              className={`h-11 rounded-2xl px-6 text-xs font-black transition-all shadow-lg ${
                roleToCreate === 'Lawyer'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-blue-600/30 hover:scale-[1.02]'
                  : 'bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-emerald-500/30 hover:scale-[1.02]'
              }`}
            >
              {isSubmitting ? (
                'Provisioning & Authorizing...'
              ) : (
                <>
                  <UserCheck className="mr-2 h-4 w-4" />
                  Provision & Authorize {roleToCreate === 'Lawyer' ? 'Advocate' : 'Agent'} Account
                </>
              )}
            </Button>
          </div>
        </form>
      </div>

      {/* Staff & Professional Registry Table */}
      <div className="rounded-3xl border border-white/10 bg-[#080c16] p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-4">
          <div>
            <h4 className="text-base font-black text-white">Active Staff & Professional Registry</h4>
            <p className="text-xs text-slate-400">All verified Advocates, Conveyancing Lawyers, and Licensed Estate Agents.</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Filter Tabs */}
            <div className="flex items-center rounded-xl border border-white/15 bg-white/[0.03] p-0.5 text-xs">
              {(['All', 'Lawyer', 'Agent'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRoleFilter(r)}
                  className={`rounded-lg px-3 py-1.5 font-bold transition-all ${
                    roleFilter === r ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {r === 'All' ? 'All Staff' : `${r}s`}
                </button>
              ))}
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search name, firm, LSK, EARB..."
                className="h-9 w-60 rounded-xl border border-white/15 bg-white/[0.04] pl-8 pr-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Table / List */}
        {filtered.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No professionals found matching the search criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-3">Professional</th>
                  <th className="py-3 px-3">Role</th>
                  <th className="py-3 px-3">Firm / Agency</th>
                  <th className="py-3 px-3">License / Roll No</th>
                  <th className="py-3 px-3">County</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filtered.map((prof) => (
                  <tr key={prof.id} className="hover:bg-white/[0.02] transition">
                    <td className="py-3.5 px-3">
                      <div className="font-bold text-white">{prof.name}</div>
                      <div className="text-[11px] text-slate-400">{prof.email}</div>
                      <div className="text-[10px] text-slate-500">{prof.phone}</div>
                    </td>
                    <td className="py-3.5 px-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10px] font-black uppercase ${
                          prof.role === 'Lawyer'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {prof.role === 'Lawyer' ? <Gavel className="h-3 w-3" /> : <Briefcase className="h-3 w-3" />}
                        {prof.role}
                      </span>
                    </td>
                    <td className="py-3.5 px-3">
                      <div className="font-medium text-slate-200">{prof.firm_or_agency || 'Independent'}</div>
                      <div className="text-[10px] text-slate-500">KRA: {prof.kra_pin || 'N/A'}</div>
                    </td>
                    <td className="py-3.5 px-3">
                      {prof.role === 'Lawyer' ? (
                        <div>
                          <div className="font-mono text-[11px] text-blue-300">{prof.lsk_number || 'LSK Verified'}</div>
                          <div className="text-[10px] text-slate-500">{prof.practicing_cert || ''}</div>
                        </div>
                      ) : (
                        <div>
                          <div className="font-mono text-[11px] text-emerald-300">{prof.earb_number || 'EARB Verified'}</div>
                          <div className="text-[10px] text-slate-500">{prof.good_conduct_number || ''}</div>
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-3 text-slate-300">{prof.county || 'National'}</td>
                    <td className="py-3.5 px-3">
                      <div className="flex flex-col gap-1">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            prof.is_verified
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                              : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                          }`}
                        >
                          <ShieldCheck className="h-3 w-3" />
                          {prof.is_verified ? 'Verified' : 'Pending'}
                        </span>
                        <span className={`text-[10px] ${prof.is_active ? 'text-slate-400' : 'text-rose-400'}`}>
                          {prof.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </div>
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {!prof.is_verified && (
                          <button
                            type="button"
                            onClick={() => handleVerify(prof.id, prof.verify_url)}
                            className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-bold text-emerald-300 hover:bg-emerald-500/20"
                          >
                            Verify
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(prof.id, prof.toggle_status_url)}
                          className={`rounded-lg border px-2.5 py-1 text-[11px] font-bold transition ${
                            prof.is_active
                              ? 'border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20'
                              : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                          }`}
                        >
                          {prof.is_active ? 'Suspend' : 'Activate'}
                        </button>
                        <a
                          href={`/messages/?partner=${encodeURIComponent(prof.email)}`}
                          className="rounded-lg border border-white/10 bg-white/[0.04] p-1.5 text-slate-300 hover:text-white hover:bg-white/10"
                          title="Direct Message"
                        >
                          <MessageSquare className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}


function AdminAnalyticsView() {
  const analytics = bootstrap.analytics || {
    financial: {
      total_gmv_kes: 185000000,
      escrow_fee_revenue_kes: 3700000,
      active_escrow_reserves_kes: 42000000,
      total_lawyer_payouts_kes: 750000,
      total_agent_payouts_kes: 1350000,
      completed_transactions_count: 28,
      active_transactions_count: 7,
      disputed_transactions_count: 1,
      refunded_transactions_count: 2,
      total_transactions_count: 38,
    },
    staff_ledger: [],
    regional_distribution: [
      { county: 'Nairobi', listings_count: 14, estimated_value_kes: 68000000 },
      { county: 'Kiambu', listings_count: 11, estimated_value_kes: 42000000 },
      { county: 'Nakuru', listings_count: 8, estimated_value_kes: 24000000 },
      { county: 'Machakos', listings_count: 6, estimated_value_kes: 18000000 },
      { county: 'Mombasa', listings_count: 5, estimated_value_kes: 32000000 },
      { county: 'Kajiado', listings_count: 4, estimated_value_kes: 15000000 },
    ],
    land_use_distribution: { Residential: 24, Commercial: 12, Agricultural: 8 },
    system_health: {
      open_tickets_count: 2,
      total_tickets_count: 14,
      flagged_fraud_parcels_count: 1,
      active_disputes_count: 1,
      uptime_percentage: '99.98%',
      escrow_status: 'Operational — Dual Signature Enforced',
    },
    tickets: [],
    user_metrics: {
      total_users: 142,
      buyers_count: 98,
      joint_buyers_count: 24,
      sellers_count: 32,
      agents_count: 8,
      lawyers_count: 4,
    },
  };

  const [staffList, setStaffList] = useState<any[]>(analytics.staff_ledger || []);
  const [staffFilter, setStaffFilter] = useState<'All' | 'Lawyer' | 'Agent'>('All');
  const [staffSearch, setStaffSearch] = useState('');
  const [disbursingId, setDisbursingId] = useState<string | null>(null);
  const [disburseSuccess, setDisburseSuccess] = useState<string | null>(null);

  const handleDisbursePayout = async (staffId: string, url: string) => {
    if (!confirm('Confirm disbursement of accrued professional fees to this staff member?')) return;
    setDisbursingId(staffId);
    setDisburseSuccess(null);

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token,
        },
      });
      const data = await resp.json();
      if (resp.ok) {
        setDisburseSuccess(data.message || 'Payout disbursed successfully.');
        setStaffList((prev) =>
          prev.map((s) => (s.id === staffId ? { ...s, status: 'PAID', balance_kes: 0, paid_kes: s.accrued_kes } : s))
        );
      } else {
        alert(data.error || 'Failed to disburse payout.');
      }
    } catch {
      alert('Network error while processing payout.');
    } finally {
      setDisbursingId(null);
    }
  };

  const filteredStaff = useMemo(() => {
    return staffList.filter((s) => {
      if (staffFilter !== 'All' && s.role !== staffFilter) return false;
      if (staffSearch) {
        const q = staffSearch.toLowerCase();
        return (
          s.name.toLowerCase().includes(q) ||
          s.email.toLowerCase().includes(q) ||
          (s.firm_or_agency && s.firm_or_agency.toLowerCase().includes(q)) ||
          (s.county && s.county.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [staffList, staffFilter, staffSearch]);

  const financial = analytics.financial || {};
  const health = analytics.system_health || {};
  const userMetrics = analytics.user_metrics || {};

  return (
    <div className="space-y-6 text-left">
      {/* Executive Header Banner */}
      <div className="rounded-3xl border border-emerald-500/30 bg-gradient-to-r from-emerald-950/40 via-[#0c1424] to-[#080d18] p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-black uppercase text-emerald-300 border border-emerald-500/30">
                Executive Command
              </span>
              <span className="text-xs text-slate-400 font-semibold">Live System Telemetry & Auditing</span>
            </div>
            <h3 className="text-xl font-black text-white">System Analytics, Revenue & Operations Suite</h3>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Real-time financial performance, escrow reserves, Kenyan regional land volumes, staff payouts ledger, and incident reporting.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="/admin/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center justify-center rounded-xl border border-white/15 bg-white/[0.04] px-4 text-xs font-bold text-slate-200 hover:bg-white/10 transition gap-1.5"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Django Control Plane
            </a>
          </div>
        </div>
      </div>

      {disburseSuccess && (
        <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-xs font-bold text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {disburseSuccess}
        </div>
      )}

      {/* KPI METRIC CARDS GRID */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total GMV */}
        <div className="rounded-3xl border border-white/10 bg-[#080c16] p-5 space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-slate-400">Total Land GMV</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
              <Banknote className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-white">{money(financial.total_gmv_kes || 0)}</div>
          <p className="text-[10px] text-slate-400">Gross completed land transactions</p>
          <div className="absolute -bottom-6 -right-6 h-20 w-20 rounded-full bg-emerald-500/5 blur-xl pointer-events-none" />
        </div>

        {/* Escrow Fee Revenue */}
        <div className="rounded-3xl border border-emerald-500/30 bg-[#080c16] p-5 space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-emerald-400">Platform Revenue</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-300">
              <ReceiptText className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-emerald-400">{money(financial.escrow_fee_revenue_kes || 0)}</div>
          <p className="text-[10px] text-slate-400">2% Escrow fee + platform processing</p>
          <div className="absolute -bottom-6 -right-6 h-20 w-20 rounded-full bg-emerald-500/10 blur-xl pointer-events-none" />
        </div>

        {/* Active Escrow Reserves */}
        <div className="rounded-3xl border border-blue-500/30 bg-[#080c16] p-5 space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-blue-400">Locked Escrow Held</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-500/20 text-blue-300">
              <Lock className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-blue-300">{money(financial.active_escrow_reserves_kes || 0)}</div>
          <p className="text-[10px] text-slate-400">{financial.active_transactions_count || 0} active buyer deposits</p>
          <div className="absolute -bottom-6 -right-6 h-20 w-20 rounded-full bg-blue-500/10 blur-xl pointer-events-none" />
        </div>

        {/* Total Settled Deals */}
        <div className="rounded-3xl border border-purple-500/30 bg-[#080c16] p-5 space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-purple-400">Settled Transactions</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-500/20 text-purple-300">
              <CheckCircle2 className="h-4 w-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-purple-300">{financial.completed_transactions_count || 0} Transfers</div>
          <p className="text-[10px] text-slate-400">Dual-signature ownership transfers</p>
          <div className="absolute -bottom-6 -right-6 h-20 w-20 rounded-full bg-purple-500/10 blur-xl pointer-events-none" />
        </div>
      </div>

      {/* SECTION 1: REGIONAL SALES DISTRIBUTION & TRANSACTION STATUS LEDGER */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Kenyan County Distribution */}
        <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-emerald-400" />
              <h4 className="text-xs font-black uppercase tracking-wider text-slate-200">
                County Volume & Distribution (Kenya)
              </h4>
            </div>
            <span className="text-[11px] text-slate-400">Top Markets</span>
          </div>

          <div className="space-y-3 pt-1">
            {(analytics.regional_distribution || []).map((region: any) => (
              <div key={region.county} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-200">{region.county} County</span>
                  <span className="text-slate-400 font-semibold">
                    {region.listings_count} Listings · <strong className="text-emerald-400">{money(region.estimated_value_kes)}</strong>
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.04]">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400"
                    style={{ width: `${Math.min(100, (region.listings_count / 15) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Transaction Status & Health Ledger */}
        <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <ReceiptText className="h-4 w-4 text-purple-400" />
              <h4 className="text-xs font-black uppercase tracking-wider text-slate-200">
                Escrow Settlement Status Breakdown
              </h4>
            </div>
            <span className="text-[11px] text-slate-400 font-bold">{financial.total_transactions_count || 0} Total</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 pt-1">
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-3.5 space-y-1">
              <div className="text-[10px] font-bold text-emerald-400 uppercase">Completed Transfers</div>
              <div className="text-xl font-black text-white">{financial.completed_transactions_count || 0}</div>
              <div className="text-[10px] text-slate-400">Ownership deed finalized</div>
            </div>

            <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-3.5 space-y-1">
              <div className="text-[10px] font-bold text-blue-400 uppercase">In Active Escrow</div>
              <div className="text-xl font-black text-white">{financial.active_transactions_count || 0}</div>
              <div className="text-[10px] text-slate-400">Funds locked in verification</div>
            </div>

            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-3.5 space-y-1">
              <div className="text-[10px] font-bold text-amber-400 uppercase">Dispute & Hiatus Cases</div>
              <div className="text-xl font-black text-white">{financial.disputed_transactions_count || 0}</div>
              <div className="text-[10px] text-slate-400">Dispute mediation active</div>
            </div>

            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-3.5 space-y-1">
              <div className="text-[10px] font-bold text-rose-400 uppercase">Processed Refunds</div>
              <div className="text-xl font-black text-white">{financial.refunded_transactions_count || 0}</div>
              <div className="text-[10px] text-slate-400">Returned to buyer accounts</div>
            </div>
          </div>

          {/* User Demographics Row */}
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-2">
            <div className="text-[10px] font-black uppercase text-slate-400 tracking-wider">User Platform Registry</div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <div className="text-base font-black text-white">{userMetrics.buyers_count || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold">Buyers ({userMetrics.joint_buyers_count || 0} Joint)</div>
              </div>
              <div>
                <div className="text-base font-black text-white">{userMetrics.sellers_count || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold">Sellers</div>
              </div>
              <div>
                <div className="text-base font-black text-emerald-400">{userMetrics.agents_count || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold">Agents</div>
              </div>
              <div>
                <div className="text-base font-black text-blue-400">{userMetrics.lawyers_count || 0}</div>
                <div className="text-[9px] text-slate-400 font-semibold">Lawyers</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: STAFF & EMPLOYEE COMPENSATION LEDGER */}
      <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.06] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-emerald-400" />
              <h4 className="text-sm font-black text-white">Staff & Professional Compensation Ledger</h4>
            </div>
            <p className="text-xs text-slate-400">
              Track tasks, conveyancing fees (Lawyers: KES 25,000/tx), commissions (Agents), and disburse payouts.
            </p>
          </div>

          {/* Filters & Search */}
          <div className="flex items-center gap-3">
            <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-0.5">
              {(['All', 'Lawyer', 'Agent'] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setStaffFilter(r)}
                  className={`rounded-lg px-3 py-1 text-xs font-bold transition ${
                    staffFilter === r ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>

            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search staff, firm, email..."
                value={staffSearch}
                onChange={(e) => setStaffSearch(e.target.value)}
                className="h-8 w-48 rounded-xl border border-white/10 bg-[#0f1422] pl-8 pr-3 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-emerald-500/50"
              />
            </div>
          </div>
        </div>

        {/* Staff Table */}
        {filteredStaff.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">No staff members found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-3">Professional</th>
                  <th className="py-3 px-3">Role</th>
                  <th className="py-3 px-3">Firm / Agency</th>
                  <th className="py-3 px-3">County</th>
                  <th className="py-3 px-3 text-center">Tasks Completed</th>
                  <th className="py-3 px-3 text-right">Total Accrued</th>
                  <th className="py-3 px-3 text-right">Paid Out</th>
                  <th className="py-3 px-3 text-right">Balance</th>
                  <th className="py-3 px-3 text-center">Status</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {filteredStaff.map((staff: any) => (
                  <tr key={staff.id} className="hover:bg-white/[0.02] transition">
                    <td className="py-3 px-3">
                      <div className="font-bold text-white">{staff.name}</div>
                      <div className="text-[10px] text-slate-400">{staff.email}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center rounded-lg px-2 py-0.5 text-[9px] font-black uppercase ${
                          staff.role === 'Lawyer'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {staff.role}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-300">{staff.firm_or_agency}</td>
                    <td className="py-3 px-3 text-slate-400">{staff.county}</td>
                    <td className="py-3 px-3 text-center font-bold text-white">{staff.tasks_completed}</td>
                    <td className="py-3 px-3 text-right font-bold text-slate-200">{money(staff.accrued_kes)}</td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-400">{money(staff.paid_kes)}</td>
                    <td className="py-3 px-3 text-right font-bold text-amber-300">{money(staff.balance_kes)}</td>
                    <td className="py-3 px-3 text-center">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[9px] font-black uppercase ${
                          staff.status === 'PAID'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-amber-500/20 text-amber-300'
                        }`}
                      >
                        {staff.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <button
                        type="button"
                        disabled={disbursingId === staff.id}
                        onClick={() => handleDisbursePayout(staff.id, staff.disburse_url)}
                        className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 text-[10px] font-bold text-emerald-300 hover:bg-emerald-500/20 transition disabled:opacity-50"
                      >
                        {disbursingId === staff.id ? 'Processing...' : 'Disburse Payout'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SECTION 3: SYSTEM COMPLAINTS & INCIDENTS DESK */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Support Tickets & Complaints */}
        <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-amber-400" />
              <h4 className="text-xs font-black uppercase tracking-wider text-slate-200">
                User Inquiries & Complaints Desk
              </h4>
            </div>
            <span className="text-[11px] text-amber-400 font-bold">
              {health.open_tickets_count || 0} Open Tickets
            </span>
          </div>

          <div className="divide-y divide-white/[0.04]">
            {(!analytics.tickets || analytics.tickets.length === 0) ? (
              <div className="py-6 text-center text-xs text-slate-500">
                No active complaints or open support tickets.
              </div>
            ) : (
              analytics.tickets.map((t: any) => (
                <div key={t.id} className="py-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <div className="font-bold text-xs text-white">{t.subject}</div>
                    <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-bold text-amber-300">
                      {t.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 line-clamp-2">{t.message}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                    <span>From: {t.user_email}</span>
                    <span>{t.created_at}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* System Health & Security Posture */}
        <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h4 className="text-xs font-black uppercase tracking-wider text-slate-200">
                Security & Fraud Monitoring
              </h4>
            </div>
            <span className="text-[11px] text-emerald-400 font-bold">Uptime: {health.uptime_percentage}</span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between rounded-2xl bg-white/[0.02] p-3 border border-white/[0.04]">
              <span className="text-slate-300 font-semibold">Dual-Signature Protocol</span>
              <Badge tone="success" className="text-[9px]">ENFORCED</Badge>
            </div>
            <div className="flex items-center justify-between rounded-2xl bg-white/[0.02] p-3 border border-white/[0.04]">
              <span className="text-slate-300 font-semibold">Flagged Fraudulent Parcels</span>
              <span className="font-black text-rose-400">{health.flagged_fraud_parcels_count || 0} Flagged</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl bg-white/[0.02] p-3 border border-white/[0.04]">
              <span className="text-slate-300 font-semibold">Disputed Escrow Holds</span>
              <span className="font-black text-amber-400">{health.active_disputes_count || 0} Under Review</span>
            </div>
            <div className="flex items-center justify-between rounded-2xl bg-white/[0.02] p-3 border border-white/[0.04]">
              <span className="text-slate-300 font-semibold">Ministry of Lands Registry Sync</span>
              <span className="font-bold text-emerald-400">Connected & Synced</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


function AdminTransactionsManagementView() {
  const initialTxs = bootstrap.transactions || [];
  const [txList, setTxList] = useState<any[]>(initialTxs);
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<{ text: string; type: 'success' | 'error' | 'warning' } | null>(null);

  const handleAction = async (txId: string, url: string, confirmPrompt: string) => {
    if (!confirm(confirmPrompt)) return;
    setActionInProgress(txId);
    setFeedbackMsg(null);

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token,
        },
      });
      const data = await resp.json();
      if (resp.ok) {
        setFeedbackMsg({ text: data.message || 'Transaction updated successfully.', type: 'success' });
        if (data.transaction_status) {
          setTxList((prev) =>
            prev.map((t) => (t.id === txId ? { ...t, status: data.transaction_status, raw_status: data.transaction_status } : t))
          );
        }
      } else {
        setFeedbackMsg({ text: data.error || 'Failed to update transaction.', type: 'error' });
      }
    } catch {
      setFeedbackMsg({ text: 'Network error while executing action.', type: 'error' });
    } finally {
      setActionInProgress(null);
    }
  };

  const filtered = useMemo(() => {
    return txList.filter((tx) => {
      if (statusFilter !== 'All') {
        if (statusFilter === 'In-Escrow') {
          if (!['Deposit_Paid', 'Under_Verification', 'Initiated'].includes(tx.raw_status || tx.status)) return false;
        } else if (tx.raw_status !== statusFilter && tx.status !== statusFilter) {
          return false;
        }
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          (tx.parcel_number && tx.parcel_number.toLowerCase().includes(q)) ||
          (tx.buyer_email && tx.buyer_email.toLowerCase().includes(q)) ||
          (tx.seller_email && tx.seller_email.toLowerCase().includes(q)) ||
          (tx.id && tx.id.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [txList, statusFilter, searchQuery]);

  return (
    <div className="space-y-6 text-left">
      {/* Header Banner */}
      <div className="rounded-3xl border border-white/10 bg-[#080c16] p-6 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.08] pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="rounded-full bg-blue-500/20 px-2.5 py-0.5 text-[10px] font-black uppercase text-blue-300 border border-blue-500/30">
                Settlement Desk
              </span>
              <span className="text-xs text-slate-400 font-semibold">Dual-Signature Payment & Escrow Controls</span>
            </div>
            <h3 className="text-xl font-black text-white">Escrow Transactions & Payment Management</h3>
            <p className="text-xs text-slate-300 max-w-2xl">
              Authorize payouts to land sellers, disburse advocate & agent fees, trigger refunds to buyers, or freeze disputed accounts.
            </p>
          </div>

          <a
            href="/transactions/"
            className="inline-flex h-9 items-center justify-center rounded-xl bg-white/[0.06] hover:bg-white/10 px-4 text-xs font-bold text-slate-200 border border-white/10 transition"
          >
            Full Ledger View →
          </a>
        </div>

        {/* Status Filters & Search Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div className="flex flex-wrap gap-1.5 rounded-2xl border border-white/10 bg-white/[0.03] p-1">
            {[
              { id: 'All', label: 'All Transactions' },
              { id: 'In-Escrow', label: 'In Active Escrow' },
              { id: 'Completed', label: 'Completed Transfers' },
              { id: 'Disputed', label: 'Disputes & Holds' },
              { id: 'Refunded', label: 'Refunded' },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setStatusFilter(f.id)}
                className={`rounded-xl px-3 py-1 text-xs font-bold transition ${
                  statusFilter === f.id
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search parcel, buyer, seller..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 w-64 rounded-xl border border-white/15 bg-white/[0.04] pl-9 pr-3 text-xs text-white placeholder:text-slate-500 outline-none focus:border-emerald-500"
            />
          </div>
        </div>
      </div>

      {feedbackMsg && (
        <div
          className={`rounded-2xl p-4 text-xs font-bold flex items-center gap-2 ${
            feedbackMsg.type === 'success'
              ? 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
              : feedbackMsg.type === 'warning'
              ? 'border border-amber-500/40 bg-amber-500/10 text-amber-300'
              : 'border border-rose-500/40 bg-rose-500/10 text-rose-300'
          }`}
        >
          <Info className="h-4 w-4 shrink-0" />
          {feedbackMsg.text}
        </div>
      )}

      {/* Transactions List */}
      {filtered.length === 0 ? (
        <div className="rounded-3xl border border-white/[0.08] bg-[#080b14] p-12 text-center text-slate-400 space-y-3">
          <ReceiptText className="mx-auto h-8 w-8 text-slate-600" />
          <div className="text-sm font-bold text-slate-200">No transactions found.</div>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            No escrow transactions matching the selected filter or search term.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((tx: any) => {
            const rawStatus = tx.raw_status || tx.status;
            const isCompleted = rawStatus === 'Completed';
            const isDisputed = rawStatus === 'Disputed' || rawStatus === 'Verification_Hiatus';
            const isRefunded = rawStatus === 'Refunded';
            const isInEscrow = ['Deposit_Paid', 'Under_Verification', 'Initiated'].includes(rawStatus);

            return (
              <div
                key={tx.id}
                className="rounded-3xl border border-white/10 bg-[#080c16] p-6 space-y-4 shadow-md transition hover:border-white/20"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 font-black border border-emerald-500/20">
                      <ReceiptText className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="font-black text-sm text-white">Parcel {tx.parcel_number}</div>
                      <div className="text-[10px] text-slate-400">
                        Ref: <span className="font-mono">{tx.id}</span> · Created: {tx.created_at}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-[10px] font-black uppercase ${
                        isCompleted
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : isDisputed
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : isRefunded
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                      }`}
                    >
                      {tx.status}
                    </span>
                    {tx.is_joint_purchase && (
                      <span className="rounded-full bg-purple-500/20 px-2.5 py-1 text-[9px] font-bold text-purple-300 border border-purple-500/30">
                        Joint Purchase
                      </span>
                    )}
                  </div>
                </div>

                {/* Financial Breakdown Row */}
                <div className="grid gap-3 sm:grid-cols-4 rounded-2xl bg-white/[0.02] p-3.5 border border-white/[0.04] text-xs">
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-bold">Agreed Land Price</div>
                    <div className="text-sm font-black text-white">{money(tx.amount)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-emerald-400 uppercase font-bold">Platform Escrow Fee (2%)</div>
                    <div className="text-sm font-black text-emerald-400">
                      {money(tx.escrow_fee || Number(tx.amount || 0) * 0.02)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-blue-400 uppercase font-bold">Seller Net Payout</div>
                    <div className="text-sm font-black text-blue-300">
                      {money(tx.seller_payout || Number(tx.amount || 0) * 0.98)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 uppercase font-bold">Parties</div>
                    <div className="text-[11px] text-slate-300 truncate">
                      Buyer: <strong>{tx.buyer_email}</strong>
                    </div>
                    <div className="text-[11px] text-slate-300 truncate">
                      Seller: <strong>{tx.seller_email}</strong>
                    </div>
                  </div>
                </div>

                {/* Administrative Action Controls */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <div className="flex items-center gap-2">
                    <a
                      href={tx.action_url || `/transactions/`}
                      className="inline-flex h-8 items-center justify-center rounded-xl border border-white/15 bg-white/[0.04] px-3.5 text-[11px] font-bold text-slate-200 hover:bg-white/10 transition gap-1"
                    >
                      <FileSignature className="h-3.5 w-3.5" />
                      View Contract
                    </a>
                    <a
                      href={`/messages/?partner=${encodeURIComponent(tx.buyer_email || '')}`}
                      className="inline-flex h-8 items-center justify-center rounded-xl border border-white/15 bg-white/[0.04] px-3 text-[11px] font-bold text-slate-300 hover:bg-white/10 transition gap-1"
                    >
                      <MessageSquare className="h-3.5 w-3.5" />
                      Message Buyer
                    </a>
                  </div>

                  {/* Actions depending on transaction status */}
                  <div className="flex flex-wrap items-center gap-2">
                    {/* If In Escrow: Can Release Payout, Refund, or Freeze */}
                    {isInEscrow && (
                      <>
                        <button
                          type="button"
                          disabled={actionInProgress === tx.id}
                          onClick={() =>
                            handleAction(
                              tx.id,
                              tx.release_url,
                              `Release escrow payout of KES ${tx.amount} to seller and finalize land transfer for Parcel ${tx.parcel_number}?`
                            )
                          }
                          className="h-8 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 px-4 text-[11px] font-black text-slate-950 shadow-md shadow-emerald-500/20 hover:scale-[1.02] transition flex items-center gap-1.5 disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Release Escrow Payout
                        </button>

                        <button
                          type="button"
                          disabled={actionInProgress === tx.id}
                          onClick={() =>
                            handleAction(
                              tx.id,
                              tx.freeze_url,
                              `Place transaction for Parcel ${tx.parcel_number} into Dispute / Investigation Hiatus?`
                            )
                          }
                          className="h-8 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 text-[11px] font-bold text-amber-300 hover:bg-amber-500/20 transition disabled:opacity-50"
                        >
                          Freeze / Dispute Hold
                        </button>

                        <button
                          type="button"
                          disabled={actionInProgress === tx.id}
                          onClick={() =>
                            handleAction(
                              tx.id,
                              tx.refund_url,
                              `Refund escrow deposit for Parcel ${tx.parcel_number} back to buyer ${tx.buyer_email}?`
                            )
                          }
                          className="h-8 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 text-[11px] font-bold text-rose-300 hover:bg-rose-500/20 transition disabled:opacity-50"
                        >
                          Refund Buyer
                        </button>
                      </>
                    )}

                    {/* If Disputed: Can Unfreeze or Refund */}
                    {isDisputed && (
                      <>
                        <button
                          type="button"
                          disabled={actionInProgress === tx.id}
                          onClick={() =>
                            handleAction(
                              tx.id,
                              tx.unfreeze_url,
                              `Lift dispute hold and resume escrow for Parcel ${tx.parcel_number}?`
                            )
                          }
                          className="h-8 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 text-[11px] font-bold text-white shadow-md hover:scale-[1.02] transition disabled:opacity-50"
                        >
                          Lift Dispute Hold
                        </button>
                        <button
                          type="button"
                          disabled={actionInProgress === tx.id}
                          onClick={() =>
                            handleAction(
                              tx.id,
                              tx.refund_url,
                              `Refund disputed deposit for Parcel ${tx.parcel_number} back to buyer?`
                            )
                          }
                          className="h-8 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 text-[11px] font-bold text-rose-300 hover:bg-rose-500/20 transition disabled:opacity-50"
                        >
                          Refund Buyer
                        </button>
                      </>
                    )}

                    {isCompleted && (
                      <span className="text-[11px] font-bold text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Payout Fully Disbursed
                      </span>
                    )}

                    {isRefunded && (
                      <span className="text-[11px] font-bold text-slate-400">Refund Processed & Archived</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ParcelListPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Marketplace"
        title={bootstrap.title}
        subtitle={bootstrap.subtitle}
        badge={bootstrap.notice}
        actions={bootstrap.actions}
      />
      <ParcelGrid />
    </div>
  );
}

function TransactionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Escrow activity"
        title={bootstrap.title}
        subtitle={bootstrap.subtitle}
        badge={bootstrap.notice}
        actions={bootstrap.actions}
      />
      <TransactionTable />
    </div>
  );
}

function LegalPage() {
  const laws = bootstrap.laws || [];
  const checklist = bootstrap.checklist || [];
  const paymentGuidance = bootstrap.payment_guidance || [];
  const documentContent = bootstrap.document_content || '';

  const actionClassByTone: Record<string, string> = {
    default: 'bg-primary text-primary-foreground hover:bg-primary/90 border-transparent',
    secondary: 'bg-slate-900 text-white hover:bg-slate-800 border-transparent',
    outline: 'bg-white text-foreground hover:bg-muted border-border',
    ghost: 'bg-transparent text-foreground hover:bg-white/70 border-transparent',
    accent: 'bg-emerald-600 text-white hover:bg-emerald-500 border-transparent',
  };

  return (
    <div className="print-document-shell min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.16),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#ffffff_42%,#eef2f7_100%)] px-4 py-8 sm:px-6 lg:px-8 print:px-0 print:py-0">
      <div className="mx-auto max-w-[9.25in] space-y-6 print:space-y-0">
        <div className="print-document-header flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <div className="text-xs font-black uppercase tracking-[0.32em] text-emerald-700">Breakout legal sheet</div>
            <h1 className="print-document-title text-3xl font-black tracking-tight text-foreground sm:text-4xl">{bootstrap.title}</h1>
            <p className="max-w-3xl text-sm leading-7 text-muted-foreground">{bootstrap.subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => window.print()}
              className="print:hidden inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
            >
              <Printer className="mr-2 h-4 w-4" />
              Print A4 legal brief
            </button>
            {bootstrap.actions?.length ? (
              bootstrap.actions.map((action) => (
                <a
                  key={action.label}
                  href={action.href}
                  target={action.external ? '_blank' : undefined}
                  rel={action.external ? 'noreferrer' : undefined}
                  className={`inline-flex h-11 items-center justify-center rounded-full border px-4 text-sm font-semibold transition-colors ${actionClassByTone[action.tone || 'default'] || actionClassByTone.default}`}
                >
                  {action.label}
                </a>
              ))
            ) : null}
          </div>
        </div>

        <div className="print-document-sheet mx-auto w-full max-w-[8.27in] rounded-[2rem] border border-stone-300 bg-white shadow-[0_35px_90px_rgba(15,23,42,0.12)]">
          <div className="border-b border-stone-200 px-8 py-8 sm:px-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-[11px] font-black uppercase tracking-[0.3em] text-emerald-700">A4 legal brief</div>
                <h2 className="print-document-title mt-2 text-2xl font-black tracking-tight text-slate-900">{bootstrap.title}</h2>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">{bootstrap.subtitle}</p>
              </div>
              <Badge tone="outline" className="w-fit rounded-full px-4 py-2">{laws.length ? `${laws.length} sections` : 'Reference sheet'}</Badge>
            </div>
          </div>

          <div className="print-document-body space-y-8 px-8 py-8 sm:px-10">
            {laws.length ? laws.map((law, index) => (
              <section key={`${law.title}-${index}`} className="break-inside-avoid rounded-[1.75rem] border border-stone-200 bg-stone-50/90 p-6 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-700">{law.citation}</div>
                    <h3 className="mt-2 text-lg font-bold text-slate-900">{law.title}</h3>
                  </div>
                  <Badge tone={law.required ? 'success' : 'warning'}>{law.required ? 'Required' : 'Guidance'}</Badge>
                </div>
                <p className="mt-4 text-sm leading-7 text-slate-700">{law.summary}</p>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-600">
                    {law.applies_to}
                  </span>
                  <a
                    href={law.official_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-9 items-center justify-center rounded-full bg-emerald-50 px-4 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100"
                  >
                    Official source
                  </a>
                </div>
              </section>
            )) : (
              <div className="rounded-2xl border border-dashed border-stone-300 bg-stone-50 p-8 text-center text-sm text-muted-foreground">
                No legal references were loaded for this page.
              </div>
            )}

            {documentContent ? (
              <article className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-sm">
                <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-700">Platform terms</div>
                <div className="print-document-body mt-4 space-y-4 text-sm leading-7 text-slate-700">
                  {splitParagraphs(documentContent).map((paragraph, paragraphIndex) => (
                    <p key={`${paragraphIndex}-${paragraph.slice(0, 24)}`} className="whitespace-pre-wrap">
                      {paragraph}
                    </p>
                  ))}
                </div>
              </article>
            ) : null}

            <div className="grid gap-6 lg:grid-cols-2">
              <section className="rounded-[1.75rem] border border-stone-200 bg-stone-50 p-6 shadow-sm">
                <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-700">Checklist</div>
                <ul className="mt-4 space-y-3 text-sm leading-7 text-slate-700">
                  {checklist.map((item: string) => (
                    <li key={item} className="flex gap-3">
                      <CircleCheckBig className="mt-1 h-4 w-4 shrink-0 text-emerald-700" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {paymentGuidance.length ? (
                <section className="rounded-[1.75rem] border border-stone-200 bg-stone-50 p-6 shadow-sm">
                  <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-700">Joint payment guidance</div>
                  <ul className="mt-4 space-y-3 text-sm leading-7 text-slate-700">
                    {paymentGuidance.map((item: string) => (
                      <li key={item} className="flex gap-3">
                        <Banknote className="mt-1 h-4 w-4 shrink-0 text-emerald-700" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


function BuyerChoicePage() {
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Buyer setup"
        title={bootstrap.title}
        subtitle={bootstrap.subtitle}
        badge={bootstrap.notice}
        actions={bootstrap.actions}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl"><Users className="h-5 w-5 text-emerald-700" />Joint buyer account</CardTitle>
            <CardDescription>Buy land as a group with a leader-managed account and shared contributions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-2 text-sm leading-7 text-foreground">
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />Members can be added, replaced, or removed by the group leader.</li>
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />Choose tenancy in common for most non-spousal group purchases.</li>
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />Use the joint laws page for Kenyan co-ownership guidance.</li>
            </ul>
            {bootstrap.form ? (
              <form method={bootstrap.form.method || 'post'} action={bootstrap.form.action} className="space-y-4">
                <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.form.csrf_token || bootstrap.csrf_token || ''} />
                <input type="hidden" name="account_type" value="Joint" />
                <Button type="submit" className="w-full rounded-full">Choose joint account</Button>
              </form>
            ) : null}
          </CardContent>
        </Card>

        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl"><Landmark className="h-5 w-5 text-emerald-700" />Individual buyer account</CardTitle>
            <CardDescription>Buy in your own name with the same escrow and legal protections.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-2 text-sm leading-7 text-foreground">
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />Ideal when one buyer is purchasing and paying alone.</li>
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />Continue straight to the marketplace after setup.</li>
              <li className="flex gap-3"><CircleCheckBig className="mt-1 h-4 w-4 text-emerald-700" />You can switch later if you decide to buy with others.</li>
            </ul>
            {bootstrap.form ? (
              <form method={bootstrap.form.method || 'post'} action={bootstrap.form.action} className="space-y-4">
                <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.form.csrf_token || bootstrap.csrf_token || ''} />
                <input type="hidden" name="account_type" value="Individual" />
                <Button type="submit" variant="outline" className="w-full rounded-full">Choose individual account</Button>
              </form>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function JointGroupsPage() {
  const groups = bootstrap.groups || [];
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Joint ownership"
        title={bootstrap.title}
        subtitle={bootstrap.subtitle}
        badge={bootstrap.notice}
        actions={bootstrap.actions}
      />
      <div className="grid gap-4 xl:grid-cols-2">
        {groups.length ? groups.map((group) => (
          <Card key={group.id} className="bg-white/92">
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">{group.name}</CardTitle>
                  <CardDescription>{group.group_type} · {group.ownership_type}</CardDescription>
                </div>
                <StatusBadge label={group.is_valid ? 'Valid' : 'Check shares'} tone={group.is_valid ? 'success' : 'warning'} />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-muted/60 p-3 text-sm">
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Payment method</div>
                  <div className="mt-1 font-semibold text-foreground">{group.preferred_payment_method}</div>
                </div>
                <div className="rounded-2xl bg-muted/60 p-3 text-sm">
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Total share</div>
                  <div className="mt-1 font-semibold text-foreground">{group.total_share}%</div>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <a href={group.detail_url} className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
                  Open group
                </a>
                <a href={group.laws_url} className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground transition-colors hover:bg-muted">
                  Laws page
                </a>
              </div>
            </CardContent>
          </Card>
        )) : (
          <Card className="bg-white/92">
            <CardContent className="p-8 text-center">
              <Users className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
              <div className="text-lg font-bold text-foreground">No joint groups yet</div>
              <p className="mt-2 text-sm text-muted-foreground">Create a joint group once your buyer account is set up.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function JointGroupDetailPage() {
  const group = bootstrap.group;
  if (!group) return <JointGroupsPage />;
  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Joint ownership"
        title={group.name}
        subtitle={`${group.group_type} · ${group.ownership_type} · ${group.members.length} members`}
        badge={group.is_valid ? 'Valid' : 'Check shares'}
        actions={bootstrap.actions}
      />

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Users className="h-4 w-4 text-emerald-700" />Members</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {group.members.map((member) => (
              <div key={member.id} className="rounded-3xl border border-border/70 bg-muted/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-foreground">
                      {member.full_name}
                      {member.is_leader ? <span className="ml-2 rounded-full bg-slate-900 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-white">Leader</span> : null}
                    </div>
                    <div className="text-sm text-muted-foreground">ID: {member.id_number || 'N/A'} · KRA: {member.kra_pin || 'N/A'}</div>
                    <div className="text-sm text-muted-foreground">Phone: {member.phone_number}{member.email ? ` · Email: ${member.email}` : ''}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black tracking-tight text-foreground">{member.share_percentage}%</div>
                    <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{member.signature_status || 'Pending'}</div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge tone="outline">{member.signature_status || 'Pending signature'}</Badge>
                  {member.edit_url ? <a href={member.edit_url} className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">Edit</a> : null}
                  {member.delete_url && !member.is_leader ? <a href={member.delete_url} className="inline-flex h-9 items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-4 text-xs font-semibold text-rose-700 hover:bg-rose-100">Request removal</a> : null}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Banknote className="h-4 w-4 text-emerald-700" />Payment method</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="rounded-2xl bg-muted/60 p-3">Method: <strong>{group.preferred_payment_method}</strong></div>
              <div className="rounded-2xl bg-muted/60 p-3">Bank: <strong>{group.bank_name || 'Not set'}</strong></div>
              <div className="rounded-2xl bg-muted/60 p-3">Account name: <strong>{group.bank_account_name || 'Not set'}</strong></div>
              <div className="rounded-2xl bg-muted/60 p-3">Account number: <strong>{group.bank_account_number || 'Not set'}</strong></div>
              <div className="rounded-2xl bg-muted/60 p-3">Branch: <strong>{group.bank_branch || 'Not set'}</strong></div>
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4 text-emerald-700" />Group summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                <span>Total share</span>
                <strong>{group.total_share}%</strong>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                <span>Ownership</span>
                <strong>{group.ownership_type}</strong>
              </div>
              <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                <span>Status</span>
                <strong>{group.is_valid ? 'Valid' : 'Needs review'}</strong>
              </div>
              <div className="grid gap-3 pt-2">
                <a href={group.laws_url} className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground hover:bg-muted">Open joint laws</a>
                <a href={group.edit_url} className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90">Edit group details</a>
                {group.add_member_url ? <a href={group.add_member_url} className="inline-flex h-11 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 px-5 text-sm font-semibold text-emerald-800 hover:bg-emerald-100">Add member</a> : null}
                {group.transfer_leadership_url ? <a href={group.transfer_leadership_url} className="inline-flex h-11 items-center justify-center rounded-full border border-stone-200 bg-white px-5 text-sm font-semibold text-foreground hover:bg-muted">Transfer leadership</a> : null}
              </div>
            </CardContent>
          </Card>

          {group.can_manage ? (
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><AlertTriangle className="h-4 w-4 text-amber-600" />Member removal</CardTitle>
                <CardDescription>Member removal now requires admin review for consent and compensation checks.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                <p>Use the request removal action on a member card to submit the case to an admin. The admin must confirm the exit is consensual and that the departing member has been compensated for their share.</p>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

const CONTENT_LIBRARY: Record<string, NonNullable<typeof bootstrap.content>> = {
  about: {
    hero: {
      kicker: 'About Digiland',
      title: 'Built for secure land transfers in Kenya',
      subtitle: 'Digiland combines verified parcel workflows, escrow settlement, and joint ownership support in one platform.',
      badge: 'Public overview',
    },
    sections: [
      {
        kicker: 'Mission',
        title: 'Reduce fraud and friction',
        body: 'The platform is designed to make land purchase workflows clearer, safer, and easier to audit by buyers, sellers, agents, and administrators.',
        bullets: ['Verified parcels only', 'Escrow-backed settlement', 'Joint buyer support'],
      },
      {
        kicker: 'Workflow',
        title: 'From listing to transfer',
        body: 'Parcel documentation is uploaded, reviewed, signed, and moved to checkout only when the contract is complete.',
        bullets: ['Upload and review documents', 'Sign the land transfer contract', 'Send the M-Pesa STK prompt or record joint bank transfer'],
      },
      {
        kicker: 'Joint ownership',
        title: 'Designed for groups and families',
        body: 'Joint buyers can manage group membership, ownership shares, legal guidance, and payment details from a dedicated workspace.',
        actions: [
          { label: 'Buyer setup', href: '/buyer/account-choice/', tone: 'outline' },
          { label: 'Joint laws', href: '/joint/laws/', tone: 'secondary' },
        ],
      },
    ],
  },
  architecture: {
    hero: {
      kicker: 'Architecture',
      title: 'A compact, auditable platform design',
      subtitle: 'The app keeps the Django backend in charge of business rules while React handles the presentation layer.',
      badge: 'System design',
    },
    sections: [
      {
        kicker: 'Backend',
        title: 'Django owns the rules',
        body: 'Identity checks, transaction state transitions, approval rules, payment logic, and joint ownership validation stay on the server.',
      },
      {
        kicker: 'Frontend',
        title: 'React renders the experience',
        body: 'The browser gets a structured bootstrap payload and renders the current page through a shared shell and component library.',
      },
      {
        kicker: 'Boundary',
        title: 'Templates are no longer the UI layer',
        body: 'The old HTML templates are being retired so the interface is consistent, easier to maintain, and visually coherent.',
      },
    ],
  },
  investors: {
    hero: {
      kicker: 'Investors',
      title: 'A focused land transaction product',
      subtitle: 'Digiland targets a narrow workflow with high trust requirements: parcel verification, contract signing, and escrow payment.',
      badge: 'Growth story',
    },
    sections: [
      {
        kicker: 'Market',
        title: 'Large, trust-heavy transactions',
        body: 'Land deals need verification, legal review, and payment protection. The platform centralises those steps into one traceable workflow.',
      },
      {
        kicker: 'Moat',
        title: 'Workflow and compliance depth',
        body: 'Joint purchase support, agent approval flows, legal checklists, and payment orchestration are embedded into the product, not bolted on.',
      },
      {
        kicker: 'Execution',
        title: 'Built for operational clarity',
        body: 'The React migration simplifies the UI stack, improves maintainability, and reduces style drift across authenticated surfaces.',
      },
    ],
  },
  terms: {
    hero: {
      kicker: 'Terms',
      title: 'Platform usage terms',
      subtitle: 'These pages summarise how the Digiland workflow is intended to be used.',
      badge: 'Legal',
    },
    sections: [
      {
        title: 'Service scope',
        body: 'Digiland provides a digital interface for land listings, document review, contract signing, and payment initiation.',
      },
      {
        title: 'User responsibilities',
        body: 'Users remain responsible for the accuracy of their personal information, parcel details, ownership records, and supporting documentation.',
      },
      {
        title: 'Transaction safety',
        body: 'Escrow and verification are workflow tools. Final legal effect depends on the governing law, executed instruments, and the applicable approvals.',
      },
    ],
  },
  privacy: {
    hero: {
      kicker: 'Privacy',
      title: 'Privacy and data handling',
      subtitle: 'The platform stores only what it needs to manage escrow, verification, and support workflows.',
      badge: 'Data policy',
    },
    sections: [
      {
        title: 'Collected information',
        body: 'Account data, parcel records, support messages, uploaded documents, and transaction events may be stored to support the workflow.',
      },
      {
        title: 'Usage',
        body: 'Data is used to verify identity, process payments, coordinate reviews, and keep an audit trail of the transaction lifecycle.',
      },
      {
        title: 'Retention',
        body: 'Records may be retained where required for legal, regulatory, audit, or dispute-resolution purposes.',
      },
    ],
  },
};

function PublicSectionCards({ sections }: { sections: NonNullable<typeof bootstrap.content>['sections'] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {sections.map((section) => (
        <Card key={section.title} className="bg-white/92">
          <CardHeader className="pb-3">
            {section.kicker ? <div className="text-xs font-bold uppercase tracking-[0.22em] text-emerald-700">{section.kicker}</div> : null}
            <CardTitle className="text-lg">{section.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm leading-7 text-foreground">{section.body}</p>
            {section.bullets?.length ? (
              <ul className="space-y-2 text-sm text-muted-foreground">
                {section.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-2">
                    <CircleCheckBig className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {section.actions?.length ? (
              <div className="flex flex-wrap gap-2">
                {section.actions.map((action) => (
                  <a
                    key={`${section.title}-${action.href}`}
                    href={action.href}
                    className="inline-flex h-10 items-center justify-center rounded-full border border-border bg-white/80 px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
                  >
                    {action.label}
                  </a>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function LandingPage({ onNavigatePartition }: { onNavigatePartition?: (partition: 'app' | 'staff' | 'admin' | 'marketing') => void }) {
  const stats = bootstrap.stats || [];

  return (
    <div className="landing-page-wrapper">
      <PublicShell
        title={bootstrap.title}
        subtitle={bootstrap.subtitle}
        nav={bootstrap.nav}
        user={bootstrap.user}
        actions={bootstrap.actions}
        hideFooter
      >
        <HeroShowcase
          notice={bootstrap.notice}
          stats={stats}
          csrfToken={bootstrap.csrf_token}
          isAuthenticated={Boolean(bootstrap.user)}
          onNavigatePartition={onNavigatePartition}
        />
      </PublicShell>
      <PremiumFooter />
    </div>
  );
}

function FeaturesPage() {
  return (
    <div className="features-page-wrapper">
      <PublicShell
        title="Protocol Features"
        subtitle="Explore the 10 core capabilities powering autonomous land escrow in Kenya."
        nav={bootstrap.nav}
        user={bootstrap.user}
        actions={bootstrap.actions}
        hideFooter
      >
        <div className="space-y-8 max-w-6xl mx-auto py-6">
          <div className="text-left space-y-2">
            <div className="text-xs font-black uppercase tracking-[0.24em] text-emerald-700">Platform Capabilities</div>
            <h1 className="text-3xl font-black text-slate-900 sm:text-4xl">Digiland Buyer Protection & Escrow Features</h1>
            <p className="text-sm text-slate-600 max-w-2xl font-medium">
              From acquisition to legal conveyancing, Digiland connects identity, escrow vaulting, and government registry validation into a seamless protocol.
            </p>
          </div>

          {/* Animated Walkthrough & Ecosystem Features */}
          <AnimatedWalkthrough />

          <div className="grid gap-6 md:grid-cols-3 text-left">
            <Card className="bg-white/95 border-slate-200/80 p-6 rounded-[1.75rem] shadow-sm">
              <CardHeader className="p-0 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 font-bold mb-2">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <CardTitle className="text-base font-bold text-slate-900 font-mono">Land Registry Title Validation</CardTitle>
              </CardHeader>
              <CardContent className="p-0 text-xs leading-relaxed text-slate-600">
                Direct integration with Ministry of Lands land registry to confirm title deed ownership, encumbrances, and parcel boundaries before contract signing.
              </CardContent>
            </Card>

            <Card className="bg-white/95 border-slate-200/80 p-6 rounded-[1.75rem] shadow-sm">
              <CardHeader className="p-0 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-700 font-bold mb-2">
                  <WalletCards className="h-5 w-5" />
                </div>
                <CardTitle className="text-base font-bold text-slate-900">M-Pesa STK & KCB Escrow Vault</CardTitle>
              </CardHeader>
              <CardContent className="p-0 text-xs leading-relaxed text-slate-600">
                Buyer deposits are held securely in escrow via M-Pesa B2C & KCB Bank until all legal conditions and advocate signatures are satisfied.
              </CardContent>
            </Card>

            <Card className="bg-white/95 border-slate-200/80 p-6 rounded-[1.75rem] shadow-sm">
              <CardHeader className="p-0 pb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700 font-bold mb-2">
                  <Gavel className="h-5 w-5" />
                </div>
                <CardTitle className="text-base font-bold text-slate-900">LSK Advocate Sign-Off</CardTitle>
              </CardHeader>
              <CardContent className="p-0 text-xs leading-relaxed text-slate-600">
                Licensed Law Society of Kenya advocates review title documents, execute cryptographic sign-offs, and oversee legal ownership transfer.
              </CardContent>
            </Card>
          </div>
        </div>
      </PublicShell>
      <PremiumFooter />
    </div>
  );
}

function ContentPage() {
  const content = bootstrap.content || CONTENT_LIBRARY[bootstrap.content_key || 'about'];
  if (!content) {
    return <LandingPage />;
  }

  const hero = content.hero || { title: bootstrap.title, subtitle: bootstrap.subtitle };

  return (
    <PublicShell title={bootstrap.title} subtitle={bootstrap.subtitle} nav={bootstrap.nav} user={bootstrap.user} actions={bootstrap.actions}>
      <div className="space-y-8">
        <section className="space-y-4">
          {hero.kicker ? <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">{hero.kicker}</div> : null}
          <div className="flex flex-col gap-4 rounded-[2rem] border border-border/70 bg-white/90 p-6 shadow-soft lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">{hero.title}</h1>
              {hero.subtitle ? <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">{hero.subtitle}</p> : null}
            </div>
            {hero.badge ? <Badge tone="outline" className="w-fit px-4 py-2">{hero.badge}</Badge> : null}
          </div>
        </section>
        <PublicSectionCards sections={content.sections} />
      </div>
    </PublicShell>
  );
}

const statusIconMap: Record<string, LucideIcon> = {
  default: Clock3,
  clock: Clock3,
  success: CircleCheckBig,
  check: CircleCheckBig,
  warning: AlertTriangle,
  alert: AlertTriangle,
  danger: ShieldAlert,
  shield: ShieldCheck,
  wallet: WalletCards,
  file: FileText,
  people: Users,
};

function StatusPage() {
  const status = bootstrap.status;
  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  if (!status) {
    return bootstrap.user ? (
      <AppShell {...shellProps}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Status details are unavailable.</CardContent>
        </Card>
      </AppShell>
    ) : (
      <PublicShell title={bootstrap.title} subtitle={bootstrap.subtitle} nav={bootstrap.nav} user={bootstrap.user} actions={bootstrap.actions}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Status details are unavailable.</CardContent>
        </Card>
      </PublicShell>
    );
  }

  const statusToneMap: Record<string, string> = {
    success: 'border-emerald-200 bg-emerald-50/70',
    warning: 'border-amber-200 bg-amber-50/70',
    danger: 'border-rose-200 bg-rose-50/70',
    muted: 'bg-white/92',
    default: 'bg-white/92',
  };
  const statusIconToneMap: Record<string, string> = {
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
    muted: 'text-slate-700',
    default: 'text-emerald-700',
  };
  const Icon = statusIconMap[status.icon || 'default'] || statusIconMap[status.tone || 'default'] || Clock3;
  const actions = [status.primary_action, status.secondary_action, ...(status.extra_actions || [])].filter(Boolean) as ActionLink[];

  const body = (
    <div className="space-y-6">
      <PageHeader kicker="System status" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={actions} />
      <Card className={statusToneMap[status.tone || 'default']}>
        <CardContent className="space-y-5 p-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl border border-border bg-white/90 shadow-soft">
            <Icon className={cn('h-7 w-7', statusIconToneMap[status.tone || 'default'] || 'text-emerald-700')} />
          </div>
          <p className="mx-auto max-w-2xl text-sm leading-7 text-foreground">{status.description}</p>
        </CardContent>
      </Card>
    </div>
  );

  return bootstrap.user ? <AppShell {...shellProps}>{body}</AppShell> : <PublicShell title={bootstrap.title} subtitle={bootstrap.subtitle} nav={bootstrap.nav} user={bootstrap.user} actions={bootstrap.actions}>{body}</PublicShell>;
}

function GenericFormPage() {
  const form = bootstrap.form;
  const memberFormset = bootstrap.member_formset;
  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };
  const combinedForm = useMemo(() => {
    if (!form) return null;
    if (!memberFormset) return form;
    return {
      ...form,
      managementFields: memberFormset.managementFields || form.managementFields,
      formsetRows: memberFormset.formsetRows || form.formsetRows,
    };
  }, [form, memberFormset]);

  const pageBody = (
    <div className="space-y-6">
      <PageHeader kicker="Digiland" title={bootstrap.title} subtitle={bootstrap.subtitle} badge={bootstrap.notice} actions={bootstrap.actions} />
      {combinedForm ? <FormRenderer form={combinedForm} csrfToken={bootstrap.csrf_token || undefined} /> : null}
    </div>
  );

  if (bootstrap.user) {
    return <AppShell {...shellProps}>{pageBody}</AppShell>;
  }
  return <PublicShell title={bootstrap.title} subtitle={bootstrap.subtitle} nav={bootstrap.nav} user={bootstrap.user} actions={bootstrap.actions}>{pageBody}</PublicShell>;
}

function ParcelDetailPage() {
  const detail = bootstrap.parcel_detail;
  const [purchaseMode, setPurchaseMode] = useState(detail?.purchase_modes?.find((mode) => mode.selected)?.value || 'individual');
  const [selectedGroup, setSelectedGroup] = useState(detail?.joint_groups?.[0]?.id || '');

  if (!detail) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Parcel details are not available.</CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-8">
        <PageHeader
          kicker="Parcel profile"
          title={detail.parcel_number}
          subtitle={`${detail.ward}, ${detail.constituency}, ${detail.county}`}
          badge={detail.verification_status}
          actions={[
            { label: 'Back to marketplace', href: '/parcels/', tone: 'outline' },
            detail.edit_url ? { label: 'Edit details', href: detail.edit_url, tone: 'secondary' } : null,
          ].filter(Boolean) as ActionLink[]}
        />

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-6">
            <Card className="overflow-hidden bg-white/92">
              <div className="aspect-[16/9] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50">
                {detail.image_url ? <img src={detail.image_url} alt={detail.parcel_number} className="h-full w-full object-cover" /> : null}
              </div>
              <CardContent className="space-y-5 p-6">
                <div className="grid gap-3 md:grid-cols-2">
                  {[
                    ['Land use', detail.land_use_type],
                    ['Size', `${detail.land_size} Acres`],
                    ['Registered owner', detail.registered_owner_id_masked],
                    ['Price', `KES ${detail.displayed_price}`],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl bg-muted/60 p-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
                      <div className="mt-1 font-semibold text-foreground">{value}</div>
                    </div>
                  ))}
                </div>

                {detail.ai_price ? (
                  <div className="rounded-3xl border border-emerald-200 bg-emerald-50/70 p-5">
                    <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">AI estimate</div>
                    <div className="mt-2 text-2xl font-black tracking-tight text-foreground">KES {detail.ai_price.total_value}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Per acre: KES {detail.ai_price.price_per_acre} | Confidence: KES {detail.ai_price.confidence_low} - {detail.ai_price.confidence_high}
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-3 sm:grid-cols-2">
                  <a href="/escrow-acts/" className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground hover:bg-muted">Read legal checklist</a>
                  {detail.can_use_joint_purchase ? <a href="/joint/laws/" className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90">Joint laws</a> : null}
                </div>
              </CardContent>
            </Card>

            {detail.google_maps_url ? (
              <Card className="bg-white/92">
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><MapPin className="h-4 w-4 text-emerald-700" />Parcel access location</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm text-muted-foreground">Use Google Maps to navigate to the recorded parcel coordinates for an authorized site visit.</p>
                  <a href={detail.google_maps_url} target="_blank" rel="noreferrer" className="inline-flex h-10 items-center justify-center rounded-full bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-700"><MapPin className="mr-2 h-4 w-4" />Open in Google Maps</a>
                </CardContent>
              </Card>
            ) : null}

            {detail.access_locked && detail.confirm_access_url ? (
              <Card className="border-amber-200 bg-amber-50/70"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Lock className="h-4 w-4 text-amber-700" />Dual-signature access required</CardTitle><CardDescription>The seller must authorize this parcel before your PIN can unlock restricted documents.</CardDescription></CardHeader><CardContent><form method="post" action={detail.confirm_access_url} className="flex gap-2"><input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} /><Input name="pin" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} placeholder="6-digit PIN" required /><Button type="submit" className="rounded-full">Confirm access</Button></form></CardContent></Card>
            ) : null}

            {detail.request_access_url ? (
              <Card className="border-emerald-200 bg-emerald-50/70"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4 text-emerald-700" />Authorize document access</CardTitle><CardDescription>Set or enter your 6-digit seller PIN to authorize the assigned reviewer.</CardDescription></CardHeader><CardContent><form method="post" action={detail.request_access_url} className="flex gap-2"><input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} /><Input name="pin" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} placeholder="6-digit PIN" required /><Button type="submit" className="rounded-full">Authorize reviewer</Button></form></CardContent></Card>
            ) : null}

            <Card className="bg-white/92">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4 text-emerald-700" />Compliance documents</CardTitle>
                {detail.upload_document_url ? (
                  <a href={detail.upload_document_url} className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">
                    <Upload className="mr-2 h-4 w-4" /> Upload Document
                  </a>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-3">
                {detail.documents.length ? detail.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between gap-3 rounded-3xl border border-border/70 bg-muted/40 p-4">
                    <div>
                      <div className="font-semibold text-foreground">{doc.document_label}</div>
                      <div className="text-sm text-muted-foreground">Uploaded {doc.uploaded_at}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={doc.verification_status === 'Match' ? 'success' : doc.verification_status === 'Mismatch' ? 'danger' : 'warning'}>{doc.verification_status}</Badge>
                      {doc.file_url ? <a href={doc.file_url} target="_blank" rel="noreferrer" className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">View</a> : null}
                      {doc.moderate_url ? <a href={doc.moderate_url} className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">Moderate</a> : null}
                      {doc.delete_url ? <a href={doc.delete_url} className="inline-flex h-9 items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-4 text-xs font-semibold text-rose-600 hover:bg-rose-100">Delete</a> : null}
                    </div>
                  </div>
                )) : (
                  <p className="text-sm text-muted-foreground">No ownership or identity documents have been attached yet.</p>
                )}
              </CardContent>
            </Card>
          </div>
          <div className="space-y-6">
            {detail.agent_verify_url ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4 text-emerald-700" />Agent moderation</CardTitle>
                  <CardDescription>Verify or flag this parcel from the review queue.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form method="post" action={detail.agent_verify_url} className="grid gap-3">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <Button type="submit" name="verify_action" value="verify" className="w-full rounded-full">Approve deed and title</Button>
                    <Button type="submit" name="verify_action" value="reject" variant="outline" className="w-full rounded-full">Flag as fraudulent</Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}

            {detail.toggle_favorite_url ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><Heart className="h-4 w-4 text-rose-600" />Saved parcels</CardTitle>
                </CardHeader>
                <CardContent>
                  <form method="post" action={detail.toggle_favorite_url}>
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <Button type="submit" variant={detail.is_favorited ? 'danger' : 'outline'} className="w-full rounded-full">
                      {detail.is_favorited ? 'Remove from saved' : 'Save parcel'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}

            {detail.can_initiate_escrow ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Commission request</CardTitle>
                  <CardDescription>Choose the purchase mode before creating a commission.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <form method="post" action={detail.initiate_escrow_url} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Purchase mode</label>
                      <select
                        value={purchaseMode}
                        onChange={(event) => setPurchaseMode(event.target.value)}
                        name="purchase_mode"
                        className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                      >
                        <option value="individual">Individual purchase</option>
                        {detail.can_use_joint_purchase ? <option value="joint">Joint group purchase</option> : null}
                      </select>
                      {detail.can_use_joint_purchase ? null : (
                        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                          Joint purchases become available after you choose the joint buyer account setup.
                        </div>
                      )}
                    </div>

                    {purchaseMode === 'joint' && detail.joint_groups?.length ? (
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">Select joint group</label>
                        <select
                          name="joint_group_id"
                          value={selectedGroup}
                          onChange={(event) => setSelectedGroup(event.target.value)}
                          className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                        >
                          {detail.joint_groups.map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.name} ({group.members.length} members)
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : null}

                    <Button type="submit" className="w-full rounded-full">Commission for purchase</Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function CommissionDetailPage() {
  const commission = bootstrap.commission_detail || bootstrap.commission_steps;
  if (!commission) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Commission details are unavailable.</CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const primaryAction = commission.is_buyer
    ? (commission.transaction_url
        ? { label: 'Continue to payment', href: commission.transaction_url, tone: 'default' as const }
        : { label: 'Back to parcel', href: commission.detail_url, tone: 'outline' as const })
    : commission.is_agent
      ? (commission.can_work && commission.steps_url
          ? { label: 'Open workflow steps', href: commission.steps_url, tone: 'default' as const }
          : commission.can_accept
            ? { label: 'Accept job', href: commission.accept_url, tone: 'accent' as const, method: 'post' as const }
            : { label: 'View workflow', href: commission.steps_url || commission.detail_url, tone: 'outline' as const })
      : commission.is_lawyer
        ? (commission.review_url
            ? { label: 'Review documents', href: commission.review_url, tone: 'accent' as const, method: 'post' as const }
            : { label: 'View dashboard', href: '/', tone: 'outline' as const })
        : { label: 'Back to dashboard', href: '/', tone: 'outline' as const };

  const secondaryAction = commission.is_buyer
    ? { label: 'View parcel', href: commission.detail_url, tone: 'secondary' as const }
    : { label: 'Track progress', href: commission.detail_url, tone: 'secondary' as const };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader
          kicker="Commission"
          title={commission.parcel.parcel_number}
          subtitle={`${commission.target_county}, ${commission.target_constituency}`}
          badge={commission.status_label}
          actions={bootstrap.actions}
        />

        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-6">
            <CommissionCard
              commission={commission}
              primaryAction={primaryAction}
              secondaryAction={secondaryAction}
              footer={commission.is_joint_purchase && commission.joint_group ? <>Joint group <span className="font-semibold text-foreground">{commission.joint_group.name}</span></> : commission.accepted_by ? <>Accepted by <span className="font-semibold text-foreground">{commission.accepted_by.email}</span></> : 'This commission is tracked end-to-end through agent, lawyer, and closing stages.'}
            />

            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Progress tracker</CardTitle>
                <CardDescription>The buyer sees the workflow as a read-only timeline. The agent sees the same timeline with action links on the workflow page.</CardDescription>
              </CardHeader>
              <CardContent>
                <CommissionStepRail commission={commission} />
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Document summary</CardTitle>
                <CardDescription>Verification only checks that the listed documents exist in the parcel record.</CardDescription>
              </CardHeader>
              <CardContent>
                <CommissionDocumentChecklist commission={commission} />
              </CardContent>
            </Card>

            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Parties</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="rounded-2xl bg-muted/60 p-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Buyer</div>
                  <div className="mt-1 font-semibold text-foreground">{commission.buyer?.email}</div>
                </div>
                {commission.accepted_by ? (
                  <div className="rounded-2xl bg-muted/60 p-3">
                    <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Agent</div>
                    <div className="mt-1 font-semibold text-foreground">{commission.accepted_by.email}</div>
                  </div>
                ) : null}
                {commission.assigned_lawyer ? (
                  <div className="rounded-2xl bg-muted/60 p-3">
                    <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Lawyer</div>
                    <div className="mt-1 font-semibold text-foreground">{commission.assigned_lawyer.email}</div>
                  </div>
                ) : null}
                <div className="rounded-2xl bg-muted/60 p-3">
                  <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">Created</div>
                  <div className="mt-1 font-semibold text-foreground">{commission.created_at}</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function AgentJobBoardPage() {
  const board = bootstrap.agent_job_board;
  if (!board) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Commission job board is unavailable.</CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader
          kicker="Agent job board"
          title="Purchase commissions"
          subtitle={`Open commissions matched to ${board.region_county || 'your region'}${board.region_constituency ? ` / ${board.region_constituency}` : ''}.`}
          badge={`${board.open_count} open`}
          actions={bootstrap.actions}
        />

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="bg-white/92">
            <CardContent className="p-5">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Open jobs</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{board.open_count}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-5">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Region</div>
              <div className="mt-2 text-lg font-black tracking-tight text-foreground">{board.region_county || 'Unassigned'}</div>
              <div className="text-sm text-muted-foreground">{board.region_constituency || 'No constituency set'}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-5">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Source</div>
              <div className="mt-2 text-lg font-black tracking-tight text-foreground">{board.region_source || 'profile'}</div>
              <div className="text-sm text-muted-foreground">Matched from profile or parcel history.</div>
            </CardContent>
          </Card>
        </div>

        {board.commissions.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {board.commissions.map((commission) => (
              <CommissionCard
                key={commission.id}
                commission={commission}
                primaryAction={commission.can_accept ? { label: 'Accept job', href: commission.accept_url, tone: 'accent', method: 'post' } : { label: 'View details', href: commission.detail_url, tone: 'outline' }}
                secondaryAction={{ label: 'Open commission', href: commission.detail_url, tone: 'secondary' }}
                footer={`Asked to serve ${commission.target_county}, ${commission.target_constituency}.`}
              />
            ))}
          </div>
        ) : (
          <Card className="bg-white/92">
            <CardContent className="p-8 text-center text-sm text-muted-foreground">No open commissions were matched to your operating region yet.</CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}

function AgentCommissionStepsPage() {
  const commission = bootstrap.commission_steps || bootstrap.commission_detail;
  if (!commission) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Commission workflow is unavailable.</CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader
          kicker="Commission workflow"
          title={commission.parcel.parcel_number}
          subtitle={`${commission.target_county}, ${commission.target_constituency}`}
          badge={commission.status_label}
          actions={bootstrap.actions}
        />

        <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-6">
            <CommissionCard
              commission={commission}
              primaryAction={commission.transaction_url ? { label: 'Continue to payment', href: commission.transaction_url, tone: 'default' } : { label: 'Back to commission', href: commission.detail_url, tone: 'outline' }}
              secondaryAction={{ label: 'Open commission', href: commission.detail_url, tone: 'secondary' }}
              footer={commission.accepted_by ? <>Working with <span className="font-semibold text-foreground">{commission.accepted_by.email}</span></> : 'Commission accepted. Follow the steps below to move it to closing.'}
            />

            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Workflow steps</CardTitle>
                <CardDescription>Each checkpoint must be completed in order before the commission can close.</CardDescription>
              </CardHeader>
              <CardContent>
                <CommissionStepRail commission={commission} />
              </CardContent>
            </Card>

            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Document checklist</CardTitle>
                <CardDescription>Confirm the parcel file contains the required documents before forwarding anything to the lawyer.</CardDescription>
              </CardHeader>
              <CardContent>
                <CommissionDocumentChecklist commission={commission} />
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className={commission.can_review_documents ? 'bg-white/92' : 'border-dashed border-border bg-white/80'}>
              <CardHeader>
                <CardTitle className="text-base">Step 1 - Document review</CardTitle>
                <CardDescription>Confirm that the parcel records are complete.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {commission.can_review_documents ? (
                  <form method="post" action={commission.step_action_urls.documents_review} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <input type="hidden" name="approved" value="true" />
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Review note</label>
                      <Textarea name="note" rows={4} placeholder="Confirm the parcel documents are in order" />
                    </div>
                    <button type="submit" className={actionButtonClass('default')}>Mark documents reviewed</button>
                  </form>
                ) : (
                  <div className="text-sm leading-7 text-muted-foreground">This step becomes available after the commission is accepted by an agent.</div>
                )}
              </CardContent>
            </Card>

            <Card className={commission.can_submit_to_lawyer ? 'bg-white/92' : 'border-dashed border-border bg-white/80'}>
              <CardHeader>
                <CardTitle className="text-base">Step 2 - Lawyer submission</CardTitle>
                <CardDescription>Forward the commission to the assigned or default lawyer for authentication.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {commission.can_submit_to_lawyer ? (
                  <form method="post" action={commission.step_action_urls.submit_to_lawyer} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Submission note</label>
                      <Textarea name="note" rows={4} placeholder="Describe what the lawyer should verify" />
                    </div>
                    <button type="submit" className={actionButtonClass('accent')}>Send to lawyer</button>
                  </form>
                ) : (
                  <div className="text-sm leading-7 text-muted-foreground">Documents must be reviewed before the lawyer stage opens.</div>
                )}
                {commission.assigned_lawyer ? (
                  <div className="rounded-2xl bg-muted/60 p-3 text-sm text-foreground">
                    Assigned lawyer: <span className="font-semibold">{commission.assigned_lawyer.email}</span>
                  </div>
                ) : null}
                <div className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
                  Lawyer status: {commission.lawyer_verified === true ? 'Verified' : commission.lawyer_verified === false ? 'Rejected' : 'Pending'}
                </div>
              </CardContent>
            </Card>

            <Card className={commission.can_schedule_site_visit ? 'bg-white/92' : 'border-dashed border-border bg-white/80'}>
              <CardHeader>
                <CardTitle className="text-base">Step 3 - Site visit</CardTitle>
                <CardDescription>Propose the visit date and place for buyer confirmation.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {commission.can_schedule_site_visit ? (
                  <form method="post" action={commission.step_action_urls.schedule_site_visit} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Visit date and time</label>
                      <Input type="datetime-local" name="visit_date" required />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Location</label>
                      <Input name="location" placeholder="Parcel access point or nearby landmark" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Notes</label>
                      <Textarea name="notes" rows={3} placeholder="Any site visit context for the buyer" />
                    </div>
                    <button type="submit" className={actionButtonClass('default')}>Schedule site visit</button>
                  </form>
                ) : (
                  <div className="text-sm leading-7 text-muted-foreground">The lawyer must verify the documents before a site visit can be scheduled.</div>
                )}
              </CardContent>
            </Card>

            <Card className={commission.can_complete_site_visit ? 'bg-white/92' : 'border-dashed border-border bg-white/80'}>
              <CardHeader>
                <CardTitle className="text-base">Step 4 - Site visit completion</CardTitle>
                <CardDescription>Record the completed visit and capture any final notes.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {commission.can_complete_site_visit ? (
                  <form method="post" action={commission.step_action_urls.complete_site_visit} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Completion notes</label>
                      <Textarea name="notes" rows={4} placeholder="Share what was observed during the site visit" />
                    </div>
                    <button type="submit" className={actionButtonClass('default')}>Mark site visit complete</button>
                  </form>
                ) : (
                  <div className="text-sm leading-7 text-muted-foreground">This step opens after the site visit has been scheduled.</div>
                )}
              </CardContent>
            </Card>

            <Card className={commission.can_close ? 'bg-white/92' : 'border-dashed border-border bg-white/80'}>
              <CardHeader>
                <CardTitle className="text-base">Step 5 - Closing</CardTitle>
                <CardDescription>Once the visit is complete, create the transaction and move into payment.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {commission.can_close ? (
                  <form method="post" action={commission.step_action_urls.close} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <button type="submit" className={actionButtonClass('accent')}>Create transaction and open payment</button>
                  </form>
                ) : (
                  <div className="text-sm leading-7 text-muted-foreground">Closing is available after document review, lawyer verification, and site visit completion.</div>
                )}
                {commission.transaction_url ? (
                  <a href={commission.transaction_url} className={actionButtonClass('outline')}>Continue to payment</a>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}


function MessagesPage() {
  const page = bootstrap.messages_page;
  if (!page) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92">
          <CardContent className="p-8 text-center text-sm text-muted-foreground">Messages are unavailable.</CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  // Combine threads from single or dual mode
  const initialThreads = useMemo(() => {
    if (page.mode === 'dual') {
      return [...(page.buyer_threads || []), ...(page.seller_threads || [])];
    }
    return page.threads || [];
  }, [page]);

  // Preset official protocol channels
  const officialChannels = [
    { id: 'general-escrow', name: 'general-escrow', topic: 'General escrow protocol questions, platform updates, and announcements' },
    { id: 'verification-desk', name: 'verification-desk', topic: 'Title deed searches, survey checks, and Ministry of Lands registry validation' },
    { id: 'legal-conveyancing', name: 'legal-conveyancing', topic: 'Advocate conveyancing milestones, LCB consent, and stamp duty clearance' },
  ];

  const quickPrompts = [
    'Hello, could you provide an update on the parcel verification status?',
    'I have uploaded the title search deed and survey maps.',
    'Could we review the latest escrow milestone agreement?',
    'What is the next step for advocate conveyancing approval?',
  ];

  const [activeChannelId, setActiveChannelId] = useState<string | null>(null);
  const isChannelMode = Boolean(activeChannelId);
  const currentChannel = officialChannels.find((c) => c.id === activeChannelId);

  const [threads, setThreads] = useState(initialThreads);
  const [selectedPartnerEmail, setSelectedPartnerEmail] = useState<string>(
    initialThreads[0]?.partner?.email || (page.allowed_recipients && page.allowed_recipients[0]?.email) || 'support@digiland.co.ke'
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'agent' | 'lawyer'>('all');
  const [inputMessage, setInputMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [isNewChatOpen, setIsNewChatOpen] = useState(false);
  const [newChatEmail, setNewChatEmail] = useState('');
  const [newChatRole, setNewChatRole] = useState('single');
  const [modalSearch, setModalSearch] = useState('');
  const [modalRoleFilter, setModalRoleFilter] = useState<'All' | 'Lawyer' | 'Agent' | 'Seller' | 'Buyer' | 'Admin'>('All');
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Active thread lookup
  const activeThread = useMemo(() => {
    return threads.find((t) => t.partner?.email && t.partner.email.toLowerCase() === selectedPartnerEmail.toLowerCase());
  }, [threads, selectedPartnerEmail]);

  // Selected recipient (if starting a chat with someone not yet in threads)
  const selectedRecipient = useMemo(() => {
    if (activeThread?.partner) return activeThread.partner;
    const found = (page.allowed_recipients || []).find(
      (r) => r.email && r.email.toLowerCase() === selectedPartnerEmail.toLowerCase()
    );
    if (found) return found;
    return {
      id: '',
      email: selectedPartnerEmail || 'support@digiland.co.ke',
      name: selectedPartnerEmail ? selectedPartnerEmail.split('@')[0] : 'Escrow Support',
      role: 'Support',
      is_staff: false,
      is_superuser: false,
    };
  }, [activeThread, page.allowed_recipients, selectedPartnerEmail]);

  // Filtered threads
  const filteredThreads = useMemo(() => {
    return threads.filter((t) => {
      if (!t.partner?.email) return false;
      const matchesSearch =
        t.partner.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.partner.name && t.partner.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (t.messages && t.messages[0]?.content && t.messages[0].content.toLowerCase().includes(searchQuery.toLowerCase()));

      if (!matchesSearch) return false;

      if (roleFilter === 'admin') return t.partner.role === 'Admin' || t.partner.is_staff;
      if (roleFilter === 'agent') return t.partner.role === 'Agent';
      if (roleFilter === 'lawyer') return t.partner.role === 'Lawyer';
      return true;
    });
  }, [threads, searchQuery, roleFilter]);

  // Background polling for real-time back-and-forth messaging updates
  useEffect(() => {
    if (!selectedPartnerEmail || isChannelMode) return;
    const interval = setInterval(async () => {
      try {
        const partner = (page.allowed_recipients || []).find(
          (r) => r.email && r.email.toLowerCase() === selectedPartnerEmail.toLowerCase()
        );
        const partnerId = partner?.id || activeThread?.partner?.id;
        if (!partnerId) return;

        const resp = await fetch(`/messages/thread/${partnerId}/`, {
          headers: { 'Accept': 'application/json' },
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.thread && data.thread.messages) {
            setThreads((prev) => {
              const exists = prev.some(
                (t) => t.partner?.email?.toLowerCase() === selectedPartnerEmail.toLowerCase()
              );
              if (exists) {
                return prev.map((t) =>
                  t.partner?.email?.toLowerCase() === selectedPartnerEmail.toLowerCase()
                    ? {
                        ...t,
                        messages: data.thread.messages,
                        count: data.thread.count,
                        latest_timestamp: data.thread.latest_timestamp,
                      }
                    : t
                );
              } else {
                return [data.thread, ...prev];
              }
            });
          }
        }
      } catch {
        // silent background poll
      }
    }, 6000);

    return () => clearInterval(interval);
  }, [selectedPartnerEmail, isChannelMode, page.allowed_recipients, activeThread?.partner?.id]);

  // Auto-scroll on active thread change or new messages
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeThread?.messages, selectedPartnerEmail]);

  // Send message handler
  const handleSendMessage = async (contentToSend?: string) => {
    const text = (contentToSend || inputMessage).trim();
    if (!text || !selectedPartnerEmail || isSending) return;

    setIsSending(true);
    setSendError(null);

    const tempId = `temp-${Date.now()}`;
    const newMsg = {
      id: tempId,
      sender_email: bootstrap.user?.email || 'You',
      content: text,
      timestamp: 'Just now',
      is_self: true,
    };

    // Optimistic UI update
    setThreads((prevThreads) => {
      const existing = prevThreads.find((t) => t.partner.email.toLowerCase() === selectedPartnerEmail.toLowerCase());
      if (existing) {
        return prevThreads.map((t) =>
          t.partner.email.toLowerCase() === selectedPartnerEmail.toLowerCase()
            ? {
                ...t,
                count: t.count + 1,
                latest_timestamp: 'Just now',
                messages: [newMsg, ...t.messages],
              }
            : t
        );
      } else {
        const newThread = {
          partner: selectedRecipient,
          latest_timestamp: 'Just now',
          count: 1,
          url: `/messages/`,
          messages: [newMsg],
        };
        return [newThread, ...prevThreads];
      }
    });

    setInputMessage('');

    try {
      const resp = await fetch(page.compose_action, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': page.csrf_token,
        },
        body: JSON.stringify({
          receiver_email: selectedPartnerEmail,
          content: text,
          recipient_type: 'single',
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || 'Failed to deliver message');
      }

      const data = await resp.json();
      if (data.message) {
        // Update temp message with server message id and timestamp
        setThreads((prevThreads) =>
          prevThreads.map((t) => {
            if (t.partner.email.toLowerCase() === selectedPartnerEmail.toLowerCase()) {
              return {
                ...t,
                messages: t.messages.map((m) => (m.id === tempId ? data.message : m)),
              };
            }
            return t;
          })
        );
      }
    } catch (err: any) {
      setSendError(err.message || 'Could not send message. Please check connection.');
    } finally {
      setIsSending(false);
    }
  };

  // Helper avatar initials & color
  const getAvatarInfo = (email: string, role?: string) => {
    const initial = (email || '?').charAt(0).toUpperCase();
    let bg = 'bg-slate-700 text-white';
    if (role === 'Admin' || role === 'Support') bg = 'bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-purple-500/20';
    else if (role === 'Agent') bg = 'bg-gradient-to-tr from-emerald-600 to-teal-600 text-white shadow-emerald-500/20';
    else if (role === 'Lawyer') bg = 'bg-gradient-to-tr from-blue-600 to-cyan-600 text-white shadow-blue-500/20';
    else if (role === 'Seller') bg = 'bg-gradient-to-tr from-amber-600 to-orange-600 text-white shadow-amber-500/20';
    else if (role === 'Buyer') bg = 'bg-gradient-to-tr from-teal-600 to-emerald-600 text-white shadow-teal-500/20';
    return { initial, bg };
  };

  const safeRecipientName = selectedRecipient?.name || (selectedRecipient?.email ? selectedRecipient.email.split('@')[0] : 'Escrow Desk');
  const safeRecipientEmail = selectedRecipient?.email || 'support@digiland.co.ke';
  const safeRecipientRole = selectedRecipient?.role || 'Support';

  return (
    <AppShell {...shellProps} activeNav="messages">
      <div className="flex h-[calc(100vh-8rem)] min-h-[640px] flex-col overflow-hidden rounded-[2rem] border border-white/[0.08] bg-[#0c111e] shadow-2xl backdrop-blur-xl md:flex-row">
        {/* Left Sub-Sidebar: CHANNELS & DIRECT MESSAGES */}
        <div className="flex w-full flex-col border-b border-white/[0.08] bg-[#080b14] md:w-72 lg:w-80 md:border-r md:border-b-0 shrink-0">
          {/* Sub-Sidebar Header */}
          <div className="flex h-14 items-center justify-between border-b border-white/[0.08] px-4">
            <div className="flex items-center gap-2">
              <span className="font-black text-sm text-slate-100 tracking-wide">Messages & Protocol</span>
            </div>
            <button
              onClick={() => setIsNewChatOpen(true)}
              title="New DM"
              className="flex h-7 w-7 items-center justify-center rounded-lg bg-white/[0.06] text-slate-300 transition hover:bg-emerald-500/20 hover:text-emerald-300"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          {/* Search Box */}
          <div className="p-3">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search channels or DMs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-full rounded-xl border border-white/10 bg-[#0f1422] pl-8 pr-3 text-xs text-slate-200 placeholder:text-slate-500 outline-none transition focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/30"
              />
            </div>
          </div>

          {/* Channels & DMs Scrollable List */}
          <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-4">
            {/* SECTION 1: CHANNELS */}
            <div>
              <div className="px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 flex items-center justify-between">
                <span>Channels</span>
                <span className="text-[9px] text-emerald-400 font-bold">Public</span>
              </div>
              <div className="mt-1 space-y-0.5">
                {officialChannels.map((channel) => {
                  const isActive = activeChannelId === channel.id;
                  return (
                    <button
                      key={channel.id}
                      onClick={() => {
                        setActiveChannelId(channel.id);
                      }}
                      className={cn(
                        'flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-xs font-bold transition-all duration-150',
                        isActive
                          ? 'bg-emerald-500/15 text-emerald-300 shadow-[inset_0_0_8px_rgba(16,185,129,0.2)]'
                          : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                      )}
                    >
                      <span className={cn('text-sm font-extrabold', isActive ? 'text-emerald-400' : 'text-slate-500')}>#</span>
                      <span className="truncate">{channel.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* SECTION 2: DIRECT MESSAGES */}
            <div>
              <div className="px-2 py-1 text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 flex items-center justify-between">
                <span>Direct Messages</span>
                <span className="text-[9px] text-purple-400 font-bold">Encrypted</span>
              </div>
              <div className="mt-1 space-y-1">
                {filteredThreads.length === 0 ? (
                  <div className="px-3 py-4 text-center text-xs text-slate-500">
                    No active DMs yet.
                    <button
                      onClick={() => setIsNewChatOpen(true)}
                      className="block mx-auto mt-1 font-bold text-emerald-400 hover:underline"
                    >
                      Start a chat
                    </button>
                  </div>
                ) : (
                  filteredThreads.map((thread, tIdx) => {
                    const partnerEmail = thread?.partner?.email || `contact-${tIdx}@digiland.co.ke`;
                    const partnerRole = thread?.partner?.role || 'User';
                    const partnerName = thread?.partner?.name || partnerEmail.split('@')[0];
                    const isSelected = !isChannelMode && selectedPartnerEmail.toLowerCase() === partnerEmail.toLowerCase();
                    const avatar = getAvatarInfo(partnerEmail, partnerRole);
                    const latestMsg = thread?.messages && thread.messages[0];

                    return (
                      <button
                        key={partnerEmail}
                        onClick={() => {
                          setActiveChannelId(null);
                          setSelectedPartnerEmail(partnerEmail);
                        }}
                        className={cn(
                          'flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left transition-all duration-150',
                          isSelected
                            ? 'bg-white/[0.08] text-white shadow-sm ring-1 ring-emerald-500/40'
                            : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200'
                        )}
                      >
                        <div className="relative shrink-0">
                          <div className={cn('flex h-7 w-7 items-center justify-center rounded-lg text-xs font-black', avatar.bg)}>
                            {avatar.initial}
                          </div>
                          <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border border-[#080b14] bg-emerald-500" />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-1">
                            <span className={cn('truncate text-xs font-bold', isSelected ? 'text-white' : 'text-slate-300')}>
                              {partnerName}
                            </span>
                            <span className="text-[9px] text-slate-500 shrink-0">{thread.latest_timestamp || ''}</span>
                          </div>
                          <div className="truncate text-[10px] text-slate-500">
                            {latestMsg?.content || 'Direct conversation'}
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* User Dock Footer */}
          <div className="border-t border-white/[0.08] p-3 bg-[#06080e] flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-xs font-black text-white shrink-0">
                {bootstrap.user?.email ? bootstrap.user.email.charAt(0).toUpperCase() : 'U'}
              </div>
              <div className="min-w-0">
                <div className="truncate text-xs font-bold text-slate-200">{bootstrap.user?.email || 'User'}</div>
                <div className="text-[10px] text-emerald-400 font-medium capitalize">{bootstrap.user?.role || 'Guest'}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Main Chat Canvas (Discord / AfterQuery Style) */}
        <div className="flex flex-1 flex-col bg-[#0e1322]">
          {/* Main Chat Header Bar */}
          <div className="flex h-14 items-center justify-between border-b border-white/[0.08] px-6 bg-[#0c101d]">
            <div className="flex items-center gap-3">
              <span className="text-xl font-extrabold text-emerald-400">
                {isChannelMode ? '#' : '@'}
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-black text-white">
                    {isChannelMode ? currentChannel?.name : safeRecipientName}
                  </h3>
                  <Badge tone="outline" className="bg-white/[0.04] text-[9px] uppercase font-bold py-0 text-slate-300">
                    {isChannelMode ? 'Platform Channel' : safeRecipientRole}
                  </Badge>
                </div>
                <div className="text-[10px] text-slate-400 truncate max-w-xl">
                  {isChannelMode ? currentChannel?.topic : `Direct encrypted session • ${safeRecipientEmail}`}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[10px] font-bold text-emerald-300">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Verified Protocol</span>
              </div>
            </div>
          </div>

          {/* Chat Stream Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Date divider */}
            <div className="relative flex items-center justify-center">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/[0.08]" />
              </div>
              <span className="relative rounded-full bg-[#13192a] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border border-white/[0.06]">
                Official Escrow Session
              </span>
            </div>

            {/* If Channel Mode */}
            {isChannelMode ? (
              <div className="space-y-6">
                <div className="flex items-start gap-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-500 text-slate-950 font-black text-base shadow-lg shadow-emerald-500/20">
                    D
                  </div>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-xs text-white">Digiland Escrow Protocol</span>
                      <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[9px] font-black uppercase text-emerald-300">TEAM</span>
                      <span className="text-[10px] text-slate-500">Today at 10:00 AM</span>
                    </div>
                    <div className="text-xs text-slate-300 leading-relaxed">
                      Welcome to <strong className="text-white">#{currentChannel?.name}</strong>. This official channel hosts protocol announcements, land title deed registry updates, and escrow settlement notifications across Kenya.
                    </div>
                    {/* Emoji Reactions */}
                    <div className="flex items-center gap-1.5 pt-1">
                      <button className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-bold text-slate-300 hover:bg-white/[0.08]">
                        <span>👍</span> <span>12</span>
                      </button>
                      <button className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-bold text-slate-300 hover:bg-white/[0.08]">
                        <span>🛡️</span> <span>8</span>
                      </button>
                      <button className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-bold text-slate-300 hover:bg-white/[0.08]">
                        <span>🇰🇪</span> <span>15</span>
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex items-start gap-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-purple-600 text-white font-black text-base shadow-lg shadow-purple-500/20">
                    A
                  </div>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-xs text-white">Chief Escrow Officer</span>
                      <span className="rounded bg-purple-500/20 px-1.5 py-0.2 text-[9px] font-black uppercase text-purple-300">ADMIN</span>
                      <span className="text-[10px] text-slate-500">Today at 10:45 AM</span>
                    </div>
                    <div className="text-xs text-slate-300 leading-relaxed">
                      Sellers with pending parcel submissions: Please make sure your Survey Deed Plans and Land Registry Search Certificates (Form RL 26) are uploaded. Verification SLAs are currently under 24 hours.
                    </div>
                    <div className="flex items-center gap-1.5 pt-1">
                      <button className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-bold text-slate-300 hover:bg-white/[0.08]">
                        <span>✅</span> <span>6</span>
                      </button>
                      <button className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[11px] font-bold text-slate-300 hover:bg-white/[0.08]">
                        <span>🔥</span> <span>4</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : !activeThread || !activeThread.messages || activeThread.messages.length === 0 ? (
              /* Empty DM State */
              <div className="mx-auto my-auto max-w-md p-8 text-center space-y-4 rounded-3xl border border-white/10 bg-white/[0.02] backdrop-blur-xl">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400">
                  <MessageSquare className="h-7 w-7" />
                </div>
                <div>
                  <h4 className="text-base font-extrabold text-white">
                    Direct channel with {safeRecipientName}
                  </h4>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    Messages sent here are private and protected by Digiland escrow dual-signature mediation.
                  </p>
                </div>

                <div className="space-y-2 pt-2">
                  <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                    Quick Suggestions
                  </div>
                  <div className="grid gap-2">
                    {quickPrompts.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => handleSendMessage(prompt)}
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] p-2.5 text-left text-xs font-semibold text-slate-300 transition hover:border-emerald-500/60 hover:bg-emerald-500/10 hover:text-white"
                      >
                        <span>{prompt}</span>
                        <CornerDownLeft className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Active DM Messages Feed (Discord / Slack style) */
              <div className="space-y-4">
                {[...(activeThread.messages || [])].reverse().map((msg, idx) => {
                  const isSelf = Boolean(msg?.is_self);
                  const senderEmail = isSelf ? (bootstrap.user?.email || 'You') : safeRecipientEmail;
                  const senderRole = isSelf ? (bootstrap.user?.role || 'User') : safeRecipientRole;
                  const avatar = getAvatarInfo(senderEmail, senderRole);

                  return (
                    <div
                      key={msg?.id || idx}
                      className={cn(
                        'group flex items-start gap-3 rounded-2xl p-3 transition-colors hover:bg-white/[0.03]',
                        isSelf ? 'border-l-2 border-emerald-500/60 bg-emerald-500/[0.03]' : ''
                      )}
                    >
                      <div
                        className={cn(
                          'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl font-black text-xs shadow-md',
                          avatar.bg
                        )}
                      >
                        {avatar.initial}
                      </div>

                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className={cn('text-xs font-extrabold', isSelf ? 'text-emerald-300' : 'text-white')}>
                            {isSelf ? 'You' : safeRecipientName}
                          </span>
                          <span
                            className={cn(
                              'rounded px-1.5 py-0.2 text-[9px] font-black uppercase tracking-wider',
                              senderRole === 'Admin'
                                ? 'bg-purple-500/20 text-purple-300'
                                : senderRole === 'Agent'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-slate-700 text-slate-300'
                            )}
                          >
                            {senderRole}
                          </span>
                          <span className="text-[10px] text-slate-500 font-medium">{msg?.timestamp || ''}</span>
                        </div>

                        <div className="text-xs sm:text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                          {msg?.content || ''}
                        </div>
                      </div>
                    </div>
                  );
                })}
                <div ref={chatBottomRef} />
              </div>
            )}
          </div>

          {/* Bottom Docked Input Box & Notice Banner */}
          <div className="border-t border-white/[0.08] bg-[#0a0e1a] p-4 space-y-2 shrink-0 z-20">
            {/* Send Error Alert (if any) */}
            {sendError && (
              <div className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>{sendError}</span>
              </div>
            )}

            {/* Disclaimer Banner */}
            <div className="flex items-center gap-2 text-[11px] text-slate-400">
              <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>
                This channel is escrow-secured — all communications are archived for transaction mediation.
              </span>
            </div>

            {/* Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="relative flex items-center rounded-2xl border border-white/20 bg-[#121727] p-1.5 transition-all focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20"
            >
              <input
                id="message-chat-input"
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder={
                  isChannelMode
                    ? `Message in #${currentChannel?.name || 'protocol'}...`
                    : `Message @${safeRecipientName}...`
                }
                autoComplete="off"
                className="h-10 w-full bg-transparent px-3 text-xs sm:text-sm text-white placeholder:text-slate-400 outline-none cursor-text pointer-events-auto"
              />

              <div className="flex items-center gap-1 pr-1">
                <Button
                  type="submit"
                  disabled={!inputMessage.trim() || isSending}
                  className="h-8 w-8 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 p-0 text-slate-950 shadow-md shadow-emerald-500/20 transition-all hover:scale-105 hover:brightness-110 disabled:opacity-30 flex items-center justify-center shrink-0 cursor-pointer"
                >
                  <Send className="h-4 w-4 text-slate-950" />
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>

      {/* Start New Chat Modal */}
      {isNewChatOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-md">
          <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#0f1523] p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-emerald-400" />
                <h3 className="font-bold text-white text-base">New Direct Message</h3>
              </div>
              <button
                onClick={() => setIsNewChatOpen(false)}
                className="rounded-full p-1.5 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Search Input */}
            <div className="mt-3">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search by name, email, or role..."
                  value={modalSearch}
                  onChange={(e) => setModalSearch(e.target.value)}
                  className="h-9 w-full rounded-xl border border-white/10 bg-[#0a0e18] pl-9 pr-3 text-xs text-slate-200 placeholder:text-slate-500 outline-none focus:border-emerald-500/60"
                />
              </div>
            </div>

            {/* Role Filter Tabs */}
            <div className="mt-3 flex flex-wrap gap-1.5 border-b border-white/10 pb-3">
              {(['All', 'Lawyer', 'Agent', 'Seller', 'Buyer', 'Admin'] as const).map((rTab) => (
                <button
                  key={rTab}
                  onClick={() => setModalRoleFilter(rTab)}
                  className={cn(
                    'px-2.5 py-1 rounded-lg text-[11px] font-bold transition',
                    modalRoleFilter === rTab
                      ? 'bg-emerald-500 text-slate-950 shadow-sm'
                      : 'bg-white/[0.04] text-slate-400 hover:bg-white/[0.08] hover:text-slate-200'
                  )}
                >
                  {rTab}
                </button>
              ))}
            </div>

            {/* Recipients List */}
            <div className="mt-3 space-y-2 max-h-80 overflow-y-auto pr-1">
              {(page.allowed_recipients || [])
                .filter((recipient) => {
                  if (modalRoleFilter !== 'All' && recipient.role !== modalRoleFilter) {
                    return false;
                  }
                  if (modalSearch.trim()) {
                    const q = modalSearch.toLowerCase();
                    const matches =
                      (recipient.email && recipient.email.toLowerCase().includes(q)) ||
                      (recipient.name && recipient.name.toLowerCase().includes(q)) ||
                      (recipient.role && recipient.role.toLowerCase().includes(q));
                    if (!matches) return false;
                  }
                  return true;
                })
                .map((recipient) => {
                  const avatar = getAvatarInfo(recipient.email, recipient.role);
                  return (
                    <button
                      key={recipient.email}
                      onClick={() => {
                        setActiveChannelId(null);
                        setSelectedPartnerEmail(recipient.email);
                        setIsNewChatOpen(false);
                      }}
                      className="flex w-full items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-left transition hover:border-emerald-500/40 hover:bg-emerald-500/10"
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl text-xs font-black shrink-0', avatar.bg)}>
                          {avatar.initial}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-slate-200 truncate">{recipient.name || recipient.email}</div>
                          <div className="text-[10px] text-slate-400 truncate">{recipient.email}</div>
                        </div>
                      </div>
                      <Badge
                        tone="outline"
                        className={cn(
                          'text-[9px] uppercase font-black px-2 py-0.5',
                          recipient.role === 'Lawyer'
                            ? 'border-blue-500/40 text-blue-300 bg-blue-500/10'
                            : recipient.role === 'Agent'
                            ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10'
                            : recipient.role === 'Seller'
                            ? 'border-amber-500/40 text-amber-300 bg-amber-500/10'
                            : recipient.role === 'Admin'
                            ? 'border-purple-500/40 text-purple-300 bg-purple-500/10'
                            : 'border-slate-600 text-slate-300 bg-slate-800/40'
                        )}
                      >
                        {recipient.role}
                      </Badge>
                    </button>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

function SupportPage() {
  const page = bootstrap.support_page;
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Support is unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <PageHeader kicker="Support" title={bootstrap.title} subtitle={bootstrap.subtitle} />
          <div className="grid gap-4 md:grid-cols-2">
            {page.tickets.length ? page.tickets.map((ticket) => (
              <Card key={ticket.id} className={ticket.status === 'Resolved' ? 'border-emerald-200 bg-white/92' : 'bg-white/92'}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="text-base">{ticket.subject}</CardTitle>
                    <Badge tone={ticket.status === 'Resolved' ? 'success' : ticket.status === 'In_Progress' ? 'warning' : 'muted'}>{ticket.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm leading-7 text-foreground">{ticket.message_excerpt}</p>
                  <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Submitted {ticket.created_at}</div>
                </CardContent>
              </Card>
            )) : (
              <Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">No support tickets yet.</CardContent></Card>
            )}
          </div>
        </div>
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Ticket className="h-4 w-4 text-emerald-700" />Open a ticket</CardTitle>
            <CardDescription>Use support for disputes, verification issues, or account access problems.</CardDescription>
          </CardHeader>
          <CardContent>
            <form method="post" action={page.create_action} className="space-y-4">
              <input type="hidden" name="csrfmiddlewaretoken" value={page.csrf_token} />
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Subject</label>
                <Input name="subject" placeholder="Title verification failed" required />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Message</label>
                <Textarea name="message" rows={5} placeholder="Describe your issue" required />
              </div>
              <Button type="submit" className="w-full rounded-full">Submit ticket</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function RecommendationsPage() {
  const page = bootstrap.recommendations_page;
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Recommendations are unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-8">
        <PageHeader kicker="AI-powered" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />

        <Card className="border-border/70 bg-white/92">
          <CardContent className="grid gap-4 p-6 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={page.rec_type === 'personalized' ? 'success' : 'outline'}>
                  {page.rec_type === 'personalized' ? 'ML personalized' : 'Popular feed'}
                </Badge>
                <Badge tone="outline">{page.popular_county || 'Target area'}</Badge>
              </div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Land discovery tuned to intent, budget, and geography</h2>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                The feed combines behavior signals, map proximity, target county demand, and premium sponsored placements to surface land that is actually relevant.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                { label: 'Recommended', value: page.recommended?.length || 0, tone: 'success' as const },
                { label: 'Sponsored', value: page.sponsored_listings?.length || 0, tone: 'warning' as const },
                { label: 'Hot deals', value: page.hot_deals?.length || 0, tone: 'accent' as const },
                { label: 'Popular', value: page.popular_parcels?.length || 0, tone: 'default' as const },
              ].map((stat) => (
                <div key={stat.label} className="rounded-3xl border border-border bg-muted/30 p-4">
                  <div className="text-[10px] font-black uppercase tracking-[0.26em] text-muted-foreground">{stat.label}</div>
                  <div className={cn('mt-2 text-2xl font-black tracking-tight', stat.tone === 'success' ? 'text-emerald-700' : stat.tone === 'warning' ? 'text-amber-700' : stat.tone === 'accent' ? 'text-slate-900' : 'text-foreground')}>
                    {stat.value}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <RecommendationSection
          title="Recommended for You"
          subtitle="Personalized land matches built from your behavior and location signals."
          items={page.recommended || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
          showMatchScore
          ctaLabel="Open parcel"
        />

        <RecommendationSection
          title="Premium Sponsored Lands"
          subtitle="Priority placements from sellers investing in visibility."
          items={page.sponsored_listings || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open sponsored parcel"
        />

        <RecommendationSection
          title="Hot Deals Near You"
          subtitle="Lower-priced opportunities inside your target radius."
          items={page.hot_deals || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open deal"
        />

        <RecommendationSection
          title={`Trending in ${page.popular_county || 'your area'}`}
          subtitle="Listings with rising engagement in your strongest county."
          items={page.trending_in_target_area || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open trend"
        />

        <RecommendationSection
          title="Recently Viewed Lands"
          subtitle="Resume from where you left off."
          items={page.recently_viewed || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Continue browsing"
        />

        <RecommendationSection
          title="Recently Viewed Similar Lands"
          subtitle="Similar parcels matched to your last viewing session."
          items={page.recently_viewed_similar || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open similar parcel"
        />

        <RecommendationSection
          title="People Also Viewed"
          subtitle="What comparable buyers are exploring."
          items={page.people_also_viewed || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open parcel"
        />

        <RecommendationSection
          title={`Popular in ${page.popular_county || 'your county'}`}
          subtitle="The highest-interest parcels in your active county."
          items={page.popular_parcels || []}
          gridClassName="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
          ctaLabel="Open parcel"
        />

        {false && page.popular_parcels.length ? (
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="text-base">Popular in {page.popular_county}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {page.popular_parcels.map((parcel) => (
                <a key={parcel.parcel_number} href={parcel.details_url} className="rounded-3xl border border-border bg-muted/40 p-4 text-sm font-semibold text-foreground hover:bg-muted">
                  {parcel.parcel_number} · {parcel.ward}, {parcel.county}
                </a>
              ))}
            </CardContent>
          </Card>
        ) : null}

        {false && page.recently_viewed.length ? (
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="text-base">Recently viewed</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {page.recently_viewed.map((parcel) => (
                <a key={parcel.parcel_number} href={parcel.details_url} className="rounded-3xl border border-border bg-muted/40 p-4 text-sm font-semibold text-foreground hover:bg-muted">
                  {parcel.parcel_number}
                </a>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </AppShell>
  );
}

function PredictionPage() {
  const page = bootstrap.prediction_page;
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Price prediction is unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const prediction = page.prediction;

  return (
    <AppShell {...shellProps}>
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-6">
          <PageHeader kicker="Machine learning" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />
          <FormRenderer form={page.form} csrfToken={bootstrap.csrf_token || undefined} />
          {page.model_info ? (
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Model info</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-3 text-sm">
                <div className="rounded-2xl bg-muted/60 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Records</div>
                  <div className="mt-1 font-bold">{page.model_info.n_records}</div>
                </div>
                <div className="rounded-2xl bg-muted/60 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Counties</div>
                  <div className="mt-1 font-bold">{page.model_info.n_counties}</div>
                </div>
                <div className="rounded-2xl bg-muted/60 p-3">
                  <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Algorithm</div>
                  <div className="mt-1 font-bold">{page.model_info.algorithm}</div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div>
          {prediction?.error ? (
            <Card className="border-rose-200 bg-rose-50/70">
              <CardContent className="p-6">
                <div className="flex items-start gap-3 text-rose-800">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                  <div>
                    <div className="font-semibold">Prediction error</div>
                    <p className="mt-1 text-sm leading-7">{prediction.error}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : prediction ? (
            <div className="space-y-6">
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="text-base">AI price estimate</CardTitle>
                  <CardDescription>{prediction.county} · {prediction.land_use} · {prediction.size_acres} Acres</CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6 text-center">
                    <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">Estimated price per acre</div>
                    <div className="mt-2 text-4xl font-black tracking-tight text-foreground">KES {prediction.price_per_acre}</div>
                    <div className="mt-2 text-sm text-muted-foreground">95% confidence: KES {prediction.confidence_low} - {prediction.confidence_high}</div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl bg-muted/60 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Total estimated value</div>
                      <div className="mt-1 text-xl font-black text-foreground">KES {prediction.total_value}</div>
                    </div>
                    <div className="rounded-2xl bg-muted/60 p-4">
                      <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Model accuracy</div>
                      <div className="mt-1 text-xl font-black text-foreground">{prediction.model_accuracy}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {prediction.comparisons?.length ? (
                <Card className="bg-white/92">
                  <CardHeader>
                    <CardTitle className="text-base">Market comparisons</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {prediction.comparisons.map((comparison) => (
                      <div key={`${comparison.county}-${comparison.constituency}`} className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted/40 p-4 text-sm">
                        <div>
                          <div className="font-semibold text-foreground">{comparison.constituency}, {comparison.county}</div>
                          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{comparison.land_use} · {comparison.size_acres} Acres</div>
                        </div>
                        <div className="font-black text-emerald-700">KES {comparison.price_per_acre}</div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
            </div>
          ) : (
            <Card className="bg-white/92">
              <CardContent className="p-8 text-center text-sm text-muted-foreground">Run a prediction to see estimated prices and comparisons.</CardContent>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function TaskManagementPage() {
  const page = bootstrap.task_board;
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Task management is unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const isAdmin = bootstrap.user?.role === 'Admin';

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Tasks" title={bootstrap.title} subtitle={bootstrap.subtitle} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {(isAdmin
            ? [
                ['Pending parcels', page.pending_parcels.length],
                ['Completed parcels', page.completed_parcels.length],
                ['Pending transactions', page.pending_transactions.length],
                ['Unassigned', page.unassigned_count || 0],
              ]
            : [
                ['Pending parcels', page.pending_parcels.length],
                ['Completed parcels', page.completed_parcels.length],
                ['Pending transactions', page.pending_transactions.length],
                ['Pending users', page.pending_users.length],
              ]
          ).map(([label, value]) => (
            <Card key={label as string} className="bg-white/92">
              <CardContent className="p-5">
                <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">{label as string}</div>
                <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{String(value)}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {isAdmin ? (
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Pending parcels</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {page.pending_parcels.map((parcel) => (
                  <div key={parcel.parcel_number} className="rounded-3xl border border-border bg-muted/40 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold text-foreground">{parcel.parcel_number}</div>
                        <div className="text-sm text-muted-foreground">{parcel.county}, {parcel.constituency}</div>
                      </div>
                      <Badge tone="warning">{parcel.status_badge || parcel.verification_status}</Badge>
                    </div>
                    <form method="post" action="/agent/assign-task/" className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
                      <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                      <input type="hidden" name="parcel_number" value={parcel.parcel_number} />
                      <select name="agent_id" className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm">
                        <option value="">Assign agent manually</option>
                        {page.agent_recommendations ? page.agent_recommendations.map((rec, index) => (
                          <option key={rec.agent_id} value={rec.agent_id}>
                            {index === 0 ? '🏆 ' : ''}{rec.agent_email} - AI Score: {Math.round(rec.score)}/100
                          </option>
                        )) : page.verified_agents.map((agent) => (
                          <option key={agent.id || agent.email} value={agent.id || agent.email}>{agent.email}</option>
                        ))}
                      </select>
                      <Button type="submit" className="rounded-full">Assign</Button>
                    </form>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="bg-white/92">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-purple-100 text-purple-700">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                  </div>
                  <CardTitle className="text-base">AI Agent Insights</CardTitle>
                </div>
                <CardDescription>Intelligent task distribution based on agent capabilities, ratings, and workload.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {page.agent_recommendations ? page.agent_recommendations.map((rec) => (
                  <div key={rec.agent_id} className="rounded-3xl border border-border bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 pb-3">
                      <div>
                        <div className="font-bold text-foreground">{rec.agent_email}</div>
                        {rec.is_new ? <span className="mt-1 inline-block rounded-md bg-emerald-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-800">New Agent Program</span> : null}
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-black tracking-tight text-purple-700">{Math.round(rec.score)}</div>
                        <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">AI Score</div>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 divide-x divide-border/50 text-center text-xs">
                      <div>
                        <div className="font-semibold text-foreground">{rec.rating?.average_rating ? `${parseFloat(rec.rating.average_rating).toFixed(1)} ★` : 'No rating'}</div>
                        <div className="mt-0.5 text-muted-foreground">Rating</div>
                      </div>
                      <div>
                        <div className="font-semibold text-foreground">{rec.completion?.rate ? `${Math.round(rec.completion.rate * 100)}%` : '0%'}</div>
                        <div className="mt-0.5 text-muted-foreground">Completion</div>
                      </div>
                      <div>
                        <div className="font-semibold text-foreground">{rec.usage?.recent_activity || 0}</div>
                        <div className="mt-0.5 text-muted-foreground">Recent Tasks</div>
                      </div>
                    </div>
                  </div>
                )) : (
                  <div className="text-center text-sm text-muted-foreground">AI recommendations not available.</div>
                )}
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className="bg-white/92">
              <CardHeader><CardTitle className="text-base">Pending parcels</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {page.pending_parcels.map((parcel) => (
                  <a key={parcel.parcel_number} href={parcel.details_url} className="block rounded-3xl border border-border bg-muted/40 p-4 hover:bg-muted">
                    <div className="font-semibold text-foreground">{parcel.parcel_number}</div>
                    <div className="text-sm text-muted-foreground">{parcel.county}, {parcel.constituency}</div>
                  </a>
                ))}
              </CardContent>
            </Card>
            <Card className="bg-white/92">
              <CardHeader><CardTitle className="text-base">Completed parcels</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {page.completed_parcels.map((parcel) => (
                  <a key={parcel.parcel_number} href={parcel.details_url} className="block rounded-3xl border border-border bg-muted/40 p-4 hover:bg-muted">
                    <div className="font-semibold text-foreground">{parcel.parcel_number}</div>
                    <div className="text-sm text-muted-foreground">{parcel.county}, {parcel.constituency}</div>
                  </a>
                ))}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function ApprovalsPage() {
  const page = bootstrap.approvals_page;
  const [activeTab, setActiveTab] = useState<'users' | 'parcels' | 'transactions' | 'removals'>('users');
  const [searchQuery, setSearchQuery] = useState('');

  if (!page) {
    return (
      <AppShell {...{
        title: bootstrap.title,
        subtitle: bootstrap.subtitle,
        user: bootstrap.user,
        nav: bootstrap.nav,
        logoutUrl: bootstrap.logout_url,
        csrfToken: bootstrap.csrf_token,
      }}>
        <Card className="bg-white/92 shadow-sm">
          <CardContent className="p-12 text-center text-muted-foreground">
            <AlertTriangle className="mx-auto mb-3 h-10 w-10 text-amber-500" />
            <div className="text-lg font-bold text-foreground">Approvals Workspace Unavailable</div>
            <p className="mt-1 text-sm">You do not have access or no pending approvals exist.</p>
          </CardContent>
        </Card>
      </AppShell>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const pendingUsers = page.pending_users || [];
  const pendingParcels = page.pending_parcels || [];
  const pendingTransactions = page.pending_transactions || [];
  const pendingRemovalRequests = page.pending_joint_removals || [];

  // Filter items by search query
  const filteredUsers = pendingUsers.filter(u => 
    !searchQuery || u.email?.toLowerCase().includes(searchQuery.toLowerCase()) || u.role?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredParcels = pendingParcels.filter(p => 
    !searchQuery || p.parcel_number?.toLowerCase().includes(searchQuery.toLowerCase()) || 
    p.county?.toLowerCase().includes(searchQuery.toLowerCase()) || 
    p.constituency?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredTransactions = pendingTransactions.filter(t => 
    !searchQuery || t.parcel_number?.toLowerCase().includes(searchQuery.toLowerCase()) || t.status?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredRemovals = pendingRemovalRequests.filter(r => 
    !searchQuery || r.group_name?.toLowerCase().includes(searchQuery.toLowerCase()) || r.member?.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AppShell {...shellProps}>
      <div className="space-y-8 max-w-7xl mx-auto">
        <PageHeader 
          kicker="Command Hub" 
          title="Central Approvals & Identity Verification" 
          subtitle="Manage pending user KYC applications, parcel verification listings, escrow transfers, and joint member exits." 
        />

        {/* Tab Selection Navigation Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/60 pb-4">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('users')}
              className={cn(
                "inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 cursor-pointer",
                activeTab === 'users'
                  ? "bg-emerald-700 text-white shadow-md"
                  : "bg-white border border-border text-slate-700 hover:bg-slate-50"
              )}
            >
              <Users className="h-4 w-4" />
              <span>Pending Users</span>
              <span className={cn("px-2 py-0.5 rounded-full text-xs font-black", activeTab === 'users' ? "bg-emerald-800 text-emerald-100" : "bg-slate-100 text-slate-700")}>
                {pendingUsers.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('parcels')}
              className={cn(
                "inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 cursor-pointer",
                activeTab === 'parcels'
                  ? "bg-emerald-700 text-white shadow-md"
                  : "bg-white border border-border text-slate-700 hover:bg-slate-50"
              )}
            >
              <Landmark className="h-4 w-4" />
              <span>Pending Parcels</span>
              <span className={cn("px-2 py-0.5 rounded-full text-xs font-black", activeTab === 'parcels' ? "bg-emerald-800 text-emerald-100" : "bg-slate-100 text-slate-700")}>
                {pendingParcels.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('transactions')}
              className={cn(
                "inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 cursor-pointer",
                activeTab === 'transactions'
                  ? "bg-emerald-700 text-white shadow-md"
                  : "bg-white border border-border text-slate-700 hover:bg-slate-50"
              )}
            >
              <WalletCards className="h-4 w-4" />
              <span>Active Escrow</span>
              <span className={cn("px-2 py-0.5 rounded-full text-xs font-black", activeTab === 'transactions' ? "bg-emerald-800 text-emerald-100" : "bg-slate-100 text-slate-700")}>
                {pendingTransactions.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('removals')}
              className={cn(
                "inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full text-sm font-bold transition-all duration-200 cursor-pointer",
                activeTab === 'removals'
                  ? "bg-emerald-700 text-white shadow-md"
                  : "bg-white border border-border text-slate-700 hover:bg-slate-50"
              )}
            >
              <Gavel className="h-4 w-4" />
              <span>Joint Removals</span>
              <span className={cn("px-2 py-0.5 rounded-full text-xs font-black", activeTab === 'removals' ? "bg-emerald-800 text-emerald-100" : "bg-slate-100 text-slate-700")}>
                {pendingRemovalRequests.length}
              </span>
            </button>
          </div>

          {/* Quick Search Input */}
          <div className="relative min-w-[240px]">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter current view..."
              className="w-full h-10 pl-9 pr-4 rounded-full border border-border bg-white text-xs font-medium focus:outline-none focus:ring-2 focus:ring-emerald-500/20 shadow-sm"
            />
            <MapPin className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
          </div>
        </div>

        {/* TAB 1: PENDING USERS */}
        {activeTab === 'users' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-black text-slate-900">User Identity & KYC Queue</h3>
              <span className="text-xs text-muted-foreground">Showing {filteredUsers.length} user(s) awaiting verification</span>
            </div>

            {filteredUsers.length === 0 ? (
              <Card className="bg-white/95">
                <CardContent className="p-12 text-center text-muted-foreground">
                  <Users className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <div className="text-base font-bold text-slate-700">No Pending User Identity Verification Requests</div>
                  <p className="text-xs mt-1">All buyer and seller identity submissions have been processed.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {filteredUsers.map((user) => (
                  <Card key={user.email} className="bg-white/95 border-slate-200/80 shadow-md rounded-[1.75rem] overflow-hidden hover:shadow-lg transition duration-200">
                    <CardContent className="p-6 text-left space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-3.5">
                          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 font-bold text-lg border border-emerald-100">
                            {user.email.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-bold text-base text-slate-900 truncate max-w-[220px]">{user.email}</div>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge tone="outline" className="text-xs font-semibold">{user.role}</Badge>
                              <span className="text-xs text-slate-400">ID Verification Pending</span>
                            </div>
                          </div>
                        </div>
                        <Badge tone="warning" className="px-3 py-1 text-xs">Needs KYC Review</Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-100">
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">ID Number</span>
                          <strong className="text-slate-800 font-semibold">{user.id_number || 'Not provided'}</strong>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">KRA PIN</span>
                          <strong className="text-slate-800 font-semibold">{user.kra_pin || 'Not provided'}</strong>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 pt-2">
                        <a 
                          href={`/agent/approvals/${user.id}/review/`} 
                          className="flex-1 inline-flex h-10 items-center justify-center rounded-full border border-slate-300 bg-white px-4 text-xs font-bold text-slate-700 hover:bg-slate-50 transition shadow-sm"
                        >
                          Review Identity & Docs
                        </a>
                        <form method="post" action={`/agent/users/${user.id}/approve/`} className="flex-1">
                          <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                          <Button type="submit" className="w-full h-10 rounded-full bg-emerald-700 hover:bg-emerald-800 text-xs font-bold shadow-md">
                            Direct Approve
                          </Button>
                        </form>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PENDING PARCELS */}
        {activeTab === 'parcels' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-black text-slate-900">Land Parcel Verification Queue</h3>
              <span className="text-xs text-muted-foreground">Showing {filteredParcels.length} parcel(s) awaiting verification</span>
            </div>

            {filteredParcels.length === 0 ? (
              <Card className="bg-white/95">
                <CardContent className="p-12 text-center text-muted-foreground">
                  <Landmark className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <div className="text-base font-bold text-slate-700">No Pending Parcel Verification Requests</div>
                  <p className="text-xs mt-1">All land parcels have been reviewed or verified.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {filteredParcels.map((parcel) => (
                  <Card key={parcel.parcel_number} className="bg-white/95 border-slate-200/80 shadow-md rounded-[1.75rem] overflow-hidden hover:shadow-lg transition duration-200">
                    <CardContent className="p-6 text-left space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-xs font-bold uppercase tracking-wider text-emerald-700">Parcel Listing</div>
                          <div className="font-black text-xl text-slate-900 mt-0.5">{parcel.parcel_number}</div>
                          <div className="text-xs font-medium text-slate-500 mt-1 flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                            {parcel.county}, {parcel.constituency}
                          </div>
                        </div>
                        <Badge tone="warning" className="px-3 py-1 text-xs">Unverified Parcel</Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-100">
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Asking Price</span>
                          <strong className="text-emerald-700 font-bold text-sm">KES {money(parcel.displayed_price || parcel.asking_price || '0')}</strong>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Land Size</span>
                          <strong className="text-slate-800 font-semibold">{parcel.land_size || 'N/A'} Acres</strong>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-2">
                        <a 
                          href={parcel.details_url} 
                          className="w-full inline-flex h-11 items-center justify-center rounded-full bg-emerald-700 hover:bg-emerald-800 text-xs font-bold text-white transition shadow-md gap-2"
                        >
                          <span>Open Parcel Verification Dashboard</span>
                          <ArrowRight className="h-4 w-4" />
                        </a>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PENDING TRANSACTIONS */}
        {activeTab === 'transactions' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-black text-slate-900">Active Escrow Transactions</h3>
              <span className="text-xs text-muted-foreground">Showing {filteredTransactions.length} active transaction(s)</span>
            </div>

            {filteredTransactions.length === 0 ? (
              <Card className="bg-white/95">
                <CardContent className="p-12 text-center text-muted-foreground">
                  <WalletCards className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <div className="text-base font-bold text-slate-700">No Active Escrow Transactions Requiring Action</div>
                  <p className="text-xs mt-1">Escrow transactions will appear here when deposits are made.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {filteredTransactions.map((tx) => (
                  <Card key={tx.id} className="bg-white/95 border-slate-200/80 shadow-md rounded-[1.75rem] overflow-hidden">
                    <CardContent className="p-6 text-left space-y-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-xs font-bold uppercase tracking-wider text-emerald-700">Escrow Transaction</div>
                          <div className="font-black text-xl text-slate-900 mt-0.5">{tx.parcel_number}</div>
                          <div className="text-xs text-slate-500 mt-1">ID: {tx.id.slice(0, 8).toUpperCase()}</div>
                        </div>
                        <Badge tone={tx.status === 'Completed' ? 'success' : 'warning'} className="px-3 py-1 text-xs">{tx.status}</Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-3 pt-2 text-xs border-t border-slate-100">
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Escrow Amount</span>
                          <strong className="text-emerald-700 font-bold text-sm">KES {money(tx.amount)}</strong>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-2.5">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Contract Signed</span>
                          <strong className={tx.contract_signed ? 'text-emerald-700 font-bold' : 'text-amber-600 font-bold'}>{tx.contract_signed ? '✓ Signed' : 'Pending'}</strong>
                        </div>
                      </div>

                      <div className="text-xs text-slate-600 space-y-1 bg-slate-50/70 p-3 rounded-xl border border-slate-100">
                        <div>Buyer: <strong className="text-slate-800">{tx.buyer_email}</strong></div>
                        <div>Seller: <strong className="text-slate-800">{tx.seller_email}</strong></div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: JOINT MEMBER REMOVALS */}
        {activeTab === 'removals' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-black text-slate-900">Joint Member Exit Requests</h3>
              <span className="text-xs text-muted-foreground">Showing {filteredRemovals.length} exit request(s)</span>
            </div>

            {filteredRemovals.length === 0 ? (
              <Card className="bg-white/95">
                <CardContent className="p-12 text-center text-muted-foreground">
                  <Gavel className="mx-auto mb-3 h-10 w-10 text-slate-300" />
                  <div className="text-base font-bold text-slate-700">No Pending Joint Member Exit Requests</div>
                  <p className="text-xs mt-1">Admin review is required for consent & compensation verification before joint members exit.</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {filteredRemovals.map((request) => (
                  <Card key={request.id} className="bg-white/95 border-slate-200/80 shadow-md rounded-[1.75rem] overflow-hidden">
                    <CardContent className="p-6 text-left space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
                        <div>
                          <div className="text-xs font-bold uppercase tracking-wider text-emerald-700">Joint Buyer Group</div>
                          <div className="font-black text-xl text-slate-900 mt-0.5">{request.group_name}</div>
                        </div>
                        <Badge tone="warning" className="px-3 py-1 text-xs w-fit">Pending Admin Verdict</Badge>
                      </div>

                      <div className="grid sm:grid-cols-3 gap-4 text-xs">
                        <div className="rounded-xl bg-slate-50 p-3">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Member to Exit</span>
                          <strong className="text-slate-900 text-sm font-bold">{request.member?.full_name || 'N/A'}</strong>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-3">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Consent Verification</span>
                          <strong className={request.consent_confirmed ? 'text-emerald-700 font-bold' : 'text-amber-600 font-bold'}>
                            {request.consent_confirmed ? '✓ Confirmed' : 'Pending Verification'}
                          </strong>
                        </div>
                        <div className="rounded-xl bg-slate-50 p-3">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold tracking-wider">Compensation Status</span>
                          <strong className={request.compensation_confirmed ? 'text-emerald-700 font-bold' : 'text-amber-600 font-bold'}>
                            {request.compensation_confirmed ? `✓ Paid (KES ${request.compensation_amount || 'N/A'})` : 'Pending Check'}
                          </strong>
                        </div>
                      </div>

                      {request.notes ? (
                        <div className="rounded-2xl border border-amber-200/80 bg-amber-50/60 p-4 text-xs text-amber-900">
                          <strong>Request Notes:</strong> {request.notes}
                        </div>
                      ) : null}

                      <div className="flex items-center gap-3 pt-2">
                        <form method="post" action={request.approve_url} className="flex-1">
                          <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                          <Button type="submit" className="w-full h-11 rounded-full bg-emerald-700 hover:bg-emerald-800 text-xs font-bold shadow-md">
                            Approve Member Exit
                          </Button>
                        </form>
                        <form method="post" action={request.reject_url} className="flex-1">
                          <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                          <Button type="submit" variant="outline" className="w-full h-11 rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-bold">
                            Reject Exit Request
                          </Button>
                        </form>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function UserReviewPage() {
  const page = bootstrap.user_review;
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">User review is unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="text-base">{page.reviewed_user.email}</CardTitle>
            <CardDescription>{page.reviewed_user.role}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-2xl bg-muted/60 p-3">ID: <strong>{page.reviewed_user.id_number || 'N/A'}</strong></div>
            <div className="rounded-2xl bg-muted/60 p-3">Phone: <strong>{page.reviewed_user.phone_number || 'N/A'}</strong></div>
            <div className="rounded-2xl bg-muted/60 p-3">KRA: <strong>{page.reviewed_user.kra_pin || 'N/A'}</strong></div>
            <div className="rounded-2xl bg-muted/60 p-3">Joined: <strong>{page.reviewed_user.joined_at || 'N/A'}</strong></div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {page.user_parcels?.length ? (
            <Card className="bg-white/92">
              <CardHeader><CardTitle className="text-base">Seller parcels</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {page.user_parcels.map((parcel) => (
                  <a key={parcel.parcel_number} href={parcel.details_url} className="block rounded-3xl border border-border bg-muted/40 p-4 hover:bg-muted">
                    <div className="font-semibold text-foreground">{parcel.parcel_number}</div>
                    <div className="text-sm text-muted-foreground">{parcel.county}, {parcel.constituency}</div>
                  </a>
                ))}
              </CardContent>
            </Card>
          ) : null}

          {page.user_transactions?.length ? (
            <Card className="bg-white/92">
              <CardHeader><CardTitle className="text-base">Buyer transactions</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                {page.user_transactions.map((tx) => (
                  <div key={tx.id} className="rounded-3xl border border-border bg-muted/40 p-4">
                    <div className="font-semibold text-foreground">{tx.parcel_number}</div>
                    <div className="text-sm text-muted-foreground">{tx.status} · KES {tx.amount}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </AppShell>
  );
}

function ContractPage() {
  const contract = bootstrap.contract;
  const [buyerSignature, setBuyerSignature] = useState('');
  const [sellerSignature, setSellerSignature] = useState('');
  const [adminBuyerSignature, setAdminBuyerSignature] = useState('');
  const [adminSellerSignature, setAdminSellerSignature] = useState('');
  const [jointSignatures, setJointSignatures] = useState<Record<string, string>>({});
  const [documentSignatures, setDocumentSignatures] = useState<Record<string, string>>({});

  if (!contract) {
    return <AppShell {...{
      title: bootstrap.title,
      subtitle: bootstrap.subtitle,
      user: bootstrap.user,
      nav: bootstrap.nav,
      logoutUrl: bootstrap.logout_url,
      csrfToken: bootstrap.csrf_token,
    }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Contract data is unavailable.</CardContent></Card></AppShell>;
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };
  const pendingMembers = contract.joint_breakdown.filter((row) => !row.member.has_signed);
  const canProceedToCheckout = Boolean(contract.checkout_available);

  const fullpageUrl = bootstrap.fullpage_sign_url;
  const shouldOpenBreakout = Boolean(
    fullpageUrl &&
    (contract.current_user_is_buyer || contract.current_user_is_seller) &&
    !contract.contract_agreed &&
    !contract.current_user_is_admin
  );

  useEffect(() => {
    if (shouldOpenBreakout && fullpageUrl) {
      window.location.replace(fullpageUrl);
    }
  }, [shouldOpenBreakout, fullpageUrl]);

  if (shouldOpenBreakout) {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.12),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#ffffff_42%,#eef2f7_100%)] px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
          <Card className="w-full border-border/60 bg-white/95 shadow-2xl">
            <CardContent className="space-y-4 p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <FileText className="h-6 w-6" />
              </div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Opening the signing sheet</h2>
              <p className="mx-auto max-w-lg text-sm leading-7 text-muted-foreground">
                Buyers and sellers now open the dedicated contract breakout page by default so the agreement reads like a clean A4 document before signing.
              </p>
              {fullpageUrl ? (
                <a
                  href={fullpageUrl}
                  className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Continue to signing page
                </a>
              ) : null}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Contract" title="Kenyan Land Transfer Agreement" subtitle={`Property: ${contract.parcel_number}`} actions={bootstrap.actions} />

        {/* Prompt to open clean full-page signing experience */}
        {fullpageUrl && (contract.current_user_is_buyer || contract.current_user_is_seller) && !contract.contract_agreed ? (
          <div className="rounded-[2rem] border border-primary/20 bg-gradient-to-r from-primary/5 to-primary/10 p-6 flex flex-col sm:flex-row items-center gap-4">
            <div className="flex-1">
              <h3 className="text-lg font-bold text-foreground">Sign documents in a dedicated view</h3>
              <p className="text-sm text-muted-foreground mt-1">Open the full-page signing experience for a clean, professional document review and signature flow — away from the dashboard UI.</p>
            </div>
            <a href={fullpageUrl} className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground hover:bg-primary/90 whitespace-nowrap gap-2 shadow-lg">
              <FileText className="h-4 w-4" />Open signing page
            </a>
          </div>
        ) : null}

        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="text-base">
              {contract.contract_agreed ? 'View signed document' : 'Sign document to proceed to checkout'}
            </CardTitle>
            <CardDescription>
              {contract.contract_agreed
                ? 'Open the locked A4 copy of your signed contract before checkout.'
                : 'All required signatures must be completed before checkout is unlocked.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-3">
            {contract.contract_agreed && fullpageUrl ? (
              <a
                href={fullpageUrl}
                className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                View signed document
              </a>
            ) : (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
                Sign documents to proceed to checkout.
              </div>
            )}
            {fullpageUrl ? (
              <a
                href={fullpageUrl}
                className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-5 text-sm font-semibold text-foreground hover:bg-muted"
              >
                Open in A4 document format
              </a>
            ) : null}
            {canProceedToCheckout ? (
              <a
                href={contract.payment_url}
                className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-5 text-sm font-semibold text-foreground hover:bg-muted"
              >
                Continue to checkout
              </a>
            ) : contract.contract_agreed ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700">
                Checkout is not available because this transaction is already {contract.transaction_status.toLowerCase().replace('_', ' ')}.
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
            {contract.is_joint_purchase ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="text-base">Joint ownership structure</CardTitle>
                  <CardDescription>{contract.joint_group_name} · {contract.joint_group_ownership}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {contract.joint_breakdown.map((row) => (
                    <div key={row.member.id} className="flex items-center justify-between gap-3 rounded-3xl border border-border bg-muted/40 p-4 text-sm">
                      <div>
                        <div className="font-semibold text-foreground">{row.member.full_name} {row.member.is_leader ? <Badge tone="outline" className="ml-2">Leader</Badge> : null}</div>
                        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{row.member.id_number} · {row.member.share_percentage}%</div>
                      </div>
                      <div className="font-black text-emerald-700">KES {row.amount}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          <div className="space-y-6">
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Contract signatories</CardTitle>
                <CardDescription>Buyer and seller signatures are required before checkout.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="rounded-2xl bg-muted/60 p-3">Buyer: <strong>{contract.buyer_email}</strong> {contract.buyer_signature_present ? <Badge tone="success" className="ml-2">Signed</Badge> : <Badge tone="warning" className="ml-2">Awaiting</Badge>}</div>
                <div className="rounded-2xl bg-muted/60 p-3">Seller: <strong>{contract.seller_email}</strong> {contract.seller_signature_present ? <Badge tone="success" className="ml-2">Signed</Badge> : <Badge tone="warning" className="ml-2">Awaiting</Badge>}</div>
              </CardContent>
            </Card>

            {contract.current_user_is_admin ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="text-base">Admin dual sign</CardTitle>
                  <CardDescription>QA flow for signing on behalf of both parties.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form method="post" action={contract.sign_url} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={contract.csrf_token} />
                    <input type="hidden" name="admin_dual_sign" value="true" />
                    <input type="hidden" name="buyer_signature_data" value={adminBuyerSignature} />
                    <input type="hidden" name="seller_signature_data" value={adminSellerSignature} />
                    <SignaturePad label="Buyer signature" onChange={setAdminBuyerSignature} />
                    <SignaturePad label="Seller signature" onChange={setAdminSellerSignature} />
                    <Button type="submit" className="w-full rounded-full">Execute dual sign</Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}

            {contract.is_joint_purchase && contract.current_user_is_buyer && pendingMembers.length ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="text-base">Co-buyer signatures</CardTitle>
                  <CardDescription>Capture each co-buyer signature before checkout.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {pendingMembers.map((row) => (
                    <form key={row.member.id} method="post" action={contract.sign_url} className="space-y-3 rounded-3xl border border-border bg-muted/30 p-4">
                      <input type="hidden" name="csrfmiddlewaretoken" value={contract.csrf_token} />
                      <input type="hidden" name="joint_member_id" value={row.member.id} />
                      <input type="hidden" name="joint_signature_data" value={jointSignatures[row.member.id] || ''} />
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="font-semibold text-foreground">{row.member.full_name}</div>
                          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{row.member.id_number} · {row.member.share_percentage}%</div>
                        </div>
                        <Badge tone="outline">{row.amount}</Badge>
                      </div>
                      <SignaturePad label={`Signature for ${row.member.full_name}`} onChange={(value) => setJointSignatures((current) => ({ ...current, [row.member.id]: value }))} />
                      <Button type="submit" className="w-full rounded-full">Save signature</Button>
                    </form>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function CheckoutFullPage() {
  const checkout = bootstrap.checkout;
  const checkoutTransactionId = checkout?.transaction_id || '';
  const checkoutCsrfToken = checkout?.csrf_token || '';
  const checkoutTransactionsUrl = checkout?.transactions_url || '';
  const paystackEnabled = Boolean(checkout?.paystack_enabled);
  const [paymentMode, setPaymentMode] = useState<'m_pesa' | 'joint_bank_account' | 'kcb_bank' | 'paystack'>(checkout?.default_payment_method || 'm_pesa');
  const [memberId, setMemberId] = useState('');
  const [phoneNumber, setPhoneNumber] = useState(checkout?.phone_number || bootstrap.user?.phone_number || '');
  const [amountOverride, setAmountOverride] = useState('');
  const [bankReference, setBankReference] = useState('');
  const [depositorName, setDepositorName] = useState(bootstrap.user?.full_name || bootstrap.user?.email || '');
  const [checkoutRequestId, setCheckoutRequestId] = useState('');
  const [viewState, setViewState] = useState<'form' | 'stk_waiting' | 'bank_waiting' | 'success' | 'failed'>('form');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const pollRef = useRef<number | null>(null);
  const backUrl = bootstrap.back_url || checkout?.transactions_url || '/';
  const failedUrl = checkout?.failed_url || '';

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!checkoutRequestId || !checkoutTransactionId || !checkoutCsrfToken || !checkoutTransactionsUrl) return undefined;
    pollRef.current = window.setInterval(async () => {
      try {
        const response = await fetch(
          `/api/v1/mpesa/check-checkout-status/?checkout_request_id=${encodeURIComponent(checkoutRequestId)}&transaction_id=${encodeURIComponent(checkoutTransactionId)}`,
          { headers: { 'X-CSRFToken': checkoutCsrfToken } }
        );
        const data = await response.json();
        if (data.payment_status === 'completed') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setViewState('success');
          setMessage('Payment confirmed.');
          window.setTimeout(() => {
            window.location.href = checkoutTransactionsUrl;
          }, 2000);
        } else if (data.payment_status === 'failed') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setViewState('failed');
          setMessage(data.message || 'The payment was declined or cancelled.');
        }
      } catch {
        // Keep polling.
      }
    }, 3000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [checkoutTransactionId, checkoutCsrfToken, checkoutTransactionsUrl, checkoutRequestId]);

  if (!checkout) {
    return (
      <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.12),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#ffffff_42%,#eef2f7_100%)] px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
          <Card className="w-full border-border/60 bg-white/95 shadow-2xl">
            <CardContent className="space-y-4 p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                <ReceiptText className="h-6 w-6" />
              </div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Checkout unavailable</h2>
              <p className="mx-auto max-w-lg text-sm leading-7 text-muted-foreground">
                This escrow checkout link could not be loaded. Return to transactions and reopen the purchase flow.
              </p>
              <a
                href={backUrl}
                className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Back to transactions
              </a>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setMessage('');

    try {
      const body = new URLSearchParams();
      body.set('csrfmiddlewaretoken', checkoutCsrfToken);
      body.set('payment_method', paymentMode);
      body.set('phone_number', phoneNumber);
      body.set('member_id', memberId);
      body.set('amount', amountOverride);
      body.set('bank_reference', bankReference);
      body.set('depositor_name', depositorName);

      const response = await fetch(checkout.process_url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': checkoutCsrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body,
      });

      const data = await response.json();
      if (data.status === 'success' || data.status === 'stk_pushed') {
        setViewState('stk_waiting');
        setCheckoutRequestId(data.checkout_request_id || '');
        setMessage(data.message || 'STK push sent.');
        if (!data.checkout_request_id) {
          window.setTimeout(() => {
            window.location.href = checkoutTransactionsUrl;
          }, 2000);
        }
      } else if (data.status === 'paystack_redirect' && data.authorization_url) {
        window.location.href = data.authorization_url;
      } else if (data.status === 'bank_pending') {
        setViewState('bank_waiting');
        setMessage(data.message || 'Joint bank transfer recorded.');
      } else {
        setViewState('failed');
        setMessage(data.message || 'Unable to initiate payment.');
      }
    } catch {
      setViewState('failed');
      setMessage('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const selectedMember = checkout.breakdown.find((row) => row.member_id === memberId);
  const flowTone: 'success' | 'warning' | 'danger' | 'outline' =
    viewState === 'failed'
      ? 'danger'
      : viewState === 'success'
        ? 'success'
        : viewState === 'stk_waiting' || viewState === 'bank_waiting'
          ? 'warning'
          : 'outline';
  const flowLabel =
    viewState === 'failed'
      ? 'Payment failed'
      : viewState === 'success'
        ? 'Payment confirmed'
        : viewState === 'stk_waiting'
          ? 'Awaiting STK approval'
          : viewState === 'bank_waiting'
            ? 'Bank transfer recorded'
            : 'Ready for payment';

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.14),_transparent_32%),linear-gradient(180deg,#f8fafc_0%,#ffffff_42%,#eef2f7_100%)] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[11.5in] flex-col gap-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-2">
            <div className="text-xs font-black uppercase tracking-[0.32em] text-emerald-700">Breakout checkout sheet</div>
            <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">Escrow checkout</h1>
            <p className="max-w-3xl text-sm leading-7 text-muted-foreground">
              Complete the deposit in a clean full-page workflow with the invoice, payment vector, and status shown together without dashboard clutter.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={flowTone}>{flowLabel}</Badge>
              <button
                type="button"
                onClick={() => window.print()}
                className="print:hidden inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
              >
                <Printer className="mr-2 h-4 w-4" />
                Print A4 checkout
              </button>
            <a
              href={backUrl}
              className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
            >
              Back to transactions
            </a>
          </div>
        </div>

        <div className="mx-auto w-full max-w-[10.75in] rounded-[2rem] border border-stone-300 bg-white shadow-[0_35px_90px_rgba(15,23,42,0.12)]">
          <div className="border-b border-stone-200 px-8 py-8 sm:px-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="text-[11px] font-black uppercase tracking-[0.3em] text-emerald-700">Escrow payment record</div>
                <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-900">{checkout.parcel_number}</h2>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
                  Seller {checkout.seller_email}
                  {checkout.buyer_email ? ` | Buyer ${checkout.buyer_email}` : ''}
                  {checkout.is_joint_purchase && checkout.joint_group_name ? ` | ${checkout.joint_group_name}` : ''}
                </p>
              </div>
              <div className="grid gap-3 sm:min-w-[18rem] sm:grid-cols-2">
                <div className="rounded-3xl border border-stone-200 bg-stone-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Transaction</div>
                  <div className="mt-1 text-sm font-black text-slate-900">{checkout.transaction_id.slice(0, 8).toUpperCase()}</div>
                </div>
                <div className="rounded-3xl border border-stone-200 bg-stone-50 p-4">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Total payable</div>
                  <div className="mt-1 text-sm font-black text-emerald-700">{money(checkout.total_payable || checkout.grand_total || checkout.agreed_price)}</div>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-8 px-8 py-8 lg:grid-cols-[0.95fr_1.05fr] sm:px-10">
            <section className="rounded-[1.75rem] border border-stone-200 bg-stone-50/80 p-6 shadow-sm">
              <div className="text-[10px] font-black uppercase tracking-[0.3em] text-emerald-700">Escrow invoice</div>
              <div className="mt-4 grid gap-3 text-sm">
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Parcel</div>
                  <div className="mt-1 font-semibold text-foreground">{checkout.parcel_number}</div>
                </div>
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Seller</div>
                  <div className="mt-1 font-semibold text-foreground">{checkout.seller_email}</div>
                </div>
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Buyer</div>
                  <div className="mt-1 font-semibold text-foreground">{checkout.buyer_email || 'N/A'}</div>
                </div>
                <div className="rounded-2xl bg-white p-4 shadow-sm">
                  <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Land price</div>
                  <div className="mt-1 text-xl font-black tracking-tight text-emerald-700">{money(checkout.land_price || checkout.agreed_price)}</div>
                </div>
              </div>

              <FeeBreakdownPanel checkout={checkout} />

              {checkout.is_joint_purchase ? (
                <div className="mt-6 space-y-4">
                  <div className="text-sm font-semibold text-foreground">Joint split</div>
                  <div className="space-y-3">
                    {checkout.breakdown.map((row) => (
                      <div key={row.member_id} className="flex items-center justify-between gap-3 rounded-3xl border border-stone-200 bg-white p-4 text-sm shadow-sm">
                        <div>
                          <div className="font-semibold text-foreground">{row.member_name}</div>
                          <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                            {row.share_percentage}% {'->'} KES {row.amount}
                          </div>
                        </div>
                        <div className="font-black text-emerald-700">KES {row.amount}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mt-6 rounded-3xl border border-emerald-200 bg-emerald-50/70 p-4 text-sm leading-7 text-emerald-900">
                  Your payment will be deposited into escrow and released only after the legal and transfer steps are completed.
                </div>
              )}

              {checkout.contributions?.length ? (
                <div className="mt-6 rounded-3xl border border-stone-200 bg-white p-4 shadow-sm">
                  <div className="text-sm font-semibold text-foreground">Recorded contributions</div>
                  <div className="mt-3 space-y-2">
                    {checkout.contributions.map((contribution, index) => (
                      <div key={`${contribution.member_name}-${index}`} className="flex items-center justify-between gap-3 rounded-2xl bg-muted/50 px-3 py-3 text-xs text-muted-foreground">
                        <span>{contribution.member_name}</span>
                        <span>{contribution.channel} | {contribution.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>

            <section className="rounded-[1.75rem] border border-stone-200 bg-white p-6 shadow-sm">
              <div className="text-[10px] font-black uppercase tracking-[0.3em] text-emerald-700">Payment instructions</div>

              <div className="mt-4">
                {viewState === 'form' ? (
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Payment option</label>
                      <select
                        value={paymentMode}
                        onChange={(event) => setPaymentMode(event.target.value as 'm_pesa' | 'joint_bank_account' | 'kcb_bank' | 'paystack')}
                        className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                      >
                        <option value="m_pesa">M-Pesa STK prompt</option>
                        <option value="kcb_bank">KCB bank transfer</option>
                        {checkout.is_joint_purchase ? <option value="joint_bank_account">Joint bank account</option> : null}
                        {paystackEnabled ? <option value="paystack">Paystack checkout</option> : <option value="paystack" disabled>Paystack checkout (not configured)</option>}
                      </select>
                    </div>

                    {checkout.is_joint_purchase && paymentMode === 'm_pesa' ? (
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">Pay as member</label>
                        <select
                          value={memberId}
                          onChange={(event) => {
                            setMemberId(event.target.value);
                            const member = checkout.breakdown.find((row) => row.member_id === event.target.value);
                            if (member) {
                              setPhoneNumber(member.phone_number || '');
                              setAmountOverride(member.amount);
                            }
                          }}
                          className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                        >
                          <option value="">Select member</option>
                          {checkout.breakdown.map((row) => (
                            <option key={row.member_id} value={row.member_id}>
                              {row.member_name} ({row.share_percentage}% {'->'} KES {row.amount})
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : null}

                    {selectedMember && checkout.is_joint_purchase && paymentMode === 'm_pesa' ? (
                      <div className="rounded-3xl border border-stone-200 bg-stone-50 p-4 text-sm leading-7 text-slate-700">
                        <div className="text-[10px] font-black uppercase tracking-[0.24em] text-emerald-700">Selected member</div>
                        <div className="mt-2 font-semibold text-slate-900">{selectedMember.member_name}</div>
                        <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          {selectedMember.share_percentage}% | {selectedMember.phone_number || 'No phone number'}
                        </div>
                        <div className="mt-2 font-semibold text-emerald-700">KES {selectedMember.amount}</div>
                      </div>
                    ) : null}

                    {paymentMode === 'm_pesa' ? (
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">M-Pesa phone number</label>
                        <Input value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} placeholder="0712345678 or +254712345678" />
                      </div>
                    ) : null}

                    {paymentMode === 'joint_bank_account' ? (
                      <div className="space-y-4 rounded-3xl border border-stone-200 bg-stone-50/80 p-4">
                        <div className="text-sm font-semibold text-foreground">Joint bank account</div>
                        <div className="grid gap-2 text-sm text-muted-foreground">
                          <div>Bank: {checkout.bank_name || 'Bank not yet configured'}</div>
                          <div>Account name: {checkout.bank_account_name || 'Not set'}</div>
                          <div>Account number: {checkout.bank_account_number || 'Not set'}</div>
                          <div>Branch: {checkout.bank_branch || 'Not set'}</div>
                        </div>
                        {!checkout.joint_bank_ready ? (
                          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                            The joint bank account has not been configured yet.
                          </div>
                        ) : null}
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-foreground">Depositor name</label>
                          <Input value={depositorName} onChange={(event) => setDepositorName(event.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-foreground">Bank transfer reference</label>
                          <Input value={bankReference} onChange={(event) => setBankReference(event.target.value)} placeholder="Transfer reference or slip number" />
                        </div>
                      </div>
                    ) : null}

                    {paymentMode === 'kcb_bank' ? (
                      <div className="space-y-4 rounded-3xl border border-stone-200 bg-stone-50/80 p-4">
                        <div className="text-sm font-semibold text-foreground">KCB escrow transfer</div>
                        <div className="grid gap-2 text-sm text-muted-foreground">
                          <div>Bank: {checkout.escrow_bank_name || 'KCB Bank Kenya'}</div>
                          <div>Account name: {checkout.escrow_bank_account_name || 'Digiland Escrow'}</div>
                          <div>Account number: {checkout.escrow_bank_account_number || 'DIGILAND-ESCROW-001'}</div>
                          <div>Branch: {checkout.escrow_bank_branch || 'Nairobi'}</div>
                        </div>
                        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                          Make the bank transfer from your KCB account, then enter the transfer reference below.
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-foreground">Depositor name</label>
                          <Input value={depositorName} onChange={(event) => setDepositorName(event.target.value)} />
                        </div>
                        <div className="space-y-2">
                          <label className="text-sm font-semibold text-foreground">Bank transfer reference</label>
                          <Input value={bankReference} onChange={(event) => setBankReference(event.target.value)} placeholder="Transfer reference or slip number" />
                        </div>
                      </div>
                    ) : null}

                    {paymentMode === 'paystack' ? (
                      <div className="rounded-3xl border border-stone-200 bg-stone-50/80 p-4 text-sm leading-7 text-slate-700">
                        <div className="text-sm font-semibold text-foreground">Paystack checkout</div>
                        <p className="mt-2 text-muted-foreground">
                          You will be redirected to Paystack to complete the payment securely by card or supported online methods.
                        </p>
                        <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-emerald-900">
                          Payment email: <strong>{checkout.buyer_email || bootstrap.user?.email || 'Not set'}</strong>
                        </div>
                        {!paystackEnabled ? (
                          <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
                            Paystack is not configured for this environment.
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {paymentMode === 'm_pesa' ? (
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">Amount override</label>
                        <Input value={amountOverride} onChange={(event) => setAmountOverride(event.target.value)} placeholder="Leave blank for default amount" />
                      </div>
                    ) : null}

                    <div className="rounded-3xl border border-stone-200 bg-stone-50/80 p-4 text-sm leading-7 text-slate-700">
                      Funds remain in escrow until the transaction is fully authorised and processed.
                    </div>

                    <Button type="submit" className="w-full rounded-full" disabled={loading || (paymentMode === 'paystack' && !paystackEnabled)}>
                      {loading
                        ? 'Processing...'
                        : paymentMode === 'paystack'
                          ? 'Continue to Paystack checkout'
                          : paymentMode === 'joint_bank_account' || paymentMode === 'kcb_bank'
                            ? 'Record bank transfer'
                            : 'Send M-Pesa STK push'}
                    </Button>
                  </form>
                ) : (
                  <div className="space-y-4">
                    {viewState === 'stk_waiting' ? (
                      <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                        <div className="text-xl font-black text-foreground">STK push sent</div>
                        <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                        <p className="mt-3 text-sm text-muted-foreground">Please authorise the payment on your phone. This page will update automatically.</p>
                      </div>
                    ) : null}

                    {viewState === 'bank_waiting' ? (
                      <div className="space-y-4">
                        <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                          <div className="text-xl font-black text-foreground">Bank transfer recorded</div>
                          <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                        </div>
                        <div className="grid gap-3 text-left text-sm">
                          <div className="rounded-2xl bg-muted/60 p-3">Reference: <strong>{bankReference}</strong></div>
                          <div className="rounded-2xl bg-muted/60 p-3">Depositor: <strong>{depositorName}</strong></div>
                        </div>
                      </div>
                    ) : null}

                    {viewState === 'success' ? (
                      <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                        <div className="text-xl font-black text-foreground">Payment confirmed</div>
                        <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                        <div className="mt-4 flex flex-wrap gap-3">
                          <a href={checkout.transactions_url} className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                            View transactions
                          </a>
                        </div>
                      </div>
                    ) : null}

                    {viewState === 'failed' ? (
                      <div className="space-y-4">
                        <div className="rounded-[2rem] border border-rose-200 bg-rose-50/70 p-6">
                          <div className="text-xl font-black text-foreground">Payment failed</div>
                          <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                          <div className="mt-4 flex flex-wrap gap-3">
                            <Button
                              type="button"
                              variant="outline"
                              className="rounded-full"
                              onClick={() => {
                                setViewState('form');
                                setMessage('');
                              }}
                            >
                              Try again
                            </Button>
                            {failedUrl ? (
                              <a href={failedUrl} className="inline-flex h-11 items-center justify-center rounded-full border border-rose-200 bg-white px-5 text-sm font-semibold text-rose-700 hover:bg-rose-50">
                                Open failure details
                              </a>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {viewState !== 'success' ? (
                      <a
                        href={checkout.transactions_url}
                        className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground hover:bg-muted"
                      >
                        View transactions
                      </a>
                    ) : null}
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}

function SellerWithdrawPage() {
  const data = bootstrap.withdraw_data;
  const [amount, setAmount] = React.useState('');
  const [phone, setPhone] = React.useState(data?.phone_number || '');

  if (!data) return <div className="p-8 text-center text-muted-foreground">Withdrawal data not available.</div>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Payouts" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Available to withdraw</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-emerald-700">KES {money(data.available_balance)}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Held in escrow</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-amber-600">KES {money(data.in_escrow)}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Total received</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-foreground">KES {money(data.total_received)}</div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Withdraw to M-Pesa</CardTitle>
            <CardDescription>Enter the amount you wish to withdraw and your M-Pesa registered phone number.</CardDescription>
          </CardHeader>
          <CardContent>
            <form method="post" action={data.action_url} className="space-y-4 max-w-md">
              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Withdrawal amount (KES)</label>
                <input
                  type="number"
                  name="withdraw_amount"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  max={data.available_balance}
                  min="1"
                  step="1"
                  placeholder="e.g. 50000"
                  required
                  className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">M-Pesa phone number</label>
                <input
                  type="tel"
                  name="phone_number"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+254712345678"
                  required
                  className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                />
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Funds will be sent directly to the M-Pesa account registered to the phone number above. Please double-check before submitting.
              </div>
              <Button type="submit" className="w-full rounded-full">Withdraw to M-Pesa</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function EscrowReleasePage() {
  const transactions = bootstrap.escrow_transactions || [];
  const isAdmin = bootstrap.is_admin;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Escrow" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />

        {isAdmin ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <strong>Admin override active.</strong> You can release payments at any time regardless of the verification deadline. Agents can only release after the escrow period ends.
          </div>
        ) : null}

        {transactions.length === 0 ? (
          <Card className="bg-white/92">
            <CardContent className="flex flex-col items-center justify-center p-12 text-center">
              <ShieldCheck className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <div className="text-lg font-bold text-foreground">No pending escrow releases</div>
              <p className="mt-2 text-sm text-muted-foreground">All eligible transactions have been processed or none are currently assigned to you.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {transactions.map((tx: any) => (
              <Card key={tx.id} className="bg-white/92">
                <CardContent className="p-6">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-foreground">{tx.parcel_number}</span>
                        <Badge tone={tx.deadline_passed ? 'success' : 'warning'}>{tx.deadline_passed ? 'Deadline passed' : `${tx.days_remaining} days left`}</Badge>
                        <Badge tone={tx.contract_signed ? 'success' : 'danger'}>{tx.contract_signed ? 'Contract signed' : 'Unsigned'}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">Buyer: {tx.buyer_email} · Seller: {tx.seller_email}</div>
                      <div className="text-sm text-muted-foreground">Created {tx.created_at} · Deadline: {tx.deadline}</div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Amount</div>
                        <div className="text-xl font-black text-foreground">KES {money(tx.amount)}</div>
                      </div>

                      {tx.can_release ? (
                        <form method="post" action={tx.release_url}>
                          <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                          <Button type="submit" className="rounded-full whitespace-nowrap">
                            Release Payment
                          </Button>
                        </form>
                      ) : (
                        <div className="rounded-2xl border border-border bg-muted/50 px-4 py-2 text-xs font-semibold text-muted-foreground">
                          {!tx.contract_signed ? 'Awaiting signatures' : 'Escrow period active'}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-4">
                    <div className="rounded-2xl bg-muted/50 p-3 text-center">
                      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Status</div>
                      <div className="mt-1 text-sm font-semibold text-foreground">{tx.status}</div>
                    </div>
                    <div className="rounded-2xl bg-muted/50 p-3 text-center">
                      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Buyer Sig</div>
                      <div className={`mt-1 text-sm font-semibold ${tx.buyer_signature ? 'text-emerald-700' : 'text-rose-600'}`}>{tx.buyer_signature ? '✓ Signed' : '✗ Pending'}</div>
                    </div>
                    <div className="rounded-2xl bg-muted/50 p-3 text-center">
                      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Seller Sig</div>
                      <div className={`mt-1 text-sm font-semibold ${tx.seller_signature ? 'text-emerald-700' : 'text-rose-600'}`}>{tx.seller_signature ? '✓ Signed' : '✗ Pending'}</div>
                    </div>
                    <div className="rounded-2xl bg-muted/50 p-3 text-center">
                      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Deadline</div>
                      <div className={`mt-1 text-sm font-semibold ${tx.deadline_passed ? 'text-emerald-700' : 'text-amber-600'}`}>{tx.deadline_passed ? 'Elapsed' : `${tx.days_remaining}d remaining`}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function AgentWithdrawPage() {
  const data = bootstrap.withdraw_data;
  const [amount, setAmount] = React.useState('');
  const [phone, setPhone] = React.useState(data?.phone_number || '');

  if (!data) return <div className="p-8 text-center text-muted-foreground">Withdrawal data not available.</div>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Payouts" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Available to withdraw</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-emerald-700">KES {money(data.available_balance)}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Completed Transactions</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{data.completed_transactions_count}</div>
              <div className="mt-1 text-sm text-muted-foreground">Commission Rate: {data.commission_rate}</div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Withdraw to M-Pesa</CardTitle>
            <CardDescription>Enter the commission amount you wish to withdraw and your M-Pesa phone number.</CardDescription>
          </CardHeader>
          <CardContent>
            <form method="post" className="space-y-4 max-w-md">
              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Withdrawal amount (KES)</label>
                <input
                  type="number"
                  name="amount"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  max={data.available_balance}
                  min="1"
                  step="0.01"
                  placeholder="e.g. 5000"
                  required
                  className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">M-Pesa phone number</label>
                <input
                  type="tel"
                  name="phone_number"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+254712345678"
                  required
                  className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
                />
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Funds will be sent directly to the M-Pesa account registered to the phone number above. Please double-check before submitting.
              </div>
              <Button type="submit" className="w-full rounded-full">Withdraw to M-Pesa</Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

function LegalProtectionPanel() {
  const [lskNumber, setLskNumber] = useState('');
  const [lawyerName, setLawyerName] = useState('');
  const [isLskVerified, setIsLskVerified] = useState(false);
  const [lawyerSigned, setLawyerSigned] = useState(false);
  const [lawyerSignature, setLawyerSignature] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [audits, setAudits] = useState({
    pagesChecked: false,
    registrySearch: false,
    physicalProduction: false,
  });

  const handleLskVerify = () => {
    if (!lskNumber || !lawyerName) return;
    setVerifying(true);
    setTimeout(() => {
      setVerifying(false);
      setIsLskVerified(true);
    }, 1200);
  };

  const handleLawyerSign = (sig: string) => {
    setLawyerSignature(sig);
    if (sig) {
      setLawyerSigned(true);
    }
  };

  return (
    <Card className="border-emerald-200 bg-emerald-50/10 shadow-lg rounded-[2rem]">
      <CardHeader>
        <div className="flex items-center gap-2.5">
          <ShieldAlert className="h-6 w-6 text-emerald-600" />
          <CardTitle className="text-xl font-black text-slate-900">Digiland Legal & Deed Protection Guard</CardTitle>
        </div>
        <CardDescription className="text-slate-500 mt-1">
          Mandatory compliance checks to prevent title forgery, loan encumbrances, and real estate scams.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Scam Warning & Checklists */}
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 space-y-3 text-left">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="audit-pages"
                checked={audits.pagesChecked}
                onChange={(e) => setAudits(prev => ({ ...prev, pagesChecked: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
              />
              <label htmlFor="audit-pages" className="text-xs font-bold text-amber-900 uppercase tracking-wide cursor-pointer select-none">
                Page-by-Page Title Audit
              </label>
            </div>
            <p className="text-xs text-amber-800 leading-relaxed">
              ⚠️ <strong>Check Back Pages:</strong> Verify all pages (especially page 3 & 4). Scammers often hide pages that show registered charges (bank loans) or caveats.
            </p>
          </div>

          <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 space-y-3 text-left">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="audit-registry"
                checked={audits.registrySearch}
                onChange={(e) => setAudits(prev => ({ ...prev, registrySearch: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
              />
              <label htmlFor="audit-registry" className="text-xs font-bold text-amber-900 uppercase tracking-wide cursor-pointer select-none">
                Registry Search & Provenance
              </label>
            </div>
            <p className="text-xs text-amber-800 leading-relaxed">
              ⚠️ <strong>Independent Search:</strong> Verify past owners and registry records directly via the official Land Registry, not just the seller's uploaded copy.
            </p>
          </div>

          <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 space-y-3 text-left">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="audit-physical"
                checked={audits.physicalProduction}
                onChange={(e) => setAudits(prev => ({ ...prev, physicalProduction: e.target.checked }))}
                className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
              />
              <label htmlFor="audit-physical" className="text-xs font-bold text-amber-900 uppercase tracking-wide cursor-pointer select-none">
                Physical Production
              </label>
            </div>
            <p className="text-xs text-amber-800 leading-relaxed">
              ⚠️ <strong>Verify Original Deed:</strong> Ensure the physical Title Deed and Green Card are produced and authenticated at the Land Control Board meeting.
            </p>
          </div>
        </div>

        {/* Lawyer LSK Verification */}
        <div className="border-t border-slate-200/80 pt-6">
          <h4 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2 text-left">
            <Scale className="h-4 w-4 text-emerald-600" /> Law Society of Kenya (LSK) Advocate Sign-off
          </h4>

          {!isLskVerified ? (
            <div className="grid gap-4 sm:grid-cols-3 max-w-2xl text-left">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Lawyer Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Advocate Kamau"
                  value={lawyerName}
                  onChange={(e) => setLawyerName(e.target.value)}
                  className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">LSK Admission Number</label>
                <input
                  type="text"
                  placeholder="e.g. P.105/12345/20"
                  value={lskNumber}
                  onChange={(e) => setLskNumber(e.target.value)}
                  className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>
              <div className="flex items-end">
                <Button
                  onClick={handleLskVerify}
                  disabled={!lawyerName || !lskNumber || verifying}
                  className="w-full h-10 rounded-xl"
                >
                  {verifying ? 'Verifying LSK...' : 'Verify LSK Advocate'}
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white">
                    <Scale className="h-5 w-5" />
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-bold text-slate-900">{lawyerName} (LSK Verified)</div>
                    <div className="text-xs text-slate-500">Admission No: {lskNumber} • Status: Active Practicing Advocate</div>
                  </div>
                </div>
                <Badge tone="success" className="px-3 py-1 rounded-full">LSK Authenticated</Badge>
              </div>

              {!lawyerSigned ? (
                <div className="max-w-md pt-2 border-t border-emerald-100/70 text-left">
                  <SignaturePad
                    label="Advocate Cryptographic Sign-off for execution of purchase"
                    onChange={handleLawyerSign}
                    className="border-emerald-200 bg-white"
                  />
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm font-semibold text-emerald-700 pt-1 text-left">
                  <ShieldCheck className="h-5 w-5" />
                  <span>Advocate contract signature recorded and locked.</span>
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ContractFullPage() {
  const contract = bootstrap.contract;
  const [documentSignatures, setDocumentSignatures] = useState<Record<string, string>>({});
  const [buyerSignature, setBuyerSignature] = useState('');
  const [sellerSignature, setSellerSignature] = useState('');
  const [lawyerSignature, setLawyerSignature] = useState('');
  const backUrl = bootstrap.back_url || '/';

  if (!contract) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 flex items-center justify-center p-6">
        <Card className="bg-white/95 max-w-md w-full shadow-2xl">
          <CardContent className="p-8 text-center space-y-4">
            <ShieldCheck className="h-12 w-12 text-muted-foreground/40 mx-auto" />
            <h2 className="text-xl font-bold text-foreground">Invalid signing link</h2>
            <p className="text-sm text-muted-foreground">This contract signing link may have expired or is invalid.</p>
            <a href="/" className="inline-flex h-11 items-center justify-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground hover:bg-primary/90">Return home</a>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="print-document-shell min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100">
      {/* Header bar */}
      <div className="print-document-header sticky top-0 z-50 border-b border-border/50 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[9.25in] items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-black tracking-tight text-foreground">Digiland Contract Signing</div>
              <div className="text-xs text-muted-foreground">Property: {contract.parcel_number}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge tone={contract.contract_agreed ? 'success' : 'warning'}>{contract.contract_agreed ? 'Fully signed' : 'Awaiting signatures'}</Badge>
            <button
              type="button"
              onClick={() => window.print()}
              className="print:hidden inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted"
            >
              <Printer className="mr-1.5 h-4 w-4" />
              Print A4 copy
            </button>
            <a href={backUrl} className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">Back to transactions</a>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[9.25in] space-y-10 px-4 py-10 sm:px-6 print:space-y-0 print:px-0 print:py-0">
        {/* Transaction overview */}
        <div className="print-document-summary grid gap-4 sm:grid-cols-4">
          <div className="rounded-3xl bg-white p-5 shadow-sm border border-border/50">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Parcel</div>
            <div className="mt-1 text-lg font-black text-foreground">{contract.parcel_number}</div>
          </div>
          <div className="rounded-3xl bg-white p-5 shadow-sm border border-border/50">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Agreed Price</div>
            <div className="mt-1 text-lg font-black text-emerald-700">KES {money(contract.agreed_price)}</div>
          </div>
          <div className="rounded-3xl bg-white p-5 shadow-sm border border-border/50">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Buyer</div>
            <div className="mt-1 text-sm font-semibold text-foreground truncate">{contract.buyer_email}</div>
          </div>
          <div className="rounded-3xl bg-white p-5 shadow-sm border border-border/50">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Seller</div>
            <div className="mt-1 text-sm font-semibold text-foreground truncate">{contract.seller_email}</div>
          </div>
        </div>

        {/* Documents — full width, not squeezed */}
        {contract.documents && contract.documents.length > 0 ? (
          <div className="space-y-8">
            <h2 className="print-document-title text-2xl font-black tracking-tight text-foreground">Legal Documents</h2>
            {contract.documents.map((doc: any, index: number) => (
              <div
                key={doc.key}
                className="mx-auto w-full max-w-[8.27in]"
                style={{
                  breakAfter: index < contract.documents.length - 1 ? 'page' : 'auto',
                  pageBreakAfter: index < contract.documents.length - 1 ? 'always' : 'auto',
                }}
              >
                <section
                  className="print-document-sheet overflow-hidden rounded-[2rem] border border-stone-300 bg-white shadow-[0_35px_90px_rgba(15,23,42,0.12)]"
                  style={{ minHeight: '11.69in' }}
                >
                  <div className="border-b border-stone-200 px-8 py-8 sm:px-10">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-sm font-black text-primary">{index + 1}</span>
                          <div>
                            <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-700">Digitally generated contract sheet</div>
                            <h3 className="print-document-title mt-2 text-2xl font-black tracking-tight text-slate-900">{doc.title}</h3>
                          </div>
                        </div>
                        <p className="mt-3 ml-12 max-w-2xl text-sm leading-7 text-slate-600">{doc.description}</p>
                      </div>
                      <Badge tone={doc.required ? 'success' : 'warning'} className="rounded-full px-4 py-2">{doc.required ? 'Required' : 'Optional'}</Badge>
                    </div>
                  </div>

                  <div className="print-document-body px-8 py-8 sm:px-10">
                    <div className="rounded-[1.5rem] border border-stone-200 bg-stone-50/80 p-6 shadow-sm">
                      <div className="space-y-4 text-[11.5pt] leading-8 text-slate-900">
                        {splitParagraphs(doc.content).map((paragraph: string, paragraphIndex: number) => (
                          <p key={`${doc.key}-${paragraphIndex}-${paragraph.slice(0, 24)}`} className="whitespace-pre-wrap">
                            {paragraph}
                          </p>
                        ))}
                      </div>
                    </div>
                  </div>

                  {(contract.current_user_is_buyer || contract.current_user_is_seller) ? (
                    <div className="border-t border-stone-200 px-8 py-8 sm:px-10">
                      <div className="mx-auto max-w-xl">
                        {(contract.current_user_is_buyer && contract.buyer_signature_present) || (contract.current_user_is_seller && contract.seller_signature_present) ? (
                          <div className="rounded-[1.4rem] border border-emerald-200 bg-emerald-50 p-5 text-emerald-800">
                            <ShieldCheck className="mb-2 h-5 w-5" />
                            <div className="text-sm font-bold">Signature locked</div>
                            <div className="mt-1 text-xs leading-6">You have already signed this document. The signature is secured and cannot be changed.</div>
                          </div>
                        ) : (
                          <>
                            <SignaturePad
                              label={`Your signature for "${doc.title}"`}
                              onChange={(val) => setDocumentSignatures(prev => ({ ...prev, [doc.key]: val }))}
                              className="print-signature-pad"
                            />
                            {documentSignatures[doc.key] ? (
                              <div className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald-700">
                                <ShieldCheck className="h-4 w-4" />
                                Signature captured
                              </div>
                            ) : null}
                          </>
                        )}
                      </div>
                    </div>
                  ) : null}
                </section>
              </div>
            ))}
          </div>
        ) : null}

        {/* Signature status and submit */}
        <div className="space-y-6">
          <LegalProtectionPanel />
          <div className="print-document-toolbar grid gap-6 lg:grid-cols-2">
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <CardTitle className="text-left text-base">Signature Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-2xl bg-muted/60 p-3 flex items-center justify-between">
                  <span className="text-sm font-semibold">Buyer: {contract.buyer_email}</span>
                  {contract.buyer_signature_present ? <Badge tone="success">Signed</Badge> : <Badge tone="warning">Awaiting</Badge>}
                </div>
                <div className="rounded-2xl bg-muted/60 p-3 flex items-center justify-between">
                  <span className="text-sm font-semibold">Seller: {contract.seller_email}</span>
                  {contract.seller_signature_present ? <Badge tone="success">Signed</Badge> : <Badge tone="warning">Awaiting</Badge>}
                </div>
                <div className="rounded-2xl bg-muted/60 p-3 flex items-center justify-between">
                  <span className="text-sm font-semibold">Lawyer: {contract.lawyer_name || 'LSK Verified Advocate'}</span>
                  {contract.lawyer_signature_present ? <Badge tone="success">Signed</Badge> : <Badge tone="warning">Awaiting</Badge>}
                </div>
              </CardContent>
            </Card>

            {contract.current_user_role === 'Lawyer' && !contract.lawyer_signature_present ? (
              <Card className="bg-white shadow-sm border-emerald-250 rounded-[2rem] overflow-hidden">
                <CardHeader>
                  <CardTitle className="text-emerald-805 text-left text-base">Execute Advocate Sign-off</CardTitle>
                  <CardDescription className="text-left">Perform LSK verification checks and submit your cryptographic signature.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <form method="post" action={contract.sign_url} className="space-y-4 text-left">
                    <input type="hidden" name="csrfmiddlewaretoken" value={contract.csrf_token} />
                    <input type="hidden" name="lawyer_signature_data" value={lawyerSignature} />
                    
                    <div className="space-y-3 p-4 bg-emerald-50/40 rounded-2xl border border-emerald-100">
                      <div className="flex items-center gap-2">
                        <input type="checkbox" id="audit-pages" required className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer" />
                        <label htmlFor="audit-pages" className="text-xs font-semibold text-slate-800 cursor-pointer select-none">I have audited all pages of the title deed (Cap. 300 compliance).</label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input type="checkbox" id="audit-registry" required className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer" />
                        <label htmlFor="audit-registry" className="text-xs font-semibold text-slate-800 cursor-pointer select-none">I have verified the provenance of registry records at the Land Registry.</label>
                      </div>
                      <div className="flex items-center gap-2">
                        <input type="checkbox" id="audit-physical" required className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer" />
                        <label htmlFor="audit-physical" className="text-xs font-semibold text-slate-800 cursor-pointer select-none">I have verified production of original Title Deed and Green Card.</label>
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Lawyer Full Name</label>
                        <input type="text" name="lawyer_name" required placeholder="Advocate Kamau" className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">LSK Admission Number</label>
                        <input type="text" name="lawyer_lsk_number" required placeholder="P.105/12345/20" className="flex h-10 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20" />
                      </div>
                    </div>

                    <div className="pt-2">
                      <SignaturePad
                        label="Cryptographic signature pad"
                        onChange={(sig) => setLawyerSignature(sig)}
                        className="border-emerald-100 bg-white"
                      />
                    </div>

                    <Button
                      type="submit"
                      className="w-full rounded-full h-12 text-base bg-emerald-700 hover:bg-emerald-800"
                      disabled={!lawyerSignature}
                    >
                      Sign off and execute transfer
                    </Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}

            {(contract.current_user_is_buyer || contract.current_user_is_seller) && !contract.contract_agreed && !((contract.current_user_is_buyer && contract.buyer_signature_present) || (contract.current_user_is_seller && contract.seller_signature_present)) ? (
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <CardTitle className="text-left text-base">Execute Contract</CardTitle>
                  <CardDescription className="text-left">Sign all required documents and submit to complete the legal process.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form method="post" action={contract.sign_url} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={contract.csrf_token} />
                    <input type="hidden" name="signature_data" value={JSON.stringify(documentSignatures)} />
                    <Button
                      type="submit"
                      className="w-full rounded-full h-12 text-base"
                      disabled={contract.documents.some((doc: any) => doc.required && !documentSignatures[doc.key])}
                    >
                      Sign and accept all documents
                    </Button>
                  </form>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>

        {contract.checkout_available ? (
          <div className="print-document-success rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-8 text-center space-y-4">
            <ShieldCheck className="h-12 w-12 text-emerald-600 mx-auto" />
            <h3 className="text-2xl font-black tracking-tight text-foreground">Legal process complete</h3>
            <p className="text-sm leading-7 text-muted-foreground max-w-md mx-auto">The contract has been fully signed. Continue to checkout to choose M-Pesa STK, KCB bank transfer, or Paystack.</p>
            <a href={contract.payment_url} className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-8 text-sm font-semibold text-primary-foreground hover:bg-primary/90 shadow-lg">Continue to checkout</a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AdminWithdrawPage() {
  const data = bootstrap.withdraw_data;
  const [amount, setAmount] = React.useState('');
  const [phone, setPhone] = React.useState(data?.phone_number || '');
  const [method, setMethod] = React.useState<'m_pesa' | 'kcb_bank'>('m_pesa');
  const [bankAccount, setBankAccount] = React.useState('');

  if (!data) return <div className="p-8 text-center text-muted-foreground">Withdrawal data not available.</div>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Platform" title="Platform Withdrawal" subtitle="Transfer platform commission earnings." actions={bootstrap.actions} />

        <div className="grid gap-4 md:grid-cols-3">
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Available to withdraw</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-emerald-700">KES {money(data.available_balance)}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Total Commission (4%)</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-foreground">KES {money(data.total_commission)}</div>
            </CardContent>
          </Card>
          <Card className="bg-white/92">
            <CardContent className="p-6">
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">Total Withdrawn</div>
              <div className="mt-2 text-3xl font-black tracking-tight text-amber-600">KES {money(data.total_withdrawn)}</div>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Withdraw platform earnings</CardTitle>
            <CardDescription>Transfer to M-Pesa or KCB bank account.</CardDescription>
          </CardHeader>
          <CardContent>
            <form method="post" action={data.action_url} className="space-y-4 max-w-md">
              <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
              <input type="hidden" name="withdrawal_method" value={method} />
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Withdrawal method</label>
                <select value={method} onChange={(e) => setMethod(e.target.value as 'm_pesa' | 'kcb_bank')} className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm">
                  <option value="m_pesa">M-Pesa</option>
                  <option value="kcb_bank">KCB Bank Transfer</option>
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Amount (KES)</label>
                <input type="number" name="amount" value={amount} onChange={(e) => setAmount(e.target.value)} max={data.available_balance} min="1" step="0.01" placeholder="e.g. 50000" required className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm" />
              </div>
              {method === 'm_pesa' ? (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground">M-Pesa phone number</label>
                  <input type="tel" name="phone_number" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+254712345678" required className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm" />
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-foreground">KCB account number</label>
                  <input type="text" name="bank_account" value={bankAccount} onChange={(e) => setBankAccount(e.target.value)} placeholder="e.g. 1234567890" required className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm" />
                </div>
              )}
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                Funds will be transferred via {method === 'kcb_bank' ? 'KCB bank' : 'M-Pesa B2C'}. Please verify the details before submitting.
              </div>
              <Button type="submit" className="w-full rounded-full">
                {method === 'kcb_bank' ? 'Transfer via KCB' : 'Withdraw to M-Pesa'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}


function AIKYCPage() {
  const [status, setStatus] = useState<'IDLE' | 'PROCESSING' | 'APPROVED' | 'REJECTED' | 'LOCKED'>('IDLE');
  const [message, setMessage] = useState('Upload your ID and a clear selfie to begin verification.');
  const [idFront, setIdFront] = useState<File | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);

  useEffect(() => {
    if (status !== 'PROCESSING') return;
    
    const interval = setInterval(async () => {
      try {
        const res = await fetch(bootstrap.kyc_status_url);
        const data = await res.json();
        
        if (data.status === 'APPROVED' || data.status === 'REJECTED' || data.status === 'LOCKED') {
          setStatus(data.status);
          setMessage(data.message);
          clearInterval(interval);
          if (data.status === 'APPROVED') {
            setTimeout(() => { window.location.href = '/agent/dashboard/'; }, 2000);
          }
        }
      } catch (e) {
        console.error(e);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [status]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idFront || !selfie) {
      alert("Please upload both documents.");
      return;
    }
    
    setStatus('PROCESSING');
    setMessage('Submitting documents securely...');
    
    const formData = new FormData();
    formData.append('id_front', idFront);
    formData.append('selfie', selfie);
    if (bootstrap.csrf_token) formData.append('csrfmiddlewaretoken', bootstrap.csrf_token);
    
    try {
      const res = await fetch(bootstrap.kyc_submit_url, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        setStatus('REJECTED');
        setMessage(err.error || 'Submission failed');
        return;
      }
      setMessage('Analyzing biometrics and extracting data...');
    } catch (e) {
      setStatus('REJECTED');
      setMessage('Network error during submission.');
    }
  };

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const body = (
    <div className="mx-auto max-w-xl space-y-6">
      <PageHeader kicker="Security" title={bootstrap.title} subtitle={bootstrap.subtitle} />
      
      <Card className="bg-white shadow-sm border border-border/50">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-lg">Identity Verification</CardTitle>
              <CardDescription>We use AI to securely match your ID against your facial biometrics.</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {status === 'PROCESSING' && (
            <div className="py-12 text-center space-y-4">
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
              <div className="font-bold text-lg">{message}</div>
              <p className="text-sm text-muted-foreground">Please wait. Do not close this page.</p>
            </div>
          )}
          
          {(status === 'APPROVED' || status === 'REJECTED' || status === 'LOCKED') && (
            <div className={`rounded-2xl p-6 text-center border ${status === 'APPROVED' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`}>
              <ShieldAlert className="h-10 w-10 mx-auto mb-3" />
              <div className="text-xl font-bold mb-2">{status === 'APPROVED' ? 'Verification Complete' : 'Verification Failed'}</div>
              <div className="text-sm opacity-90">{message}</div>
              {status !== 'APPROVED' && (
                <Button className="mt-6" variant="outline" onClick={() => setStatus('IDLE')}>Try Again</Button>
              )}
            </div>
          )}

          {status === 'IDLE' && (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-3 rounded-2xl border border-dashed border-border/60 bg-muted/20 p-5">
                <label className="block text-sm font-bold text-foreground">1. Government ID (Front)</label>
                <p className="text-xs text-muted-foreground mb-3">Clear, well-lit photo of your National ID or Passport.</p>
                <input 
                  type="file" 
                  accept="image/*" 
                  onChange={(e) => setIdFront(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                />
              </div>
              
              <div className="space-y-3 rounded-2xl border border-dashed border-border/60 bg-muted/20 p-5">
                <label className="block text-sm font-bold text-foreground">2. Selfie Photo</label>
                <p className="text-xs text-muted-foreground mb-3">A clear selfie showing your full face to match against your ID.</p>
                <input 
                  type="file" 
                  accept="image/*" 
                  onChange={(e) => setSelfie(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                />
              </div>
              
              <Button type="submit" className="w-full h-12 rounded-full text-base font-bold shadow-lg">Start Secure Verification</Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );

  if (bootstrap.user) return <AppShell {...shellProps}>{body}</AppShell>;
  return <PublicShell title={bootstrap.title} subtitle={bootstrap.subtitle} nav={bootstrap.nav} user={bootstrap.user}>{body}</PublicShell>;
}


interface RoleSelectionPageProps {
  shellProps: any;
}

function RoleSelectionPage({ shellProps }: RoleSelectionPageProps) {
  const [selectedRole, setSelectedRole] = useState<'buyer' | 'seller' | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (bootstrap.user?.role && bootstrap.user?.is_onboarded) {
      const targetUrl = bootstrap.user.role === 'Buyer' ? '/buyer/dashboard/' : '/seller/dashboard/';
      window.location.href = targetUrl;
    }
  }, []);

  const handleContinue = async () => {
    if (!selectedRole) return;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/onboarding/select-role/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
        body: JSON.stringify({ role: selectedRole }),
      });
      let data: any = {};
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        if (response.ok) {
          data = { redirect_url: selectedRole === 'buyer' ? '/buyer/dashboard/' : '/seller/dashboard/' };
        } else {
          throw new Error('Failed to select role. Please try again.');
        }
      }
      if (!response.ok) {
        throw new Error(data.error || 'Failed to select role. Please try again.');
      }
      // Success: redirect based on selected role
      const redirectUrl = data.redirect_url || (selectedRole === 'buyer' ? '/buyer/dashboard/' : '/seller/dashboard/');
      window.location.href = redirectUrl;
    } catch (err: any) {
      setError(err.message || 'An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PublicShell title="Welcome to Digiland" subtitle="Choose how you'd like to get started" nav={[]} user={bootstrap.user}>
      <div className="flex min-h-[70vh] items-center justify-center px-4 py-12">
        <div className="w-full max-w-4xl space-y-8 text-center">
          {/* Header */}
          <div className="space-y-3">
            <h1 className="text-4xl font-black tracking-tight text-slate-900 sm:text-5xl">
              What brings you here?
            </h1>
            <p className="mx-auto max-w-2xl text-base text-slate-500">
              Choose how you'd like to use the platform. You can change this later if your account supports multiple roles.
            </p>
          </div>

          {/* Cards Grid */}
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            {/* Buyer Card */}
            <div
              onClick={() => setSelectedRole('buyer')}
              className={`group relative cursor-pointer overflow-hidden rounded-[2rem] border-2 bg-white/80 p-8 text-left shadow-sm transition-all duration-300 hover:-translate-y-1 hover:bg-white hover:shadow-xl ${
                selectedRole === 'buyer'
                  ? 'border-emerald-500 ring-2 ring-emerald-500/25 bg-emerald-50/10'
                  : 'border-border/70 hover:border-emerald-300'
              }`}
            >
              <div className="flex flex-col h-full justify-between gap-6">
                <div className="flex items-center justify-between">
                  <div className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300 ${
                    selectedRole === 'buyer' ? 'bg-emerald-500 text-white' : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'
                  }`}>
                    <ShoppingCart className="h-6 w-6" />
                  </div>
                  {selectedRole === 'buyer' && (
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </span>
                  )}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">Buy Land & Secure Escrow</h3>
                  <p className="mt-2 text-sm text-slate-500 leading-relaxed font-normal">
                    Browse verified parcels of land, connect with sellers, and complete secure escrow-protected transactions.
                  </p>
                </div>
              </div>
            </div>

            {/* Seller Card */}
            <div
              onClick={() => setSelectedRole('seller')}
              className={`group relative cursor-pointer overflow-hidden rounded-[2rem] border-2 bg-white/80 p-8 text-left shadow-sm transition-all duration-300 hover:-translate-y-1 hover:bg-white hover:shadow-xl ${
                selectedRole === 'seller'
                  ? 'border-emerald-500 ring-2 ring-emerald-500/25 bg-emerald-50/10'
                  : 'border-border/70 hover:border-emerald-300'
              }`}
            >
              <div className="flex flex-col h-full justify-between gap-6">
                <div className="flex items-center justify-between">
                  <div className={`flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300 ${
                    selectedRole === 'seller' ? 'bg-emerald-500 text-white' : 'bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100'
                  }`}>
                    <Briefcase className="h-6 w-6" />
                  </div>
                  {selectedRole === 'seller' && (
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white">
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </span>
                  )}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-900">List Parcels & Sell Safely</h3>
                  <p className="mt-2 text-sm text-slate-500 leading-relaxed font-normal">
                    List your land parcels, manage offers, track verified buyer activity, and finalize transactions securely.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          {error && (
            <div className="mx-auto max-w-md rounded-2xl border border-rose-100 bg-rose-50/50 p-4 text-sm text-rose-600">
              {error}
            </div>
          )}

          <div className="pt-4 flex flex-col items-center gap-3">
            <Button
              onClick={handleContinue}
              disabled={!selectedRole || loading}
              className="w-full max-w-sm rounded-full py-6 text-base font-semibold shadow-md transition-all duration-200"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Saving choice...
                </span>
              ) : selectedRole ? (
                `Continue as ${selectedRole === 'buyer' ? 'Buyer' : 'Seller'}`
              ) : (
                'Select a role to continue'
              )}
            </Button>
          </div>
        </div>
      </div>
    </PublicShell>
  );
}


function NotFoundPage() {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      window.location.href = `/parcels/?q=${encodeURIComponent(searchQuery.trim())}`;
    } else {
      window.location.href = '/parcels/';
    }
  };

  return (
    <PublicShell title="Page Not Found - Digiland" subtitle="The requested resource could not be found." nav={bootstrap.nav} user={bootstrap.user}>
      <div className="flex min-h-[75vh] items-center justify-center px-4 py-12">
        <div className="relative w-full max-w-3xl space-y-8 overflow-hidden rounded-[2.5rem] border border-emerald-500/20 bg-slate-950 p-8 text-center text-white shadow-2xl backdrop-blur-xl sm:p-12">
          {/* Background Glow */}
          <div className="pointer-events-none absolute -left-24 -top-24 h-64 w-64 rounded-full bg-emerald-500/15 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-24 -right-24 h-64 w-64 rounded-full bg-teal-500/15 blur-3xl" />

          {/* Badge & Icon */}
          <div className="relative z-10 flex flex-col items-center gap-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-3xl border border-emerald-400/30 bg-emerald-400/10 text-emerald-400 shadow-xl shadow-emerald-500/10">
              <Compass className="h-10 w-10 animate-pulse" />
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/10 px-4 py-1 text-xs font-bold uppercase tracking-widest text-rose-400">
              404 — Page Not Found
            </span>
          </div>

          {/* Header text */}
          <div className="relative z-10 space-y-3">
            <h1 className="text-3xl font-black tracking-tight text-white sm:text-5xl">
              Looking for a land parcel or page?
            </h1>
            <p className="mx-auto max-w-lg text-sm font-normal leading-relaxed text-slate-300 sm:text-base">
              The page, document, or parcel listing you are trying to reach doesn't exist, has been moved, or may have been sold.
            </p>
          </div>

          {/* Quick Search Bar */}
          <form onSubmit={handleSearch} className="relative z-10 mx-auto flex max-w-md flex-col gap-2.5 rounded-2xl border border-white/15 bg-white/[0.08] p-2 backdrop-blur-xl sm:flex-row">
            <div className="flex flex-1 items-center gap-2.5 px-3">
              <Search className="h-4 w-4 shrink-0 text-emerald-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search county, ward, or parcel..."
                className="w-full bg-transparent py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
              />
            </div>
            <Button type="submit" className="h-11 rounded-xl bg-emerald-500 px-6 font-bold text-slate-950 hover:bg-emerald-400 transition">
              Search
            </Button>
          </form>

          {/* Primary CTA Buttons */}
          <div className="relative z-10 flex flex-wrap items-center justify-center gap-3 pt-2">
            <a
              href="/parcels/"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full bg-emerald-500 px-6 text-sm font-bold text-slate-950 transition hover:bg-emerald-400 shadow-lg shadow-emerald-500/20"
            >
              <Grid2X2 className="h-4 w-4" /> Browse Marketplace
            </a>
            <a
              href="/"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-6 text-sm font-bold text-white transition hover:bg-white/20"
            >
              <ArrowLeft className="h-4 w-4" /> Return to Home
            </a>
            <a
              href="/support/"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/20 bg-white/10 px-6 text-sm font-bold text-slate-300 transition hover:bg-white/20 hover:text-white"
            >
              <HelpCircle className="h-4 w-4" /> Support
            </a>
          </div>

          {/* Quick Popular Searches */}
          <div className="relative z-10 flex flex-wrap items-center justify-center gap-3 pt-6 border-t border-white/10 text-xs text-slate-400">
            <span>Popular Locations:</span>
            {['Nairobi', 'Nakuru', 'Kiambu', 'Kajiado'].map((tag) => (
              <a
                key={tag}
                href={`/parcels/?q=${encodeURIComponent(tag)}`}
                className="text-slate-300 hover:text-emerald-400 transition underline underline-offset-4 decoration-emerald-500/30"
              >
                {tag}
              </a>
            ))}
          </div>
        </div>
      </div>
    </PublicShell>
  );
}


function ReactAppInner() {
  const { activePartition, setActivePartition, isRoleAllowed } = usePartition();
  const page = bootstrap.page;
  const user = bootstrap.user;
  const userRole = user?.role;

  // Enforce Partition Access Guard if user is logged in with incompatible role
  if (user && userRole && !isRoleAllowed(userRole)) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <PortalBar />
        <PartitionGuard userRole={userRole} currentPartition={activePartition} onSwitchPortal={setActivePartition} />
      </div>
    );
  }

  // Handle staff partition login override
  if (activePartition === 'staff' && (page === 'staff-login' || !user)) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <PortalBar />
        <StaffLoginPage onNavigateToApp={() => setActivePartition('app')} />
      </div>
    );
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  let pageContent: ReactNode = null;

  if (activePartition === 'marketing' || page === 'landing') pageContent = <LandingPage onNavigatePartition={setActivePartition} />;
  else if (page === '404') pageContent = <NotFoundPage />;
  else if (page === 'features') pageContent = <FeaturesPage />;

  else if (page === 'onboarding-select-role') pageContent = <RoleSelectionPage shellProps={shellProps} />;
  else if (page === 'content') pageContent = <ContentPage />;
  else if (page === 'status') pageContent = <StatusPage />;
  else if (page === 'staff-login') pageContent = <StaffLoginPage onNavigateToApp={() => setActivePartition('app')} />;
  else if (page === 'form' || page === 'agent-kyc' || page === 'payment-onboarding') pageContent = <GenericFormPage />;
  else if (page === 'ai-kyc') pageContent = <AIKYCPage />;
  else if (page === 'buyer-choice') pageContent = <AppShell {...shellProps}><BuyerChoicePage /></AppShell>;
  else if (page === 'legal' || page === 'joint-laws') pageContent = <AppShell {...shellProps} activeNav="legal"><LegalPage /></AppShell>;
  else if (page === 'parcel-list') pageContent = <AppShell {...shellProps}><ParcelListPage /></AppShell>;
  else if (page === 'transactions') pageContent = <AppShell {...shellProps}><TransactionsPage /></AppShell>;
  else if (page === 'joint-groups') pageContent = <AppShell {...shellProps}><JointGroupsPage /></AppShell>;
  else if (page === 'joint-group-detail') pageContent = <AppShell {...shellProps}><JointGroupDetailPage /></AppShell>;
  else if (page === 'parcel-detail') pageContent = <ParcelDetailPage />;
  else if (page === 'lawyer-checklist' || page === 'lawyer-tasks') pageContent = <LawyerTasksPage />;
  else if (page === 'commission-detail') pageContent = <CommissionDetailPage />;
  else if (page === 'agent-job-board') pageContent = <AgentJobBoardPage />;
  else if (page === 'agent-commission-steps') pageContent = <AgentCommissionStepsPage />;
  else if (page === 'messages') pageContent = <MessagesPage />;
  else if (page === 'support') pageContent = <SupportPage />;
  else if (page === 'contract') pageContent = <ContractPage />;
  else if (page === 'checkout' || page === 'checkout-fullpage') pageContent = <CheckoutFullPage />;
  else if (page === 'recommendations') pageContent = <RecommendationsPage />;
  else if (page === 'price-prediction') pageContent = <PredictionPage />;
  else if (page === 'task-management') pageContent = <TaskManagementPage />;
  else if (page === 'approvals') pageContent = <ApprovalsPage />;
  else if (page === 'user-review') pageContent = <UserReviewPage />;
  else if (page === 'seller-promotions') pageContent = <AppShell {...shellProps}><SellerPromotionsPage pageData={bootstrap.seller_promotions_page!} csrfToken={bootstrap.csrf_token} /></AppShell>;
  else if (page === 'promotion-tiers') pageContent = <AppShell {...shellProps}><PromotionTiersPage data={bootstrap.promotion_tiers_page!} /></AppShell>;
  else if (page === 'sponsored-ads') pageContent = <AppShell {...shellProps}><SponsoredAdsPage data={bootstrap.sponsored_ads_page!} /></AppShell>;
  else if (page === 'seller-withdraw') pageContent = <SellerWithdrawPage />;
  else if (page === 'escrow-release') pageContent = <EscrowReleasePage />;
  else if (page === 'agent-withdraw') pageContent = <AgentWithdrawPage />;
  else if (page === 'dashboard' || page === 'admin-dashboard' || page === 'agent-dashboard' || page === 'lawyer-dashboard') pageContent = <AppShell {...shellProps}><DashboardPage /></AppShell>;
  else if (page === 'finance') pageContent = <AppShell {...shellProps}><AdminFinancePage /></AppShell>;
  else if (page === 'contract-fullpage') pageContent = <ContractFullPage />;
  else if (page === 'admin-withdraw') pageContent = <AdminWithdrawPage />;
  else if (page === 'message-thread') pageContent = <MessageThreadPage />;
  else {
    pageContent = (
      <AppShell {...shellProps}>
        <div className="space-y-6">
          <PageHeader kicker="Digiland" title={bootstrap.title} subtitle={bootstrap.subtitle} badge={bootstrap.notice} actions={bootstrap.actions} />
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle>Page not yet migrated</CardTitle>
              <CardDescription>This screen is still using the Django template route. The React shell is ready for it, but the view has not been switched over yet.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>We have already moved the main dashboard, parcel list, transactions, legal pages, and joint-group screens into the new UI layer.</p>
              <div className="flex flex-wrap gap-3">
                <Button className="rounded-full" onClick={() => window.location.reload()}>Refresh</Button>
                <Button variant="outline" className="rounded-full" onClick={() => (window.location.href = '/')}>Return home</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </AppShell>
    );
  }

  return (
    <>
      <PortalBar />
      {pageContent}
      <PopupAdManager popupAds={bootstrap.popup_ads} csrfToken={bootstrap.csrf_token} />
    </>
  );
}

function ReactApp() {
  return (
    <PartitionProvider>
      <ReactAppInner />
    </PartitionProvider>
  );
}

function AdminFinancePage() {
  const finance = bootstrap.finance_dashboard;
  const [pinVerified, setPinVerified] = useState(!!bootstrap.finance_pin_verified);
  const [pin, setPin] = useState('');
  const [pinError, setPinError] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const verifyUrl = bootstrap.finance_verify_url || '';
  const withdrawUrl = bootstrap.admin_withdraw_url || '';

  // PIN gate overlay
  if (!pinVerified) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center text-center">
        <div className="w-full max-w-[320px] mx-auto space-y-6">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-amber-700">
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
          </div>
          <h2 className="text-xl font-black tracking-tight text-foreground">Finance Dashboard Locked</h2>
          <p className="text-sm text-muted-foreground">Enter the admin finance PIN to access the financial data.</p>
          <form onSubmit={async (e) => {
            e.preventDefault();
            setPinLoading(true);
            setPinError('');
            try {
              const body = new URLSearchParams();
              body.set('csrfmiddlewaretoken', bootstrap.csrf_token || '');
              body.set('finance_pin', pin);
              const resp = await fetch(verifyUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': bootstrap.csrf_token || '', 'X-Requested-With': 'XMLHttpRequest' },
                body,
              });
              const data = await resp.json();
              if (data.status === 'success') {
                setPinVerified(true);
              } else {
                setPinError(data.message || 'Incorrect PIN.');
              }
            } catch {
              setPinError('Network error. Please try again.');
            } finally {
              setPinLoading(false);
            }
          }} className="space-y-4">
            <input
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="Enter finance PIN"
              required
              className="flex h-12 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-center text-lg tracking-[0.3em] shadow-sm"
              autoFocus
            />
            {pinError ? <div className="rounded-2xl bg-rose-50 border border-rose-200 p-3 text-sm text-rose-700">{pinError}</div> : null}
            <Button type="submit" className="w-full rounded-full" disabled={pinLoading}>{pinLoading ? 'Verifying...' : 'Unlock Finance Dashboard'}</Button>
          </form>
        </div>
      </div>
    );
  }

  if (!finance) {
    return (
      <div className="flex h-[50vh] flex-col items-center justify-center text-center">
        <div className="mb-4 rounded-full bg-amber-100 p-3 text-amber-700">
          <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
        </div>
        <h2 className="text-xl font-bold text-foreground">Finance Data Missing</h2>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">The backend did not provide the finance dashboard data payload.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Withdraw action banner */}
      {withdrawUrl ? (
        <div className="rounded-[2rem] border border-emerald-200 bg-gradient-to-r from-emerald-50/70 to-emerald-100/50 p-5 flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1">
            <h3 className="text-base font-bold text-foreground">Withdraw platform earnings</h3>
            <p className="text-sm text-muted-foreground">Transfer available commission to M-Pesa or KCB bank account.</p>
          </div>
          <a href={withdrawUrl} className="inline-flex h-11 items-center justify-center rounded-full bg-emerald-600 px-6 text-sm font-semibold text-white hover:bg-emerald-700 whitespace-nowrap gap-2 shadow">
            <WalletCards className="h-4 w-4" />Withdraw funds
          </a>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="bg-white/92">
          <CardContent className="p-6">
            <div className="text-sm font-semibold text-muted-foreground">Total Volume</div>
            <div className="mt-2 text-3xl font-bold text-foreground">KES {finance.total_volume.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-6">
            <div className="text-sm font-semibold text-muted-foreground">Platform Commission (4%)</div>
            <div className="mt-2 text-3xl font-bold text-emerald-600">KES {finance.platform_commission.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-6">
            <div className="text-sm font-semibold text-muted-foreground">Estimated Tax Obligation</div>
            <div className="mt-2 text-3xl font-bold text-amber-600">KES {finance.total_tax.toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-6">
            <div className="text-sm font-semibold text-muted-foreground">Reversed / Escrow Refunded</div>
            <div className="mt-2 text-3xl font-bold text-rose-600">KES {finance.reversed_volume.toLocaleString()}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 bg-white/92">
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
            <CardDescription>Latest completed escrow settlements.</CardDescription>
          </CardHeader>
          <CardContent>
            {finance.recent_transactions.length ? (
              <div className="space-y-4">
                {finance.recent_transactions.map((tx) => (
                  <div key={tx.id} className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-border bg-white p-4">
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-foreground">Parcel {tx.parcel_number}</div>
                        <div className="text-xs text-muted-foreground">{tx.updated_at}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold text-foreground">KES {parseFloat(tx.amount).toLocaleString()}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-700">Completed</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No recent completed transactions.</div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle>Transaction Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                  <span className="text-sm font-semibold text-muted-foreground">Completed</span>
                  <span className="font-bold text-foreground">{finance.completed_count}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                  <span className="text-sm font-semibold text-muted-foreground">Pending</span>
                  <span className="font-bold text-foreground">{finance.pending_count}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                  <span className="text-sm font-semibold text-muted-foreground">Reversed</span>
                  <span className="font-bold text-foreground">{finance.reversed_count}</span>
                </div>
                <div className="mt-4 border-t border-border/70 pt-3 flex items-center justify-between">
                  <span className="text-sm font-bold text-foreground">Total</span>
                  <span className="font-black text-foreground">{finance.total_transactions}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle>Monthly Volume</CardTitle>
            </CardHeader>
            <CardContent>
              {finance.monthly.length ? (
                <div className="space-y-3">
                  {finance.monthly.map((m, idx) => (
                    <div key={idx} className="flex items-center justify-between rounded-2xl border border-border p-3">
                      <div>
                        <div className="text-sm font-semibold text-foreground">{m.month}</div>
                        <div className="text-xs text-muted-foreground">{m.count} txns</div>
                      </div>
                      <div className="font-bold text-foreground">KES {m.volume.toLocaleString()}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-muted-foreground text-center">No monthly data available.</div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function LawyerTasksPage() {
  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };
  const tasks = bootstrap.tasks || [];
  const completedCount = bootstrap.completed_count || 0;
  const totalCount = bootstrap.total_count || tasks.length || 7;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <AppShell {...shellProps}>
      <div className="mx-auto max-w-5xl space-y-6">
        <PageHeader
          kicker="Conveyancing Completion"
          title={bootstrap.title || "Post-Signing Conveyancing Tasks"}
          subtitle={bootstrap.subtitle || "Mandatory Advocate Statutory Completion Checklist (Kenyan Land Law)"}
          actions={bootstrap.actions}
        />

        <Card className="bg-white/92 border-emerald-200 shadow-sm">
          <CardContent className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-foreground">Completion Progress</h3>
                <p className="text-xs text-muted-foreground">{completedCount} of {totalCount} mandatory conveyancing milestones verified</p>
              </div>
              <div className="text-2xl font-black text-emerald-700">{progressPercent}%</div>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-emerald-100">
              <div className="h-full bg-emerald-600 transition-all duration-500" style={{ width: `${progressPercent}%` }} />
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {tasks.map((task: any) => (
            <Card key={task.task_key} className={cn("bg-white/92 transition-all shadow-sm", task.is_completed ? "border-emerald-300 bg-emerald-50/40" : "border-border")}>
              <CardContent className="p-6">
                <form method="post" action={`/transactions/${bootstrap.transaction_id}/lawyer-tasks/`} className="space-y-4">
                  <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token} />
                  <input type="hidden" name="task_key" value={task.task_key} />
                  
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold", task.is_completed ? "bg-emerald-600 text-white" : "bg-muted text-muted-foreground")}>
                        {task.is_completed ? "✓" : "!"}
                      </div>
                      <div>
                        <h4 className="text-base font-bold text-foreground">{task.task_name}</h4>
                        <p className="text-xs text-muted-foreground">Advocate: {task.lawyer_email} {task.completed_at ? `· Verified on ${task.completed_at}` : ""}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Badge tone={task.is_completed ? "success" : "warning"}>
                        {task.is_completed ? "Verified & Completed" : "Pending"}
                      </Badge>
                    </div>
                  </div>

                  {bootstrap.can_edit ? (
                    <div className="grid gap-3 pt-3 border-t border-border/60 sm:grid-cols-2">
                      <div>
                        <label className="text-xs font-semibold text-foreground">Reference / Registration No.</label>
                        <input
                          type="text"
                          name="reference_number"
                          defaultValue={task.reference_number}
                          placeholder="e.g. LCB/2026/0491 or KRA-STAMP-8912"
                          className="mt-1 flex h-9 w-full rounded-xl border border-input bg-white px-3 text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-xs font-semibold text-foreground">Advocate Completion Notes</label>
                        <input
                          type="text"
                          name="notes"
                          defaultValue={task.notes}
                          placeholder="Add confirmation notes..."
                          className="mt-1 flex h-9 w-full rounded-xl border border-input bg-white px-3 text-xs"
                        />
                      </div>
                      <div className="sm:col-span-2 flex justify-end gap-2 pt-2">
                        {task.is_completed ? (
                          <Button type="submit" name="is_completed" value="false" variant="outline" className="h-8 rounded-full text-xs">
                            Mark Pending
                          </Button>
                        ) : (
                          <Button type="submit" name="is_completed" value="true" className="h-8 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-xs">
                            Mark Completed & Save
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : task.reference_number || task.notes ? (
                    <div className="pt-2 text-xs text-muted-foreground space-y-1">
                      {task.reference_number ? <div><strong>Reference:</strong> {task.reference_number}</div> : null}
                      {task.notes ? <div><strong>Notes:</strong> {task.notes}</div> : null}
                    </div>
                  ) : null}
                </form>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

function MessageThreadPage() {
  const page = bootstrap.message_thread;
  if (!page) return null;
  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };
  
  const thread = page.thread;

  return (
    <AppShell {...shellProps}>
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <a href="/messages/" className="inline-flex items-center text-sm font-semibold text-emerald-700 transition-opacity hover:opacity-80">
            <ArrowRight className="mr-2 h-4 w-4 rotate-180" /> Back to inbox
          </a>
          {page.clear_action ? (
            <Button
              variant="danger"
              className="h-9 rounded-full px-5 text-xs"
              onClick={async () => {
                if (window.confirm('Are you sure you want to permanently clear this entire conversation?')) {
                  try {
                    const body = new URLSearchParams();
                    body.set('csrfmiddlewaretoken', page.csrf_token);
                    const resp = await fetch(page.clear_action, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                      body,
                    });
                    if (resp.ok) {
                      window.location.href = '/messages/';
                    } else {
                      alert('Failed to clear thread. Please try again.');
                    }
                  } catch (e) {
                    alert('Network error. Please try again.');
                  }
                }
              }}
            >
              Clear Thread
            </Button>
          ) : null}
        </div>

        <PageHeader 
          kicker="Conversation" 
          title={thread.partner.email} 
          subtitle={thread.partner.role} 
        />
        
        <Card className="bg-white/92">
          <CardContent className="space-y-4 p-6">
            {thread.messages.length === 0 ? (
              <div className="text-center text-sm text-muted-foreground py-8">No messages in this thread.</div>
            ) : (
              [...thread.messages].reverse().map((message: any) => (
                <div key={message.id} className={message.is_self ? 'ml-auto max-w-[85%] rounded-3xl bg-primary px-5 py-4 text-sm text-primary-foreground' : 'max-w-[85%] rounded-3xl bg-muted/60 px-5 py-4 text-sm text-foreground'}>
                  <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.2em] opacity-70">{message.is_self ? 'You' : message.sender_email} · {message.timestamp}</div>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
        
        <Card className="bg-white/92">
          <CardContent className="p-6">
            <form method="post" action={page.compose_action} className="space-y-4">
              <input type="hidden" name="csrfmiddlewaretoken" value={page.csrf_token} />
              <input type="hidden" name="recipient_type" value="single" />
              <input type="hidden" name="receiver_email" value={thread.partner.email} />
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Reply</label>
                <Textarea name="content" rows={4} placeholder="Type your reply here..." className="bg-white/95" required />
              </div>
              <div className="flex justify-end">
                <Button type="submit" className="rounded-full px-8">Send Message</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}

export default ReactApp;
