export type PageKind =
  | 'landing'
  | 'dashboard'
  | 'parcel-list'
  | 'transactions'
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
  email: string;
  role: string;
  buyer_account_type?: string | null;
  is_identity_verified?: boolean;
  full_name?: string | null;
  phone_number?: string | null;
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

export interface CheckoutData {
  transaction_id: string;
  parcel_number: string;
  seller_email: string;
  buyer_email?: string;
  agreed_price: string;
  is_joint_purchase: boolean;
  joint_group_name?: string;
  joint_group_ownership?: string;
  joint_payment_method?: string;
  joint_bank_ready?: boolean;
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
  contract?: ContractData | null;
  checkout?: CheckoutData | null;
  messages_page?: MessagesPageData | null;
  support_page?: SupportPageData | null;
  status?: StatusPageData | null;
  recommendations_page?: RecommendationsPageData | null;
  prediction_page?: PredictionPageData | null;
  task_board?: TaskManagementData | null;
  approvals_page?: ApprovalsPageData | null;
  user_review?: UserReviewPageData | null;
  parcels?: ParcelSummary[];
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
  [key: string]: any;
}
