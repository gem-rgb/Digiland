import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  ChevronDown,
  ChevronUp,
  RefreshCw,
  TrendingUp,
  Flame,
  Star,
  MapPin,
  Eye,
  Sparkles,
  DollarSign,
  Loader2,
  ArrowRight,
  Heart,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import type { ParcelSummary, RecommendationParcelSummary } from '../../types.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FeedParcel extends ParcelSummary {
  match_score?: number;
  view_count?: number;
  is_sponsored?: boolean;
  sponsor_label?: string;
  price_trend?: 'up' | 'down' | 'stable';
  is_favorited?: boolean;
}

export interface FeedSection {
  id: string;
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  parcels: FeedParcel[];
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}

export interface RecommendationsFeedProps {
  /** Sections to display in the feed */
  sections: FeedSection[];
  /** Callback to fetch more parcels for a section (infinite scroll) */
  onLoadMore?: (sectionId: string) => Promise<void>;
  /** Callback when user pulls to refresh */
  onRefresh?: () => Promise<void>;
  /** Callback to track a parcel view */
  onTrackView?: (parcelNumber: string) => void;
  /** Callback when a parcel card is clicked */
  onParcelClick?: (parcel: FeedParcel) => void;
  /** Callback when favorite is toggled */
  onToggleFavorite?: (parcel: FeedParcel) => void;
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

function formatMoney(value: string | number) {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (Number.isFinite(parsed)) {
    return `KES ${kshFormatter.format(parsed)}`;
  }
  return `KES ${value}`;
}

function statusTone(status?: string): 'success' | 'warning' | 'danger' | 'muted' {
  if (!status) return 'muted';
  const v = status.toLowerCase();
  if (v.includes('verified') || v.includes('completed')) return 'success';
  if (v.includes('pending') || v.includes('initiated') || v.includes('under')) return 'warning';
  if (v.includes('fraud') || v.includes('reject') || v.includes('failed')) return 'danger';
  return 'muted';
}

/* ------------------------------------------------------------------ */
/*  Section Icons Map                                                  */
/* ------------------------------------------------------------------ */

const SECTION_ICONS: Record<string, React.ReactNode> = {
  recommended: <Sparkles className="h-4 w-4" />,
  popular: <TrendingUp className="h-4 w-4" />,
  hot_deals: <Flame className="h-4 w-4" />,
  trending: <TrendingUp className="h-4 w-4" />,
  also_viewed: <Eye className="h-4 w-4" />,
  sponsored: <DollarSign className="h-4 w-4" />,
  nearby: <MapPin className="h-4 w-4" />,
  favorites: <Heart className="h-4 w-4" />,
  top_rated: <Star className="h-4 w-4" />,
};

/* ------------------------------------------------------------------ */
/*  Feed Parcel Card                                                   */
/* ------------------------------------------------------------------ */

function FeedParcelCard({
  parcel,
  onTrackView,
  onParcelClick,
  onToggleFavorite,
}: {
  parcel: FeedParcel;
  onTrackView?: (parcelNumber: string) => void;
  onParcelClick?: (parcel: FeedParcel) => void;
  onToggleFavorite?: (parcel: FeedParcel) => void;
}) {
  const price = parcel.displayed_price || parcel.asking_price;
  const tone = statusTone(parcel.verification_status);

  const handleClick = useCallback(() => {
    onTrackView?.(parcel.parcel_number);
    onParcelClick?.(parcel);
  }, [parcel, onTrackView, onParcelClick]);

  return (
    <Card
      className="group cursor-pointer overflow-hidden bg-white/92 transition-all duration-200 hover:shadow-glow dark:bg-slate-800/90"
      onClick={handleClick}
    >
      <div className="relative aspect-[16/10] bg-gradient-to-br from-emerald-50 via-stone-50 to-teal-50 dark:from-emerald-950/30 dark:via-slate-900 dark:to-teal-950/30">
        {parcel.image_url ? (
          <img
            src={parcel.image_url}
            alt={parcel.parcel_number}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm font-semibold uppercase tracking-[0.24em] text-muted-foreground">
            No image
          </div>
        )}
        <div className="absolute left-3 top-3 flex max-w-[75%] flex-wrap gap-1.5">
          {parcel.is_promoted && <Badge tone="success">Featured</Badge>}
          {parcel.is_sponsored && (
            <Badge tone="warning" className="text-[9px]">
              {parcel.sponsor_label || 'Sponsored'}
            </Badge>
          )}
          {parcel.match_score != null && (
            <Badge tone="success">{Math.round(parcel.match_score)}% match</Badge>
          )}
        </div>
        <div className="absolute right-3 top-3 flex gap-1.5">
          <Badge tone={tone}>{parcel.status_badge || parcel.verification_status}</Badge>
        </div>
        {onToggleFavorite && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(parcel);
            }}
            className={cn(
              'absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-full bg-white/80 backdrop-blur-sm transition-colors hover:bg-white dark:bg-slate-800/80 dark:hover:bg-slate-700',
              parcel.is_favorited ? 'text-rose-500' : 'text-muted-foreground'
            )}
          >
            <Heart className={cn('h-4 w-4', parcel.is_favorited ? 'fill-current' : '')} />
          </button>
        )}
      </div>
      <CardContent className="space-y-3 p-4">
        <div>
          <h4 className="text-sm font-bold text-foreground">{parcel.parcel_number}</h4>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {parcel.county}, {parcel.constituency}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="rounded-lg bg-muted/60 px-2 py-1 dark:bg-slate-700/40">{parcel.land_use_type}</span>
          <span className="rounded-lg bg-muted/60 px-2 py-1 dark:bg-slate-700/40">{parcel.land_size}</span>
          {parcel.view_count != null && (
            <span className="flex items-center gap-1">
              <Eye className="h-3 w-3" /> {parcel.view_count}
            </span>
          )}
        </div>
        {price && (
          <div className="flex items-center justify-between">
            <span className="text-base font-black tracking-tight text-emerald-700 dark:text-emerald-400">
              {formatMoney(price)}
            </span>
            {parcel.price_trend === 'up' && (
              <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                <TrendingUp className="h-3 w-3" /> trending up
              </span>
            )}
          </div>
        )}
        <a
          href={parcel.details_url}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex h-9 w-full items-center justify-center rounded-full bg-primary px-4 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          View details
          <ArrowRight className="ml-2 h-3.5 w-3.5" />
        </a>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Collapsible Section                                                */
