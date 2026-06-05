import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, ArrowDown, Banknote, BarChart3, Camera, CheckCircle2, CircleCheckBig, Clock3, ExternalLink, Eye, FileSignature, FileText, Gavel, Heart, Landmark, Lock, Mail, MapPin, MessageSquare, Printer, ReceiptText, Search, ShieldAlert, ShieldCheck, Sparkles, Ticket, Upload, UserCheck, Users, WalletCards, type LucideIcon } from 'lucide-react';
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
import type { ActionLink, CheckoutData, ParcelSummary, RecommendationParcelSummary } from './types.js';
import { cn } from './lib/utils.js';
import { SellerPromotionsPage } from './pages/seller-promotions-page.js';
import { PromotionTiersPage } from './pages/promotion-tiers-page.js';
import { SponsoredAdsPage } from './pages/sponsored-ads-page.js';
import { PaymentMethodSelector } from './components/checkout/payment-method-selector.js';
import { HeroShowcase } from './components/landing/hero-showcase.js';

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

  return (
    <Card className={cn('overflow-hidden bg-white/92', parcel.is_promoted ? 'border-amber-200 shadow-soft' : '', className)}>
      <div className="relative aspect-[16/10] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50">
        {parcel.image_url ? (
          <img src={parcel.image_url} alt={parcel.parcel_number} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">
            No image
          </div>
        )}
        <div className="absolute left-3 top-3 flex max-w-[75%] flex-wrap gap-2">
          {parcel.is_promoted ? <Badge tone="success">Featured</Badge> : null}
          {parcel.promotion_tier ? <Badge tone={promotionTone}>{parcel.promotion_tier}</Badge> : null}
          {showMatchScore && parcel.match_score != null ? <Badge tone="success">{Math.round(parcel.match_score)}% match</Badge> : null}
        </div>
        <div className="absolute right-3 top-3">
          <StatusBadge label={parcel.status_badge || parcel.verification_status} tone={listingTone} />
        </div>
      </div>
      <CardHeader className={cn('pb-3', compact ? 'pb-2' : '')}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className={cn('text-base', compact ? 'text-sm' : '')}>{parcel.parcel_number}</CardTitle>
            <CardDescription>
              {parcel.county}, {parcel.constituency}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className={cn('space-y-4', compact ? 'p-4 pt-0' : '')}>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-2xl bg-muted/60 p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Land use</div>
            <div className="mt-1 font-semibold text-foreground">{parcel.land_use_type}</div>
          </div>
          <div className="rounded-2xl bg-muted/60 p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Size</div>
            <div className="mt-1 font-semibold text-foreground">{parcel.land_size}</div>
          </div>
        </div>

        {price ? (
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 p-3">
            <div className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700">Price</div>
            <div className="mt-1 text-lg font-black tracking-tight text-foreground">{money(price)}</div>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {parcel.ward ? <span>{parcel.ward}</span> : null}
          {parcel.displayed_price || parcel.asking_price ? <span>Transparent pricing</span> : null}
        </div>

        <a
          href={parcel.details_url}
          className="inline-flex h-11 w-full items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {parcel.manage_label || ctaLabel}
          <ArrowRight className="ml-2 h-4 w-4" />
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
          <div className="text-lg font-bold text-foreground">No parcels found</div>
          <p className="mt-2 text-sm text-muted-foreground">Listings will appear here once parcels are uploaded and reviewed.</p>
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
  const isAdmin = role === 'Admin';
  const subtitle = role === 'Admin' || role === 'Agent'
    ? 'Monitor parcels, approvals, transactions, and messages from one workspace.'
    : role === 'Seller'
      ? 'Manage your listings, review buyer activity, and track escrow status.'
      : 'Browse land, review contracts, and manage joint purchase activity from one clean workspace.';

  const pendingAgents = bootstrap.pending_agent_applications || [];
  const individualBuyers = bootstrap.individual_buyers || [];

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Workspace"
        title={bootstrap.title}
        subtitle={subtitle}
        badge={bootstrap.notice}
        actions={bootstrap.actions}
      />
      <StatGrid />

      <Card className="bg-white/92">
        <CardHeader>
          <PanelTitle title="Recent transactions" subtitle="Latest escrow movement in your account." action={<a href="/transactions/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">Open register</a>} />
        </CardHeader>
        <CardContent className="p-0">
          <TransactionTable />
        </CardContent>
      </Card>

      {isAdmin && pendingAgents.length > 0 ? (
        <Card className="bg-white/92">
          <CardHeader>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                <ShieldAlert className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">Agent Applications</CardTitle>
                <CardDescription>{pendingAgents.length} pending KYC review{pendingAgents.length !== 1 ? 's' : ''}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {pendingAgents.map((agent: any) => (
              <div key={agent.id} className="rounded-3xl border border-border bg-muted/30 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-bold text-foreground">{agent.email}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      ID: {agent.id_number || '—'} · KRA: {agent.kra_pin || '—'} · Phone: {agent.phone_number || '—'}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">Joined {agent.joined_at || '—'}</div>
                  </div>
                  <Badge tone={agent.kyc?.submitted ? 'warning' : 'danger'}>
                    {agent.kyc?.status || 'No KYC'}
                  </Badge>
                </div>

                {agent.kyc?.submitted ? (
                  <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {agent.kyc.id_photo_url ? (
                      <a href={agent.kyc.id_photo_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted">
                        <FileText className="h-4 w-4 text-emerald-700" /> ID Photo
                      </a>
                    ) : null}
                    {agent.kyc.resume_url ? (
                      <a href={agent.kyc.resume_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted">
                        <FileText className="h-4 w-4 text-blue-700" /> Resume / CV
                      </a>
                    ) : null}
                    {agent.kyc.certificate_url ? (
                      <a href={agent.kyc.certificate_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted">
                        <FileText className="h-4 w-4 text-purple-700" /> Good Conduct
                      </a>
                    ) : null}
                    {agent.kyc.practicing_cert_url ? (
                      <a href={agent.kyc.practicing_cert_url} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-3 text-xs font-semibold text-foreground hover:bg-muted">
                        <FileText className="h-4 w-4 text-amber-700" /> Practicing Cert
                      </a>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-3 rounded-2xl bg-rose-50 p-3 text-xs text-rose-700">KYC documents have not been submitted yet.</div>
                )}

                <div className="mt-4 flex flex-wrap gap-2">
                  {agent.kyc?.submitted ? (
                    <form method="post" action={agent.approve_url}>
                      <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                      <Button type="submit" className="rounded-full bg-emerald-700 hover:bg-emerald-800">Approve Agent</Button>
                    </form>
                  ) : null}
                  <form method="post" action={agent.reject_url}>
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <Button type="submit" variant="outline" className="rounded-full border-rose-300 text-rose-700 hover:bg-rose-50">Reject</Button>
                  </form>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {isAdmin && individualBuyers.length > 0 ? (
        <Card className="bg-white/92">
          <CardHeader>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
                <Users className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">Buyer Account Type Upgrades</CardTitle>
                <CardDescription>Promote individual buyers to joint account owners on verified admin request.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {individualBuyers.map((buyer: any) => (
              <div key={buyer.id} className="rounded-3xl border border-border bg-muted/30 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-bold text-foreground">{buyer.email}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Current account type: Individual
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">Phone: {buyer.phone_number || '—'} · Joined {buyer.joined_at || '—'}</div>
                  </div>
                  <form method="post" action={buyer.promote_to_joint_url}>
                    <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                    <Button type="submit" className="rounded-full bg-emerald-700 hover:bg-emerald-800">
                      Promote to Joint
                    </Button>
                  </form>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card className="bg-white/92">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4 text-emerald-700" />Key actions</CardTitle>
          <CardDescription>Shortcuts to the most common workflows.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {(bootstrap.actions || []).map((action) => (
            <a key={action.href} href={action.href} className="flex items-center justify-between rounded-2xl border border-border bg-muted/45 px-4 py-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted">
              <span>{action.label}</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </a>
          ))}
        </CardContent>
      </Card>
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

function LandingPage() {
  const parcels = bootstrap.parcels || [];
  const stats = bootstrap.stats || [];

  return (
    <PublicShell
      title={bootstrap.title}
      subtitle={bootstrap.subtitle}
      nav={bootstrap.nav}
      user={bootstrap.user}
      actions={bootstrap.actions}
    >
      <div className="space-y-8">
        <HeroShowcase
          notice={bootstrap.notice}
          stats={stats}
          csrfToken={bootstrap.csrf_token}
          isAuthenticated={Boolean(bootstrap.user)}
        />

        {/* ── HOW IT WORKS SECTION ── */}
        <section id="how-it-works" className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">How it works</div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Secure land transactions, step by step</h2>
            </div>
            <a href="/escrow-acts/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">Read the legal checklist</a>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {[
              {
                title: 'List and verify',
                body: 'Sellers upload parcel details and compliance documents. Licensed agents review the listing before it goes live. Every property is verified against official land records.',
              },
              {
                title: 'Sign the contract',
                body: 'Buyer and seller sign the land transfer agreement. Joint buyers can capture member signatures as well. Contracts are legally binding and digitally secured.',
              },
              {
                title: 'Send payment',
                body: 'Once the contract is complete, the buyer sees checkout and receives an M-Pesa STK prompt or joint bank instructions. Funds are held in escrow until ownership is confirmed.',
              },
            ].map((step, index) => (
              <Card key={step.title} className="bg-white/92">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Badge tone="outline">0{index + 1}</Badge>
                    <Sparkles className="h-4 w-4 text-emerald-700" />
                  </div>
                  <CardTitle className="text-lg">{step.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm leading-7 text-foreground">{step.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {parcels.length ? (
          <section className="space-y-4">
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">Marketplace</div>
                <h2 className="text-2xl font-black tracking-tight text-foreground">Recent verified parcels</h2>
              </div>
              <a href="/parcels/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">View all parcels</a>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {parcels.slice(0, 6).map((parcel) => (
                <ListingCard key={parcel.parcel_number} parcel={parcel} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PublicShell>
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
                  <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Purchase readiness</CardTitle>
                  <CardDescription>Choose the purchase mode before initiating escrow.</CardDescription>
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

                    <Button type="submit" className="w-full rounded-full">Initiate secure escrow</Button>
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

function MessagesPage() {
  const page = bootstrap.messages_page;
  if (!page) {
    return <AppShell {...{
      title: bootstrap.title,
      subtitle: bootstrap.subtitle,
      user: bootstrap.user,
      nav: bootstrap.nav,
      logoutUrl: bootstrap.logout_url,
      csrfToken: bootstrap.csrf_token,
    }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Messages are unavailable.</CardContent></Card></AppShell>;
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  const renderThread = (thread: NonNullable<typeof page.threads>[number]) => {
    const latestMessage = thread.messages[0];
    const previewText = latestMessage?.content.length > 60 ? latestMessage.content.slice(0, 60) + '...' : latestMessage?.content;

    return (
      <a href={thread.url} key={thread.partner.email} className="block transition-transform hover:-translate-y-1">
        <Card className="bg-white/92 transition-colors hover:border-emerald-200 hover:bg-white">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base text-emerald-800">{thread.partner.email}</CardTitle>
                <CardDescription>{thread.partner.role}</CardDescription>
              </div>
              <Badge tone="outline">{thread.count} msgs</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {latestMessage ? (
              <div className="text-sm text-muted-foreground italic">
                <span className="font-semibold not-italic">{latestMessage.is_self ? 'You' : thread.partner.email}:</span> {previewText}
              </div>
            ) : null}
            <div className="mt-4 flex items-center text-xs font-semibold text-emerald-600">
              View full conversation <ArrowRight className="ml-1 h-3 w-3" />
            </div>
          </CardContent>
        </Card>
      </a>
    );
  };

  const composeForm = (
    <form method="post" action={page.compose_action} className="space-y-4">
      <input type="hidden" name="csrfmiddlewaretoken" value={page.csrf_token} />
      {bootstrap.user?.role === 'Admin' || bootstrap.user?.role === 'Agent' ? (
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">Recipient type</label>
            <select
              name="recipient_type"
              className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm"
              onChange={(e) => {
                const el = document.getElementById('receiver_email_container');
                if (el) el.style.display = e.target.value === 'single' ? 'block' : 'none';
                const input = document.getElementById('receiver_email_input') as HTMLInputElement;
                if (input) input.required = e.target.value === 'single';
              }}
            >
              <option value="single">Single user</option>
              <option value="all">All users</option>
              <option value="buyers">All buyers</option>
              <option value="sellers">All sellers</option>
              <option value="agents">All agents</option>
            </select>
          </div>
          <div className="space-y-2" id="receiver_email_container">
            <label className="text-sm font-semibold text-foreground">Recipient email</label>
            <Input id="receiver_email_input" name="receiver_email" type="email" placeholder="user@example.com" required />
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <label className="text-sm font-semibold text-foreground">Send to</label>
          <select name="receiver_email" className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm" required>
            <option value="">Select a recipient</option>
            {page.allowed_recipients.map((recipient) => (
              <option key={recipient.email} value={recipient.email}>
                {recipient.email} ({recipient.role})
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-foreground">Message</label>
        <Textarea name="content" rows={5} placeholder="Write your message here" required />
      </div>
      <Button type="submit" className="w-full rounded-full">Send message</Button>
    </form>
  );

  return (
    <AppShell {...shellProps}>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <PageHeader kicker="Messages" title={bootstrap.title} subtitle={bootstrap.subtitle} />
          {page.mode === 'single' ? (
            <div className="space-y-4">
              {page.threads.length ? page.threads.map(renderThread) : <Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">No messages in your inbox yet.</CardContent></Card>}
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                <Card className="bg-white/92"><CardHeader><CardTitle className="text-base">Buyer threads</CardTitle></CardHeader></Card>
                {page.buyer_threads?.length ? page.buyer_threads.map(renderThread) : <Card className="bg-white/92"><CardContent className="p-6 text-sm text-muted-foreground">No buyer threads yet.</CardContent></Card>}
              </div>
              <div className="space-y-4">
                <Card className="bg-white/92"><CardHeader><CardTitle className="text-base">Seller threads</CardTitle></CardHeader></Card>
                {page.seller_threads?.length ? page.seller_threads.map(renderThread) : <Card className="bg-white/92"><CardContent className="p-6 text-sm text-muted-foreground">No seller threads yet.</CardContent></Card>}
              </div>
            </div>
          )}
        </div>
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><MessageSquare className="h-4 w-4 text-emerald-700" />Compose message</CardTitle>
            <CardDescription>Buyers and sellers can message staff only. Staff can message any user.</CardDescription>
          </CardHeader>
          <CardContent>{composeForm}</CardContent>
        </Card>
      </div>
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
  if (!page) return <AppShell {...{
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Approvals are unavailable.</CardContent></Card></AppShell>;

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };
  const pendingRemovalRequests = page.pending_joint_removals || [];

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Approvals" title={bootstrap.title} subtitle={bootstrap.subtitle} />
        <div className="grid gap-6 xl:grid-cols-4">
          <Card className="bg-white/92">
            <CardHeader><CardTitle className="text-base">Pending users</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {page.pending_users.map((user) => (
                <div key={user.email} className="rounded-3xl border border-border bg-muted/40 p-4">
                  <div className="font-semibold text-foreground">{user.email}</div>
                  <div className="text-sm text-muted-foreground">{user.role}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <a href={`/agent/approvals/${user.id}/review/`} className="inline-flex h-9 items-center justify-center rounded-full border border-border bg-white px-4 text-xs font-semibold text-foreground hover:bg-muted">Review</a>
                    <form method="post" action={`/agent/users/${user.id}/approve/`}>
                      <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                      <Button type="submit" size="sm" className="rounded-full">Approve</Button>
                    </form>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

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
            <CardHeader><CardTitle className="text-base">Pending transactions</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {page.pending_transactions.map((tx) => (
                <div key={tx.id} className="rounded-3xl border border-border bg-muted/40 p-4">
                  <div className="font-semibold text-foreground">{tx.parcel_number}</div>
                  <div className="text-sm text-muted-foreground">{tx.status} · KES {tx.amount}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-white/92 xl:col-span-4">
            <CardHeader>
              <CardTitle className="text-base">Pending joint member removals</CardTitle>
              <CardDescription>Admin must confirm consent and compensation before a member is removed from a joint group.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {pendingRemovalRequests.length ? pendingRemovalRequests.map((request) => (
                <div key={request.id} className="rounded-3xl border border-border bg-muted/40 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="font-semibold text-foreground">{request.group_name}</div>
                      <div className="text-sm text-muted-foreground">
                        Remove <strong>{request.member.full_name}</strong> · Requested by {request.requested_by?.email || 'Unknown'}
                      </div>
                      <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                        Consent: {request.consent_confirmed ? 'Confirmed' : 'Pending'} · Compensation: {request.compensation_confirmed ? `Confirmed${request.compensation_amount ? ` (KES ${request.compensation_amount})` : ''}` : 'Pending'}
                      </div>
                      {request.notes ? <div className="rounded-2xl bg-white px-3 py-2 text-sm text-foreground">{request.notes}</div> : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <form method="post" action={request.approve_url}>
                        <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                        <Button type="submit" size="sm" className="rounded-full">Approve removal</Button>
                      </form>
                      <form method="post" action={request.reject_url}>
                        <input type="hidden" name="csrfmiddlewaretoken" value={bootstrap.csrf_token || ''} />
                        <Button type="submit" size="sm" variant="outline" className="rounded-full">Reject</Button>
                      </form>
                    </div>
                  </div>
                </div>
              )) : (
                <div className="rounded-3xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  No pending joint removal requests.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
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

function ContractFullPage() {
  const contract = bootstrap.contract;
  const [documentSignatures, setDocumentSignatures] = useState<Record<string, string>>({});
  const [buyerSignature, setBuyerSignature] = useState('');
  const [sellerSignature, setSellerSignature] = useState('');
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
        <div className="print-document-toolbar grid gap-6 lg:grid-cols-2">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle>Signature Status</CardTitle>
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
            </CardContent>
          </Card>

          {(contract.current_user_is_buyer || contract.current_user_is_seller) && !contract.contract_agreed && !((contract.current_user_is_buyer && contract.buyer_signature_present) || (contract.current_user_is_seller && contract.seller_signature_present)) ? (
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <CardTitle>Execute Contract</CardTitle>
                <CardDescription>Sign all required documents and submit to complete the legal process.</CardDescription>
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


function ReactApp() {
  const page = bootstrap.page;
  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

  let pageContent: ReactNode = null;

  if (page === 'landing') pageContent = <LandingPage />;
  else if (page === 'content') pageContent = <ContentPage />;
  else if (page === 'status') pageContent = <StatusPage />;
  else if (page === 'form' || page === 'staff-login' || page === 'agent-kyc' || page === 'payment-onboarding') pageContent = <GenericFormPage />;
  else if (page === 'ai-kyc') pageContent = <AIKYCPage />;
  else if (page === 'buyer-choice') pageContent = <AppShell {...shellProps}><BuyerChoicePage /></AppShell>;
  else if (page === 'legal' || page === 'joint-laws') pageContent = <LegalPage />;
  else if (page === 'parcel-list') pageContent = <AppShell {...shellProps}><ParcelListPage /></AppShell>;
  else if (page === 'transactions') pageContent = <AppShell {...shellProps}><TransactionsPage /></AppShell>;
  else if (page === 'joint-groups') pageContent = <AppShell {...shellProps}><JointGroupsPage /></AppShell>;
  else if (page === 'joint-group-detail') pageContent = <AppShell {...shellProps}><JointGroupDetailPage /></AppShell>;
  else if (page === 'parcel-detail') pageContent = <ParcelDetailPage />;
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
  else if (page === 'dashboard' || page === 'admin-dashboard' || page === 'agent-dashboard') pageContent = <AppShell {...shellProps}><DashboardPage /></AppShell>;
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
      {pageContent}
      <PopupAdManager popupAds={bootstrap.popup_ads} csrfToken={bootstrap.csrf_token} />
    </>
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
