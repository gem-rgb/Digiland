import React, { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import anime from 'animejs';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Droplets,
  Gavel,
  Gauge,
  Landmark,
  LoaderCircle,
  MapPin,
  MapPinned,
  Ruler,
  Search,
  ShieldCheck,
  Sprout,
  Sparkles,
  Ticket,
  TrendingUp,
  Upload,
  Users,
  WalletCards,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Input } from '../ui/input.js';
import { cn } from '../../lib/utils.js';
import type { PredictionResultSummary } from '../../types.js';
import { useCtaHover, useHeroEntrance, useHeroParticles } from '../../hooks/use-hero-animations.js';

type HeroStat = {
  label: string;
  value: string;
};

type HeroShowcaseProps = {
  notice?: string;
  stats?: HeroStat[];
  csrfToken?: string;
  isAuthenticated?: boolean;
};

type CurvePoint = {
  x: number;
  y: number;
};

type EcosystemCard = {
  title: string;
  description: string;
  icon: LucideIcon;
};

type MarketSignal = {
  label: string;
  value: string;
  note: string;
  top?: string;
  left?: string;
  right?: string;
  bottom?: string;
  xFactor: number;
  yFactor: number;
};

type LandUseValue = 'Residential' | 'Commercial' | 'Agricultural';

type LocationSuggestion = {
  label: string;
  county: string;
  constituency: string;
  region: string;
  description: string;
  landUse: LandUseValue;
  marketPosition: string;
  featured?: boolean;
};

const landUseOptions: Array<{
  value: LandUseValue;
  label: string;
  description: string;
  icon: LucideIcon;
}> = [
  {
    value: 'Residential',
    label: 'Residential',
    description: 'Homes, estates, and buyer-ready plots.',
    icon: Landmark,
  },
  {
    value: 'Commercial',
    label: 'Commercial',
    description: 'Retail, mixed-use, and service corridors.',
    icon: Building2,
  },
  {
    value: 'Agricultural',
    label: 'Agricultural',
    description: 'Farmland, agri-zones, and expansion land.',
    icon: Sprout,
  },
];

const locationSuggestions: LocationSuggestion[] = [
  {
    label: 'Karen',
    county: 'Nairobi',
    constituency: 'Karen',
    region: 'Nairobi metro',
    description: 'Premium residential parcels with strong buyer demand.',
    landUse: 'Residential',
    marketPosition: 'Premium zone',
    featured: true,
  },
  {
    label: 'Westlands',
    county: 'Nairobi',
    constituency: 'Westlands',
    region: 'Nairobi core',
    description: 'High-intent commercial and mixed-use demand.',
    landUse: 'Commercial',
    marketPosition: 'Premium zone',
  },
  {
    label: 'Kilimani',
    county: 'Nairobi',
    constituency: 'Kilimani',
    region: 'Urban growth',
    description: 'Compact parcels with steady premium positioning.',
    landUse: 'Residential',
    marketPosition: 'Premium zone',
  },
  {
    label: 'Langata',
    county: 'Nairobi',
    constituency: 'Langata',
    region: 'Metro fringe',
    description: 'Balanced demand across family and investment buyers.',
    landUse: 'Residential',
    marketPosition: 'Market average',
  },
  {
    label: 'Embakasi',
    county: 'Nairobi',
    constituency: 'Embakasi',
    region: 'Transit corridor',
    description: 'Transport-linked parcels with active enquiry flow.',
    landUse: 'Commercial',
    marketPosition: 'Growth corridor',
  },
  {
    label: 'Kitengela',
    county: 'Kajiado',
    constituency: 'Kitengela',
    region: 'South-east growth belt',
    description: 'Fast-moving suburban plots with expansion potential.',
    landUse: 'Residential',
    marketPosition: 'Growth corridor',
  },
  {
    label: 'Isinya',
    county: 'Kajiado',
    constituency: 'Isinya',
    region: 'South corridor',
    description: 'Strategic land near infrastructure-led expansion.',
    landUse: 'Agricultural',
    marketPosition: 'Emerging market',
  },
  {
    label: 'Athi River',
    county: 'Machakos',
    constituency: 'Athi River',
    region: 'Industrial belt',
    description: 'Commercial-ready land near logistics and industry.',
    landUse: 'Commercial',
    marketPosition: 'Growth corridor',
  },
  {
    label: 'Syokimau',
    county: 'Machakos',
    constituency: 'Syokimau',
    region: 'Commuter belt',
    description: 'High-conversion residential search destination.',
    landUse: 'Residential',
    marketPosition: 'Growth corridor',
  },
  {
    label: 'Juja',
    county: 'Kiambu',
    constituency: 'Juja',
    region: 'North corridor',
    description: 'Student and commuter demand with steady liquidity.',
    landUse: 'Residential',
    marketPosition: 'Growth corridor',
  },
  {
    label: 'Changamwe',
    county: 'Mombasa',
    constituency: 'Changamwe',
    region: 'Coastal logistics',
    description: 'Commercial parcels with port-adjacent demand.',
    landUse: 'Commercial',
    marketPosition: 'Coastal demand',
  },
  {
    label: 'Nyali',
    county: 'Mombasa',
    constituency: 'Nyali',
    region: 'Coastal premium',
    description: 'Premium residential and hospitality-led searches.',
    landUse: 'Residential',
    marketPosition: 'Premium zone',
  },
  {
    label: 'Mvita',
    county: 'Mombasa',
    constituency: 'Mvita',
    region: 'Urban coast',
    description: 'Central coastal land with active market signalling.',
    landUse: 'Commercial',
    marketPosition: 'Coastal demand',
  },
  {
    label: 'Eldoret',
    county: 'Uasin Gishu',
    constituency: 'Eldoret',
    region: 'Western growth',
    description: 'Regional hub with broad residential and commercial appeal.',
    landUse: 'Commercial',
    marketPosition: 'Market average',
  },
  {
    label: 'Kapsabet',
    county: 'Nandi',
    constituency: 'Kapsabet',
    region: 'Highland market',
    description: 'Emerging value opportunities with measured growth.',
    landUse: 'Agricultural',
    marketPosition: 'Emerging market',
  },
];

const defaultLocationSuggestion = locationSuggestions[0]!;

const etaModelFacts = [
  { label: 'Coverage', value: '47 counties' },
  { label: 'Feature set', value: '8 market signals' },
  { label: 'Engine', value: 'Random Forest' },
];

const curveAnchors: Array<{
  x: number;
  y: number;
  amplitude: number;
  frequency: number;
  phase: number;
}> = [
  { x: 0, y: 228, amplitude: 3, frequency: 0.7, phase: 0.2 },
  { x: 112, y: 212, amplitude: 6, frequency: 0.85, phase: 0.6 },
  { x: 224, y: 190, amplitude: 4, frequency: 0.6, phase: 1.15 },
  { x: 356, y: 146, amplitude: 5, frequency: 0.78, phase: 1.8 },
  { x: 498, y: 108, amplitude: 7, frequency: 0.56, phase: 2.1 },
  { x: 620, y: 124, amplitude: 4, frequency: 0.68, phase: 2.8 },
  { x: 720, y: 88, amplitude: 2, frequency: 0.45, phase: 3.2 },
];

