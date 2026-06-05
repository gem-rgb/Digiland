import React, { useState } from 'react';
import { Badge } from '../components/ui/badge.js';
import { Button } from '../components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card.js';
import { Separator } from '../components/ui/separator.js';
import { PageHeader } from '../components/layout/page-header.js';
import {
  Check,
  Crown,
  Sparkles,
  Star,
  Zap,
  ArrowRight,
  Landmark,
} from 'lucide-react';
import { cn } from '../lib/utils.js';

interface TierFeature {
  label: string;
  included: boolean;
  detail?: string;
}

interface PromotionTier {
  id: string;
  name: string;
  slug: string;
  tier_level: number;
  monthly_price: string;
  features_json: TierFeature[];
  active: boolean;
}

interface PromotionPlan {
  id: string;
  tier: PromotionTier;
  tier_name: string;
  status: string;
  is_active: boolean;
  auto_renew: boolean;
  start_date: string;
  end_date: string;
}

interface PromotionTiersPageData {
  tiers: PromotionTier[];
  current_plan: PromotionPlan | null;
  seller_email: string;
}

const kshFormatter = new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 0,
  minimumFractionDigits: 0,
});

function money(value: string | number) {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(parsed) ? `KES ${kshFormatter.format(parsed)}/mo` : `KES ${value}/mo`;
}

const TIER_ICONS: Record<string, React.ReactNode> = {
  basic: <Landmark className="h-6 w-6" />,
  pro: <Zap className="h-6 w-6" />,
  elite: <Crown className="h-6 w-6" />,
};

const TIER_COLORS: Record<string, { border: string; bg: string; text: string; badge: string }> = {
  basic: { border: 'border-stone-300', bg: 'bg-stone-50', text: 'text-stone-700', badge: 'outline' },
  pro: { border: 'border-blue-300', bg: 'bg-blue-50', text: 'text-blue-700', badge: 'warning' },
  elite: { border: 'border-amber-300', bg: 'bg-amber-50', text: 'text-amber-700', badge: 'success' },
};

export function PromotionTiersPage({ data }: { data: PromotionTiersPageData }) {
  const { tiers, current_plan, seller_email } = data;
  const [selectedTier, setSelectedTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const currentTierSlug = current_plan?.tier?.slug || 'basic';

  async function handleSelectTier(tierSlug: string) {
    setSelectedTier(tierSlug);
    setLoading(true);
    try {
      const resp = await fetch('/api/v1/promotion-plans/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.getAttribute('content') || '' },
        body: JSON.stringify({ tier_id: tierSlug, auto_renew: true }),
      });
      if (resp.ok) {
        window.location.reload();
      }
    } catch (e) {
      console.error('Failed to update plan', e);
    } finally {
      setLoading(false);
      setSelectedTier(null);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        kicker="Subscription"
        title="Promotion Tiers"
        subtitle="Choose a tier to boost your listings. Higher tiers unlock premium visibility, advanced analytics, and more buyer reach."
      />

      {/* Current Plan Banner */}
      {current_plan && (
        <Card className="border-emerald-200 bg-emerald-50/70">
          <CardContent className="flex items-center justify-between p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700">
                <Star className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-bold uppercase tracking-[0.2em] text-emerald-700">Current Plan</div>
                <div className="text-lg font-black text-foreground">{current_plan.tier_name}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">Status</div>
              <Badge tone={current_plan.is_active ? 'success' : 'warning'}>
                {current_plan.status}
              </Badge>
              <div className="mt-1 text-xs text-muted-foreground">
                {current_plan.auto_renew ? 'Auto-renews' : 'Manual renewal'} · Until {current_plan.end_date}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tier Comparison Cards */}
      <div className="grid gap-6 lg:grid-cols-3">
        {tiers.map((tier) => {
          const slug = tier.slug.toLowerCase();
          const colors = TIER_COLORS[slug] || TIER_COLORS.basic;
          const isCurrent = tier.slug === currentTierSlug;
          const features: TierFeature[] = tier.features_json || [];

          return (
            <Card
              key={tier.id}
              className={cn(
                'relative overflow-hidden transition-shadow hover:shadow-lg',
                isCurrent ? 'ring-2 ring-emerald-500' : '',
                colors.border
              )}
            >
              {isCurrent && (
                <div className="absolute right-0 top-0 rounded-bl-xl bg-emerald-600 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-white">
                  Current
                </div>
              )}

              <CardHeader className={cn('pb-4', colors.bg)}>
                <div className={cn('mb-2 flex h-12 w-12 items-center justify-center rounded-2xl', colors.bg, colors.text)}>
                  {TIER_ICONS[slug] || <Star className="h-6 w-6" />}
                </div>
                <CardTitle className="text-xl">{tier.name}</CardTitle>
                <CardDescription>
                  <span className="text-2xl font-black text-foreground">{money(tier.monthly_price)}</span>
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 pt-4">
                <Separator />
                <div className="space-y-3">
                  {features.map((feature, idx) => (
                    <div key={idx} className="flex items-start gap-3 text-sm">
                      <Check className={cn('mt-0.5 h-4 w-4 shrink-0', feature.included ? 'text-emerald-600' : 'text-muted-foreground/40')} />
                      <span className={feature.included ? 'text-foreground' : 'text-muted-foreground/60'}>
                        {feature.label}
                        {feature.detail && <span className="ml-1 text-xs text-muted-foreground">({feature.detail})</span>}
                      </span>
                    </div>
                  ))}
                </div>

                <Button
                  className={cn('w-full rounded-full', isCurrent ? 'bg-emerald-700' : '')}
                  variant={isCurrent ? 'default' : 'outline'}
                  disabled={isCurrent || loading}
                  onClick={() => handleSelectTier(tier.slug)}
                >
                  {isCurrent ? 'Current Plan' : loading && selectedTier === tier.slug ? 'Processing...' : `Select ${tier.name}`}
                  {!isCurrent && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
