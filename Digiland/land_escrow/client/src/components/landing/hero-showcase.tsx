import React, { useState } from 'react';
import {
  ArrowRight,
  BarChart3,
  Gavel,
  Landmark,
  MapPin,
  Search as SearchIcon,
  Sparkles,
  ShieldCheck,
  WalletCards,
  UserCheck,
  FileCheck,
  CheckCircle2,
  Lock,
  Building,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent } from '../ui/card.js';
import { getPortalUrl } from '../../lib/partition-context.js';

type HeroStat = {
  label: string;
  value: string;
};

type HeroShowcaseProps = {
  notice?: string;
  stats?: HeroStat[];
  csrfToken?: string;
  isAuthenticated?: boolean;
  onNavigatePartition?: (partition: 'app' | 'staff' | 'admin' | 'marketing') => void;
};

export function HeroShowcase({
  notice,
  stats,
  isAuthenticated,
  onNavigatePartition,
}: HeroShowcaseProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const appUrl = getPortalUrl('app');
    if (onNavigatePartition) {
      onNavigatePartition('app');
    } else {
      window.location.href = `${appUrl}?search=${encodeURIComponent(searchQuery)}`;
    }
  };

  return (
    <div className="relative overflow-hidden bg-slate-950 py-12 sm:py-20 text-white border-b border-slate-800">
      {/* Background radial ambient light - Green & Purple glow */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-emerald-600/15 blur-[120px]" />
      <div className="pointer-events-none absolute top-1/2 -right-40 h-[500px] w-[500px] rounded-full bg-purple-600/10 blur-[140px]" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        
        {/* Top Notice Pill */}
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-semibold text-emerald-300 backdrop-blur-md">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>{notice || 'Digiland Protocol v2.0 • Kenya Land Escrow & Verification'}</span>
            <Badge tone="purple" className="ml-2 text-[10px] px-2 py-0.5 uppercase tracking-wider">AI Verified</Badge>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
              <ShieldCheck className="w-4 h-4" /> ArdhiSasa Integrated
            </span>
            <span>•</span>
            <span className="inline-flex items-center gap-1 text-purple-400 font-medium">
              <Sparkles className="w-4 h-4" /> Smart Escrow
            </span>
          </div>
        </div>

        {/* Hero Partition Layout: Left Column (Copy + CTAs) | Right Column (Poster Asset showcase) */}
        <div className="grid items-center gap-12 lg:grid-cols-12 lg:gap-8">
          
          {/* Left Column (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 rounded-lg bg-slate-900 border border-slate-800 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-emerald-400">
              <Building className="w-3.5 h-3.5 text-emerald-400" />
              Kenya's #1 Land Escrow Platform
            </div>

            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white leading-[1.08]">
              OWN YOUR <br />
              <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-200 bg-clip-text text-transparent">
                PLOT.
              </span>
            </h1>

            <p className="text-xl font-bold text-slate-200 tracking-wide">
              Safe. Simple. Secure.
            </p>

            <p className="text-base sm:text-lg text-slate-300 max-w-xl leading-relaxed">
              Verify title deeds, execute lawyer-backed escrow agreements, and complete land purchases with 100% fraud protection and M-Pesa / Bank integration.
            </p>

            {/* Quick Search */}
            <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 max-w-xl bg-slate-900/90 p-2 rounded-2xl border border-slate-800 shadow-xl">
              <div className="flex-1 flex items-center px-3 gap-2">
                <SearchIcon className="w-5 h-5 text-emerald-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search plot by County, Parcel ID, or Town..."
                  className="w-full bg-transparent text-sm text-white placeholder-slate-500 outline-none py-2.5"
                />
              </div>
              <Button type="submit" className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-6 py-2.5 rounded-xl flex items-center justify-center gap-2">
                <span>Explore</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </form>

            {/* Partition CTA Buttons */}
            <div className="pt-4 flex flex-wrap items-center gap-4">
              <a
                href={getPortalUrl('app')}
                onClick={(e) => {
                  if (onNavigatePartition) {
                    e.preventDefault();
                    onNavigatePartition('app');
                  }
                }}
                className="inline-flex items-center gap-3 px-7 py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold text-base shadow-lg shadow-emerald-950/50 transition-all hover:scale-[1.02]"
              >
                <span>Launch User App (Buyers & Sellers)</span>
                <ArrowRight className="w-5 h-5" />
              </a>

              <a
                href={getPortalUrl('staff')}
                onClick={(e) => {
                  if (onNavigatePartition) {
                    e.preventDefault();
                    onNavigatePartition('staff');
                  }
                }}
                className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-sm transition-all"
              >
                <UserCheck className="w-4 h-4 text-purple-400" />
                <span>Staff Portal (Agents & Lawyers)</span>
              </a>
            </div>

            {/* Value Indicators */}
            <div className="pt-6 grid grid-cols-3 gap-4 border-t border-slate-800/80 max-w-xl text-slate-300">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Verified Lands</div>
                  <div className="text-[10px] text-slate-400">ArdhiSasa checked</div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Lock className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Secure Escrow</div>
                  <div className="text-[10px] text-slate-400">Locked till transfer</div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  <FileCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Instant Titles</div>
                  <div className="text-[10px] text-slate-400">Digital certificate</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column (5 cols) - Poster Image Asset Showcase */}
          <div className="lg:col-span-5 relative">
            <div className="relative mx-auto max-w-md lg:max-w-none">
              
              {/* Outer Glow container */}
              <div className="absolute -inset-1.5 rounded-3xl bg-gradient-to-r from-emerald-500/40 via-teal-500/30 to-purple-600/30 blur-xl opacity-70 animate-pulse" />

              <div className="relative rounded-3xl bg-slate-900 border border-slate-700/80 p-3 shadow-2xl overflow-hidden group">
                <img
                  src="/images/own_your_plot_poster.jpg"
                  alt="Digiland - Own Your Plot Banner"
                  className="w-full h-auto rounded-2xl object-cover transform transition duration-500 group-hover:scale-[1.01]"
                />

                {/* Floating Micro-Badge Highlights */}
                <div className="absolute top-6 left-6 bg-slate-950/90 border border-emerald-500/40 backdrop-blur-md px-3.5 py-1.5 rounded-full flex items-center gap-2 shadow-lg">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-xs font-bold text-white">Verified Plot Listings</span>
                </div>

                <div className="absolute bottom-6 right-6 bg-slate-950/90 border border-purple-500/40 backdrop-blur-md px-4 py-2 rounded-xl flex items-center gap-2.5 shadow-lg">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <div>
                    <div className="text-xs font-bold text-purple-200">Legal Title Guarantee</div>
                    <div className="text-[10px] text-slate-400">Lawyer Verified</div>
                  </div>
                </div>
              </div>

            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
