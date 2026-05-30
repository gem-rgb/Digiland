import React from 'react';
import { Badge } from '../ui/badge.js';
import type { ActionLink } from '../../types.js';
import { cn } from '../../lib/utils.js';

interface PageHeaderProps {
  kicker?: string;
  title: string;
  subtitle?: string;
  actions?: ActionLink[];
  badge?: string;
  className?: string;
}

export function PageHeader({ kicker, title, subtitle, actions, badge, className }: PageHeaderProps) {
  return (
    <section className={cn('mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between', className)}>
      <div className="max-w-3xl">
        {kicker ? <div className="mb-3 text-xs font-bold uppercase tracking-[0.28em] text-emerald-700">{kicker}</div> : null}
        <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">{title}</h1>
        {subtitle ? <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">{subtitle}</p> : null}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {badge ? <Badge tone="outline" className="px-4 py-2">{badge}</Badge> : null}
        {actions?.map((action) => (
          <a
            key={`${action.label}-${action.href}`}
            href={action.href}
            target={action.external ? '_blank' : undefined}
            rel={action.external ? 'noreferrer' : undefined}
            className={cn(
              'inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              action.tone === 'secondary'
                ? 'bg-secondary text-secondary-foreground hover:bg-secondary/85'
                : action.tone === 'outline'
                  ? 'border border-border bg-white/80 text-foreground hover:bg-muted'
                  : action.tone === 'ghost'
                    ? 'bg-transparent text-foreground hover:bg-muted'
                    : action.tone === 'accent'
                      ? 'bg-accent text-accent-foreground hover:bg-accent/80'
                      : 'bg-primary text-primary-foreground hover:bg-primary/90'
            )}
          >
            {action.label}
          </a>
        ))}
      </div>
    </section>
  );
}