const ecosystemCards: EcosystemCard[] = [
  { title: 'Buy Land', description: 'Verified listings, guided onboarding, and buyer confidence from first browse to close.', icon: Landmark },
  { title: 'Marketplace', description: 'Search, compare, and move through a market built for high-intent land buyers.', icon: BarChart3 },
  { title: 'Virtual Cities', description: 'Map future districts, premium zones, and digital growth corridors.', icon: MapPin },
  { title: 'AI Agents', description: 'Automate valuation, review, and support with secure agentic workflows.', icon: Sparkles },
  { title: 'Land Analytics', description: 'Track demand signals, price movement, and verification trends in real time.', icon: BarChart3 },
  { title: 'Development Tools', description: 'Use the platform to power onboarding, inspection, and workflow automation.', icon: Upload },
  { title: 'Revenue Streams', description: 'Unlock promotion, escrow, and monetisation paths across the ecosystem.', icon: WalletCards },
  { title: 'Governance', description: 'Coordinate approvals, reviews, and policy-driven controls with confidence.', icon: Gavel },
  { title: 'NFT Assets', description: 'Prepare for tokenised asset experiences, provenance, and digital ownership layers.', icon: Ticket },
  { title: 'Infrastructure', description: 'Trust, identity, and operational plumbing for enterprise-grade land commerce.', icon: ShieldCheck },
];

const marketSignals: MarketSignal[] = [
  {
    label: 'Metro core',
    value: 'High liquidity',
    note: 'Premium parcels move fastest',
    top: '10%',
    left: '6%',
    xFactor: 0.45,
    yFactor: 0.22,
  },
  {
    label: 'Growth belt',
    value: 'Balanced demand',
    note: 'Search volume keeps climbing',
    top: '18%',
    right: '5%',
    xFactor: -0.38,
    yFactor: 0.18,
  },
  {
    label: 'Coastal demand',
    value: 'Commercial lift',
    note: 'Port-linked parcels stay active',
    bottom: '20%',
    right: '9%',
    xFactor: -0.3,
    yFactor: -0.26,
  },
  {
    label: 'Emerging towns',
    value: 'Rising interest',
    note: 'Expansion zones widen the funnel',
    bottom: '12%',
    left: '19%',
    xFactor: 0.28,
    yFactor: -0.24,
  },
];

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

const kshFormatter = new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 0,
});

function formatKsh(value: number | string | null | undefined) {
  if (value == null || value === '') {
    return 'KSh 0';
  }

  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return `KSh ${kshFormatter.format(Number.isFinite(parsed) ? parsed : 0)}`;
}

function parseNumeric(value: number | string | null | undefined) {
  if (value == null || value === '') {
    return 0;
  }

  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function parsePercent(value?: string | null) {
  if (!value) return 0;
  const parsed = Number.parseFloat(String(value).replace('%', ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function deriveConfidenceLabel(result: PredictionResultSummary | null) {
  if (!result || result.error) {
    return 'Preliminary Estimate';
  }

  const accuracy = parsePercent(result.model_accuracy);
  const low = parseNumeric(result.confidence_low);
  const high = parseNumeric(result.confidence_high);
  const spread = low > 0 && high > 0 ? (high - low) / Math.max(low, 1) : 1;

  if (accuracy >= 78 && spread <= 0.55) {
    return 'High Confidence';
  }

  if (accuracy >= 60 && spread <= 0.8) {
    return 'Medium Confidence';
  }

  return 'Preliminary Estimate';
}

function deriveMarketPosition(result: PredictionResultSummary | null, suggestion?: LocationSuggestion | null) {
  if (!result || result.error) {
    return suggestion?.marketPosition || 'Market average';
  }

  const price = parseNumeric(result.price_per_acre);
  const low = parseNumeric(result.confidence_low);
  const high = parseNumeric(result.confidence_high);

  if (low && high && price >= high * 0.94) {
    return 'Premium zone';
  }

  if (low && high && price <= low * 1.06) {
    return 'Below market average';
  }

  return suggestion?.marketPosition || 'Market average';
}

function getCookie(name: string) {
  if (typeof document === 'undefined') return '';

  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length < 2) return '';
  return parts.pop()?.split(';').shift() || '';
}

function extractPredictionFromHtml(html: string): PredictionResultSummary | null {
  if (typeof DOMParser === 'undefined') {
    return null;
  }

  const doc = new DOMParser().parseFromString(html, 'text/html');
  const script = doc.getElementById('digiland-bootstrap');
  if (!script) {
    return null;
  }

  try {
    const payload = JSON.parse(script.textContent || '{}') as {
      prediction_page?: { prediction?: PredictionResultSummary | null } | null;
    };
    return payload.prediction_page?.prediction || null;
  } catch {
    return null;
  }
}

function buildSmoothPath(points: CurvePoint[]) {
  if (!points.length) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  const commands = [`M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`];

  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[index - 1] ?? points[index];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[index + 2] ?? p2;

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    commands.push(
      `C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`
    );
  }

  return commands.join(' ');
}

function buildAreaPath(points: CurvePoint[], baseY: number) {
  if (!points.length) return '';

  const linePath = buildSmoothPath(points);
  const first = points[0];
  const last = points[points.length - 1];

  return `${linePath} L ${last.x.toFixed(1)} ${baseY.toFixed(1)} L ${first.x.toFixed(1)} ${baseY.toFixed(1)} Z`;
}

function getCurveFrame(time: number) {
  const points = curveAnchors.map((anchor, index) => {
    const drift = Math.sin(time * anchor.frequency + anchor.phase) * anchor.amplitude;
    const premiumLift = index === 4 ? Math.max(0, Math.sin(time * 0.54 + 1.2)) * 10 : 0;
    const momentum = index >= 3 ? Math.sin(time * 0.33 + index * 0.4) * 2.8 : 0;
    return {
      x: anchor.x,
      y: clamp(anchor.y - drift - premiumLift - momentum, 38, 260),
    };
  });

  const line = buildSmoothPath(points);
  const area = buildAreaPath(points, 272);
  const peak = points[4]!;
  const latest = points[points.length - 1]!;

  return { line, area, peak, latest, points };
}

function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', update);
      return () => media.removeEventListener('change', update);
    }

    media.addListener(update);
    return () => media.removeListener(update);
  }, []);

  return reducedMotion;
}

function useHeroParallax(ref: React.RefObject<HTMLElement>, reducedMotion: boolean) {
  useEffect(() => {
    const node = ref.current;
    if (!node || reducedMotion) {
      return;
    }

    let frame = 0;
    let nextX = 0;
    let nextY = 0;

    const apply = () => {
      node.style.setProperty('--hero-pointer-x', `${nextX.toFixed(2)}`);
      node.style.setProperty('--hero-pointer-y', `${nextY.toFixed(2)}`);
      frame = 0;
    };

    const schedule = (x: number, y: number) => {
      nextX = clamp(x, -20, 20);
      nextY = clamp(y, -20, 20);

      if (!frame) {
        frame = window.requestAnimationFrame(apply);
      }
    };

    const handleMove = (event: PointerEvent) => {
      const rect = node.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const dx = ((event.clientX - rect.left) / rect.width - 0.5) * 20;
      const dy = ((event.clientY - rect.top) / rect.height - 0.5) * 20;
      schedule(dx, dy);
    };

    const handleLeave = () => schedule(0, 0);

    node.addEventListener('pointermove', handleMove, { passive: true });
    node.addEventListener('pointerleave', handleLeave);

    return () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      node.removeEventListener('pointermove', handleMove);
      node.removeEventListener('pointerleave', handleLeave);
    };
  }, [ref, reducedMotion]);
}

