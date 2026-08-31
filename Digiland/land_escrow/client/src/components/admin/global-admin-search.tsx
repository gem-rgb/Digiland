import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Users,
  Briefcase,
  Grid2X2,
  ReceiptText,
  ShieldCheck,
  X,
  ArrowRight,
  Sparkles,
  Command,
  Building2,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import { apiClient } from '../../lib/api-client.js';

interface GlobalAdminSearchProps {
  onSelectResult?: (category: string, item: any) => void;
}

export function GlobalAdminSearch({ onSelectResult }: GlobalAdminSearchProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<'all' | 'users' | 'staff' | 'parcels' | 'transactions'>('all');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<{
    users: any[];
    staff: any[];
    parcels: any[];
    transactions: any[];
    total_matches: number;
  }>({
    users: [],
    staff: [],
    parcels: [],
    transactions: [],
    total_matches: 0,
  });

  const inputRef = useRef<HTMLInputElement>(null);

  // Global Keyboard Shortcut: Ctrl+K / Cmd+K / Slash to open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Focus search input when modal opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Debounced search query
  useEffect(() => {
    if (!isOpen || !query.trim()) {
      setResults({ users: [], staff: [], parcels: [], transactions: [], total_matches: 0 });
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const resp = await apiClient.get<any>(
          `/api/v1/admin/search/?q=${encodeURIComponent(query.trim())}&category=${category}&limit=8`
        );
        if (resp.ok && resp.data) {
          setResults({
            users: resp.data.users || [],
            staff: resp.data.staff || [],
            parcels: resp.data.parcels || [],
            transactions: resp.data.transactions || [],
            total_matches: resp.data.total_matches || 0,
          });
        }
      } catch (err) {
        console.error('Failed to execute admin search:', err);
      } finally {
        setIsLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query, category, isOpen]);

  const handleSelectItem = (cat: string, item: any) => {
    setIsOpen(false);
    if (onSelectResult) {
      onSelectResult(cat, item);
    }
    // Dispatch global event for listeners across the app
    window.dispatchEvent(
      new CustomEvent('digiland:open-admin-item', {
        detail: { category: cat, item },
      })
    );
  };

  return (
    <>
      {/* ── Trigger Search Bar in Header ─────────────────────────────────── */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="hidden md:flex items-center gap-2 h-9 w-64 lg:w-80 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-400 hover:border-emerald-500 hover:bg-white transition shadow-2xs"
      >
        <Search className="h-3.5 w-3.5 text-slate-400" />
        <span className="truncate">Search users, staff, parcels, tx...</span>
        <kbd className="ml-auto inline-flex items-center gap-0.5 rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-500 shadow-2xs">
          <Command className="h-2.5 w-2.5" /> K
        </kbd>
      </button>

      {/* ── Floating Spotlight Modal Dialog ─────────────────────────────── */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4 bg-slate-950/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div
            className="w-full max-w-2xl rounded-3xl border border-slate-200 bg-white shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-150 text-left"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Input Bar */}
            <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3.5 bg-white">
              <Search className={`h-5 w-5 ${isLoading ? 'animate-pulse text-emerald-600' : 'text-slate-400'}`} />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name, email, phone, ID number, title, or tx..."
                className="w-full text-sm font-medium text-slate-900 placeholder:text-slate-400 outline-none bg-transparent"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="rounded-lg p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="rounded-lg border border-slate-200 px-2 py-1 text-[11px] font-bold text-slate-500 hover:bg-slate-100"
              >
                ESC
              </button>
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 border-b border-slate-100 px-4 py-2 bg-slate-50/70 overflow-x-auto text-xs">
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 mr-1">Category:</span>
              {[
                { id: 'all', label: 'All Database' },
                { id: 'staff', label: 'Staff & Lawyers' },
                { id: 'users', label: 'Buyers & Sellers' },
                { id: 'parcels', label: 'Land Parcels' },
                { id: 'transactions', label: 'Escrow Tx' },
              ].map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setCategory(c.id as any)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                    category === c.id
                      ? 'bg-emerald-600 text-white shadow-2xs font-black'
                      : 'text-slate-600 hover:bg-slate-200/70'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>

            {/* Results Container */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {!query.trim() ? (
                <div className="py-12 text-center text-slate-400 space-y-2">
                  <Search className="mx-auto h-8 w-8 text-slate-300" />
                  <div className="text-xs font-bold text-slate-700">Type to search database records</div>
                  <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
                    Lookup users by email, national ID, KRA PIN, staff licenses (LSK/ISLK/EARB), or parcel title numbers.
                  </p>
                </div>
              ) : results.total_matches === 0 && !isLoading ? (
                <div className="py-12 text-center text-slate-400 space-y-1">
                  <AlertTriangle className="mx-auto h-8 w-8 text-amber-400 mb-2" />
                  <div className="text-xs font-bold text-slate-800">No database matches found for "{query}"</div>
                  <p className="text-[11px] text-slate-400">Try adjusting your spelling or selecting "All Database".</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* 1. Staff & Professionals */}
                  {results.staff.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-black uppercase text-slate-500 px-1">
                        <span className="flex items-center gap-1.5">
                          <Briefcase className="h-3.5 w-3.5 text-purple-600" /> Staff & Professionals
                        </span>
                        <span>{results.staff.length} matches</span>
                      </div>
                      <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white overflow-hidden">
                        {results.staff.map((s) => (
                          <div
                            key={s.id}
                            onClick={() => handleSelectItem('staff', s)}
                            className="flex items-center justify-between p-3 hover:bg-slate-50 cursor-pointer transition"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900 text-xs">{s.name}</span>
                                <span className={`rounded-md px-1.5 py-0.5 text-[9px] font-black uppercase ${
                                  s.role === 'Lawyer'
                                    ? 'bg-blue-100 text-blue-800'
                                    : s.role === 'Surveyor'
                                    ? 'bg-teal-100 text-teal-800'
                                    : 'bg-emerald-100 text-emerald-800'
                                }`}>
                                  {s.role}
                                </span>
                                {s.is_verified && (
                                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" title="Verified" />
                                )}
                              </div>
                              <div className="text-[11px] text-slate-500">{s.email} • {s.county || 'National'}</div>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-300" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 2. People (Buyers & Sellers) */}
                  {results.users.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-black uppercase text-slate-500 px-1">
                        <span className="flex items-center gap-1.5">
                          <Users className="h-3.5 w-3.5 text-blue-600" /> Buyers & Landowners
                        </span>
                        <span>{results.users.length} matches</span>
                      </div>
                      <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white overflow-hidden">
                        {results.users.map((u) => (
                          <div
                            key={u.id}
                            onClick={() => handleSelectItem('user', u)}
                            className="flex items-center justify-between p-3 hover:bg-slate-50 cursor-pointer transition"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900 text-xs">{u.name}</span>
                                <span className="rounded-md bg-slate-100 text-slate-700 px-1.5 py-0.5 text-[9px] font-bold">
                                  {u.role}
                                </span>
                              </div>
                              <div className="text-[11px] text-slate-500">{u.email} • {u.phone}</div>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-300" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 3. Land Parcels */}
                  {results.parcels.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-black uppercase text-slate-500 px-1">
                        <span className="flex items-center gap-1.5">
                          <Grid2X2 className="h-3.5 w-3.5 text-emerald-600" /> Land Parcels
                        </span>
                        <span>{results.parcels.length} matches</span>
                      </div>
                      <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white overflow-hidden">
                        {results.parcels.map((p) => (
                          <div
                            key={p.id}
                            onClick={() => handleSelectItem('parcel', p)}
                            className="flex items-center justify-between p-3 hover:bg-slate-50 cursor-pointer transition"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-emerald-800 text-xs">{p.title_number}</span>
                                <span className="text-[10px] font-bold text-slate-500">{p.county}</span>
                              </div>
                              <div className="text-[11px] text-slate-500">
                                {p.size_acres} Acres • KES {Number(p.price_kes).toLocaleString()} • Owner: {p.owner_name}
                              </div>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-300" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 4. Escrow Transactions */}
                  {results.transactions.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-black uppercase text-slate-500 px-1">
                        <span className="flex items-center gap-1.5">
                          <ReceiptText className="h-3.5 w-3.5 text-amber-600" /> Escrow Transactions
                        </span>
                        <span>{results.transactions.length} matches</span>
                      </div>
                      <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white overflow-hidden">
                        {results.transactions.map((tx) => (
                          <div
                            key={tx.id}
                            onClick={() => handleSelectItem('transaction', tx)}
                            className="flex items-center justify-between p-3 hover:bg-slate-50 cursor-pointer transition"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900 text-xs">Parcel {tx.parcel_title}</span>
                                <span className="rounded-md bg-amber-50 text-amber-800 border border-amber-200 px-1.5 py-0.5 text-[9px] font-bold">
                                  {tx.status}
                                </span>
                              </div>
                              <div className="text-[11px] text-slate-500">
                                Buyer: {tx.buyer_name} • KES {Number(tx.agreed_price).toLocaleString()}
                              </div>
                            </div>
                            <ArrowRight className="h-4 w-4 text-slate-300" />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-slate-100 bg-slate-50 px-4 py-2.5 text-[11px] text-slate-400 flex items-center justify-between">
              <span>Database query execution • PostgreSQL live index</span>
              <span>Press <kbd className="font-mono bg-white px-1 border rounded">ESC</kbd> to close</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
