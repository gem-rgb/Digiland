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
  Search as SearchIcon,
  Sparkles,
  Ticket,
  Upload,
  UserPlus,
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
    <div className="relative min-h-[calc(100vh-7rem)] overflow-hidden rounded-[2.5rem] border border-emerald-400/15 bg-slate-950 px-5 py-8 text-white shadow-2xl sm:px-10 sm:py-10 lg:px-16 lg:py-12">
      <div className="pointer-events-none absolute inset-0 opacity-30" style={{ backgroundImage: 'linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px)', backgroundSize: '42px 42px' }} />
      <div className="pointer-events-none absolute -right-24 -top-24 h-[34rem] w-[34rem] rounded-full bg-emerald-500/20 blur-[150px]" />
      <div className="pointer-events-none absolute -bottom-40 left-1/4 h-[28rem] w-[28rem] rounded-full bg-cyan-500/10 blur-[140px]" />
      {!reducedMotion ? <canvas ref={particlesRef} className="pointer-events-none absolute inset-0 h-full w-full opacity-20 mix-blend-screen" /> : null}

      <div className="relative z-10 mx-auto flex min-h-[calc(100vh-11rem)] max-w-7xl flex-col justify-between gap-10">
        {/* Top bar */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div ref={ctaRef} className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.24em] text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.9)]" /> {notice || 'Digiland Protocol / Kenya'}
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated && (
              <a
                href="/parcels/"
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-bold text-emerald-300 transition hover:bg-emerald-500/20"
              >
                Dashboard Active
              </a>
            )}
            <div className="hidden text-right text-[10px] font-bold uppercase tracking-[0.22em] text-slate-500 sm:block">
              Secure land infrastructure<br /><span className="text-emerald-400">Network online</span>
            </div>
          </div>
        </div>

        <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div className="max-w-3xl">
            <div className="mb-5 text-xs font-black uppercase tracking-[0.28em] text-emerald-400">Autonomous land registry & escrow protocol</div>
            <h1 className="text-4xl font-black leading-[0.98] tracking-[-0.04em] text-white sm:text-6xl lg:text-7xl">Kenya's Autonomous<br /><span className="bg-gradient-to-r from-emerald-300 via-teal-200 to-cyan-300 bg-clip-text text-transparent">Land Registry & Escrow Protocol</span></h1>
            <p className="mt-6 max-w-2xl text-sm leading-7 text-slate-300 sm:text-lg sm:leading-8">Automated ArdhiSasa land title validation, M-Pesa escrow vaulting, and cryptographic Law Society advocate authentication.</p>

            <form onSubmit={handleSearch} className="mt-8 flex max-w-2xl flex-col gap-3 rounded-[1.35rem] border border-white/10 bg-white/[0.07] p-2 backdrop-blur-xl sm:flex-row">
              <div className="flex min-w-0 flex-1 items-center gap-3 rounded-xl px-3"><SearchIcon className="h-5 w-5 shrink-0 text-emerald-400" /><input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search county, ward, or parcel number" className="w-full bg-transparent py-3 text-sm text-white outline-none placeholder:text-slate-500" /></div>
              <Button type="submit" className="h-12 rounded-xl bg-emerald-500 px-6 font-black text-slate-950 hover:bg-emerald-400"><SearchIcon className="mr-2 h-4 w-4" />Search</Button>
            </form>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500"><span>Popular:</span>{['Nairobi', 'Nakuru', 'Kiambu', 'Kajiado'].map((tag) => <a key={tag} href={`/parcels/?q=${encodeURIComponent(tag)}`} className="text-slate-300 transition hover:text-emerald-300">{tag}</a>)}</div>

            {/* Action buttons */}
            <div className="my-8 sm:my-10 flex flex-wrap items-center gap-4 sm:gap-5">
              {!isAuthenticated ? (
                <a
                  href="/accounts/signup/"
                  className="inline-flex h-14 sm:h-16 min-w-[240px] sm:min-w-[280px] items-center justify-center gap-3 rounded-full bg-gradient-to-r from-emerald-400 via-emerald-500 to-teal-400 px-8 sm:px-10 text-base sm:text-lg font-black text-slate-950 shadow-[0_6px_30px_rgba(16,185,129,0.45)] ring-2 ring-emerald-400/50 ring-offset-2 ring-offset-slate-950 transition-all duration-200 hover:scale-[1.03] hover:shadow-[0_10px_40px_rgba(16,185,129,0.65)] hover:brightness-110 active:scale-[0.98]"
                >
                  <UserPlus className="h-5 w-5" />
                  Get Started — Free
                  <ArrowRight className="h-5 w-5" />
                </a>
              ) : (
                <a
                  href="/parcels/"
                  className="inline-flex h-14 sm:h-16 min-w-[250px] items-center justify-center gap-3 rounded-full bg-emerald-500 px-8 text-base font-black text-slate-950 shadow-[0_6px_25px_rgba(16,185,129,0.4)] transition-all duration-200 hover:scale-[1.02] hover:bg-emerald-400"
                >
                  Launch Marketplace
                  <ArrowRight className="h-5 w-5" />
                </a>
              )}
            </div>
          </div>

          <div className="relative rounded-[2rem] border border-white/10 bg-white/[0.06] p-5 shadow-[0_30px_100px_-45px_rgba(16,185,129,0.8)] backdrop-blur-2xl sm:p-7">
            <div className="flex items-center justify-between border-b border-white/10 pb-4"><div><div className="text-[10px] font-black uppercase tracking-[0.25em] text-emerald-400">System concept architecture</div><div className="mt-1 text-sm font-bold text-slate-300">Three trust layers. One closing path.</div></div><ShieldCheck className="h-6 w-6 text-emerald-400" /></div>
            <div className="mt-5 space-y-3">
              {([['01', 'ArdhiSasa Registry Validation', 'Government title deed check', Landmark], ['02', 'Smart Escrow Vault', 'M-Pesa STK & KCB bank deposit lock', WalletCards], ['03', 'Cryptographic Advocate Sign-Off', 'LSK lawyer title transfer', Gavel]] as const).map(([number, title, description, Icon]) => {
                const IconComp = Icon as LucideIcon;
                return (
                  <div key={String(number)} className="group flex items-center gap-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4 transition hover:border-emerald-400/40">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-400/10 text-xs font-black text-emerald-300">{number}</div>
                    <div className="min-w-0 flex-1"><div className="text-sm font-black text-white">{title}</div><div className="mt-1 text-xs text-slate-400">{description}</div></div>
                    <IconComp className="h-5 w-5 shrink-0 text-emerald-400" />
                  </div>
                );
              })}
            </div>
            <div className="mt-6 grid grid-cols-3 gap-2 border-t border-white/10 pt-5 text-center"><div><div className="text-lg font-black text-white">24/7</div><div className="text-[9px] uppercase tracking-wider text-slate-500">Monitoring</div></div><div><div className="text-lg font-black text-white">M-Pesa</div><div className="text-[9px] uppercase tracking-wider text-slate-500">Vaulting</div></div><div><div className="text-lg font-black text-white">LSK</div><div className="text-[9px] uppercase tracking-wider text-slate-500">Verified</div></div></div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/10 pt-5 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500"><span>ArdhiSasa synchronized</span><span>Escrow protected</span><span>Advocate authenticated</span><span className="text-emerald-400">Protocol status: operational</span></div>
      </div>
    </div>
  );
}