function useMarketCurveMotion(reducedMotion: boolean) {
  const lineRef = useRef<SVGPathElement>(null);
  const areaRef = useRef<SVGPathElement>(null);
  const peakRef = useRef<SVGCircleElement>(null);
  const latestRef = useRef<SVGCircleElement>(null);

  useEffect(() => {
    const line = lineRef.current;
    const area = areaRef.current;
    const peak = peakRef.current;
    const latest = latestRef.current;

    if (!line || !area || !peak || !latest) {
      return;
    }

    const initial = getCurveFrame(0);
    line.setAttribute('d', initial.line);
    area.setAttribute('d', initial.area);
    peak.setAttribute('cx', `${initial.peak.x}`);
    peak.setAttribute('cy', `${initial.peak.y}`);
    latest.setAttribute('cx', `${initial.latest.x}`);
    latest.setAttribute('cy', `${initial.latest.y}`);

    if (reducedMotion) {
      return;
    }

    let frame = 0;
    let start = 0;

    const tick = (now: number) => {
      if (!start) start = now;
      const time = (now - start) / 1000;
      const frameState = getCurveFrame(time);

      line.setAttribute('d', frameState.line);
      area.setAttribute('d', frameState.area);
      peak.setAttribute('cx', `${frameState.peak.x}`);
      peak.setAttribute('cy', `${frameState.peak.y}`);
      peak.setAttribute('r', `${9 + Math.sin(time * 1.4) * 1.1}`);
      latest.setAttribute('cx', `${frameState.latest.x}`);
      latest.setAttribute('cy', `${frameState.latest.y}`);
      latest.setAttribute('r', `${5.4 + Math.sin(time * 1.9) * 0.6}`);

      frame = window.requestAnimationFrame(tick);
    };

    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [reducedMotion]);

  return { lineRef, areaRef, peakRef, latestRef };
}

function useEcosystemReveal(sectionRef: React.RefObject<HTMLElement>, reducedMotion: boolean) {
  useEffect(() => {
    const section = sectionRef.current;
    if (!section) return;

    const heading = section.querySelector<HTMLElement>('.ecosystem-heading');
    const subtitle = section.querySelector<HTMLElement>('.ecosystem-subtitle');
    const cards = Array.from(section.querySelectorAll<HTMLElement>('.ecosystem-card'));

    if (reducedMotion) {
      if (heading) {
        heading.style.opacity = '1';
        heading.style.transform = 'none';
      }
      if (subtitle) {
        subtitle.style.opacity = '1';
        subtitle.style.transform = 'none';
      }
      cards.forEach((card) => {
        card.style.opacity = '1';
        card.style.transform = 'none';
      });
      return;
    }

    if (typeof IntersectionObserver === 'undefined') {
      heading?.style.setProperty('opacity', '1');
      heading?.style.setProperty('transform', 'none');
      subtitle?.style.setProperty('opacity', '1');
      subtitle?.style.setProperty('transform', 'none');
      cards.forEach((card) => {
        card.style.opacity = '1';
        card.style.transform = 'none';
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          if (heading) {
            anime({
              targets: heading,
              opacity: [0, 1],
              translateY: [18, 0],
              duration: 700,
              easing: 'easeOutCubic',
            });
          }

          if (subtitle) {
            anime({
              targets: subtitle,
              opacity: [0, 1],
              translateY: [14, 0],
              delay: 90,
              duration: 650,
              easing: 'easeOutCubic',
            });
          }

          anime({
            targets: cards,
            opacity: [0, 1],
            translateY: [24, 0],
            scale: [0.965, 1],
            delay: anime.stagger(80, { start: 170 }),
            duration: 700,
            easing: 'easeOutCubic',
          });

          observer.disconnect();
        });
      },
      { threshold: 0.22 }
    );

    observer.observe(section);
    return () => observer.disconnect();
  }, [reducedMotion, sectionRef]);
}

function useAutoFeaturedIndex(count: number, reducedMotion: boolean) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (reducedMotion || count <= 1) {
      return;
    }

    const interval = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % count);
    }, 2600);

    return () => window.clearInterval(interval);
  }, [count, reducedMotion]);

  return activeIndex;
}

