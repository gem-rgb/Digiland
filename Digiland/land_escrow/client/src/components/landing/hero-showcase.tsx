import React, { useState } from 'react';
import {
  ShieldCheck,
  Search as SearchIcon,
  MapPin,
  ArrowRight,
  Sparkles,
  Lock,
  Building2,
  Users,
  Compass,
  CheckCircle2,
  Check,
} from 'lucide-react';
import { Button } from '../ui/button.js';
import { Badge } from '../ui/badge.js';
import type { UserSummary } from '../../types.js';
import { getPortalUrl, type Partition } from '../../lib/partition-context.js';
import OwnYourPlotPoster from '../../../../static/images/own_your_plot_poster.jpg';

interface HeroShowcaseProps {
  title?: string;
  subtitle?: string;
  notice?: string;
  user?: UserSummary | null;
  stats?: any[];
  csrfToken?: string;
  isAuthenticated?: boolean;
  onNavigatePartition?: (partition: Partition) => void;
}

export function HeroShowcase({
  title,
  subtitle,
  notice,
  user,
  stats,
  isAuthenticated,
  onNavigatePartition,
}: HeroShowcaseProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const appUrl = getPortalUrl('app');
    const targetUrl = `${appUrl}/parcels/${searchQuery.trim() ? `?search=${encodeURIComponent(searchQuery.trim())}` : ''}`;
    window.location.href = targetUrl;
  };

  const popularLocations = ['Nairobi', 'Nakuru', 'Kiambu', 'Kajiado', 'Naivasha', 'Eldoret'];

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 via-white to-slate-50/70 py-12 sm:py-20 lg:py-24 text-slate-900 border-b border-slate-200/80 min-h-[85vh] flex items-center">
      
      {/* Ambient Soft Aura Background Glows */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-emerald-400/10 blur-[140px]" />
      <div className="pointer-events-none absolute top-1/3 -right-40 h-[500px] w-[500px] rounded-full bg-teal-400/10 blur-[140px]" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full">
        
        {/* Top Eyebrow Notice */}
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-xs font-bold text-emerald-800 shadow-sm">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>{notice || "Kenya's #1 Land Verification & Safe Transaction Platform"}</span>
            <span className="ml-1 inline-flex items-center gap-1 text-[10px] bg-emerald-600 text-white font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              <Sparkles className="w-3 h-3" /> Multi-Layer Verified
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Multi-Layer Verification & Audit Tracking</span>
          </div>
        </div>

        {/* Hero Split Layout: Left Text & Search | Right Poster Image */}
        <div className="grid items-center gap-12 lg:grid-cols-12 lg:gap-12">
          
          {/* Left Column (7 cols) - Clean Typography & Search */}
          <div className="space-y-6 text-left lg:col-span-7">
            
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-xl bg-purple-50 border border-purple-200/80 text-purple-800 text-xs font-black tracking-wide uppercase">
              <Sparkles className="w-3.5 h-3.5 text-purple-600" />
              <span>Structured Verification Protocol</span>
            </div>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight text-slate-950 leading-[1.1]">
              Find, Choose & Own <br />
              <span className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500 bg-clip-text text-transparent">
                Land Made Simple.
              </span>
            </h1>

            <p className="text-lg sm:text-xl text-slate-600 max-w-2xl font-medium leading-relaxed">
              Buy verified land parcels across Kenya with transparency and accountability. Multi-layer title deed screening, licensed surveyor checks, advocate due diligence, and verified settlement records.
            </p>

            {/* Fiverr-Style Hero Search Bar */}
            <div className="pt-2 max-w-2xl space-y-3">
              <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 bg-white p-2.5 rounded-2xl border border-slate-300 shadow-xl shadow-slate-200/60">
                <div className="flex-1 flex items-center px-3 gap-3">
                  <SearchIcon className="w-5 h-5 text-emerald-600 shrink-0" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search land by County, Town, or Parcel Number..."
                    className="w-full bg-transparent text-sm text-slate-900 placeholder-slate-400 outline-none py-2 font-medium"
                  />
                </div>
                <Button
                  type="submit"
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-7 py-3 rounded-xl flex items-center justify-center gap-2 shadow-md shadow-emerald-950/20 text-sm"
                >
                  <span>Search Plots</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </form>

              {/* Popular Category Tags (Fiverr style) */}
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 pt-1">
                <span className="font-semibold text-slate-700">Popular Locations:</span>
                {popularLocations.map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    onClick={() => {
                      const appUrl = getPortalUrl('app');
                      window.location.href = `${appUrl}/parcels/?search=${encodeURIComponent(loc)}`;
                    }}
                    className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-emerald-50 hover:text-emerald-700 border border-slate-200 font-medium transition text-slate-600"
                  >
                    {loc}
                  </button>
                ))}
              </div>
            </div>

            {/* Primary Action Buttons (Public Only) */}
            <div className="pt-4 flex flex-wrap items-center gap-4">
              <a
                href={`${getPortalUrl('app')}/parcels/`}
                className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-base shadow-xl shadow-emerald-600/30 transition-all hover:scale-[1.02]"
              >
                <Compass className="w-5 h-5" />
                <span>Explore Marketplace</span>
                <ArrowRight className="w-5 h-5" />
              </a>

              <a
                href="/escrow-acts/"
                className="inline-flex items-center gap-2 px-6 py-4 rounded-xl bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-bold text-sm shadow-sm transition"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>How Verification Works</span>
              </a>
            </div>

            {/* Value Guarantees */}
            <div className="pt-4 flex flex-wrap items-center gap-6 text-xs font-bold text-slate-600">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Title Deed Verified</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Verified Payment Records</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Transparent Audit Trail</span>
              </div>
            </div>


          </div>

          {/* Right Column (5 cols) - Side by Side Poster Image Showcase */}
          <div className="relative lg:col-span-5 flex items-center justify-center">
            
            {/* Visual Backplate Halo */}
            <div className="absolute inset-0 bg-gradient-to-tr from-emerald-500/20 to-teal-500/10 rounded-[2.5rem] blur-2xl transform scale-95 pointer-events-none" />

            {/* Card Container holding the poster */}
            <div className="relative w-full max-w-md overflow-hidden rounded-[2rem] border border-slate-200/90 bg-white p-3 shadow-2xl shadow-slate-300/60">
              
              {/* Poster Image Container */}
              <div className="relative aspect-[3/4] w-full overflow-hidden rounded-[1.5rem] bg-slate-100">
                <img
                  src={OwnYourPlotPoster}
                  alt="Digiland - Own Your Plot"
                  className="h-full w-full object-cover object-center transition-transform duration-700 hover:scale-105"
                  loading="eager"
                  decoding="sync"
                />
              </div>

              {/* Floating Trust Pill Badge */}
              <div className="mt-3 flex items-center justify-between px-3 py-2 bg-slate-50 rounded-xl border border-slate-200">
                <div className="flex items-center gap-2">
                  <span className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-ping" />
                  <span className="text-xs font-bold text-slate-800">Ministry of Lands Sync</span>
                </div>
                <span className="text-[11px] font-black text-emerald-700 uppercase tracking-wider">
                  Audited
                </span>

              </div>

            </div>

          </div>

        </div>

      </div>
    </section>
  );
}