/* ------------------------------------------------------------------ */

function FeedSectionComponent({
  section,
  onTrackView,
  onParcelClick,
  onToggleFavorite,
  onLoadMore,
}: {
  section: FeedSection;
  onTrackView?: (parcelNumber: string) => void;
  onParcelClick?: (parcel: FeedParcel) => void;
  onToggleFavorite?: (parcel: FeedParcel) => void;
  onLoadMore?: (sectionId: string) => Promise<void>;
}) {
  const [collapsed, setCollapsed] = useState(section.defaultCollapsed ?? false);
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      await onLoadMore?.(section.id);
    } finally {
      setLoadingMore(false);
    }
  }, [onLoadMore, section.id, loadingMore]);

  // Horizontal scroll with mouse wheel
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (scrollRef.current) {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        scrollRef.current.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }
  }, []);

  if (!section.parcels.length) return null;

  return (
    <section className="space-y-3 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2 text-left transition-colors hover:text-emerald-700 dark:hover:text-emerald-400"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
            {section.icon || SECTION_ICONS[section.id] || <Star className="h-4 w-4" />}
          </span>
          <div>
            <h3 className="text-base font-bold text-foreground">{section.title}</h3>
            {section.subtitle && (
              <p className="text-xs text-muted-foreground">{section.subtitle}</p>
            )}
          </div>
          {section.collapsible !== false && (
            <span className="ml-1 text-muted-foreground">
              {collapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            </span>
          )}
        </button>
        <Badge tone="outline" className="text-[10px]">
          {section.parcels.length}
        </Badge>
      </div>

      {!collapsed && (
        <div
          ref={scrollRef}
          onWheel={handleWheel}
          className="scrollbar-thin flex gap-4 overflow-x-auto pb-2 sm:grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 sm:overflow-x-visible"
        >
          {section.parcels.map((parcel) => (
            <div key={parcel.parcel_number} className="min-w-[260px] sm:min-w-0 flex-shrink-0">
              <FeedParcelCard
                parcel={parcel}
                onTrackView={onTrackView}
                onParcelClick={onParcelClick}
                onToggleFavorite={onToggleFavorite}
              />
            </div>
          ))}
        </div>
      )}

      {!collapsed && onLoadMore && (
        <div className="flex justify-center pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="text-xs text-emerald-700 dark:text-emerald-400"
          >
            {loadingMore ? (
              <>
                <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                Loading more…
              </>
            ) : (
              'Show more'
            )}
          </Button>
        </div>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Pull-to-refresh wrapper                                            */
/* ------------------------------------------------------------------ */

function PullToRefresh({
  children,
  onRefresh,
  loading,
}: {
  children: React.ReactNode;
  onRefresh?: () => Promise<void>;
  loading?: boolean;
}) {
  const [pulling, setPulling] = useState(false);
  const [pullDistance, setPullDistance] = useState(0);
  const startYRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (containerRef.current?.scrollTop === 0) {
      startYRef.current = e.touches[0].clientY;
      setPulling(true);
    }
  }, []);

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!pulling) return;
      const diff = e.touches[0].clientY - startYRef.current;
      if (diff > 0 && containerRef.current?.scrollTop === 0) {
        setPullDistance(Math.min(diff * 0.5, 80));
      }
    },
    [pulling]
  );

  const handleTouchEnd = useCallback(async () => {
    if (pullDistance > 50 && onRefresh) {
      await onRefresh();
    }
    setPulling(false);
    setPullDistance(0);
  }, [pullDistance, onRefresh]);

  return (
    <div
      ref={containerRef}
      onTouchStart={onRefresh ? handleTouchStart : undefined}
      onTouchMove={onRefresh ? handleTouchMove : undefined}
      onTouchEnd={onRefresh ? handleTouchEnd : undefined}
      className="relative"
    >
      {pullDistance > 0 && (
        <div
          className="flex items-center justify-center text-emerald-600 dark:text-emerald-400 transition-all"
          style={{ height: pullDistance }}
        >
          <RefreshCw
            className={cn('h-5 w-5', pullDistance > 50 ? 'animate-spin' : '')}
          />
          <span className="ml-2 text-xs font-semibold">
            {pullDistance > 50 ? 'Release to refresh' : 'Pull down'}
          </span>
        </div>
      )}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function RecommendationsFeed({
  sections,
  onLoadMore,
  onRefresh,
  onTrackView,
  onParcelClick,
  onToggleFavorite,
  loading = false,
  className,
}: RecommendationsFeedProps) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await onRefresh?.();
    } finally {
      setRefreshing(false);
    }
  }, [onRefresh, refreshing]);

  // Infinite scroll: detect when user scrolls near bottom
  const sentinelRef = useRef<HTMLDivElement>(null);

  if (loading && !sections.length) {
    return (
      <div className={cn('space-y-8', className)}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-3 animate-pulse">
            <div className="h-6 w-48 rounded-lg bg-muted" />
            <div className="flex gap-4 overflow-hidden">
              {Array.from({ length: 3 }).map((_, j) => (
                <div key={j} className="min-w-[260px] flex-shrink-0">
                  <div className="aspect-[16/10] rounded-3xl bg-muted" />
                  <div className="mt-3 h-4 w-3/4 rounded bg-muted" />
                  <div className="mt-2 h-3 w-1/2 rounded bg-muted" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!sections.length) {
    return (
      <Card className="bg-white/92 dark:bg-slate-800/90">
        <CardContent className="p-8 text-center">
          <Sparkles className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <div className="text-lg font-bold text-foreground">No recommendations yet</div>
          <p className="mt-2 text-sm text-muted-foreground">
            Start browsing parcels to get personalized recommendations.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <PullToRefresh onRefresh={onRefresh ? handleRefresh : undefined} loading={refreshing}>
      <div className={cn('space-y-8', className)}>
        {sections.map((section) => (
          <FeedSectionComponent
            key={section.id}
            section={section}
            onTrackView={onTrackView}
            onParcelClick={onParcelClick}
            onToggleFavorite={onToggleFavorite}
            onLoadMore={onLoadMore}
          />
        ))}
        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-1" />
      </div>
    </PullToRefresh>
  );
}

/* ------------------------------------------------------------------ */
/*  API Integration Hooks                                              */
/* ------------------------------------------------------------------ */

export function useRecommendations(apiBaseUrl: string = '') {
  const [sections, setSections] = useState<FeedSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/recommendations/feed/`);
      if (!response.ok) throw new Error('Failed to fetch recommendations');
      const data = await response.json();

      const mapped: FeedSection[] = [
        {
          id: 'recommended',
          title: 'Recommended For You',
          subtitle: 'Based on your browsing history and preferences',
          icon: <Sparkles className="h-4 w-4" />,
          parcels: data.recommended || [],
        },
        {
          id: 'popular',
          title: 'Popular Near You',
          subtitle: `Top listings in ${data.popular_county || 'your area'}`,
          icon: <TrendingUp className="h-4 w-4" />,
          parcels: data.popular_parcels || [],
        },
        {
          id: 'hot_deals',
          title: 'Hot Deals',
          subtitle: 'Limited-time offers on verified parcels',
          icon: <Flame className="h-4 w-4" />,
          parcels: data.hot_deals || [],
        },
        {
          id: 'trending',
          title: 'Trending In Your Area',
          subtitle: 'Most viewed parcels this week',
          icon: <TrendingUp className="h-4 w-4" />,
          parcels: data.trending_in_target_area || [],
        },
        {
          id: 'also_viewed',
          title: 'People Also Viewed',
          subtitle: 'Parcels similar to ones you\'ve viewed',
          icon: <Eye className="h-4 w-4" />,
          parcels: data.people_also_viewed || [],
        },
        {
          id: 'sponsored',
          title: 'Sponsored Listings',
          subtitle: 'Promoted by verified sellers',
          icon: <DollarSign className="h-4 w-4" />,
          parcels: (data.sponsored_listings || []).map((p: FeedParcel) => ({
            ...p,
            is_sponsored: true,
            sponsor_label: 'Sponsored',
          })),
        },
      ].filter((s) => s.parcels.length > 0);

      setSections(mapped);
    } catch (err: any) {
      setError(err.message || 'Failed to load recommendations');
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  const trackView = useCallback(
    async (parcelNumber: string) => {
      try {
        await fetch(`${apiBaseUrl}/api/recommendations/track/view/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parcel_number: parcelNumber }),
        });
      } catch {
        // Silently fail tracking
      }
    },
    [apiBaseUrl]
  );

  const trackFavorite = useCallback(
    async (parcel: FeedParcel) => {
      try {
        await fetch(`${apiBaseUrl}/api/recommendations/track/favorite/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parcel_number: parcel.parcel_number }),
        });
      } catch {
        // Silently fail tracking
      }
    },
    [apiBaseUrl]
  );

  return {
    sections,
    loading,
    error,
    fetchRecommendations,
    trackView,
    trackFavorite,
  };
}

export default RecommendationsFeed;
