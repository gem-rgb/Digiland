import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowRight, Banknote, BarChart3, CircleCheckBig, Clock3, ExternalLink, FileSignature, FileText, Gavel, Heart, Landmark, Mail, MessageSquare, ReceiptText, ShieldAlert, ShieldCheck, Sparkles, Ticket, Users, WalletCards, type LucideIcon } from 'lucide-react';
import type { FormEvent, ReactNode } from 'react';
import { readBootstrap } from './lib/bootstrap.js';
import { AppShell } from './components/layout/app-shell.js';
import { PublicShell } from './components/layout/public-shell.js';
import { PageHeader } from './components/layout/page-header.js';
import { FormRenderer } from './components/forms/serialized-form.js';
import { SignaturePad } from './components/forms/signature-pad.js';
import { Input } from './components/ui/input.js';
import { Textarea } from './components/ui/textarea.js';
import { Badge } from './components/ui/badge.js';
import { Button } from './components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card.js';
import { Separator } from './components/ui/separator.js';
import type { ActionLink } from './types.js';
import { cn } from './lib/utils.js';

const bootstrap = readBootstrap();

function statusTone(status?: string) {
  if (!status) return 'muted';
  const value = status.toLowerCase();
  if (value.includes('verified') || value.includes('completed') || value.includes('signed') || value.includes('approved')) return 'success';
  if (value.includes('pending') || value.includes('initiated') || value.includes('under')) return 'warning';
  if (value.includes('fraud') || value.includes('reject') || value.includes('failed') || value.includes('disputed') || value.includes('reversed')) return 'danger';
  return 'muted';
}

