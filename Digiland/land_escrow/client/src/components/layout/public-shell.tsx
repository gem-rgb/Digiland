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
    'inline-flex h-10 items-center justify-center rounded-xl px-5 text-xs font-bold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500',
    tone === 'secondary' || tone === 'outline' || tone === 'ghost'
      ? 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-950 shadow-sm'
      : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 hover:scale-[1.02]'
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
    <div className={cn('min-h-screen flex flex-col bg-slate-50 text-slate-900 antialiased font-sans', className)}>
      
      {/* Light Rafiki AI Style Header */}
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/95 text-slate-900 backdrop-blur-xl shadow-xs">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          
          {/* Brand Logo */}
          <a href="/" className="flex items-center gap-3 rounded-full px-1 py-1 transition hover:opacity-90">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white font-black shadow-md shadow-emerald-600/30">
              <ShieldCheck className="h-5 w-5" />
            </span>
            <div className="leading-tight text-left">
              <div className="text-base font-black tracking-tight text-slate-950">Digiland</div>
              <div className="text-[10px] font-bold uppercase tracking-[0.22em] text-emerald-700">Land Escrow</div>
            </div>
          </a>

          {/* Centered Public Navigation Links */}
          <nav className="hidden min-w-0 flex-1 items-center justify-center gap-1.5 lg:flex">
            {!user &&
              nav.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'rounded-xl px-4 py-2 text-xs font-bold transition-all duration-200',
                    item.active
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-xs'
                      : 'text-slate-600 hover:text-slate-950 hover:bg-slate-100/80'
                  )}
                >
                  {item.label}
                </a>
              ))}
          </nav>

          {/* Right User or Guest Action Buttons */}
          <div className="ml-auto flex items-center gap-2.5 sm:gap-3 lg:ml-0">
            {user ? (
              <>
                <Badge tone="outline" className="hidden sm:inline-flex border-emerald-300 bg-emerald-50 text-emerald-800 font-bold">
                  {user.role}
                </Badge>
                <div className="hidden items-center gap-3 rounded-xl border border-slate-200 bg-white px-3.5 py-1.5 shadow-sm md:flex">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white font-black text-xs shadow-xs">
                    {(displayName || 'U').slice(0, 1).toUpperCase()}
                  </div>
                  <div className="leading-tight text-left">
                    <div className="text-xs font-bold text-slate-900">{displayName}</div>
                    <div className="text-[10px] text-slate-500">{user.buyer_account_type ? `${user.buyer_account_type} buyer` : 'Authenticated'}</div>
                  </div>
                </div>
                {logoutUrl ? (
                  <form method="post" action={logoutUrl} className="hidden md:block">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken || ''} />
                    <Button variant="outline" className="h-9 rounded-xl border-slate-200 bg-white text-slate-700 hover:bg-slate-100 text-xs font-bold" type="submit">
                      <LogOut className="h-3.5 w-3.5 mr-1" />
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
                ) : (
                  <>
                    <a
                      href="/accounts/login/"
                      className="inline-flex h-9 items-center justify-center rounded-xl border border-slate-300 bg-white px-4 text-xs font-bold text-slate-700 shadow-xs hover:bg-slate-50 hover:text-slate-950 transition"
                    >
                      <LogIn className="mr-1.5 h-3.5 w-3.5 text-slate-500" />
                      Sign In
                    </a>
                    <a
                      href="/accounts/signup/"
                      className="inline-flex h-9 items-center justify-center rounded-xl bg-emerald-600 px-4 text-xs font-bold text-white shadow-md shadow-emerald-600/20 hover:bg-emerald-500 transition hover:scale-[1.02]"
                    >
                      <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                      Sign Up
                    </a>
                  </>
                )}
              </div>
            )}
          </div>

        </div>
      </header>

      {/* Main Page Content Body */}
      <main className="flex-1 w-full">{children}</main>

      {/* Footer */}
      {!hideFooter && footer}

      <LocationPermissionModal />
    </div>
  );
}
