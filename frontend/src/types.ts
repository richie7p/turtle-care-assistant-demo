export interface PublicConfig {
  app_name: string;
  app_short_name: string;
  app_icon: string;
  app_tagline: string;
  app_description: string;
  assistant_name: string;
  knowledge_label: string;
  profile_label: string;
  welcome_title: string;
  welcome_description: string;
  disclaimer: string;
  enable_turtle_module: boolean;
  ai_provider: string;
  ai_configured: boolean;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "admin";
  created_at: string;
}

export interface Attachment {
  id: string;
  original_name: string;
  media_type: string;
  size_bytes: number;
  purpose: string;
  created_at: string;
  url?: string;
}

export interface Turtle {
  id: string;
  user_id: string;
  name: string;
  species: string;
  turtle_type: "aquatic" | "terrestrial";
  age?: string;
  sex: "male" | "female" | "unknown";
  shell_length_cm?: number;
  weight_g?: number;
  habitat?: string;
  placement?: "indoor" | "outdoor";
  enclosure_size?: string;
  has_uvb?: boolean;
  has_heater?: boolean;
  diet?: string;
  notes?: string;
  photo?: Attachment;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  turtle_id?: string;
  turtle_name?: string;
  title: string;
  summary?: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  document_id: string;
  chunk_id: string;
  title: string;
  source_name: string;
  source_url: string;
  section: string;
  rank: number;
  score: number;
}

export interface Message {
  id: string;
  user_id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  status: string;
  created_at: string;
  attachments: Attachment[];
  citations: Citation[];
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface KnowledgeDocument {
  id: string;
  slug: string;
  title: string;
  description: string;
  source_url: string;
  source_name: string;
  reviewed_at: string;
  tags: string[];
  chunk_count: number;
}

export interface UserSettings {
  theme: "light" | "dark" | "system";
  response_style: "concise" | "balanced" | "detailed";
  default_turtle_id?: string;
}

export interface AdminStats {
  users: number;
  active_users: number;
  admins: number;
  turtles: number;
  conversations: number;
  message_count: number;
  conversations_today: number;
  ai_requests_today: number;
  ai_errors_today: number;
  ai_success_rate_today?: number;
  input_tokens_today: number;
  output_tokens_today: number;
  estimated_cost_today?: number;
  cost_configured: boolean;
  feature_usage: Record<string, number>;
  model: string;
  vision_model: string;
  embedding_model: string;
  configured: boolean;
  last_success_at?: string;
  last_latency_ms?: number;
  knowledge_documents: number;
  knowledge_chunks: number;
  embedded_chunks: number;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
  last_login_at?: string;
  turtle_count: number;
  conversation_count: number;
  message_count: number;
  ai_request_count: number;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUsage {
  id: string;
  request_id: string;
  user_id?: string;
  user_email?: string;
  feature: string;
  provider: string;
  model: string;
  input_tokens?: number;
  output_tokens?: number;
  usage_estimated: boolean;
  estimated_cost?: number;
  latency_ms?: number;
  status: string;
  error_code?: string;
  created_at: string;
}

export interface AdminUsageList {
  items: AdminUsage[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminKnowledgeItem {
  id: string;
  slug: string;
  title: string;
  is_active: boolean;
  reviewed_at: string;
  chunk_count: number;
  embedded_chunks: number;
  updated_at: string;
}

export interface AdminKnowledgeStatus {
  items: AdminKnowledgeItem[];
  documents: number;
  active_documents: number;
  chunks: number;
  embedded_chunks: number;
  embedding_model: string;
}

export interface AdminAudit {
  id: string;
  actor_user_id?: string;
  actor_email?: string;
  action: string;
  target_type: string;
  target_id?: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AdminAuditList {
  items: AdminAudit[];
  total: number;
}

export interface AdminProviderHealth {
  reachable: boolean;
  status: string;
  message: string;
  latency_ms?: number;
  chat_model_available: boolean;
  vision_model_available: boolean;
  embedding_model_available: boolean;
  checked_at: string;
}

export interface AdminSystemInfo {
  app_env: string;
  database_backend: string;
  session_days: number;
  ai_requests_per_minute: number;
  ai_per_user_concurrency: number;
  ai_global_concurrency: number;
  max_input_chars: number;
  max_image_bytes: number;
  max_images_per_message: number;
  context_recent_messages: number;
  summary_trigger_messages: number;
}
