import React from 'react';
import type { ReactNode } from 'react';
import { LogIn, LogOut, ShieldCheck, UserPlus } from 'lucide-react';
import type { ActionLink, NavItem, UserSummary } from '../../types.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { LocationPermissionModal } from '../ui/location-permission-modal.js';
import { cn } from '../../lib/utils.js';

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

interface PublicShellProps {
  title: string;
  subtitle?: string;
  nav: NavItem[];
  user?: UserSummary | null;
  logoutUrl?: string;
  csrfToken?: string;
  actions?: ActionLink[];
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  hideFooter?: boolean;
}

export function PublicShell({
  title,
  subtitle,
  nav,
  user,
  logoutUrl,
  csrfToken,
  actions,
  children,
  footer,
  className,
  hideFooter,
}: PublicShellProps) {
  const displayName = user?.full_name || user?.email || 'Visitor';

  return (
    <div className={cn('min-h-screen flex flex-col', className)}>
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/90 text-white backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3 rounded-full px-1 py-1 transition hover:opacity-90">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500 text-slate-950 font-black shadow-[0_0_20px_rgba(16,185,129,0.4)]">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div className="leading-tight">
              <div className="text-base font-black tracking-tight text-white">Digiland</div>
              <div className="text-xs font-bold uppercase tracking-[0.22em] text-emerald-400">Land escrow</div>
            </div>
          </a>

          {/* Nav links - centered (public only) */}
          <nav className="hidden min-w-0 flex-1 items-center justify-center gap-1 lg:flex">
            {!user &&
              nav.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'rounded-full px-4 py-2 text-sm font-bold transition-all duration-200',
                    item.active ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30' : 'text-slate-300 hover:text-white hover:bg-white/10'
                  )}
                >
                  {item.label}
                </a>
              ))}
          </nav>

          {/* Right actions */}
          <div className="ml-auto flex items-center gap-2.5 sm:gap-3 lg:ml-0">
            {user ? (
              <>
                <Badge tone="outline" className="hidden sm:inline-flex border-emerald-400/30 bg-emerald-500/10 text-emerald-300">{user.role}</Badge>
                <div className="hidden items-center gap-3 rounded-full border border-white/10 bg-slate-900/80 px-4 py-2 shadow-sm md:flex">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300 font-black border border-emerald-500/30">
                    {(displayName || 'U').slice(0, 1).toUpperCase()}
                  </div>
                  <div className="leading-tight">
                    <div className="text-sm font-bold text-white">{displayName}</div>
                    <div className="text-xs text-slate-400">{user.buyer_account_type ? `${user.buyer_account_type} buyer` : 'Authenticated'}</div>
                  </div>
                </div>
                {logoutUrl ? (
                  <form method="post" action={logoutUrl} className="hidden md:block">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                    <Button variant="outline" className="rounded-full border-white/15 bg-white/5 text-white hover:bg-white/10" type="submit">
                      <LogOut className="h-4 w-4" />
                      Sign out
                    </Button>
                  </form>
                ) : null}
              </>
            ) : (
              <div className="flex items-center gap-2 sm:gap-3">
                {actions && actions.length > 0 ? (
                  actions.map((action) => (
                    <a
                      key={`${action.label}-${action.href}`}
                      href={action.href}
                      target={action.external ? '_blank' : undefined}
                      rel={action.external ? 'noreferrer' : undefined}
                      className={actionClass(action.tone)}
                    >
                      {action.label}
                    </a>
                  ))
                ) : null}
                <a
                  href="/accounts/login/"
                  className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-white/20 bg-white/[0.08] px-3.5 sm:px-4 py-2 text-xs sm:text-sm font-bold text-white backdrop-blur-md transition-all duration-200 hover:border-emerald-400/50 hover:bg-emerald-400/15 hover:text-emerald-300"
                >
                  <LogIn className="h-4 w-4 text-emerald-400" />
                  <span>Sign In</span>
                </a>
                <a
                  href="/accounts/signup/"
                  className="inline-flex h-10 items-center justify-center gap-1.5 rounded-full border border-emerald-400/40 bg-gradient-to-r from-emerald-500 to-teal-500 px-3.5 sm:px-5 py-2 text-xs sm:text-sm font-black text-slate-950 shadow-[0_0_18px_rgba(16,185,129,0.4)] transition-all duration-200 hover:shadow-[0_0_24px_rgba(16,185,129,0.7)] hover:brightness-110"
                >
                  <UserPlus className="h-4 w-4" />
                  <span>Sign Up</span>
                </a>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>

      {/* Footer */}
      {!hideFooter && <footer className="border-t border-border/60 bg-white/80 backdrop-blur-xl py-6 mt-auto">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {footer ? footer : (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-4 w-4 text-emerald-700" />
                <span className="text-xs font-semibold text-foreground">Digiland</span>
                <span className="text-xs text-muted-foreground">© 2026 Secure land escrow platform.</span>
              </div>
              <div className="flex items-center gap-6 text-xs text-muted-foreground">
                <a href="/escrow-acts/" className="hover:text-emerald-700 transition-colors font-semibold">Legal</a>
                <a href="/parcels/" className="hover:text-emerald-700 transition-colors font-semibold">Marketplace</a>
                <a href="/accounts/login/" className="hover:text-emerald-700 transition-colors font-semibold">Sign in</a>
              </div>
            </div>
          )}
        </div>
      </footer>}

      <LocationPermissionModal />
    </div>
  );
}
