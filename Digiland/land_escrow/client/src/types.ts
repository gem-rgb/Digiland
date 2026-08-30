export type PageKind =
  | 'landing'
  | 'dashboard'
  | 'parcel-list'
  | 'transactions'
  | 'seller-promotions'
  | 'promotion-tiers'
  | 'sponsored-ads'
  | 'buyer-choice'
  | 'legal'
  | 'joint-laws'
  | 'joint-groups'
  | 'joint-group-detail'
  | 'content'
  | 'form'
  | 'staff-login'
  | 'agent-kyc'
  | 'ai-kyc'
  | 'agent-onboarding'
  | 'temp-approve'
  | 'task-management'
  | 'approvals'
  | 'user-review'
  | 'parcel-detail'
  | 'lawyer-checklist'
  | 'commission-detail'
  | 'agent-job-board'
  | 'agent-commission-steps'
  | 'messages'
  | 'support'
  | 'contract'
  | 'contract-fullpage'
  | 'payment-onboarding'
  | 'checkout'
  | 'checkout-fullpage'
  | 'status'
  | 'recommendations'
  | 'price-prediction'
  | 'admin-dashboard'
  | 'agent-dashboard'
  | 'lawyer-dashboard'
  | 'surveyor-dashboard'
  | 'seller-withdraw'
  | 'escrow-release'
  | 'agent-withdraw'
  | 'finance'
  | 'admin-withdraw'
  | 'message-thread'
  | 'simple';

export interface NavItem {
  label: string;
  href: string;
  icon?: string;
  active?: boolean;
}

export interface UserSummary {
  id?: string;
  email: string;
  role: string;
  buyer_account_type?: string | null;
  is_identity_verified?: boolean;
  is_onboarded?: boolean;
  is_superuser?: boolean;
  is_staff?: boolean;
  full_name?: string | null;
  phone_number?: string | null;
  is_account_manager?: boolean;
  primary_account_id?: string | null;
  primary_account_name?: string | null;
  primary_account_type?: 'INDIVIDUAL' | 'JOINT' | 'ORGANIZATION' | null;
  primary_entity_type?: string | null;
}

export interface AccountMemberSummary {
  id: string;
  account: string;
  account_name?: string;
  user?: string | null;
  role: string;
  role_display: string;
  status: string;
  status_display: string;
  full_name: string;
  email?: string | null;
  phone_number?: string | null;
  id_number?: string | null;
  kra_pin?: string | null;
  share_percentage: number | string;
  is_account_leader: boolean;
  joined_at?: string | null;
}

export interface DecisionVoteSummary {
  id: string;
  decision: string;
  voter: string;
  voter_name: string;
  account_member: string;
  member_name: string;
  vote: 'APPROVE' | 'REJECT' | 'REQUEST_DISCUSSION';
  vote_display: string;
  comment?: string | null;
  voted_at: string;
}

export interface AccountDecisionSummary {
  id: string;
  account: string;
  account_name?: string;
  land_parcel?: string | null;
  transaction?: string | null;
  decision_type: string;
  decision_type_display: string;
  title: string;
  proposal_text: string;
  proposed_amount?: number | string | null;
  target_member?: string | null;
  target_member_name?: string | null;
  approval_rule: string;
  status: 'ACTIVE' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | 'CANCELLED' | 'EXECUTED' | 'LEGAL_HOLD';
  status_display: string;
  created_by_email?: string;
  opened_at: string;
  deadline?: string | null;
  closed_at?: string | null;
  votes: DecisionVoteSummary[];
  total_eligible_voters: number;
  approved_votes_count: number;
  rejected_votes_count: number;
  discussion_requests_count: number;
}

export interface AccountSummary {
  id: string;
  account_type: 'INDIVIDUAL' | 'JOINT' | 'ORGANIZATION';
  account_type_display: string;
  purpose: 'BUY' | 'SELL' | 'BOTH';
  purpose_display: string;
  entity_type: string;
  entity_type_display: string;
  display_name: string;
  legal_name?: string | null;
  registration_number?: string | null;
  tax_id_or_kra_pin?: string | null;
  status: string;
  status_display: string;
  governance_rule: string;
  members: AccountMemberSummary[];
  active_members_count: number;
  decisions: AccountDecisionSummary[];
  created_at: string;
}

