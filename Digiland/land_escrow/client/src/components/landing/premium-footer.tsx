import React, { useState, useEffect, useRef, useCallback } from 'react';
import anime from 'animejs';
import {
  ShieldCheck,
  Lock,
  Landmark,
  FileCheck2,
  Zap,
  ArrowRight,
  MapPin,
  CheckCircle2,
  Send,
  Sparkles,
  Twitter,
  Linkedin,
  Github,
  Instagram,
  Globe,
} from 'lucide-react';
import { Button } from '../ui/button.js';
import { getPortalUrl } from '../../lib/partition-context.js';

/* ==========================================================================
   Data Types & Constants
   ========================================================================== */

type NavLink = { label: string; href: string };
type NavColumn = { title: string; links: NavLink[] };
type SocialLink = { icon: React.ElementType; label: string; href: string };

const FOOTER_NAV_COLUMNS: NavColumn[] = [
  {
    title: 'Buyers',
    links: [
      { label: 'Explore Land', href: `${getPortalUrl('app')}/parcels/` },
      { label: 'How Buying Works', href: '/escrow-acts/' },
      { label: 'Valuation Estimator', href: '/#estimator' },
      { label: 'Buyer Protection', href: '/features/' },
    ],
  },
  {
    title: 'Sellers',
    links: [
      { label: 'Sell With Digiland', href: `${getPortalUrl('app')}/accounts/signup/?role=seller` },
      { label: 'List Your Property', href: `${getPortalUrl('app')}/parcels/upload/` },
      { label: 'Escrow Verification', href: '/escrow-acts/' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About Digiland', href: '/features/' },
      { label: 'How It Works', href: '/escrow-acts/' },
      { label: 'Contact Support', href: '/support/' },
    ],
  },
  {
    title: 'Legal & Account',
    links: [
      { label: 'Privacy Policy', href: '/escrow-acts/' },
      { label: 'Terms & Conditions', href: '/escrow-acts/' },
      { label: 'Sign In', href: `${getPortalUrl('app')}/accounts/login/` },
      { label: 'Create Account', href: `${getPortalUrl('app')}/accounts/signup/` },
    ],
  },
];

type StatCounter = {
  target: number;
  prefix?: string;
  suffix: string;
  label: string;
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
    description: 'AES-256 encrypted escrow deposits & SOC 2 compliant security protocol.',
  },
  {
    icon: Landmark,
    label: 'CBK & M-Pesa Regulated',
    description: 'Automated settlement via Central Bank & Safaricom M-Pesa STK.',
  },
  {
    icon: FileCheck2,
    label: 'Land Registry Direct Sync',
    description: 'Instant title deed validation against official Ministry of Lands databases.',
  },
  {
    icon: Zap,
    label: 'Advocate Legal Oversight',
    description: 'Verified legal advocates execute title deeds and contracts.',
  },
];

const SOCIAL_LINKS: SocialLink[] = [
  { icon: Twitter, label: 'Twitter / X', href: 'https://x.com/digilandke' },
  { icon: Linkedin, label: 'LinkedIn', href: 'https://linkedin.com/company/digilandke' },
  { icon: Github, label: 'GitHub', href: 'https://github.com/digilandke' },
  { icon: Instagram, label: 'Instagram', href: 'https://instagram.com/digilandke' },
  { icon: Globe, label: 'Facebook', href: 'https://facebook.com/digilandke' },
];

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

function useScrollReveal(
  ref: React.RefObject<HTMLElement | HTMLDivElement | null>,
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

    targets.forEach((t) => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(20px)';
    });

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          anime({
            targets,
            opacity: [0, 1],
            translateY: [20, 0],
            delay: anime.stagger(stagger),
            duration: 650,
            easing: 'easeOutCubic',
          });
          observer.disconnect();
        });
      },
      { threshold: 0.1 },
    );

    observer.observe(root);
    return () => observer.disconnect();
  }, [ref, selector, reduced, stagger]);
}

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

