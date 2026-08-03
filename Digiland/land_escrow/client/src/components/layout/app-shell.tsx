import React from 'react';
import { Banknote, FileText, Gavel, Grid2X2, HandCoins, LayoutDashboard, LogOut, type LucideIcon, Menu, ReceiptText, ShieldCheck, Users, WalletCards } from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card } from '../ui/card.js';
import { LocationPermissionModal } from '../ui/location-permission-modal.js';
import type { ActionLink, NavItem, UserSummary } from '../../types.js';
import { cn } from '../../lib/utils.js';

const iconMap: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  parcels: Grid2X2,
  transactions: ReceiptText,
  legal: Gavel,
  joint: Users,
  checkout: WalletCards,
  groups: HandCoins,
  payments: Banknote,
  documents: FileText,
  security: ShieldCheck,
};

function actionClass(tone?: ActionLink['tone']) {
  return cn(
    'inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    tone === 'secondary'
      ? 'bg-secondary text-secondary-foreground hover:bg-secondary/85'
      : tone === 'outline'
        ? 'border border-border bg-white/80 text-foreground hover:bg-muted'
        : tone === 'ghost'
          ? 'bg-transparent text-foreground hover:bg-muted'
          : tone === 'accent'
            ? 'bg-accent text-accent-foreground hover:bg-accent/80'
            : 'bg-primary text-primary-foreground hover:bg-primary/90'
  );
}

interface AppShellProps {
  title: string;
  subtitle?: string;
  user?: UserSummary | null;
  nav: NavItem[];
  children: ReactNode;
  actions?: ActionLink[];
  logoutUrl?: string;
  csrfToken?: string;
}

export function AppShell({ title, subtitle, user, nav, children, actions, logoutUrl, csrfToken }: AppShellProps) {
  const currentRole = user?.role || 'Guest';
  const displayName = user?.full_name || user?.email || 'Visitor';

  return (
    <div className="min-h-screen bg-slate-50/50">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-white/90 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1536px] items-center gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3 rounded-full px-1 py-1 transition hover:opacity-90">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-700 text-white shadow-soft">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div className="leading-tight">
              <div className="text-base font-extrabold tracking-tight text-foreground">Digiland</div>
              <div className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-700">Land Escrow</div>
            </div>
          </a>

          <div className="hidden min-w-0 flex-1 lg:flex">
            <div className="ml-6 max-w-3xl">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-emerald-700">{title}</div>
              {subtitle ? <div className="truncate text-sm font-medium text-slate-500">{subtitle}</div> : null}
            </div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            {actions?.map((action) => (
              <a
                key={`${action.label}-${action.href}`}
                href={action.href}
                target={action.external ? '_blank' : undefined}
                rel={action.external ? 'noreferrer' : undefined}
                className={actionClass(action.tone)}
              >
                {action.label}
              </a>
            ))}
            <Badge tone="outline" className="hidden sm:inline-flex bg-slate-100/80 font-bold">
              {currentRole}
            </Badge>
            <div className="hidden items-center gap-3 rounded-full border border-border bg-white px-4 py-2 shadow-sm md:flex">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 font-bold text-sm">
                {(displayName || 'U').slice(0, 1).toUpperCase()}
              </div>
              <div className="leading-tight">
                <div className="text-sm font-bold text-slate-900">{displayName}</div>
                <div className="text-[11px] font-medium text-slate-500">{user?.buyer_account_type ? `${user.buyer_account_type} buyer` : 'Authenticated session'}</div>
              </div>
            </div>
            {logoutUrl ? (
              <form method="post" action={logoutUrl}>
                <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                <Button variant="outline" size="sm" className="rounded-full h-10 px-4 text-xs font-bold border-red-200/80 text-red-700 hover:bg-red-50 hover:border-red-300" type="submit">
                  <LogOut className="h-3.5 w-3.5 mr-1.5" />
                  Sign out
                </Button>
              </form>
            ) : null}
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1536px] gap-8 px-4 py-8 sm:px-6 lg:px-8">
        <aside className="hidden w-64 shrink-0 lg:block">
          <Card className="sticky top-24 overflow-hidden bg-white shadow-sm border-slate-200/80 rounded-3xl">
            <div className="border-b border-slate-100 px-6 py-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-[10px] font-black uppercase tracking-[0.24em] text-slate-400">Navigation</div>
                  <div className="mt-1 text-base font-extrabold tracking-tight text-slate-900">{title}</div>
                </div>
                {logoutUrl ? (
                  <form method="post" action={logoutUrl}>
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                    <Button variant="outline" size="sm" className="rounded-2xl h-8 px-2.5 text-xs" type="submit">
                      <LogOut className="h-3.5 w-3.5 mr-1" />
                      Exit
                    </Button>
                  </form>
                ) : null}
              </div>
            </div>
            <nav className="space-y-1.5 p-3">
              {nav.map((item) => {
                const Icon = item.icon ? iconMap[item.icon] || Grid2X2 : Grid2X2;
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-2xl px-4 py-3 text-xs font-bold transition-all duration-200',
                      item.active ? 'bg-emerald-700 text-white shadow-md' : 'text-slate-700 hover:bg-slate-100/70 hover:text-slate-900'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </a>
                );
              })}
            </nav>
            <div className="border-t border-slate-100 p-4">
              <div className="rounded-2xl bg-slate-50 p-3 text-xs">
                <div className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">Active Session</div>
                <div className="mt-1 font-bold text-slate-900 truncate">{displayName}</div>
                <div className="text-[11px] text-slate-500 truncate">{user?.email || 'Guest'}</div>
              </div>
            </div>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="mb-5 flex items-center gap-3 lg:hidden">
            <Button variant="outline" size="icon" className="rounded-full">
              <Menu className="h-4 w-4" />
            </Button>
            <div className="flex-1">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-emerald-700">{title}</div>
              {subtitle ? <div className="text-xs text-muted-foreground">{subtitle}</div> : null}
            </div>
            {logoutUrl ? (
              <form method="post" action={logoutUrl}>
                <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                <Button variant="outline" size="sm" className="rounded-full h-9 px-3 text-xs font-bold border-red-200/80 text-red-700 hover:bg-red-50" type="submit">
                  <LogOut className="h-3.5 w-3.5 mr-1" />
                  Sign out
                </Button>
              </form>
            ) : null}
          </div>
          {children}
        </main>
      </div>

      <LocationPermissionModal />
    </div>
  );
}