export interface ReviewUserSummary extends UserSummary {
  id: string;
  is_active?: boolean;
  id_number?: string | null;
  phone_number?: string | null;
  kra_pin?: string | null;
  joined_at?: string | null;
  role_label?: string;
}


export interface ActionLink {
  label: string;
  href: string;
  tone?: 'default' | 'secondary' | 'outline' | 'ghost' | 'accent';
  external?: boolean;
}

export interface StatusChip {
  label: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'muted';
}

export interface StatCardData {
  label: string;
  value: string;
  tone?: 'default' | 'success' | 'warning' | 'accent';
}

export interface FormChoice {
  value: string;
  label: string;
  selected?: boolean;
  disabled?: boolean;
}

export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'number' | 'tel' | 'file' | 'textarea' | 'select' | 'checkbox' | 'radio' | 'hidden' | 'url';
  value?: string;
  checked?: boolean;
  placeholder?: string;
  helpText?: string;
  required?: boolean;
  disabled?: boolean;
  rows?: number;
  min?: string;
  max?: string;
  step?: string;
  accept?: string;
  options?: FormChoice[];
  errors?: string[];
  autoFocus?: boolean;
}

export interface FormSection {
  title?: string;
  subtitle?: string;
  fields: FormField[];
}

export interface SerializedForm {
  action: string;
  method?: string;
  enctype?: string;
  submitLabel: string;
  cancelLabel?: string;
  cancelHref?: string;
  intro?: string;
  sections?: FormSection[];
  fields?: FormField[];
  hiddenFields?: Array<{ name: string; value: string }>;
  managementFields?: Array<{ name: string; value: string }>;
  csrf_token?: string;
  formsetRows?: Array<{
    index: number;
    fields: FormField[];
    hiddenFields?: Array<{ name: string; value: string }>;
    deleteField?: FormField;
  }>;
  errors?: string[];
}

export interface ParcelSummary {
  parcel_number: string;
  county: string;
  constituency: string;
  ward?: string;
  land_size: string;
  land_use_type: string;
  verification_status: string;
  image_url?: string | null;
  details_url: string;
  manage_label?: string;
  manage_url?: string;
  status_badge?: string;
  asking_price?: string | null;
  displayed_price?: string | null;
  promotion_tier?: string | null;
  is_promoted?: boolean;
  latitude?: string | null;
  longitude?: string | null;
  google_maps_url?: string | null;
}

export interface ParcelDocumentSummary {
  id: string;
  document_type: string;
  document_label: string;
  verification_status: string;
  uploaded_at: string;
  file_url?: string | null;
}

export interface TransactionSummary {
  id: string;
  parcel_number: string;
  role_label: string;
  amount: string;
  status: string;
  status_tone?: 'success' | 'warning' | 'danger' | 'muted' | 'default';
  created_at: string;
  action_label: string;
  action_url: string;
  is_joint_purchase?: boolean;
  joint_label?: string;
}

export interface CommissionStep {
  key: string;
  status: string;
  label: string;
  description: string;
  completed: boolean;
  active: boolean;
  state: 'complete' | 'current' | 'upcoming' | 'skipped';
}

export interface CommissionDocumentSummary {
  id: string;
  document_type: string;
  document_label: string;
  verification_status: string;
  uploaded_at: string;
}