function formatNumber(value: number, decimals: number): string {
  if (decimals > 0) {
    return value.toFixed(decimals);
  }
  const rounded = Math.round(value);
  return rounded.toLocaleString('en-KE');
}

function FooterNavLink({ label, href }: NavLink) {
  return (
    <a
      href={href}
      className="group relative inline-block text-sm font-semibold text-slate-600 transition-colors duration-200 hover:text-emerald-700 focus-visible:outline-none"
    >
      {label}
      <span
        className="absolute bottom-0 left-1/2 h-0.5 w-0 -translate-x-1/2 bg-emerald-600 transition-all duration-300 group-hover:w-full"
        aria-hidden="true"
      />
    </a>
  );
}

function SocialIcon({ icon: Icon, label, href }: SocialLink) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      className="group relative flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 transition-all duration-300 hover:scale-110 hover:border-emerald-500 hover:bg-emerald-50 hover:text-emerald-700 shadow-sm"
    >
      <Icon className="h-4 w-4" />
    </a>
  );
}

function CounterCard({ stat, reduced }: { stat: StatCounter; reduced: boolean }) {
  const numberRef = useRef<HTMLSpanElement>(null);
  useCounter(stat.target, stat.decimals ?? 0, numberRef, reduced);

  return (
    <div className="flex flex-col items-center justify-center gap-1 text-center bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-lg shadow-slate-200/50 hover:shadow-xl hover:border-emerald-500/30 transition-all">
      <div className="flex items-baseline gap-0.5">
        {stat.prefix && (
          <span className="text-sm font-bold text-slate-600 sm:text-base">{stat.prefix}</span>
        )}
        <span
          ref={numberRef}
          className="text-2xl font-black tracking-tight text-slate-950 sm:text-3xl lg:text-4xl"
        >
          0
        </span>
        <span className="text-lg font-bold text-emerald-600 sm:text-xl lg:text-2xl">{stat.suffix}</span>
      </div>
      <span className="text-xs font-bold uppercase tracking-wider text-slate-500 sm:text-xs">
        {stat.label}
      </span>
    </div>
  );
}

function TrustCard({ icon: Icon, label, description }: TrustItem) {
  return (
    <div className="footer-reveal-item flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-200 hover:border-emerald-500/40 hover:shadow-md">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-500/20 bg-emerald-50">
        <Icon className="h-5 w-5 text-emerald-600" />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-bold text-slate-900">{label}</p>
        <p className="mt-0.5 text-xs font-normal leading-5 text-slate-600">{description}</p>
      </div>
    </div>
  );
}

