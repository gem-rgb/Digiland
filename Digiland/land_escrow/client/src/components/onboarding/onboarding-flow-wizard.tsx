import React, { useState } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Users,
  Building2,
  User,
  Sparkles,
  ShieldCheck,
  Landmark,
  Home,
  Briefcase,
  Layers,
  Scale,
  DollarSign,
  HeartHandshake,
  Vote,
} from 'lucide-react';
import { DigitalCrownAvatar } from '../ui/digital-crown-avatar.js';
import { Button } from '../ui/button.js';
import { Input } from '../ui/input.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Badge } from '../ui/badge.js';
import type { UserSummary } from '../../types.js';

interface OnboardingFlowWizardProps {
  user?: UserSummary | null;
  csrfToken?: string;
  onComplete?: (result: any) => void;
}

export function OnboardingFlowWizard({ user, csrfToken, onComplete }: OnboardingFlowWizardProps) {
  // Step State
  const [step, setStep] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form State
  const [purpose, setPurpose] = useState<'BUY' | 'SELL' | 'BOTH' | null>(null);
  const [accountType, setAccountType] = useState<'INDIVIDUAL' | 'JOINT' | 'ORGANIZATION' | null>(null);
  const [entityType, setEntityType] = useState<string>('PERSON');
  const [displayName, setDisplayName] = useState<string>('');
  const [legalName, setLegalName] = useState<string>('');
  const [registrationNumber, setRegistrationNumber] = useState<string>('');
  const [kraPin, setKraPin] = useState<string>('');
  const [governanceRule, setGovernanceRule] = useState<string>('SIMPLE_MAJORITY');

  // Step 1: Purpose Selection
  const handlePurposeSelect = (p: 'BUY' | 'SELL' | 'BOTH') => {
    setPurpose(p);
    setStep(2);
  };

  // Step 2: Account Structure Selection
  const handleStructureSelect = (type: 'INDIVIDUAL' | 'JOINT' | 'ORGANIZATION') => {
    setAccountType(type);
    if (type === 'INDIVIDUAL') {
      setEntityType('PERSON');
      setStep(4); // Skip entity type selection for standard person
    } else {
      setStep(3);
    }
  };

  // Step 3: Entity Type Selection
  const handleEntityTypeSelect = (entity: string) => {
    setEntityType(entity);
    setStep(4);
  };

  // Step 4: Submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload = {
      purpose: purpose || 'BUY',
      account_type: accountType || 'INDIVIDUAL',
      entity_type: entityType,
      display_name: displayName.trim(),
      legal_name: legalName.trim() || displayName.trim(),
      registration_number: registrationNumber.trim(),
      tax_id_or_kra_pin: kraPin.trim(),
      governance_rule: governanceRule,
    };

    try {
      const response = await fetch('/api/onboarding/select-role/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to complete onboarding.');
      }

      if (onComplete) {
        onComplete(data);
      } else {
        window.location.href = data.redirect_url || (purpose === 'SELL' ? '/seller/dashboard/' : '/buyer/dashboard/');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during account provisioning.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 text-slate-900">
      {/* Progress Bar & Header */}
      <div className="mb-8 text-center space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-1 text-xs font-bold text-emerald-800">
          <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
          <span>Digiland Entity & Account Setup</span>
          <span className="font-mono text-slate-400">• Step {step} of 4</span>
        </div>
        <div className="mx-auto h-1.5 w-48 rounded-full bg-slate-200 overflow-hidden">
          <div
            className="h-full bg-emerald-600 transition-all duration-300 rounded-full"
            style={{ width: `${(step / 4) * 100}%` }}
          />
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-800 text-center">
          {error}
        </div>
      )}

      {/* STEP 1: WHAT ARE YOU LOOKING TO DO? */}
      {step === 1 && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
              What brings you to Digiland?
            </h1>
            <p className="text-slate-600 text-sm max-w-xl mx-auto">
              Select your primary intent on the platform. You can operate multiple buyer or seller accounts under one login.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-3 pt-4">
            {/* Buy Card */}
            <div
              onClick={() => handlePurposeSelect('BUY')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-500 hover:shadow-lg text-left"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 transition group-hover:bg-emerald-600 group-hover:text-white">
                <Home className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-bold text-slate-900">Buy Property</h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                Browse verified parcels, purchase individually, as a chama, family, or institution with escrow protection.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-emerald-700">
                <span>Continue</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>

            {/* Sell Card */}
            <div
              onClick={() => handlePurposeSelect('SELL')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-500 hover:shadow-lg text-left"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-700 transition group-hover:bg-teal-600 group-hover:text-white">
                <Landmark className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-bold text-slate-900">Sell Property</h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                List land, coordinate co-owner legal signoffs, AI verification, and receive secure payouts.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-teal-700">
                <span>Continue</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>

            {/* Both Card */}
            <div
              onClick={() => handlePurposeSelect('BOTH')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-500 hover:shadow-lg text-left"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-700 transition group-hover:bg-indigo-600 group-hover:text-white">
                <Briefcase className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-bold text-slate-900">Buy & Sell Both</h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                Manage property acquisitions and portfolio listings simultaneously from one unified account workspace.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-indigo-700">
                <span>Continue</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* STEP 2: HOW WILL YOU BE BUYING / SELLING? */}
      {step === 2 && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
              {purpose === 'BUY' ? 'How will you be buying?' : purpose === 'SELL' ? 'What kind of seller are you?' : 'How will you operate your account?'}
            </h1>
            <p className="text-slate-600 text-sm max-w-xl mx-auto">
              Select the account structure that best represents how decisions, payments, and legal title will be handled.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-3 pt-4">
            {/* Option 1: Individual */}
            <div
              onClick={() => handleStructureSelect('INDIVIDUAL')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-500 hover:shadow-lg text-left"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-700 transition group-hover:bg-slate-900 group-hover:text-white">
                <User className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-bold text-slate-900">Individual</h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                {purpose === 'BUY'
                  ? "I'm buying property on my own in my personal capacity."
                  : "I'm selling personal property registered in my name."}
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-slate-800">
                <span>Select Individual</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>

            {/* Option 2: Joint / Group */}
            <div
              onClick={() => handleStructureSelect('JOINT')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-emerald-300 bg-emerald-50/20 p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-600 hover:shadow-lg text-left ring-1 ring-emerald-500/20"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-600 text-white transition group-hover:scale-105">
                <Users className="h-6 w-6" />
              </div>
              <div className="mt-5 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900">Joint / Group</h3>
                <Badge tone="success" className="text-[10px] font-extrabold uppercase">Team Crown 👑</Badge>
              </div>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                {purpose === 'BUY'
                  ? 'Create a shared account for a chama, family, or investment partners with group voting.'
                  : 'Selling inherited, family, or co-owned land with multi-owner approval requirements.'}
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-emerald-700">
                <span>Select Joint / Group</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>

            {/* Option 3: Organization / Institution */}
            <div
              onClick={() => handleStructureSelect('ORGANIZATION')}
              className="group relative cursor-pointer overflow-hidden rounded-3xl border-2 border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-indigo-500 hover:shadow-lg text-left"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-700 transition group-hover:bg-indigo-600 group-hover:text-white">
                <Building2 className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-lg font-bold text-slate-900">Organization / Institution</h3>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed font-normal">
                Represent a company, government entity, NGO, SACCO, cooperative, or institutional investor with authorized representatives.
              </p>
              <div className="mt-4 flex items-center gap-1 text-xs font-bold text-indigo-700">
                <span>Select Organization</span> <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
              </div>
            </div>
          </div>

          <div className="pt-4 text-center">
            <Button variant="ghost" onClick={() => setStep(1)} className="rounded-full text-xs gap-1.5">
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Purpose
            </Button>
          </div>
        </div>
      )}

      {/* STEP 3: ENTITY CLASSIFICATION */}
      {step === 3 && (
        <div className="space-y-6 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight">
              {accountType === 'JOINT'
                ? 'What kind of group are you creating?'
                : 'What type of organization are you representing?'}
            </h1>
            <p className="text-slate-600 text-sm max-w-xl mx-auto">
              This helps Digiland apply the appropriate governance rules and document verification workflows.
            </p>
          </div>

          {accountType === 'JOINT' ? (
            <div className="grid gap-4 sm:grid-cols-3 pt-4">
              {[
                { id: 'FAMILY', name: 'Family / Relatives', desc: 'Siblings, spouses, parents, or family trusts' },
                { id: 'CHAMA', name: 'Chama / Investment Group', desc: 'Registered or informal investment group' },
                { id: 'FRIENDS', name: 'Friends / Private Group', desc: 'Colleagues or private investors pooling funds' },
                { id: 'BUSINESS_PARTNERS', name: 'Business Partners', desc: 'Commercial partners acquiring/selling assets' },
                { id: 'JOINT_INVESTMENT', name: 'Joint Investment Syndicate', desc: 'Structured syndication with defined shares' },
                { id: 'OTHER', name: 'Other Group', desc: 'Other multi-member human group' },
              ].map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleEntityTypeSelect(item.id)}
                  className={`cursor-pointer rounded-2xl border-2 p-4 text-left transition ${
                    entityType === item.id
                      ? 'border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-400'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="font-bold text-sm text-slate-900">{item.name}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.desc}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-3 pt-4">
              {[
                { id: 'COMPANY', name: 'Company / Corporate Entity', desc: 'Private Ltd, Public Ltd, or Partnership' },
                { id: 'GOVERNMENT', name: 'Government Entity', desc: 'Ministry, State Agency, or County Government' },
                { id: 'NGO', name: 'NGO / Non-Profit', desc: 'Non-governmental or charitable trust' },
                { id: 'SACCO', name: 'SACCO / Cooperative', desc: 'Savings & Credit Society or Cooperative' },
                { id: 'INSTITUTION', name: 'Educational / Religious', desc: 'University, School, Church, or Mosque' },
                { id: 'BANK', name: 'Bank / Financial Institution', desc: 'Commercial bank, microfinance, or asset manager' },
                { id: 'ESTATE', name: 'Estate / Legal Representative', desc: 'Succession, executor, or letters of admin' },
                { id: 'OTHER', name: 'Other Organization', desc: 'Other legally incorporated organization' },
              ].map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleEntityTypeSelect(item.id)}
                  className={`cursor-pointer rounded-2xl border-2 p-4 text-left transition ${
                    entityType === item.id
                      ? 'border-indigo-500 bg-indigo-50/40 ring-1 ring-indigo-400'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="font-bold text-sm text-slate-900">{item.name}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.desc}</div>
                </div>
              ))}
            </div>
          )}

          <div className="pt-4 text-center">
            <Button variant="ghost" onClick={() => setStep(2)} className="rounded-full text-xs gap-1.5">
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Account Type
            </Button>
          </div>
        </div>
      )}

      {/* STEP 4: PROFILE DETAILS & GOVERNANCE */}
      {step === 4 && (
        <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-300">
          <div className="text-center space-y-2">
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
              {accountType === 'INDIVIDUAL'
                ? 'Confirm Personal Account'
                : accountType === 'JOINT'
                ? 'Name Your Joint Group'
                : 'Enter Organization Details'}
            </h1>
            <p className="text-slate-600 text-xs">
              Complete your account profile. You can invite team members immediately after activation.
            </p>
          </div>

          {/* Identity & Role Preview Card */}
          <div className="rounded-3xl border border-slate-200 bg-gradient-to-r from-slate-900 to-slate-950 p-5 text-white shadow-md flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <DigitalCrownAvatar
                name={displayName || user?.full_name || user?.email || 'User'}
                isManager={accountType === 'JOINT'}
                isOrganization={accountType === 'ORGANIZATION'}
                size="lg"
              />
              <div className="min-w-0 text-left">
                <div className="text-xs text-emerald-400 font-bold uppercase tracking-wider">
                  {accountType === 'JOINT'
                    ? 'Account Leadership Role'
                    : accountType === 'ORGANIZATION'
                    ? 'Authorized Representative'
                    : 'Personal Account'}
                </div>
                <div className="text-base font-bold text-white truncate">
                  {accountType === 'JOINT'
                    ? (purpose === 'SELL' ? 'Seller Team Manager 👑' : 'Buyer Team Manager 👑')
                    : accountType === 'ORGANIZATION'
                    ? 'Primary Representative 🏢'
                    : 'Individual Buyer / Seller'}
                </div>
                <div className="text-[11px] text-slate-300">
                  {accountType === 'JOINT'
                    ? 'You will lead group invitations and proposal creation with peer voting.'
                    : accountType === 'ORGANIZATION'
                    ? 'Authorized to act on behalf of the registered entity in Digiland.'
                    : 'Standard personal account for individual purchases.'}
                </div>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 text-left">
            {accountType !== 'INDIVIDUAL' && (
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  {accountType === 'JOINT' ? 'Group / Chama Name' : 'Registered Organization Name'} *
                </label>
                <Input
                  required
                  placeholder={accountType === 'JOINT' ? 'e.g. Umoja Family Investment Chama' : 'e.g. ABC Holdings Kenya Ltd'}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="rounded-2xl h-11"
                />
              </div>
            )}

            {accountType === 'ORGANIZATION' && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Registration / Certificate No.
                  </label>
                  <Input
                    placeholder="e.g. CPR/2026/10294"
                    value={registrationNumber}
                    onChange={(e) => setRegistrationNumber(e.target.value)}
                    className="rounded-2xl h-11"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                    Corporate KRA PIN
                  </label>
                  <Input
                    placeholder="e.g. P051234567Z"
                    value={kraPin}
                    onChange={(e) => setKraPin(e.target.value)}
                    className="rounded-2xl h-11"
                  />
                </div>
              </div>
            )}

            {accountType === 'JOINT' && (
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
                  Group Governance Voting Rule
                </label>
                <select
                  value={governanceRule}
                  onChange={(e) => setGovernanceRule(e.target.value)}
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-medium text-slate-900 shadow-xs focus:border-emerald-500 focus:outline-hidden"
                >
                  <option value="SIMPLE_MAJORITY">Simple Majority (&gt;50% of active members)</option>
                  <option value="TWO_THIRDS">Two-Thirds Majority (≥66.7% of active members)</option>
                  <option value="UNANIMOUS">Unanimous Consent (100% of active members)</option>
                </select>
                <p className="mt-1 text-[11px] text-slate-500">
                  One eligible member = one vote. Removing members or committing purchase proposals strictly requires this threshold.
                </p>
              </div>
            )}

            <div className="pt-4 flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep(accountType === 'INDIVIDUAL' ? 2 : 3)}
                className="rounded-full text-xs"
              >
                <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back
              </Button>

              <Button
                type="submit"
                disabled={loading}
                className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white px-8 text-xs font-bold shadow-md shadow-emerald-950/20"
              >
                {loading ? 'Provisioning Account...' : 'Complete & Open Dashboard'}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
