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
      href: (user?.role === 'Admin' || user?.role === 'Agent' || user?.role === 'Lawyer' || user?.role === 'Staff' || user?.is_superuser)
        ? '/agent/dashboard/'
        : user?.role === 'Seller'
        ? '/seller/dashboard/'
        : '/buyer/dashboard/',
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
    <div className="flex min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-emerald-500 selection:text-white font-sans">
      
      {/* 1. Leftmost Ultra-Sleek App Rail (Desktop - Rafiki AI Light Theme) */}
      <aside className="hidden w-[72px] shrink-0 flex-col items-center justify-between border-r border-slate-200/90 bg-white py-4 md:flex z-40 shadow-xs">
        
        {/* Top: Digiland Emblem */}
        <div className="flex flex-col items-center gap-5">
          <a
            href="/"
            title="Digiland Protocol"
            className="group relative flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-600 text-white shadow-md shadow-emerald-600/30 transition-all duration-200 hover:scale-105 hover:bg-emerald-500"
          >
            <ShieldCheck className="h-6 w-6" />
            <span className="absolute left-full ml-3 hidden whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-bold text-white shadow-xl group-hover:block z-50">
              Digiland Home
            </span>
          </a>

          <div className="h-[1px] w-8 bg-slate-200" />

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
                      ? 'bg-emerald-50 text-emerald-700 shadow-xs ring-1 ring-emerald-300'
                      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'
                  )}
                >
                  {item.active && (
                    <span className="absolute -left-3 h-5 w-1 rounded-r-full bg-emerald-600 shadow-xs" />
                  )}
                  <Icon className="h-5 w-5 transition-transform group-hover:scale-110" />
                  <span className="text-[9px] font-semibold tracking-tight mt-0.5">{item.label}</span>

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
                className="group relative flex h-10 w-10 items-center justify-center rounded-2xl text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
              >
                <LogOut className="h-4 w-4" />
                <span className="absolute left-full ml-3 hidden whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1 text-xs font-bold text-white shadow-xl group-hover:block z-50">
                  Sign out
                </span>
              </button>
            </form>
          ) : null}

          {/* User Avatar Circle */}
          <div
            title={`${displayName} (${currentRole})`}
            className="relative flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl bg-emerald-600 font-black text-sm text-white shadow-sm transition hover:scale-105"
          >
            {userInitial}
            <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-400 shadow-xs" />
          </div>
        </div>
      </aside>

      {/* 2. Main Workspace Layout */}
      <div className="flex min-w-0 flex-1 flex-col">
        
        {/* Top Navbar Header */}
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 backdrop-blur-xl sm:px-6 shadow-xs">
          
          {/* Mobile Menu Trigger & Title */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-700 md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs font-black uppercase tracking-[0.2em] text-emerald-700">
                {(title || 'Digiland').split(' - ')[0]}
              </span>
              {subtitle && (
                <>
                  <span className="hidden text-slate-400 sm:inline">•</span>
                  <span className="hidden truncate text-xs font-medium text-slate-600 sm:inline max-w-md">
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
                className="hidden sm:inline-flex h-8 items-center justify-center rounded-xl bg-emerald-50 border border-emerald-200/80 px-3 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100"
              >
                {action.label}
              </a>
            ))}

            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1 text-xs">
              <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-xs" />
              <span className="font-bold text-slate-900">{displayName}</span>
              <span className="rounded-md bg-emerald-100 px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wider text-emerald-800">
                {currentRole}
              </span>
            </div>

            {logoutUrl && (
              <form method="post" action={logoutUrl} className="md:hidden">
                <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                <button
                  type="submit"
                  className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-rose-600"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </form>
            )}
          </div>
        </header>

        {/* Mobile Flyout Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 flex flex-col bg-white/98 p-6 backdrop-blur-xl md:hidden text-slate-900">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-6 w-6 text-emerald-600" />
                <span className="font-black text-slate-950 text-base">Digiland Protocol</span>
              </div>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-full p-2 text-slate-500 hover:text-slate-950"
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
                    item.active ? 'bg-emerald-600 text-white' : 'text-slate-700 hover:bg-slate-100'
                  )}
                >
                  <item.icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </a>
              ))}
            </nav>
          </div>
        )}

        {/* Content Children */}
        <main className="flex-1 overflow-x-hidden p-4 sm:p-6 lg:p-8">{children}</main>

        <LocationPermissionModal />
      </div>
    </div>
  );
}