export function PremiumFooter() {
  const reduced = useReducedMotion();

  const ctaRef = useRef<HTMLElement>(null);
  const brandRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLDivElement>(null);
  const trustRef = useRef<HTMLElement>(null);

  useScrollReveal(ctaRef, '.cta-reveal', reduced, 100);
  useScrollReveal(brandRef, '.brand-reveal', reduced, 70);
  useScrollReveal(navRef, '.nav-col-reveal', reduced, 120);
  useScrollReveal(trustRef, '.footer-reveal-item', reduced, 90);

  return (
    <footer className="relative overflow-hidden bg-gradient-to-b from-slate-50 via-white to-slate-100 text-slate-900 border-t border-slate-200" role="contentinfo">
      
      {/* 1. Light Rafiki AI Style CTA Section */}
      <section
        ref={ctaRef}
        className="cta-section relative overflow-hidden px-4 sm:px-6 py-16 sm:py-20 lg:py-24"
        aria-label="Call to action"
      >
        <div className="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 h-[500px] w-[700px] rounded-full bg-emerald-400/10 blur-[130px]" />

        <div className="cta-reveal relative z-10 mx-auto max-w-5xl text-center space-y-6" style={{ opacity: 0 }}>
          
          <h2 className="text-3xl font-black tracking-tight sm:text-4xl lg:text-5xl text-slate-950">
            Ready to Transact Land{' '}
            <span className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500 bg-clip-text text-transparent">
              With Absolute Trust?
            </span>
          </h2>

          <p className="mx-auto max-w-2xl text-base leading-7 text-slate-600 sm:text-lg sm:leading-8 font-medium">
            Join thousands of buyers and property owners across Kenya using Digiland for verified title deeds, M-Pesa escrow protection, and legal closing.
          </p>

          {/* Action Buttons */}
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href={`${getPortalUrl('app')}/accounts/signup/`}
              className="inline-flex h-12 items-center justify-center rounded-xl bg-emerald-600 px-8 text-sm font-extrabold text-white shadow-xl shadow-emerald-600/30 transition-all hover:bg-emerald-500 hover:scale-[1.02]"
            >
              <span>Get Started Free</span>
              <ArrowRight className="ml-2 h-4 w-4" />
            </a>
            <a
              href={`${getPortalUrl('app')}/parcels/`}
              className="inline-flex h-12 items-center justify-center rounded-xl border border-slate-300 bg-white px-8 text-sm font-bold text-slate-800 shadow-sm transition-all hover:bg-slate-50 hover:border-slate-400"
            >
              <span>Browse Marketplace</span>
              <MapPin className="ml-2 h-4 w-4 text-emerald-600" />
            </a>
          </div>

          {/* Floating Stat Counters (Light Mode) */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 pt-10">
            {CTA_COUNTERS.map((stat) => (
              <CounterCard key={stat.label} stat={stat} reduced={reduced} />
            ))}
          </div>

        </div>
      </section>

      {/* 2. Trust & Guarantee Cards */}
      <section ref={trustRef} className="border-t border-slate-200/80 bg-white px-4 sm:px-6 py-12">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {TRUST_ITEMS.map((item) => (
              <TrustCard key={item.label} {...item} />
            ))}
          </div>
        </div>
      </section>

      {/* 3. Footer Links & Copyright */}
      <div className="border-t border-slate-200 bg-slate-50 px-4 sm:px-6 py-12">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 lg:grid-cols-12">
            
            {/* Brand column */}
            <div ref={brandRef} className="lg:col-span-5 space-y-4">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white font-black shadow-md shadow-emerald-600/30">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <span className="text-xl font-black tracking-tight text-slate-950">Digiland</span>
              </div>

              <p className="text-sm font-bold text-slate-800">
                Kenya's Land Escrow & Verification Protocol
              </p>

              <p className="text-xs leading-relaxed text-slate-500 max-w-sm">
                Digiland protects land buyers with automated title deed checks, M-Pesa deposit vaulting, and legal oversight to make Kenya land commerce 100% transparent and safe.
              </p>

              <div className="flex items-center gap-2 pt-2">
                {SOCIAL_LINKS.map((link) => (
                  <SocialIcon key={link.label} {...link} />
                ))}
              </div>
            </div>

            {/* Nav Columns */}
            <div ref={navRef} className="lg:col-span-7 grid grid-cols-2 sm:grid-cols-3 gap-6">
              {FOOTER_NAV_COLUMNS.map((col) => (
                <div key={col.title} className="nav-col-reveal space-y-3">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-900">{col.title}</h3>
                  <ul className="space-y-2">
                    {col.links.map((link) => (
                      <li key={link.label}>
                        <FooterNavLink {...link} />
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

          </div>

          {/* Bottom copyright */}
          <div className="mt-10 border-t border-slate-200/80 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-semibold text-slate-500">
            <p>© {new Date().getFullYear()} Digiland Protocol. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <a href="/privacy/" className="hover:text-emerald-700 transition">Privacy Policy</a>
              <span>•</span>
              <a href="/terms/" className="hover:text-emerald-700 transition">Terms of Service</a>
              <span>•</span>
              <a href="/security/" className="hover:text-emerald-700 transition">Security</a>
            </div>
          </div>

        </div>
      </div>

    </footer>
  );
}
