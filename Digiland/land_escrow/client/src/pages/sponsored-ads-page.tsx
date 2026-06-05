import React, { useState } from 'react';
import { Badge } from '../components/ui/badge.js';
import { Button } from '../components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card.js';
import { Separator } from '../components/ui/separator.js';
import { PageHeader } from '../components/layout/page-header.js';
import { Input } from '../components/ui/input.js';
import { Textarea } from '../components/ui/textarea.js';
import {
  Megaphone,
  Plus,
  Play,
  Pause,
  BarChart3,
  Eye,
  MousePointer,
  MessageSquare,
  DollarSign,
  Clock,
  Target,
  ArrowRight,
} from 'lucide-react';
import { cn } from '../lib/utils.js';

interface SponsoredAdSummary {
  id: string;
  parcel_number: string;
  parcel: { parcel_number: string; county: string; asking_price: string; image_url: string | null };
  tier: string;
  title: string;
  description: string;
  status: string;
  billing_model: string;
  budget_daily: string | null;
  budget_total: string | null;
  budget_spent: string;
  is_active: boolean;
  engagement_summary: {
    impressions: number;
    clicks: number;
    saves: number;
    inquiries: number;
    shares: number;
  };
  starts_at: string;
  ends_at: string;
  created_at: string;
}

interface SponsoredAdsPageData {
  campaigns: SponsoredAdSummary[];
  parcels: Array<{ id: string; parcel_number: string; county: string; asking_price: string }>;
  total_active: number;
  total_spent: string;
  total_impressions: number;
  total_clicks: number;
}

const kshFormatter = new Intl.NumberFormat('en-KE', { maximumFractionDigits: 0, minimumFractionDigits: 0 });
function money(value: string | number) {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(parsed) ? `KES ${kshFormatter.format(parsed)}` : `KES ${value}`;
}

const BILLING_LABELS: Record<string, string> = {
  PayPerDay: 'Pay Per Day',
  PayPerClick: 'Pay Per Click (CPC)',
  PayPerImpression: 'Pay Per Impression (CPM)',
  Subscription: 'Monthly Subscription',
};

const STATUS_TONES: Record<string, 'success' | 'warning' | 'danger' | 'muted' | 'default'> = {
  Active: 'success',
  Draft: 'warning',
  Paused: 'muted',
  Ended: 'default',
  Rejected: 'danger',
};