export interface CommissionSummary {
  id: string;
  status: string;
  status_label: string;
  status_tone?: 'success' | 'warning' | 'danger' | 'muted' | 'accent';
  buyer?: UserSummary | null;
  accepted_by?: UserSummary | null;
  accepted_at?: string | null;
  assigned_lawyer?: UserSummary | null;
  lawyer_submitted_at?: string | null;
  lawyer_verified?: boolean | null;
  lawyer_verification_note?: string;
  lawyer_verified_at?: string | null;
  documents_reviewed?: boolean;
  documents_review_note?: string;
  documents_reviewed_at?: string | null;
  site_visit_date?: string | null;
  site_visit_location?: string;
  site_visit_notes?: string;
  site_visit_complete?: boolean;
  site_visit_completed_at?: string | null;
  transaction_id?: string | null;
  transaction_status?: string | null;
  closed_at?: string | null;
  is_joint_purchase?: boolean;
  joint_group?: JointGroupSummary | null;
  target_county: string;
  target_constituency: string;
  created_at: string;
  updated_at: string;
  parcel: ParcelSummary;
  documents: CommissionDocumentSummary[];
  document_count: number;
  required_documents: Array<{ title: string; key: string; required: boolean; description: string }>;
  steps: CommissionStep[];
  detail_url: string;
  accept_url: string;
  steps_url: string;
  review_url?: string | null;
  transaction_url?: string | null;
  step_action_urls: {
    documents_review: string;
    submit_to_lawyer: string;
    lawyer_verdict: string;
    schedule_site_visit: string;
    complete_site_visit: string;
    close: string;
  };
  can_accept?: boolean;
  can_work?: boolean;
  can_review_documents?: boolean;
  can_submit_to_lawyer?: boolean;
  can_schedule_site_visit?: boolean;
  can_complete_site_visit?: boolean;
  can_close?: boolean;
  can_review_as_lawyer?: boolean;
  is_buyer?: boolean;
  is_agent?: boolean;
  is_lawyer?: boolean;
  is_admin?: boolean;
}

export interface CommissionBoardData {
  region_county?: string | null;
  region_constituency?: string | null;
  region_source?: string | null;
  open_count: number;
  commissions: CommissionSummary[];
}

export interface LawSummary {
  title: string;
  citation: string;
  applies_to: string;
  summary: string;
  official_url: string;
  required: boolean;
}

export interface JointMemberSummary {
  id: string;
  full_name: string;
  share_percentage: string;
  phone_number: string;
  email?: string | null;
  id_number?: string | null;
  kra_pin?: string | null;
  is_leader?: boolean;
  has_signed?: boolean;
  signature_status?: string;
  edit_url?: string;
  delete_url?: string;
}

export interface JointGroupSummary {
  id: string;
  name: string;
  group_type: string;
  ownership_type: string;
  preferred_payment_method: string;
  bank_name?: string | null;
  bank_account_name?: string | null;
  bank_account_number?: string | null;
  bank_branch?: string | null;
  total_share: string;
  is_valid: boolean;
  members: JointMemberSummary[];
  detail_url: string;
  edit_url: string;
  laws_url: string;
  add_member_url?: string | null;
  transfer_leadership_url?: string | null;
  can_manage?: boolean;
  is_group_leader?: boolean;
  can_view_members?: boolean;
}

export interface BreakdownRow {
  member_name: string;
  member_id?: string;
  share_percentage: string;
  amount: string;
  phone_number?: string;
}

export interface ContributionSummary {
  member_name: string;
  amount: string;
  channel: string;
  status: string;
  phone_number?: string | null;
  bank_reference?: string | null;
  depositor_name?: string | null;
}

export interface FeeBreakdownLine {
  key: string;
  label: string;
  amount: string;
  description: string;
  note?: string | null;
  included?: boolean;
  tone?: 'default' | 'success' | 'warning' | 'muted';
}

export interface FeeExplanation {
  label: string;
  percent?: string;
  amount?: string;
  what: string;
  why: string;
}

export interface CheckoutData {
  transaction_id: string;
  parcel_number: string;
  seller_email: string;
  buyer_email?: string;
  agreed_price: string;
  land_price?: string;
  is_joint_purchase: boolean;
  joint_group_name?: string;
  joint_group_ownership?: string;
  joint_payment_method?: string;
  joint_bank_ready?: boolean;
  platform_service_fee?: string;
  escrow_fee?: string;
  processing_fee?: string;
  legal_verification_fee?: string;
  due_diligence_fee?: string;
  include_legal_verification?: boolean;
  include_due_diligence?: boolean;
  fee_breakdown?: FeeBreakdownLine[];
  fee_explanations?: Record<string, FeeExplanation>;
  grand_total?: string;
  total_payable?: string;
  breakdown: BreakdownRow[];
  contributions: ContributionSummary[];
  phone_number: string;
  csrf_token: string;
  process_url: string;
  transactions_url: string;
  sign_url?: string;
  failed_url?: string;
  default_payment_method?: 'm_pesa' | 'joint_bank_account';
  bank_name?: string | null;
  bank_account_name?: string | null;
  bank_account_number?: string | null;
  bank_branch?: string | null;
  paystack_enabled?: boolean;
  escrow_bank_name?: string | null;
  escrow_bank_account_name?: string | null;
  escrow_bank_account_number?: string | null;
  escrow_bank_branch?: string | null;
}

