import React, { useCallback, useEffect, useRef, useState } from 'react';
import anime from 'animejs';
import {
  ArrowRight,
  CheckCircle2,
  FileCheck2,
  Globe,
  Instagram,
  Github,
  Landmark,
  Linkedin,
  Lock,
  Mail,
  MapPin,
  Send,
  Twitter,
  Zap,
} from 'lucide-react';
import { Button } from '../ui/button.js';
import { Card } from '../ui/card.js';
import { Input } from '../ui/input.js';

/* ==========================================================================
   Data
   ========================================================================== */

type NavLink = { label: string; href: string };

const NAV_COLUMNS: Array<{ title: string; links: NavLink[] }> = [
  {
    title: 'Platform',
    links: [
      { label: 'Browse Parcels', href: '/parcels/' },
      { label: 'List Property', href: '/parcels/upload/' },
      { label: 'Escrow Protection', href: '/escrow-acts/' },
      { label: 'Platform Features', href: '/features/' },
    ],
  },
  {
    title: 'User Portals',
    links: [
      { label: 'Buyer Dashboard', href: '/buyer-choice/' },
      { label: 'Seller Hub', href: '/parcels/upload/' },
      { label: 'Staff & Advocates', href: '/staff/login/' },
      { label: 'Admin Control Plane', href: '/admin/' },
    ],
  },
  {
    title: 'Legal & Escrow',
    links: [
      { label: 'Legal Framework', href: '/escrow-acts/' },
      { label: 'Joint Ownership Laws', href: '/joint-laws/' },
      { label: 'ArdhiSasa Registry Sync', href: '/escrow-acts/' },
      { label: 'LSK Advocate Sign-Off', href: '/staff/login/' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About Digiland', href: '/features/' },
      { label: 'System Architecture', href: '/features/' },
      { label: 'Help & Support', href: '/support/' },
      { label: 'Partner Network', href: '/parcels/' },
    ],
  },
];

type StatCounter = {
  /** Numeric target value to count up to */
  target: number;
  /** Prefix shown before the number (e.g. "KES ") */
  prefix?: string;
  /** Suffix shown after the number (e.g. "+", "B+") */
  suffix: string;
  /** Label underneath the number */
  label: string;
  /** Number of decimal places to display (0 = integer) */
  decimals?: number;
};

const CTA_COUNTERS: StatCounter[] = [
  { target: 2500, prefix: '', suffix: '+', label: 'Verified Parcels' },
  { target: 47, prefix: '', suffix: '', label: 'Counties Covered' },
  { target: 3.2, prefix: 'KES ', suffix: 'B+', label: 'Escrowed', decimals: 1 },
  { target: 10000, prefix: '', suffix: '+', label: 'Active Users' },
];

type TrustItem = { icon: React.ElementType; label: string; description: string };

const TRUST_ITEMS: TrustItem[] = [
  {
    icon: Lock,
    label: 'Bank-Grade Vault Security',
    description: 'AES-256 encrypted escrow deposits & SOC 2 compliant architecture.',
  },
  {
    icon: Landmark,
    label: 'CBK & M-Pesa Regulated',
    description: 'Automated settlement via Central Bank & Safaricom M-Pesa STK.',
  },
  {
    icon: FileCheck2,
    label: 'ArdhiSasa Direct Sync',
    description: 'Instant title deed validation against Ministry of Lands databases.',
  },
  {
    icon: Zap,
    label: 'LSK Advocate Sign-Off',
    description: 'Verified Law Society of Kenya lawyers execute title deeds.',
  },
];

type SocialLink = { icon: React.ElementType; label: string; href: string };

const SOCIAL_LINKS: SocialLink[] = [
  { icon: Twitter, label: 'Twitter / X', href: 'https://x.com/digilandke' },
  { icon: Linkedin, label: 'LinkedIn', href: 'https://linkedin.com/company/digilandke' },
  { icon: Github, label: 'GitHub', href: 'https://github.com/digilandke' },
  { icon: Instagram, label: 'Instagram', href: 'https://instagram.com/digilandke' },
  { icon: Globe, label: 'Facebook', href: 'https://facebook.com/digilandke' },
];

/* ==========================================================================
   Hook – prefers-reduced-motion
   ========================================================================== */

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  return reduced;
}

