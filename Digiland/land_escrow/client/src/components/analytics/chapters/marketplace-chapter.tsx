import React, { useState } from 'react';
import {
  Layers,
  MapPin,
  TrendingUp,
  Tag,
  Eye,
  MousePointerClick,
  Sparkles,
  BarChart3,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  Building,
  TreePine,
  Briefcase,
} from 'lucide-react';
import { Badge } from '../../ui/badge.js';
import { AnalyticsContextData, formatKES, formatNumber, AdCampaignData } from '../types.js';

export function MarketplaceChapter({
  timeframe,
  totalGmv,
  adRevenue,
  rawAnalytics,
  onNavigateChapter,
}: AnalyticsContextData) {
  const [filterQuery, setFilterQuery] = useState('');
  const [selectedLandUse, setSelectedLandUse] = useState<string>('ALL');

  const landUseDist = rawAnalytics.land_use_distribution || {
    Residential: 24,
    Commercial: 12,
    Agricultural: 8,
    Industrial: 3,
  };

  const totalListingsCount = Object.values(landUseDist).reduce((a: number, b: any) => a + Number(b), 0) || 47;

  const defaultCampaigns: AdCampaignData[] = [
    {
      id: '1',
      name: 'Nairobi Prime Commercial Spotlight',
      seller_name: 'Kenya Prime Lands Ltd',
      status: 'Active',
      impressions: 34200,
      clicks: 2840,
      ctr: 8.3,
      spend_kes: 45000,
      roi_pct: 215,
      tier: 'Diamond Tier',
    },
    {
      id: '2',
      name: 'Kiambu Coffee Estate Gated Parcels',
      seller_name: 'Ridgeview Holdings',
      status: 'Active',
      impressions: 18900,
      clicks: 1420,
      ctr: 7.5,
      spend_kes: 25000,
      roi_pct: 180,
      tier: 'Gold Tier',
    },
    {
      id: '3',
      name: 'Nakuru Agri-Tech 50-Acre Blocks',
      seller_name: 'Rift Valley Agribusiness',
      status: 'Active',
      impressions: 14500,
      clicks: 980,
      ctr: 6.7,
      spend_kes: 15000,
      roi_pct: 140,
      tier: 'Silver Tier',
    },
    {
      id: '4',
      name: 'Mombasa Oceanview Eco-Villas',
      seller_name: 'Coastline Properties',
      status: 'Paused',
      impressions: 9200,
      clicks: 540,
      ctr: 5.8,
      spend_kes: 12000,
      roi_pct: 95,
      tier: 'Bronze Tier',
    },
  ];

  const filteredCampaigns = defaultCampaigns.filter((c) =>
    c.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
    (c.seller_name && c.seller_name.toLowerCase().includes(filterQuery.toLowerCase()))
  );

  return (
    <div className="space-y-6 animate-fade-in text-left">
      {/* ── Marketplace Metrics Strip ────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Total Listed Parcels</div>
          <div className="mt-1 text-2xl font-black text-slate-900">{totalListingsCount}</div>
          <div className="text-[10px] text-emerald-700 font-bold mt-0.5">100% Pre-Screened</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Avg Price / Acre</div>
          <div className="mt-1 text-2xl font-black text-blue-700">KES 4.2M</div>
          <div className="text-[10px] text-slate-500 mt-0.5">National Median</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Promoted Listings</div>
          <div className="mt-1 text-2xl font-black text-purple-700">12 Ads</div>
          <div className="text-[10px] text-purple-700 font-semibold mt-0.5">{formatKES(adRevenue)} ad spend</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Avg Days on Market</div>
          <div className="mt-1 text-2xl font-black text-slate-900">28 Days</div>
          <div className="text-[10px] text-emerald-700 font-semibold mt-0.5">-14% vs traditional</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Ardhisasa Synced</div>
          <div className="mt-1 text-2xl font-black text-emerald-700">96.8%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Ministry of Lands API</div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Inquiry Conversion</div>
          <div className="mt-1 text-2xl font-black text-amber-700">31.4%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">View-to-Contract</div>
        </div>
      </div>

      {/* ── Land Use Type Breakdown & Pricing Tiers ──────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Land Use Classification */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Land Use Classification Distribution</h4>
              <div className="text-[11px] text-slate-500">Zoning allocations across listed portfolio</div>
            </div>
            <Badge tone="outline" className="text-[10px] font-bold">
              {totalListingsCount} Parcels
            </Badge>
          </div>

          <div className="space-y-3 text-xs">
            {Object.entries(landUseDist).map(([type, count]: [string, any], idx) => {
              const pct = totalListingsCount ? ((Number(count) / totalListingsCount) * 100) : 0;
              const color = ['bg-emerald-600', 'bg-blue-600', 'bg-purple-600', 'bg-amber-600'][idx % 4];
              const textTone = ['text-emerald-700', 'text-blue-700', 'text-purple-700', 'text-amber-700'][idx % 4];
              return (
                <div key={type} className="space-y-1">
                  <div className="flex justify-between font-bold">
                    <span className="text-slate-800 flex items-center gap-1.5">
                      {type === 'Residential' && <Building className="h-3.5 w-3.5 text-emerald-600" />}
                      {type === 'Commercial' && <Briefcase className="h-3.5 w-3.5 text-blue-600" />}
                      {type === 'Agricultural' && <TreePine className="h-3.5 w-3.5 text-purple-600" />}
                      {type} Land
                    </span>
                    <span className={textTone}>
                      {count} parcels ({pct.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${color} transition-all duration-500`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Pricing Tiers & Valuation Brackets */}
        <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h4 className="text-sm font-black text-slate-900">Parcel Price & Acreage Valuation Tiers</h4>
              <div className="text-[11px] text-slate-500">Market supply segment distribution</div>
            </div>
            <Tag className="h-4 w-4 text-emerald-600" />
          </div>

          <div className="space-y-2.5 text-xs">
            {[
              { bracket: 'Entry Micro-Plots (< KES 1M)', share: '22%', count: '10 parcels', speed: 'High (14 days)' },
              { bracket: 'Mid-Tier Suburban (KES 1M - 5M)', share: '48%', count: '23 parcels', speed: 'Very High (21 days)' },
              { bracket: 'Prime Commercial / Acreage (KES 5M - 20M)', share: '24%', count: '11 parcels', speed: 'Moderate (45 days)' },
              { bracket: 'Institutional Mega-Blocks (> KES 20M)', share: '6%', count: '3 parcels', speed: 'Syndicate (60 days)' },
            ].map((tier, idx) => (
              <div key={idx} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-900">{tier.bracket}</div>
                  <div className="text-[10px] text-slate-500">{tier.count} • Sales velocity: {tier.speed}</div>
                </div>
                <Badge tone="accent" className="font-bold text-[10px]">
                  {tier.share}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Featured & Sponsored Ad Campaign Intelligence ────────────────── */}
      <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <h4 className="text-sm font-black text-slate-900 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-500" />
              Sponsored Ads & Promotion Tier Intelligence
            </h4>
            <div className="text-[11px] text-slate-500">
              Active seller spotlight campaigns, impression delivery, and ROI conversions
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search campaigns..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                className="h-8 rounded-xl border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="py-2.5 px-3">Campaign & Seller</th>
                <th className="py-2.5 px-3">Tier</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 text-right">Impressions</th>
                <th className="py-2.5 px-3 text-right">Clicks</th>
                <th className="py-2.5 px-3 text-right">CTR</th>
                <th className="py-2.5 px-3 text-right">Spend</th>
                <th className="py-2.5 px-3 text-right">ROI Multiplier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredCampaigns.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50/80 transition">
                  <td className="py-3 px-3">
                    <div className="font-bold text-slate-900">{c.name}</div>
                    <div className="text-[10px] text-slate-500">{c.seller_name}</div>
                  </td>
                  <td className="py-3 px-3">
                    <Badge tone="purple" className="text-[9px] font-black">
                      {c.tier}
                    </Badge>
                  </td>
                  <td className="py-3 px-3">
                    <Badge tone={c.status === 'Active' ? 'success' : 'muted'} className="text-[9px] font-black">
                      {c.status}
                    </Badge>
                  </td>
                  <td className="py-3 px-3 text-right font-medium text-slate-700">{formatNumber(c.impressions)}</td>
                  <td className="py-3 px-3 text-right font-medium text-slate-700">{formatNumber(c.clicks)}</td>
                  <td className="py-3 px-3 text-right font-bold text-emerald-700">{c.ctr}%</td>
                  <td className="py-3 px-3 text-right font-bold text-slate-900">{formatKES(c.spend_kes)}</td>
                  <td className="py-3 px-3 text-right font-black text-emerald-700">+{c.roi_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
