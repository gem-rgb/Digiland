import React, { useMemo } from 'react';
import {
  Check,
  Circle,
  Clock3,
  AlertTriangle,
  RotateCcw,
  ShieldCheck,
  FileSearch,
  Wallet,
  PartyPopper,
  ChevronRight,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type EscrowStepStatus = 'completed' | 'current' | 'pending' | 'disputed';

export interface EscrowStep {
  id: string;
  label: string;
  description?: string;
  status: EscrowStepStatus;
  completedAt?: string | null;
  estimatedTime?: string | null;
  icon?: React.ReactNode;
}

export interface EscrowBranch {
  type: 'dispute' | 'refund';
  label: string;
  description?: string;
  active: boolean;
  fromStep: string;
  step?: EscrowStep;
}

export interface EscrowFlowProps {
  /** The ordered list of escrow steps */
  steps: EscrowStep[];
  /** Branch indicators (dispute/refund) */
  branches?: EscrowBranch[];
  /** Estimated time remaining for the entire flow */
  estimatedTimeRemaining?: string;
  /** Transaction ID for display */
  transactionId?: string;
  /** Callback when a step is clicked */
  onStepClick?: (step: EscrowStep) => void;
  /** Callback when dispute button is clicked */
  onDispute?: () => void;
  /** Callback when refund button is clicked */
  onRefund?: () => void;
  /** Compact mode (horizontal on desktop) */
  compact?: boolean;
  /** Additional class name */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Default Step Factory                                               */
/* ------------------------------------------------------------------ */

export function createDefaultEscrowSteps(
  currentStepIndex: number = 0,
  statuses?: Partial<Record<string, EscrowStepStatus>>
): EscrowStep[] {
  const defaultSteps: EscrowStep[] = [
    {
      id: 'initiated',
      label: 'Initiated',
      description: 'Transaction created and parties notified',
      status: 'pending',
      icon: <Wallet className="h-4 w-4" />,
    },
    {
      id: 'deposit_paid',
      label: 'Deposit Paid',
      description: 'Buyer deposit received in escrow',
      status: 'pending',
      icon: <ShieldCheck className="h-4 w-4" />,
    },
    {
      id: 'under_verification',
      label: 'Under Verification',
      description: 'Documents and ownership being verified',
      status: 'pending',
      icon: <FileSearch className="h-4 w-4" />,
    },
    {
      id: 'verification_hiatus',
      label: 'Verification Hiatus',
      description: '7-day cooling-off period for due diligence',
      estimatedTime: '7 days',
      status: 'pending',
      icon: <Clock3 className="h-4 w-4" />,
    },
    {
      id: 'completed',
      label: 'Completed',
      description: 'Funds released and ownership transferred',
      status: 'pending',
      icon: <PartyPopper className="h-4 w-4" />,
    },
  ];

  return defaultSteps.map((step, i) => {
    const customStatus = statuses?.[step.id];
    if (customStatus) {
      return { ...step, status: customStatus };
    }
    if (i < currentStepIndex) {
      return { ...step, status: 'completed' as const };
    }
    if (i === currentStepIndex) {
      return { ...step, status: 'current' as const };
    }
    return step;
  });
}

/* ------------------------------------------------------------------ */
/*  Step Icon Component                                                */
/* ------------------------------------------------------------------ */

function StepIcon({
  step,
  size = 'default',
}: {
  step: EscrowStep;
  size?: 'default' | 'sm';
}) {
  const dim = size === 'sm' ? 'h-8 w-8' : 'h-10 w-10';
  const iconDim = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';

  switch (step.status) {
    case 'completed':
      return (
        <div className={cn(dim, 'flex items-center justify-center rounded-full bg-emerald-600 text-white shadow-sm')}>
          <Check className={iconDim} />
        </div>
      );
    case 'current':
      return (
        <div className="relative">
          <div className={cn(dim, 'flex items-center justify-center rounded-full bg-emerald-100 text-emerald-700 ring-2 ring-emerald-500 ring-offset-2 dark:bg-emerald-900/40 dark:text-emerald-400 dark:ring-emerald-500 dark:ring-offset-slate-900')}>
            {step.icon || <Circle className={iconDim} />}
          </div>
          <div className="absolute -inset-1 animate-pulse-ring rounded-full border-2 border-emerald-400" />
        </div>
      );
    case 'disputed':
      return (
        <div className={cn(dim, 'flex items-center justify-center rounded-full bg-rose-100 text-rose-600 ring-2 ring-rose-400 ring-offset-2 dark:bg-rose-900/40 dark:text-rose-400 dark:ring-rose-500 dark:ring-offset-slate-900')}>
          <AlertTriangle className={iconDim} />
        </div>
      );
    case 'pending':
    default:
      return (
        <div className={cn(dim, 'flex items-center justify-center rounded-full bg-muted text-muted-foreground dark:bg-slate-700 dark:text-slate-400')}>
          {step.icon || <Circle className={iconDim} />}
        </div>
      );
  }
}

/* ------------------------------------------------------------------ */
/*  Vertical Step Component                                            */
/* ------------------------------------------------------------------ */

function VerticalStep({
  step,
  isLast,
  branch,
  onStepClick,
}: {
  step: EscrowStep;
  isLast: boolean;
  branch?: EscrowBranch;
  onStepClick?: (step: EscrowStep) => void;
}) {
  const statusLabel: Record<EscrowStepStatus, string> = {
    completed: 'Completed',
    current: 'In Progress',
    pending: 'Pending',
    disputed: 'Disputed',
  };

  const statusTone: Record<EscrowStepStatus, 'success' | 'warning' | 'muted' | 'danger'> = {
    completed: 'success',
    current: 'warning',
    pending: 'muted',
    disputed: 'danger',
  };

  return (
    <div className="relative flex gap-4">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-5 top-10 h-[calc(100%-2.5rem)] w-0.5">
          <div
            className={cn(
              'h-full w-full',
              step.status === 'completed'
                ? 'bg-emerald-500'
                : step.status === 'disputed'
                  ? 'bg-rose-400'
                  : 'bg-border dark:bg-slate-700'
            )}
          />
        </div>
      )}

      {/* Icon */}
      <div className="relative z-10 flex-shrink-0">
        <StepIcon step={step} />
      </div>

      {/* Content */}
      <div className="flex-1 pb-8">
        <button
          type="button"
          onClick={() => onStepClick?.(step)}
          className="text-left w-full group"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <h4
                className={cn(
                  'text-sm font-bold transition-colors',
                  step.status === 'completed' ? 'text-emerald-700 dark:text-emerald-400' :
                  step.status === 'current' ? 'text-foreground' :
                  step.status === 'disputed' ? 'text-rose-700 dark:text-rose-400' :
                  'text-muted-foreground'
                )}
              >
                {step.label}
                {step.status === 'current' && (
                  <span className="ml-2 inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                    <span className="mr-1 h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Current
                  </span>
                )}
              </h4>
              {step.description && (
                <p className="mt-1 text-xs text-muted-foreground leading-5">{step.description}</p>
              )}
            </div>
            <Badge tone={statusTone[step.status]} className="shrink-0 text-[9px]">
              {statusLabel[step.status]}
            </Badge>
          </div>

          {/* Meta info */}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {step.completedAt && (
              <span className="flex items-center gap-1">
                <Check className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                {step.completedAt}
              </span>
            )}
            {step.estimatedTime && step.status !== 'completed' && (
              <span className="flex items-center gap-1">
                <Clock3 className="h-3 w-3" />
                ~{step.estimatedTime}
              </span>
            )}
          </div>
        </button>

        {/* Branch indicator */}
        {branch && branch.active && branch.step && (
          <div className="mt-3 ml-2 rounded-2xl border border-dashed border-rose-300 bg-rose-50/80 p-3 dark:border-rose-700 dark:bg-rose-950/30">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-400">
                {branch.type === 'dispute' ? (
                  <AlertTriangle className="h-3 w-3" />
                ) : (
                  <RotateCcw className="h-3 w-3" />
                )}
              </div>
              <div>
                <div className="text-xs font-bold text-rose-700 dark:text-rose-400">{branch.label}</div>
                {branch.step.description && (
                  <p className="text-[11px] text-rose-600/80 dark:text-rose-300/80">{branch.step.description}</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Horizontal Step Component (compact)                                */
/* ------------------------------------------------------------------ */

function HorizontalStep({
  step,
  isLast,
  onStepClick,
}: {
  step: EscrowStep;
  isLast: boolean;
  onStepClick?: (step: EscrowStep) => void;
}) {
  return (
    <div className="flex items-start">
      <button
        type="button"
        onClick={() => onStepClick?.(step)}
        className="flex flex-col items-center gap-2 group"
      >
        <StepIcon step={step} size="sm" />
        <div className="text-center">
          <div
            className={cn(
              'text-[11px] font-bold leading-tight',
              step.status === 'completed' ? 'text-emerald-700 dark:text-emerald-400' :
              step.status === 'current' ? 'text-foreground' :
              step.status === 'disputed' ? 'text-rose-700 dark:text-rose-400' :
              'text-muted-foreground'
            )}
          >
            {step.label}
          </div>
          {step.estimatedTime && step.status !== 'completed' && (
            <div className="mt-0.5 text-[10px] text-muted-foreground">~{step.estimatedTime}</div>
          )}
        </div>
      </button>
      {!isLast && (
        <div className="flex flex-1 items-center px-2 pt-4">
          <div
            className={cn(
              'h-0.5 w-full',
              step.status === 'completed' ? 'bg-emerald-500' : 'bg-border dark:bg-slate-700'
            )}
          />
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function EscrowFlow({
  steps,
  branches = [],
  estimatedTimeRemaining,
  transactionId,
  onStepClick,
  onDispute,
  onRefund,
  compact = false,
  className,
}: EscrowFlowProps) {
  const currentStepIndex = useMemo(
    () => steps.findIndex((s) => s.status === 'current'),
    [steps]
  );

  const hasDispute = steps.some((s) => s.status === 'disputed') ||
    branches.some((b) => b.active && b.type === 'dispute');

  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const progressPercent = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  return (
    <Card className={cn('bg-white/92 dark:bg-slate-800/90', className)}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              Escrow Progress
            </CardTitle>
            {transactionId && (
              <CardDescription className="mt-1">
                Transaction {transactionId}
              </CardDescription>
            )}
          </div>
          <div className="flex items-center gap-2">
            {hasDispute && (
              <Badge tone="danger">
                <AlertTriangle className="mr-1 h-3 w-3" />
                Disputed
              </Badge>
            )}
            {estimatedTimeRemaining && (
              <Badge tone="outline" className="flex items-center gap-1">
                <Clock3 className="h-3 w-3" />
                ~{estimatedTimeRemaining} remaining
              </Badge>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
            <span>{completedCount} of {steps.length} steps complete</span>
            <span className="font-bold text-foreground">{Math.round(progressPercent)}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-muted/60 dark:bg-slate-700/40 overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-700',
                hasDispute ? 'bg-rose-500' : 'bg-emerald-500'
              )}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {compact ? (
          /* Horizontal layout */
          <div className="flex items-start overflow-x-auto pb-2 scrollbar-thin">
            {steps.map((step, i) => (
              <HorizontalStep
                key={step.id}
                step={step}
                isLast={i === steps.length - 1}
                onStepClick={onStepClick}
              />
            ))}
          </div>
        ) : (
          /* Vertical layout */
          <div>
            {steps.map((step, i) => {
              const branch = branches.find((b) => b.fromStep === step.id);
              return (
                <VerticalStep
                  key={step.id}
                  step={step}
                  isLast={i === steps.length - 1}
                  branch={branch}
                  onStepClick={onStepClick}
                />
              );
            })}
          </div>
        )}

        {/* Action buttons */}
        {(onDispute || onRefund) && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-border/60 pt-4 dark:border-slate-700/40">
            {onDispute && (
              <Button
                variant="outline"
                size="sm"
                onClick={onDispute}
                className="rounded-full border-rose-300 text-rose-700 hover:bg-rose-50 dark:border-rose-700 dark:text-rose-400 dark:hover:bg-rose-950/30"
              >
                <AlertTriangle className="mr-2 h-3.5 w-3.5" />
                Raise Dispute
              </Button>
            )}
            {onRefund && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefund}
                className="rounded-full border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950/30"
              >
                <RotateCcw className="mr-2 h-3.5 w-3.5" />
                Request Refund
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default EscrowFlow;
