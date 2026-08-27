import React, { useState } from 'react';
import {
  ArrowRight,
  Search as SearchIcon,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Building,
  FileCheck,
  MapPin,
  Compass,
  ArrowUpRight,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { getPortalUrl } from '../../lib/partition-context.js';
import posterImg from '../../assets/own_your_plot_poster.jpg';

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

  const popularLocations = ['Nairobi', 'Nakuru', 'Kiambu', 'Kajiado', 'Naivasha', 'Eldoret'];

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-slate-50 via-white to-slate-50/70 py-16 sm:py-24 lg:py-28 text-slate-900 border-b border-slate-200/80 min-h-[85vh] flex items-center">
      
      {/* Rafiki AI Ambient Soft Aura Background Glows */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[600px] w-[600px] rounded-full bg-emerald-400/10 blur-[140px]" />
      <div className="pointer-events-none absolute top-1/3 -right-40 h-[500px] w-[500px] rounded-full bg-purple-400/10 blur-[140px]" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full">
        
        {/* Top Eyebrow Tag */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-xs font-bold text-emerald-800 shadow-sm">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>{notice || "Kenya's #1 Autonomous Land Escrow Protocol"}</span>
            <span className="ml-1 inline-flex items-center gap-1 text-[10px] bg-purple-600 text-white font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
              <Sparkles className="w-3 h-3" /> AI Verified
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-semibold text-slate-600">
            <a
              href={getPortalUrl('app')}
              onClick={(e) => {
                if (onNavigatePartition) {
                  e.preventDefault();
                  onNavigatePartition('app');
                }
              }}
              className="hover:text-emerald-700 transition flex items-center gap-1"
            >
              <span>Selling Land? List as Seller</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </a>
            <span>•</span>
            <a
              href={getPortalUrl('staff')}
              onClick={(e) => {
                if (onNavigatePartition) {
                  e.preventDefault();
                  onNavigatePartition('staff');
                }
              }}
              className="hover:text-purple-700 transition flex items-center gap-1"
            >
              <span>Staff Portal (Agents & Advocates)</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        {/* Hero Split Layout: Left Content (Buyer-Focused) | Right Mockup Showcase */}
        <div className="grid items-center gap-12 lg:grid-cols-12 lg:gap-12">
          
          {/* Left Column (7 cols) - Buyer-Centric Messaging */}
          <div className="lg:col-span-7 space-y-6">
            
            <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-slate-950 leading-[1.06]">
              Find, Choose & Own <br />
              <span className="bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500 bg-clip-text text-transparent">
                Land Made Simple.
              </span>
            </h1>

            <p className="text-lg sm:text-xl text-slate-600 max-w-2xl font-medium leading-relaxed">
              Buy verified land parcels in Kenya with total confidence. Instant ArdhiSasa title checking, M-Pesa escrow protection, and legal advocate sign-off.
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

              {/* Popular Tags (Fiverr style) */}
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 pt-1">
                <span className="font-semibold text-slate-700">Popular:</span>
                {popularLocations.map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    onClick={() => {
                      setSearchQuery(loc);
                      const appUrl = getPortalUrl('app');
                      if (onNavigatePartition) {
                        onNavigatePartition('app');
                      } else {
                        window.location.href = `${appUrl}?search=${encodeURIComponent(loc)}`;
                      }
                    }}
                    className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-emerald-50 hover:text-emerald-700 border border-slate-200 font-medium transition text-slate-600"
                  >
                    {loc}
                  </button>
                ))}
              </div>
            </div>

            {/* Primary Action Buttons */}
            <div className="pt-4 flex flex-wrap items-center gap-4">
              <a
                href={getPortalUrl('app')}
                onClick={(e) => {
                  if (onNavigatePartition) {
                    e.preventDefault();
                    onNavigatePartition('app');
                  }
                }}
                className="inline-flex items-center gap-3 px-8 py-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-base shadow-xl shadow-emerald-600/30 transition-all hover:scale-[1.02]"
              >
                <Compass className="w-5 h-5" />
                <span>Explore Marketplace</span>
                <ArrowRight className="w-5 h-5" />
              </a>

              <a
                href="#features"
                className="inline-flex items-center gap-2 px-6 py-4 rounded-xl bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-bold text-sm shadow-sm transition"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>How Escrow Works</span>
              </a>
            </div>

            {/* Bullet Proofs (Rafiki AI style) */}
            <div className="pt-4 flex flex-wrap items-center gap-6 text-xs font-bold text-slate-600">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>100% Title Deed Verification</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>M-Pesa & Bank Escrow Lock</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-purple-600" />
                <span>LSK Advocate Authenticated</span>
              </div>
            </div>

          </div>

          {/* Right Column (5 cols) - Rafiki AI Dual Mockup Stack */}
          <div className="lg:col-span-5 relative">
            <div className="relative mx-auto max-w-md lg:max-w-none">
              
              {/* Soft Drop Shadow Aura */}
              <div className="absolute -inset-2 rounded-3xl bg-gradient-to-r from-emerald-400/20 via-teal-400/20 to-purple-400/20 blur-2xl opacity-70" />

              {/* Main Poster Showcase Frame */}
              <div className="relative rounded-3xl bg-white border border-slate-200 p-3 shadow-2xl shadow-slate-300/70 overflow-hidden group">
                <img
                  src={posterImg}
                  alt="Digiland - Own Your Plot Banner"
                  className="w-full h-auto rounded-2xl object-cover shadow-sm transition duration-500 group-hover:scale-[1.01]"
                />

                {/* Floating Badge 1: Verified Plot */}
                <div className="absolute top-6 left-6 bg-white/95 border border-emerald-500/30 backdrop-blur-md px-3.5 py-2 rounded-xl flex items-center gap-2.5 shadow-lg">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
                  <div>
                    <div className="text-xs font-extrabold text-slate-900">ArdhiSasa Verified</div>
                    <div className="text-[10px] text-emerald-700 font-semibold">100% Title Deeds Synced</div>
                  </div>
                </div>

                {/* Floating Badge 2: Lawyer Authenticated */}
                <div className="absolute bottom-6 right-6 bg-slate-900 border border-purple-500/40 text-white backdrop-blur-md px-4 py-2.5 rounded-xl flex items-center gap-2.5 shadow-xl">
                  <Sparkles className="w-4 h-4 text-purple-400" />
                  <div>
                    <div className="text-xs font-bold text-purple-200">Advocate Title Guarantee</div>
                    <div className="text-[10px] text-slate-400">Law Society of Kenya</div>
                  </div>
                </div>
              </div>

            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
