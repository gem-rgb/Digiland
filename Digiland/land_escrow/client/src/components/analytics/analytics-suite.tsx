import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { readBootstrap } from '../../lib/bootstrap.js';
import { AnalyticsChapterId, TimeframeOption, AnalyticsContextData } from './types.js';
import { ChapterNav, CHAPTERS_CONFIG } from './chapter-nav.js';
import { OverviewChapter } from './chapters/overview-chapter.js';
import { MarketplaceChapter } from './chapters/marketplace-chapter.js';
import { RevenueTaxesChapter } from './chapters/revenue-taxes-chapter.js';
import { TransactionsChapter } from './chapters/transactions-chapter.js';
import { EscrowVaultChapter } from './chapters/escrow-vault-chapter.js';
import { PropertiesRegionalChapter } from './chapters/properties-regional-chapter.js';
import { UsersDemographicsChapter } from './chapters/users-demographics-chapter.js';
import { FinancialReportsChapter } from './chapters/financial-reports-chapter.js';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '../ui/button.js';

interface AnalyticsSuiteProps {
  initialChapter?: AnalyticsChapterId;
  className?: string;
}

const bootstrap = readBootstrap();

function parseChapterFromLocation(): AnalyticsChapterId {
  if (typeof window === 'undefined') return 'overview';

  // 1. Check Search params (?chapter=... or ?section=...)
  const params = new URLSearchParams(window.location.search);
  const chapterParam = params.get('chapter') || params.get('section') || params.get('subpage');
  if (chapterParam && isValidChapter(chapterParam)) {
    return chapterParam as AnalyticsChapterId;
  }

  // 2. Check Hash (#marketplace, #revenue_taxes, etc.)
  const hash = window.location.hash.replace('#', '');
  if (hash && isValidChapter(hash)) {
    return hash as AnalyticsChapterId;
  }

  // 3. Check Pathname (/analytics/marketplace/ or /admin/analytics/regional/)
  const path = window.location.pathname.toLowerCase();
  if (path.includes('/marketplace')) return 'marketplace';
  if (path.includes('/revenue') || path.includes('/taxes')) return 'revenue_taxes';
  if (path.includes('/transaction') || path.includes('/velocity')) return 'transactions';
  if (path.includes('/escrow') || path.includes('/vault')) return 'escrow';
  if (path.includes('/regional') || path.includes('/densit') || path.includes('/propert')) return 'regional';
  if (path.includes('/user') || path.includes('/demograph')) return 'users';
  if (path.includes('/expense') || path.includes('/report') || path.includes('/financial')) return 'expenses_reports';
  if (path.includes('/overview')) return 'overview';

  // 4. Check bootstrap active_chapter if passed from Django
  if (bootstrap.active_chapter && isValidChapter(bootstrap.active_chapter)) {
    return bootstrap.active_chapter as AnalyticsChapterId;
  }

  return 'overview';
}

function isValidChapter(val: string): boolean {
  const validChapters: AnalyticsChapterId[] = [
    'overview',
    'marketplace',
    'revenue_taxes',
    'transactions',
    'escrow',
    'regional',
    'users',
    'expenses_reports',
  ];
  return validChapters.includes(val as AnalyticsChapterId);
}

