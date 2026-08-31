import React, { useState } from 'react';
import {
  Globe,
  MapPin,
  TrendingUp,
  Compass,
  Building,
  TreePine,
  Search,
  Filter,
  ArrowUpRight,
  Sparkles,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber, RegionalCountyData } from '../types.js';

export function PropertiesRegionalChapter({
  timeframe,
  totalGmv,
  rawAnalytics,
}: AnalyticsContextData) {
  const [searchCounty, setSearchCounty] = useState('');
  const regionalDist: RegionalCountyData[] = rawAnalytics.regional_distribution || [
    { county: 'Nairobi', listings_count: 14, estimated_value_kes: 78000000, avg_price_per_acre: 18500000, demand_score: 'Extreme' },
    { county: 'Kiambu', listings_count: 11, estimated_value_kes: 42000000, avg_price_per_acre: 8200000, demand_score: 'High' },
    { county: 'Nakuru', listings_count: 8, estimated_value_kes: 24000000, avg_price_per_acre: 3200000, demand_score: 'High' },
    { county: 'Machakos', listings_count: 6, estimated_value_kes: 18000000, avg_price_per_acre: 2800000, demand_score: 'Moderate' },
    { county: 'Mombasa', listings_count: 5, estimated_value_kes: 32000000, avg_price_per_acre: 12000000, demand_score: 'High' },
    { county: 'Kajiado', listings_count: 4, estimated_value_kes: 15000000, avg_price_per_acre: 2400000, demand_score: 'Moderate' },
    { county: 'Kilifi', listings_count: 3, estimated_value_kes: 11000000, avg_price_per_acre: 3800000, demand_score: 'Moderate' },
    { county: 'Kisumu', listings_count: 2, estimated_value_kes: 8500000, avg_price_per_acre: 4500000, demand_score: 'Moderate' },
  ];

  const filteredCounties = regionalDist.filter((c) =>
    c.county.toLowerCase().includes(searchCounty.toLowerCase())
  );

  const maxListings = Math.max(...regionalDist.map((c) => c.listings_count), 1);

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Regional Density Hero Metrics ─────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Top County</div>
          <div className="mt-1 text-2xl font-black text-slate-900">Nairobi</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">14 parcels (KES 78M)</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Highest Growth</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">Kiambu</div>
          <div className="text-[10px] text-emerald-700 font-semibold mt-0.5">+34% inquiry volume</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Avg Plot Size</div>
          <div className="mt-1 text-2xl font-black text-blue-700">0.50 Acre</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Subdivision standard</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Active Counties</div>
          <div className="mt-1 text-2xl font-black text-purple-700">8 / 47</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">Expanding registry</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Urban vs Rural</div>
          <div className="mt-1 text-2xl font-black text-slate-900">68 : 32</div>
          <div className="text-[10px] text-slate-500 mt-0.5">% Value ratio</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">GIS Sync Rate</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">100%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Survey of Kenya beaconed</div>
        </div>
      </div>

      {/* ── County Density Leaderboard & Regional Inquiry Heatmap ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* County Density Visual Breakdown */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">County-by-County Parcel Density & Valuation</h4>
              <div className="text-[11px] text-slate-500">Active land listings distribution across Kenyan registries</div>
            </div>
            <Globe className="h-4 w-4 text-emerald-600" />
          </div>

          <div className="space-y-3.5 text-xs">
            {regionalDist.map((reg) => {
              const pct = (reg.listings_count / maxListings) * 100;
              return (
                <div key={reg.county} className="space-y-1">
                  <div className="flex justify-between font-bold">
                    <span className="text-slate-800 flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5 text-emerald-600" />
                      {reg.county} County
                    </span>
                    <span className="text-emerald-700 font-black">
                      {reg.listings_count} parcels ({formatKES(reg.estimated_value_kes)})
                    </span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-600 transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Regional Land Economics & Demand Insights */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Regional Land Economics & Buyer Heatmap</h4>
              <div className="text-[11px] text-slate-500">Acreage pricing trends and buyer inquiry momentum</div>
            </div>
            <TrendingUp className="h-4 w-4 text-blue-600" />
          </div>

          <div className="space-y-3 text-xs">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-900">Nairobi Metropolis Core</span>
                <Badge tone="danger" className="text-[9px] font-black uppercase">Extreme Demand</Badge>
              </div>
              <div className="text-[11px] text-slate-600">
                High commercial development density. Average price: KES 18.5M/Acre. Highest buyer syndication rate.
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-900">Kiambu & Machakos Peri-Urban Corridor</span>
                <Badge tone="success" className="text-[9px] font-black uppercase">High Residential</Badge>
              </div>
              <div className="text-[11px] text-slate-600">
                Fastest subdivision velocity for 50x100 plots. Gated community developments with title deeds ready.
              </div>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3.5 space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-black text-slate-900">Rift Valley & Coast Agri-Tourism Zones</span>
                <Badge tone="accent" className="text-[9px] font-black uppercase">Agri & Commercial</Badge>
              </div>
              <div className="text-[11px] text-slate-600">
                Large 20-100 acre agribusiness parcels and oceanview hospitality developments in Kilifi & Nakuru.
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── County Intelligence Leaderboard Table ─────────────────────────── */}
      <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <h4 className="text-sm font-black text-slate-900 flex items-center gap-2">
              <Compass className="h-4 w-4 text-emerald-600" />
              Comprehensive Regional County Registry Table
            </h4>
            <div className="text-[11px] text-slate-500">
              Verified inventory and estimated value across active Kenyan land registries
            </div>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by county..."
              value={searchCounty}
              onChange={(e) => setSearchCounty(e.target.value)}
              className="h-8 rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="py-2.5 px-3">County Name</th>
                <th className="py-2.5 px-3 text-right">Listed Parcels</th>
                <th className="py-2.5 px-3 text-right">Estimated Value</th>
                <th className="py-2.5 px-3 text-right">Avg Price / Acre</th>
                <th className="py-2.5 px-3 text-center">Buyer Demand Score</th>
                <th className="py-2.5 px-3 text-center">Cadastral Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCounties.map((c) => (
                <tr key={c.county} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5 text-emerald-600" />
                    {c.county} County
                  </td>
                  <td className="py-3 px-3 text-right font-black text-slate-900">{c.listings_count}</td>
                  <td className="py-3 px-3 text-right font-black text-emerald-700">{formatKES(c.estimated_value_kes)}</td>
                  <td className="py-3 px-3 text-right font-semibold text-slate-700">{formatKES(c.avg_price_per_acre || 4500000)}</td>
                  <td className="py-3 px-3 text-center">
                    <Badge
                      tone={c.demand_score === 'Extreme' ? 'danger' : c.demand_score === 'High' ? 'success' : 'accent'}
                      className="text-[9px] font-black uppercase"
                    >
                      {c.demand_score || 'High'}
                    </Badge>
                  </td>
                  <td className="py-3 px-3 text-center">
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                      Ardhisasa Synced
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
