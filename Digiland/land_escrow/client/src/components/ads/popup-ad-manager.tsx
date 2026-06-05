import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowRight, BadgeCheck, Clock3, Eye, Film, MapPinned, Megaphone, MousePointerClick, Sparkles, X } from 'lucide-react';
import type { PopupAdCampaignSummary, PopupAdsPayload } from '../../types.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent } from '../ui/card.js';

interface PopupAdManagerProps {
  popupAds?: PopupAdsPayload | null;
  csrfToken?: string;
}

type SessionCampaignState = {
  seenAt?: string;
  dismissedAt?: string;
  showCount?: number;
  dismissCount?: number;
};

const STORAGE_KEY = 'digiland-popup-state';
const EVENT_URL = '/api/popup-ads/event/';

function readState(): { campaigns: Record<string, SessionCampaignState> } {
  if (typeof window === 'undefined') return { campaigns: {} };
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { campaigns: {} };
    const parsed = JSON.parse(raw) as { campaigns?: Record<string, SessionCampaignState> };
    return { campaigns: parsed.campaigns || {} };
  } catch {
    return { campaigns: {} };
  }
}

function writeState(state: { campaigns: Record<string, SessionCampaignState> }) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function isMobileViewport() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 767px)').matches;
}

function isRecentlySuppressed(state: SessionCampaignState | undefined, cooldownMinutes?: number) {
  if (!state?.seenAt) return false;
  const seen = new Date(state.seenAt).getTime();
  if (Number.isNaN(seen)) return false;
  const elapsedMinutes = (Date.now() - seen) / 60000;
  if (state.dismissCount && state.dismissCount >= 1) return true;
  if (cooldownMinutes && elapsedMinutes < cooldownMinutes) return true;
  return false;
}

function getEventType(campaign: PopupAdCampaignSummary) {
  const text = `${campaign.cta_text} ${campaign.headline}`.toLowerCase();
  if (/inquire|reserve|book|contact|message|talk|call|viewing|schedule/.test(text)) {
    return 'Lead';
  }
  return 'Click';
}

function mediaClassName(popup: PopupAdCampaignSummary) {
  if (popup.creative_image_url) {
    return 'bg-slate-950';
  }
  return 'bg-gradient-to-br from-slate-950 via-emerald-950 to-slate-900';
}

async function sendEvent(
  csrfToken: string | undefined,
  campaign: PopupAdCampaignSummary,
  eventType: string,
  extra?: Record<string, unknown>,
  buyerCategory?: string
) {
  if (typeof window === 'undefined') return;
  const payload = {
    campaign_id: campaign.id,
    event_type: eventType,
    placement_area: campaign.trigger || 'marketplace',
    page_context: campaign.trigger || 'marketplace',
    county_context: campaign.parcel?.county || '',
    intent_score: campaign.score || 0,
    relevance_score: campaign.score || 0,
    dwell_seconds: extra?.dwell_seconds || 0,
    buyer_category: buyerCategory || '',
    metadata: {
      popup_type: campaign.popup_type,
      trigger: campaign.trigger,
      headline: campaign.headline,
      ...extra,
    },
  };

  try {
    await fetch(EVENT_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(payload),
    });
  } catch {
    // Silently ignore telemetry failures; the popup should never block browsing.
  }
}