export interface ContractBreakdownRow {
  member: JointMemberSummary;
  amount: string;
}

export interface ContractDocumentSummary {
  key: string;
  title: string;
  description: string;
  content: string;
  required: boolean;
}

export interface ContractData {
  transaction_id: string;
  parcel_number: string;
  buyer_email: string;
  seller_email: string;
  agreed_price: string;
  contract_agreed: boolean;
  transaction_status: string;
  checkout_available: boolean;
  buyer_signature_present: boolean;
  seller_signature_present: boolean;
  is_joint_purchase: boolean;
  joint_group_name?: string | null;
  joint_group_ownership?: string | null;
  joint_breakdown: ContractBreakdownRow[];
  documents: ContractDocumentSummary[];
  laws: LawSummary[];
  current_user_role: string;
  current_user_is_buyer: boolean;
  current_user_is_seller: boolean;
  current_user_is_admin: boolean;
  current_user_is_joint_leader: boolean;
  sign_url: string;
  payment_url: string;
  transactions_url: string;
  csrf_token: string;
  signature_data_name?: string;
  admin_dual_sign?: boolean;
  [key: string]: any;
}

export interface MessageThreadMessage {
  id: string;
  sender_email: string;
  content: string;
  timestamp: string;
  is_self: boolean;
}

export interface MessageThreadSummary {
  partner: UserSummary;
  latest_timestamp: string;
  count: number;
  messages: MessageThreadMessage[];
}

export interface MessagesPageData {
  mode: 'single' | 'dual';
  header: string;
  threads: MessageThreadSummary[];
  buyer_threads?: MessageThreadSummary[];
  seller_threads?: MessageThreadSummary[];
  allowed_recipients: UserSummary[];
  msg_error?: string | null;
  compose_action: string;
  csrf_token: string;
}

export interface SupportTicketSummary {
  id: string;
  subject: string;
  message_excerpt: string;
  status: string;
  created_at: string;
}

export interface SupportPageData {
  tickets: SupportTicketSummary[];
  create_action: string;
  csrf_token: string;
}

export interface StatusPageData {
  icon?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'muted';
  title: string;
  description: string;
  primary_action?: ActionLink;
  secondary_action?: ActionLink;
  extra_actions?: ActionLink[];
}

export interface ContentSection {
  kicker?: string;
  title: string;
  body: string;
  bullets?: string[];
  actions?: ActionLink[];
}

export interface ContentPageData {
  hero?: {
    kicker?: string;
    title: string;
    subtitle?: string;
    badge?: string;
  };
  sections: ContentSection[];
}

export interface RecommendationParcelSummary extends ParcelSummary {
  match_score?: number;
}

export interface RecommendationsPageData {
  rec_type: string;
  recommended: RecommendationParcelSummary[];
  popular_county: string;
  popular_parcels: ParcelSummary[];
  recently_viewed: ParcelSummary[];
  recently_viewed_similar?: ParcelSummary[];
  hot_deals?: ParcelSummary[];
  trending_in_target_area?: ParcelSummary[];
  people_also_viewed?: ParcelSummary[];
  sponsored_listings?: ParcelSummary[];
}

export interface PopupCampaignParcelSummary {
  parcel_number: string;
  county: string;
  constituency: string;
  ward: string;
  land_size: string;
  land_use_type: string;
  verification_status: string;
  image_url?: string | null;
  displayed_price: string;
  asking_price?: string | null;
  details_url: string;
}

export interface PopupAdSellerSummary {
  email: string;
  role: string;
  is_verified: boolean;
  trust_score: number;
  label: string;
}

