import React, { useState } from 'react';
import {
  Banknote,
  FileText,
  Gavel,
  Grid2X2,
  HandCoins,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  Menu,
  ReceiptText,
  ShieldCheck,
  Users,
  WalletCards,
  MessageSquare,
  Sparkles,
  Search,
  Bell,
  ChevronDown,
  X,
  Compass,
  Briefcase,
  Home,
  Layers,
  Scale,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { LocationPermissionModal } from '../ui/location-permission-modal.js';
import type { ActionLink, NavItem, UserSummary } from '../../types.js';
import { cn } from '../../lib/utils.js';

const iconMap: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  home: Home,
  chat: MessageSquare,
  messages: MessageSquare,
  parcels: Grid2X2,
  transactions: ReceiptText,
  legal: Gavel,
  joint: Users,
  checkout: WalletCards,
  groups: HandCoins,
  payments: Banknote,
  documents: FileText,
  security: ShieldCheck,
  features: Sparkles,
  promotions: Layers,
};

interface AppShellProps {
  title: string;
  subtitle?: string;
  user?: UserSummary | null;
  nav: NavItem[];
  children: ReactNode;
  actions?: ActionLink[];
  logoutUrl?: string;
  csrfToken?: string;
  activeNav?: string;
}

export function AppShell({
  title = 'Digiland',
  subtitle,
  user,
  nav,
  children,
  actions,
  logoutUrl,
  csrfToken,
  activeNav,
}: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const currentRole = user?.role || 'Guest';
  const displayName = user?.full_name || (user?.email ? user.email.split('@')[0] : 'User');
  const userInitial = displayName.charAt(0).toUpperCase();
  const safeTitle = (title || 'Digiland').toLowerCase();

  // Core App Rail navigation icons tailored by role
  const allRailItems = [
    {
      label: 'Dashboard',
      href: user?.role === 'Seller' ? '/seller/dashboard/' : user?.role === 'Buyer' ? '/buyer/dashboard/' : '/parcels/',
      icon: LayoutDashboard,
      active: safeTitle.includes('dashboard') || safeTitle.includes('workspace'),
    },
    {
      label: user?.role === 'Seller' ? 'My Parcels' : 'Parcels',
      href: '/parcels/',
      icon: Grid2X2,
      active: safeTitle.includes('parcel') || safeTitle.includes('marketplace'),
    },
    ...(user?.role === 'Seller'
      ? [
          {
            label: 'Promotions',
            href: '/seller/promotions/',
            icon: Layers,
            active: safeTitle.includes('promotion') || safeTitle.includes('ad') || safeTitle.includes('tier'),
          },
        ]
      : []),
    {
      label: 'Escrow',
      href: '/transactions/',
      icon: ReceiptText,
      active: safeTitle.includes('transaction') || safeTitle.includes('escrow'),
    },
    {
      label: 'Messages',
      href: '/messages/',
      icon: MessageSquare,
      active: activeNav === 'messages' || safeTitle.includes('message'),
      badge: 'DM',
    },
    {
      label: 'Legal',
      href: user?.role === 'Seller' ? '/seller/laws/' : '/escrow-acts/',
      icon: Scale,
      active: safeTitle.includes('legal') || safeTitle.includes('law') || safeTitle.includes('act'),
    },
  ];

  const railItems = allRailItems;

  return (
    <div className="flex min-h-screen bg-[#0d121f] text-slate-100 antialiased selection:bg-emerald-500 selection:text-slate-950 font-sans">
      {/* 1. Leftmost Ultra-Sleek App Rail (Desktop) */}
      <aside className="hidden w-[72px] shrink-0 flex-col items-center justify-between border-r border-white/[0.08] bg-[#080b13] py-4 md:flex z-40">
        {/* Top: Digiland Emblem */}
        <div className="flex flex-col items-center gap-6">
          <a
            href="/"
            title="Digiland Protocol"
            className="group relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-slate-950 shadow-[0_0_20px_rgba(16,185,129,0.35)] transition-all duration-200 hover:scale-105 hover:shadow-[0_0_25px_rgba(16,185,129,0.5)]"
          >
            <ShieldCheck className="h-6 w-6 text-slate-950" />
            <span className="absolute left-full ml-3 hidden whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-bold text-white shadow-xl group-hover:block z-50">
              Digiland Protocol
            </span>
          </a>

          <div className="h-[1px] w-8 bg-white/10" />

          {/* Navigation Icon Stack */}
          <nav className="flex flex-col items-center gap-2">
            {railItems.map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.label}
                  href={item.href}
                  title={item.label}
                  className={cn(
                    'group relative flex h-11 w-11 flex-col items-center justify-center rounded-2xl text-[10px] font-bold transition-all duration-150',
                    item.active
                      ? 'bg-emerald-500/20 text-emerald-300 shadow-[inset_0_0_12px_rgba(16,185,129,0.3)] ring-1 ring-emerald-500/50'
                      : 'text-slate-400 hover:bg-white/[0.06] hover:text-slate-100'
                  )}
                >
                  {item.active && (
                    <span className="absolute -left-3 h-5 w-1 rounded-r-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
                  )}
                  <Icon className="h-5 w-5 transition-transform group-hover:scale-110" />
                  <span className="text-[9px] font-medium tracking-tight mt-0.5 opacity-80">{item.label}</span>

                  {/* Tooltip */}
                  <span className="absolute left-full ml-3 hidden whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-bold text-white shadow-xl group-hover:block z-50">
                    {item.label}
                  </span>
                </a>
              );
            })}
          </nav>
        </div>

        {/* Bottom Rail: User Avatar & Logout */}
        <div className="flex flex-col items-center gap-3">
          {logoutUrl ? (
            <form method="post" action={logoutUrl}>
              <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
              <button
                type="submit"
                title="Sign out"
                className="group relative flex h-10 w-10 items-center justify-center rounded-2xl text-slate-400 transition hover:bg-rose-500/15 hover:text-rose-400"
              >
                <LogOut className="h-4 w-4" />
                <span className="absolute left-full ml-3 hidden whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-bold text-rose-400 shadow-xl group-hover:block z-50">
                  Sign out
                </span>
              </button>
            </form>
          ) : null}

          {/* User Avatar Circle */}
          <div
            title={`${displayName} (${currentRole})`}
            className="relative flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 font-black text-sm text-white shadow-md shadow-purple-500/20 transition hover:scale-105"
          >
            {userInitial}
            <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-[#080b13] bg-emerald-500 shadow-sm" />
          </div>
        </div>
      </aside>

      {/* 2. Main Workspace Layout */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Navbar Header */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-white/[0.08] bg-[#0c111e]/90 px-4 backdrop-blur-xl sm:px-6">
          {/* Mobile Menu Trigger & Title */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.06] text-slate-300 md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs font-black uppercase tracking-[0.2em] text-emerald-400">
                {(title || 'Digiland').split(' - ')[0]}
              </span>
              {subtitle && (
                <>
                  <span className="hidden text-slate-600 sm:inline">•</span>
                  <span className="hidden truncate text-xs font-medium text-slate-400 sm:inline max-w-md">
                    {subtitle}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-3">
            {actions?.map((action) => (
              <a
                key={`${action.label}-${action.href}`}
                href={action.href}
                className="hidden sm:inline-flex h-8 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/30 px-3 text-xs font-bold text-emerald-300 transition hover:bg-emerald-500/20"
              >
                {action.label}
              </a>
            ))}

            <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
              <span className="font-bold text-slate-200">{displayName}</span>
              <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[10px] font-black uppercase tracking-wider text-emerald-300">
                {currentRole}
              </span>
            </div>

            {logoutUrl && (
              <form method="post" action={logoutUrl} className="md:hidden">
                <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                <button
                  type="submit"
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-500/10 text-rose-400"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </form>
            )}
          </div>
        </header>

        {/* Mobile Flyout Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 flex flex-col bg-slate-950/95 p-6 backdrop-blur-xl md:hidden">
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-6 w-6 text-emerald-400" />
                <span className="font-black text-white text-base">Digiland Protocol</span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-full p-2 text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="mt-6 flex flex-col gap-2">
              {railItems.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    'flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-bold',
                    item.active ? 'bg-emerald-600 text-white' : 'text-slate-300 hover:bg-white/10'
                  )}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </a>
              ))}
            </nav>
          </div>
        )}

        {/* Workspace Canvas (Full Width & Clean) */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1700px] w-full mx-auto">{children}</main>
      </div>

      <LocationPermissionModal />
    </div>
  );
}


