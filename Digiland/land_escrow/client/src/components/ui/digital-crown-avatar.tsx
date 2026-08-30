import React from 'react';
import { Building2, ShieldCheck, User as UserIcon } from 'lucide-react';
import { cn } from '../../lib/utils.js';

interface DigitalCrownAvatarProps {
  name: string;
  isManager?: boolean;
  isOrganization?: boolean;
  roleTitle?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  imageUrl?: string | null;
  className?: string;
  showTooltip?: boolean;
}

export function DigitalCrownAvatar({
  name,
  isManager = false,
  isOrganization = false,
  roleTitle,
  size = 'md',
  imageUrl,
  className,
  showTooltip = true,
}: DigitalCrownAvatarProps) {
  const initial = (name || 'U').charAt(0).toUpperCase();

  const sizeClasses = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-10 w-10 text-sm',
    lg: 'h-14 w-14 text-lg',
    xl: 'h-20 w-20 text-2xl',
  };

  const crownContainerSizes = {
    sm: 'h-12 w-12',
    md: 'h-16 w-16',
    lg: 'h-20 w-20',
    xl: 'h-28 w-28',
  };

  const crownSvgOffsets = {
    sm: '-top-2.5',
    md: '-top-3.5',
    lg: '-top-4.5',
    xl: '-top-6',
  };

  return (
    <div className={cn('relative inline-flex items-center justify-center group select-none', className)}>
      {/* 1. DIGITAL GEOMETRIC CROWN (Subtle particles, connected geometric nodes & orbital aura) */}
      {isManager && !isOrganization && (
        <div
          className={cn(
            'pointer-events-none absolute z-10 flex items-center justify-center',
            crownContainerSizes[size],
            crownSvgOffsets[size]
          )}
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 100 40"
            className="w-full h-full text-emerald-400 drop-shadow-[0_2px_8px_rgba(16,185,129,0.45)] transition-transform duration-300 group-hover:scale-110"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Connecting Geometric Arcs */}
            <path
              d="M 22 26 Q 36 12 50 16 Q 64 12 78 26"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="2 3"
              className="opacity-75"
            />

            {/* Central Node (Crown Apex) */}
            <g transform="translate(50, 10)">
              <polygon points="0,-4 3.5,0 0,4 -3.5,0" fill="#10b981" />
              <circle cx="0" cy="0" r="1.5" fill="#ffffff" />
            </g>

            {/* Left Node */}
            <g transform="translate(32, 16)">
              <circle cx="0" cy="0" r="2.5" fill="#10b981" className="opacity-90" />
              <circle cx="0" cy="0" r="1" fill="#ffffff" />
            </g>

            {/* Right Node */}
            <g transform="translate(68, 16)">
              <circle cx="0" cy="0" r="2.5" fill="#10b981" className="opacity-90" />
              <circle cx="0" cy="0" r="1" fill="#ffffff" />
            </g>

            {/* Outer Left Orbital Node */}
            <g transform="translate(18, 26)">
              <polygon points="0,-2.5 2.5,0 0,2.5 -2.5,0" fill="#34d399" className="opacity-80" />
            </g>

            {/* Outer Right Orbital Node */}
            <g transform="translate(82, 26)">
              <polygon points="0,-2.5 2.5,0 0,2.5 -2.5,0" fill="#34d399" className="opacity-80" />
            </g>
          </svg>
        </div>
      )}

      {/* 2. MAIN AVATAR ELEMENT */}
      <div
        className={cn(
          'relative flex items-center justify-center rounded-2xl font-black text-white shadow-sm transition-all duration-200 group-hover:scale-105 overflow-hidden',
          sizeClasses[size],
          isOrganization
            ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 ring-2 ring-indigo-500/30'
            : isManager
            ? 'bg-gradient-to-br from-emerald-600 via-teal-700 to-slate-950 ring-2 ring-emerald-400 shadow-md shadow-emerald-950/20'
            : 'bg-gradient-to-br from-slate-700 to-slate-900 ring-1 ring-slate-200'
        )}
      >
        {imageUrl ? (
          <img src={imageUrl} alt={name} className="h-full w-full object-cover" />
        ) : isOrganization ? (
          <Building2 className="h-1/2 w-1/2 text-indigo-300" />
        ) : (
          <span>{initial}</span>
        )}

        {/* Status indicator badge */}
        {isManager && !isOrganization && (
          <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-400 shadow-xs" />
        )}
        {isOrganization && (
          <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-indigo-400 shadow-xs" />
        )}
      </div>

      {/* 3. SUBTLE HOVER TOOLTIP */}
      {showTooltip && (
        <div className="absolute left-1/2 -bottom-8 -translate-x-1/2 pointer-events-none hidden whitespace-nowrap rounded-lg bg-slate-900/95 px-2.5 py-1 text-[10px] font-bold text-white shadow-xl backdrop-blur-md group-hover:block z-50 transition-opacity">
          {roleTitle || (isManager ? 'Team Manager' : isOrganization ? 'Authorized Representative' : name)}
        </div>
      )}
    </div>
  );
}
