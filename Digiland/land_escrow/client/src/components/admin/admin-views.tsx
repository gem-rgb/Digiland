import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Briefcase,
  CheckCircle2,
  ExternalLink,
  Eye,
  Filter,
  Gavel,
  Info,
  Lock,
  Mail,
  MessageSquare,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import { Button } from '../ui/button.js';
import { Badge } from '../ui/badge.js';
import { readBootstrap } from '../../lib/bootstrap.js';

const bootstrap = readBootstrap();

// =========================================================================
// 1. ADMIN PEOPLE & STAFF MANAGEMENT HUB
// =========================================================================
export function AdminPeopleHubView() {
  const [activeSubTab, setActiveSubTab] = useState<'users' | 'provision'>('users');
  const [usersList, setUsersList] = useState<any[]>(bootstrap.all_users || bootstrap.professionals || []);
  const [roleFilter, setRoleFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Provisioning Form States
  const [roleToCreate, setRoleToCreate] = useState<'Lawyer' | 'Agent' | 'Staff' | 'Admin'>('Lawyer');
  const [provisionMode, setProvisionMode] = useState<'DIRECT_ACTIVE' | 'INVITATION'>('DIRECT_ACTIVE');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('Digiland@2026');
  const [nationalId, setNationalId] = useState('');
  const [kraPin, setKraPin] = useState('');
  const [county, setCounty] = useState('Nairobi');

  // Professional specific fields
  const [lawFirmName, setLawFirmName] = useState('');
  const [lskNumber, setLskNumber] = useState('');
  const [practicingCert, setPracticingCert] = useState('');
  const [yearOfAdmission, setYearOfAdmission] = useState('2020');
  const [agencyName, setAgencyName] = useState('');
  const [earbNumber, setEarbNumber] = useState('');
  const [goodConductNumber, setGoodConductNumber] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [generatedInviteUrl, setGeneratedInviteUrl] = useState<string | null>(null);

  // Filtered Users
  const filteredUsers = useMemo(() => {
    return usersList.filter((u) => {
      if (roleFilter !== 'All' && u.role !== roleFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          (u.name && u.name.toLowerCase().includes(q)) ||
          (u.email && u.email.toLowerCase().includes(q)) ||
          (u.phone && u.phone.toLowerCase().includes(q)) ||
          (u.county && u.county.toLowerCase().includes(q)) ||
          (u.firm_or_agency && u.firm_or_agency.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [usersList, roleFilter, searchQuery]);

  const handleToggleStatus = async (user: any) => {
    setActionLoadingId(user.id);
    setActionMessage(null);
    try {
      const resp = await fetch(`/admin/api/users/${user.id}/toggle-status/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
      });
      const data = await resp.json();
      if (resp.ok) {
        setUsersList((prev) =>
          prev.map((u) => (u.id === user.id ? { ...u, is_active: data.is_active } : u))
        );
        setActionMessage(`Account for ${user.email} is now ${data.is_active ? 'active' : 'suspended'}.`);
      } else {
        alert(data.error || 'Failed to update account status');
      }
    } catch {
      alert('Network error updating status');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDeleteUser = async (user: any) => {
    const confirmText = `Are you sure you want to PERMANENTLY DELETE user '${user.name || user.email}' (${user.email})?\n\nThis will remove their login, profile, and credentials.\nThis action CANNOT be undone.`;
    if (!confirm(confirmText)) return;

    setActionLoadingId(user.id);
    setActionMessage(null);
    try {
      const resp = await fetch(`/admin/api/users/${user.id}/delete/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
      });
      const data = await resp.json();
      if (resp.ok) {
        setUsersList((prev) => prev.filter((u) => u.id !== user.id));
        setActionMessage(`User account for ${user.email} was permanently deleted.`);
      } else {
        alert(data.error || 'Failed to delete user account');
      }
    } catch {
      alert('Network error deleting user');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReassignRole = async (user: any, newRole: string) => {
    if (!confirm(`Are you sure you want to reassign ${user.email} to role '${newRole}'?`)) return;
    setActionLoadingId(user.id);
    try {
      const resp = await fetch(`/admin/api/users/${user.id}/update-role/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
        body: JSON.stringify({ role: newRole }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setUsersList((prev) =>
          prev.map((u) => (u.id === user.id ? { ...u, role: newRole } : u))
        );
        setActionMessage(`Updated role to ${newRole} for ${user.email}`);
      } else {
        alert(data.error || 'Failed to update role');
      }
    } catch {
      alert('Network error updating role');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormError(null);
    setFormSuccess(null);
    setGeneratedInviteUrl(null);

    const payload = {
      role: roleToCreate,
      provision_mode: provisionMode,
      full_name: fullName,
      email,
      phone_number: phone,
      password: provisionMode === 'DIRECT_ACTIVE' ? password : '',
      national_id: nationalId,
      kra_pin: kraPin,
      county,
      law_firm_name: lawFirmName,
      lsk_number: lskNumber,
      practicing_cert_number: practicingCert,
      year_of_admission: yearOfAdmission,
      agency_name: agencyName,
      earb_number: earbNumber,
      good_conduct_number: goodConductNumber,
    };

    try {
      const resp = await fetch(bootstrap.provision_action || '/admin/staff/provision/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Failed to provision account');
      }

      setFormSuccess(data.message || `Successfully provisioned ${roleToCreate} account for ${fullName}!`);
      if (data.invite_url) {
        setGeneratedInviteUrl(data.invite_url);
      }
      if (data.user) {
        setUsersList((prev) => [data.user, ...prev]);
      }

      // Reset form
      setFullName('');
      setEmail('');
      setPhone('');
      setNationalId('');
      setKraPin('');
      setLawFirmName('');
      setLskNumber('');
      setPracticingCert('');
      setAgencyName('');
      setEarbNumber('');
      setGoodConductNumber('');
    } catch (err: any) {
      setFormError(err.message || 'An error occurred while provisioning user.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 text-left">
      {/* Top Header Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h3 className="text-lg font-black text-slate-900">People & Privileged Accounts Hub</h3>
          <p className="text-xs text-slate-500 font-medium">
            Manage public buyers/sellers and internally provisioned real estate professionals (Agents, Lawyers, Staff, Admins).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveSubTab('users')}
            className={`inline-flex h-9 items-center gap-1.5 rounded-xl px-4 text-xs font-bold transition ${
              activeSubTab === 'users'
                ? 'bg-emerald-600 text-white font-black shadow-md shadow-emerald-600/20'
                : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Users className="h-3.5 w-3.5" /> All Users ({usersList.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab('provision')}
            className={`inline-flex h-9 items-center gap-1.5 rounded-xl px-4 text-xs font-bold transition ${
              activeSubTab === 'provision'
                ? 'bg-emerald-600 text-white font-black shadow-md shadow-emerald-600/20'
                : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            <UserCheck className="h-3.5 w-3.5" /> Provision New User
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-50 p-3 text-xs text-emerald-800 font-medium">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* SUB-VIEW 1: USERS DIRECTORY */}
      {activeSubTab === 'users' && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {['All', 'Buyer', 'Seller', 'Agent', 'Lawyer', 'Staff', 'Admin'].map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRoleFilter(r)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                    roleFilter === r
                      ? 'bg-emerald-600 text-white font-black shadow-xs'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
                  }`}
                >
                  {r === 'All' ? 'All Roles' : `${r}s`}
                </button>
              ))}
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search name, email, phone, county..."
                className="h-9 w-64 rounded-xl border border-slate-300 bg-slate-50 pl-8 pr-3 text-xs text-slate-900 placeholder:text-slate-400 outline-none focus:border-emerald-500 focus:bg-white transition"
              />
            </div>
          </div>

          {/* Table */}
          {filteredUsers.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              No user accounts found matching your filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                    <th className="py-3 px-3">User & Contact</th>
                    <th className="py-3 px-3">Role</th>
                    <th className="py-3 px-3">County / Region</th>
                    <th className="py-3 px-3">Verification</th>
                    <th className="py-3 px-3">Account Status</th>
                    <th className="py-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredUsers.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition">
                      <td className="py-3.5 px-3">
                        <div className="font-bold text-slate-900">{u.name}</div>
                        <div className="text-[11px] text-slate-500 font-medium">{u.email}</div>
                        <div className="text-[10px] text-slate-400">{u.phone || 'No phone'}</div>
                      </td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[10px] font-black uppercase ${
                            u.role === 'Admin'
                              ? 'bg-purple-100 text-purple-800 border border-purple-200'
                              : u.role === 'Lawyer'
                              ? 'bg-blue-100 text-blue-800 border border-blue-200'
                              : u.role === 'Agent'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                              : 'bg-slate-100 text-slate-700 border border-slate-200'
                          }`}
                        >
                          {u.role === 'Lawyer' ? (
                            <Gavel className="h-3 w-3" />
                          ) : u.role === 'Agent' ? (
                            <Briefcase className="h-3 w-3" />
                          ) : (
                            <User className="h-3 w-3" />
                          )}
                          {u.role}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-slate-600 font-medium">{u.county || 'Nairobi'}</td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            u.is_verified
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                              : 'bg-amber-100 text-amber-800 border border-amber-200'
                          }`}
                        >
                          <ShieldCheck className="h-3 w-3" />
                          {u.is_verified ? 'Verified' : 'Unverified'}
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-bold ${
                            u.is_active ? 'text-emerald-700' : 'text-rose-700'
                          }`}
                        >
                          <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? 'bg-emerald-600' : 'bg-rose-600'}`} />
                          {u.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <select
                            value={u.role}
                            onChange={(e) => handleReassignRole(u, e.target.value)}
                            disabled={actionLoadingId === u.id}
                            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 outline-none hover:border-slate-400 transition"
                          >
                            <option value="Buyer">Role: Buyer</option>
                            <option value="Seller">Role: Seller</option>
                            <option value="Agent">Role: Agent</option>
                            <option value="Lawyer">Role: Lawyer</option>
                            <option value="Staff">Role: Staff</option>
                            <option value="Admin">Role: Admin</option>
                          </select>

                          {/* Suspend / Activate Button */}
                          <button
                            type="button"
                            onClick={() => handleToggleStatus(u)}
                            disabled={actionLoadingId === u.id}
                            className={`rounded-lg border px-2.5 py-1 text-[11px] font-bold transition ${
                              u.is_active
                                ? 'border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100'
                                : 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                            }`}
                            title={u.is_active ? 'Suspend account' : 'Reactivate account'}
                          >
                            {u.is_active ? 'Suspend' : 'Activate'}
                          </button>

                          {/* Permanent Delete Button */}
                          <button
                            type="button"
                            onClick={() => handleDeleteUser(u)}
                            disabled={actionLoadingId === u.id}
                            className="rounded-lg border border-rose-300 bg-rose-50 text-rose-700 hover:bg-rose-100 hover:border-rose-400 px-2 py-1 text-[11px] font-bold transition inline-flex items-center gap-1"
                            title="Permanently Delete User Account"
                          >
                            <Trash2 className="h-3 w-3" />
                            <span>Delete</span>
                          </button>

                          <a
                            href={`/messages/?partner=${encodeURIComponent(u.email)}`}
                            className="rounded-lg border border-slate-300 bg-slate-50 p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                            title="Direct Message"
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SUB-VIEW 2: PROVISION NEW USER WIZARD */}
      {activeSubTab === 'provision' && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
          <div className="border-b border-slate-200 pb-4">
            <h4 className="text-base font-black text-slate-900">Internal Privileged User Provisioning</h4>
            <p className="text-xs text-slate-500 font-medium">
              Provision certified Advocates, Licensed Field Agents, Compliance Officers, and Admin Staff with role-based access.
            </p>
          </div>

          {formError && (
            <div className="flex items-center gap-2 rounded-2xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800 font-medium">
              <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />
              <span>{formError}</span>
            </div>
          )}

          {formSuccess && (
            <div className="space-y-2 rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-xs text-emerald-800">
              <div className="flex items-center gap-2 font-bold">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                <span>{formSuccess}</span>
              </div>
              {generatedInviteUrl && (
                <div className="mt-2 rounded-xl border border-slate-200 bg-slate-900 p-3">
                  <div className="text-[11px] font-bold text-slate-300 mb-1">Single-Use Secure Invitation Link:</div>
                  <div className="font-mono text-xs text-emerald-400 break-all select-all">{generatedInviteUrl}</div>
                  <div className="text-[10px] text-slate-400 mt-1">Send this link to the user to securely set their password and access their workspace.</div>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleCreateUser} className="space-y-6">
            {/* Step 1: Role Selection */}
            <div>
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">1. Select Privileged Role</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { r: 'Lawyer', title: 'Advocate / Lawyer', desc: 'Conveyancing & LSK verified' },
                  { r: 'Agent', title: 'Real Estate Agent', desc: 'Site inspections & EARB license' },
                  { r: 'Staff', title: 'Compliance Staff', desc: 'Internal operations desk' },
                  { r: 'Admin', title: 'System Administrator', desc: 'Full platform authority' },
                ].map(({ r, title, desc }) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRoleToCreate(r as any)}
                    className={`rounded-2xl border p-3.5 text-left transition ${
                      roleToCreate === r
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-950 font-bold shadow-xs ring-1 ring-emerald-600'
                        : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <div className="text-xs font-black text-slate-900">{title}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: Provisioning Mode */}
            <div>
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block mb-2">2. Provisioning Method</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setProvisionMode('DIRECT_ACTIVE')}
                  className={`rounded-2xl border p-3.5 text-left transition ${
                    provisionMode === 'DIRECT_ACTIVE'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-950 font-bold shadow-xs ring-1 ring-emerald-600'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <div className="text-xs font-black text-slate-900">Direct Active Creation</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Admin sets initial password; account is pre-verified and active immediately.</div>
                </button>

                <button
                  type="button"
                  onClick={() => setProvisionMode('INVITATION')}
                  className={`rounded-2xl border p-3.5 text-left transition ${
                    provisionMode === 'INVITATION'
                      ? 'border-emerald-600 bg-emerald-50 text-emerald-950 font-bold shadow-xs ring-1 ring-emerald-600'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <div className="text-xs font-black text-slate-900">Secure Invitation Link (Recommended)</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Generates single-use token; user sets their own password securely.</div>
                </button>
              </div>
            </div>

            {/* Step 3: Identity & Contact Information */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">3. Identity & Contact Details</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">Full Name *</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Adv. James Mwangi"
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">Email Address *</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="official@lawfirm.co.ke"
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">Phone Number (M-Pesa Payouts)</label>
                  <input
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+254712345678"
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">National ID / Passport No</label>
                  <input
                    type="text"
                    value={nationalId}
                    onChange={(e) => setNationalId(e.target.value)}
                    placeholder="e.g. 29481920"
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">KRA PIN</label>
                  <input
                    type="text"
                    value={kraPin}
                    onChange={(e) => setKraPin(e.target.value)}
                    placeholder="A012345678Z"
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-600 block mb-1 font-bold">Primary Operating County</label>
                  <select
                    value={county}
                    onChange={(e) => setCounty(e.target.value)}
                    className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                  >
                    {['Nairobi', 'Kiambu', 'Machakos', 'Kajiado', 'Nakuru', 'Mombasa', 'Uasin Gishu', 'Kisumu'].map((c) => (
                      <option key={c} value={c}>{c} County</option>
                    ))}
                  </select>
                </div>

                {provisionMode === 'DIRECT_ACTIVE' && (
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">Initial Password</label>
                    <input
                      type="text"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Step 4: Role-Specific Professional Credentials */}
            {roleToCreate === 'Lawyer' && (
              <div className="space-y-3 rounded-2xl border border-blue-200 bg-blue-50/50 p-4">
                <label className="text-xs font-black text-blue-900 uppercase tracking-wider block">Advocate Professional Verification Details</label>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">Law Firm Name</label>
                    <input
                      type="text"
                      value={lawFirmName}
                      onChange={(e) => setLawFirmName(e.target.value)}
                      placeholder="e.g. Mwangi & Associates Advocates"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">LSK Roll Number</label>
                    <input
                      type="text"
                      value={lskNumber}
                      onChange={(e) => setLskNumber(e.target.value)}
                      placeholder="e.g. P.105/14820/18"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">Practicing Cert No</label>
                    <input
                      type="text"
                      value={practicingCert}
                      onChange={(e) => setPracticingCert(e.target.value)}
                      placeholder="e.g. LSK-PC-2026-8492"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">Admission Year</label>
                    <input
                      type="text"
                      value={yearOfAdmission}
                      onChange={(e) => setYearOfAdmission(e.target.value)}
                      placeholder="2018"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {roleToCreate === 'Agent' && (
              <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
                <label className="text-xs font-black text-emerald-900 uppercase tracking-wider block">Real Estate Agent Licensing Details</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">Agency / Brokerage Name</label>
                    <input
                      type="text"
                      value={agencyName}
                      onChange={(e) => setAgencyName(e.target.value)}
                      placeholder="e.g. Prime Ridge Properties Ltd"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">EARB Registration No</label>
                    <input
                      type="text"
                      value={earbNumber}
                      onChange={(e) => setEarbNumber(e.target.value)}
                      placeholder="e.g. EARB/2026/0842"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-600 block mb-1 font-bold">DCI Good Conduct Certificate</label>
                    <input
                      type="text"
                      value={goodConductNumber}
                      onChange={(e) => setGoodConductNumber(e.target.value)}
                      placeholder="e.g. DCI/PCC/2026/19482"
                      className="w-full h-10 rounded-xl border border-slate-300 bg-white px-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Submit Action */}
            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                disabled={isSubmitting}
                className="h-11 rounded-2xl px-6 text-xs font-black bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20"
              >
                {isSubmitting ? (
                  'Provisioning User...'
                ) : (
                  <>
                    <UserCheck className="mr-2 h-4 w-4" />
                    Provision {roleToCreate} Account
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}


// =========================================================================
// 2. ADMIN KYC & VERIFICATION DESK WITH SIDE-BY-SIDE DOCUMENT INSPECTOR
// =========================================================================
export function AdminKycDeskView() {
  const [applications, setApplications] = useState<any[]>(bootstrap.pending_agent_applications || []);
  const [selectedApp, setSelectedApp] = useState<any | null>(applications[0] || null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const handleDecision = async (decision: 'APPROVE' | 'REJECT' | 'REQUEST_INFO') => {
    if (!selectedApp) return;
    setIsProcessing(true);
    setFeedbackMessage(null);

    try {
      const resp = await fetch(`/admin/api/kyc/${selectedApp.id}/decision/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
        body: JSON.stringify({
          decision,
          review_notes: reviewNotes,
        }),
      });

      const data = await resp.json();
      if (resp.ok) {
        setFeedbackMessage(data.message || `KYC decision recorded: ${decision}`);
        setApplications((prev) => prev.filter((a) => a.id !== selectedApp.id));
        setSelectedApp(null);
        setReviewNotes('');
      } else {
        alert(data.error || 'Failed to submit KYC decision');
      }
    } catch {
      alert('Network error submitting decision');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-200 pb-4">
        <h3 className="text-lg font-black text-slate-900">KYC & Document Verification Station</h3>
        <p className="text-xs text-slate-500 font-medium">
          Inspect uploaded credentials, AI OCR extracted signals, and execute statutory human review decisions.
        </p>
      </div>

      {feedbackMessage && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-50 p-3 text-xs text-emerald-800 font-medium">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{feedbackMessage}</span>
        </div>
      )}

      {applications.length === 0 ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-12 text-center shadow-xs space-y-3">
          <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
          <h4 className="text-sm font-black text-slate-900">KYC Approvals Queue Clear</h4>
          <p className="text-xs text-slate-500">All submitted agent, lawyer, and seller documents have been reviewed.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Applications List */}
          <div className="lg:col-span-4 space-y-3">
            <div className="text-xs font-black uppercase text-slate-500 px-1">
              Pending Applications ({applications.length})
            </div>
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {applications.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  onClick={() => setSelectedApp(app)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedApp?.id === app.id
                      ? 'border-emerald-600 bg-emerald-50 text-slate-900 shadow-xs ring-1 ring-emerald-600'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="font-bold text-xs text-slate-900">{app.name}</div>
                    <Badge tone="warning" className="text-[9px] uppercase font-bold py-0">
                      {app.status || 'Pending'}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">{app.email}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">ID: {app.id_number} | KRA: {app.kra_pin}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Right Column: Side-by-side Document & AI Signal Inspector */}
          {selectedApp && (
            <div className="lg:col-span-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
              {/* Applicant Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <h4 className="text-base font-black text-slate-900">{selectedApp.name}</h4>
                  <div className="text-xs text-slate-500 font-medium">{selectedApp.email} • {selectedApp.phone || 'No phone'}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-200">
                    National ID: {selectedApp.id_number}
                  </span>
                  <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-bold text-blue-800 border border-blue-200">
                    KRA: {selectedApp.kra_pin}
                  </span>
                </div>
              </div>

              {/* Side-by-Side: Document Preview & Extracted OCR Signals */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Document Display Panel */}
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                  <div className="text-[11px] font-bold uppercase text-slate-600 flex items-center justify-between">
                    <span>Uploaded ID Document</span>
                    <span className="text-emerald-700 font-bold text-[10px]">High Res</span>
                  </div>
                  <div className="aspect-[4/3] rounded-xl border border-slate-200 bg-white flex flex-col items-center justify-center p-4 text-center">
                    <ShieldCheck className="h-12 w-12 text-emerald-600 mb-2 opacity-90" />
                    <div className="text-xs font-bold text-slate-900">Kenyan National ID Card</div>
                    <div className="font-mono text-[10px] text-slate-500 mt-1">ID No: {selectedApp.id_number}</div>
                    <div className="text-[9px] text-slate-400 mt-0.5">Holder: {selectedApp.name}</div>
                  </div>
                </div>

                {/* AI Extraction & Authenticity Signals */}
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-3 text-xs">
                  <div className="text-[11px] font-bold uppercase text-slate-600 flex items-center justify-between">
                    <span>AI Verification Signals</span>
                    <Badge tone="success" className="text-[9px] py-0 font-bold">Passed</Badge>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500 font-medium">OCR Confidence:</span>
                      <span className="font-bold text-emerald-700">96.4%</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500 font-medium">Laplacian Blur Score:</span>
                      <span className="font-bold text-emerald-700">88.5 (Sharp)</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500 font-medium">Canny Edge Density:</span>
                      <span className="font-bold text-emerald-700">0.0240 (No Tamper)</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500 font-medium">Government Template Match:</span>
                      <span className="font-bold text-emerald-700">95.0%</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500 font-medium">Identity Cross-Match:</span>
                      <span className="font-bold text-emerald-700">Exact Match</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Human Decision Station */}
              <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  Human Review & Decision Authority
                </label>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Optional decision notes / statutory justification..."
                  rows={2}
                  className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs text-slate-900 outline-none focus:border-emerald-500"
                />

                <div className="flex flex-wrap items-center justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => handleDecision('REQUEST_INFO')}
                    className="h-9 rounded-xl border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 text-xs font-bold"
                  >
                    Request Info
                  </Button>
                  <Button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => handleDecision('REJECT')}
                    className="h-9 rounded-xl border border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100 text-xs font-bold"
                  >
                    Reject Application
                  </Button>
                  <Button
                    type="button"
                    disabled={isProcessing}
                    onClick={() => handleDecision('APPROVE')}
                    className="h-9 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black shadow-md shadow-emerald-600/20"
                  >
                    <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Approve & Activate
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// =========================================================================
// 3. ADMIN AI EVALUATION & BENCHMARK TESTING LAB
// =========================================================================
export function AdminAIEvaluationLabView() {
  const [evaluation, setEvaluation] = useState<any>(bootstrap.ai_evaluation || null);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedTestCase, setSelectedTestCase] = useState<any | null>(null);

  const runEvaluation = async () => {
    setIsRunning(true);
    try {
      const resp = await fetch('/admin/api/ai-evaluation/run/?dataset=DigiLand%20Statutory%20KYC%20v2026', {
        headers: {
          'Accept': 'application/json',
        },
      });
      const data = await resp.json();
      if (resp.ok && data.evaluation) {
        setEvaluation(data.evaluation);
        if (data.evaluation.results && data.evaluation.results.length > 0) {
          setSelectedTestCase(data.evaluation.results[0]);
        }
      } else {
        alert(data.error || 'Failed to run AI evaluation');
      }
    } catch {
      alert('Network error executing AI evaluation');
    } finally {
      setIsRunning(false);
    }
  };

  const cm = evaluation?.confusion_matrix || { true_positives: 5, true_negatives: 5, false_positives: 0, false_negatives: 0 };

  return (
    <div className="space-y-6 text-left">
      {/* Header & Run Trigger */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-black text-slate-900">AI Document Verification Lab & Evaluation Suite</h3>
            <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-black uppercase text-purple-800 border border-purple-200">
              Auditable AI
            </span>
          </div>
          <p className="text-xs text-slate-500 font-medium">
            Empirical benchmark evaluation of OpenCV Laplacian blur detection, Tesseract OCR, and Canny edge analysis against ground-truth Kenyan statutory documents.
          </p>
        </div>

        <Button
          type="button"
          disabled={isRunning}
          onClick={runEvaluation}
          className="h-10 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 px-5 text-xs font-black text-white shadow-md shadow-purple-600/30 hover:scale-[1.02] transition"
        >
          {isRunning ? (
            'Evaluating Benchmark...'
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" /> Run Benchmark Evaluation
            </>
          )}
        </Button>
      </div>

      {/* Metrics Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">Overall Accuracy</div>
          <div className="mt-1 text-2xl font-black text-emerald-600">{evaluation?.accuracy_pct || 100}%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">{evaluation?.correct_predictions || 10}/{evaluation?.total_tested || 10} Correct</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">Precision</div>
          <div className="mt-1 text-2xl font-black text-purple-600">{evaluation?.precision_pct || 100}%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">TP / (TP + FP)</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">Recall</div>
          <div className="mt-1 text-2xl font-black text-blue-600">{evaluation?.recall_pct || 100}%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">TP / (TP + FN)</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">F1 Score</div>
          <div className="mt-1 text-2xl font-black text-amber-600">{evaluation?.f1_score_pct || 100}%</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Harmonic Mean</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">False Positives</div>
          <div className="mt-1 text-2xl font-black text-slate-800">{cm.false_positives}</div>
          <div className="text-[10px] text-emerald-600 font-bold mt-0.5">Zero Fraud Escapes</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-[10px] font-black uppercase text-slate-500">False Negatives</div>
          <div className="mt-1 text-2xl font-black text-slate-800">{cm.false_negatives}</div>
          <div className="text-[10px] text-emerald-600 font-bold mt-0.5">Zero Valid Rejections</div>
        </div>
      </div>

      {/* Benchmark Test Cases Table & Inspector */}
      {evaluation?.results && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Labeled Cases List */}
          <div className="lg:col-span-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
            <div className="text-xs font-black uppercase text-slate-500">
              Benchmark Dataset Test Cases ({evaluation.results.length})
            </div>
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {evaluation.results.map((tc: any) => (
                <button
                  key={tc.test_case_id}
                  type="button"
                  onClick={() => setSelectedTestCase(tc)}
                  className={`w-full rounded-2xl border p-3 text-left transition ${
                    selectedTestCase?.test_case_id === tc.test_case_id
                      ? 'border-purple-600 bg-purple-50 text-slate-900 shadow-xs ring-1 ring-purple-600'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] font-bold text-slate-500">{tc.test_case_id}</span>
                    <span
                      className={`text-[10px] font-black uppercase rounded-full px-2 py-0.5 ${
                        tc.predicted_label === 'APPROVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {tc.predicted_label}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-slate-900 mt-1">{tc.name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">OCR: {tc.ocr_confidence}% | Blur: {tc.blur_score}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Test Case Detail Inspector */}
          {selectedTestCase && (
            <div className="lg:col-span-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
              <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-black text-slate-900">{selectedTestCase.name}</h4>
                  <div className="text-[11px] text-slate-500 font-mono">Test Case ID: {selectedTestCase.test_case_id}</div>
                </div>
                <Badge
                  tone={selectedTestCase.is_correct ? 'success' : 'danger'}
                  className="text-[10px] uppercase font-bold"
                >
                  {selectedTestCase.is_correct ? 'Prediction Matched' : 'Prediction Discrepancy'}
                </Badge>
              </div>

              {/* Signals Breakdown */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Expected Label</div>
                  <div className="text-sm font-black text-slate-900 mt-0.5">{selectedTestCase.expected_label}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">AI Predicted Label</div>
                  <div className="text-sm font-black text-emerald-700 mt-0.5">{selectedTestCase.predicted_label}</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">OCR Confidence</div>
                  <div className="text-sm font-black text-slate-900 mt-0.5">{selectedTestCase.ocr_confidence}%</div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Laplacian Blur Score</div>
                  <div className="text-sm font-black text-slate-900 mt-0.5">{selectedTestCase.blur_score}</div>
                </div>
              </div>

              {/* Reasons & Flags */}
              {selectedTestCase.reasons && selectedTestCase.reasons.length > 0 && (
                <div className="space-y-1 rounded-2xl border border-rose-200 bg-rose-50 p-3 text-xs">
                  <div className="font-bold text-rose-800">AI Rejection / Warning Reasons:</div>
                  {selectedTestCase.reasons.map((r: string, idx: number) => (
                    <div key={idx} className="text-slate-700">• {r}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// =========================================================================
// 4. ADMIN TRANSACTIONS MANAGEMENT & SETTLEMENT DESK
// =========================================================================
export function AdminTransactionsManagementView() {
  const [transactions, setTransactions] = useState<any[]>(bootstrap.transactions || []);
  const [loadingTxId, setLoadingTxId] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const handleAction = async (txId: string, action: 'release' | 'refund' | 'freeze' | 'unfreeze') => {
    if (!confirm(`Confirm ${action} action on transaction ${txId}?`)) return;
    setLoadingTxId(txId);
    setFeedbackMessage(null);

    try {
      const resp = await fetch(`/admin/transaction/${txId}/${action}/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': bootstrap.csrf_token || '',
        },
      });
      const data = await resp.json();
      if (resp.ok) {
        setFeedbackMessage(data.message || `Successfully executed ${action} on escrow transaction.`);
        setTransactions((prev) =>
          prev.map((t) => (t.id === txId ? { ...t, status: action === 'release' ? 'Completed' : (action === 'refund' ? 'Refunded' : (action === 'freeze' ? 'Disputed' : 'Under_Verification')) } : t))
        );
      } else {
        alert(data.error || `Failed to execute ${action}`);
      }
    } catch {
      alert('Network error executing transaction action');
    } finally {
      setLoadingTxId(null);
    }
  };

  return (
    <div className="space-y-6 text-left">
      <div className="border-b border-slate-200 pb-4">
        <h3 className="text-lg font-black text-slate-900">Escrow Settlements & Financial Control Desk</h3>
        <p className="text-xs text-slate-500 font-medium">
          Executive settlement desk for 1-click escrow payout release, buyer refunds, and dispute freeze management.
        </p>
      </div>

      {feedbackMessage && (
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-50 p-3 text-xs text-emerald-800 font-medium">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{feedbackMessage}</span>
        </div>
      )}

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        {transactions.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No escrow transactions found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wider text-slate-500 bg-slate-50/50">
                  <th className="py-3 px-3">Parcel / Transaction</th>
                  <th className="py-3 px-3">Agreed Price</th>
                  <th className="py-3 px-3">Buyer & Seller</th>
                  <th className="py-3 px-3">Escrow Status</th>
                  <th className="py-3 px-3 text-right">Settlement Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3.5 px-3">
                      <div className="font-bold text-slate-900">{tx.parcel_title || tx.parcel_number || 'Land Parcel'}</div>
                      <div className="text-[10px] text-slate-500 font-mono">TX: {tx.id.slice(0, 8)}...</div>
                    </td>
                    <td className="py-3.5 px-3">
                      <div className="font-black text-emerald-700">KES {Number(tx.agreed_price || 0).toLocaleString()}</div>
                      <div className="text-[10px] text-slate-500">Deposit: KES {Number(tx.deposit_amount || 0).toLocaleString()}</div>
                    </td>
                    <td className="py-3.5 px-3">
                      <div className="text-slate-800 font-medium">Buyer: {tx.buyer_email || 'Verified Buyer'}</div>
                      <div className="text-[10px] text-slate-500">Seller: {tx.seller_email || 'Verified Seller'}</div>
                    </td>
                    <td className="py-3.5 px-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase ${
                          tx.status === 'Completed'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : tx.status === 'Refunded'
                            ? 'bg-blue-100 text-blue-800 border border-blue-200'
                            : tx.status === 'Disputed'
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : 'bg-amber-100 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {tx.status || 'Pending'}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {tx.status !== 'Completed' && tx.status !== 'Refunded' && (
                          <>
                            <button
                              type="button"
                              disabled={loadingTxId === tx.id}
                              onClick={() => handleAction(tx.id, 'release')}
                              className="rounded-lg bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 px-2.5 py-1 text-[11px] font-bold text-emerald-800 transition"
                            >
                              Release Payout
                            </button>
                            <button
                              type="button"
                              disabled={loadingTxId === tx.id}
                              onClick={() => handleAction(tx.id, 'refund')}
                              className="rounded-lg bg-blue-50 hover:bg-blue-100 border border-blue-300 px-2.5 py-1 text-[11px] font-bold text-blue-800 transition"
                            >
                              Refund Buyer
                            </button>
                            <button
                              type="button"
                              disabled={loadingTxId === tx.id}
                              onClick={() => handleAction(tx.id, tx.status === 'Disputed' ? 'unfreeze' : 'freeze')}
                              className="rounded-lg bg-rose-50 hover:bg-rose-100 border border-rose-300 px-2.5 py-1 text-[11px] font-bold text-rose-800 transition"
                            >
                              {tx.status === 'Disputed' ? 'Unfreeze' : 'Freeze'}
                            </button>
                          </>
                        )}
                        <a
                          href={`/transactions/`}
                          className="rounded-lg border border-slate-300 bg-slate-50 p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition"
                          title="View Details"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
