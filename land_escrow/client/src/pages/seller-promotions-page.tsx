import React from 'react';
import { BarChart3, BadgeCheck, Clock3, Eye, Megaphone, MousePointerClick, Sparkles, Target, TrendingUp, WalletCards, Zap } from 'lucide-react';
import type { SellerPromotionsPageData, PopupAdCampaignSummary } from '../types.js';
import { FormRenderer } from '../components/forms/serialized-form.js';
import { Badge } from '../components/ui/badge.js';
import { Button } from '../components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card.js';
import { PageHeader } from '../components/layout/page-header.js';
import { Separator } from '../components/ui/separator.js';
import { cn } from '../lib/utils.js';

function toneClass(tone?: string) {
  if (tone === 'success') return 'bg-emerald-100 text-emerald-800';
  if (tone === 'warning') return 'bg-amber-100 text-amber-800';
  if (tone === 'muted') return 'bg-slate-100 text-slate-700';
  return 'bg-slate-100 text-slate-700';
}

function SummaryCard({ label, value, sublabel, icon: Icon }: { label: string; value: string; sublabel?: string; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <Card className="bg-white/92">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">{label}</div>
            <div className="mt-2 text-3xl font-black tracking-tight text-foreground">{value}</div>
            {sublabel ? <div className="mt-1 text-sm text-muted-foreground">{sublabel}</div> : null}
          </div>
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CampaignCard({ campaign, actionUrl, csrfToken }: { campaign: PopupAdCampaignSummary; actionUrl: string; csrfToken?: string }) {
  const statusTone = campaign.status_tone || 'muted';

  return (
    <Card className="overflow-hidden bg-white/92">
      <div className="grid gap-0 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="relative min-h-[260px] bg-slate-950">
          {campaign.creative_image_url ? (
            <img
              src={campaign.creative_image_url}
              alt={campaign.headline}
              className="absolute inset-0 h-full w-full object-cover opacity-80"
            />
          ) : null}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950/90 via-slate-950/70 to-emerald-950/55" />
          <div className="relative flex h-full flex-col justify-between p-6 text-white">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="outline" className="border-white/15 bg-white/10 text-white">
                <Megaphone className="mr-1 h-3.5 w-3.5" />
                {campaign.popup_type_label}
              </Badge>
              <Badge tone="outline" className={cn('border-0', toneClass(statusTone))}>
                {campaign.status_label}
              </Badge>
              <Badge tone="outline" className="border-white/15 bg-white/10 text-white">
                {campaign.billing_model_label}
              </Badge>
            </div>

            <div className="space-y-3">
              <div className="text-[10px] font-black uppercase tracking-[0.32em] text-emerald-200/90">
                {campaign.parcel.county} market
              </div>
              <h3 className="max-w-2xl text-2xl font-black tracking-tight sm:text-3xl">{campaign.headline}</h3>
              <p className="max-w-2xl text-sm leading-7 text-slate-100/85">{campaign.subheadline}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              {campaign.social_proof.map((item) => (
                <div key={item} className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-[11px] font-semibold">
                  {item}
                </div>
              ))}
              <div className="rounded-full border border-white/10 bg-white/10 px-3 py-1.5 text-[11px] font-semibold">
                {campaign.scarcity_text}
              </div>
            </div>
          </div>
        </div>

        <CardContent className="space-y-5 p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-3xl border border-border bg-muted/30 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Listing</div>
              <div className="mt-2 text-base font-bold text-foreground">{campaign.parcel.parcel_number}</div>
              <div className="mt-1 text-sm text-muted-foreground">{campaign.parcel.constituency}, {campaign.parcel.county}</div>
            </div>
            <div className="rounded-3xl border border-border bg-muted/30 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Budget</div>
              <div className="mt-2 text-base font-bold text-foreground">KES {Number(campaign.budget.total_budget).toLocaleString()}</div>
              <div className="mt-1 text-sm text-muted-foreground">Spend KES {Number(campaign.budget.spent_amount).toLocaleString()} of KES {Number(campaign.budget.total_budget).toLocaleString()}</div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl bg-muted/50 p-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">Impressions</div>
              <div className="mt-1 text-2xl font-black text-foreground">{campaign.metrics.impressions}</div>
            </div>
            <div className="rounded-2xl bg-muted/50 p-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">CTR</div>
              <div className="mt-1 text-2xl font-black text-foreground">{campaign.metrics.ctr.toFixed(2)}%</div>
            </div>
            <div className="rounded-2xl bg-muted/50 p-4">
              <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">ROI</div>
              <div className="mt-1 text-2xl font-black text-foreground">{campaign.metrics.roi.toFixed(2)}x</div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-border bg-white/80 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Audience</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {campaign.targeting.buyer_categories.map((item) => (
                  <Badge key={item} tone="outline" className="bg-emerald-50 text-emerald-800">{item}</Badge>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-border bg-white/80 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Regions</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {campaign.targeting.counties.map((item) => (
                  <Badge key={item} tone="outline">{item}</Badge>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge tone="outline" className="bg-slate-50">{campaign.seller.label}</Badge>
            <Badge tone="outline" className="bg-slate-50">{campaign.frequency.frequency_cap_per_session} / session</Badge>
            <Badge tone="outline" className="bg-slate-50">{campaign.frequency.cooldown_minutes} min cooldown</Badge>
            <Badge tone="outline" className="bg-slate-50">{campaign.targeting.travel_radius_km} km radius</Badge>
          </div>

          <div className="flex flex-wrap gap-2">
            <form method="post" action={actionUrl} className="inline-flex">
              <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
              <input type="hidden" name="form_type" value="campaign_action" />
              <input type="hidden" name="campaign_id" value={campaign.id} />
              <input type="hidden" name="campaign_action" value={campaign.status === 'Active' ? 'pause' : 'activate'} />
              <Button type="submit" className="rounded-full">
                {campaign.status === 'Active' ? 'Pause campaign' : 'Activate now'}
              </Button>
            </form>
            <form method="post" action={actionUrl} className="inline-flex">
              <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
              <input type="hidden" name="form_type" value="campaign_action" />
              <input type="hidden" name="campaign_id" value={campaign.id} />
              <input type="hidden" name="campaign_action" value="archive" />
              <Button type="submit" variant="outline" className="rounded-full">
                Archive
              </Button>
            </form>
            <a href={campaign.landing_url} target="_blank" rel="noreferrer" className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white px-5 text-sm font-semibold text-foreground hover:bg-muted">
              Preview destination
            </a>
          </div>
        </CardContent>
      </div>
    </Card>
  );
}

export function SellerPromotionsPage({ pageData, csrfToken }: { pageData: SellerPromotionsPageData; csrfToken?: string }) {
  const summary = pageData.summary;

  return (
    <div className="space-y-6">
      <PageHeader
        kicker="Promotions"
        title="Intelligent buyer pop-up campaigns"
        subtitle="Targeted land discovery ads, performance analytics, and AI feedback loops in one studio."
        badge={`${pageData.events_count} tracked events`}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Campaigns live" value={String(summary.active_campaigns)} sublabel={`${summary.total_campaigns} total`} icon={Megaphone} />
        <SummaryCard label="CTR" value={`${summary.ctr.toFixed(2)}%`} sublabel={`${summary.total_clicks} clicks`} icon={MousePointerClick} />
        <SummaryCard label="Leads" value={String(summary.total_leads)} sublabel={`${summary.lead_rate.toFixed(2)}% lead rate`} icon={Eye} />
        <SummaryCard label="ROI" value={`${summary.roi.toFixed(2)}x`} sublabel={`KES ${Number(summary.total_spend).toLocaleString()} spend`} icon={TrendingUp} />
      </div>

      <Card className="bg-white/92">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4 text-emerald-700" />
            Launch a campaign
          </CardTitle>
          <CardDescription>
            Configure popup type, audience targeting, frequency controls, and creative assets. Active campaigns are auto-marked paid in this development build so you can test the full flow.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FormRenderer form={pageData.form} csrfToken={csrfToken} submitVariant="default" />
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_0.9fr]">
        <div className="space-y-4">
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="h-4 w-4 text-emerald-700" />
                Live campaigns
              </CardTitle>
              <CardDescription>Ranked by score and performance. Higher relevance and better bids rise to the top.</CardDescription>
            </CardHeader>
          </Card>

          <div className="space-y-4">
            {pageData.campaigns.length ? (
              pageData.campaigns.map((campaign) => (
                <CampaignCard key={campaign.id} campaign={campaign} actionUrl={pageData.campaign_action_url} csrfToken={csrfToken} />
              ))
            ) : (
              <Card className="bg-white/92">
                <CardContent className="p-8 text-center">
                  <Megaphone className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
                  <div className="text-lg font-bold text-foreground">No campaigns yet</div>
                  <p className="mt-2 text-sm text-muted-foreground">Create your first popup campaign above. Once active, it will enter the buyer experience on relevant discovery pages.</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Target className="h-4 w-4 text-emerald-700" />
                Targeting engine
              </CardTitle>
              <CardDescription>Supported popup formats and audience models.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {pageData.supported_popup_types.map((item) => (
                  <Badge key={item} tone="outline" className="bg-emerald-50 text-emerald-800">{item}</Badge>
                ))}
              </div>
              <Separator />
              <div className="flex flex-wrap gap-2">
                {pageData.supported_billing_models.map((item) => (
                  <Badge key={item} tone="outline">{item}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-emerald-700" />
                AI recommendations
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {pageData.recommendations.map((item) => (
                <div key={item.title} className="rounded-2xl border border-border bg-muted/30 p-4">
                  <div className="font-bold text-foreground">{item.title}</div>
                  <div className="mt-1 text-sm leading-7 text-muted-foreground">{item.body}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <WalletCards className="h-4 w-4 text-emerald-700" />
                County performance
              </CardTitle>
              <CardDescription>Heatmap-style view of where popup engagement is strongest.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {pageData.heatmap.length ? (
                pageData.heatmap.map((row) => (
                  <div key={row.county} className="rounded-2xl border border-border bg-muted/30 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-bold text-foreground">{row.county}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{row.impressions} impressions, {row.clicks} clicks, {row.leads} leads</div>
                      </div>
                      <div className="text-right text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
                        {row.dismissals} dismissals
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  No event data yet. Once buyers start engaging, counties and popup types will rank here.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="bg-white/92">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock3 className="h-4 w-4 text-emerald-700" />
                Trigger mix
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {pageData.trigger_breakdown.length ? (
                pageData.trigger_breakdown.map((row) => (
                  <div key={row.popup_type} className="rounded-2xl border border-border bg-muted/30 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-bold text-foreground">{row.popup_type}</div>
                      <div className="text-sm text-muted-foreground">{row.impressions} impressions</div>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      <div>{row.clicks} clicks</div>
                      <div>{row.leads} leads</div>
                      <div>{Math.max(0, row.impressions - row.clicks)} view-only</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Trigger analytics will appear once campaigns are live.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
