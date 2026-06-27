import React, { useState, useEffect, useRef, useCallback } from 'react';
import anime from 'animejs';
import {
  Search,
  Upload,
  ShieldCheck,
  Lock,
  FileSignature,
  CircleCheckBig,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  Gauge,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { cn } from '../../lib/utils.js';

/* ──────────────────────────── types ──────────────────────────── */

type RoleFilter = 'all' | 'buyer' | 'seller';

type WalkthroughStep = {
  icon: LucideIcon;
  color: string;
  bg: string;
  heading: string;
  paragraph: string;
};

type WalkthroughScene = {
  id: number;
  label: string;
  roles: 'both' | 'buyer' | 'seller';
  kicker: string;
  kickerColor: string;
  kickerBg: string;
  title: string;
  description: string;
  caption: string;
  steps: WalkthroughStep[];
};

/* ──────────────────────────── data ──────────────────────────── */

export const SCENES: WalkthroughScene[] = [
  {
    id: 1,
    label: 'Discover Land',
    roles: 'buyer',
    kicker: 'Buyer · Step 1',
    kickerColor: 'text-emerald-200',
    kickerBg: 'bg-emerald-500/20 border-emerald-400/30',
    title: 'Discover Your Perfect Plot',
    description:
      'Browse verified land listings across Kenya with intelligent filters, map views, and real-time market signals.',
    caption: 'Search thousands of verified land listings across 47 counties.',
    steps: [
      { icon: Search, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Smart Search', paragraph: 'Filter by county, size, price, and land use.' },
      { icon: Gauge, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Market Signals', paragraph: 'See demand trends and price movement live.' },
      { icon: ShieldCheck, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Verified Badges', paragraph: 'Every listing passes a verification check.' },
    ],
  },
  {
    id: 2,
    label: 'List Your Land',
    roles: 'seller',
    kicker: 'Seller · Step 1',
    kickerColor: 'text-amber-200',
    kickerBg: 'bg-amber-500/20 border-amber-400/30',
    title: 'List Land in Minutes',
    description:
      'Upload documents, set your price, and publish your listing to thousands of verified buyers on the platform.',
    caption: 'Create a listing with documents, photos, and pricing in under 5 minutes.',
    steps: [
      { icon: Upload, color: 'text-amber-300', bg: 'bg-amber-500/15', heading: 'Upload Documents', paragraph: 'Title deeds, maps, and consent letters.' },
      { icon: Gauge, color: 'text-amber-300', bg: 'bg-amber-500/15', heading: 'Set Pricing', paragraph: 'Use smart estimates or set your own price.' },
      { icon: CircleCheckBig, color: 'text-amber-300', bg: 'bg-amber-500/15', heading: 'Publish & Reach', paragraph: 'Go live to the entire buyer network.' },
    ],
  },
  {
    id: 3,
    label: 'KYC Identity',
    roles: 'both',
    kicker: 'Both · Step 2',
    kickerColor: 'text-blue-200',
    kickerBg: 'bg-blue-500/20 border-blue-400/30',
    title: 'Verify Your Identity',
    description:
      'Complete KYC verification to build trust and unlock escrow. Both buyer and seller must verify before any transaction proceeds.',
    caption: 'KYC verification is required for both parties before escrow.',
    steps: [
      { icon: ShieldCheck, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'ID Verification', paragraph: 'National ID or passport upload and check.' },
      { icon: Lock, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'Secure Storage', paragraph: 'Documents encrypted and never shared.' },
      { icon: CircleCheckBig, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'Trust Badge', paragraph: 'Verified badge appears on your profile.' },
    ],
  },
  {
    id: 4,
    label: 'Fund Escrow',
    roles: 'buyer',
    kicker: 'Buyer · Step 3',
    kickerColor: 'text-emerald-200',
    kickerBg: 'bg-emerald-500/20 border-emerald-400/30',
    title: 'Fund the Escrow',
    description:
      'Securely deposit the purchase amount into an escrow account. Funds are held safely until all conditions are met.',
    caption: 'Funds are held in escrow until all contract conditions are satisfied.',
    steps: [
      { icon: Lock, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Secure Deposit', paragraph: 'M-Pesa or bank transfer into escrow.' },
      { icon: ShieldCheck, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Held Safely', paragraph: 'Funds locked until contract conditions met.' },
      { icon: Gauge, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Full Transparency', paragraph: 'Track deposit status in real time.' },
    ],
  },
  {
    id: 5,
    label: 'Sign Contract',
    roles: 'both',
    kicker: 'Both · Step 4',
    kickerColor: 'text-blue-200',
    kickerBg: 'bg-blue-500/20 border-blue-400/30',
    title: 'Sign the Contract',
    description:
      'Review and digitally sign the sale agreement. Both parties sign securely online with full audit trails and legal validity.',
    caption: 'Digital signatures with legal validity and full audit trails.',
    steps: [
      { icon: FileSignature, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'Review Terms', paragraph: 'Read every clause before you sign.' },
      { icon: ShieldCheck, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'Digital Signature', paragraph: 'Legally binding e-signature on both sides.' },
      { icon: Lock, color: 'text-blue-300', bg: 'bg-blue-500/15', heading: 'Audit Trail', paragraph: 'Timestamped record of every action.' },
    ],
  },
  {
    id: 6,
    label: 'Transfer Done',
    roles: 'both',
    kicker: 'Final Step',
    kickerColor: 'text-emerald-200',
    kickerBg: 'bg-emerald-500/20 border-emerald-400/30',
    title: 'Transfer Complete',
    description:
      'Escrow releases funds to the seller, the title is transferred, and both parties receive confirmation. The land is officially yours.',
    caption: 'Funds released and title transferred — the deal is done.',
    steps: [
      { icon: CircleCheckBig, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Funds Released', paragraph: 'Seller receives payment automatically.' },
      { icon: ShieldCheck, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Title Transferred', paragraph: 'Ownership officially recorded and updated.' },
      { icon: CircleCheckBig, color: 'text-emerald-300', bg: 'bg-emerald-500/15', heading: 'Deal Closed', paragraph: 'Both parties receive final confirmation.' },
    ],
  },
];

const SPEED_OPTIONS = [0.5, 1, 1.5, 2] as const;
const AUTOPLAY_DURATION = 6000;

/* ──────────────────────────── helpers ──────────────────────────── */

function useReducedMotion() {
  const [prefersReduced, setPrefersReduced] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setPrefersReduced(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return prefersReduced;
}

function getFilteredScenes(role: RoleFilter) {
  if (role === 'all') return SCENES;
  return SCENES.filter((s) => s.roles === role || s.roles === 'both');
}

/* ──────────────────────────── mock device screens ──────────────────────────── */

export function MockBrowse() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      {/* Search bar */}
      <div className="flex items-center gap-2 rounded-xl bg-slate-800/80 px-3 py-2.5">
        <Search className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-xs text-slate-400">Search county, size, price...</span>
      </div>
      {/* Filter chips */}
      <div className="flex gap-1.5">
        {['Residential', 'Commercial', 'Agricultural'].map((chip) => (
          <span key={chip} className={cn(
            'rounded-full px-2.5 py-1 text-[10px] font-semibold',
            chip === 'Residential' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-700/60 text-slate-400'
          )}>
            {chip}
          </span>
        ))}
      </div>
      {/* Property cards */}
      <div className="grid flex-1 grid-cols-2 gap-2">
        {[
          { name: 'Karen Plot', price: 'KSh 4.2M', tag: 'Verified' },
          { name: 'Kitengela 0.5ac', price: 'KSh 1.8M', tag: 'Hot' },
          { name: 'Syokimau Land', price: 'KSh 2.5M', tag: 'Verified' },
          { name: 'Isinya 1ac', price: 'KSh 950K', tag: 'New' },
        ].map((card) => (
          <div key={card.name} className="flex flex-col gap-1.5 rounded-xl bg-slate-800/60 p-2.5">
            <div className="h-14 rounded-lg bg-gradient-to-br from-emerald-900/40 to-slate-800/80" />
            <span className="text-[11px] font-semibold text-white">{card.name}</span>
            <span className="text-[10px] text-emerald-300">{card.price}</span>
            <span className="w-fit rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[8px] font-bold text-emerald-300">
              {card.tag}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MockUpload() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      {/* Dropzone */}
      <div className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-amber-400/30 bg-amber-500/5 py-5">
        <Upload className="h-6 w-6 text-amber-300" />
        <span className="text-[10px] font-semibold text-amber-200">Drop title deed & photos</span>
        <span className="text-[9px] text-slate-400">PDF, JPG, PNG up to 10 MB</span>
      </div>
      {/* Form fields */}
      <div className="space-y-2">
        {['Land Title', 'Asking Price (KSh)', 'County / Location'].map((field) => (
          <div key={field} className="flex flex-col gap-1">
            <span className="text-[9px] font-semibold text-slate-400">{field}</span>
            <div className="h-7 rounded-lg bg-slate-800/70 px-2.5 pt-1.5 text-[10px] text-slate-300">
              {field === 'Asking Price (KSh)' ? '4,200,000' : field === 'County / Location' ? 'Nairobi · Karen' : ''}
            </div>
          </div>
        ))}
      </div>
      {/* Submit */}
      <button className="mt-auto rounded-xl bg-amber-500/20 py-2 text-[11px] font-bold text-amber-200 transition hover:bg-amber-500/30">
        Publish Listing
      </button>
    </div>
  );
}

export function MockKYC() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <div className="flex items-center gap-2 rounded-xl bg-blue-500/10 px-3 py-2.5">
        <ShieldCheck className="h-4 w-4 text-blue-300" />
        <span className="text-xs font-semibold text-blue-200">Identity Verification</span>
      </div>
      {/* Checklist */}
      <div className="flex flex-col gap-2">
        {[
          { label: 'National ID uploaded', state: 'done' as const },
          { label: 'Selfie verification', state: 'done' as const },
          { label: 'Address confirmation', state: 'active' as const },
          { label: 'Bank account link', state: 'todo' as const },
          { label: 'Tax compliance cert', state: 'todo' as const },
        ].map((item) => (
          <div key={item.label} className={cn(
            'flex items-center gap-2.5 rounded-xl px-3 py-2.5',
            item.state === 'done' && 'bg-emerald-500/10',
            item.state === 'active' && 'bg-blue-500/10 ring-1 ring-blue-400/30',
            item.state === 'todo' && 'bg-slate-800/40',
          )}>
            <div className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[10px]',
              item.state === 'done' && 'bg-emerald-500/20 text-emerald-300',
              item.state === 'active' && 'bg-blue-500/20 text-blue-300',
              item.state === 'todo' && 'bg-slate-700/60 text-slate-500',
            )}>
              {item.state === 'done' ? '✓' : item.state === 'active' ? '→' : '○'}
            </div>
            <span className={cn(
              'text-[11px] font-medium',
              item.state === 'done' && 'text-emerald-200',
              item.state === 'active' && 'text-blue-200',
              item.state === 'todo' && 'text-slate-500',
            )}>
              {item.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function MockEscrow() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      {/* Amount card */}
      <div className="flex flex-col items-center gap-1 rounded-xl bg-emerald-500/10 py-4">
        <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-300/70">Escrow Amount</span>
        <span className="text-2xl font-black text-white">KSh 4,200,000</span>
        <span className="text-[10px] text-slate-400">Karen · 0.5 acres · Residential</span>
      </div>
      {/* Payment method */}
      <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400">Payment Method</span>
      {[
        { name: 'M-Pesa', detail: 'Paybill · Instant', selected: true },
        { name: 'Bank Transfer', detail: 'EFT · 1-2 business days', selected: false },
      ].map((method) => (
        <div key={method.name} className={cn(
          'flex items-center gap-3 rounded-xl px-3 py-2.5',
          method.selected ? 'bg-emerald-500/10 ring-1 ring-emerald-400/30' : 'bg-slate-800/40',
        )}>
          <div className={cn(
            'h-4 w-4 rounded-full border-2',
            method.selected ? 'border-emerald-400 bg-emerald-400' : 'border-slate-600',
          )} />
          <div>
            <span className={cn('text-[11px] font-semibold', method.selected ? 'text-white' : 'text-slate-400')}>
              {method.name}
            </span>
            <span className="ml-2 text-[9px] text-slate-500">{method.detail}</span>
          </div>
        </div>
      ))}
      <button className="mt-auto rounded-xl bg-emerald-600/30 py-2 text-[11px] font-bold text-emerald-200 transition hover:bg-emerald-600/40">
        Deposit to Escrow
      </button>
    </div>
  );
}

export function MockContract() {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      {/* Contract header */}
      <div className="flex items-center gap-2 rounded-xl bg-blue-500/10 px-3 py-2.5">
        <FileSignature className="h-4 w-4 text-blue-300" />
        <span className="text-xs font-semibold text-blue-200">Sale Agreement</span>
      </div>
      {/* Contract body */}
      <div className="flex-1 space-y-2 rounded-xl bg-slate-800/40 p-3">
        {[
          'THIS AGREEMENT is made on 12 March 2025',
          'BETWEEN the Seller and the Buyer for the',
          'transfer of land parcel LR No. Karen/245',
          'at a consideration of KSh 4,200,000.',
          '',
          'The Seller warrants clear title and that',
          'the property is free from encumbrances.',
        ].map((line, i) => (
          <p key={i} className="text-[9px] leading-4 text-slate-400" style={{ opacity: line ? 1 : 0 }}>
            {line || '\u00A0'}
          </p>
        ))}
      </div>
      {/* Signature pad */}
      <div className="rounded-xl border border-dashed border-blue-400/20 bg-blue-500/5 p-2.5">
        <span className="text-[9px] font-semibold text-blue-300/60">Sign here</span>
        <div className="mt-1 h-8">
          <svg className="h-full w-full" viewBox="0 0 200 30">
            <path d="M10 20 C 40 5, 60 25, 90 15 S 140 5, 170 18 Q 185 22, 190 15" fill="none" stroke="rgba(147,197,253,0.6)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

export function MockComplete() {
  return (
    <div className="flex h-full flex-col items-center gap-3 p-4">
      {/* Success ring */}
      <div className="relative flex h-20 w-20 items-center justify-center">
        <svg className="absolute h-full w-full -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="rgba(5,150,105,0.15)" strokeWidth="4" />
          <circle cx="40" cy="40" r="36" fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="226" strokeDashoffset="0" strokeLinecap="round" />
        </svg>
        <CircleCheckBig className="h-9 w-9 text-emerald-400" />
      </div>
      <span className="text-base font-black text-white">Transfer Complete</span>
      <span className="text-center text-[10px] leading-5 text-slate-400">
        KSh 4,200,000 released to seller.<br />Title deed updated and recorded.
      </span>
      {/* Status chips */}
      <div className="mt-2 flex flex-wrap justify-center gap-1.5">
        {[
          { label: 'Funds Released', color: 'bg-emerald-500/15 text-emerald-300' },
          { label: 'Title Transferred', color: 'bg-emerald-500/15 text-emerald-300' },
          { label: 'Audit Logged', color: 'bg-blue-500/15 text-blue-300' },
        ].map((chip) => (
          <span key={chip.label} className={cn('rounded-full px-2.5 py-1 text-[9px] font-bold', chip.color)}>
            {chip.label}
          </span>
        ))}
      </div>
      {/* Detail card */}
      <div className="mt-auto w-full rounded-xl bg-slate-800/50 p-3">
        <div className="grid grid-cols-2 gap-2 text-center">
          {[
            { label: 'Property', value: 'Karen Plot' },
            { label: 'Amount', value: 'KSh 4.2M' },
            { label: 'Buyer', value: 'Verified' },
            { label: 'Seller', value: 'Verified' },
          ].map((item) => (
            <div key={item.label}>
              <div className="text-[8px] uppercase tracking-wider text-slate-500">{item.label}</div>
              <div className="text-[11px] font-semibold text-white">{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const MOCK_SCREENS: Record<number, React.FC> = {
  1: MockBrowse,
  2: MockUpload,
  3: MockKYC,
  4: MockEscrow,
  5: MockContract,
  6: MockComplete,
};

/* ──────────────────────────── main component ──────────────────────────── */

export function AnimatedWalkthrough() {
  const reducedMotion = useReducedMotion();

  /* ── state ── */
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [speedIndex, setSpeedIndex] = useState(1); // default 1x
  const [showCompletion, setShowCompletion] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  /* ── derived ── */
  const scenes = getFilteredScenes(roleFilter);
  const currentScene = scenes[activeIndex] ?? SCENES[0];
  const speed = SPEED_OPTIONS[speedIndex];

  /* ── refs ── */
  const stageRef = useRef<HTMLDivElement>(null);
  const sceneContentRef = useRef<HTMLDivElement>(null);
  const deviceFrameRef = useRef<HTMLDivElement>(null);
  const countdownRef = useRef<SVGCircleElement>(null);
  const autoplayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const animeRef = useRef<anime.AnimeInstance | null>(null);
  const countdownAnimeRef = useRef<anime.AnimeInstance | null>(null);

  /* ── autoplay timer ── */
  const clearAutoplay = useCallback(() => {
    if (autoplayTimerRef.current) {
      clearTimeout(autoplayTimerRef.current);
      autoplayTimerRef.current = null;
    }
  }, []);

  const startAutoplay = useCallback(() => {
    clearAutoplay();
    if (!isPlaying) return;
    const duration = AUTOPLAY_DURATION / speed;
    autoplayTimerRef.current = setTimeout(() => {
      goNext();
    }, duration);
  }, [isPlaying, speed, activeIndex, scenes.length, roleFilter]);

  /* ── countdown ring ── */
  const animateCountdown = useCallback(() => {
    if (countdownAnimeRef.current) countdownAnimeRef.current.pause();

    const el = countdownRef.current;
    if (!el || !isPlaying || reducedMotion) {
      if (el) el.style.strokeDashoffset = '0';
      return;
    }

    const circumference = 2 * Math.PI * 14;
    el.style.strokeDasharray = `${circumference}`;
    el.style.strokeDashoffset = '0';

    countdownAnimeRef.current = anime({
      targets: el,
      strokeDashoffset: [0, circumference],
      duration: AUTOPLAY_DURATION / speed,
      easing: 'linear',
    });
  }, [isPlaying, speed, reducedMotion]);

  /* ── scene entrance animation ── */
  const animateEntrance = useCallback(() => {
    if (animeRef.current) animeRef.current.pause();

    const content = sceneContentRef.current;
    const device = deviceFrameRef.current;
    if (!content || reducedMotion) {
      if (content) {
        content.querySelectorAll('.scene-enter').forEach((el) => {
          (el as HTMLElement).style.opacity = '1';
          (el as HTMLElement).style.transform = 'none';
        });
      }
      if (device) {
        device.style.opacity = '1';
        device.style.transform = 'none';
      }
      return;
    }

    const items = content.querySelectorAll<HTMLElement>('.scene-enter');
    anime({
      targets: items,
      opacity: [0, 1],
      translateY: [20, 0],
      delay: anime.stagger(80, { start: 100 }),
      duration: 500,
      easing: 'easeOutCubic',
    });

    if (device) {
      anime({
        targets: device,
        opacity: [0, 1],
        translateX: [40, 0],
        duration: 600,
        easing: 'easeOutCubic',
        delay: 200,
      });
    }
  }, [reducedMotion]);

  /* ── scene transition ── */
  const transitionTo = useCallback(
    (nextIndex: number, direction: 'forward' | 'backward' = 'forward') => {
      if (isTransitioning || nextIndex === activeIndex) return;
      setIsTransitioning(true);
      clearAutoplay();
      if (countdownAnimeRef.current) countdownAnimeRef.current.pause();

      const content = sceneContentRef.current;
      const device = deviceFrameRef.current;

      if (reducedMotion || !content) {
        setActiveIndex(nextIndex);
        setIsTransitioning(false);
        return;
      }

      const exitX = direction === 'forward' ? -60 : 60;
      const enterX = direction === 'forward' ? 60 : -60;

      const exitAnim = anime({
        targets: [content, device].filter(Boolean),
        opacity: [1, 0],
        translateX: [0, exitX],
        duration: 300,
        easing: 'easeInCubic',
        complete: () => {
          setActiveIndex(nextIndex);
          if (device) {
            device.style.transform = `translateX(${enterX}px)`;
          }
          content.style.transform = `translateX(${enterX}px)`;

          anime({
            targets: [content, device].filter(Boolean),
            opacity: [0, 1],
            translateX: [enterX, 0],
            duration: 400,
            easing: 'easeOutCubic',
            complete: () => {
              setIsTransitioning(false);
            },
          });

          // Re-run entrance stagger after position is set
          const items = content.querySelectorAll<HTMLElement>('.scene-enter');
          items.forEach((el) => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
          });

          setTimeout(() => animateEntrance(), 50);
        },
      });

      animeRef.current = exitAnim;
    },
    [activeIndex, isTransitioning, reducedMotion, clearAutoplay, animateEntrance]
  );

  /* ── navigation ── */
  const goNext = useCallback(() => {
    if (activeIndex >= scenes.length - 1) {
      setShowCompletion(true);
      clearAutoplay();
      if (countdownAnimeRef.current) countdownAnimeRef.current.pause();
      return;
    }
    transitionTo(activeIndex + 1, 'forward');
  }, [activeIndex, scenes.length, transitionTo, clearAutoplay]);

  const goPrev = useCallback(() => {
    if (showCompletion) {
      setShowCompletion(false);
      return;
    }
    if (activeIndex <= 0) return;
    transitionTo(activeIndex - 1, 'backward');
  }, [activeIndex, showCompletion, transitionTo]);

  const goToScene = useCallback(
    (index: number) => {
      if (showCompletion) setShowCompletion(false);
      const direction = index > activeIndex ? 'forward' : 'backward';
      transitionTo(index, direction);
    },
    [activeIndex, showCompletion, transitionTo]
  );

  /* ── effects ── */
  useEffect(() => {
    if (showCompletion) return;
    if (isPlaying) {
      startAutoplay();
      animateCountdown();
    }
    return () => clearAutoplay();
  }, [isPlaying, activeIndex, speed, scenes.length, showCompletion, startAutoplay, animateCountdown, clearAutoplay]);

  useEffect(() => {
    if (!showCompletion) animateEntrance();
  }, [activeIndex, roleFilter, showCompletion, animateEntrance]);

  // Reset when role filter changes
  useEffect(() => {
    setActiveIndex(0);
    setShowCompletion(false);
  }, [roleFilter]);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.key === 'ArrowRight') {
        goNext();
      } else if (e.key === 'ArrowLeft') {
        goPrev();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goNext, goPrev]);

  /* ── handlers ── */
  const handlePlayPause = () => setIsPlaying((p) => !p);

  const cycleSpeed = () => setSpeedIndex((i) => (i + 1) % SPEED_OPTIONS.length);

  const handleScrub = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const idx = Math.round(ratio * (scenes.length - 1));
    goToScene(idx);
  };

  const restart = () => {
    setShowCompletion(false);
    setActiveIndex(0);
    setIsPlaying(true);
  };

  /* ── device hover tilt ── */
  const handleDevicePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reducedMotion) return;
    const el = deviceFrameRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * -5;
    el.style.transform = `perspective(800px) rotateY(${x}deg) rotateX(${y}deg)`;
  };

  const handleDevicePointerLeave = () => {
    if (reducedMotion) return;
    const el = deviceFrameRef.current;
    if (!el) return;
    el.style.transform = 'perspective(800px) rotateY(0deg) rotateX(0deg)';
    el.style.transition = 'transform 0.4s ease';
    setTimeout(() => {
      if (el) el.style.transition = '';
    }, 400);
  };

  /* ── compute progress ── */
  const progress = scenes.length > 1 ? activeIndex / (scenes.length - 1) : 0;

  /* ── render ── */
  const MockScreen = MOCK_SCREENS[currentScene.id];

  return (
    <section
      className="relative w-full overflow-hidden rounded-[2rem] bg-[#0f172a] py-6 sm:py-8"
      aria-label="How It Works walkthrough"
    >
      {/* Ambient glow orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-emerald-500/10 blur-[120px]" />
        <div className="absolute -right-24 top-1/3 h-80 w-80 rounded-full bg-blue-500/8 blur-[100px]" />
        <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-amber-500/6 blur-[90px]" />
      </div>

      {/* Film grain overlay */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\'/%3E%3C/svg%3E")' }} />

      <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6">
        {/* ── Top bar ── */}
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            {/* Logo */}
            <span className="text-lg font-black tracking-tight">
              <span className="text-white">Digi</span>
              <span className="text-emerald-400">land</span>
            </span>
            {/* Pulsing dot + label */}
            <div className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-200">How It Works</span>
            </div>
          </div>
          {/* Step indicator */}
          <span className="text-xs font-medium text-slate-400">
            Stage{' '}
            <span className="font-bold text-white">{activeIndex + 1}</span>
            {' '}of{' '}
            <span className="font-bold text-white">{scenes.length}</span>
          </span>
        </div>

        {/* ── Role selector ── */}
        <div className="mb-5 flex gap-1.5 rounded-full border border-white/8 bg-slate-800/40 p-1 w-fit">
          {(['all', 'buyer', 'seller'] as const).map((role) => (
            <button
              key={role}
              onClick={() => setRoleFilter(role)}
              className={cn(
                'rounded-full px-4 py-1.5 text-[11px] font-bold uppercase tracking-wider transition',
                roleFilter === role
                  ? 'bg-emerald-500/20 text-emerald-200 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              )}
              aria-label={`Filter by ${role} steps`}
              aria-pressed={roleFilter === role}
            >
              {role === 'all' ? 'All Steps' : role === 'buyer' ? 'Buyer' : 'Seller'}
            </button>
          ))}
        </div>

        {/* ── Timeline bar ── */}
        <div className="mb-6 flex items-center gap-2" role="group" aria-label="Walkthrough timeline">
          {/* Scrubber track */}
          <div
            className="relative flex h-2 flex-1 cursor-pointer items-center rounded-full bg-slate-700/50"
            onClick={handleScrub}
            role="slider"
            aria-label="Scrub to scene"
            aria-valuenow={activeIndex + 1}
            aria-valuemin={1}
            aria-valuemax={scenes.length}
            tabIndex={0}
          >
            {/* Filled track */}
            <div
              className="absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-300"
              style={{ width: `${progress * 100}%` }}
            />
            {/* Nodes */}
            <div className="relative z-10 flex w-full justify-between px-0">
              {scenes.map((scene, i) => (
                <button
                  key={scene.id}
                  onClick={(e) => { e.stopPropagation(); goToScene(i); }}
                  className={cn(
                    'flex h-4 w-4 items-center justify-center rounded-full border-2 transition-all duration-200',
                    i === activeIndex
                      ? 'border-emerald-400 bg-emerald-400 scale-125 shadow-lg shadow-emerald-400/30'
                      : i < activeIndex
                      ? 'border-emerald-500/60 bg-emerald-500/40'
                      : 'border-slate-600 bg-slate-800'
                  )}
                  aria-label={`Go to ${scene.label}`}
                  tabIndex={-1}
                >
                  <span className="sr-only">{scene.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Stage ── */}
        <div
          ref={stageRef}
          className="relative overflow-hidden rounded-2xl border border-white/8 bg-slate-900/60 shadow-2xl backdrop-blur-xl"
        >
          {!showCompletion ? (
            <div className="flex flex-col lg:flex-row">
              {/* Left panel - Content */}
              <div ref={sceneContentRef} className="flex-1 p-6 sm:p-8 lg:p-10">
                {/* Scene number watermark */}
                <div className="pointer-events-none absolute left-4 top-4 text-7xl font-black text-white/[0.03] select-none sm:left-8 sm:text-8xl lg:left-10">
                  {String(currentScene.id).padStart(2, '0')}
                </div>

                {/* Kicker badge */}
                <div className="scene-enter mb-4" style={{ opacity: 0 }}>
                  <span className={cn(
                    'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-widest',
                    currentScene.kickerBg,
                    currentScene.kickerColor
                  )}>
                    {currentScene.kicker}
                  </span>
                </div>

                {/* Title */}
                <h3 className="scene-enter mb-3 text-2xl font-black tracking-tight text-white sm:text-3xl lg:text-4xl" style={{ opacity: 0 }}>
                  {currentScene.title}
                </h3>

                {/* Description */}
                <p className="scene-enter mb-6 max-w-lg text-sm leading-7 text-slate-300 sm:text-base" style={{ opacity: 0 }}>
                  {currentScene.description}
                </p>

                {/* Steps */}
                <div className="space-y-4">
                  {currentScene.steps.map((step, i) => {
                    const Icon = step.icon;
                    return (
                      <div key={i} className="scene-enter flex items-start gap-3" style={{ opacity: 0 }}>
                        <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', step.bg)}>
                          <Icon className={cn('h-4 w-4', step.color)} />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{step.heading}</div>
                          <div className="text-xs leading-6 text-slate-400">{step.paragraph}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right panel - Mock Device */}
              <div className="hidden p-6 sm:flex sm:items-center sm:justify-center lg:w-[380px] lg:p-8">
                <div
                  ref={deviceFrameRef}
                  className="scene-enter relative w-full max-w-[320px] overflow-hidden rounded-[1.5rem] border border-white/10 bg-slate-950 shadow-[0_24px_60px_-16px_rgba(0,0,0,0.6)]"
                  style={{
                    perspective: '800px',
                    transform: 'perspective(800px) rotateY(-2deg) rotateX(1deg)',
                    opacity: 0,
                  }}
                  onPointerMove={handleDevicePointerMove}
                  onPointerLeave={handleDevicePointerLeave}
                >
                  {/* Notch */}
                  <div className="flex items-center justify-center py-2">
                    <div className="h-1.5 w-16 rounded-full bg-slate-700/60" />
                  </div>
                  {/* Screen */}
                  <div className="mx-2 mb-3 h-[300px] overflow-hidden rounded-xl bg-slate-900">
                    {MockScreen && <MockScreen />}
                  </div>
                  {/* Home indicator */}
                  <div className="flex justify-center pb-2">
                    <div className="h-1 w-10 rounded-full bg-slate-600/40" />
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* ── Completion overlay ── */
            <div className="flex min-h-[400px] flex-col items-center justify-center gap-5 p-8 text-center">
              <div className="relative flex h-24 w-24 items-center justify-center">
                <svg className="absolute h-full w-full -rotate-90" viewBox="0 0 96 96">
                  <circle cx="48" cy="48" r="42" fill="none" stroke="rgba(5,150,105,0.15)" strokeWidth="3" />
                  <circle cx="48" cy="48" r="42" fill="none" stroke="#10b981" strokeWidth="3" strokeDasharray="264" strokeDashoffset="0" strokeLinecap="round" />
                </svg>
                <CircleCheckBig className="h-12 w-12 text-emerald-400" />
              </div>
              <h3 className="text-3xl font-black text-white">Walkthrough Complete</h3>
              <p className="max-w-md text-sm leading-7 text-slate-300">
                You&apos;ve seen every step of the Digiland escrow journey — from discovery to transfer. Ready to get started?
              </p>
              <div className="flex gap-3">
                <Button variant="outline" size="sm" onClick={restart} className="border-white/10 text-white hover:bg-white/10">
                  <ChevronLeft className="mr-1 h-4 w-4" /> Replay
                </Button>
                <Button size="sm" className="bg-emerald-600 text-white hover:bg-emerald-500">
                  Get Started
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* ── Control bar ── */}
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Transport controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={goPrev}
              disabled={activeIndex === 0 && !showCompletion}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-slate-800/50 text-slate-300 transition hover:border-white/20 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Previous scene"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={handlePlayPause}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300 transition hover:bg-emerald-500/30"
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
            </button>
            <button
              onClick={goNext}
              disabled={activeIndex >= scenes.length - 1 && !showCompletion}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-slate-800/50 text-slate-300 transition hover:border-white/20 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Next scene"
            >
              <ChevronRight className="h-4 w-4" />
            </button>

            {/* Autoplay countdown ring */}
            <div className="ml-2 flex items-center gap-2">
              <svg className="h-7 w-7 -rotate-90" viewBox="0 0 32 32" aria-hidden="true">
                <circle cx="16" cy="16" r="14" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="2" />
                <circle
                  ref={countdownRef}
                  cx="16" cy="16" r="14"
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2"
                  strokeLinecap="round"
                  style={{ strokeDasharray: 2 * Math.PI * 14, strokeDashoffset: 0 }}
                />
              </svg>
              <span className="text-[10px] font-medium text-slate-500">
                {isPlaying ? 'Auto' : 'Paused'}
              </span>
            </div>
          </div>

          {/* Speed control */}
          <button
            onClick={cycleSpeed}
            className="flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-slate-800/40 px-3 text-[11px] font-bold text-slate-300 transition hover:border-white/20 hover:text-white"
            aria-label={`Playback speed: ${speed}x. Click to change.`}
          >
            <Gauge className="h-3.5 w-3.5" />
            {speed}x
          </button>
        </div>

        {/* ── Caption bar ── */}
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-white/5 bg-slate-800/30 px-4 py-2.5">
          <div className={cn(
            'h-1.5 w-1.5 rounded-full',
            currentScene.roles === 'buyer' ? 'bg-emerald-400' :
            currentScene.roles === 'seller' ? 'bg-amber-400' : 'bg-blue-400'
          )} />
          <span className="text-xs text-slate-400">{currentScene.caption}</span>
        </div>

        {/* ── Keyboard hint ── */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-[10px] text-slate-600">
          <span><kbd className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-slate-400">Space</kbd> Play / Pause</span>
          <span><kbd className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-slate-400">←</kbd><kbd className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-slate-400 ml-1">→</kbd> Navigate</span>
        </div>
      </div>
    </section>
  );
}
