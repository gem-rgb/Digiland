import React from 'react';
import { Banknote, FileText, Gavel, Grid2X2, HandCoins, LayoutDashboard, LogOut, type LucideIcon, Menu, ReceiptText, ShieldCheck, Users, WalletCards } from 'lucide-react';
import type { ReactNode } from 'react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card } from '../ui/card.js';
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
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-white/82 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3 rounded-full px-1 py-1 transition hover:opacity-90">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-soft">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div className="leading-tight">
              <div className="text-base font-extrabold tracking-tight text-foreground">Digiland</div>
              <div className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Land escrow</div>
            </div>
          </a>

          <div className="hidden min-w-0 flex-1 lg:flex">
            <div className="ml-4 max-w-2xl">
              <div className="text-sm font-bold uppercase tracking-[0.22em] text-emerald-700">{title}</div>
              {subtitle ? <div className="truncate text-sm text-muted-foreground">{subtitle}</div> : null}
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
            <Badge tone="outline" className="hidden sm:inline-flex">
              {currentRole}
            </Badge>
            <div className="hidden items-center gap-3 rounded-full border border-border bg-background/80 px-4 py-2 shadow-sm md:flex">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accent-foreground font-bold">
                {(displayName || 'U').slice(0, 1).toUpperCase()}
              </div>
              <div className="leading-tight">
                <div className="text-sm font-semibold text-foreground">{displayName}</div>
                <div className="text-xs text-muted-foreground">{user?.buyer_account_type ? `${user.buyer_account_type} buyer` : 'Authenticated session'}</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <aside className="hidden w-72 shrink-0 lg:block">
          <Card className="sticky top-24 overflow-hidden bg-white/90">
            <div className="border-b border-border/70 px-6 py-5">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Navigation</div>
              <div className="mt-1 text-lg font-extrabold tracking-tight text-foreground">{title}</div>
              {subtitle ? <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div> : null}
            </div>
            <nav className="space-y-1 p-3">
              {nav.map((item) => {
                const Icon = item.icon ? iconMap[item.icon] || Grid2X2 : Grid2X2;
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition-colors',
                      item.active ? 'bg-primary text-primary-foreground shadow-sm' : 'text-foreground hover:bg-muted'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </a>
                );
              })}
            </nav>
            <div className="border-t border-border/70 p-4">
            <div className="rounded-3xl bg-muted/60 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">Session</div>
              <div className="mt-2 text-sm font-semibold text-foreground">{displayName}</div>
              <div className="mt-1 text-xs text-muted-foreground">{user?.email || 'Guest'}</div>
              <div className="mt-4">
                {logoutUrl ? (
                  <form method="post" action={logoutUrl}>
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                    <Button variant="outline" className="w-full justify-start rounded-2xl" type="submit">
                      <LogOut className="h-4 w-4" />
                      Sign out
                    </Button>
                  </form>
                ) : (
                  <a href="/accounts/login/" className="inline-flex h-11 w-full items-center justify-start gap-2 rounded-2xl border border-border bg-white/80 px-4 text-sm font-semibold text-foreground transition-colors hover:bg-muted">
                    <LogOut className="h-4 w-4" />
                    Sign in
                  </a>
                )}
              </div>
            </div>
            </div>
          </Card>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="mb-5 flex items-center gap-3 lg:hidden">
            <Button variant="outline" size="icon" className="rounded-full">
              <Menu className="h-4 w-4" />
            </Button>
            <div>
              <div className="text-sm font-bold uppercase tracking-[0.22em] text-emerald-700">{title}</div>
              {subtitle ? <div className="text-sm text-muted-foreground">{subtitle}</div> : null}
            </div>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
