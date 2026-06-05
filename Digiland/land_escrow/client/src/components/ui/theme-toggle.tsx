import React, { useEffect, useState, useCallback } from 'react';
import { Sun, Moon } from 'lucide-react';
import { cn } from '../../lib/utils.js';

type Theme = 'light' | 'dark';

const STORAGE_KEY = 'digiland-theme';

function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
  } catch {
    // localStorage not available
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>('light');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = getStoredTheme();
    setTheme(stored);
    applyTheme(stored);
    setMounted(true);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      applyTheme(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Silently fail if localStorage is not available
      }
      return next;
    });
  }, []);

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e: MediaQueryListEvent) => {
      // Only apply system theme if no user preference is stored
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        const newTheme = e.matches ? 'dark' : 'light';
        setTheme(newTheme);
        applyTheme(newTheme);
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  if (!mounted) {
    return (
      <button
        className={cn(
          'relative inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white/80 text-foreground transition-colors hover:bg-muted',
          className
        )}
        aria-label="Toggle theme"
      >
        <Sun className="h-5 w-5" />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={cn(
        'relative inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white/80 text-foreground transition-all duration-300 hover:bg-muted hover:scale-105 active:scale-95 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700',
        className
      )}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      <span className="relative h-5 w-5">
        <Sun
          className={cn(
            'absolute inset-0 h-5 w-5 transition-all duration-300',
            theme === 'light'
              ? 'rotate-0 scale-100 opacity-100'
              : '-rotate-90 scale-0 opacity-0'
          )}
        />
        <Moon
          className={cn(
            'absolute inset-0 h-5 w-5 transition-all duration-300',
            theme === 'dark'
              ? 'rotate-0 scale-100 opacity-100'
              : 'rotate-90 scale-0 opacity-0'
          )}
        />
      </span>
    </button>
  );
}

/**
 * ThemeProvider - wraps the app and applies the theme class on mount.
 * Place this at the top of your component tree.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const theme = getStoredTheme();
    applyTheme(theme);
    setMounted(true);
  }, []);

  // Prevent flash of wrong theme
  if (!mounted) {
    return <>{children}</>;
  }

  return <>{children}</>;
}