function LandPriceEstimatorPanel({
  notice,
  stats = [],
  csrfToken,
  isAuthenticated = false,
  ctaRef,
}: {
  notice?: string;
  stats?: HeroStat[];
  csrfToken?: string;
  isAuthenticated?: boolean;
  ctaRef: React.RefObject<HTMLDivElement>;
}) {
  const reducedMotion = useReducedMotionPreference();
  const suggestionsWrapRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const [locationQuery, setLocationQuery] = useState(defaultLocationSuggestion.label);
  const [selectedSuggestion, setSelectedSuggestion] = useState<LocationSuggestion | null>(defaultLocationSuggestion);
  const [county, setCounty] = useState(defaultLocationSuggestion.county);
  const [constituency, setConstituency] = useState(defaultLocationSuggestion.constituency);
  const [landUse, setLandUse] = useState<LandUseValue>(defaultLocationSuggestion.landUse);
  const [sizeAcres, setSizeAcres] = useState('0.50');
  const [roadAccess, setRoadAccess] = useState(true);
  const [waterAccess, setWaterAccess] = useState(true);
  const [electricityAccess, setElectricityAccess] = useState(true);
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [prediction, setPrediction] = useState<PredictionResultSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [animatedTotal, setAnimatedTotal] = useState(0);

  const filteredSuggestions = useMemo(() => {
    const search = locationQuery.trim().toLowerCase();
    const ranked = locationSuggestions.filter((suggestion) => {
      if (!search) return true;
      return [
        suggestion.label,
        suggestion.county,
        suggestion.constituency,
        suggestion.region,
        suggestion.description,
        suggestion.marketPosition,
      ].some((value) => value.toLowerCase().includes(search));
    });

    return ranked.slice(0, 8);
  }, [locationQuery]);

  useEffect(() => {
    if (!isSuggestionsOpen) {
      return;
    }

    setHighlightedIndex((current) => clamp(current, 0, Math.max(0, filteredSuggestions.length - 1)));
  }, [filteredSuggestions.length, isSuggestionsOpen]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      if (!suggestionsWrapRef.current?.contains(event.target as Node)) {
        setIsSuggestionsOpen(false);
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, []);

  useEffect(() => {
    if (!prediction || prediction.error) {
      setAnimatedTotal(0);
      return;
    }

    const target = parseNumeric(prediction.total_value);
    if (reducedMotion) {
      setAnimatedTotal(target);
      return;
    }

    const tween = { value: 0 };
    const animation = anime({
      targets: tween,
      value: target,
      round: 1,
      duration: 900,
      easing: 'easeOutCubic',
      update: () => setAnimatedTotal(Math.round(tween.value)),
    });

    return () => animation.pause();
  }, [prediction?.total_value, prediction?.error, reducedMotion]);

  useEffect(() => {
    const node = resultsRef.current;
    if (!node || !showResults || !prediction) {
      return;
    }

    if (reducedMotion) {
      node.querySelectorAll<HTMLElement>('.estimator-result-item').forEach((element) => {
        element.style.opacity = '1';
        element.style.transform = 'none';
      });
      return;
    }

    const itemTargets = node.querySelectorAll<HTMLElement>('.estimator-result-item');
    const highlightTargets = node.querySelectorAll<HTMLElement>('.estimator-result-highlight');

    anime({
      targets: highlightTargets,
      opacity: [0, 1],
      scale: [0.98, 1],
      duration: 620,
      easing: 'easeOutCubic',
    });

    anime({
      targets: itemTargets,
      opacity: [0, 1],
      translateY: [14, 0],
      scale: [0.985, 1],
      delay: anime.stagger(70, { start: 120 }),
      duration: 620,
      easing: 'easeOutCubic',
    });
  }, [prediction, reducedMotion, showResults]);

  function markDirty() {
    setShowResults(false);
    setPrediction(null);
    setError(null);
  }

  function selectSuggestion(suggestion: LocationSuggestion) {
    setSelectedSuggestion(suggestion);
    setLocationQuery(suggestion.label);
    setCounty(suggestion.county);
    setConstituency(suggestion.constituency);
    setLandUse(suggestion.landUse);
    setIsSuggestionsOpen(false);
    markDirty();
  }

  function resolveSuggestionFromQuery() {
    const search = locationQuery.trim().toLowerCase();
    if (!search) {
      return null;
    }

    return (
      filteredSuggestions.find((suggestion) =>
        [suggestion.label, suggestion.county, suggestion.constituency].some(
          (value) => value.toLowerCase() === search
        )
      ) ||
      locationSuggestions.find((suggestion) =>
        [suggestion.label, suggestion.county, suggestion.constituency].some(
          (value) => value.toLowerCase() === search
        )
      ) ||
      null
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const suggestion = selectedSuggestion || resolveSuggestionFromQuery();
    const resolvedCounty = suggestion?.county || county.trim();
    const resolvedConstituency = suggestion?.constituency || constituency.trim() || resolvedCounty;

    if (!resolvedCounty || !resolvedConstituency) {
      setError('Choose a Kenyan location from the suggestions to run the live estimate.');
      return;
    }

    const parsedSize = parseNumeric(sizeAcres);
    if (parsedSize <= 0) {
      setError('Enter a valid land size in acres.');
      return;
    }

    setCounty(resolvedCounty);
    setConstituency(resolvedConstituency);
    setIsLoading(true);
    setError(null);

    try {
      const body = new URLSearchParams();
      body.set('county', resolvedCounty);
      body.set('constituency', resolvedConstituency);
      body.set('land_use', landUse);
      body.set('size_acres', String(parsedSize));
      if (roadAccess) body.set('has_road_access', 'on');
      if (waterAccess) body.set('has_water', 'on');
      if (electricityAccess) body.set('has_electricity', 'on');

      const response = await fetch('/price-prediction/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'X-CSRFToken': csrfToken || getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: body.toString(),
      });

      const html = await response.text();
      const result = extractPredictionFromHtml(html);

      if (!result) {
        if (response.redirected || response.url.includes('/accounts/login')) {
          setError('Sign in to run a live DigiLand valuation.');
        } else {
          setError('The valuation service returned an unexpected response.');
        }
        return;
      }

      setPrediction(result);
      setShowResults(true);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to reach the valuation service.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleLocationKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!isSuggestionsOpen && event.key !== 'ArrowDown') {
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIsSuggestionsOpen(true);
      setHighlightedIndex((current) => clamp(current + 1, 0, Math.max(0, filteredSuggestions.length - 1)));
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setHighlightedIndex((current) => clamp(current - 1, 0, Math.max(0, filteredSuggestions.length - 1)));
      return;
    }

    if (event.key === 'Enter') {
      if (isSuggestionsOpen && filteredSuggestions[highlightedIndex]) {
        event.preventDefault();
        selectSuggestion(filteredSuggestions[highlightedIndex]!);
      }
      return;
    }

    if (event.key === 'Escape') {
      setIsSuggestionsOpen(false);
    }
  }

  const confidenceLabel = deriveConfidenceLabel(prediction);
  const marketPosition = deriveMarketPosition(prediction, selectedSuggestion);
  const comparisonRows = prediction?.comparisons?.slice(0, 3) || [];
  const displayedTotal = animatedTotal || parseNumeric(prediction?.total_value);

  const helperText = selectedSuggestion
    ? `${selectedSuggestion.region} · ${selectedSuggestion.marketPosition}`
    : 'Search by county, estate, or corridor.';

  return (
    <Card
      className="hero-right-card relative overflow-hidden !border-white/15 !bg-slate-950/90 !text-white shadow-[0_36px_90px_-34px_rgba(5,150,105,0.58)] backdrop-blur-2xl"
      style={{
        opacity: 0,
        transform:
          'translate3d(calc(var(--hero-pointer-x, 0) * 0.45px), calc(var(--hero-pointer-y, 0) * 0.34px), 0)',
      }}
    >
      <div
        className="hero-ambient-fx absolute -right-16 -top-16 h-60 w-60 rounded-full bg-emerald-400/18 blur-3xl"
        style={{
          opacity: 0,
          transform:
            'translate3d(calc(var(--hero-pointer-x, 0) * 0.45px), calc(var(--hero-pointer-y, 0) * 0.34px), 0)',
          animationDelay: '0.15s',
          animationDuration: '18s',
        }}
      />
      <div
        className="hero-ambient-fx absolute -left-20 bottom-0 h-72 w-72 rounded-full bg-cyan-400/12 blur-3xl"
        style={{
          opacity: 0,
          transform:
            'translate3d(calc(var(--hero-pointer-x, 0) * -0.2px), calc(var(--hero-pointer-y, 0) * -0.14px), 0)',
          animationDelay: '1s',
          animationDuration: '22s',
        }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.12),_transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.32),rgba(2,6,23,0.58))]" />
      <div className="hero-noise-overlay absolute inset-0 opacity-[0.16]" />
      <div className="hero-grid-overlay absolute inset-0 opacity-[0.08]" />

      <CardContent className="relative z-10 space-y-5 p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="hero-entrance-item" style={{ opacity: 0 }}>
              <Badge tone="outline" className="border-emerald-300/30 bg-emerald-300/10 text-emerald-100">
                {notice || 'Live land price estimator'}
              </Badge>
            </div>
            <div className="hero-headline hero-entrance-item" style={{ opacity: 0 }}>
              <CardTitle className="max-w-2xl text-2xl font-black tracking-tight text-white sm:text-[1.75rem]">
                Estimate Land Value Instantly
              </CardTitle>
            </div>
            <div className="hero-entrance-item" style={{ opacity: 0 }}>
              <CardDescription className="max-w-2xl text-sm leading-7 text-slate-300">
                DigiLand uses location intelligence, parcel characteristics, and the existing ML pricing engine to
                return a live estimate with confidence bands and comparable market context.
              </CardDescription>
            </div>
          </div>

          <div className="rounded-[1.3rem] border border-white/10 bg-white/6 px-4 py-3 text-right backdrop-blur-xl">
            <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-200/80">
              Location precision
            </div>
            <div className="mt-1 text-2xl font-black tracking-tight text-white">Live</div>
            <div className="mt-1 text-[11px] text-slate-300">Search + ML valuation</div>
          </div>
        </div>

        <div className="hero-entrance-item flex flex-wrap gap-2" style={{ opacity: 0 }}>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-200 backdrop-blur-xl">
            <MapPinned className="h-3.5 w-3.5 text-emerald-300" />
            Kenya location search
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-200 backdrop-blur-xl">
            <Gauge className="h-3.5 w-3.5 text-emerald-300" />
            Confidence intervals
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-3 py-1.5 text-xs font-semibold text-slate-200 backdrop-blur-xl">
            <TrendingUp className="h-3.5 w-3.5 text-emerald-300" />
            Market context
          </div>
        </div>

        {!showResults || !prediction ? (
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div ref={suggestionsWrapRef} className="hero-entrance-item space-y-2" style={{ opacity: 0 }}>
              <label htmlFor="land-estimator-location" className="text-sm font-semibold text-white">
                Location
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  id="land-estimator-location"
                  value={locationQuery}
                  onChange={(event) => {
                    setLocationQuery(event.target.value);
                    setSelectedSuggestion(null);
                    setCounty('');
                    setConstituency('');
                    setIsSuggestionsOpen(true);
                    setHighlightedIndex(0);
                    markDirty();
                  }}
                  onFocus={() => setIsSuggestionsOpen(true)}
                  onKeyDown={handleLocationKeyDown}
                  placeholder="Search county, estate, or town"
                  autoComplete="off"
                  aria-autocomplete="list"
                  aria-expanded={isSuggestionsOpen}
                  aria-controls="land-estimator-suggestions"
                  aria-activedescendant={
                    isSuggestionsOpen && filteredSuggestions[highlightedIndex]
                      ? `land-estimator-option-${highlightedIndex}`
                      : undefined
                  }
                  disabled={isLoading}
                  className="border-white/12 bg-slate-900/72 pl-11 pr-11 text-white placeholder:text-slate-500 focus-visible:ring-emerald-400/50"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 transition hover:text-white"
                  aria-label={isSuggestionsOpen ? 'Collapse suggestions' : 'Expand suggestions'}
                  onClick={() => setIsSuggestionsOpen((open) => !open)}
                >
                  {isSuggestionsOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
              </div>

              <p className="text-xs leading-6 text-slate-400">{helperText}</p>

              {isSuggestionsOpen ? (
                <div
                  id="land-estimator-suggestions"
                  role="listbox"
                  aria-label="Location suggestions"
                  className="max-h-72 overflow-auto rounded-[1.5rem] border border-white/10 bg-slate-900/90 p-2 shadow-[0_24px_50px_-28px_rgba(15,23,42,0.8)] backdrop-blur-xl"
                >
                  {filteredSuggestions.length ? (
                    filteredSuggestions.map((suggestion, index) => {
                      const active = index === highlightedIndex;
                      const selected = selectedSuggestion?.label === suggestion.label;

                      return (
                        <button
                          key={`${suggestion.label}-${suggestion.county}`}
                          id={`land-estimator-option-${index}`}
                          type="button"
                          role="option"
                          aria-selected={selected}
                          onMouseEnter={() => setHighlightedIndex(index)}
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={() => selectSuggestion(suggestion)}
                          className={cn(
                            'flex w-full items-start gap-3 rounded-[1.15rem] px-4 py-3 text-left transition duration-200',
                            active
                              ? 'bg-emerald-400/12 text-white'
                              : 'text-slate-200 hover:bg-white/6 hover:text-white'
                          )}
                        >
                          <div
                            className={cn(
                              'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border transition',
                              suggestion.featured
                                ? 'border-emerald-300/40 bg-emerald-400/15 text-emerald-200'
                                : 'border-white/10 bg-white/6 text-slate-300'
                            )}
                          >
                            <MapPin className="h-4 w-4" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="font-semibold text-inherit">{suggestion.label}</div>
                              <Badge tone="outline" className="border-white/10 bg-white/6 text-[10px] uppercase tracking-[0.2em] text-slate-300">
                                {suggestion.marketPosition}
                              </Badge>
                            </div>
                            <div className="mt-1 text-xs text-slate-400">
                              {suggestion.constituency}, {suggestion.county} · {suggestion.region}
                            </div>
                            <div className="mt-2 text-xs leading-6 text-slate-500">{suggestion.description}</div>
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="rounded-[1.15rem] border border-dashed border-white/10 px-4 py-5 text-sm text-slate-400">
                      No exact match yet. Try a county, town, estate, or corridor in Kenya.
                    </div>
                  )}
                </div>
              ) : null}

              {selectedSuggestion ? (
                <div className="flex flex-wrap gap-2 pt-1">
                  <Badge tone="outline" className="border-white/10 bg-white/6 text-slate-200">
                    {selectedSuggestion.county}
                  </Badge>
                  <Badge tone="outline" className="border-white/10 bg-white/6 text-slate-200">
                    {selectedSuggestion.constituency}
                  </Badge>
                  <Badge tone="outline" className="border-white/10 bg-white/6 text-slate-200">
                    {selectedSuggestion.marketPosition}
                  </Badge>
                </div>
              ) : null}
            </div>

            <div className="hero-entrance-item space-y-2" style={{ opacity: 0 }}>
              <div className="flex items-center justify-between gap-3">
                <label className="text-sm font-semibold text-white">Land use</label>
                <span className="text-xs uppercase tracking-[0.22em] text-slate-500">Match the parcel profile</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                {landUseOptions.map((option) => {
                  const active = landUse === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        setLandUse(option.value);
                        markDirty();
                      }}
                      aria-pressed={active}
                      className={cn(
                        'flex flex-col gap-1 rounded-[1.35rem] border px-4 py-3 text-left transition duration-200',
                        active
                          ? 'border-emerald-300/50 bg-emerald-400/10 text-white shadow-[0_18px_38px_-28px_rgba(16,185,129,0.45)]'
                          : 'border-white/10 bg-white/6 text-slate-200 hover:border-emerald-300/30 hover:bg-white/10 hover:text-white'
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <option.icon className={cn('h-4 w-4', active ? 'text-emerald-200' : 'text-emerald-300/80')} />
                        {active ? <CheckCircle2 className="h-4 w-4 text-emerald-200" /> : null}
                      </div>
                      <div className="text-sm font-semibold">{option.label}</div>
                      <div className="text-xs leading-6 text-slate-400">{option.description}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hero-entrance-item grid gap-3 sm:grid-cols-2" style={{ opacity: 0 }}>
              <div className="space-y-2">
                <label htmlFor="land-estimator-size" className="text-sm font-semibold text-white">
                  Land size
                </label>
                <div className="relative">
                  <Ruler className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    id="land-estimator-size"
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={sizeAcres}
                    onChange={(event) => {
                      setSizeAcres(event.target.value);
                      markDirty();
                    }}
                    disabled={isLoading}
                    className="border-white/12 bg-slate-900/72 pl-11 pr-20 text-white placeholder:text-slate-500 focus-visible:ring-emerald-400/50"
                  />
                  <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                    acres
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <ShieldCheck className="h-4 w-4 text-emerald-300" />
                  Infrastructure
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: 'Road', value: roadAccess, setter: setRoadAccess, icon: MapPinned },
                    { label: 'Water', value: waterAccess, setter: setWaterAccess, icon: Droplets },
                    { label: 'Power', value: electricityAccess, setter: setElectricityAccess, icon: Sparkles },
                  ].map((item) => {
                    const active = item.value;
                    return (
                      <button
                        key={item.label}
                        type="button"
                        onClick={() => {
                          item.setter((current: boolean) => !current);
                          markDirty();
                        }}
                        aria-pressed={active}
                        className={cn(
                          'flex flex-col items-center justify-center gap-1 rounded-[1.2rem] border px-3 py-3 text-center transition duration-200',
                          active
                            ? 'border-emerald-300/50 bg-emerald-400/10 text-white'
                            : 'border-white/10 bg-white/6 text-slate-300 hover:border-emerald-300/30 hover:bg-white/10 hover:text-white'
                        )}
                      >
                        <item.icon className={cn('h-4 w-4', active ? 'text-emerald-200' : 'text-emerald-300/80')} />
                        <span className="text-xs font-semibold">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div ref={ctaRef} className="hero-entrance-item flex flex-col gap-3 pt-2 sm:flex-row" style={{ opacity: 0 }}>
              <Button
                type="submit"
                disabled={isLoading}
                className="hero-cta-btn h-12 w-full rounded-full bg-primary px-6 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 sm:w-auto"
              >
                {isLoading ? (
                  <>
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                    Calculating...
                  </>
                ) : (
                  <>
                    Estimate Value
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>

              <Button
                type="button"
                variant="outline"
                disabled={isLoading}
                className="hero-cta-btn h-12 w-full rounded-full border-white/10 bg-white/6 text-white hover:bg-white/10 sm:w-auto"
                onClick={() => {
                  setShowResults(false);
                  setPrediction(null);
                }}
              >
                Reset
              </Button>
            </div>

            {error ? (
              <div className="hero-entrance-item rounded-[1.35rem] border border-rose-300/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-100" style={{ opacity: 0 }}>
                {error}
              </div>
            ) : null}

            {!isAuthenticated ? (
              <div className="hero-entrance-item rounded-[1.35rem] border border-white/10 bg-white/6 px-4 py-3 text-xs leading-6 text-slate-300" style={{ opacity: 0 }}>
                Live valuations require a signed-in DigiLand session. If you are browsing anonymously, sign in to
                submit the estimate to the existing ML pricing service.
              </div>
            ) : null}
          </form>
        ) : (
          <div ref={resultsRef} className="space-y-4">
            {prediction.error ? (
              <div className="estimator-result-highlight rounded-[1.6rem] border border-rose-300/20 bg-rose-400/10 p-5">
                <div className="flex items-start gap-3 text-rose-50">
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-200" />
                  <div>
                    <div className="font-semibold">Valuation unavailable</div>
                    <p className="mt-1 text-sm leading-7 text-rose-100">{prediction.error}</p>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="estimator-result-highlight rounded-[1.8rem] border border-emerald-300/20 bg-emerald-400/10 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Badge tone="outline" className="border-emerald-300/30 bg-emerald-300/10 text-emerald-100">
                      {confidenceLabel}
                    </Badge>
                    <Button
                      type="button"
                      variant="ghost"
                      className="hero-cta-btn h-9 rounded-full px-3 text-xs font-semibold text-emerald-100 hover:bg-white/8 hover:text-white"
                      onClick={() => setShowResults(false)}
                    >
                      Adjust inputs
                    </Button>
                  </div>

                  <div className="mt-5 space-y-1">
                    <div className="text-[10px] font-black uppercase tracking-[0.3em] text-emerald-100/80">
                      Estimated value
                    </div>
                    <div className="text-4xl font-black tracking-tight text-white sm:text-5xl">
                      {formatKsh(displayedTotal)}
                    </div>
                    <div className="text-sm text-slate-300">
                      Per acre: {formatKsh(prediction.price_per_acre)} · Confidence band {formatKsh(prediction.confidence_low)} -{' '}
                      {formatKsh(prediction.confidence_high)}
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    { label: 'County', value: prediction.county || county },
                    { label: 'Location', value: prediction.land_use || landUse },
                    { label: 'Size', value: `${prediction.size_acres || sizeAcres} Acres` },
                    { label: 'Model accuracy', value: prediction.model_accuracy || '—' },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="estimator-result-item rounded-[1.2rem] border border-white/10 bg-white/6 px-4 py-3 backdrop-blur-xl"
                    >
                      <div className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-400">
                        {item.label}
                      </div>
                      <div className="mt-1 text-sm font-semibold text-white">{item.value}</div>
                    </div>
                  ))}
                </div>

                <div className="estimator-result-item rounded-[1.5rem] border border-white/10 bg-white/6 p-4 backdrop-blur-xl">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-[10px] font-black uppercase tracking-[0.26em] text-slate-400">
                        Market position
                      </div>
                      <div className="mt-1 text-base font-black tracking-tight text-white">{marketPosition}</div>
                    </div>
                    <MapPinned className="h-5 w-5 text-emerald-300" />
                  </div>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    {selectedSuggestion
                      ? `${selectedSuggestion.label} sits in the ${selectedSuggestion.region} cluster, which the model treats as a ${marketPosition.toLowerCase()} signal when compared with nearby parcels.`
                      : 'The model positions this estimate against comparable county and constituency signals to place the parcel within the current market range.'}
                  </p>
                </div>

                {comparisonRows.length ? (
                  <div className="space-y-2">
                    <div className="text-[10px] font-black uppercase tracking-[0.26em] text-slate-400">
                      Comparable market signals
                    </div>
                    <div className="space-y-2">
                      {comparisonRows.map((comparison) => (
                        <div
                          key={`${comparison.county}-${comparison.constituency}`}
                          className="estimator-result-item flex items-center justify-between gap-3 rounded-[1.2rem] border border-white/10 bg-white/6 px-4 py-3 text-sm text-slate-200"
                        >
                          <div>
                            <div className="font-semibold text-white">
                              {comparison.constituency}, {comparison.county}
                            </div>
                            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">
                              {comparison.land_use} · {comparison.size_acres} Acres
                            </div>
                          </div>
                          <div className="font-black text-emerald-200">{formatKsh(comparison.price_per_acre)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-col gap-3 pt-1 sm:flex-row">
                  <Button
                    type="button"
                    variant="outline"
                    className="hero-cta-btn h-11 rounded-full border-white/10 bg-white/6 text-white hover:bg-white/10"
                    onClick={() => setShowResults(false)}
                  >
                    Refine estimate
                  </Button>
                  <Button
                    type="button"
                    className="hero-cta-btn h-11 rounded-full bg-primary px-5 text-sm font-bold text-primary-foreground hover:bg-primary/90"
                    onClick={() => {
                      setShowResults(false);
                      setError(null);
                    }}
                  >
                    Estimate another parcel
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {stats.length ? (
          <div className="hero-entrance-item grid gap-3 pt-2 sm:grid-cols-3" style={{ opacity: 0 }}>
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-[1.2rem] border border-white/10 bg-white/6 p-4 backdrop-blur-xl">
                <div className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-400">{stat.label}</div>
                <div className="mt-1 text-sm font-black tracking-tight text-white">{stat.value}</div>
              </div>
            ))}
          </div>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-3">
          {etaModelFacts.map((fact) => (
            <div key={fact.label} className="rounded-[1.2rem] border border-white/10 bg-white/6 p-4 backdrop-blur-xl">
              <div className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-400">{fact.label}</div>
              <div className="mt-1 text-sm font-black tracking-tight text-white">{fact.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MarketValueVisualization({ reducedMotion }: { reducedMotion: boolean }) {
  const { lineRef, areaRef, peakRef, latestRef } = useMarketCurveMotion(reducedMotion);

  return (
    <Card
      aria-label="Animated land intelligence dashboard"
      className="hero-right-card hero-market-card relative overflow-hidden !border-white/15 !bg-slate-950/90 !text-white shadow-[0_40px_90px_-34px_rgba(5,150,105,0.55)] backdrop-blur-2xl"
      style={{
        opacity: 0,
        transform:
          'translate3d(calc(var(--hero-pointer-x, 0) * 0.45px), calc(var(--hero-pointer-y, 0) * 0.34px), 0)',
      }}
    >
      <div
        className="hero-ambient-fx absolute -right-16 -top-16 h-60 w-60 rounded-full bg-emerald-400/18 blur-3xl"
        style={{
          opacity: 0,
          transform:
            'translate3d(calc(var(--hero-pointer-x, 0) * -0.24px), calc(var(--hero-pointer-y, 0) * -0.18px), 0)',
          animationDelay: '0.15s',
          animationDuration: '18s',
        }}
      />
      <div
        className="hero-ambient-fx absolute -left-20 bottom-0 h-72 w-72 rounded-full bg-cyan-400/12 blur-3xl"
        style={{
          opacity: 0,
          transform:
            'translate3d(calc(var(--hero-pointer-x, 0) * 0.18px), calc(var(--hero-pointer-y, 0) * 0.12px), 0)',
          animationDelay: '0.9s',
          animationDuration: '22s',
        }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.1),_transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.3),rgba(2,6,23,0.55))]" />
      <div className="hero-noise-overlay absolute inset-0 opacity-[0.16]" />
      <div className="hero-grid-overlay absolute inset-0 opacity-[0.08]" />

      <CardHeader className="relative z-10 gap-0 pb-4 pt-5 sm:pt-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3">
            <Badge tone="outline" className="border-emerald-400/25 bg-emerald-400/10 text-emerald-100">
              ML land intelligence
            </Badge>
            <div>
              <CardTitle className="text-2xl font-black tracking-tight text-white sm:text-[1.75rem]">
                Kenya land intelligence pulse
              </CardTitle>
              <CardDescription className="mt-2 max-w-[28rem] text-sm leading-7 text-slate-300">
                The same pricing engine weighs location, size, land use, and infrastructure before it returns a
                valuation. This dashboard visualises that analysis in real time.
              </CardDescription>
            </div>
          </div>

          <div className="rounded-[1.4rem] border border-white/10 bg-white/6 px-4 py-3 text-right backdrop-blur-xl">
            <div className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-200/80">Model</div>
            <div className="mt-1 text-xl font-black tracking-tight text-white">Random Forest</div>
            <div className="mt-1 text-[11px] text-slate-300">8 pricing signals</div>
          </div>
        </div>

        <div className="hero-market-chip mt-5 grid gap-3 sm:grid-cols-3" style={{ opacity: 0 }}>
          {[
            { label: 'Coverage', value: '47 counties' },
            { label: 'Inputs', value: '8 feature signals' },
            { label: 'Latency', value: 'Fast inference' },
          ].map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/6 p-3 backdrop-blur-xl">
              <div className="text-[10px] font-black uppercase tracking-[0.26em] text-slate-400">
                {metric.label}
              </div>
              <div className="mt-1 text-base font-black tracking-tight text-white">{metric.value}</div>
            </div>
          ))}
        </div>
      </CardHeader>

      <CardContent className="relative z-10 space-y-4">
        <div className="relative overflow-hidden rounded-[1.8rem] border border-white/10 bg-slate-900/72 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] sm:p-5">
          <div
            className="hero-market-zone absolute left-[56%] top-[15%] h-[58%] w-[27%] rounded-[2rem] bg-emerald-400/14 blur-2xl"
            style={{
              opacity: 0.55,
              transform: 'scale(1)',
              animationDelay: '0.4s',
            }}
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),transparent_34%)]" />

          <div className="absolute left-4 top-4 z-20 rounded-full border border-white/10 bg-slate-950/70 px-3 py-1 text-[10px] font-black uppercase tracking-[0.26em] text-emerald-100 backdrop-blur-xl">
            Market activity curve
          </div>

          <svg viewBox="0 0 720 320" className="relative z-10 h-[18rem] w-full overflow-visible sm:h-[20rem]">
            <defs>
              <linearGradient id="digiland-market-line" x1="0%" x2="100%" y1="0%" y2="0%">
                <stop offset="0%" stopColor="#6ee7b7" />
                <stop offset="55%" stopColor="#34d399" />
                <stop offset="100%" stopColor="#22c55e" />
              </linearGradient>
              <linearGradient id="digiland-market-fill" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="rgba(52, 211, 153, 0.34)" />
                <stop offset="65%" stopColor="rgba(16, 185, 129, 0.08)" />
                <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
              </linearGradient>
              <filter id="digiland-market-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feColorMatrix
                  in="blur"
                  type="matrix"
                  values="0 0 0 0 0.20  0 0 0 0 0.95  0 0 0 0 0.65  0 0 0 0.85 0"
                  result="glow"
                />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <path
              ref={areaRef}
              d="M 0 228 C 38 222, 74 215, 112 212 C 148 209, 184 196, 224 190 C 264 184, 309 166, 356 146 C 404 124, 451 114, 498 108 C 542 102, 580 118, 620 124 C 652 128, 686 108, 720 88 L 720 272 L 0 272 Z"
              fill="url(#digiland-market-fill)"
            />

            <path
              ref={lineRef}
              d="M 0 228 C 38 222, 74 215, 112 212 C 148 209, 184 196, 224 190 C 264 184, 309 166, 356 146 C 404 124, 451 114, 498 108 C 542 102, 580 118, 620 124 C 652 128, 686 108, 720 88"
              fill="none"
              filter="url(#digiland-market-glow)"
              stroke="url(#digiland-market-line)"
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <circle
              ref={peakRef}
              cx="498"
              cy="108"
              r="9"
              fill="#34d399"
              filter="url(#digiland-market-glow)"
            />
            <circle ref={latestRef} cx="720" cy="88" r="5.4" fill="#ffffff" stroke="#22c55e" strokeWidth="3" />

            <g opacity="0.28">
              <path
                d="M 94 64 C 138 48, 198 44, 244 58 C 286 70, 314 96, 332 126 C 348 152, 348 184, 334 210 C 316 244, 270 260, 226 262 C 182 264, 140 250, 110 224 C 80 198, 64 162, 64 124 C 64 100, 74 80, 94 64 Z"
                fill="none"
                stroke="rgba(255,255,255,0.15)"
                strokeWidth="2"
              />
              <circle cx="176" cy="112" r="6" fill="#34d399" filter="url(#digiland-market-glow)" />
              <circle cx="278" cy="150" r="5" fill="#22c55e" filter="url(#digiland-market-glow)" />
              <circle cx="214" cy="220" r="4.5" fill="#6ee7b7" filter="url(#digiland-market-glow)" />
            </g>
          </svg>

          <div className="pointer-events-none absolute inset-0">
            {marketSignals.map((signal, index) => (
              <div
                key={signal.label}
                className="hero-floating-indicator pointer-events-auto absolute rounded-[1.2rem] border border-white/10 bg-white/10 px-3 py-2 text-white shadow-[0_18px_36px_-24px_rgba(15,23,42,0.75)] backdrop-blur-xl transition duration-300 ease-out hover:border-emerald-200/40 hover:bg-white/15 hover:shadow-[0_22px_40px_-24px_rgba(16,185,129,0.35)]"
                style={{
                  top: signal.top ?? undefined,
                  left: signal.left ?? undefined,
                  right: signal.right ?? undefined,
                  bottom: signal.bottom ?? undefined,
                  opacity: 0,
                  transform: `translate3d(calc(var(--hero-pointer-x, 0) * ${signal.xFactor}px), calc(var(--hero-pointer-y, 0) * ${signal.yFactor}px), 0)`,
                  minWidth: '11.5rem',
                  animationDelay: `${index * 0.35}s`,
                  animationDuration: `${8.5 + index * 0.8}s`,
                }}
                aria-label={`${signal.label}: ${signal.value}`}
              >
                <div className="text-[10px] font-black uppercase tracking-[0.24em] text-emerald-100/80">
                  {signal.label}
                </div>
                <div className="mt-1 text-sm font-black tracking-tight text-white">{signal.value}</div>
                <div className="mt-0.5 text-[11px] text-slate-300">{signal.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="hero-market-chip grid gap-3 sm:grid-cols-3" style={{ opacity: 0 }}>
          {[
            { label: 'Verified inventory', value: '1,284 parcels' },
            { label: 'Signal depth', value: 'Comparable clusters active' },
            { label: 'Trust layer', value: 'Escrow protected' },
          ].map((metric) => (
            <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/6 px-4 py-3 backdrop-blur-xl">
              <div className="text-[10px] font-black uppercase tracking-[0.26em] text-slate-400">{metric.label}</div>
              <div className="mt-1 text-sm font-black tracking-tight text-white">{metric.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function EcosystemGridSection({ reducedMotion }: { reducedMotion: boolean }) {
  const sectionRef = useRef<HTMLElement>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const featuredIndex = useAutoFeaturedIndex(ecosystemCards.length, reducedMotion);

  useEcosystemReveal(sectionRef, reducedMotion);

  const activeIndex = hoveredIndex ?? featuredIndex;

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.1),_transparent_32%),linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(255,255,255,0.82))] p-6 shadow-soft sm:p-8 lg:p-10"
    >
      <div className="pointer-events-none absolute inset-0">
        <div className="hero-grid-overlay absolute inset-0 opacity-[0.13]" />
        <div className="absolute -left-20 top-0 h-72 w-72 rounded-full bg-emerald-200/28 blur-3xl dark:bg-emerald-500/12" />
        <div className="absolute right-[-6rem] bottom-[-5rem] h-80 w-80 rounded-full bg-cyan-200/24 blur-3xl dark:bg-cyan-500/12" />
        <div className="hero-noise-overlay absolute inset-0 opacity-[0.16]" />
      </div>

      <div className="relative z-10">
        <div className="max-w-3xl">
          <div className="ecosystem-heading text-xs font-black uppercase tracking-[0.26em] text-emerald-700">
            Explore the DigiLand Ecosystem
          </div>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-foreground sm:text-4xl lg:text-[2.6rem] lg:leading-[1.08]">
            Everything You Need to Build Digital Value
          </h2>
          <p className="ecosystem-subtitle mt-4 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base sm:leading-8">
            From acquisition to governance, DigiLand connects the services, workflows, and intelligence layers
            that make modern land commerce feel premium and reliable.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {ecosystemCards.map((card, index) => {
            const isFeatured = activeIndex === index;

            return (
              <article
                key={card.title}
                className={cn(
                  'ecosystem-card group relative overflow-hidden rounded-[1.55rem] border p-5 text-left shadow-[0_18px_50px_-32px_rgba(15,23,42,0.28)] backdrop-blur-xl transition duration-300 ease-out',
                  isFeatured
                    ? 'border-emerald-300/70 bg-white/95 shadow-[0_26px_60px_-28px_rgba(5,150,105,0.35)]'
                    : 'border-border/70 bg-white/82 hover:-translate-y-1 hover:border-emerald-200 hover:shadow-[0_24px_60px_-28px_rgba(15,23,42,0.22)]'
                )}
                style={
                  reducedMotion
                    ? { opacity: 1, transform: 'none' }
                    : { opacity: 0, transform: 'translateY(18px)' }
                }
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                <div
                  className={cn(
                    'absolute inset-0 opacity-0 transition-opacity duration-300',
                    isFeatured && 'opacity-100'
                  )}
                  style={{
                    background:
                      'radial-gradient(circle at top left, rgba(16,185,129,0.15), transparent 58%), radial-gradient(circle at bottom right, rgba(34,197,94,0.08), transparent 46%)',
                  }}
                />
                <div
                  className={cn(
                    'relative flex h-12 w-12 items-center justify-center rounded-2xl border transition duration-300',
                    isFeatured
                      ? 'border-emerald-100 bg-emerald-600 text-white shadow-glow'
                      : 'border-emerald-100/70 bg-emerald-50 text-emerald-700 group-hover:bg-emerald-100'
                  )}
                >
                  <card.icon className={cn('h-5 w-5 transition duration-300', !isFeatured && 'group-hover:scale-110 group-hover:-rotate-3')} />
                </div>

                <div className="relative mt-5 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-[0.26em] text-emerald-700/80">
                      DigiLand capability
                    </div>
                    <h3 className="mt-2 text-lg font-black tracking-tight text-foreground">{card.title}</h3>
                  </div>
                  {isFeatured ? (
                    <Badge tone="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                      Featured
                    </Badge>
                  ) : null}
                </div>

                <p className="relative mt-3 text-sm leading-7 text-muted-foreground">{card.description}</p>

                <div className="relative mt-5 inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.24em] text-emerald-700">
                  <span>Explore</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5" />
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function HeroShowcase({ notice, stats = [], csrfToken, isAuthenticated = false }: HeroShowcaseProps) {
  const reducedMotion = useReducedMotionPreference();
  const heroRef = useHeroEntrance();
  const particlesRef = useHeroParticles();
  const ctaRef = useCtaHover();

  useHeroParallax(heroRef, reducedMotion);

  return (
    <div className="space-y-8">
      <section
        ref={heroRef}
        className="relative overflow-hidden rounded-[2rem] border border-border/70 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.16),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.09),_transparent_24%),linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(255,255,255,0.84))] p-6 shadow-soft sm:p-8 lg:p-10"
      >
        {!reducedMotion ? (
          <canvas
            ref={particlesRef}
            className="pointer-events-none absolute inset-0 h-full w-full"
            style={{ opacity: 0.28, mixBlendMode: 'screen' }}
          />
        ) : null}

        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className="hero-ambient-fx absolute -left-20 top-0 h-72 w-72 rounded-full bg-emerald-300/24 blur-3xl"
            style={{
              opacity: 0,
              transform:
                'translate3d(calc(var(--hero-pointer-x, 0) * -0.28px), calc(var(--hero-pointer-y, 0) * -0.18px), 0)',
              animationDelay: '0.3s',
              animationDuration: '19s',
            }}
          />
          <div
            className="hero-ambient-fx absolute right-[-5rem] top-[-4rem] h-80 w-80 rounded-full bg-cyan-300/18 blur-3xl"
            style={{
              opacity: 0,
              transform:
                'translate3d(calc(var(--hero-pointer-x, 0) * 0.18px), calc(var(--hero-pointer-y, 0) * 0.12px), 0)',
              animationDelay: '1.1s',
              animationDuration: '23s',
            }}
          />
          <div className="hero-grid-overlay absolute inset-0 opacity-[0.11]" />
          <div className="hero-noise-overlay absolute inset-0 opacity-[0.12]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(255,255,255,0.22),_transparent_52%)] opacity-70" />
        </div>

        <div className="relative z-10 grid gap-8 lg:grid-cols-[1.04fr_0.96fr]">
          <LandPriceEstimatorPanel
            notice={notice}
            stats={stats}
            csrfToken={csrfToken}
            isAuthenticated={Boolean(isAuthenticated)}
            ctaRef={ctaRef}
          />
          <MarketValueVisualization reducedMotion={reducedMotion} />
        </div>
      </section>

      <EcosystemGridSection reducedMotion={reducedMotion} />
    </div>
  );
}