export interface PopupAdBudgetSummary {
  daily_budget: string;
  total_budget: string;
  spent_amount: string;
  remaining_budget: string;
  priority_bid: string;
  billing_model: string;
  billing_model_label: string;
}

export interface PopupAdMetricSummary {
  impressions: number;
  clicks: number;
  leads: number;
  dismissals: number;
  ctr: number;
  lead_rate: number;
  spend: string;
  revenue: string;
  roi: number;
  quality_score: number;
  engagement_score: number;
  auction_score: number;
  seller_trust_score: number;
}

export interface PopupAdCampaignSummary {
  id: string;
  campaign_name: string;
  popup_type: string;
  popup_type_label: string;
  billing_model: string;
  billing_model_label: string;
  status: string;
  status_label: string;
  status_tone?: 'success' | 'warning' | 'muted' | 'default';
  headline: string;
  subheadline: string;
  cta_text: string;
  landing_url: string;
  creative_image_url?: string | null;
  creative_video_url?: string | null;
  parcel: PopupCampaignParcelSummary;
  seller: PopupAdSellerSummary;
  targeting: {
    counties: string[];
    locations: string[];
    buyer_categories: string[];
    intent_tags: string[];
    budget_min?: string | null;
    budget_max?: string | null;
    acreage_min?: string | null;
    acreage_max?: string | null;
    travel_radius_km: number;
    geo_exclusive: boolean;
  };
  frequency: {
    frequency_cap_per_session: number;
    cooldown_minutes: number;
    duration_days: number;
    geo_exclusive: boolean;
  };
  budget: PopupAdBudgetSummary;
  metrics: PopupAdMetricSummary;
  amenities: Array<{ label: string; value: string }>;
  score: number;
  match_reasons: string[];
  trigger?: 'smart' | 'geo' | 'urgency' | 'retargeting' | 'exit_intent' | null;
  social_proof: string[];
  scarcity_text: string;
  created_at: string;
  updated_at: string;
  display_delay_ms?: number;
}

export interface PopupAdsPayload {
  enabled: boolean;
  page: PageKind | string;
  placement?: string;
  intent_score?: number;
  intent_label?: string;
  buyer_category?: string;
  county?: string | null;
  constituency?: string | null;
  ward?: string | null;
  recommended_delay_ms?: number;
  frequency_cap_per_session?: number;
  session_show_count?: number;
  candidates: Record<'smart' | 'geo' | 'urgency' | 'retargeting' | 'exit_intent', PopupAdCampaignSummary[]>;
  primary?: PopupAdCampaignSummary | null;
  exit_candidate?: PopupAdCampaignSummary | null;
  recent_search_terms?: string[];
  suppressed_reason?: string | null;
  reason?: string | null;
}

export interface PopupDashboardSummary {
  total_campaigns: number;
  active_campaigns: number;
  paused_campaigns: number;
  draft_campaigns: number;
  total_impressions: number;
  total_clicks: number;
  total_leads: number;
  total_dismissals: number;
  ctr: number;
  lead_rate: number;
  total_spend: string;
  total_revenue: string;
  roi: number;
}

export interface PopupHeatmapRow {
  county: string;
  impressions: number;
  clicks: number;
  leads: number;
  dismissals: number;
}

export interface PopupTriggerBreakdownRow {
  popup_type: string;
  impressions: number;
  clicks: number;
  leads: number;
}

export interface SellerPromotionsPageData {
  summary: PopupDashboardSummary;
  campaigns: PopupAdCampaignSummary[];
  heatmap: PopupHeatmapRow[];
  trigger_breakdown: PopupTriggerBreakdownRow[];
  recommendations: Array<{ title: string; body: string }>;
  supported_popup_types: string[];
  supported_billing_models: string[];
  events_count: number;
  campaign_action_url: string;
  form: SerializedForm;
}

export interface PredictionComparisonSummary {
  constituency: string;
  county: string;
  land_use: string;
  size_acres: string;
  price_per_acre: string;
}

export interface PredictionResultSummary {
  error?: string;
  county?: string;
  constituency?: string;
  town?: string;
  land_use?: string;
  size_acres?: string;
  price_per_acre?: string;
  total_value?: string;
  confidence_low?: string;
  confidence_high?: string;
  model_accuracy?: string;
  comparisons?: PredictionComparisonSummary[];
}

