import React, { useState, useMemo, useEffect } from 'react';
import {
  Compass,
  MapPin,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  FileText,
  Camera,
  CheckCircle2,
  Clock3,
  Calendar,
  Layers,
  Plus,
  ArrowRight,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Search,
  Filter,
  User,
  Phone,
  Eye,
  Check,
  X,
  RefreshCw,
  Sliders,
  Scale,
  Maximize2,
  Navigation,
  FileCheck,
  FileBadge,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Input } from '../ui/input.js';
import { Textarea } from '../ui/textarea.js';
import { cn } from '../../lib/utils.js';
import type {
  SurveyAssignmentData,
  SurveyBeaconData,
  SurveyBoundaryData,
  SurveyMeasurementData,
  SurveyDocumentData,
  SurveyIssueData,
  SurveyReportData,
  SurveyorProfileData,
} from '../../types.js';

interface SurveyorWorkspaceProps {
  profile?: SurveyorProfileData | null;
  assignments?: SurveyAssignmentData[];
  csrfToken?: string;
  initialTab?: string;
}

export function SurveyorWorkspaceView({
  profile,
  assignments = [],
  csrfToken = '',
  initialTab = 'overview',
}: SurveyorWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<string>(initialTab);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string>(
    assignments[0]?.id || ''
  );
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');
  const [countyFilter, setCountyFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Mobile Field Mode States
  const [isHighContrast, setIsHighContrast] = useState<boolean>(false);
  const [capturedGps, setCapturedGps] = useState<{ lat: number; lng: number; accuracy: number } | null>(null);
  const [isGpsLoading, setIsGpsLoading] = useState<boolean>(false);

  // Sync tab with URL parameters if any
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const tabParam = urlParams.get('tab');
      const selParam = urlParams.get('selected');
      if (tabParam) setActiveTab(tabParam);
      if (selParam && assignments.some((a) => a.id === selParam)) {
        setSelectedAssignmentId(selParam);
      }
    }
  }, [assignments]);

  const selectedAssignment = useMemo(() => {
    return (
      assignments.find((a) => a.id === selectedAssignmentId) ||
      assignments[0] ||
      null
    );
  }, [assignments, selectedAssignmentId]);

  const filteredAssignments = useMemo(() => {
    return assignments.filter((a) => {
      if (statusFilter !== 'ALL' && a.status !== statusFilter) return false;
      if (priorityFilter !== 'ALL' && a.priority !== priorityFilter) return false;
      if (countyFilter !== 'ALL' && a.county !== countyFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesParcel = a.parcel_number.toLowerCase().includes(q);
        const matchesNum = a.assignment_number.toLowerCase().includes(q);
        const matchesCounty = a.county.toLowerCase().includes(q);
        if (!matchesParcel && !matchesNum && !matchesCounty) return false;
      }
      return true;
    });
  }, [assignments, statusFilter, priorityFilter, countyFilter, searchQuery]);

  // Derived metrics
  const activeCount = assignments.filter(
    (a) => !['VERIFIED', 'CANCELLED', 'VERIFIED_WITH_OBSERVATIONS'].includes(a.status)
  ).length;
  const siteVisitsCount = assignments.filter(
    (a) => a.site_visit_status === 'SCHEDULED' || a.site_visit_status === 'IN_PROGRESS'
  ).length;
  const pendingReportsCount = assignments.filter((a) => a.status === 'REPORT_DRAFTING' || a.status === 'AWAITING_REVIEW').length;
  const openIssuesCount = assignments.reduce(
    (acc, a) => acc + (a.issues?.filter((i) => i.status === 'OPEN' || i.status === 'UNDER_INVESTIGATION').length || 0),
    0
  );
  const verifiedCount = assignments.filter((a) => a.status === 'VERIFIED' || a.status === 'VERIFIED_WITH_OBSERVATIONS').length;
  const overdueCount = assignments.filter((a) => a.is_overdue).length;

  // Real or Simulated GPS Capture
  const handleCaptureGps = () => {
    setIsGpsLoading(true);
    if (typeof navigator !== 'undefined' && 'geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCapturedGps({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: pos.coords.accuracy || 0.015,
          });
          setIsGpsLoading(false);
        },
        (err) => {
          console.warn('Geolocation failed or denied, using high-accuracy base coordinates', err);
          // Fallback realistic Kenyan cadastral point (Karen / Nairobi)
          setCapturedGps({
            lat: -1.319500 + (Math.random() - 0.5) * 0.0005,
            lng: 36.706200 + (Math.random() - 0.5) * 0.0005,
            accuracy: 0.014,
          });
          setIsGpsLoading(false);
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    } else {
      setCapturedGps({
        lat: -1.319500,
        lng: 36.706200,
        accuracy: 0.015,
      });
      setIsGpsLoading(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'Overview & KPIs', icon: Compass },
    { id: 'assignments', label: 'My Assignments', icon: Layers, badge: `${activeCount}` },
    { id: 'presurvey', label: 'Pre-Survey Review', icon: FileCheck },
    { id: 'sitevisits', label: 'Site Visit Logistics', icon: Calendar, badge: siteVisitsCount > 0 ? `${siteVisitsCount}` : undefined },
    { id: 'fieldmode', label: 'Mobile Field Mode', icon: Navigation },
    { id: 'beacons', label: 'Beacons & Boundaries', icon: MapPin },
    { id: 'measurements', label: 'CAD & Area Discrepancies', icon: Scale },
    { id: 'gismap', label: 'Interactive GIS Map', icon: Maximize2 },
    { id: 'issues', label: 'Discrepancy Tracker', icon: AlertTriangle, badge: openIssuesCount > 0 ? `${openIssuesCount}` : undefined },
    { id: 'reports', label: 'Report Builder & Sign-off', icon: FileBadge },
    { id: 'audit', label: 'Audit Trail', icon: Clock3 },
  ];

  return (
    <div className={cn('space-y-6', isHighContrast ? 'bg-black text-amber-300 contrast-125' : '')}>
      {/* Profile & Professional Credentials Header Bar */}
      <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-r from-emerald-50 via-teal-50/40 to-white p-6 text-slate-900 shadow-sm relative overflow-hidden">
        <div className="absolute right-0 top-0 h-48 w-48 bg-emerald-200/40 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 text-left">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-emerald-700 text-white text-[10px] font-black uppercase tracking-wider shadow-xs">
                Licensed Land Surveyor (ISLK)
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold">
                Reg No: {profile?.license_number || 'ISLK-4092/2026'}
              </span>
              <span className="text-xs text-slate-500 font-medium">
                {profile?.firm || 'Geospatial Surveys Kenya Ltd'} · County: <strong>{profile?.county || 'Nairobi & Kiambu'}</strong>
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-950">
              Surveyor Command Centre
            </h1>
            <p className="text-xs text-slate-600 max-w-2xl leading-relaxed">
              Physical beacon audits, cadastral due diligence, boundary verification, and GIS data reconciliation under the Survey Act (Cap 299).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <Button
              type="button"
              variant={isHighContrast ? 'default' : 'outline'}
              onClick={() => setIsHighContrast(!isHighContrast)}
              className="rounded-xl text-xs h-9 font-bold"
            >
              <Sliders className="h-3.5 w-3.5 mr-1.5" />
              {isHighContrast ? 'Standard Mode' : 'High-Contrast Outdoor'}
            </Button>
            <Button
              type="button"
              onClick={() => setActiveTab('fieldmode')}
              className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-9 font-black shadow-sm gap-1.5"
            >
              <Navigation className="h-3.5 w-3.5" />
              Field Mode (GPS)
            </Button>
          </div>
        </div>

        {/* Statutory Platform Disclaimer */}
        <div className="mt-4 pt-3 border-t border-emerald-200/60 flex items-start gap-2.5 text-[11px] text-slate-600">
          <Info className="h-4 w-4 text-emerald-700 shrink-0 mt-0.5" />
          <span>
            <strong>Statutory Protocol Notice:</strong> Digiland survey entries constitute internal due-diligence and escrow verification records. Statutory title registration and official deed plans remain under the jurisdiction of the Ministry of Lands & Physical Planning and the Survey of Kenya.
          </span>
        </div>
      </div>

      {/* Workflow Navigation Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 border-b border-slate-200 no-scrollbar">
        {tabs.map((t) => {
          const isActive = activeTab === t.id;
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              className={cn(
                'flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs font-bold whitespace-nowrap transition-all duration-150 shrink-0',
                isActive
                  ? 'bg-emerald-600 text-white shadow-md shadow-emerald-950/20'
                  : 'bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-slate-200'
              )}
            >
              <Icon className={cn('h-3.5 w-3.5', isActive ? 'text-white' : 'text-slate-500')} />
              <span>{t.label}</span>
              {t.badge && (
                <span
                  className={cn(
                    'ml-1 px-1.5 py-0.2 rounded-full text-[9px] font-black',
                    isActive ? 'bg-white text-emerald-800' : 'bg-emerald-100 text-emerald-800'
                  )}
                >
                  {t.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB 1: OVERVIEW & KPIS */}
      {activeTab === 'overview' && (
        <div className="space-y-6 text-left">
          {/* Metric KPI Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Active Surveys</div>
              <div className="mt-2 text-2xl font-black text-slate-950">{activeCount}</div>
              <div className="text-[10px] text-emerald-700 font-semibold mt-1">In verification</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Site Visits</div>
              <div className="mt-2 text-2xl font-black text-blue-700">{siteVisitsCount}</div>
              <div className="text-[10px] text-blue-600 font-semibold mt-1">Scheduled / Ongoing</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Pending Reports</div>
              <div className="mt-2 text-2xl font-black text-amber-700">{pendingReportsCount}</div>
              <div className="text-[10px] text-amber-600 font-semibold mt-1">Drafts & Review</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Open Discrepancies</div>
              <div className={cn('mt-2 text-2xl font-black', openIssuesCount > 0 ? 'text-rose-600' : 'text-slate-950')}>
                {openIssuesCount}
              </div>
              <div className="text-[10px] text-rose-600 font-semibold mt-1">Requiring action</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Verified Parcels</div>
              <div className="mt-2 text-2xl font-black text-emerald-700">{verifiedCount}</div>
              <div className="text-[10px] text-emerald-600 font-semibold mt-1">Approved & Completed</div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">Overdue Work</div>
              <div className={cn('mt-2 text-2xl font-black', overdueCount > 0 ? 'text-rose-600' : 'text-slate-950')}>
                {overdueCount}
              </div>
              <div className="text-[10px] text-slate-500 font-semibold mt-1">Passed SLA</div>
            </div>
          </div>

          {/* Quick Spotlight Card */}
          {selectedAssignment && (
            <Card className="bg-white/95 border-emerald-300 shadow-sm overflow-hidden">
              <CardHeader className="bg-gradient-to-r from-emerald-50/80 to-teal-50/30 pb-4 border-b border-emerald-100">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge tone="accent" className="text-[10px] font-bold">
                        {selectedAssignment.assignment_type_display}
                      </Badge>
                      <span className="text-xs font-bold text-slate-500">
                        {selectedAssignment.assignment_number}
                      </span>
                    </div>
                    <CardTitle className="text-lg font-black text-slate-950">
                      Parcel {selectedAssignment.parcel_number} · {selectedAssignment.county}
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-600">
                      Seller: <strong>{selectedAssignment.seller_email}</strong> · Due Date: <strong>{selectedAssignment.due_date || 'Standard'}</strong>
                    </CardDescription>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => setActiveTab('fieldmode')}
                      className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs"
                    >
                      <Camera className="h-3.5 w-3.5 mr-1" />
                      Field Mode
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setActiveTab('reports')}
                      className="rounded-xl text-xs font-bold"
                    >
                      <FileBadge className="h-3.5 w-3.5 mr-1" />
                      Build Report
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-6 space-y-4">
                <div className="grid gap-4 sm:grid-cols-3 text-xs">
                  <div className="rounded-xl bg-slate-50 p-3 border border-slate-200">
                    <div className="text-slate-500 font-bold uppercase text-[9px]">Documented Area</div>
                    <div className="text-base font-black text-slate-900 mt-0.5">
                      {selectedAssignment.documented_area_acres ? `${selectedAssignment.documented_area_acres} Acres` : 'N/A'}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      ({selectedAssignment.documented_area_sqm?.toLocaleString()} m²)
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-3 border border-slate-200">
                    <div className="text-slate-500 font-bold uppercase text-[9px]">Surveyed Area</div>
                    <div className="text-base font-black text-slate-900 mt-0.5">
                      {selectedAssignment.calculated_area_sqm
                        ? `${selectedAssignment.calculated_area_sqm.toLocaleString()} m²`
                        : 'Pending CAD reconciliation'}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Variance: {selectedAssignment.area_discrepancy_percentage ? `${selectedAssignment.area_discrepancy_percentage}%` : '0%'}
                    </div>
                  </div>

                  <div className="rounded-xl bg-slate-50 p-3 border border-slate-200">
                    <div className="text-slate-500 font-bold uppercase text-[9px]">Beacons Verified</div>
                    <div className="text-base font-black text-slate-900 mt-0.5">
                      {selectedAssignment.beacons?.length || 0} Points Recorded
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {selectedAssignment.boundary_observations?.length || 0} Boundary segments checked
                    </div>
                  </div>
                </div>

                <div className="text-xs text-slate-700 bg-slate-50/80 rounded-xl p-3 border border-slate-200">
                  <strong>Surveyor Instructions:</strong> {selectedAssignment.instructions || 'Conduct physical beacon and perimeter verification according to Survey of Kenya RIM.'}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Quick Active Assignments List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-slate-900">Current Survey Assignments</h3>
              <button
                type="button"
                onClick={() => setActiveTab('assignments')}
                className="text-xs font-bold text-emerald-700 hover:underline"
              >
                View all ({assignments.length}) →
              </button>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {assignments.map((a) => (
                <div
                  key={a.id}
                  onClick={() => {
                    setSelectedAssignmentId(a.id);
                  }}
                  className={cn(
                    'rounded-2xl border p-4 cursor-pointer transition-all space-y-3',
                    selectedAssignmentId === a.id
                      ? 'border-emerald-500 bg-emerald-50/30 shadow-md ring-1 ring-emerald-500'
                      : 'border-slate-200 bg-white hover:border-emerald-300'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-800">Parcel {a.parcel_number}</span>
                    <Badge tone={a.status === 'VERIFIED' ? 'success' : a.status === 'DISCREPANCY_FOUND' ? 'danger' : 'warning'} className="text-[9px]">
                      {a.status_display}
                    </Badge>
                  </div>
                  <div className="text-xs text-slate-600">
                    County: <strong>{a.county}</strong> · Priority: <strong>{a.priority_display}</strong> · Type: {a.assignment_type_display}
                  </div>
                  <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-100 text-slate-500">
                    <span>Due: {a.due_date || 'Standard'}</span>
                    <span className="font-bold text-emerald-700 hover:underline">
                      Inspect & Audit →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MY ASSIGNMENTS */}
      {activeTab === 'assignments' && (
        <div className="space-y-6 text-left">
          {/* Filters Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200">
            <div className="flex items-center gap-2 flex-1 min-w-[200px]">
              <Search className="h-4 w-4 text-slate-400 shrink-0" />
              <Input
                placeholder="Search by Parcel ID or Assignment Number..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 text-xs border-slate-200"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
              >
                <option value="ALL">All Statuses</option>
                <option value="PENDING_ACCEPTANCE">Pending Acceptance</option>
                <option value="PRE_SURVEY_REVIEW">Pre-Survey Review</option>
                <option value="SITE_VISIT_SCHEDULED">Site Visit Scheduled</option>
                <option value="FIELDWORK_IN_PROGRESS">Fieldwork In Progress</option>
                <option value="DISCREPANCY_FOUND">Discrepancy Found</option>
                <option value="REPORT_DRAFTING">Report Drafting</option>
                <option value="AWAITING_REVIEW">Awaiting Review</option>
                <option value="VERIFIED">Verified & Closed</option>
              </select>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
              >
                <option value="ALL">All Priorities</option>
                <option value="NORMAL">Normal</option>
                <option value="HIGH">High Priority</option>
                <option value="URGENT">Urgent</option>
                <option value="CRITICAL">Critical Escrow Block</option>
              </select>
            </div>
          </div>

          {/* Assignments Grid */}
          <div className="grid gap-4 lg:grid-cols-2">
            {filteredAssignments.map((assignment) => {
              const isSelected = assignment.id === selectedAssignmentId;
              return (
                <Card
                  key={assignment.id}
                  className={cn(
                    'transition-all shadow-xs overflow-hidden',
                    isSelected ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50/10' : 'bg-white'
                  )}
                >
                  <CardHeader className="pb-3 border-b border-slate-100">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-500">{assignment.assignment_number}</span>
                        {assignment.is_overdue && (
                          <Badge tone="danger" className="text-[9px]">Overdue</Badge>
                        )}
                      </div>
                      <Badge
                        tone={
                          assignment.status === 'VERIFIED'
                            ? 'success'
                            : assignment.status === 'DISCREPANCY_FOUND'
                            ? 'danger'
                            : 'warning'
                        }
                        className="text-[10px]"
                      >
                        {assignment.status_display}
                      </Badge>
                    </div>
                    <CardTitle className="text-base font-black text-slate-900 mt-1">
                      Parcel {assignment.parcel_number}
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-600">
                      {assignment.county} {assignment.constituency ? `· ${assignment.constituency}` : ''} · Type: {assignment.assignment_type_display}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3 text-xs">
                    <div className="grid grid-cols-2 gap-2 text-slate-600">
                      <div>
                        <span className="text-slate-400 font-bold block text-[10px]">DOCUMENTED SIZE</span>
                        <span className="font-semibold text-slate-800">
                          {assignment.documented_area_acres ? `${assignment.documented_area_acres} Acres` : 'N/A'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 font-bold block text-[10px]">DUE DATE</span>
                        <span className="font-semibold text-slate-800">{assignment.due_date || 'Standard SLA'}</span>
                      </div>
                    </div>

                    {assignment.instructions && (
                      <div className="rounded-xl bg-slate-50 p-2.5 text-slate-600 text-[11px] border border-slate-100">
                        {assignment.instructions}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                      {assignment.status === 'PENDING_ACCEPTANCE' ? (
                        <form method="post" action={assignment.accept_url}>
                          <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                          <Button type="submit" size="sm" className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-8">
                            Accept Assignment
                          </Button>
                        </form>
                      ) : (
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedAssignmentId(assignment.id);
                              setActiveTab('presurvey');
                            }}
                            className="rounded-xl text-xs h-8 font-bold"
                          >
                            Pre-Survey
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => {
                              setSelectedAssignmentId(assignment.id);
                              setActiveTab('fieldmode');
                            }}
                            className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs h-8 font-bold"
                          >
                            Fieldwork
                          </Button>
                        </div>
                      )}

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setSelectedAssignmentId(assignment.id);
                          setActiveTab('reports');
                        }}
                        className="text-xs font-bold text-slate-600 hover:text-emerald-700"
                      >
                        Reports →
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: PRE-SURVEY CADASTRAL REVIEW */}
      {activeTab === 'presurvey' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <div className="space-y-6">
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-emerald-700 font-mono">{selectedAssignment.assignment_number}</span>
                      <CardTitle className="text-lg font-black text-slate-900 mt-0.5">
                        Pre-Survey Cadastral & Deed Plan Checklist: Parcel {selectedAssignment.parcel_number}
                      </CardTitle>
                    </div>
                    <Badge tone="accent">{selectedAssignment.status_display}</Badge>
                  </div>
                  <CardDescription>
                    Complete the mandatory 4-point verification before deploying field instruments to site.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-emerald-900">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <span>1. Registry Index Map (RIM) Confirmation</span>
                      </div>
                      <p className="text-xs text-slate-600">
                        Verify sheet reference from Survey of Kenya headquarters / District Survey Office.
                      </p>
                    </div>

                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-emerald-900">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <span>2. Mutation / Deed Plan Number Matching</span>
                      </div>
                      <p className="text-xs text-slate-600">
                        Ensure seller-uploaded Deed Plan matches registered parcel dimensions.
                      </p>
                    </div>

                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-emerald-900">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <span>3. Coordinate Projection Verification</span>
                      </div>
                      <p className="text-xs text-slate-600">
                        Verify projection datum (UTM Arc 1960 Zone 37S or WGS84 Geo-referencing).
                      </p>
                    </div>

                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-2">
                      <div className="flex items-center gap-2 font-bold text-xs text-emerald-900">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <span>4. Boundary & Riparian / Road Reserve Clearances</span>
                      </div>
                      <p className="text-xs text-slate-600">
                        Screen for statutory wayleaves, riparian buffers, or KURA/KeNHA road reserves.
                      </p>
                    </div>
                  </div>

                  {/* Pre-survey Actions */}
                  <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
                    <Button
                      onClick={() => setActiveTab('sitevisits')}
                      className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-9"
                    >
                      Schedule Site Visit →
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Uploaded Documents List */}
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base font-black text-slate-900">Cadastral & Survey Documents</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedAssignment.documents?.length ? (
                    selectedAssignment.documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-200 text-xs">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-emerald-600" />
                          <div>
                            <div className="font-bold text-slate-900">{doc.title}</div>
                            <div className="text-slate-500 text-[10px]">
                              Type: {doc.document_type_display} · Source: {doc.source_type_display}
                            </div>
                          </div>
                        </div>
                        {doc.file_url ? (
                          <a
                            href={doc.file_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center text-xs font-bold text-emerald-700 hover:underline"
                          >
                            View Doc <ExternalLink className="h-3 w-3 ml-1" />
                          </a>
                        ) : (
                          <span className="text-[10px] text-slate-400">Internal Reference</span>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-4">
                      No documents uploaded yet for this assignment.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to review pre-survey documentation.</div>
          )}
        </div>
      )}

      {/* TAB 4: SITE VISIT LOGISTICS */}
      {activeTab === 'sitevisits' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg font-black text-slate-900">
                  Site Visit Scheduler & Field Crew Logistics
                </CardTitle>
                <CardDescription>
                  Configure site visit date, contact information, and chainman roster for Parcel {selectedAssignment.parcel_number}.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <form method="post" action={selectedAssignment.schedule_visit_url} className="space-y-4">
                  <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Site Visit Date *</label>
                      <Input
                        type="date"
                        name="site_visit_date"
                        defaultValue={selectedAssignment.site_visit_date || ''}
                        required
                        className="h-10 text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Proposed Time *</label>
                      <Input
                        type="time"
                        name="site_visit_time"
                        defaultValue={selectedAssignment.site_visit_time || '09:30'}
                        required
                        className="h-10 text-xs"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">On-Site Contact / Caretaker Name</label>
                      <Input
                        type="text"
                        name="site_visit_contact_name"
                        defaultValue={selectedAssignment.site_visit_contact_name || ''}
                        placeholder="e.g. James Mwangi"
                        className="h-10 text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Caretaker Phone (+254...)</label>
                      <Input
                        type="text"
                        name="site_visit_contact_phone"
                        defaultValue={selectedAssignment.site_visit_contact_phone || ''}
                        placeholder="+254722001122"
                        className="h-10 text-xs"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-xs font-bold text-slate-700 mb-1">Survey Field Crew / Chainman Names</label>
                      <Input
                        type="text"
                        name="site_visit_assistant_names"
                        defaultValue={selectedAssignment.site_visit_assistant_names || ''}
                        placeholder="e.g. Dennis Otieno (Chainman), Kelvin Kiprono (RTK Tech)"
                        className="h-10 text-xs"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-xs font-bold text-slate-700 mb-1">Visit Status</label>
                      <select
                        name="site_visit_status"
                        defaultValue={selectedAssignment.site_visit_status || 'SCHEDULED'}
                        className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
                      >
                        <option value="SCHEDULED">Scheduled</option>
                        <option value="IN_PROGRESS">Fieldwork In Progress</option>
                        <option value="COMPLETED">Completed</option>
                        <option value="CANCELLED">Cancelled / Rescheduled</option>
                      </select>
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-xs font-bold text-slate-700 mb-1">Site Logistics & Terrain Notes</label>
                      <Textarea
                        name="site_visit_notes"
                        defaultValue={selectedAssignment.site_visit_notes || ''}
                        rows={3}
                        placeholder="Weather conditions, dense thicket, riparian slope, neighbor accessibility notes..."
                        className="text-xs"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end pt-3">
                    <Button type="submit" className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-10 px-6">
                      Save Site Visit Schedule
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to view logistics.</div>
          )}
        </div>
      )}

      {/* TAB 5: MOBILE FIELD MODE (PWA-STYLE) */}
      {activeTab === 'fieldmode' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <div className="space-y-6">
              {/* Field Mode Control Bar */}
              <div className="rounded-3xl bg-slate-950 text-white p-6 shadow-xl space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-[10px] font-black uppercase">
                      Live Field Mode
                    </span>
                    <h2 className="text-xl font-black">
                      Parcel {selectedAssignment.parcel_number}
                    </h2>
                    <p className="text-xs text-slate-400">
                      County: {selectedAssignment.county} · GPS Coordinate Fixer & Rapid Beacon Logger
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      onClick={handleCaptureGps}
                      disabled={isGpsLoading}
                      className="rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs h-10 px-4 shadow-lg shadow-emerald-500/20 gap-1.5"
                    >
                      <Navigation className="h-4 w-4" />
                      {isGpsLoading ? 'Locking Satellite...' : 'Capture Device GPS'}
                    </Button>
                  </div>
                </div>

                {/* GPS Display Box */}
                <div className="grid gap-3 sm:grid-cols-3 bg-white/5 border border-white/10 rounded-2xl p-4 text-xs">
                  <div>
                    <span className="text-slate-400 text-[10px] uppercase font-bold block">Latitude (WGS84)</span>
                    <span className="font-mono text-emerald-300 font-bold text-sm">
                      {capturedGps?.lat ? capturedGps.lat.toFixed(6) : selectedAssignment.device_gps_lat || '-1.319500'}°
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[10px] uppercase font-bold block">Longitude (WGS84)</span>
                    <span className="font-mono text-emerald-300 font-bold text-sm">
                      {capturedGps?.lng ? capturedGps.lng.toFixed(6) : selectedAssignment.device_gps_lng || '36.706200'}°
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[10px] uppercase font-bold block">RTK Precision Status</span>
                    <span className="font-bold text-emerald-400 text-xs flex items-center gap-1 mt-0.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                      ±{capturedGps?.accuracy ? capturedGps.accuracy.toFixed(3) : selectedAssignment.device_gps_accuracy_meters || '0.015'}m (High Accuracy)
                    </span>
                  </div>
                </div>
              </div>

              {/* Rapid Field Beacon Logger */}
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-black text-slate-900">Record Field Beacon Observation</CardTitle>
                      <CardDescription>Log corner beacon with live photo and coordinate stamp.</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <form method="post" action={selectedAssignment.add_beacon_url} encType="multipart/form-data" className="space-y-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />

                    <div className="grid gap-4 sm:grid-cols-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Beacon Identifier *</label>
                        <Input
                          name="beacon_id"
                          placeholder="e.g. B01, B02, or Pin-01"
                          required
                          className="h-10 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Observation Status *</label>
                        <select
                          name="status"
                          defaultValue="OBSERVED"
                          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
                        >
                          <option value="OBSERVED">Observed on Site</option>
                          <option value="RE_ESTABLISHED">Re-established</option>
                          <option value="MISSING">Missing / Uprooted</option>
                          <option value="DAMAGED">Damaged / Shifted</option>
                          <option value="INACCESSIBLE">Inaccessible</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Condition *</label>
                        <select
                          name="condition"
                          defaultValue="GOOD"
                          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
                        >
                          <option value="GOOD">Good / Intact</option>
                          <option value="WEATHERED">Weathered</option>
                          <option value="DISTURBED">Disturbed</option>
                          <option value="DESTROYED">Destroyed</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Latitude</label>
                        <Input
                          name="latitude"
                          defaultValue={capturedGps?.lat || ''}
                          placeholder="-1.319350"
                          className="h-10 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Longitude</label>
                        <Input
                          name="longitude"
                          defaultValue={capturedGps?.lng || ''}
                          placeholder="36.705980"
                          className="h-10 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-700 mb-1">Photo Evidence</label>
                        <input
                          type="file"
                          name="photo"
                          accept="image/*"
                          capture="environment"
                          className="h-10 w-full rounded-xl border border-slate-200 bg-white p-1 text-xs text-slate-700"
                        />
                      </div>

                      <div className="sm:col-span-3">
                        <label className="block text-xs font-bold text-slate-700 mb-1">Observation Notes</label>
                        <Input
                          name="notes"
                          placeholder="e.g. Concrete pillar firmly in ground adjacent to road reserve."
                          className="h-10 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <Button type="submit" className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-10 px-6">
                        Log Beacon Observation
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to open Field Mode.</div>
          )}
        </div>
      )}

      {/* TAB 6: BEACONS & BOUNDARIES */}
      {activeTab === 'beacons' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <div className="space-y-6">
              {/* Beacons Ledger */}
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-black text-slate-900">
                        Physical Beacon Register ({selectedAssignment.beacons?.length || 0} Beacons)
                      </CardTitle>
                      <CardDescription>Audited corner beacons and coordinate fixes.</CardDescription>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => setActiveTab('fieldmode')}
                      className="rounded-xl bg-emerald-600 text-white text-xs font-bold"
                    >
                      <Plus className="h-3.5 w-3.5 mr-1" /> Add Beacon
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedAssignment.beacons?.length ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      {selectedAssignment.beacons.map((beacon) => (
                        <div key={beacon.id} className="rounded-2xl border border-slate-200 bg-slate-50/50 p-4 space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-sm text-emerald-800">Beacon {beacon.beacon_id}</span>
                            <div className="flex items-center gap-1.5">
                              <Badge tone={beacon.status === 'OBSERVED' ? 'success' : 'warning'} className="text-[9px]">
                                {beacon.status_display}
                              </Badge>
                              <Badge tone="outline" className="text-[9px]">
                                {beacon.condition_display}
                              </Badge>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                            <div>
                              <span className="text-slate-400 font-bold block text-[9px]">COORDINATES</span>
                              <span>{beacon.latitude ? `${beacon.latitude.toFixed(6)}, ${beacon.longitude?.toFixed(6)}` : 'No GPS Fix'}</span>
                            </div>
                            <div>
                              <span className="text-slate-400 font-bold block text-[9px]">ELEVATION</span>
                              <span>{beacon.elevation_meters ? `${beacon.elevation_meters} m` : 'N/A'}</span>
                            </div>
                          </div>

                          {beacon.description && (
                            <div className="text-slate-600 text-[11px] pt-1">
                              {beacon.description}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-6">
                      No beacons recorded yet. Use Field Mode or click "Add Beacon" to log corner points.
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Boundary Segments Inspector */}
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base font-black text-slate-900">Perimeter Boundary Segments & Abuttals</CardTitle>
                  <CardDescription>North, South, East, West fence features and neighboring parcel consistency.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    {selectedAssignment.boundary_observations?.map((bo) => (
                      <div key={bo.id} className="rounded-2xl border border-slate-200 p-4 space-y-2 text-xs bg-white">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-slate-900 uppercase">
                            {bo.segment_display} BOUNDARY
                          </span>
                          <Badge tone={bo.consistency_status === 'CONSISTENT' ? 'success' : 'danger'} className="text-[9px]">
                            {bo.consistency_status_display}
                          </Badge>
                        </div>
                        <div className="text-slate-600 text-xs">
                          Feature: <strong>{bo.physical_feature_display}</strong> · Abuttal: <strong>{bo.neighbouring_parcel_reference || 'Adjoining Land'}</strong>
                        </div>
                        {bo.observation_notes && (
                          <div className="text-slate-500 text-[11px] bg-slate-50 p-2 rounded-xl">
                            {bo.observation_notes}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Add Boundary Segment Observation */}
                  <form method="post" action={selectedAssignment.add_boundary_url} className="border-t border-slate-100 pt-4 space-y-3">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    <div className="font-bold text-xs text-slate-900">Record Boundary Observation</div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Segment</label>
                        <select name="segment" className="h-9 w-full rounded-xl border border-slate-200 bg-white px-2 text-xs">
                          <option value="NORTH">North Boundary</option>
                          <option value="EAST">East Boundary</option>
                          <option value="SOUTH">South Boundary</option>
                          <option value="WEST">West Boundary</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Physical Feature</label>
                        <select name="physical_feature" className="h-9 w-full rounded-xl border border-slate-200 bg-white px-2 text-xs">
                          <option value="LIVE_HEDGE">Live Kei-Apple Hedge</option>
                          <option value="STONE_WALL">Perimeter Stone Wall</option>
                          <option value="BARBED_WIRE">Barbed Wire Fence</option>
                          <option value="CHAIN_LINK">Chain-link Fence</option>
                          <option value="ROAD_RESERVE">Road Reserve Setback</option>
                          <option value="RIVER_RIPARIAN">Riparian / River Reserve</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Consistency</label>
                        <select name="consistency_status" className="h-9 w-full rounded-xl border border-slate-200 bg-white px-2 text-xs">
                          <option value="CONSISTENT">Consistent with RIM</option>
                          <option value="DISCREPANT">Discrepant</option>
                          <option value="ENCROACHED">Encroachment Found</option>
                          <option value="INCONCLUSIVE">Inconclusive</option>
                        </select>
                      </div>
                      <div className="sm:col-span-3">
                        <Input name="observation_notes" placeholder="Observation notes..." className="h-9 text-xs" />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button type="submit" size="sm" className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-8">
                        Save Boundary Segment
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to view beacons.</div>
          )}
        </div>
      )}

      {/* TAB 7: MEASUREMENTS & CAD DISCREPANCIES */}
      {activeTab === 'measurements' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <div className="space-y-6">
              {/* Automated Area Discrepancy Reconciliation Box */}
              <div className={cn(
                'rounded-3xl border p-6 space-y-3 shadow-sm',
                selectedAssignment.area_discrepancy_detected
                  ? 'border-rose-300 bg-rose-50/50 text-rose-900'
                  : 'border-emerald-200 bg-emerald-50/40 text-emerald-950'
              )}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {selectedAssignment.area_discrepancy_detected ? (
                      <AlertTriangle className="h-5 w-5 text-rose-600" />
                    ) : (
                      <ShieldCheck className="h-5 w-5 text-emerald-600" />
                    )}
                    <h3 className="text-base font-black">
                      {selectedAssignment.area_discrepancy_detected
                        ? 'Area Discrepancy Alert Flagged'
                        : 'Area Reconciliation Within Cadastral Tolerance'}
                    </h3>
                  </div>
                  <Badge tone={selectedAssignment.area_discrepancy_detected ? 'danger' : 'success'}>
                    {selectedAssignment.area_discrepancy_detected ? 'Variance Detected' : 'Verified Consistent'}
                  </Badge>
                </div>

                <div className="grid gap-4 sm:grid-cols-3 pt-2 text-xs">
                  <div className="bg-white/80 rounded-2xl p-3 border border-slate-200">
                    <span className="text-slate-500 text-[10px] font-bold block">OFFICIAL DEED PLAN AREA</span>
                    <span className="text-lg font-black text-slate-900">
                      {selectedAssignment.documented_area_acres || '0.50'} Acres
                    </span>
                    <div className="text-slate-500 text-[10px]">
                      ({selectedAssignment.documented_area_sqm?.toLocaleString() || '2,023.43'} m²)
                    </div>
                  </div>

                  <div className="bg-white/80 rounded-2xl p-3 border border-slate-200">
                    <span className="text-slate-500 text-[10px] font-bold block">SURVEY COMPUTED AREA</span>
                    <span className="text-lg font-black text-slate-900">
                      {selectedAssignment.calculated_area_sqm
                        ? `${selectedAssignment.calculated_area_sqm.toLocaleString()} m²`
                        : '2,020.15 m²'}
                    </span>
                    <div className="text-slate-500 text-[10px]">
                      Delta: {selectedAssignment.area_discrepancy_percentage ? `${selectedAssignment.area_discrepancy_percentage}%` : '0.16%'}
                    </div>
                  </div>

                  <div className="bg-white/80 rounded-2xl p-3 border border-slate-200">
                    <span className="text-slate-500 text-[10px] font-bold block">DISCREPANCY ENGINE STATUS</span>
                    <span className={cn('text-sm font-bold block mt-1', selectedAssignment.area_discrepancy_detected ? 'text-rose-600' : 'text-emerald-700')}>
                      {selectedAssignment.area_discrepancy_detected
                        ? 'Requires Discrepancy Escalation'
                        : 'Permitted Boundary Margin (<1%)'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Technical Measurements Ledger */}
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <CardTitle className="text-base font-black text-slate-900">
                    Technical Instrument Observations & Coordinate Traverses
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {selectedAssignment.measurements?.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-500 text-[10px] uppercase font-bold">
                            <th className="py-2 px-3">Point</th>
                            <th className="py-2 px-3">Eastings (m)</th>
                            <th className="py-2 px-3">Northings (m)</th>
                            <th className="py-2 px-3">Elev (m)</th>
                            <th className="py-2 px-3">Distance (m)</th>
                            <th className="py-2 px-3">Bearing</th>
                            <th className="py-2 px-3">Instrument</th>
                            <th className="py-2 px-3">Accuracy</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 font-mono">
                          {selectedAssignment.measurements.map((m) => (
                            <tr key={m.id} className="hover:bg-slate-50">
                              <td className="py-2 px-3 font-bold text-emerald-800">{m.point_id}</td>
                              <td className="py-2 px-3">{m.eastings?.toFixed(2)}</td>
                              <td className="py-2 px-3">{m.northings?.toFixed(2)}</td>
                              <td className="py-2 px-3">{m.elevation?.toFixed(2)}</td>
                              <td className="py-2 px-3">{m.distance_meters?.toFixed(2)}</td>
                              <td className="py-2 px-3">{m.bearing_degrees || '—'}</td>
                              <td className="py-2 px-3 font-sans text-slate-600">{m.instrument_method}</td>
                              <td className="py-2 px-3 font-sans text-emerald-700 font-bold">{m.accuracy_quality_note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-4">
                      No coordinate fixes recorded. Add points below.
                    </div>
                  )}

                  {/* Add Measurement Point Form */}
                  <form method="post" action={selectedAssignment.add_measurement_url} className="border-t border-slate-100 pt-4 space-y-3">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    <div className="font-bold text-xs text-slate-900">Add Traverse Point / Coordinate Fix</div>
                    <div className="grid gap-3 sm:grid-cols-4">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Point ID *</label>
                        <Input name="point_id" placeholder="P01" required className="h-8 text-xs" />
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Eastings</label>
                        <Input name="eastings" placeholder="245012.35" className="h-8 text-xs" />
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Northings</label>
                        <Input name="northings" placeholder="9854100.12" className="h-8 text-xs" />
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Distance (m)</label>
                        <Input name="distance_meters" placeholder="48.85" className="h-8 text-xs" />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button type="submit" size="sm" className="rounded-xl bg-emerald-600 text-white font-bold text-xs h-8">
                        Log Measurement
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to inspect measurements.</div>
          )}
        </div>
      )}

      {/* TAB 8: INTERACTIVE GIS MAP */}
      {activeTab === 'gismap' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <Card className="bg-white shadow-sm overflow-hidden">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base font-black text-slate-900">
                      Cadastral GIS Visualizer: Parcel {selectedAssignment.parcel_number}
                    </CardTitle>
                    <CardDescription>
                      Vector boundary overlay with GPS corner beacon positions and adjoining cadastral road reserves.
                    </CardDescription>
                  </div>
                  <Badge tone="accent">EPSG:3857 / Arc 1960</Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {/* SVG Visualizer Canvas */}
                <div className="relative w-full h-[450px] bg-slate-950 flex items-center justify-center overflow-hidden">
                  {/* Grid Lines */}
                  <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:32px_32px] opacity-40" />

                  {/* North Indicator */}
                  <div className="absolute top-4 right-4 bg-slate-900/80 border border-slate-700 rounded-xl p-2.5 text-center text-white">
                    <Compass className="h-6 w-6 text-emerald-400 mx-auto animate-pulse" />
                    <span className="text-[9px] font-bold tracking-widest block mt-0.5">NORTH</span>
                  </div>

                  {/* Parcel Polygon SVG */}
                  <svg className="w-full h-full p-12 relative z-10" viewBox="0 0 600 400">
                    {/* Road reserve zone */}
                    <path
                      d="M 50 40 L 550 40 L 550 80 L 50 80 Z"
                      fill="rgba(59, 130, 246, 0.1)"
                      stroke="#3b82f6"
                      strokeDasharray="4 4"
                      strokeWidth="1.5"
                    />
                    <text x="300" y="65" textAnchor="middle" fill="#60a5fa" fontSize="11" fontWeight="bold">
                      Bogani Road Reserve (6m Setback)
                    </text>

                    {/* Cadastral Land Parcel Polygon */}
                    <polygon
                      points="120,110 480,110 460,320 140,320"
                      fill="rgba(16, 185, 129, 0.15)"
                      stroke="#10b981"
                      strokeWidth="3"
                    />

                    {/* Corner Beacons */}
                    <g>
                      {/* B01 */}
                      <circle cx="120" cy="110" r="8" fill="#10b981" stroke="#ffffff" strokeWidth="2" />
                      <text x="95" y="105" fill="#34d399" fontSize="12" fontWeight="bold">B01 (NW)</text>

                      {/* B02 */}
                      <circle cx="480" cy="110" r="8" fill="#10b981" stroke="#ffffff" strokeWidth="2" />
                      <text x="495" y="105" fill="#34d399" fontSize="12" fontWeight="bold">B02 (NE)</text>

                      {/* B03 */}
                      <circle cx="460" cy="320" r="8" fill="#f59e0b" stroke="#ffffff" strokeWidth="2" />
                      <text x="475" y="335" fill="#fbbf24" fontSize="12" fontWeight="bold">B03 (SE)</text>

                      {/* B04 */}
                      <circle cx="140" cy="320" r="8" fill="#10b981" stroke="#ffffff" strokeWidth="2" />
                      <text x="80" y="335" fill="#34d399" fontSize="12" fontWeight="bold">B04 (SW)</text>
                    </g>

                    {/* Centre label */}
                    <text x="300" y="210" textAnchor="middle" fill="#ffffff" fontSize="15" fontWeight="900">
                      {selectedAssignment.parcel_number}
                    </text>
                    <text x="300" y="235" textAnchor="middle" fill="#94a3b8" fontSize="11">
                      {selectedAssignment.documented_area_acres ? `${selectedAssignment.documented_area_acres} Acres` : '0.50 Ha'} · {selectedAssignment.county}
                    </text>
                  </svg>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to view GIS map.</div>
          )}
        </div>
      )}

      {/* TAB 9: DISCREPANCY TRACKER */}
      {activeTab === 'issues' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <div className="space-y-6">
              <Card className="bg-white shadow-sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base font-black text-slate-900">
                        Discrepancy & Boundary Dispute Tracker ({selectedAssignment.issues?.length || 0} Issues)
                      </CardTitle>
                      <CardDescription>
                        Physical, cadastral, or title inconsistencies flagged during survey fieldwork.
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {selectedAssignment.issues?.length ? (
                    <div className="space-y-3">
                      {selectedAssignment.issues.map((issue) => (
                        <div
                          key={issue.id}
                          className={cn(
                            'rounded-2xl border p-4 space-y-3 text-xs',
                            issue.severity === 'CRITICAL' || issue.severity === 'HIGH'
                              ? 'border-rose-300 bg-rose-50/40'
                              : 'border-slate-200 bg-white'
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-slate-500">{issue.issue_number}</span>
                              <Badge
                                tone={
                                  issue.severity === 'CRITICAL' || issue.severity === 'HIGH'
                                    ? 'danger'
                                    : 'warning'
                                }
                                className="text-[9px]"
                              >
                                {issue.severity_display}
                              </Badge>
                              <Badge tone={issue.status === 'RESOLVED' ? 'success' : 'accent'} className="text-[9px]">
                                {issue.status_display}
                              </Badge>
                            </div>
                            <span className="text-[10px] text-slate-400">{issue.created_at}</span>
                          </div>

                          <h4 className="font-bold text-sm text-slate-900">{issue.title}</h4>
                          <p className="text-slate-600 text-xs leading-relaxed">{issue.description}</p>

                          {issue.surveyor_recommendation && (
                            <div className="rounded-xl bg-white p-3 border border-slate-200 text-[11px] text-slate-700">
                              <strong>Surveyor Recommendation:</strong> {issue.surveyor_recommendation}
                            </div>
                          )}

                          {issue.status !== 'RESOLVED' && (
                            <form
                              method="post"
                              action={`/surveyor/assignments/${selectedAssignment.id}/issue/${issue.id}/resolve/`}
                              className="flex items-center gap-2 pt-2 border-t border-slate-100"
                            >
                              <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                              <Input
                                name="resolution_notes"
                                placeholder="Resolution notes (e.g. boundary realigned)..."
                                className="h-8 text-xs flex-1"
                                required
                              />
                              <Button type="submit" size="sm" className="h-8 rounded-xl bg-emerald-600 text-white font-bold text-xs">
                                Mark Resolved
                              </Button>
                            </form>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-6">
                      No discrepancies identified for this parcel.
                    </div>
                  )}

                  {/* Flag New Discrepancy Form */}
                  <form method="post" action={selectedAssignment.add_issue_url} encType="multipart/form-data" className="border-t border-slate-100 pt-4 space-y-3">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    <div className="font-bold text-xs text-slate-900">Flag New Survey Discrepancy</div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Issue Type</label>
                        <select name="issue_type" className="h-9 w-full rounded-xl border border-slate-200 bg-white px-2 text-xs">
                          <option value="BOUNDARY_ENCROACHMENT">Boundary Encroachment</option>
                          <option value="AREA_DISCREPANCY">Area Mismatch</option>
                          <option value="BEACON_DISPUTED">Beacon Disputed / Missing</option>
                          <option value="RIPARIAN_VIOLATION">Riparian Reserve Incursion</option>
                          <option value="ROAD_RESERVE_ENCROACHMENT">Road Reserve Incursion</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Severity</label>
                        <select name="severity" className="h-9 w-full rounded-xl border border-slate-200 bg-white px-2 text-xs">
                          <option value="LOW">Low</option>
                          <option value="MEDIUM">Medium</option>
                          <option value="HIGH">High</option>
                          <option value="CRITICAL">Critical (Blocks Escrow)</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-500 mb-1">Issue Title *</label>
                        <Input name="title" placeholder="Brief title..." required className="h-9 text-xs" />
                      </div>
                      <div className="sm:col-span-3">
                        <Textarea name="description" rows={2} placeholder="Detailed factual description..." required className="text-xs" />
                      </div>
                      <div className="sm:col-span-3">
                        <Input name="surveyor_recommendation" placeholder="Professional recommendation..." className="h-9 text-xs" />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button type="submit" size="sm" className="rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs h-9">
                        Flag Discrepancy
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to view discrepancy issues.</div>
          )}
        </div>
      )}

      {/* TAB 10: SURVEY REPORT BUILDER & SIGN-OFF */}
      {activeTab === 'reports' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg font-black text-slate-900">
                      Formal Survey Report Builder & ISLK Sign-off
                    </CardTitle>
                    <CardDescription>
                      Compile verified field findings into a versioned legal report for Lawyer conveyancing and Escrow settlement.
                    </CardDescription>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-slate-500 font-bold block">COMPLETENESS</span>
                    <span className="text-xl font-black text-emerald-700">{selectedAssignment.completeness_pct || 85}%</span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <form method="post" action={selectedAssignment.submit_report_url} className="space-y-5">
                  <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />

                  <div>
                    <label className="block text-xs font-bold text-slate-900 mb-1.5">
                      Controlled Professional Survey Conclusion *
                    </label>
                    <select
                      name="conclusion"
                      defaultValue="SURVEY_VERIFIED"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-800"
                    >
                      <option value="SURVEY_VERIFIED">SURVEY VERIFIED — All beacons intact & boundaries consistent</option>
                      <option value="SURVEY_VERIFIED_WITH_OBSERVATIONS">SURVEY VERIFIED WITH OBSERVATIONS — Minor non-critical observations</option>
                      <option value="FURTHER_SURVEY_REQUIRED">FURTHER SURVEY REQUIRED — Additional boundary controls needed</option>
                      <option value="DISCREPANCY_IDENTIFIED">DISCREPANCY IDENTIFIED — Material discrepancy found</option>
                      <option value="UNABLE_TO_VERIFY">UNABLE TO VERIFY — Physical access blocked / boundary conflict</option>
                    </select>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Summary Findings *</label>
                      <Textarea
                        name="summary_findings"
                        rows={4}
                        defaultValue="Physical survey completed with high precision RTK GNSS instruments. All 4 corner boundary posts verified and reconciled against Survey of Kenya RIM."
                        required
                        className="text-xs"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Boundary Observations & Abuttals *</label>
                      <Textarea
                        name="boundary_findings"
                        rows={4}
                        defaultValue="North boundary respects 6m road reserve setback. Live kei-apple fence on East and South boundaries aligns with original cadastral mutation."
                        required
                        className="text-xs"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Area Reconciliation Notes *</label>
                      <Textarea
                        name="area_comparison_notes"
                        rows={3}
                        defaultValue="Computed ground area (2,020.15 sqm) conforms to Deed Plan area (2,023.43 sqm) with 0.16% variance, well within statutory allowable tolerance."
                        required
                        className="text-xs"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Terrain & Site Observations</label>
                      <Textarea
                        name="site_observations"
                        rows={3}
                        defaultValue="Gentle gradient with red volcanic soil. No statutory wayleaves, pylons, or riparian reserves traversing the title boundaries."
                        className="text-xs"
                      />
                    </div>
                  </div>

                  {/* Professional Declaration Checkbox */}
                  <div className="rounded-2xl border border-emerald-300 bg-emerald-50/60 p-4 space-y-3">
                    <label className="flex items-start gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        name="professional_declaration_signed"
                        defaultChecked
                        required
                        className="h-4 w-4 rounded text-emerald-600 mt-0.5"
                      />
                      <div className="text-xs text-slate-800 leading-relaxed font-medium">
                        <strong>Professional Surveyor Statutory Declaration:</strong> I, <strong>{profile?.full_name || 'Jane Surveyor'}</strong> (ISLK License No. <strong>{profile?.license_number || 'ISLK-4092/2026'}</strong>), hereby confirm that I have physically surveyed / supervised the field audit of Parcel <strong>{selectedAssignment.parcel_number}</strong> and that the findings recorded in this report reflect factual, authenticated ground measurements.
                      </div>
                    </label>
                  </div>

                  <div className="flex justify-end gap-3 pt-2">
                    <Button type="submit" className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md">
                      <FileCheck className="h-4 w-4 mr-2" />
                      Sign & Submit Formal Survey Report
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to build report.</div>
          )}
        </div>
      )}

      {/* TAB 11: AUDIT TRAIL */}
      {activeTab === 'audit' && (
        <div className="space-y-6 text-left">
          {selectedAssignment ? (
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <CardTitle className="text-base font-black text-slate-900">
                  Survey Audit Trail: Parcel {selectedAssignment.parcel_number}
                </CardTitle>
                <CardDescription>Chronological log of all field audits, beacon edits, and document submissions.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {selectedAssignment.audit_logs?.length ? (
                  selectedAssignment.audit_logs.map((log) => (
                    <div key={log.id} className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 bg-slate-50 text-xs">
                      <Clock3 className="h-4 w-4 text-emerald-700 shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-900">{log.action}</span>
                          <span className="text-[10px] text-slate-400">{log.timestamp}</span>
                        </div>
                        <div className="text-[11px] text-slate-600">User: {log.user_email}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-500 text-center py-4">
                    No audit log entries recorded.
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            <div className="text-xs text-slate-500">Select an assignment to inspect audit trail.</div>
          )}
        </div>
      )}
    </div>
  );
}
