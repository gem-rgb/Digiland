import React, {
  useEffect,
  useRef,
  useState,
} from 'react';
import anime from 'animejs';
import {
  ArrowRight,
  BarChart3,
  Gavel,
  Landmark,
  MapPin,
  Sparkles,
  Ticket,
  Upload,
  ShieldCheck,
  WalletCards,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { cn } from '../../lib/utils.js';
import { useCtaHover, useHeroEntrance, useHeroParticles } from '../../hooks/use-hero-animations.js';
import {
  SCENES,
  MockBrowse,
  MockUpload,
  MockKYC,
  MockEscrow,
  MockContract,
  MockComplete,
} from './animated-walkthrough.js';

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

type EcosystemCard = {
  title: string;
  description: string;
  icon: LucideIcon;
};

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

const MOCK_SCREENS: Record<number, React.FC> = {
  1: MockBrowse,
  2: MockUpload,
  3: MockKYC,
  4: MockEscrow,
  5: MockContract,
  6: MockComplete,
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
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
        <div className="absolute -left-20 top-0 h-72 w-72 rounded-full bg-emerald-200/28 blur-3xl dark:bg-emerald-500/12" />
        <div className="absolute right-[-6rem] bottom-[-5rem] h-80 w-80 rounded-full bg-cyan-200/24 blur-3xl dark:bg-cyan-500/12" />
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

export function HeroShowcase({ notice, csrfToken, isAuthenticated = false }: HeroShowcaseProps) {
  const reducedMotion = useReducedMotionPreference();
  const heroRef = useHeroEntrance();
  const particlesRef = useHeroParticles();
  const ctaRef = useCtaHover();
  const [searchQuery, setSearchQuery] = useState('');
  const [propertyType, setPropertyType] = useState('all');
  const [priceRange, setPriceRange] = useState('all');

  useHeroParallax(heroRef, reducedMotion);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (searchQuery.trim()) params.set('q', searchQuery.trim());
    if (propertyType !== 'all') params.set('type', propertyType);
    if (priceRange !== 'all') params.set('price', priceRange);
    window.location.href = `/parcels/?${params.toString()}`;
  };

  const popularTags = [
    { label: 'Nairobi', query: 'Nairobi' },
    { label: 'Nakuru', query: 'Nakuru' },
    { label: 'Kiambu', query: 'Kiambu' },
    { label: 'Kajiado', query: 'Kajiado' },
    { label: 'Kilifi', query: 'Kilifi' },
    { label: 'Agricultural Land', query: 'Agricultural' },
    { label: 'Ranches & Farms', query: 'Ranch' },
    { label: 'ArdhiSasa Verified', query: 'Verified' },
  ];

  return (
    <div className="space-y-6">
      {/* Land.com Inspired Hero Section with Landscape Background Overlay */}
      <section
        ref={heroRef}
        className="relative overflow-hidden rounded-[2.5rem] bg-slate-900 text-white px-6 py-16 sm:px-10 sm:py-24 lg:px-16 lg:py-28 shadow-2xl min-h-[80vh] flex flex-col justify-center border border-emerald-500/20"
      >
        {/* Scenic Nature & Landscape Background Image with Rich Dark Overlay */}
        <div
          className="absolute inset-0 bg-cover bg-center opacity-45 mix-blend-luminosity pointer-events-none scale-105 transition-transform duration-1000"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=2000&q=80')`,
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/70 to-slate-950/40 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950/90 via-slate-950/60 to-transparent pointer-events-none" />

        {!reducedMotion ? (
          <canvas
            ref={particlesRef}
            className="pointer-events-none absolute inset-0 h-full w-full opacity-15 mix-blend-screen"
          />
        ) : null}

        {/* Ambient background glows */}
        <div className="absolute -right-24 -top-24 h-[500px] w-[500px] rounded-full bg-emerald-500/15 blur-[160px] pointer-events-none select-none" />
        <div className="absolute -left-20 bottom-10 h-[400px] w-[400px] rounded-full bg-amber-500/10 blur-[140px] pointer-events-none select-none" />

        {/* Main Hero Content */}
        <div className="relative z-10 max-w-4xl mx-auto text-center space-y-8">
          {/* Top Pill Badge */}
          <div ref={ctaRef} className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-950/80 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-emerald-300 backdrop-blur-md shadow-lg">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            {notice || "Kenya's Premier Land Escrow & Marketplace"}
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight leading-[1.08] text-white drop-shadow-md font-serif">
            Find & Secure Your Land <br />
            <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-amber-300 bg-clip-text text-transparent italic font-sans font-extrabold">
              with Absolute Trust
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-xl leading-relaxed text-slate-200 font-light max-w-2xl mx-auto drop-shadow-sm">
            Ranches, Farms, Agricultural & Residential Land for Sale Across Kenya — Protected by ArdhiSasa Title Checks and M-Pesa Escrow.
          </p>

          {/* Land.com-Style Multi-Filter Search Console */}
          <div className="w-full max-w-3xl mx-auto pt-2">
            <form
              onSubmit={handleSearch}
              className="bg-white/95 backdrop-blur-2xl rounded-3xl p-3 sm:p-4 shadow-2xl border border-white/40 text-slate-900 space-y-3 sm:space-y-0 sm:flex sm:items-center sm:gap-3 transition-all duration-300 focus-within:ring-4 focus-within:ring-emerald-500/30"
            >
              {/* Search Query Input */}
              <div className="flex-1 flex items-center gap-3 px-3 py-1 bg-slate-50/80 rounded-2xl sm:bg-transparent sm:py-0">
                <MapPin className="h-5 w-5 text-emerald-600 shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="County, Town, Sub-county, or Parcel No..."
                  className="w-full bg-transparent py-2.5 text-slate-900 placeholder:text-slate-500 font-semibold text-sm sm:text-base focus:outline-none"
                />
              </div>

              {/* Property Type Dropdown */}
              <div className="hidden md:flex items-center border-l border-slate-200 pl-3 pr-1 py-1">
                <select
                  value={propertyType}
                  onChange={(e) => setPropertyType(e.target.value)}
                  className="bg-transparent text-xs sm:text-sm font-semibold text-slate-700 focus:outline-none cursor-pointer pr-2"
                >
                  <option value="all">All Land Types</option>
                  <option value="Agricultural">Agricultural Land</option>
                  <option value="Residential">Residential Plot</option>
                  <option value="Commercial">Commercial Plot</option>
                  <option value="Ranch">Ranches & Farms</option>
                </select>
              </div>

              {/* Price Range Dropdown */}
              <div className="hidden lg:flex items-center border-l border-slate-200 pl-3 pr-1 py-1">
                <select
                  value={priceRange}
                  onChange={(e) => setPriceRange(e.target.value)}
                  className="bg-transparent text-xs sm:text-sm font-semibold text-slate-700 focus:outline-none cursor-pointer pr-2"
                >
                  <option value="all">Any Price</option>
                  <option value="under_1m">Under KES 1M</option>
                  <option value="1m_5m">KES 1M - 5M</option>
                  <option value="5m_20m">KES 5M - 20M</option>
                  <option value="20m_plus">KES 20M+</option>
                </select>
              </div>

              {/* Submit Search Button */}
              <Button
                type="submit"
                className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-12 px-8 rounded-2xl sm:rounded-2xl transition duration-300 shadow-lg flex items-center justify-center gap-2 text-sm whitespace-nowrap shrink-0"
              >
                <Search className="h-4 w-4" />
                <span>Search Land</span>
              </Button>
            </form>
          </div>

          {/* Quick Popular Location & Category Filter Tags */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2 text-xs">
            <span className="text-slate-400 font-medium mr-1">Popular:</span>
            {popularTags.map((tag) => (
              <a
                key={tag.label}
                href={`/parcels/?q=${encodeURIComponent(tag.query)}`}
                className="rounded-full bg-white/10 hover:bg-emerald-500/20 border border-white/15 hover:border-emerald-400/50 px-3.5 py-1 text-slate-200 hover:text-emerald-300 font-semibold transition duration-200 backdrop-blur-sm"
              >
                {tag.label}
              </a>
            ))}
          </div>

          {/* Trust Metrics Bar */}
          <div className="flex flex-wrap items-center justify-center gap-8 pt-6 text-xs font-semibold text-slate-300 border-t border-white/10">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <span>ArdhiSasa Registry Synchronized</span>
            </div>
            <div className="flex items-center gap-2">
              <WalletCards className="h-4 w-4 text-teal-400" />
              <span>100% Escrow Vault Protection</span>
            </div>
            <div className="flex items-center gap-2">
              <Gavel className="h-4 w-4 text-amber-400" />
              <span>Law Society Advocates Verified</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
