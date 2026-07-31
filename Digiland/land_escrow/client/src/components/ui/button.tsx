import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils.js';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-emerald-500 text-slate-950 hover:bg-emerald-400 font-extrabold shadow-sm',
        secondary: 'bg-slate-800 text-slate-100 hover:bg-slate-700 border border-slate-700',
        outline: 'border border-white/20 bg-white/10 text-white hover:bg-white/20 hover:border-emerald-400/60 hover:text-emerald-300 backdrop-blur-md',
        ghost: 'bg-transparent text-slate-200 hover:bg-white/10 hover:text-white',
        accent: 'bg-emerald-600 text-white hover:bg-emerald-500',
        danger: 'bg-rose-600 text-white hover:bg-rose-500',
      },
      size: {
        sm: 'h-9 px-4',
        md: 'h-11 px-5',
        lg: 'h-12 px-6 text-base',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return <button ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />;
  }
);
Button.displayName = 'Button';