export interface PredictionPageData {
  counties: string[];
  land_use_types: string[];
  form: SerializedForm;
  model_info?: {
    n_records: string;
    n_counties: string;
    algorithm: string;
  } | null;
  prediction?: PredictionResultSummary | null;
}

export interface ParcelDetailData {
  parcel_number: string;
  image_url?: string | null;
  land_use_type: string;
  county: string;
  constituency: string;
  ward: string;
  land_size: string;
  registered_owner_id_masked: string;
  verification_status: string;
  status_tone?: 'success' | 'warning' | 'danger' | 'muted' | 'default';
  displayed_price: string;
  is_favorited: boolean;
  ai_price?: {
    total_value: string;
    price_per_acre: string;
    confidence_low: string;
    confidence_high: string;
  } | null;
  documents: ParcelDocumentSummary[];
  can_edit: boolean;
  can_upload_document: boolean;
  can_initiate_escrow: boolean;
  can_use_joint_purchase: boolean;
  assigned_agent_email?: string | null;
  joint_groups?: JointGroupSummary[];
  purchase_modes?: Array<{ value: string; label: string; selected?: boolean }>;
  initiate_escrow_url: string;
  upload_document_url?: string | null;
  edit_url?: string | null;
  delete_url?: string | null;
  toggle_favorite_url?: string | null;
  agent_verify_url?: string | null;
  access_locked?: boolean;
  request_access_url?: string | null;
  confirm_access_url?: string | null;
  latitude?: string | null;
  longitude?: string | null;
  google_maps_url?: string | null;
}

export interface TaskManagementData {
  pending_parcels: ParcelSummary[];
  completed_parcels: ParcelSummary[];
  pending_transactions: TransactionSummary[];
  pending_users: ReviewUserSummary[];
  pending_agents: ReviewUserSummary[];
  verified_agents: ReviewUserSummary[];
  unassigned_count?: number;
}

export interface ApprovalsPageData {
  pending_users: ReviewUserSummary[];
  pending_parcels: ParcelSummary[];
  pending_transactions: TransactionSummary[];
  pending_joint_removals?: JointMemberRemovalRequestSummary[];
  pending_commissions?: CommissionSummary[];
}

export interface JointMemberRemovalRequestSummary {
  id: string;
  group_id: string;
  group_name: string;
  member: JointMemberSummary;
  requested_by?: UserSummary | null;
  consent_confirmed: boolean;
  compensation_confirmed: boolean;
  compensation_amount?: string | null;
  notes?: string | null;
  status: string;
  status_label?: string;
  admin_reviewed_by?: UserSummary | null;
  admin_reviewed_at?: string | null;
  admin_notes?: string | null;
  created_at: string;
  approve_url: string;
  reject_url: string;
}

export interface UserReviewPageData {
  reviewed_user: ReviewUserSummary;
  user_parcels?: ParcelSummary[];
  user_transactions?: TransactionSummary[];
}

export interface PromotionTierFeature {
  label: string;
  included: boolean;
  detail?: string;
}

export interface PromotionTierData {
  id: string;
  name: string;
  slug: string;
  tier_level: number;
  monthly_price: string;
  features_json: PromotionTierFeature[];
  active: boolean;
}

export interface PromotionPlanData {
  id: string;
  tier: PromotionTierData;
  tier_name: string;
  status: string;
  is_active: boolean;
  auto_renew: boolean;
  start_date: string;
  end_date: string;
}

export interface PromotionTiersPageData {
  tiers: PromotionTierData[];
  current_plan: PromotionPlanData | null;
  seller_email: string;
}

export interface SponsoredAdEngagementSummary {
  impressions: number;
  clicks: number;
  saves: number;
  inquiries: number;
  shares: number;
}

export interface SponsoredAdSummary {
  id: string;
  parcel_number: string;
  parcel: { parcel_number: string; county: string; asking_price: string; image_url: string | null } | null;
  tier: string;
  title: string;
  description: string;
  status: string;
  billing_model: string;
  budget_daily: string | null;
  budget_total: string | null;
  budget_spent: string;
  is_active: boolean;
  engagement_summary: SponsoredAdEngagementSummary;
  starts_at: string;
  ends_at: string;
  created_at: string;
}