/* ==========================================================================
   Hook – Scroll reveal (IntersectionObserver → anime.js staggered fade-up)
   ========================================================================== */

function useScrollReveal(
  ref: React.RefObject<HTMLElement | null>,
  selector: string,
  reduced: boolean,
  stagger = 80,
) {
  useEffect(() => {
    const root = ref.current;
    if (!root) return;

    const targets = Array.from(root.querySelectorAll<HTMLElement>(selector));
    if (!targets.length) return;

    if (reduced) {
      targets.forEach((t) => {
        t.style.opacity = '1';
        t.style.transform = 'none';
      });
      return;
    }

    /* Start invisible */
    targets.forEach((t) => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(24px)';
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          anime({
            targets,
            opacity: [0, 1],
            translateY: [24, 0],
            delay: anime.stagger(stagger),
            duration: 720,
            easing: 'easeOutCubic',
          });
          observer.disconnect();
        });
      },
      { threshold: 0.12 },
    );

    observer.observe(root);
    return () => observer.disconnect();
  }, [ref, selector, reduced, stagger]);
}

/* ==========================================================================
   Hook – Number counter (anime.js tween from 0 → target on scroll)
   ========================================================================== */

function useCounter(
  target: number,
  decimals: number,
  ref: React.RefObject<HTMLElement | null>,
  reduced: boolean,
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (reduced) {
      el.textContent = formatNumber(target, decimals);
      return;
    }

    let triggered = false;
    const tween = { value: 0 };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting || triggered) return;
          triggered = true;

          const anim = anime({
            targets: tween,
            value: target,
            duration: target >= 1000 ? 1800 : 1200,
            easing: 'easeOutExpo',
            round: decimals > 0 ? Math.pow(10, decimals) : 1,
            update: () => {
              el.textContent = formatNumber(tween.value, decimals);
            },
          });

          return () => anim.pause();
        });
      },
      { threshold: 0.3 },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [target, decimals, ref, reduced]);
}

/** Format the animated number value for display */
function formatNumber(value: number, decimals: number): string {
  if (decimals > 0) {
    return value.toFixed(decimals);
  }
  const rounded = Math.round(value);
  return rounded.toLocaleString('en-KE');
}

/* ==========================================================================
   Sub-components
   ========================================================================== */

/** Footer navigation link with hover underline expand-from-center */
function FooterNavLink({ label, href }: NavLink) {
  return (
    <a
      href={href}
      className="group relative inline-block text-sm font-semibold text-slate-200 transition-colors duration-200 hover:text-emerald-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
    >
      {label}
      <span
        className="absolute bottom-0 left-1/2 h-px w-0 -translate-x-1/2 bg-emerald-400 transition-all duration-300 group-hover:w-full"
        aria-hidden="true"
      />
    </a>
  );
}

/** Social icon button with scale + emerald glow on hover */
function SocialIcon({ icon: Icon, label, href }: SocialLink) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      className="group relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-slate-200 transition-all duration-300 hover:scale-[1.15] hover:border-emerald-400/60 hover:bg-emerald-400/20 hover:text-emerald-300 hover:shadow-[0_0_18px_rgba(52,211,153,0.35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
    >
      <Icon className="h-[18px] w-[18px]" />
    </a>
  );
}

/** Animated number counter card for the CTA section */
function CounterCard({ stat, reduced }: { stat: StatCounter; reduced: boolean }) {
  const numberRef = useRef<HTMLSpanElement>(null);
  useCounter(stat.target, stat.decimals ?? 0, numberRef, reduced);

  return (
    <div className="flex flex-col items-center gap-1.5 text-center">
      <div className="flex items-baseline gap-0.5">
        {stat.prefix && (
          <span className="text-sm font-bold text-slate-300 sm:text-base">{stat.prefix}</span>
        )}
        <span
          ref={numberRef}
          className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl lg:text-4xl"
        >
          0
        </span>
        <span className="text-lg font-bold text-emerald-400 sm:text-xl lg:text-2xl">{stat.suffix}</span>
      </div>
      <span className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300 sm:text-sm">
        {stat.label}
      </span>
    </div>
  );
}

