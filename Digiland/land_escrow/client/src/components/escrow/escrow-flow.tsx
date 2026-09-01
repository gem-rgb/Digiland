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
  UserCheck,
  MapPin,
  Scale,
  FileText,
  BadgeCheck,
  Compass,
  Building2,
  Receipt,
  ArrowRightLeft,
  Info,
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
  stage?: 'Stage A: Pre-Interest' | 'Stage B: Due Diligence' | 'Stage C: Settlement & Transfer';
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
  /** The ordered list of transaction milestone steps */
  steps?: EscrowStep[];
  /** Branch indicators (dispute/case) */
  branches?: EscrowBranch[];
  /** Estimated time remaining for the flow */
  estimatedTimeRemaining?: string;
  /** Transaction ID for display */
  transactionId?: string;
  /** Callback when a step is clicked */
  onStepClick?: (step: EscrowStep) => void;
  /** Callback when dispute button is clicked */
  onDispute?: () => void;
  /** Callback when refund/reversal button is clicked */
  onRefund?: () => void;
  /** Compact mode (horizontal on desktop) */
  compact?: boolean;
  /** Additional class name */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  15 Transaction Milestones Factory                                  */
/* ------------------------------------------------------------------ */

export function create15MilestoneSteps(
  currentStepIndex: number = 0,
  statuses?: Partial<Record<string, EscrowStepStatus>>
): EscrowStep[] {
  const milestoneDefinitions: EscrowStep[] = [
    // Stage A: Pre-Interest Verification
    {
      id: 'PARCEL_LISTED',
      label: '1. Parcel Listed',
      stage: 'Stage A: Pre-Interest',
      description: 'Property details, registry numbers, and photos submitted to platform',
      status: 'pending',
      icon: <Building2 className="h-4 w-4" />,
    },
    {
      id: 'SELLER_IDENTITY_VERIFIED',
      label: '2. Seller Identity Verified',
      stage: 'Stage A: Pre-Interest',
      description: 'Government ID, facial biometric match, and seller phone check verified',
      status: 'pending',
      icon: <UserCheck className="h-4 w-4" />,
    },
    {
      id: 'PARCEL_DOCS_SUBMITTED',
      label: '3. Parcel Documents Submitted',
      stage: 'Stage A: Pre-Interest',
      description: 'Title deed, mutation forms, or allotment letters uploaded',
      status: 'pending',
      icon: <FileText className="h-4 w-4" />,
    },
    {
      id: 'INITIAL_SCREENING_COMPLETED',
      label: '4. Document Screening Completed',
      stage: 'Stage A: Pre-Interest',
      description: 'Automated AI checks for title consistency and gazette caveats completed',
      status: 'pending',
      icon: <FileSearch className="h-4 w-4" />,
    },
    {
      id: 'PARCEL_LISTED_FOR_BUYERS',
      label: '5. Listed for Buyers',
      stage: 'Stage A: Pre-Interest',
      description: 'Verified listing published with controlled disclosure overview',
      status: 'pending',
      icon: <BadgeCheck className="h-4 w-4" />,
    },

    // Stage B: Transaction / Interest Verification
    {
      id: 'BUYER_EXPRESSES_INTEREST',
      label: '6. Buyer Expresses Interest',
      stage: 'Stage B: Due Diligence',
      description: 'Genuine purchase inquiry registered; detailed records unlocked',
      status: 'pending',
      icon: <Compass className="h-4 w-4" />,
    },
    {
      id: 'PROFESSIONAL_VERIFICATION_INITIATED',
      label: '7. Verification Commission Initiated',
      stage: 'Stage B: Due Diligence',
      description: 'Licensed field professionals assigned to conduct independent diligence',
      status: 'pending',
      icon: <Clock3 className="h-4 w-4" />,
    },
    {
      id: 'SURVEY_VERIFICATION',
      label: '8. Survey Verification',
      stage: 'Stage B: Due Diligence',
      description: 'Surveyor checks boundary beacons, GPS coordinates, and registry maps',
      status: 'pending',
      icon: <MapPin className="h-4 w-4" />,
    },
    {
      id: 'PHYSICAL_SITE_ASSESSMENT',
      label: '9. Physical Site Assessment',
      stage: 'Stage B: Due Diligence',
      description: 'On-ground visit inspecting access road, topography, and neighboring claims',
      status: 'pending',
      icon: <Building2 className="h-4 w-4" />,
    },
    {
      id: 'LEGAL_DUE_DILIGENCE',
      label: '10. Legal Due Diligence',
      stage: 'Stage B: Due Diligence',
      description: 'Advocate official search at Ministry of Lands and encumbrance certificate',
      status: 'pending',
      icon: <Scale className="h-4 w-4" />,
    },
    {
      id: 'TRANSACTION_AGREEMENT',
      label: '11. Transaction Agreement Signed',
      stage: 'Stage B: Due Diligence',
      description: 'Sale agreement executed with digital cryptographic signatures by both parties',
      status: 'pending',
      icon: <FileText className="h-4 w-4" />,
    },

    // Stage C: Settlement & Ownership Transfer
    {
      id: 'PAYMENT_INITIATED',
      label: '12. Payment Initiated',
      stage: 'Stage C: Settlement & Transfer',
      description: 'Payment prompt sent to buyer via M-Pesa STK or direct settlement instructions',
      status: 'pending',
      icon: <Wallet className="h-4 w-4" />,
    },
    {
      id: 'PAYMENT_CONFIRMED',
      label: '13. Payment Confirmed by Provider',
      stage: 'Stage C: Settlement & Transfer',
      description: 'Provider receipt and immutable transaction confirmation logged by DigiLand',
      status: 'pending',
      icon: <Receipt className="h-4 w-4" />,
    },
    {
      id: 'OWNERSHIP_TRANSFER_PROCESS',
      label: '14. Ownership Transfer Process',
      stage: 'Stage C: Settlement & Transfer',
      description: 'Stamp duty payment, land control board clearance, and title transfer filing',
      status: 'pending',
      icon: <ArrowRightLeft className="h-4 w-4" />,
    },
    {
      id: 'TRANSACTION_COMPLETED',
      label: '15. Transaction Completed',
      stage: 'Stage C: Settlement & Transfer',
      description: 'Title transferred to buyer, verified transaction audit package archived',
      status: 'pending',
      icon: <PartyPopper className="h-4 w-4" />,
    },
  ];

  return milestoneDefinitions.map((step, i) => {
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

// Backward compatibility helper
export function createDefaultEscrowSteps(
  currentStepIndex: number = 0,
  statuses?: Partial<Record<string, EscrowStepStatus>>
): EscrowStep[] {
  return create15MilestoneSteps(currentStepIndex, statuses);
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
  const dim = size === 'sm' ? 'h-7 w-7' : 'h-9 w-9';
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
    <div className="relative flex gap-3">
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-[1.125rem] top-9 h-[calc(100%-2.25rem)] w-0.5">
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
      <div className="flex-1 pb-6">
        <button
          type="button"
          onClick={() => onStepClick?.(step)}
          className="text-left w-full group"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h4
                  className={cn(
                    'text-xs sm:text-sm font-semibold transition-colors',
                    step.status === 'completed' ? 'text-emerald-700 dark:text-emerald-400' :
                    step.status === 'current' ? 'text-foreground font-bold' :
                    step.status === 'disputed' ? 'text-rose-700 dark:text-rose-400' :
                    'text-muted-foreground'
                  )}
                >
                  {step.label}
                </h4>
                {step.stage && (
                  <span className="hidden sm:inline-block text-[10px] text-muted-foreground/80 bg-muted/50 px-1.5 py-0.5 rounded">
                    {step.stage}
                  </span>
                )}
                {step.status === 'current' && (
                  <span className="inline-flex items-center text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                    <span className="mr-1 h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Active
                  </span>
                )}
              </div>
              {step.description && (
                <p className="mt-0.5 text-xs text-muted-foreground leading-4">{step.description}</p>
              )}
            </div>
            <Badge tone={statusTone[step.status]} className="shrink-0 text-[9px]">
              {statusLabel[step.status]}
            </Badge>
          </div>

          {/* Meta info */}
          <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
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
          <div className="mt-2.5 rounded-xl border border-dashed border-rose-300 bg-rose-50/80 p-2.5 dark:border-rose-700 dark:bg-rose-950/30">
            <div className="flex items-center gap-2">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-400">
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
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function EscrowFlow({
  steps: userSteps,
  branches = [],
  estimatedTimeRemaining,
  transactionId,
  onStepClick,
  onDispute,
  onRefund,
  compact = false,
  className,
}: EscrowFlowProps) {
  const steps = useMemo(() => {
    return userSteps && userSteps.length > 0 ? userSteps : create15MilestoneSteps(0);
  }, [userSteps]);

  const hasDispute = steps.some((s) => s.status === 'disputed') ||
    branches.some((b) => b.active && b.type === 'dispute');

  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const progressPercent = steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  return (
    <Card className={cn('bg-white/92 dark:bg-slate-800/90 shadow-sm border border-border/80', className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              Transaction Verification Milestones
            </CardTitle>
            {transactionId && (
              <CardDescription className="mt-1 text-xs">
                Tracking 15 Independent Verification & Settlement Stages • Ref: {transactionId}
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

        {/* Structured verification non-custodial disclaimer banner */}
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-emerald-50/70 p-2.5 text-xs text-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/40">
          <Info className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
          <p className="leading-4">
            <strong>Platform Assurance:</strong> DigiLand conducts structured multi-party verification and maintains traceable audit evidence. DigiLand is not an escrow custodian and does not hold customer funds.
          </p>
        </div>

        {/* Progress bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
            <span>{completedCount} of {steps.length} milestones completed</span>
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

      <CardContent className="pt-2">
        {/* Milestone sequence */}
        <div className="space-y-0.5">
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
                Open Dispute Case
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
                Request Payment Reversal
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Direct alias for modern architecture
export const TransactionMilestonesFlow = EscrowFlow;

export default EscrowFlow;