export interface SponsoredAdsPageData {
  campaigns: SponsoredAdSummary[];
  parcels: Array<{ id: string; parcel_number: string; county: string; asking_price: string }>;
  total_active: number;
  total_spent: string;
  total_impressions: number;
  total_clicks: number;
}

export interface BootstrapData {
  page: PageKind;
  title: string;
  subtitle?: string;
  user?: UserSummary | null;
  nav: NavItem[];
  logout_url?: string;
  csrf_token?: string;
  actions?: ActionLink[];
  content_key?: string;
  content?: ContentPageData | null;
  form?: SerializedForm | null;
  member_formset?: SerializedForm | null;
  parcel_detail?: ParcelDetailData | null;
  commission_detail?: CommissionSummary | null;
  commission_steps?: CommissionSummary | null;
  agent_job_board?: CommissionBoardData | null;
  commissions?: CommissionSummary[];
  active_commissions?: CommissionSummary[];
  commission_reviews?: CommissionSummary[];
  open_commissions?: CommissionSummary[];
  contract?: ContractData | null;
  checkout?: CheckoutData | null;
  messages_page?: MessagesPageData | null;
  support_page?: SupportPageData | null;
  status?: StatusPageData | null;
  recommendations_page?: RecommendationsPageData | null;
  popup_ads?: PopupAdsPayload | null;
  seller_promotions_page?: SellerPromotionsPageData | null;
  promotion_tiers_page?: PromotionTiersPageData | null;
  sponsored_ads_page?: SponsoredAdsPageData | null;
  prediction_page?: PredictionPageData | null;
  task_board?: TaskManagementData | null;
  approvals_page?: ApprovalsPageData | null;
  user_review?: UserReviewPageData | null;
  parcels?: ParcelSummary[];
  search_query?: string;
  search_active?: boolean;
  post_transaction_tasks?: Array<{ key: string; label: string; completed: boolean; notes?: string; evidence_url?: string }>;
  transaction_id?: string;
  transactions?: TransactionSummary[];
  laws?: LawSummary[];
  checklist?: string[];
  payment_guidance?: string[];
  groups?: JointGroupSummary[];
  group?: JointGroupSummary | null;
  stats?: StatCardData[];
  messages?: { level: string; text: string }[];
  notice?: string;
  document_content?: string | null;
  fullpage_sign_url?: string;
  back_url?: string;
  require_signature?: boolean;
  fullpage_mode?: boolean;
  kyc_status_url?: string;
  kyc_submit_url?: string;
  kyc_manual_url?: string;
  kyc_login_url?: string;
  withdraw_data?: any;
  escrow_transactions?: any[];
  finance_dashboard?: any;
  finance_pin_verified?: boolean;
  finance_verify_url?: string;
  admin_withdraw_url?: string;
  pending_agent_applications?: any[];
  individual_buyers?: any[];
  message_thread?: any;
  is_admin?: boolean;
  surveyor_profile?: SurveyorProfileData | null;
  assignments?: SurveyAssignmentData[];
  survey_findings?: SurveyAssignmentData[];
  active_assignments_count?: number;
  scheduled_visits_count?: number;
  pending_reports_count?: number;
  open_issues_count?: number;
  completed_surveys_count?: number;
  overdue_surveys_count?: number;
  counties?: string[];
  [key: string]: any;
}

export interface SurveyBeaconData {
  id: string;
  beacon_id: string;
  status: string;
  status_display: string;
  condition: string;
  condition_display: string;
  latitude?: number | null;
  longitude?: number | null;
  easting?: number | null;
  northing?: number | null;
  elevation_meters?: number | null;
  description?: string;
  photo_url?: string | null;
  notes?: string;
  created_at?: string;
}

export interface SurveyBoundaryData {
  id: string;
  segment: string;
  segment_display: string;
  neighbouring_parcel_reference?: string;
  physical_feature: string;
  physical_feature_display: string;
  condition_description?: string;
  consistency_status: string;
  consistency_status_display: string;
  observation_notes?: string;
  photo_url?: string | null;
  created_at?: string;
}