/** Trust / certification card with icon, label, and description */
function TrustCard({ icon: Icon, label, description }: TrustItem) {
  return (
    <div className="footer-reveal-item flex items-start gap-3 rounded-2xl border border-emerald-500/20 bg-slate-900/90 p-4 shadow-lg backdrop-blur-md transition-all duration-200 hover:border-emerald-400/50 hover:bg-slate-900">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-400/30 bg-emerald-500/20">
        <Icon className="h-5 w-5 text-emerald-300" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-bold text-white">{label}</p>
        <p className="mt-0.5 text-xs font-normal leading-5 text-slate-300">{description}</p>
      </div>
    </div>
  );
}

/* ==========================================================================
   Film-grain overlay (SVG noise texture)
   ========================================================================== */

function FilmGrainOverlay() {
  return (
    <div
      className="pointer-events-none absolute inset-0 opacity-[0.035]"
      style={{
        backgroundImage:
          'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")',
        backgroundRepeat: 'repeat',
        backgroundSize: '128px 128px',
      }}
      aria-hidden="true"
    />
  );
}

/* ==========================================================================
   Main component
   ========================================================================== */

export function PremiumFooter() {
  const reduced = useReducedMotion();

  /* Refs for scroll-reveal sections */
  const ctaRef = useRef<HTMLElement>(null);
  const brandRef = useRef<HTMLElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const trustRef = useRef<HTMLElement>(null);
  const newsletterRef = useRef<HTMLElement>(null);

  /* Scroll-reveal animation hooks */
  useScrollReveal(ctaRef, '.cta-reveal', reduced, 100);
  useScrollReveal(brandRef, '.brand-reveal', reduced, 70);
  useScrollReveal(navRef, '.nav-col-reveal', reduced, 120);
  useScrollReveal(trustRef, '.footer-reveal-item', reduced, 90);
  useScrollReveal(newsletterRef, '.newsletter-reveal', reduced, 100);

  /* Newsletter subscription state */
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubscribe = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!email.trim()) return;
      setSubmitting(true);

      /* Simulate API round-trip */
      setTimeout(() => {
        setSubscribed(true);
        setSubmitting(false);
        setEmail('');

        /* Reset success indicator after a few seconds */
        setTimeout(() => setSubscribed(false), 4000);
      }, 900);
    },
    [email],
  );

  return (
    <footer className="relative overflow-hidden bg-slate-950 text-white border-t border-white/10" role="contentinfo">
      {/* ================================================================== */}
      {/*  1. Footer Hero CTA                                                */}
      {/* ================================================================== */}
      <section
        ref={ctaRef}
        className="cta-section relative overflow-hidden px-6 py-20 sm:py-24 lg:py-28"
        aria-label="Call to action"
      >
        {/* Layered gradient background */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-slate-950 via-emerald-950/20 to-slate-950" />

        {/* Ambient glow orbs */}
        <div
          className="pointer-events-none absolute -left-32 top-0 h-[420px] w-[420px] rounded-full bg-emerald-500/15 blur-[120px]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -right-24 bottom-0 h-[360px] w-[360px] rounded-full bg-cyan-400/10 blur-[100px]"
          aria-hidden="true"
        />

        {/* Film grain texture */}
        <FilmGrainOverlay />

        <div className="cta-reveal relative z-10 mx-auto max-w-5xl text-center" style={{ opacity: 0 }}>
          <h2 className="text-3xl font-black tracking-tight sm:text-4xl lg:text-5xl font-serif">
            Ready to Transact Land{' '}
            <span className="bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent italic font-sans font-extrabold">
              With Absolute Trust?
            </span>
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg sm:leading-8 font-light">
            Join thousands of buyers, sellers, and advocates across Kenya using Digiland for verified title deeds, M-Pesa escrow protection, and legal closing.
          </p>

          {/* CTA Buttons */}
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="/accounts/signup/"
              className="inline-flex h-13 items-center justify-center rounded-full bg-emerald-500 px-8 text-base font-extrabold text-slate-950 shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all duration-300 hover:bg-emerald-400 hover:shadow-[0_0_40px_rgba(16,185,129,0.7)]"
            >
              Get Started Free
              <ArrowRight className="ml-2 h-4 w-4" />
            </a>
            <a
              href="/parcels/"
              className="inline-flex h-13 items-center justify-center rounded-full border border-white/25 bg-white/10 px-8 text-base font-bold text-white shadow-lg backdrop-blur-md transition-all duration-300 hover:border-emerald-400 hover:bg-emerald-400/20 hover:text-emerald-300"
            >
              Browse Marketplace
              <MapPin className="ml-2 h-4 w-4" />
            </a>
          </div>

          {/* Animated number counters */}
          <div className="mt-14 grid grid-cols-2 gap-6 sm:gap-10 lg:grid-cols-4">
            {CTA_COUNTERS.map((stat) => (
              <div
                key={stat.label}
                className="cta-reveal flex flex-col items-center rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-5 backdrop-blur-md hover:border-emerald-500/30 transition duration-300"
                style={{ opacity: 0 }}
              >
                <CounterCard stat={stat} reduced={reduced} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================================================================== */}
      {/*  2. Brand & Navigation Section                                       */}
      {/* ================================================================== */}
      <section
        ref={brandRef}
        className="relative border-t border-white/10 px-6 py-16"
        aria-label="Digiland brand"
      >
        <div
          className="brand-reveal mx-auto flex max-w-7xl flex-col items-start gap-12 lg:flex-row lg:items-start lg:justify-between"
          style={{ opacity: 0 }}
        >
          {/* Brand info */}
          <div className="max-w-md space-y-4">
            {/* Logo + Kenya Flag Pill */}
            <div className="flex items-center gap-3">
              <div className="flex items-baseline gap-0" aria-label="Digiland">
                <span className="text-3xl font-black tracking-tight text-white">Digi</span>
                <span className="text-3xl font-black tracking-tight text-emerald-400">land</span>
              </div>
              <span className="rounded-full bg-emerald-500/20 border border-emerald-400/40 px-3 py-1 text-[11px] font-extrabold uppercase tracking-wider text-emerald-300">
                🇰🇪 Kenya Land Protocol
              </span>
            </div>

            <p className="text-sm font-bold text-slate-100">
              Kenya's Autonomous Land Registry & Escrow Infrastructure
            </p>

            <p className="text-sm leading-6 text-slate-300 font-normal">
              Digiland connects land buyers, property sellers, and Law Society of Kenya advocates. We combine automated ArdhiSasa title verification, M-Pesa deposit vaulting, and legal oversight to make Kenya land commerce 100% transparent and safe.
            </p>

            {/* Social media icons */}
            <div className="flex items-center gap-3 pt-2">
              {SOCIAL_LINKS.map((link) => (
                <SocialIcon key={link.label} {...link} />
              ))}
            </div>
          </div>

          {/* ================================================================== */}
          {/*  3. Navigation Columns                                              */}
          {/* ================================================================== */}
          <nav
            ref={navRef}
            className="grid w-full grid-cols-2 gap-8 sm:grid-cols-2 lg:w-auto lg:max-w-2xl lg:grid-cols-4 lg:gap-12"
            aria-label="Footer navigation"
          >
            {NAV_COLUMNS.map((col) => (
              <div key={col.title} className="nav-col-reveal space-y-3" style={{ opacity: 0 }}>
                <h3 className="text-xs font-black uppercase tracking-[0.2em] text-emerald-400">
                  {col.title}
                </h3>
                <ul className="space-y-2.5" role="list">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <FooterNavLink {...link} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </div>
      </section>

      {/* ================================================================== */}
      {/*  4. Trust & Certifications Section                                  */}
      {/* ================================================================== */}
      <section ref={trustRef} className="relative px-6 py-10" aria-label="Trust and certifications">
        <Card className="mx-auto max-w-6xl !border-white/10 !bg-white/[0.03] !p-0 backdrop-blur-xl">
          <div className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
            {TRUST_ITEMS.map((item) => (
              <TrustCard key={item.label} {...item} />
            ))}
          </div>
        </Card>
      </section>

      {/* ================================================================== */}
      {/*  5. Newsletter Subscription                                          */}
      {/* ================================================================== */}
      <section ref={newsletterRef} className="relative px-6 py-14" aria-label="Newsletter subscription">
        {/* Ambient glow behind newsletter */}
        <div
          className="pointer-events-none absolute left-1/2 top-0 h-56 w-56 -translate-x-1/2 rounded-full bg-emerald-500/10 blur-[80px]"
          aria-hidden="true"
        />

        <div className="newsletter-reveal relative z-10 mx-auto max-w-lg text-center" style={{ opacity: 0 }}>
          <div className="flex items-center justify-center gap-2">
            <Mail className="h-5 w-5 text-emerald-400" />
            <h3 className="text-lg font-bold text-white">Stay Informed</h3>
          </div>

          <p className="mt-2 text-sm leading-6 text-slate-300 font-light">
            Receive updates on newly verified land listings, county price benchmarks, and legal policy updates across Kenya.
          </p>

          <form onSubmit={handleSubscribe} className="mt-6 flex items-center gap-2">
            <div className="relative flex-1">
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email address..."
                aria-label="Email address for newsletter"
                className="h-12 rounded-full border-white/15 bg-white/5 pl-5 pr-4 text-sm text-white placeholder:text-slate-500 focus-visible:ring-emerald-400/50 focus-visible:ring-offset-slate-950"
              />
            </div>

            <Button
              type="submit"
              disabled={submitting || subscribed}
              className="h-12 rounded-full bg-emerald-600 px-6 font-bold text-white shadow-[0_0_18px_rgba(5,150,105,0.3)] transition-all duration-300 hover:bg-emerald-500 hover:shadow-[0_0_30px_rgba(5,150,105,0.45)] disabled:opacity-60"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <svg
                    className="h-4 w-4 animate-spin"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                </span>
              ) : subscribed ? (
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4" />
                  Subscribed
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <Send className="h-4 w-4" />
                  Subscribe
                </span>
              )}
            </Button>
          </form>

          <p className="mt-3 text-xs text-slate-500">We respect your privacy. Unsubscribe anytime.</p>
        </div>
      </section>

      {/* ================================================================== */}
      {/*  6. Footer Bottom Bar                                               */}
      {/* ================================================================== */}
      <div className="border-t border-white/10 px-6 py-6 bg-slate-950/90">
        <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 text-xs text-slate-400 sm:flex-row sm:justify-between">
          {/* Left – Copyright & Status */}
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              All Systems Operational
            </span>
            <span className="text-slate-600">&bull;</span>
            <p>&copy; 2026 Digiland Kenya. All rights reserved.</p>
          </div>

          {/* Center – Legal links */}
          <nav className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1 font-medium" aria-label="Legal links">
            <a
              href="/escrow-acts/"
              className="transition-colors duration-200 hover:text-emerald-400"
            >
              Legal & Escrow Acts
            </a>
            <span className="text-white/20" aria-hidden="true">&middot;</span>
            <a
              href="/joint-laws/"
              className="transition-colors duration-200 hover:text-emerald-400"
            >
              Joint Land Laws
            </a>
            <span className="text-white/20" aria-hidden="true">&middot;</span>
            <a
              href="/privacy/"
              className="transition-colors duration-200 hover:text-emerald-400"
            >
              Privacy Policy
            </a>
            <span className="text-white/20" aria-hidden="true">&middot;</span>
            <a
              href="/terms/"
              className="transition-colors duration-200 hover:text-emerald-400"
            >
              Terms of Service
            </a>
          </nav>

          {/* Right – Made in Kenya */}
          <p className="flex items-center gap-1.5 font-bold text-slate-300">
            Made in Kenya <span aria-label="Kenya flag">🇰🇪</span>
          </p>
        </div>
      </div>
    </footer>
  );
}