function PopupCard({
  popup,
  onClose,
  onCtaClick,
}: {
  popup: PopupAdCampaignSummary;
  onClose: () => void;
  onCtaClick: () => void;
}) {
  const trustTone = popup.seller.is_verified ? 'success' : 'warning';

  return (
    <div className="w-full max-w-xl overflow-hidden rounded-[2rem] border border-white/15 bg-slate-950/95 text-white shadow-[0_40px_100px_-30px_rgba(15,23,42,0.75)] backdrop-blur-xl">
      <div className={`relative ${mediaClassName(popup)}`}>
        {popup.creative_image_url ? (
          <img
            src={popup.creative_image_url}
            alt={popup.headline}
            className="absolute inset-0 h-full w-full object-cover opacity-70"
          />
        ) : null}
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/95 via-slate-950/70 to-slate-950/25" />
        <div className="relative flex items-start justify-between gap-3 p-5 sm:p-6">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="outline" className="border-white/15 bg-white/10 text-white">
                <Megaphone className="mr-1 h-3.5 w-3.5" />
                Sponsored
              </Badge>
              <Badge tone={trustTone} className="bg-white/10 text-white">
                <BadgeCheck className="mr-1 h-3.5 w-3.5" />
                {popup.seller.label}
              </Badge>
              {popup.trigger ? (
                <Badge tone="default" className="bg-emerald-500/20 text-emerald-100">
                  {popup.popup_type_label}
                </Badge>
              ) : null}
            </div>
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.3em] text-emerald-200/80">
                {popup.parcel.county} Discovery
              </div>
              <h3 className="mt-2 max-w-[26rem] text-2xl font-black tracking-tight text-white sm:text-3xl">
                {popup.headline}
              </h3>
              <p className="mt-2 max-w-[30rem] text-sm leading-7 text-slate-200/90">
                {popup.subheadline}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/10 text-white transition-colors hover:bg-white/20"
            aria-label="Dismiss popup"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <CardContent className="space-y-4 p-5 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-border/60 bg-white/5 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-300">Price</div>
            <div className="mt-1 text-sm font-extrabold text-white">{popup.parcel.displayed_price}</div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-white/5 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-300">Size</div>
            <div className="mt-1 text-sm font-extrabold text-white">{popup.parcel.land_size} acres</div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-white/5 p-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-300">Score</div>
            <div className="mt-1 text-sm font-extrabold text-white">{popup.score.toFixed(1)}</div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {popup.amenities.slice(0, 4).map((item) => (
            <div key={item.label} className="flex items-center gap-3 rounded-2xl border border-border/60 bg-white/5 px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-200">
                <MapPinned className="h-4 w-4" />
              </div>
              <div>
                <div className="text-xs font-bold uppercase tracking-[0.2em] text-slate-300">{item.label}</div>
                <div className="text-sm font-semibold text-white">{item.value}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          {popup.social_proof.map((proof) => (
            <div key={proof} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-100">
              <Eye className="h-3.5 w-3.5 text-emerald-300" />
              {proof}
            </div>
          ))}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-100">
            <Clock3 className="h-3.5 w-3.5 text-emerald-300" />
            {popup.scarcity_text}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            type="button"
            onClick={onCtaClick}
            className="h-12 rounded-full bg-emerald-500 px-5 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
          >
            {popup.cta_text}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            className="h-12 rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10"
          >
            Keep browsing
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-white/10 pt-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
          <span className="inline-flex items-center gap-1.5">
            <MousePointerClick className="h-3.5 w-3.5 text-emerald-300" />
            {popup.metrics.clicks} clicks
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-emerald-300" />
            {popup.metrics.leads} leads
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Film className="h-3.5 w-3.5 text-emerald-300" />
            {popup.parcel.land_use_type}
          </span>
        </div>
      </CardContent>
    </div>
  );
}

export function PopupAdManager({ popupAds, csrfToken }: PopupAdManagerProps) {
  const [active, setActive] = useState<PopupAdCampaignSummary | null>(null);
  const [visible, setVisible] = useState(false);
  const shownAtRef = useRef<number | null>(null);
  const portalTarget = typeof document !== 'undefined' ? document.body : null;

  const sessionState = useMemo(() => readState(), [visible]);

  useEffect(() => {
    if (!popupAds?.enabled || !popupAds.primary) return;
    const primary = popupAds.primary;
    const campaignState = readState().campaigns[primary.id];
    if (isRecentlySuppressed(campaignState, primary.frequency.cooldown_minutes)) return;

    const delay = isMobileViewport()
      ? Math.max(primary.display_delay_ms || popupAds.recommended_delay_ms || 2200, 2600)
      : (primary.display_delay_ms || popupAds.recommended_delay_ms || 2200);
    const timer = window.setTimeout(() => {
      setActive(primary);
      setVisible(true);
      shownAtRef.current = performance.now();

      const state = readState();
      const current = state.campaigns[primary.id] || {};
      state.campaigns[primary.id] = {
        ...current,
        seenAt: new Date().toISOString(),
        showCount: (current.showCount || 0) + 1,
        dismissCount: current.dismissCount || 0,
      };
      writeState(state);
      void sendEvent(csrfToken, primary, 'Impression', {
        placement_area: popupAds.placement || popupAds.page,
        dwell_seconds: 0,
        trigger: primary.trigger,
      }, popupAds.buyer_category);
    }, delay);

    return () => window.clearTimeout(timer);
  }, [csrfToken, popupAds, sessionState.campaigns]);

  useEffect(() => {
    if (!popupAds?.exit_candidate || active) return;
    const candidate = popupAds.exit_candidate;
    const onMouseOut = (event: MouseEvent) => {
      if (isMobileViewport()) return;
      if (event.clientY <= 0 && !visible) {
        const state = readState();
        const campaignState = state.campaigns[candidate.id];
        if (isRecentlySuppressed(campaignState, candidate.frequency.cooldown_minutes)) return;
        setActive(candidate);
        setVisible(true);
        shownAtRef.current = performance.now();
        state.campaigns[candidate.id] = {
          ...(state.campaigns[candidate.id] || {}),
          seenAt: new Date().toISOString(),
          showCount: ((state.campaigns[candidate.id] || {}).showCount || 0) + 1,
        };
        writeState(state);
        void sendEvent(csrfToken, candidate, 'Exit_Intent', {
          placement_area: popupAds.placement || popupAds.page,
          trigger: 'exit_intent',
          dwell_seconds: 0,
        }, popupAds.buyer_category);
      }
    };

    document.addEventListener('mouseout', onMouseOut);
    return () => document.removeEventListener('mouseout', onMouseOut);
  }, [active, csrfToken, popupAds, visible]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && active) {
        handleClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  function handleClose() {
    if (!active) return;
    const dwellSeconds = shownAtRef.current ? Math.max(0, (performance.now() - shownAtRef.current) / 1000) : 0;
    const state = readState();
    const current = state.campaigns[active.id] || {};
    state.campaigns[active.id] = {
      ...current,
      dismissedAt: new Date().toISOString(),
      dismissCount: (current.dismissCount || 0) + 1,
    };
    writeState(state);
    setVisible(false);
    void sendEvent(csrfToken, active, 'Dismissed', {
      placement_area: popupAds?.placement || popupAds?.page,
      dwell_seconds: dwellSeconds,
      trigger: active.trigger,
    }, popupAds?.buyer_category);
    window.setTimeout(() => setActive(null), 180);
  }

  function handleCtaClick() {
    if (!active) return;
    const dwellSeconds = shownAtRef.current ? Math.max(0, (performance.now() - shownAtRef.current) / 1000) : 0;
    const eventType = getEventType(active);
    void sendEvent(csrfToken, active, eventType, {
      placement_area: popupAds?.placement || popupAds?.page,
      dwell_seconds: dwellSeconds,
      trigger: active.trigger,
    }, popupAds?.buyer_category);

    setVisible(false);
    window.setTimeout(() => {
      setActive(null);
      window.location.href = active.landing_url;
    }, 150);
  }

  if (!popupAds?.enabled || (!active && !popupAds.primary && !popupAds.exit_candidate) || !portalTarget) return null;

  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[80] p-3 sm:p-6">
      {active ? (
        <div
          className={`pointer-events-auto ml-auto w-full max-w-xl transition-all duration-300 ease-out ${
            visible ? 'translate-y-0 opacity-100' : 'translate-y-5 opacity-0'
          }`}
        >
          <PopupCard popup={active} onClose={handleClose} onCtaClick={handleCtaClick} />
        </div>
      ) : null}
    </div>,
    portalTarget
  );
}