function money(value: string | number) {
  return `KES ${value}`;
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
        <Card key={parcel.parcel_number} className="overflow-hidden bg-white/92">
          <div className="aspect-[16/10] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50">
            {parcel.image_url ? (
              <img src={parcel.image_url} alt={parcel.parcel_number} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                No image
              </div>
            )}
          </div>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">{parcel.parcel_number}</CardTitle>
                <CardDescription>
                  {parcel.county}, {parcel.constituency}
                </CardDescription>
              </div>
              <StatusBadge label={parcel.status_badge || parcel.verification_status} tone={statusTone(parcel.verification_status)} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
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
            <a
              href={parcel.details_url}
              className="inline-flex h-11 w-full items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {parcel.manage_label || 'View details'}
              <ArrowRight className="ml-2 h-4 w-4" />
            </a>
          </CardContent>
        </Card>
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
  const subtitle = role === 'Admin' || role === 'Agent'
    ? 'Monitor parcels, approvals, transactions, and messages from one workspace.'
    : role === 'Seller'
      ? 'Manage your listings, review buyer activity, and track escrow status.'
      : 'Browse land, review contracts, and manage joint purchase activity from one clean workspace.';

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

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="bg-white/92">
          <CardHeader>
            <PanelTitle title="Recent parcels" subtitle="Verified listings and monitored parcels." action={<a href="/parcels/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">View all</a>} />
          </CardHeader>
          <CardContent>
            <ParcelGrid />
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-white/92">
            <CardHeader>
              <PanelTitle title="Recent transactions" subtitle="Latest escrow movement in your account." action={<a href="/transactions/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">Open register</a>} />
            </CardHeader>
            <CardContent className="p-0">
              <TransactionTable />
            </CardContent>
          </Card>

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
      </div>
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
  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-6">
        <PageHeader
          kicker="Kenya law"
          title={bootstrap.title}
          subtitle={bootstrap.subtitle}
          badge={bootstrap.notice}
          actions={bootstrap.actions}
        />
        {bootstrap.laws ? LegalCards(bootstrap.laws) : null}
      </div>
      <div className="space-y-6">
        <Card className="bg-white/92">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><ShieldAlert className="h-4 w-4 text-amber-600" />Checklist</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3 text-sm leading-7 text-foreground">
              {(bootstrap.checklist || []).map((item) => (
                <li key={item} className="flex gap-3">
                  <CircleCheckBig className="mt-1 h-4 w-4 shrink-0 text-emerald-700" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {bootstrap.payment_guidance?.length ? (
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><WalletCards className="h-4 w-4 text-emerald-700" />Joint payment guidance</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3 text-sm leading-7 text-foreground">
                {bootstrap.payment_guidance.map((item) => (
                  <li key={item} className="flex gap-3">
                    <Banknote className="mt-1 h-4 w-4 shrink-0 text-emerald-700" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}
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
                  {member.delete_url && !member.is_leader ? <a href={member.delete_url} className="inline-flex h-9 items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-4 text-xs font-semibold text-rose-700 hover:bg-rose-100">Remove</a> : null}
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
              </div>
            </CardContent>
          </Card>
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
        <section className="overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_right,_rgba(16,185,129,0.15),_transparent_25%),linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(255,255,255,0.8))] p-6 shadow-soft sm:p-8 lg:p-10">
          <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-5">
              <Badge tone="outline" className="w-fit px-4 py-2">{bootstrap.notice || 'Kenya land escrow platform'}</Badge>
              <h1 className="max-w-3xl text-4xl font-black tracking-tight text-foreground sm:text-5xl">Buy and sell land with confidence, not guesswork.</h1>
              <p className="max-w-2xl text-base leading-8 text-muted-foreground sm:text-lg">
                Digiland keeps parcel verification, joint ownership, contract signing, and escrow payment in one controlled flow.
              </p>
              <div className="flex flex-wrap gap-3">
                {(bootstrap.actions || []).map((action) => (
                  <a
                    key={action.href}
                    href={action.href}
                    className={
                      action.tone === 'secondary'
                        ? 'inline-flex h-12 items-center justify-center rounded-full bg-secondary px-5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-secondary/85'
                        : action.tone === 'outline'
                          ? 'inline-flex h-12 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground transition-colors hover:bg-muted'
                          : 'inline-flex h-12 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90'
                    }
                  >
                    {action.label}
                  </a>
                ))}
              </div>
              {stats.length ? (
                <div className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-4">
                  {stats.map((stat) => (
                    <Card key={stat.label} className="bg-white/90">
                      <CardContent className="p-4">
                        <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">{stat.label}</div>
                        <div className="mt-2 text-2xl font-black tracking-tight text-foreground">{stat.value}</div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : null}
            </div>

            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-xl">Why it works</CardTitle>
                <CardDescription>Structured workflow, fewer style mismatches, and clearer action paths for each role.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  'Verified parcels only reach checkout after review.',
                  'Joint buyers get a dedicated ownership and payment flow.',
                  'Contracts and legal references are surfaced in the browser.',
                  'Agents and admins use one command-centre layout.',
                ].map((item) => (
                  <div key={item} className="flex gap-3 rounded-2xl border border-border bg-muted/40 p-4">
                    <CircleCheckBig className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
                    <span className="text-sm leading-6 text-foreground">{item}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">How it works</div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Three steps to a secure transfer</h2>
            </div>
            <a href="/escrow-acts/" className="text-sm font-semibold text-emerald-700 hover:text-emerald-800">Read the legal checklist</a>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {[
              {
                title: 'List and verify',
                body: 'Sellers upload parcel details and compliance documents. Licensed agents review the listing before it goes live.',
              },
              {
                title: 'Sign the contract',
                body: 'Buyer and seller sign the land transfer agreement. Joint buyers can capture member signatures as well.',
              },
              {
                title: 'Send payment',
                body: 'Once the contract is complete, the buyer sees checkout and receives an M-Pesa STK prompt or joint bank instructions.',
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
                <Card key={parcel.parcel_number} className="overflow-hidden bg-white/92">
                  <div className="aspect-[16/10] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50">
                    {parcel.image_url ? (
                      <img src={parcel.image_url} alt={parcel.parcel_number} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                        No image
                      </div>
                    )}
                  </div>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <CardTitle className="text-base">{parcel.parcel_number}</CardTitle>
                        <CardDescription>{parcel.county}, {parcel.constituency}</CardDescription>
                      </div>
                      <Badge tone={parcel.verification_status === 'Verified' ? 'success' : 'warning'}>{parcel.status_badge || parcel.verification_status}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
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
                    <a href={parcel.details_url} className="inline-flex h-11 w-full items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90">
                      {parcel.manage_label || 'View details'}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </a>
                  </CardContent>
                </Card>
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
      <div className="space-y-6">
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
      <div className="space-y-6">
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
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><FileText className="h-4 w-4 text-emerald-700" />Compliance documents</CardTitle>
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

  const renderThread = (thread: NonNullable<typeof page.threads>[number]) => (
    <Card key={thread.partner.email} className="bg-white/92">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">{thread.partner.email}</CardTitle>
            <CardDescription>{thread.partner.role}</CardDescription>
          </div>
          <Badge tone="outline">{thread.count}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {thread.messages.map((message) => (
          <div key={message.id} className={message.is_self ? 'ml-auto max-w-[85%] rounded-3xl bg-primary px-4 py-3 text-sm text-primary-foreground' : 'max-w-[85%] rounded-3xl bg-muted/60 px-4 py-3 text-sm text-foreground'}>
            <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.2em] opacity-70">{message.is_self ? 'You' : message.sender_email} · {message.timestamp}</div>
            {message.content}
          </div>
        ))}
      </CardContent>
    </Card>
  );

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
      <div className="space-y-6">
        <PageHeader kicker="AI-powered" title={bootstrap.title} subtitle={bootstrap.subtitle} actions={bootstrap.actions} />

        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">{page.rec_type === 'personalized' ? 'Tailored picks' : 'Trending now'}</div>
              <h2 className="text-2xl font-black tracking-tight text-foreground">Recommended for you</h2>
            </div>
            {page.rec_type === 'personalized' ? <Badge tone="success">ML personalized</Badge> : <Badge tone="outline">Popular</Badge>}
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {page.recommended.length ? page.recommended.map((parcel) => (
              <Card key={parcel.parcel_number} className="overflow-hidden bg-white/92">
                <div className="aspect-[16/10] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50">
                  {parcel.image_url ? <img src={parcel.image_url} alt={parcel.parcel_number} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-emerald-700"><Sparkles className="h-10 w-10" /></div>}
                </div>
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-bold text-foreground">{parcel.parcel_number}</div>
                      <div className="text-xs text-muted-foreground">{parcel.ward}, {parcel.county}</div>
                    </div>
                    {parcel.match_score != null ? <Badge tone="success">{Math.round(parcel.match_score)}% match</Badge> : null}
                  </div>
                  <div className="text-base font-black text-emerald-700">KES {parcel.land_size}</div>
                  <a href={parcel.details_url} className="inline-flex h-10 w-full items-center justify-center rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground hover:bg-primary/90">
                    Open parcel
                  </a>
                </CardContent>
              </Card>
            )) : (
              <Card className="bg-white/92 md:col-span-2 xl:col-span-4"><CardContent className="p-8 text-center text-sm text-muted-foreground">No recommendations yet.</CardContent></Card>
            )}
          </div>
        </div>

        {page.popular_parcels.length ? (
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

        {page.recently_viewed.length ? (
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

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Approvals" title={bootstrap.title} subtitle={bootstrap.subtitle} />
        <div className="grid gap-6 xl:grid-cols-3">
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

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Contract" title="Kenyan Land Transfer Agreement" subtitle={`Property: ${contract.parcel_number}`} actions={bootstrap.actions} />

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-6">
            <Card className="bg-white/92">
              <CardHeader>
                <CardTitle className="text-base">Legal framework</CardTitle>
                <CardDescription>Core Kenyan land-sale statutes and official references.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-2">
                {contract.laws.map((law) => (
                  <Card key={`${law.title}-${law.citation}`} className="bg-white/90">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <CardTitle className="text-sm">{law.title}</CardTitle>
                          <CardDescription>{law.citation}</CardDescription>
                        </div>
                        <Badge tone={law.required ? 'success' : 'warning'}>{law.required ? 'Core' : 'Conditional'}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm leading-7 text-foreground">{law.summary}</p>
                      <a href={law.official_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800">
                        Open official source
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </CardContent>
                  </Card>
                ))}
              </CardContent>
            </Card>

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
          </div>

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
            ) : contract.current_user_is_buyer || contract.current_user_is_seller ? (
              <Card className="bg-white/92">
                <CardHeader>
                  <CardTitle className="text-base">Sign this contract</CardTitle>
                  <CardDescription>Draw your signature to accept the legal terms.</CardDescription>
                </CardHeader>
                <CardContent>
                  <form method="post" action={contract.sign_url} className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={contract.csrf_token} />
                    <input type="hidden" name="signature_data" value={contract.current_user_is_buyer ? buyerSignature : sellerSignature} />
                    <SignaturePad label={contract.current_user_is_buyer ? 'Buyer signature' : 'Seller signature'} onChange={contract.current_user_is_buyer ? setBuyerSignature : setSellerSignature} />
                    <Button type="submit" className="w-full rounded-full">Sign and accept</Button>
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

            {contract.contract_agreed && contract.current_user_is_buyer ? (
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="space-y-4 p-6 text-center">
                  <h3 className="text-xl font-black tracking-tight text-foreground">Legal process complete</h3>
                  <p className="text-sm leading-7 text-muted-foreground">The contract has been signed. Continue to checkout and enter the phone number that should receive the M-Pesa STK prompt.</p>
                  <a href={contract.payment_url} className="inline-flex h-12 items-center justify-center rounded-full bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90">Continue to checkout</a>
                </CardContent>
              </Card>
            ) : null}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function CheckoutPage() {
  const checkout = bootstrap.checkout;
  const checkoutTransactionId = checkout?.transaction_id || '';
  const checkoutCsrfToken = checkout?.csrf_token || '';
  const checkoutTransactionsUrl = checkout?.transactions_url || '';
  const [paymentMode, setPaymentMode] = useState<'m_pesa' | 'joint_bank_account'>(checkout?.default_payment_method || 'm_pesa');
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
        const response = await fetch(`/api/v1/mpesa/check-checkout-status/?checkout_request_id=${encodeURIComponent(checkoutRequestId)}&transaction_id=${encodeURIComponent(checkoutTransactionId)}`, {
          headers: { 'X-CSRFToken': checkoutCsrfToken },
        });
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
    return <AppShell {...{
      title: bootstrap.title,
      subtitle: bootstrap.subtitle,
      user: bootstrap.user,
      nav: bootstrap.nav,
      logoutUrl: bootstrap.logout_url,
      csrfToken: bootstrap.csrf_token,
    }}><Card className="bg-white/92"><CardContent className="p-8 text-center text-sm text-muted-foreground">Checkout is unavailable.</CardContent></Card></AppShell>;
  }

  const shellProps = {
    title: bootstrap.title,
    subtitle: bootstrap.subtitle,
    user: bootstrap.user,
    nav: bootstrap.nav,
    logoutUrl: bootstrap.logout_url,
    csrfToken: bootstrap.csrf_token,
  };

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

  return (
    <AppShell {...shellProps}>
      <div className="space-y-6">
        <PageHeader kicker="Checkout" title="Regulated escrow deposit" subtitle="Funds remain held in escrow until deed transfer and final authorisation are complete." actions={bootstrap.actions} />
        <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="text-base">Escrow invoice summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 text-sm">
                <div className="rounded-2xl bg-muted/60 p-3">Transaction ID: <strong>{checkout.transaction_id.slice(0, 8).toUpperCase()}</strong></div>
                <div className="rounded-2xl bg-muted/60 p-3">Parcel: <strong>{checkout.parcel_number}</strong></div>
                <div className="rounded-2xl bg-muted/60 p-3">Seller: <strong>{checkout.seller_email}</strong></div>
                <div className="rounded-2xl bg-muted/60 p-3">Agreed price: <strong>KES {checkout.agreed_price}</strong></div>
                {checkout.is_joint_purchase && checkout.joint_group_name ? <div className="rounded-2xl bg-muted/60 p-3">Joint group: <strong>{checkout.joint_group_name}</strong></div> : null}
              </div>

              {checkout.is_joint_purchase ? (
                <div className="space-y-3">
                  <div className="text-sm font-semibold text-foreground">Joint split</div>
                  {checkout.breakdown.map((row) => (
                    <div key={row.member_id} className="flex items-center justify-between gap-3 rounded-3xl border border-border bg-muted/40 p-4 text-sm">
                      <div>
                        <div className="font-semibold text-foreground">{row.member_name}</div>
                        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{row.share_percentage}% · {row.phone_number}</div>
                      </div>
                      <div className="font-black text-emerald-700">KES {row.amount}</div>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="text-base">Select payment vector</CardTitle>
              <CardDescription>Choose M-Pesa or the jointly owned bank account if the group has one.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {viewState === 'form' ? (
                <form onSubmit={handleSubmit} className="space-y-4">
                  {checkout.is_joint_purchase ? (
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Payment option</label>
                      <select value={paymentMode} onChange={(event) => setPaymentMode(event.target.value as 'm_pesa' | 'joint_bank_account')} className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm">
                        <option value="m_pesa">Leader pays with M-Pesa</option>
                        <option value="joint_bank_account">Pay from the joint bank account</option>
                      </select>
                    </div>
                  ) : null}

                  {checkout.is_joint_purchase && paymentMode === 'm_pesa' ? (
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Pay as member</label>
                      <select value={memberId} onChange={(event) => {
                        setMemberId(event.target.value);
                        const member = checkout.breakdown.find((row) => row.member_id === event.target.value);
                        if (member) {
                          setPhoneNumber(member.phone_number || '');
                          setAmountOverride(member.amount);
                        }
                      }} className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm">
                        <option value="">Select member</option>
                        {checkout.breakdown.map((row) => (
                          <option key={row.member_id} value={row.member_id}>
                            {row.member_name} ({row.share_percentage}% → KES {row.amount})
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}

                  {paymentMode === 'joint_bank_account' ? (
                    <div className="space-y-4 rounded-3xl border border-border bg-muted/30 p-4">
                      <div className="text-sm font-semibold text-foreground">Joint bank account</div>
                      <div className="text-sm text-muted-foreground">{checkout.bank_name || 'Bank not yet configured'}</div>
                      <div className="text-sm text-muted-foreground">Account name: {checkout.bank_account_name || 'Not set'}</div>
                      <div className="text-sm text-muted-foreground">Account number: {checkout.bank_account_number || 'Not set'}</div>
                      <div className="text-sm text-muted-foreground">Branch: {checkout.bank_branch || 'Not set'}</div>
                      {!checkout.joint_bank_ready ? <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">The joint bank account has not been configured yet.</div> : null}
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">Depositor name</label>
                        <Input value={depositorName} onChange={(event) => setDepositorName(event.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-semibold text-foreground">Bank transfer reference</label>
                        <Input value={bankReference} onChange={(event) => setBankReference(event.target.value)} placeholder="Transfer reference or slip number" />
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">M-Pesa phone number</label>
                      <Input value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} placeholder="0712345678 or +254712345678" />
                    </div>
                  )}

                  {paymentMode === 'm_pesa' ? (
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-foreground">Amount override</label>
                      <Input value={amountOverride} onChange={(event) => setAmountOverride(event.target.value)} placeholder="Leave blank for default amount" />
                    </div>
                  ) : null}

                  <Button type="submit" className="w-full rounded-full" disabled={loading}>
                    {loading ? 'Processing...' : paymentMode === 'joint_bank_account' ? 'Record bank transfer' : 'Send M-Pesa STK push'}
                  </Button>
                </form>
              ) : (
                <div className="space-y-4 text-center">
                  {viewState === 'stk_waiting' ? (
                    <>
                      <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                        <div className="text-xl font-black text-foreground">STK push sent</div>
                        <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                      </div>
                      <div className="text-sm text-muted-foreground">Please authorise the payment on your phone. This page will update automatically.</div>
                    </>
                  ) : null}
                  {viewState === 'bank_waiting' ? (
                    <>
                      <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                        <div className="text-xl font-black text-foreground">Bank transfer recorded</div>
                        <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                      </div>
                      <div className="grid gap-3 text-left text-sm">
                        <div className="rounded-2xl bg-muted/60 p-3">Reference: <strong>{bankReference}</strong></div>
                        <div className="rounded-2xl bg-muted/60 p-3">Depositor: <strong>{depositorName}</strong></div>
                      </div>
                    </>
                  ) : null}
                  {viewState === 'success' ? (
                    <div className="rounded-[2rem] border border-emerald-200 bg-emerald-50/70 p-6">
                      <div className="text-xl font-black text-foreground">Payment confirmed</div>
                      <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                    </div>
                  ) : null}
                  {viewState === 'failed' ? (
                    <div className="rounded-[2rem] border border-rose-200 bg-rose-50/70 p-6">
                      <div className="text-xl font-black text-foreground">Payment failed</div>
                      <p className="mt-2 text-sm leading-7 text-muted-foreground">{message}</p>
                      <div className="mt-4 flex flex-wrap justify-center gap-3">
                        <Button type="button" variant="outline" className="rounded-full" onClick={() => {
                          setViewState('form');
                          setMessage('');
                        }}>
                          Try again
                        </Button>
                      </div>
                    </div>
                  ) : null}
                  <a href={checkout.transactions_url} className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground hover:bg-muted">View transactions</a>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
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

  if (page === 'landing') return <LandingPage />;
  if (page === 'content') return <ContentPage />;
  if (page === 'status') return <StatusPage />;
  if (page === 'form' || page === 'staff-login' || page === 'agent-kyc' || page === 'payment-onboarding') return <GenericFormPage />;
  if (page === 'buyer-choice') return <AppShell {...shellProps}><BuyerChoicePage /></AppShell>;
  if (page === 'legal' || page === 'joint-laws') return <AppShell {...shellProps}><LegalPage /></AppShell>;
  if (page === 'parcel-list') return <AppShell {...shellProps}><ParcelListPage /></AppShell>;
  if (page === 'transactions') return <AppShell {...shellProps}><TransactionsPage /></AppShell>;
  if (page === 'joint-groups') return <AppShell {...shellProps}><JointGroupsPage /></AppShell>;
  if (page === 'joint-group-detail') return <AppShell {...shellProps}><JointGroupDetailPage /></AppShell>;
  if (page === 'parcel-detail') return <ParcelDetailPage />;
  if (page === 'messages') return <MessagesPage />;
  if (page === 'support') return <SupportPage />;
  if (page === 'contract') return <ContractPage />;
  if (page === 'checkout') return <CheckoutPage />;
  if (page === 'recommendations') return <RecommendationsPage />;
  if (page === 'price-prediction') return <PredictionPage />;
  if (page === 'task-management') return <TaskManagementPage />;
  if (page === 'approvals') return <ApprovalsPage />;
  if (page === 'user-review') return <UserReviewPage />;
function AdminFinancePage() {
  const finance = bootstrap.finance_dashboard;

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

  if (page === 'dashboard' || page === 'admin-dashboard' || page === 'agent-dashboard') return <AppShell {...shellProps}><DashboardPage /></AppShell>;
  if (page === 'finance') return <AppShell {...shellProps}><AdminFinancePage /></AppShell>;
  return (
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

export default ReactApp;