export interface SurveyMeasurementData {
  id: string;
  point_id: string;
  eastings?: number | null;
  northings?: number | null;
  elevation?: number | null;
  distance_meters?: number | null;
  bearing_degrees?: string;
  instrument_method?: string;
  accuracy_quality_note?: string;
  surveyor_notes?: string;
  created_at?: string;
}

export interface SurveyDocumentData {
  id: string;
  title: string;
  document_type: string;
  document_type_display: string;
  source_type: string;
  source_type_display: string;
  visibility: string;
  visibility_display: string;
  file_url?: string | null;
  file_format?: string;
  file_size_bytes?: number;
  version: number;
  description?: string;
  uploaded_by_email?: string;
  created_at?: string;
}

export interface SurveyIssueData {
  id: string;
  issue_number: string;
  issue_type: string;
  issue_type_display: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | string;
  severity_display: string;
  status: 'OPEN' | 'UNDER_INVESTIGATION' | 'RESOLVED' | 'WAIVED' | string;
  status_display: string;
  title: string;
  description: string;
  evidence_notes?: string;
  photo_url?: string | null;
  surveyor_recommendation?: string;
  assigned_to_email?: string;
  resolution_notes?: string;
  resolved_at?: string;
  created_at?: string;
}

export interface SurveyReportData {
  id: string;
  version: number;
  surveyor_email: string;
  surveyor_name: string;
  conclusion: string;
  conclusion_display: string;
  summary_findings: string;
  boundary_findings: string;
  area_comparison_notes: string;
  site_observations: string;
  discrepancies_summary: string;
  professional_declaration_signed: boolean;
  signed_at?: string;
  submission_timestamp?: string;
  review_status: string;
  review_status_display: string;
  reviewer_email?: string;
  reviewer_feedback?: string;
  reviewed_at?: string;
  created_at?: string;
}

export interface SurveyAuditLogData {
  id: string;
  action: string;
  user_email: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface SurveyAssignmentData {
  id: string;
  assignment_number: string;
  parcel_number: string;
  parcel_id: string;
  county: string;
  constituency?: string;
  ward?: string;
  land_use?: string;
  seller_email: string;
  surveyor_email: string;
  surveyor_name: string;
  surveyor_license?: string;
  assignment_type: string;
  assignment_type_display: string;
  status: string;
  status_display: string;
  priority: string;
  priority_display: string;
  instructions?: string;
  assigned_at?: string;
  due_date?: string;
  due_date_iso?: string;
  accepted_at?: string;
  completed_at?: string;
  is_overdue?: boolean;
  site_visit_date?: string;
  site_visit_time?: string;
  site_visit_status: string;
  site_visit_status_display: string;
  site_visit_contact_name?: string;
  site_visit_contact_phone?: string;
  site_visit_assistant_names?: string;
  site_visit_notes?: string;
  device_gps_lat?: number | null;
  device_gps_lng?: number | null;
  device_gps_accuracy_meters?: number | null;
  pre_survey_checklist?: Record<string, boolean>;
  completeness_pct?: number;
  documented_area_acres?: number | null;
  documented_area_sqm?: number | null;
  calculated_area_sqm?: number | null;
  area_discrepancy_detected?: boolean;
  area_discrepancy_percentage?: number | null;
  internal_notes?: string;
  beacons: SurveyBeaconData[];
  boundary_observations: SurveyBoundaryData[];
  measurements: SurveyMeasurementData[];
  documents: SurveyDocumentData[];
  issues: SurveyIssueData[];
  reports: SurveyReportData[];
  audit_logs: SurveyAuditLogData[];
  accept_url: string;
  schedule_visit_url: string;
  add_beacon_url: string;
  add_boundary_url: string;
  add_measurement_url: string;
  upload_document_url: string;
  add_issue_url: string;
  submit_report_url: string;
}

export interface SurveyorProfileData {
  full_name: string;
  email: string;
  license_number: string;
  firm: string;
  county: string;
  is_verified: boolean;
  phone_number?: string;
}
