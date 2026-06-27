'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  MapPin,
  Building2,
  Sprout,
  Gauge,
  TrendingUp,
  Droplets,
  ShieldCheck,
  LoaderCircle,
  AlertTriangle,
  ChevronDown,
  CheckCircle2,
  Landmark,
  type LucideIcon,
} from 'lucide-react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent } from '../ui/card.js';
import { Input } from '../ui/input.js';

// ── Types ──────────────────────────────────────────────────────────────────────
type LandUseValue = 'Residential' | 'Commercial' | 'Agricultural';

interface PredictionResult {
  price_per_acre: number;
  total_value: number;
  confidence_low: number;
  confidence_high: number;
  county: string;
  constituency: string;
  town: string;
  land_use: string;
  size_acres: number;
  model_accuracy: string;
  confidence_label: string;
  market_position: string;
  comparisons: Array<{
    county: string;
    constituency: string;
    town?: string;
    land_use: string;
    size_acres: number;
    price_per_acre: number;
  }>;
  prediction_id: string;
  model_version: string;
}

interface PriceEstimatorSectionProps {
  csrfToken?: string;
  isAuthenticated?: boolean;
}

// ── County data (will be fetched from API, but have fallback) ──────────────────
const COUNTIES = [
  'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo Marakwet', 'Embu',
  'Garissa', 'Homa Bay', 'Isiolo', 'Kajiado', 'Kakamega', 'Kericho',
  'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii', 'Kisumu', 'Kitui',
  'Kwale', 'Laikipia', 'Lamu', 'Machakos', 'Makueni', 'Mandera',
  'Marsabit', 'Meru', 'Migori', 'Mombasa', 'Murang_a', 'Nairobi',
  'Nakuru', 'Nandi', 'Narok', 'Nyandarua', 'Nyamira', 'Nyeri',
  'Samburu', 'Siaya', 'Taita Taveta', 'Tana River', 'Tharaka Nithi',
  'Trans Nzoia', 'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir',
  'West Pokot'
];

const LAND_USES: Array<{ value: LandUseValue; label: string; icon: LucideIcon }> = [
  { value: 'Residential', label: 'Residential', icon: Landmark },
  { value: 'Commercial', label: 'Commercial', icon: Building2 },
  { value: 'Agricultural', label: 'Agricultural', icon: Sprout },
];

const PLOT_GRADES = [
  { value: '', label: 'Auto-detect' },
  { value: 'A', label: 'A — Premium' },
  { value: 'B', label: 'B — Good' },
  { value: 'C', label: 'C — Average' },
  { value: 'D', label: 'D — Developing' },
];

// ── Helper ──────────────────────────────────────────────────────────────────────
function formatKES(value: number): string {
  if (value >= 1_000_000_000) return `KES ${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `KES ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `KES ${(value / 1_000).toFixed(0)}K`;
  return `KES ${value.toLocaleString()}`;
}

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? match[2] : '';
}

