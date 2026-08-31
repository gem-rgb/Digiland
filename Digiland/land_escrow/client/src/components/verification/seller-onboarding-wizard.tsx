import React, { useState, useEffect, useMemo } from 'react';
import {
  Compass,
  FileText,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  MapPin,
  Upload,
  Search,
  ArrowRight,
  ArrowLeft,
  Info,
  Check,
  X,
  FileBadge,
  Sparkles,
  Building,
  User,
  Scale,
  Clock,
  Layers,
  Lock,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Input } from '../ui/input.js';
import { Textarea } from '../ui/textarea.js';
import { cn } from '../../lib/utils.js';

interface SellerOnboardingWizardProps {
  userProfile?: {
    email?: string;
    first_name?: string;
    last_name?: string;
    national_id?: string;
    kra_pin?: string;
    phone_number?: string;
  } | null;
  csrfToken?: string;
  initialCaseId?: string;
  onComplete?: (caseData: any) => void;
}

export function SellerOnboardingWizard({
  userProfile,
  csrfToken = '',
  initialCaseId,
  onComplete,
}: SellerOnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [caseId, setCaseId] = useState<string | null>(initialCaseId || null);
  const [caseNumber, setCaseNumber] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Step 1: Property Basics
  const [propertyType, setPropertyType] = useState<string>('LAND_PLOT');
  const [tenureType, setTenureType] = useState<string>('FREEHOLD');
  const [parcelNumber, setParcelNumber] = useState<string>('');
  const [county, setCounty] = useState<string>('Nairobi');
  const [subCounty, setSubCounty] = useState<string>('Westlands');
  const [locality, setLocality] = useState<string>('Karen');
  const [landSize, setLandSize] = useState<string>('0.75');
  const [sizeUnit, setSizeUnit] = useState<string>('ACRES');
  const [intendedUse, setIntendedUse] = useState<string>('RESIDENTIAL');
  const [ownershipType, setOwnershipType] = useState<string>('INDIVIDUAL');
  const [sellerRelationship, setSellerRelationship] = useState<string>('REGISTERED_OWNER');
  const [locationSearch, setLocationSearch] = useState<string>('');
  const [pinnedCoordinates, setPinnedCoordinates] = useState<{ lat: number; lng: number } | null>({
    lat: -1.3195,
    lng: 36.7062,
  });

  // Step 2: Property Details & Cross-Consistency Inputs
  const [registeredOwnerName, setRegisteredOwnerName] = useState<string>(
    userProfile ? `${userProfile.first_name || ''} ${userProfile.last_name || ''}`.trim() : ''
  );
  const [registeredAcreage, setRegisteredAcreage] = useState<string>('0.75');
  const [titleType, setTitleType] = useState<string>('TITLE_DEED');
  const [isSubdivided, setIsSubdivided] = useState<string>('NO');
  const [hasSpousalInterest, setHasSpousalInterest] = useState<string>('NO');
  const [hasRecentTransfer, setHasRecentTransfer] = useState<string>('NO');

  // Step 3 & 4: Documents & AI Screening State
  const [uploadedDocuments, setUploadedDocuments] = useState<Record<string, any>>({});
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);

  // Step 5: Final Submission Confirmation
  const [declarationSigned, setDeclarationSigned] = useState<boolean>(false);
  const [isFinalSubmitted, setIsFinalSubmitted] = useState<boolean>(false);

  // Normalized area conversion
  const normalizedAcres = useMemo(() => {
    const val = parseFloat(landSize) || 0;
    if (sizeUnit === 'HECTARES') return val * 2.47105;
    if (sizeUnit === 'SQ_METRES') return val / 4046.86;
    if (sizeUnit === 'SQ_FEET') return val / 43560;
    return val;
  }, [landSize, sizeUnit]);

  // Dynamic Document Checklist Calculation
  const documentChecklist = useMemo(() => {
    const list = [
      {
        type: 'TITLE_DEED',
        name: 'Current Title Deed / Certificate of Lease',
        description: 'Upload your current registered ownership title document or lease certificate.',
        required: true,
        hint: 'Original Title Deed or Certificate of Lease (PDF / Image)',
      },
      {
        type: 'OFFICIAL_SEARCH',
        name: 'Official Land Search Certificate',
        description: 'Recent official land search certificate issued by Ministry of Lands (Ardhisasa).',
        required: true,
        hint: 'Official Search Certificate (issued within last 6 months)',
      },
      {
        type: 'SELLER_ID',
        name: 'Seller National ID / Passport',
        description: 'Scanned front & back of National ID or bio-page of Passport.',
        required: true,
        hint: 'National ID or Passport (PDF / Image)',
      },
    ];

    // Tenure conditional: Leasehold requires Land Rent Clearance
    if (tenureType === 'LEASEHOLD') {
      list.push({
        type: 'LAND_RENT_CLEARANCE',
        name: 'Land Rent Clearance Certificate',
        description: 'Valid clearance certificate showing up-to-date Ministry land rent payments.',
        required: true,
        hint: 'National Government Land Rent Clearance',
      });
    }

    // Rates clearance (applicable for urban/county properties)
    list.push({
      type: 'LAND_RATES_CLEARANCE',
      name: 'County Land Rates Clearance Certificate',
      description: 'County government receipt or certificate confirming zero land rate arrears.',
      required: false,
      hint: 'County Rates Clearance (or select Not Available to request internal check)',
    });

    // Agricultural classification triggers Land Control Board Consent
    if (propertyType === 'AGRICULTURAL' || intendedUse === 'AGRICULTURAL') {
      list.push({
        type: 'LCB_CONSENT',
        name: 'Land Control Board (LCB) Consent',
        description: 'Mandatory Land Control Board consent for agricultural land transactions under Cap 302.',
        required: true,
        hint: 'LCB Consent to Sell / Transfer',
      });
    }

    // Spousal interest conditional
    if (hasSpousalInterest === 'YES') {
      list.push({
        type: 'SPOUSAL_CONSENT',
        name: 'Spousal Consent Affidavit',
        description: 'Sworn affidavit of spousal consent under the Matrimonial Property Act.',
        required: true,
        hint: 'Notarized Spousal Consent Affidavit & Spouse ID',
      });
    }

    // Subdivision conditional
    if (isSubdivided === 'YES') {
      list.push({
        type: 'SURVEY_PLAN',
        name: 'Survey Plan / Mutation Document',
        description: 'Approved mutation form, subdivision scheme plan, or RIM extract.',
        required: true,
        hint: 'Survey Plan or Certified Mutation Sheet',
      });
    }

    // Company ownership conditional
    if (ownershipType === 'COMPANY') {
      list.push({
        type: 'COMPANY_CERTIFICATE',
        name: 'Certificate of Incorporation / CR12 Form',
        description: 'Company registration certificate, CR12 official list of directors, and KRA PIN.',
        required: true,
        hint: 'Certificate of Incorporation & Official CR12',
      });
      list.push({
        type: 'BOARD_RESOLUTION',
        name: 'Board Resolution to Sell Property',
        description: 'Signed board resolution authorizing sale of company property.',
        required: true,
        hint: 'Board Resolution & Authorized Representative ID',
      });
    }

    // Estate ownership conditional
    if (ownershipType === 'ESTATE') {
      list.push({
        type: 'GRANT_PROBATE',
        name: 'Grant of Probate / Letters of Administration',
        description: 'High Court Grant of Probate or Letters of Administration confirming legal authority.',
        required: true,
        hint: 'Court Certified Grant of Probate / Confirmation of Grant',
      });
    }

    return list;
  }, [propertyType, tenureType, ownershipType, intendedUse, isSubdivided, hasSpousalInterest]);

  // Helper to safely retrieve CSRF token from prop, cookie, or meta tag
  const getActiveCsrfToken = (): string => {
    if (csrfToken && csrfToken.trim()) return csrfToken;
    if (typeof document !== 'undefined') {
      const cookieMatch = document.cookie.match(/csrftoken=([^;]+)/);
      if (cookieMatch) return cookieMatch[1];
      const meta = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement | null;
      if (meta?.content) return meta.content;
      const input = document.querySelector('input[name="csrfmiddlewaretoken"]') as HTMLInputElement | null;
      if (input?.value) return input.value;
    }
    return '';
  };

  // Helper to safely fetch and parse JSON without crashing on HTML responses
  const safeFetch = async (url: string, options: RequestInit): Promise<any> => {
    const activeToken = getActiveCsrfToken();
    const headers = new Headers(options.headers || {});
    if (activeToken && !headers.has('X-CSRFToken')) {
      headers.set('X-CSRFToken', activeToken);
    }

    const response = await fetch(url, { ...options, headers });
    const contentType = response.headers.get('content-type') || '';
    let resData: any = null;

    if (contentType.includes('application/json')) {
      try {
        resData = await response.json();
      } catch {
        resData = null;
      }
    } else {
      const text = await response.text();
      if (text.includes('<!DOCTYPE') || text.includes('<html')) {
        if (response.status === 403) {
          throw new Error('Security session expired. Please refresh the page and try again.');
        }
        throw new Error(`Server returned error (${response.status}). Please verify your input and try again.`);
      }
      resData = { error: text };
    }

    if (!response.ok) {
      const msg = resData?.error || resData?.detail || resData?.message || `Request failed with status ${response.status}`;
      throw new Error(msg);
    }

    return resData;
  };

  // Handle Step 1 Save & Create Case
  const handleStep1Submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!parcelNumber.trim()) {
      setErrorMessage('Parcel / LR Number is required.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resData = await safeFetch('/api/verification/wizard/save-step/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          step: 1,
          case_id: caseId,
          parcel_number: parcelNumber,
          property_type: propertyType,
          tenure_type: tenureType,
          county,
          constituency: subCounty,
          ward: locality,
          land_size: landSize,
          size_unit: sizeUnit,
          intended_use: intendedUse,
          ownership_type: ownershipType,
          seller_relationship: sellerRelationship,
          location_description: `${locality}, ${subCounty}, ${county}`,
          latitude: pinnedCoordinates?.lat,
          longitude: pinnedCoordinates?.lng,
        }),
      });

      if (resData.case) {
        setCaseId(resData.case.id);
        setCaseNumber(resData.case.case_number);
      }
      setCurrentStep(2);
    } catch (err: any) {
      setErrorMessage(err.message || 'An error occurred saving property basics.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Step 2 Save
  const handleStep2Submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) {
      setErrorMessage('Case session invalid. Please return to Step 1.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await safeFetch(`/api/verification/wizard/${caseId}/step/2/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          registered_owner_name: registeredOwnerName,
          registered_area: registeredAcreage,
          registered_area_unit: 'ACRES',
          title_type: titleType,
          is_subdivided: isSubdivided === 'YES',
          has_spousal_interest: hasSpousalInterest,
          has_recent_transfer: hasRecentTransfer,
          ownership_type: ownershipType,
        }),
      });

      setCurrentStep(3);
    } catch (err: any) {
      setErrorMessage(err.message || 'An error occurred saving property details.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Document Upload
  const handleFileUpload = async (docType: string, file: File) => {
    if (!caseId) return;

    setUploadingDocType(docType);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', docType);

    try {
      const resData = await safeFetch(`/api/verification/wizard/${caseId}/upload-document/`, {
        method: 'POST',
        body: formData,
      });

      setUploadedDocuments((prev) => ({
        ...prev,
        [docType]: {
          doc: resData.document,
          screening: resData.screening,
        },
      }));
    } catch (err: any) {
      setErrorMessage(err.message || 'File upload failed.');
    } finally {
      setUploadingDocType(null);
    }
  };

  // Handle Final Submission
  const handleFinalSubmit = async () => {
    if (!caseId) return;
    if (!declarationSigned) {
      setErrorMessage('You must confirm the statutory accuracy declaration before submitting.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const resData = await safeFetch(`/api/verification/wizard/${caseId}/step/5/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          confirmed: true,
        }),
      });

      setIsFinalSubmitted(true);
      if (onComplete) onComplete(resData.case);
    } catch (err: any) {
      setErrorMessage(err.message || 'Error completing final verification submission.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const requiredUploadedCount = documentChecklist
    .filter((d) => d.required)
    .filter((d) => uploadedDocuments[d.type]).length;
  const totalRequiredCount = documentChecklist.filter((d) => d.required).length;

  return (
    <div className="max-w-4xl mx-auto space-y-6 text-left p-4 sm:p-6">
      {/* Wizard Top Header */}
      <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-r from-emerald-950 via-slate-900 to-slate-950 p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 h-48 w-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-black uppercase tracking-wider">
              Digiland Verification Engine
            </span>
            {caseNumber && (
              <span className="px-2.5 py-0.5 rounded-full bg-white/10 text-slate-300 font-mono text-[10px] font-bold">
                Case No: {caseNumber}
              </span>
            )}
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            Guided Property Onboarding & Verification Intake
          </h1>
          <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
            Digiland treats every property listing as a structured due-diligence case. Provide basic information and existing document evidence — our AI screening engine and licensed professionals verify the rest.
          </p>

          {/* 5-Step Progress Indicators */}
          <div className="grid grid-cols-5 gap-2 pt-4 border-t border-white/10 text-[11px] font-bold">
            {[
              { num: 1, label: '1. Property Basics' },
              { num: 2, label: '2. Property Details' },
              { num: 3, label: '3. Documents' },
              { num: 4, label: '4. AI Screening' },
              { num: 5, label: '5. Review & Submit' },
            ].map((step) => {
              const isActive = currentStep === step.num;
              const isDone = currentStep > step.num;
              return (
                <div
                  key={step.num}
                  className={cn(
                    'flex flex-col items-center py-2 rounded-xl text-center transition-all',
                    isActive
                      ? 'bg-emerald-500 text-slate-950 font-black shadow-lg shadow-emerald-500/20'
                      : isDone
                      ? 'bg-white/10 text-emerald-400'
                      : 'bg-white/5 text-slate-500'
                  )}
                >
                  <span className="text-[10px] font-black">{step.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Error Alert Box */}
      {errorMessage && (
        <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 text-rose-800 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-900">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* STEP 1: PROPERTY BASICS */}
      {currentStep === 1 && (
        <Card className="bg-white shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle className="text-lg font-black text-slate-950">Tell Us About Your Property</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Start by giving us basic property details. We will use this information to determine the documents and verification checks required for your parcel.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form onSubmit={handleStep1Submit} className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Property Type *</label>
                  <select
                    value={propertyType}
                    onChange={(e) => setPropertyType(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="LAND_PLOT">Land / Plot</option>
                    <option value="AGRICULTURAL">Agricultural Land</option>
                    <option value="RESIDENTIAL">Residential Property</option>
                    <option value="COMMERCIAL">Commercial Property</option>
                    <option value="DEVELOPMENT">Development Land</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Ownership / Tenure *</label>
                  <select
                    value={tenureType}
                    onChange={(e) => setTenureType(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="FREEHOLD">Freehold</option>
                    <option value="LEASEHOLD">Leasehold</option>
                    <option value="UNKNOWN">Not Sure (Internal Review Will Determine)</option>
                  </select>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-bold text-slate-800 mb-1">Parcel / LR Number *</label>
                  <Input
                    value={parcelNumber}
                    onChange={(e) => setParcelNumber(e.target.value)}
                    placeholder="e.g. LR No. 209/14000 or Kiambu/Block 12/402"
                    required
                    className="h-10 text-xs"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Enter the parcel or land reference number exactly as it appears on your title deed or official land document.
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">County *</label>
                  <Input
                    value={county}
                    onChange={(e) => setCounty(e.target.value)}
                    placeholder="e.g. Nairobi, Kiambu, Machakos"
                    required
                    className="h-10 text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Sub-county / Constituency</label>
                  <Input
                    value={subCounty}
                    onChange={(e) => setSubCounty(e.target.value)}
                    placeholder="e.g. Westlands, Dagoretti, Ruiru"
                    className="h-10 text-xs"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-bold text-slate-800 mb-1">Locality / Neighborhood</label>
                  <Input
                    value={locality}
                    onChange={(e) => setLocality(e.target.value)}
                    placeholder="e.g. Karen, Ruiru, Kitengela, Naivasha"
                    className="h-10 text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Land Size *</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={landSize}
                    onChange={(e) => setLandSize(e.target.value)}
                    required
                    className="h-10 text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Size Unit *</label>
                  <select
                    value={sizeUnit}
                    onChange={(e) => setSizeUnit(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="ACRES">Acres</option>
                    <option value="HECTARES">Hectares</option>
                    <option value="SQ_METRES">Square Metres</option>
                    <option value="SQ_FEET">Square Feet</option>
                  </select>
                </div>
              </div>

              {/* Normalized Area Conversion Box */}
              <div className="rounded-2xl bg-slate-50 border border-slate-200 p-3 text-xs flex items-center justify-between text-slate-700">
                <span className="font-semibold">Normalized System Calculation:</span>
                <span className="font-mono font-bold text-emerald-800 text-sm">
                  {normalizedAcres.toFixed(4)} Acres ({ (normalizedAcres * 4046.86).toLocaleString() } m²)
                </span>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Intended Use *</label>
                  <select
                    value={intendedUse}
                    onChange={(e) => setIntendedUse(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="RESIDENTIAL">Residential</option>
                    <option value="AGRICULTURAL">Agricultural</option>
                    <option value="COMMERCIAL">Commercial</option>
                    <option value="MIXED_USE">Mixed Use</option>
                    <option value="DEVELOPMENT">Development</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Who Owns This Property? *</label>
                  <select
                    value={ownershipType}
                    onChange={(e) => setOwnershipType(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="INDIVIDUAL">Individual Owner</option>
                    <option value="JOINT">Joint Ownership</option>
                    <option value="COMPANY">Company / Organization</option>
                    <option value="ESTATE">Estate / Deceased Owner</option>
                    <option value="TRUST">Trust / Other Legal Entity</option>
                    <option value="UNKNOWN">Not Sure</option>
                  </select>
                </div>
              </div>

              {/* Approximate Location Notice */}
              <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 space-y-2 text-xs text-amber-900">
                <div className="flex items-center gap-2 font-bold">
                  <MapPin className="h-4 w-4 text-amber-700" />
                  <span>Approximate Property Location</span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Seller-provided GPS coordinates are stored as approximate location points for buyer discovery. Official cadastral boundary lines are verified independently on-site by licensed ISLK Land Surveyors.
                </p>
              </div>

              <div className="flex justify-end pt-4">
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md gap-2"
                >
                  {isSubmitting ? 'Saving Property Basics...' : 'Continue to Property Details →'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* STEP 2: PROPERTY DETAILS & PROGRESSIVE DISCLOSURE */}
      {currentStep === 2 && (
        <Card className="bg-white shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle className="text-lg font-black text-slate-950">Ownership & Title Details</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Provide registered ownership information. This enables automated cross-document consistency checks against uploaded titles and official searches.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form onSubmit={handleStep2Submit} className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className="block text-xs font-bold text-slate-800 mb-1">Registered Owner Name (as shown on Title) *</label>
                  <Input
                    value={registeredOwnerName}
                    onChange={(e) => setRegisteredOwnerName(e.target.value)}
                    placeholder="e.g. John Kamau Mwangi or Maina Enterprises Ltd"
                    required
                    className="h-10 text-xs"
                  />
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Enter the exact full name of the registered owner as printed on the official title deed.
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Registered Land Size (Shown on Title)</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={registeredAcreage}
                    onChange={(e) => setRegisteredAcreage(e.target.value)}
                    placeholder="0.75"
                    className="h-10 text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Title Instrument Type *</label>
                  <select
                    value={titleType}
                    onChange={(e) => setTitleType(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="TITLE_DEED">Title Deed</option>
                    <option value="CERTIFICATE_OF_LEASE">Certificate of Lease</option>
                    <option value="OTHER">Other Ownership Document</option>
                    <option value="UNKNOWN">Not Sure</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Is the Property Part of a Subdivision? *</label>
                  <select
                    value={isSubdivided}
                    onChange={(e) => setIsSubdivided(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="NO">No (Original Parcel / Block)</option>
                    <option value="YES">Yes (Subdivided Plot)</option>
                    <option value="UNSURE">Not Sure</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1">Spousal or Matrimonial Interest? *</label>
                  <select
                    value={hasSpousalInterest}
                    onChange={(e) => setHasSpousalInterest(e.target.value)}
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-800 font-medium"
                  >
                    <option value="NO">No</option>
                    <option value="YES">Yes</option>
                    <option value="UNSURE">Not Sure (Requires Legal Review)</option>
                  </select>
                </div>
              </div>

              {/* Professional Survey Responsibility Callout */}
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-1.5 text-xs text-emerald-950">
                <div className="flex items-center gap-2 font-bold">
                  <ShieldCheck className="h-4 w-4 text-emerald-700" />
                  <span>No Survey Computation Required from Seller</span>
                </div>
                <p className="text-[11px] text-emerald-800 leading-relaxed">
                  Digiland does <strong>not</strong> require sellers to calculate or provide technical survey data (Eastings, Northings, Bearings, Beacon Coordinates, Traverse computations). Our licensed ISLK Land Surveyor extracts and verifies technical data from your uploaded survey plans.
                </p>
              </div>

              <div className="flex justify-between pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setCurrentStep(1)}
                  className="rounded-xl text-xs h-11 px-6 font-bold"
                >
                  ← Back to Property Basics
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md gap-2"
                >
                  {isSubmitting ? 'Saving Property Details...' : 'Continue to Required Documents →'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* STEP 3: REQUIRED DOCUMENTS INTAKE CARDS */}
      {currentStep === 3 && (
        <Card className="bg-white shadow-sm border-slate-200">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-lg font-black text-slate-950">Property Document Evidence Intake</CardTitle>
                <CardDescription className="text-xs text-slate-600">
                  Upload existing property documents. Requirements are dynamically tailored based on your property tenure, ownership structure, and agricultural status.
                </CardDescription>
              </div>

              <div className="bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-2xl text-center shrink-0">
                <span className="text-[10px] font-bold text-emerald-800 uppercase block">Required Checklist</span>
                <span className="text-base font-black text-emerald-950">
                  {requiredUploadedCount} / {totalRequiredCount} Received
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Dynamic Document Cards List */}
            <div className="grid gap-4 md:grid-cols-2">
              {documentChecklist.map((item) => {
                const uploaded = uploadedDocuments[item.type];
                const isUploading = uploadingDocType === item.type;

                return (
                  <div
                    key={item.type}
                    className={cn(
                      'rounded-2xl border p-4 space-y-3 transition-all text-xs bg-white',
                      uploaded
                        ? 'border-emerald-300 ring-1 ring-emerald-500/20 bg-emerald-50/20'
                        : item.required
                        ? 'border-slate-300'
                        : 'border-slate-200 bg-slate-50/40'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-950">{item.name}</span>
                          <Badge tone={item.required ? 'accent' : 'outline'} className="text-[9px]">
                            {item.required ? 'Required' : 'Conditional'}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-relaxed">{item.description}</p>
                      </div>

                      {uploaded && (
                        <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                      )}
                    </div>

                    {/* File Upload Control / Card Status */}
                    {uploaded ? (
                      <div className="rounded-xl bg-white p-3 border border-emerald-200 space-y-2">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-mono font-bold text-slate-800 truncate max-w-[180px]">
                            {uploaded.doc?.original_filename}
                          </span>
                          <Badge tone={uploaded.doc?.ai_status === 'PASSED' ? 'success' : 'warning'} className="text-[9px]">
                            {uploaded.doc?.ai_status === 'PASSED' ? '✓ AI Screened' : '⚠ Requires Review'}
                          </Badge>
                        </div>

                        {uploaded.screening?.confidence_score && (
                          <div className="text-[10px] text-slate-600 flex items-center justify-between border-t border-slate-100 pt-1.5">
                            <span>AI Confidence Score: <strong>{uploaded.screening.confidence_score}%</strong></span>
                            <span className="text-emerald-700 font-bold">No obvious anomalies</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <label className="cursor-pointer block">
                          <div className="rounded-xl border border-dashed border-slate-300 hover:border-emerald-500 bg-slate-50 hover:bg-emerald-50/50 p-3 text-center transition-all">
                            <Upload className="h-4 w-4 text-slate-400 mx-auto mb-1" />
                            <span className="text-xs font-bold text-slate-700 block">
                              {isUploading ? 'Screening Document...' : 'Choose File to Upload'}
                            </span>
                            <span className="text-[10px] text-slate-400 block">{item.hint}</span>
                          </div>
                          <input
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png"
                            disabled={isUploading}
                            onChange={(e) => {
                              const f = e.target.files?.[0];
                              if (f) handleFileUpload(item.type, f);
                            }}
                            className="hidden"
                          />
                        </label>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex justify-between pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentStep(2)}
                className="rounded-xl text-xs h-11 px-6 font-bold"
              >
                ← Back to Details
              </Button>

              <Button
                type="button"
                onClick={() => setCurrentStep(4)}
                disabled={requiredUploadedCount < totalRequiredCount}
                className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md gap-2"
              >
                Continue to AI Screening →
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 4: AI SCREENING & CONSISTENCY SUMMARY */}
      {currentStep === 4 && (
        <Card className="bg-white shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle className="text-lg font-black text-slate-950">AI Document Screening & Cross-Consistency Results</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Automated OCR field extraction, SHA-256 duplicate fingerprinting, and consistency checks across your submitted evidence.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Disclaimer Alert */}
            <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4 text-xs text-blue-900 space-y-1.5">
              <div className="flex items-center gap-2 font-bold">
                <Info className="h-4 w-4 text-blue-700 shrink-0" />
                <span>AI Screening Disclaimer & Review Principle</span>
              </div>
              <p className="text-[11px] text-blue-800 leading-relaxed">
                AI screening evaluates consistency, extracts text fields, and flags duplicate or missing information. A high AI score means <strong>"AI found no obvious document anomalies"</strong> — it is NOT a legal title certification. Final verification is conducted by Digiland's licensed professionals.
              </p>
            </div>

            {/* Uploaded Documents AI Breakdown */}
            <div className="space-y-3">
              {Object.entries(uploadedDocuments).map(([docType, data]) => {
                const doc = data.doc;
                const screening = data.screening;

                return (
                  <div key={docType} className="rounded-2xl border border-slate-200 p-4 space-y-3 text-xs bg-slate-50/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-emerald-700" />
                        <span className="font-bold text-slate-900">{doc.original_filename}</span>
                      </div>
                      <Badge tone={doc.ai_confidence >= 80 ? 'success' : 'warning'} className="text-[10px]">
                        Confidence: {doc.ai_confidence ? `${doc.ai_confidence}%` : 'Screened'}
                      </Badge>
                    </div>

                    {screening?.consistency_checks?.length ? (
                      <div className="grid gap-2 sm:grid-cols-2 pt-2 border-t border-slate-200/60">
                        {screening.consistency_checks.map((chk: any, idx: number) => (
                          <div key={idx} className="bg-white p-2.5 rounded-xl border border-slate-200 flex items-center justify-between">
                            <span className="font-semibold text-slate-700 text-[11px]">{chk.check_name}</span>
                            <span className={cn('font-bold text-[10px]', chk.status === 'PASS' ? 'text-emerald-700' : 'text-amber-700')}>
                              {chk.status === 'PASS' ? '✓ Passed' : '⚠ Review'}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>

            <div className="flex justify-between pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentStep(3)}
                className="rounded-xl text-xs h-11 px-6 font-bold"
              >
                ← Back to Documents
              </Button>
              <Button
                type="button"
                onClick={() => setCurrentStep(5)}
                className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md gap-2"
              >
                Proceed to Review & Submit →
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* STEP 5: FINAL SUBMISSION REVIEW & STATUTORY CONFIRMATION */}
      {currentStep === 5 && (
        <Card className="bg-white shadow-sm border-slate-200">
          <CardHeader>
            <CardTitle className="text-lg font-black text-slate-950">Review & Submit Property Case</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Review your property details and document evidence before submitting for Digiland Phase 1 pre-screening.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Case Passport Preview */}
            <div className="rounded-2xl bg-slate-950 text-white p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div>
                  <span className="text-[10px] text-slate-400 font-bold block uppercase">VERIFICATION PASSPORT</span>
                  <span className="font-mono text-emerald-400 font-bold text-sm">{caseNumber || 'DL-VER-2026-004821'}</span>
                </div>
                <Badge tone="accent">Phase 1 Pre-Screening</Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 text-xs">
                <div>
                  <span className="text-slate-400 text-[10px] block font-bold">PARCEL NUMBER</span>
                  <span className="font-bold text-white text-sm">{parcelNumber}</span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block font-bold">LOCATION</span>
                  <span className="font-bold text-white text-sm">{locality}, {county}</span>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] block font-bold">REGISTERED OWNER</span>
                  <span className="font-bold text-white text-sm">{registeredOwnerName || 'Seller'}</span>
                </div>
              </div>
            </div>

            {/* Statutory Declaration Checkbox */}
            <div className="rounded-2xl border border-emerald-300 bg-emerald-50/60 p-4 space-y-3">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={declarationSigned}
                  onChange={(e) => setDeclarationSigned(e.target.checked)}
                  className="h-4 w-4 rounded text-emerald-600 mt-0.5"
                />
                <div className="text-xs text-slate-800 leading-relaxed font-medium">
                  <strong>Seller Statutory Declaration:</strong> I hereby confirm that the information and document evidence provided for Parcel <strong>{parcelNumber}</strong> are accurate to the best of my knowledge, and I authorize Digiland's licensed professionals (Agents, Surveyors, Advocates) to verify these records against official government land registries.
                </div>
              </label>
            </div>

            {/* Submit Action */}
            <div className="flex justify-between pt-4 border-t border-slate-100">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCurrentStep(4)}
                className="rounded-xl text-xs h-11 px-6 font-bold"
              >
                ← Back to Screening
              </Button>

              <Button
                type="button"
                onClick={handleFinalSubmit}
                disabled={!declarationSigned || isSubmitting}
                className="rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs h-11 px-8 shadow-md gap-2"
              >
                {isSubmitting ? 'Submitting Verification Case...' : 'Submit Property for Verification ✓'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Success Modal / Banner after final submission */}
      {isFinalSubmitted && (
        <Card className="bg-emerald-950 text-white p-6 rounded-3xl shadow-2xl text-center space-y-4 border border-emerald-500/40">
          <CheckCircle2 className="h-12 w-12 text-emerald-400 mx-auto animate-bounce" />
          <h2 className="text-xl font-black text-white">Property Submitted for Verification!</h2>
          <p className="text-xs text-slate-300 max-w-md mx-auto leading-relaxed">
            Your verification case <strong>{caseNumber}</strong> has been created. Our AI document screening engine has logged your evidence and queued the property for Digiland professional review.
          </p>
          <div className="pt-2">
            <Button
              onClick={() => (window.location.href = '/parcels/')}
              className="rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs h-10 px-6"
            >
              Return to Seller Dashboard
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