export function SponsoredAdsPage({ data }: { data: SponsoredAdsPageData }) {
  const { campaigns, parcels, total_active, total_spent, total_impressions, total_clicks } = data;
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    parcel: '',
    tier: 'Basic',
    billing_model: 'PayPerClick',
    budget_daily: '',
    budget_total: '',
    title: '',
    description: '',
    targeting_criteria: '{}',
  });
  const [loading, setLoading] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const resp = await fetch('/api/v1/sponsored-ads/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.getAttribute('content') || '' },
        body: JSON.stringify({
          ...form,
          budget_daily: form.budget_daily || null,
          budget_total: form.budget_total || null,
        }),
      });
      if (resp.ok) {
        window.location.reload();
      }
    } catch (e) {
      console.error('Failed to create campaign', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(campaignId: string, action: 'activate' | 'pause') {
    try {
      const resp = await fetch(`/api/v1/sponsored-ads/${campaignId}/${action}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.getAttribute('content') || '' },
      });
      if (resp.ok) window.location.reload();
    } catch (e) {
      console.error(`Failed to ${action} campaign`, e);
    }
  }

  const overallCtr = total_impressions > 0 ? ((total_clicks / total_impressions) * 100).toFixed(2) : '0.00';

  return (
    <div className="space-y-8">
      <PageHeader
        kicker="Advertising"
        title="Sponsored Ads"
        subtitle="Create and manage sponsored ad campaigns. Choose billing models, set budgets, and track performance."
        actions={[
          { label: 'Create Campaign', href: '#', tone: 'accent' as const },
        ]}
      />

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="bg-white/92">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
                <Megaphone className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Active</div>
                <div className="text-2xl font-black text-foreground">{total_active}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
                <Eye className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Impressions</div>
                <div className="text-2xl font-black text-foreground">{total_impressions.toLocaleString()}</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                <MousePointer className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">CTR</div>
                <div className="text-2xl font-black text-foreground">{overallCtr}%</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white/92">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
                <DollarSign className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Spent</div>
                <div className="text-2xl font-black text-foreground">{money(total_spent)}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Create Campaign Form */}
      <Card className="bg-white/92">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Plus className="h-5 w-5 text-emerald-700" />
              <CardTitle className="text-base">Create New Campaign</CardTitle>
            </div>
            <Button variant="outline" className="rounded-full" onClick={() => setShowForm(!showForm)}>
              {showForm ? 'Cancel' : 'New Campaign'}
            </Button>
          </div>
        </CardHeader>
        {showForm && (
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Parcel</label>
                  <select
                    className="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm"
                    value={form.parcel}
                    onChange={(e) => setForm({ ...form, parcel: e.target.value })}
                    required
                  >
                    <option value="">Select parcel</option>
                    {parcels.map((p) => (
                      <option key={p.id} value={p.id}>{p.parcel_number} — {p.county}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Billing Model</label>
                  <select
                    className="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm"
                    value={form.billing_model}
                    onChange={(e) => setForm({ ...form, billing_model: e.target.value })}
                  >
                    {Object.entries(BILLING_LABELS).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Tier</label>
                  <select
                    className="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm"
                    value={form.tier}
                    onChange={(e) => setForm({ ...form, tier: e.target.value })}
                  >
                    <option value="Basic">Basic</option>
                    <option value="Pro">Pro</option>
                    <option value="Elite">Elite</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Total Budget (KES)</label>
                  <Input
                    type="number"
                    placeholder="e.g. 50000"
                    value={form.budget_total}
                    onChange={(e) => setForm({ ...form, budget_total: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Ad Title</label>
                <Input
                  placeholder="e.g. Prime 2-Acre Plot in Kiambu"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">Description</label>
                <Textarea
                  placeholder="Describe what makes this listing special..."
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={3}
                />
              </div>
              <Button type="submit" className="rounded-full bg-emerald-700 hover:bg-emerald-800" disabled={loading}>
                {loading ? 'Creating...' : 'Create Campaign'} <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        )}
      </Card>

      {/* Campaign List */}
      <div className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-black tracking-tight text-foreground">Your Campaigns</h2>
            <p className="mt-1 text-sm text-muted-foreground">Track performance and manage your active campaigns.</p>
          </div>
          <Badge tone="outline">{campaigns.length} total</Badge>
        </div>

        {campaigns.length === 0 ? (
          <Card className="bg-white/90">
            <CardContent className="p-8 text-center">
              <Megaphone className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
              <div className="text-lg font-bold text-foreground">No campaigns yet</div>
              <p className="mt-2 text-sm text-muted-foreground">Create your first sponsored ad campaign to boost your listings.</p>
            </CardContent>
          </Card>
        ) : (
          campaigns.map((campaign) => {
            const eng = campaign.engagement_summary;
            const ctr = eng.impressions > 0 ? ((eng.clicks / eng.impressions) * 100).toFixed(2) : '0.00';
            const budgetUsed = campaign.budget_total ? (Number(campaign.budget_spent) / Number(campaign.budget_total) * 100).toFixed(0) : null;

            return (
              <Card key={campaign.id} className="bg-white/92">
                <CardContent className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-foreground">{campaign.title || campaign.parcel_number}</span>
                        <Badge tone={STATUS_TONES[campaign.status] || 'default'}>{campaign.status}</Badge>
                        <Badge tone="outline">{BILLING_LABELS[campaign.billing_model] || campaign.billing_model}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {campaign.parcel?.county || '—'} · {campaign.tier} tier · Created {new Date(campaign.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {campaign.status === 'Draft' && (
                        <Button size="sm" className="rounded-full bg-emerald-700" onClick={() => handleAction(campaign.id, 'activate')}>
                          <Play className="mr-1 h-3 w-3" /> Activate
                        </Button>
                      )}
                      {campaign.status === 'Active' && (
                        <Button size="sm" variant="outline" className="rounded-full" onClick={() => handleAction(campaign.id, 'pause')}>
                          <Pause className="mr-1 h-3 w-3" /> Pause
                        </Button>
                      )}
                    </div>
                  </div>

                  <Separator className="my-4" />

                  <div className="grid gap-4 sm:grid-cols-5">
                    <div className="rounded-2xl bg-muted/60 p-3 text-center">
                      <Eye className="mx-auto h-4 w-4 text-blue-600" />
                      <div className="mt-1 text-lg font-black">{eng.impressions.toLocaleString()}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Impressions</div>
                    </div>
                    <div className="rounded-2xl bg-muted/60 p-3 text-center">
                      <MousePointer className="mx-auto h-4 w-4 text-amber-600" />
                      <div className="mt-1 text-lg font-black">{eng.clicks.toLocaleString()}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Clicks</div>
                    </div>
                    <div className="rounded-2xl bg-muted/60 p-3 text-center">
                      <BarChart3 className="mx-auto h-4 w-4 text-emerald-600" />
                      <div className="mt-1 text-lg font-black">{ctr}%</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">CTR</div>
                    </div>
                    <div className="rounded-2xl bg-muted/60 p-3 text-center">
                      <MessageSquare className="mx-auto h-4 w-4 text-purple-600" />
                      <div className="mt-1 text-lg font-black">{eng.inquiries}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Inquiries</div>
                    </div>
                    <div className="rounded-2xl bg-muted/60 p-3 text-center">
                      <DollarSign className="mx-auto h-4 w-4 text-rose-600" />
                      <div className="mt-1 text-lg font-black">{money(campaign.budget_spent)}</div>
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                        {budgetUsed ? `${budgetUsed}% used` : 'Spent'}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
