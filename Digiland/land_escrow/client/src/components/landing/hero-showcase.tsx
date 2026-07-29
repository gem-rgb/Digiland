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
  const [email, setEmail] = useState('');

  useHeroParallax(heroRef, reducedMotion);

  return (
    <div className="space-y-6">
      {/* Sleek Web3 / Crypto-Style Hero Section */}
      <section
        ref={heroRef}
        className="relative overflow-hidden rounded-[2.5rem] border border-emerald-500/20 bg-slate-950 text-white px-6 py-12 sm:px-10 sm:py-16 lg:px-14 lg:py-20 shadow-2xl min-h-[75vh] flex flex-col justify-center"
      >
        {!reducedMotion ? (
          <canvas
            ref={particlesRef}
            className="pointer-events-none absolute inset-0 h-full w-full opacity-20 mix-blend-screen"
          />
        ) : null}

        {/* Ambient background glows */}
        <div className="absolute -right-32 -top-32 h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[160px] pointer-events-none select-none" />
        <div className="absolute -left-32 bottom-0 h-[400px] w-[400px] rounded-full bg-cyan-600/10 blur-[140px] pointer-events-none select-none" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(16,185,129,0.05)_1px,_transparent_1px)] bg-[size:32px_32px] opacity-60 pointer-events-none select-none" />

        {/* Main Content Layout */}
        <div className="relative z-10 grid gap-10 lg:grid-cols-12 lg:items-center">
          {/* Left Column: Headline, Subheadline & Action Buttons */}
          <div className="lg:col-span-7 space-y-6 text-left">
            <div ref={ctaRef} className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.2em] text-emerald-300 backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              {notice || 'Kenya\'s Autonomous Land Registry & Escrow Protocol'}
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-[1.08] text-white">
              The Trust Layer for <br />
              <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-amber-300 bg-clip-text text-transparent">
                Kenyan Land Commerce
              </span>
            </h1>

            <p className="text-base sm:text-lg leading-relaxed text-slate-300 font-light max-w-xl">
              Automated ArdhiSasa land title validation, M-Pesa escrow vaulting, and cryptographic Law Society advocate authentication — all in one unified protocol.
            </p>

            {/* Crypto-Style Search & Launch Pill */}
            <div className="w-full max-w-xl pt-2">
              <form 
                onSubmit={(e) => {
                  e.preventDefault();
                  const target = email.includes('@') ? `/accounts/signup/?email=${encodeURIComponent(email)}` : `/marketplace/?q=${encodeURIComponent(email)}`;
                  window.location.href = target;
                }}
                className="flex items-center bg-white/95 backdrop-blur-2xl rounded-full p-2 shadow-2xl border border-white/20 focus-within:ring-4 focus-within:ring-emerald-500/30 transition-all duration-300"
              >
                <div className="pl-4 pr-2 text-slate-400 hidden sm:flex items-center">
                  <MapPin className="h-5 w-5 text-emerald-600" />
                </div>
                <input
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter County, Parcel No, or Email..."
                  className="flex-1 bg-transparent px-3 py-2 text-slate-900 placeholder:text-slate-500 font-medium text-sm sm:text-base focus:outline-none"
                />
                <Button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-11 px-6 rounded-full transition duration-300 shadow-md flex items-center gap-2 text-xs sm:text-sm whitespace-nowrap"
                >
                  <span>Launch Marketplace</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            </div>

            {/* Quick Metrics Ticker */}
            <div className="flex flex-wrap items-center gap-6 pt-4 text-xs font-semibold text-slate-300 border-t border-white/10">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <span>ArdhiSasa Synchronized</span>
              </div>
              <div className="flex items-center gap-2">
                <WalletCards className="h-4 w-4 text-teal-400" />
                <span>100% Escrow Protected</span>
              </div>
              <div className="flex items-center gap-2">
                <Gavel className="h-4 w-4 text-amber-400" />
                <span>LSK Advocate Verified</span>
              </div>
            </div>
          </div>

          {/* Right Column: High-Impact Protocol Concept Showcase Card */}
          <div className="lg:col-span-5">
            <div className="relative overflow-hidden rounded-[2rem] border border-white/15 bg-white/5 backdrop-blur-2xl p-6 sm:p-8 shadow-2xl space-y-6 text-left hover:border-emerald-500/40 transition duration-500">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs font-black uppercase tracking-[0.2em] text-emerald-300">System Concept Architecture</span>
                </div>
                <Badge tone="outline" className="border-white/20 text-white text-[10px]">Protocol Flow</Badge>
              </div>

              {/* Protocol Flow Visual Steps */}
              <div className="space-y-4">
                <div className="flex items-start gap-4 p-3.5 rounded-2xl bg-white/5 border border-white/10">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30 text-sm">
                    01
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Title Verification & ArdhiSasa Sync</div>
                    <div className="text-xs text-slate-400 mt-0.5">Automated title deed check against Ministry of Lands registry.</div>
                  </div>
                </div>

                <div className="flex items-start gap-4 p-3.5 rounded-2xl bg-white/5 border border-white/10">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-500/20 text-teal-300 font-bold border border-teal-500/30 text-sm">
                    02
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Smart Escrow Deposit Vault</div>
                    <div className="text-xs text-slate-400 mt-0.5">Funds locked safely via M-Pesa STK & KCB Bank until legal closing.</div>
                  </div>
                </div>

                <div className="flex items-start gap-4 p-3.5 rounded-2xl bg-white/5 border border-white/10">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30 text-sm">
                    03
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Cryptographic Advocate Sign-Off</div>
                    <div className="text-xs text-slate-400 mt-0.5">LSK Advocate executes deed transfer under legal supervision.</div>
                  </div>
                </div>
              </div>

              {/* Protocol Status Banner */}
              <div className="pt-2">
                <a 
                  href="/escrow-acts/" 
                  className="flex items-center justify-between p-3.5 rounded-2xl bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-emerald-200 transition text-xs font-bold"
                >
                  <span>Explore Complete Legal & Escrow Acts</span>
                  <ArrowRight className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