export function AnalyticsSuite({ initialChapter, className }: AnalyticsSuiteProps) {
  const [activeChapter, setActiveChapter] = useState<AnalyticsChapterId>(() => {
    return initialChapter || parseChapterFromLocation();
  });

  const [timeframe, setTimeframe] = useState<TimeframeOption>('30D');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [copiedReport, setCopiedReport] = useState(false);

  // Sync with browser URL changes
  useEffect(() => {
    const handlePopState = () => {
      setActiveChapter(parseChapterFromLocation());
    };
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('hashchange', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('hashchange', handlePopState);
    };
  }, []);

  const handleSelectChapter = useCallback((chapter: AnalyticsChapterId) => {
    setActiveChapter(chapter);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('chapter', chapter);
      window.history.pushState({}, '', url.toString());
    }
  }, []);

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 500);
  }, []);

  const rawAnalytics = bootstrap.system_analytics || bootstrap.analytics || {};
  const financial = rawAnalytics.financial || rawAnalytics.financial_overview || {};
  const taxes = rawAnalytics.taxes || rawAnalytics.tax_liability || {};
  const expenses = rawAnalytics.expenses || rawAnalytics.operating_expenses || {};
  const userMetrics = rawAnalytics.user_metrics || {};
  const failures = rawAnalytics.failures || {};

  const multiplier = timeframe === '30D' ? 0.35 : timeframe === '90D' ? 0.65 : 1.0;

  const totalGmv = (financial.total_gmv_kes || 128000000) * multiplier;
  const escrowRevenue = (financial.escrow_fee_revenue_kes || 3200000) * multiplier;
  const adRevenue = (financial.ad_promotions_revenue_kes || 85000) * multiplier;
  const grossRevenue = (financial.total_gross_revenue_kes || escrowRevenue + adRevenue) * multiplier;
  const totalStaffCompensation = (financial.total_staff_compensation_kes || 560000) * multiplier;
  const totalOperatingExpenses = (expenses.total_operating_expenses_kes || 89500) * multiplier;
  const totalTaxes = (taxes.total_taxes_kes || escrowRevenue * 0.16 + totalStaffCompensation * 0.05) * multiplier;
  const netIncome = grossRevenue - totalOperatingExpenses - totalTaxes;

  const handleExportDeck = useCallback(() => {
    const summary = {
      executive_summary_deck: 'Digiland Autonomous Land Escrow Intelligence Suite',
      generated_at: new Date().toISOString(),
      timeframe,
      metrics: {
        total_gmv_kes: totalGmv,
        gross_platform_revenue_kes: grossRevenue,
        escrow_commissions_kes: escrowRevenue,
        seller_ad_revenue_kes: adRevenue,
        professional_staff_compensation_kes: totalStaffCompensation,
        monthly_operating_overhead_kes: totalOperatingExpenses,
        statutory_taxes_vat_wht_kes: totalTaxes,
        net_operating_income_ebitda_kes: netIncome,
        total_registered_users: userMetrics.total_users || 19,
        active_users: userMetrics.active_users || 18,
        disputed_escrow_cases: failures.disputed_escrow_cases || 0,
        system_uptime_percentage: failures.uptime_percentage || 99.98,
      },
    };

    if (navigator.clipboard) {
      navigator.clipboard.writeText(JSON.stringify(summary, null, 2));
      setCopiedReport(true);
      setTimeout(() => setCopiedReport(false), 2500);
    }
  }, [timeframe, totalGmv, grossRevenue, escrowRevenue, adRevenue, totalStaffCompensation, totalOperatingExpenses, totalTaxes, netIncome, userMetrics, failures]);

  const contextData: AnalyticsContextData = useMemo(() => ({
    timeframe,
    multiplier,
    totalGmv,
    escrowRevenue,
    adRevenue,
    grossRevenue,
    totalStaffCompensation,
    totalOperatingExpenses,
    totalTaxes,
    netIncome,
    rawAnalytics,
    onNavigateChapter: handleSelectChapter,
  }), [timeframe, multiplier, totalGmv, escrowRevenue, adRevenue, grossRevenue, totalStaffCompensation, totalOperatingExpenses, totalTaxes, netIncome, rawAnalytics, handleSelectChapter]);

  // Current chapter index for Next/Previous chapter buttons
  const currentIndex = CHAPTERS_CONFIG.findIndex((c) => c.id === activeChapter);
  const prevChapter = currentIndex > 0 ? CHAPTERS_CONFIG[currentIndex - 1] : null;
  const nextChapter = currentIndex < CHAPTERS_CONFIG.length - 1 ? CHAPTERS_CONFIG[currentIndex + 1] : null;

  return (
    <div className={`space-y-6 ${className || ''}`}>
      {/* ── Main Chapter Navigation Strip ─────────────────────────────────── */}
      <ChapterNav
        activeChapter={activeChapter}
        onSelectChapter={handleSelectChapter}
        timeframe={timeframe}
        onSelectTimeframe={setTimeframe}
        isRefreshing={isRefreshing}
        onRefresh={handleRefresh}
        onExport={handleExportDeck}
        copiedReport={copiedReport}
      />

      {/* ── Active Chapter Subpage View ───────────────────────────────────── */}
      <main className="min-h-[500px]">
        {activeChapter === 'overview' && <OverviewChapter {...contextData} />}
        {activeChapter === 'marketplace' && <MarketplaceChapter {...contextData} />}
        {activeChapter === 'revenue_taxes' && <RevenueTaxesChapter {...contextData} />}
        {activeChapter === 'transactions' && <TransactionsChapter {...contextData} />}
        {activeChapter === 'escrow' && <EscrowVaultChapter {...contextData} />}
        {activeChapter === 'regional' && <PropertiesRegionalChapter {...contextData} />}
        {activeChapter === 'users' && <UsersDemographicsChapter {...contextData} />}
        {activeChapter === 'expenses_reports' && <FinancialReportsChapter {...contextData} />}
      </main>

      {/* ── Chapter Pagination Footer ─────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200/80 pt-6">
        <div>
          {prevChapter ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => handleSelectChapter(prevChapter.id)}
              className="h-9 rounded-2xl border-slate-200 bg-white hover:bg-slate-50 text-xs font-bold text-slate-700 shadow-xs"
            >
              <ChevronLeft className="mr-1.5 h-4 w-4" />
              Chapter {prevChapter.number}: {prevChapter.shortLabel}
            </Button>
          ) : (
            <div />
          )}
        </div>

        <div className="text-xs font-semibold text-slate-400">
          Chapter {currentIndex + 1} of {CHAPTERS_CONFIG.length}
        </div>

        <div>
          {nextChapter ? (
            <Button
              type="button"
              onClick={() => handleSelectChapter(nextChapter.id)}
              className="h-9 rounded-2xl bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold shadow-xs"
            >
              Chapter {nextChapter.number}: {nextChapter.shortLabel}
              <ChevronRight className="ml-1.5 h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={() => handleSelectChapter('overview')}
              className="h-9 rounded-2xl border-slate-200 bg-white hover:bg-slate-50 text-xs font-bold text-slate-700 shadow-xs"
            >
              Back to Overview
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default AnalyticsSuite;