// ── Component ───────────────────────────────────────────────────────────────────
export function PriceEstimatorSection({ csrfToken, isAuthenticated }: PriceEstimatorSectionProps) {
  // Form state
  const [county, setCounty] = useState('');
  const [constituency, setConstituency] = useState('');
  const [town, setTown] = useState('');
  const [landUse, setLandUse] = useState<LandUseValue>('Residential');
  const [sizeAcres, setSizeAcres] = useState('0.50');
  const [roadAccess, setRoadAccess] = useState(true);
  const [waterAccess, setWaterAccess] = useState(true);
  const [electricityAccess, setElectricityAccess] = useState(true);
  const [plotGrade, setPlotGrade] = useState('');
  const [proximityTarmac, setProximityTarmac] = useState('');
  const [proximitySchool, setProximitySchool] = useState('');
  const [proximityHospital, setProximityHospital] = useState('');

  // Cascading dropdowns
  const [constituencies, setConstitituencies] = useState<string[]>([]);
  const [towns, setTowns] = useState<string[]>([]);
  const [loadingConstituencies, setLoadingConstituencies] = useState(false);
  const [loadingTowns, setLoadingTowns] = useState(false);

  // Result state
  const [isLoading, setIsLoading] = useState(false);
  const [prediction, setPrediction] = useState<PredictionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [animatedPrice, setAnimatedPrice] = useState(0);

  // Refs
  const resultRef = useRef<HTMLDivElement>(null);

  // ── Fetch constituencies when county changes ──
  useEffect(() => {
    if (!county) {
      setConstitituencies([]);
      setConstituency('');
      setTowns([]);
      setTown('');
      return;
    }
    setLoadingConstituencies(true);
    fetch(`/api/v1/price-prediction/?action=constituencies&county=${encodeURIComponent(county)}`)
      .then(res => res.json())
      .then(data => {
        setConstitituencies(data.constituencies || []);
        setConstituency('');
        setTowns([]);
        setTown('');
      })
      .catch(() => setConstitituencies([]))
      .finally(() => setLoadingConstituencies(false));
  }, [county]);

  // ── Fetch towns when constituency changes ──
  useEffect(() => {
    if (!county || !constituency) {
      setTowns([]);
      setTown('');
      return;
    }
    setLoadingTowns(true);
    fetch(`/api/v1/price-prediction/?action=towns&county=${encodeURIComponent(county)}&constituency=${encodeURIComponent(constituency)}`)
      .then(res => res.json())
      .then(data => {
        setTowns(data.towns || []);
        setTown('');
      })
      .catch(() => setTowns([]))
      .finally(() => setLoadingTowns(false));
  }, [county, constituency]);

  // ── Animated number counter ──
  useEffect(() => {
    if (!prediction?.price_per_acre) {
      setAnimatedPrice(0);
      return;
    }
    const target = prediction.price_per_acre;
    const duration = 1200;
    const start = performance.now();
    let raf: number;

    function step(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedPrice(Math.round(target * eased));
      if (progress < 1) {
        raf = requestAnimationFrame(step);
      }
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [prediction?.price_per_acre]);

  // ── Submit handler ──
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!county || !landUse) {
      setError('Please select a county and land use type.');
      return;
    }

    const parsedSize = parseFloat(sizeAcres);
    if (!parsedSize || parsedSize <= 0) {
      setError('Enter a valid land size in acres.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setPrediction(null);

    try {
      const body: Record<string, unknown> = {
        county,
        constituency: constituency || county,
        town: town || constituency || county,
        land_use: landUse,
        size_acres: parsedSize,
        has_road_access: roadAccess,
        has_water: waterAccess,
        has_electricity: electricityAccess,
      };

      if (plotGrade) body.plot_grade = plotGrade;
      if (proximityTarmac) body.proximity_to_tarmac_km = parseFloat(proximityTarmac);
      if (proximitySchool) body.proximity_to_school_km = parseFloat(proximitySchool);
      if (proximityHospital) body.proximity_to_hospital_km = parseFloat(proximityHospital);

      const response = await fetch('/api/v1/price-prediction/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || getCookie('csrftoken'),
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        if (response.status === 400) {
          const data = await response.json().catch(() => null);
          const msg = data?.errors
            ? Object.values(data.errors).flat().join(' ')
            : data?.error || 'Invalid request. Check your inputs.';
          setError(msg);
        } else if (response.status === 422) {
          setError('This location is not yet covered. Try a different county.');
        } else if (response.status === 503) {
          setError('The valuation engine is currently unavailable. Try again shortly.');
        } else if (response.status === 429) {
          setError('Too many requests. Wait a moment before trying again.');
        } else {
          setError('Unable to get a valuation right now. Try again later.');
        }
        return;
      }

      const data = await response.json();
      if (data.error) {
        setError(data.error);
        return;
      }

      setPrediction(data);

      // Scroll to results
      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Network error. Try again.');
    } finally {
      setIsLoading(false);
    }
  }, [county, constituency, town, landUse, sizeAcres, roadAccess, waterAccess, electricityAccess, plotGrade, proximityTarmac, proximitySchool, proximityHospital, csrfToken]);

  // ── Confidence gauge percentage ──
  const confidencePct = prediction
    ? Math.min(100, Math.max(0, ((prediction.price_per_acre - prediction.confidence_low) / (prediction.confidence_high - prediction.confidence_low || 1)) * 100))
    : 0;

  // ── Market comparison bar data ──
  const maxComparison = prediction?.comparisons?.length
    ? Math.max(...prediction.comparisons.map(c => c.price_per_acre), prediction.price_per_acre)
    : 0;

  return (
    <section className="relative overflow-hidden py-16 sm:py-20" id="price-estimator">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-950 via-slate-900 to-emerald-950" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(16,185,129,0.15),transparent_50%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(20,184,166,0.1),transparent_50%)]" />

      <div className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6">
        {/* Section heading */}
        <div className="mb-10 text-center">
          <Badge className="mb-4 border-amber-400/30 bg-amber-400/10 text-amber-300 hover:bg-amber-400/20">
            <Gauge className="mr-1.5 h-3.5 w-3.5" />
            AI-Powered Valuation
          </Badge>
          <h2 className="text-3xl font-black tracking-tight text-white sm:text-4xl">
            Estimate Land Value <span className="text-amber-400">Instantly</span>
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-base leading-7 text-slate-300">
            Get an instant, AI-powered land value estimate based on location, parcel characteristics, and current market data.
            See confidence ranges and comparable sales nearby.
          </p>
        </div>

        {/* Glassmorphism card */}
        <Card className="border-white/10 bg-white/5 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.5)] backdrop-blur-2xl">
          <CardContent className="p-6 sm:p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Row 1: County, Constituency, Town */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">County *</label>
                  <div className="relative">
                    <select
                      value={county}
                      onChange={e => setCounty(e.target.value)}
                      className="h-10 w-full appearance-none rounded-lg border border-white/10 bg-white/5 px-3 pr-8 text-sm text-white focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                    >
                      <option value="" className="bg-slate-900">Select County</option>
                      {COUNTIES.map(c => (
                        <option key={c} value={c} className="bg-slate-900">{c}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">Constituency</label>
                  <div className="relative">
                    <select
                      value={constituency}
                      onChange={e => setConstituency(e.target.value)}
                      disabled={!county || loadingConstituencies}
                      className="h-10 w-full appearance-none rounded-lg border border-white/10 bg-white/5 px-3 pr-8 text-sm text-white focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-50"
                    >
                      <option value="" className="bg-slate-900">
                        {loadingConstituencies ? 'Loading...' : county ? 'Select Constituency' : 'Select County first'}
                      </option>
                      {constituencies.map(c => (
                        <option key={c} value={c} className="bg-slate-900">{c}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">Town / Neighborhood</label>
                  <div className="relative">
                    {towns.length > 0 ? (
                      <>
                        <select
                          value={town}
                          onChange={e => setTown(e.target.value)}
                          disabled={loadingTowns}
                          className="h-10 w-full appearance-none rounded-lg border border-white/10 bg-white/5 px-3 pr-8 text-sm text-white focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400 disabled:opacity-50"
                        >
                          <option value="" className="bg-slate-900">
                            {loadingTowns ? 'Loading...' : 'Select Town'}
                          </option>
                          {towns.map(t => (
                            <option key={t} value={t} className="bg-slate-900">{t}</option>
                          ))}
                        </select>
                        <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-400" />
                      </>
                    ) : (
                      <Input
                        value={town}
                        onChange={e => setTown(e.target.value)}
                        placeholder="e.g. Karen, Kitengela"
                        className="border-white/10 bg-white/5 text-white placeholder:text-slate-500 focus:border-emerald-400"
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Row 2: Land Use, Size, Plot Grade */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">Land Use *</label>
                  <div className="grid grid-cols-3 gap-2">
                    {LAND_USES.map(lu => (
                      <button
                        key={lu.value}
                        type="button"
                        onClick={() => setLandUse(lu.value)}
                        className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-xs font-medium transition-all ${
                          landUse === lu.value
                            ? 'border-emerald-400 bg-emerald-400/15 text-emerald-300'
                            : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-slate-200'
                        }`}
                      >
                        <lu.icon className="h-4 w-4" />
                        {lu.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">Size (acres) *</label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={sizeAcres}
                    onChange={e => setSizeAcres(e.target.value)}
                    className="border-white/10 bg-white/5 text-white placeholder:text-slate-500 focus:border-emerald-400"
                    placeholder="1.00"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-200">Plot Grade</label>
                  <div className="relative">
                    <select
                      value={plotGrade}
                      onChange={e => setPlotGrade(e.target.value)}
                      className="h-10 w-full appearance-none rounded-lg border border-white/10 bg-white/5 px-3 pr-8 text-sm text-white focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                    >
                      {PLOT_GRADES.map(pg => (
                        <option key={pg.value} value={pg.value} className="bg-slate-900">{pg.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-400" />
                  </div>
                </div>
              </div>

              {/* Row 3: Infrastructure toggles */}
              <div className="flex flex-wrap gap-3">
                {[
                  { label: 'Road Access', value: roadAccess, setter: setRoadAccess, icon: '🛣️' },
                  { label: 'Water', value: waterAccess, setter: setWaterAccess, icon: '💧' },
                  { label: 'Electricity', value: electricityAccess, setter: setElectricityAccess, icon: '⚡' },
                ].map(item => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => item.setter(!item.value)}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all ${
                      item.value
                        ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300'
                        : 'border-white/10 bg-white/5 text-slate-500'
                    }`}
                  >
                    <span>{item.icon}</span>
                    {item.label}
                    {item.value && <CheckCircle2 className="h-3.5 w-3.5" />}
                  </button>
                ))}
              </div>

              {/* Row 4: Optional proximity inputs */}
              <details className="group">
                <summary className="cursor-pointer text-sm font-medium text-slate-400 hover:text-slate-200">
                  Advanced: Proximity Details (optional)
                </summary>
                <div className="mt-3 grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400">Distance to tarmac (km)</label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="50"
                      value={proximityTarmac}
                      onChange={e => setProximityTarmac(e.target.value)}
                      placeholder="Auto-estimate"
                      className="border-white/10 bg-white/5 text-white placeholder:text-slate-600 focus:border-emerald-400"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400">Distance to school (km)</label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="50"
                      value={proximitySchool}
                      onChange={e => setProximitySchool(e.target.value)}
                      placeholder="Auto-estimate"
                      className="border-white/10 bg-white/5 text-white placeholder:text-slate-600 focus:border-emerald-400"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-400">Distance to hospital (km)</label>
                    <Input
                      type="number"
                      step="0.5"
                      min="0"
                      max="50"
                      value={proximityHospital}
                      onChange={e => setProximityHospital(e.target.value)}
                      placeholder="Auto-estimate"
                      className="border-white/10 bg-white/5 text-white placeholder:text-slate-600 focus:border-emerald-400"
                    />
                  </div>
                </div>
              </details>

              {/* Submit button */}
              <Button
                type="submit"
                disabled={isLoading || !county}
                className="w-full bg-gradient-to-r from-amber-500 to-amber-600 py-3 text-base font-bold text-white shadow-lg shadow-amber-500/20 hover:from-amber-600 hover:to-amber-700 disabled:opacity-50"
              >
                {isLoading ? (
                  <>
                    <LoaderCircle className="mr-2 h-5 w-5 animate-spin" />
                    Running AI Valuation...
                  </>
                ) : (
                  <>
                    <TrendingUp className="mr-2 h-5 w-5" />
                    Get Instant Valuation
                  </>
                )}
              </Button>
            </form>

            {/* Error */}
            {error && (
              <div className="mt-6 flex items-start gap-3 rounded-xl border border-rose-400/30 bg-rose-400/5 p-4 text-rose-300">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
            )}

            {/* Results */}
            {prediction && (
              <div ref={resultRef} className="mt-8 space-y-6">
                {/* Price display */}
                <div className="rounded-2xl border border-amber-400/20 bg-gradient-to-br from-amber-400/5 to-amber-500/10 p-6 text-center">
                  <div className="text-xs font-bold uppercase tracking-[0.24em] text-amber-400">
                    {prediction.confidence_label}
                  </div>
                  <div className="mt-2 text-4xl font-black tracking-tight text-amber-400 sm:text-5xl">
                    {formatKES(animatedPrice)}
                  </div>
                  <div className="mt-1 text-sm text-amber-300/70">per acre</div>
                  <div className="mt-3 flex items-center justify-center gap-2 text-xs text-slate-400">
                    <MapPin className="h-3.5 w-3.5" />
                    {prediction.town && prediction.town !== prediction.county
                      ? `${prediction.town}, ${prediction.county}`
                      : prediction.county}
                    <span className="text-slate-600">·</span>
                    {prediction.land_use}
                    <span className="text-slate-600">·</span>
                    {prediction.size_acres} acres
                  </div>

                  {/* Confidence gauge */}
                  <div className="mx-auto mt-5 max-w-md">
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span>95% Confidence Range</span>
                      <span className="text-amber-400/70">
                        {formatKES(prediction.confidence_low)} – {formatKES(prediction.confidence_high)}
                      </span>
                    </div>
                    <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-600 via-amber-400 to-amber-600 transition-all duration-700"
                        style={{ width: `${Math.max(20, Math.min(100, (confidencePct)))}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Stats grid */}
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Total Value</div>
                    <div className="mt-1 text-xl font-black text-white">{formatKES(prediction.total_value)}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Market Position</div>
                    <div className="mt-1 text-xl font-black text-emerald-400">{prediction.market_position}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Model Accuracy</div>
                    <div className="mt-1 text-xl font-black text-white">{prediction.model_accuracy}</div>
                  </div>
                </div>

                {/* Market comparisons */}
                {prediction.comparisons?.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-sm font-bold text-slate-300">Market Comparisons</h3>
                    {prediction.comparisons.slice(0, 4).map((comp, i) => {
                      const barWidth = maxComparison > 0 ? (comp.price_per_acre / maxComparison) * 100 : 0;
                      return (
                        <div key={i} className="rounded-xl border border-white/10 bg-white/5 p-3">
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                              <MapPin className="h-3.5 w-3.5 text-emerald-400" />
                              <span className="font-medium text-slate-200">
                                {comp.town || comp.constituency}, {comp.county}
                              </span>
                              <span className="text-xs text-slate-500">
                                {comp.land_use} · {comp.size_acres} ac
                              </span>
                            </div>
                            <span className="font-bold text-amber-400">{formatKES(comp.price_per_acre)}/ac</span>
                          </div>
                          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                            <div
                              className="h-full rounded-full bg-emerald-500/60"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Prediction metadata */}
                <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Prediction #{prediction.prediction_id?.slice(0, 8)}...
                  </span>
                  <span>v{prediction.model_version}</span>
                  <span className="inline-flex items-center gap-1">
                    <Droplets className="h-3.5 w-3.5" />
                    {prediction.confidence_label}
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
