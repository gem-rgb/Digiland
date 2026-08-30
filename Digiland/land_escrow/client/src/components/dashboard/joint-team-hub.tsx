import React, { useState, useEffect } from 'react';
import {
  Users,
  Vote,
  ShieldCheck,
  Plus,
  ArrowRight,
  CheckCircle2,
  XCircle,
  MessageSquare,
  Clock3,
  AlertTriangle,
  FileCheck,
  Building2,
  Trash2,
  Landmark,
  Layers,
  Sparkles,
} from 'lucide-react';
import { DigitalCrownAvatar } from '../ui/digital-crown-avatar.js';
import { Button } from '../ui/button.js';
import { Badge } from '../ui/badge.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Input } from '../ui/input.js';
import type { AccountSummary, AccountMemberSummary, AccountDecisionSummary, UserSummary } from '../../types.js';

interface JointTeamHubProps {
  initialAccount?: AccountSummary | null;
  currentUser?: UserSummary | null;
  csrfToken?: string;
}

export function JointTeamHub({ initialAccount, currentUser, csrfToken }: JointTeamHubProps) {
  const [account, setAccount] = useState<AccountSummary | null>(initialAccount || null);
  const [loading, setLoading] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState<'decisions' | 'members' | 'properties' | 'audit'>('decisions');

  // Proposal Creation Modal State
  const [showProposalModal, setShowProposalModal] = useState(false);
  const [proposalType, setProposalType] = useState<string>('PURCHASE_PROPOSAL');
  const [proposalTitle, setProposalTitle] = useState('');
  const [proposalText, setProposalText] = useState('');
  const [proposedAmount, setProposedAmount] = useState('');
  const [targetMemberId, setTargetMemberId] = useState('');

  // Invite Modal State
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePhone, setInvitePhone] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('CO_BUYER');
  const [inviteShare, setInviteShare] = useState('0');

  // Fetch / Refresh Account Feed
  const refreshAccount = async () => {
    if (!account?.id) return;
    try {
      const res = await fetch(`/api/v1/accounts/${account.id}/dashboard/`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        setAccount(data.account);
      }
    } catch (err) {
      console.error('Failed to refresh joint account:', err);
    }
  };

  // Cast Vote
  const handleVote = async (decisionId: string, voteChoice: 'APPROVE' | 'REJECT' | 'REQUEST_DISCUSSION', comment = '') => {
    try {
      const res = await fetch(`/api/v1/decisions/${decisionId}/vote/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({ vote: voteChoice, comment }),
      });
      const data = await res.json();
      if (res.ok) {
        await refreshAccount();
      } else {
        alert(data.error || 'Failed to submit vote.');
      }
    } catch (err: any) {
      alert(err.message || 'Error casting vote.');
    }
  };

  // Submit Proposal
  const handleCreateProposal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account?.id) return;
    setLoading(true);
    try {
      const res = await fetch('/api/v1/decisions/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          account: account.id,
          decision_type: proposalType,
          title: proposalTitle,
          proposal_text: proposalText,
          proposed_amount: proposedAmount ? parseFloat(proposedAmount) : null,
          target_member: targetMemberId || null,
          approval_rule: account.governance_rule || 'SIMPLE_MAJORITY',
        }),
      });
      if (res.ok) {
        setShowProposalModal(false);
        setProposalTitle('');
        setProposalText('');
        setProposedAmount('');
        setTargetMemberId('');
        await refreshAccount();
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to create proposal.');
      }
    } catch (err: any) {
      alert(err.message || 'Error creating proposal.');
    } finally {
      setLoading(false);
    }
  };

  // Submit Invitation
  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account?.id) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/accounts/${account.id}/invite-member/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          email: inviteEmail,
          phone_number: invitePhone,
          full_name: inviteName,
          role: inviteRole,
          share_percentage: inviteShare,
        }),
      });
      if (res.ok) {
        setShowInviteModal(false);
        setInviteEmail('');
        setInvitePhone('');
        setInviteName('');
        await refreshAccount();
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to send invitation.');
      }
    } catch (err: any) {
      alert(err.message || 'Error sending invite.');
    } finally {
      setLoading(false);
    }
  };

  const members = account?.members || [];
  const decisions = account?.decisions || [];
  const pendingDecisions = decisions.filter((d) => d.status === 'ACTIVE');

  return (
    <div className="space-y-6 text-left">
      {/* 1. HERO JOINT ACCOUNT HEADER */}
      <div className="rounded-3xl border border-emerald-200/80 bg-gradient-to-r from-emerald-950 via-slate-900 to-slate-950 p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 h-48 w-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[10px] font-black uppercase tracking-wider">
                {account?.entity_type_display || 'Human Joint Account'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-white/10 text-slate-300 font-mono text-[10px] font-bold">
                {members.length} Members
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 text-[10px] font-semibold">
                Governance: {account?.governance_rule === 'SIMPLE_MAJORITY' ? 'Simple Majority (>50%)' : 'Two-Thirds (≥66.7%)'}
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-2">
              {account?.display_name || 'My Joint Investment Group'}
            </h1>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Shared account with peer voting, digital crown leadership, and independent legal title protections under Kenyan land law.
            </p>
          </div>

          {/* Members Avatar Stack with Digital Crown Manager */}
          <div className="flex items-center gap-3 bg-white/5 backdrop-blur-md p-3 rounded-2xl border border-white/10 shrink-0">
            <div className="flex -space-x-3 overflow-hidden p-1">
              {members.map((m) => (
                <div key={m.id} className="relative">
                  <DigitalCrownAvatar
                    name={m.full_name || m.email || 'Member'}
                    isManager={m.is_account_leader}
                    roleTitle={m.role_display}
                    size="md"
                  />
                </div>
              ))}
            </div>
            <div className="border-l border-white/20 pl-3">
              <Button
                onClick={() => setShowInviteModal(true)}
                size="sm"
                className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold gap-1 h-8 px-3"
              >
                <Plus className="h-3.5 w-3.5" /> Invite
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. "DECISIONS AWAITING YOU" CALLOUT BANNER */}
      {pendingDecisions.length > 0 && (
        <div className="rounded-3xl border-2 border-amber-300 bg-amber-50/80 p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-500 text-white shadow-xs">
                <Vote className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-extrabold text-sm text-amber-950">
                  {pendingDecisions.length} Group Decision{pendingDecisions.length > 1 ? 's' : ''} Awaiting Review
                </h4>
                <p className="text-xs text-amber-900 mt-0.5">
                  Your vote is required to advance pending property purchase or group governance proposals.
                </p>
              </div>
            </div>
            <Button
              onClick={() => setActiveSubTab('decisions')}
              className="rounded-full bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shrink-0 self-start sm:self-center"
            >
              Review Decisions
            </Button>
          </div>
        </div>
      )}

      {/* 3. NAVIGATION SUB-TABS */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          {[
            { id: 'decisions', label: 'Decisions & Voting', count: pendingDecisions.length },
            { id: 'members', label: 'Team Members', count: members.length },
            { id: 'properties', label: 'Group Properties', count: 0 },
            { id: 'audit', label: 'Audit History', count: null },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveSubTab(tab.id as any)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
                activeSubTab === tab.id
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <span>{tab.label}</span>
              {tab.count !== null && tab.count > 0 && (
                <span className="rounded-full bg-emerald-500 text-white px-1.5 py-0.2 text-[9px] font-black">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        <Button
          onClick={() => setShowProposalModal(true)}
          className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold gap-1 h-9 px-4"
        >
          <Plus className="h-3.5 w-3.5" /> New Proposal
        </Button>
      </div>

      {/* 4. SUB-TAB CONTENT */}

      {/* TAB 1: DECISIONS & VOTING */}
      {activeSubTab === 'decisions' && (
        <div className="space-y-4">
          {decisions.length === 0 ? (
            <Card className="bg-white/90 border-slate-200">
              <CardContent className="p-8 text-center space-y-2">
                <Vote className="mx-auto h-10 w-10 text-slate-400" />
                <div className="text-base font-bold text-slate-800">No proposals created yet</div>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Create a purchase proposal, due diligence request, or member resolution for peer review.
                </p>
                <Button
                  onClick={() => setShowProposalModal(true)}
                  className="rounded-full bg-emerald-600 text-white text-xs font-bold mt-2"
                >
                  Create First Proposal
                </Button>
              </CardContent>
            </Card>
          ) : (
            decisions.map((decision) => {
              const totalVoters = decision.total_eligible_voters || 1;
              const approvedPct = Math.round((decision.approved_votes_count / totalVoters) * 100);
              const isApproved = decision.status === 'APPROVED';
              const isRejected = decision.status === 'REJECTED';

              return (
                <Card key={decision.id} className="bg-white border-slate-200 shadow-sm overflow-hidden">
                  <CardHeader className="bg-slate-50/70 border-b border-slate-100 p-4 sm:p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 text-[10px] font-bold uppercase">
                            {decision.decision_type_display}
                          </span>
                          <span className="text-xs text-slate-500 font-medium">
                            Proposed by {decision.created_by_email}
                          </span>
                        </div>
                        <CardTitle className="text-lg font-black text-slate-900">{decision.title}</CardTitle>
                      </div>

                      <Badge
                        tone={isApproved ? 'success' : isRejected ? 'danger' : 'warning'}
                        className="text-xs font-bold"
                      >
                        {decision.status_display}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="p-5 space-y-4">
                    <p className="text-xs text-slate-700 leading-relaxed font-normal">{decision.proposal_text}</p>

                    {decision.proposed_amount && (
                      <div className="rounded-2xl bg-emerald-50 border border-emerald-200/80 p-3 flex items-center justify-between text-xs">
                        <span className="font-bold text-emerald-900">Proposed Purchase Amount:</span>
                        <span className="font-black text-base text-emerald-700 font-mono">
                          KES {parseFloat(String(decision.proposed_amount)).toLocaleString()}
                        </span>
                      </div>
                    )}

                    {/* Voting Progress Bar */}
                    <div className="space-y-1.5 pt-2">
                      <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                        <span>Group Approvals: {decision.approved_votes_count} of {totalVoters} ({approvedPct}%)</span>
                        <span className="text-slate-500 font-normal">Threshold: {decision.approval_rule}</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            isApproved ? 'bg-emerald-600' : isRejected ? 'bg-rose-500' : 'bg-emerald-500'
                          }`}
                          style={{ width: `${approvedPct}%` }}
                        />
                      </div>
                    </div>

                    {/* Voting Action Buttons */}
                    {decision.status === 'ACTIVE' && (
                      <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-slate-100">
                        <Button
                          onClick={() => handleVote(decision.id, 'APPROVE')}
                          className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold gap-1"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                        </Button>
                        <Button
                          onClick={() => handleVote(decision.id, 'REJECT')}
                          variant="outline"
                          className="rounded-full border-rose-200 text-rose-700 hover:bg-rose-50 text-xs font-bold gap-1"
                        >
                          <XCircle className="h-3.5 w-3.5" /> Reject
                        </Button>
                        <Button
                          onClick={() => handleVote(decision.id, 'REQUEST_DISCUSSION')}
                          variant="ghost"
                          className="rounded-full text-slate-600 text-xs font-bold gap-1"
                        >
                          <MessageSquare className="h-3.5 w-3.5" /> Request Discussion
                        </Button>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* TAB 2: TEAM MEMBERS & PERMISSIONS */}
      {activeSubTab === 'members' && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {members.map((member) => (
              <Card key={member.id} className="bg-white border-slate-200 shadow-sm p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <DigitalCrownAvatar
                      name={member.full_name || member.email || 'Member'}
                      isManager={member.is_account_leader}
                      roleTitle={member.role_display}
                      size="lg"
                    />
                    <div>
                      <div className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
                        <span>{member.full_name}</span>
                        {member.is_account_leader && (
                          <span className="text-[10px] font-black uppercase text-emerald-700 bg-emerald-100 px-2 py-0.2 rounded-full">
                            Manager 👑
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500">{member.email || 'No email provided'}</div>
                      <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                        Role: {member.role_display} · Share: {member.share_percentage}%
                      </div>
                    </div>
                  </div>

                  {!member.is_account_leader && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setProposalType('MEMBER_REMOVAL');
                        setTargetMemberId(member.id);
                        setProposalTitle(`Propose Removal of ${member.full_name}`);
                        setProposalText(`Formal group proposal to vote on removing ${member.full_name} from the joint account.`);
                        setShowProposalModal(true);
                      }}
                      className="text-xs text-rose-600 hover:bg-rose-50 rounded-xl"
                    >
                      <Trash2 className="h-3.5 w-3.5 mr-1" /> Propose Exit
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: AUDIT HISTORY */}
      {activeSubTab === 'audit' && (
        <Card className="bg-white border-slate-200">
          <CardHeader>
            <CardTitle className="text-base font-bold text-slate-900">Immutable Account Audit Log</CardTitle>
            <CardDescription className="text-xs">
              Every vote, invitation, permission modification, and proposal is permanently logged.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 space-y-2">
            <div className="text-xs text-slate-600 divide-y divide-slate-100">
              {decisions.map((d) => (
                <div key={d.id} className="py-2.5 flex items-center justify-between">
                  <div>
                    <span className="font-bold text-slate-900">{d.title}</span>
                    <span className="text-slate-500 ml-2">Status: {d.status_display}</span>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono">{d.opened_at?.split('T')[0]}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* PROPOSAL MODAL */}
      {showProposalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
          <Card className="w-full max-w-lg bg-white border-slate-200 shadow-2xl rounded-3xl animate-in fade-in duration-200">
            <CardHeader className="border-b border-slate-100 p-5">
              <CardTitle className="text-lg font-black text-slate-900">Create Group Proposal</CardTitle>
              <CardDescription className="text-xs">
                Submit a formal proposal for team voting. All eligible members will be notified.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleCreateProposal} className="space-y-4 text-left">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Proposal Type</label>
                  <select
                    value={proposalType}
                    onChange={(e) => setProposalType(e.target.value)}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900"
                  >
                    <option value="PURCHASE_PROPOSAL">Property Purchase Proposal</option>
                    <option value="DUE_DILIGENCE_INITIATION">Initiate Due Diligence Request</option>
                    <option value="MEMBER_REMOVAL">Propose Member Removal</option>
                    <option value="CHANGE_MANAGER">Leadership Succession / Change Manager</option>
                    <option value="CUSTOM_PROPOSAL">Custom Group Resolution</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Proposal Title *</label>
                  <Input
                    required
                    placeholder="e.g. Purchase Approval for 2-Acre Kiambu Parcel LR 10294"
                    value={proposalTitle}
                    onChange={(e) => setProposalTitle(e.target.value)}
                    className="rounded-2xl"
                  />
                </div>

                {proposalType === 'PURCHASE_PROPOSAL' && (
                  <div>
                    <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Proposed Purchase Amount (KES)</label>
                    <Input
                      type="number"
                      placeholder="e.g. 4500000"
                      value={proposedAmount}
                      onChange={(e) => setProposedAmount(e.target.value)}
                      className="rounded-2xl"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Proposal Details & Rationale *</label>
                  <textarea
                    required
                    rows={3}
                    placeholder="Explain the proposal details and rationale for team approval..."
                    value={proposalText}
                    onChange={(e) => setProposalText(e.target.value)}
                    className="w-full rounded-2xl border border-slate-200 p-3 text-xs text-slate-900 focus:outline-hidden focus:border-emerald-500"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setShowProposalModal(false)}
                    className="rounded-full text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={loading}
                    className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
                  >
                    {loading ? 'Submitting...' : 'Publish for Voting'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {/* INVITE MODAL */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4">
          <Card className="w-full max-w-md bg-white border-slate-200 shadow-2xl rounded-3xl animate-in fade-in duration-200">
            <CardHeader className="border-b border-slate-100 p-5">
              <CardTitle className="text-lg font-black text-slate-900">Invite Co-Buyer to Group</CardTitle>
              <CardDescription className="text-xs">
                Invited members receive secure access to review properties and participate in votes.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleSendInvite} className="space-y-4 text-left">
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Full Legal Name</label>
                  <Input
                    placeholder="e.g. Mary Wanjiku"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    className="rounded-2xl"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Email Address *</label>
                  <Input
                    required
                    type="email"
                    placeholder="e.g. mary@example.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="rounded-2xl"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Phone Number (Optional)</label>
                  <Input
                    placeholder="e.g. +254712345678"
                    value={invitePhone}
                    onChange={(e) => setInvitePhone(e.target.value)}
                    className="rounded-2xl"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setShowInviteModal(false)}
                    className="rounded-full text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={loading}
                    className="rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
                  >
                    {loading ? 'Sending...' : 'Send Invitation'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
