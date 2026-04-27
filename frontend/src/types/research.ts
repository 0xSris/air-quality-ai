export type ResearchMode = "environment" | "company" | "person" | "market" | "job" | "product";
export type DepthMode = "quick" | "standard" | "deep";

export interface UserProfile {
  user_id: number;
  email: string;
  display_name: string;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: UserProfile;
}

export interface SessionSummary {
  session_id: string;
  title: string;
  mode: ResearchMode;
  depth: DepthMode;
  created_at: string;
  updated_at: string;
  pinned: boolean;
  bookmarked: boolean;
  compare_selected: boolean;
  tags: string[];
  latest_query?: string | null;
}

export interface ResearchMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SourceItem {
  source_id: string;
  title: string;
  source_type: string;
  snippet: string;
  credibility: number;
  url?: string | null;
  cluster?: string | null;
  agreement: "supports" | "mixed" | "weak";
  metadata?: Record<string, unknown> | null;
}

export interface AgentStep {
  step_id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "partial";
  summary: string;
  started_at: string;
  finished_at?: string | null;
  payload?: Record<string, unknown> | null;
}

export interface ConfidenceBreakdown {
  overall: number;
  data_quality: number;
  coverage: number;
  reasoning_strength: number;
}

export interface ClaimScore {
  claim: string;
  confidence: number;
  supporting_sources: string[];
  contradiction_sources: string[];
}

export interface ReportSection {
  key: string;
  title: string;
  content: string;
  sources: string[];
}

export interface ResearchReport {
  report_id: string;
  session_id: string;
  query: string;
  title: string;
  mode: ResearchMode;
  depth: DepthMode;
  overview: string;
  sections: ReportSection[];
  follow_ups: string[];
  sources: SourceItem[];
  claims: ClaimScore[];
  contradictions: string[];
  confidence: ConfidenceBreakdown;
  summary_markdown: string;
  created_at: string;
}

export interface SessionDetail {
  session: SessionSummary;
  messages: ResearchMessage[];
  reports: ResearchReport[];
  steps: AgentStep[];
}

export interface ResearchQueryResponse {
  session: SessionSummary;
  messages: ResearchMessage[];
  report: ResearchReport;
  steps: AgentStep[];
  degraded: boolean;
}

export interface ExportResponse {
  filename: string;
  format: "json" | "markdown" | "pdf";
  download_url: string;
}

export interface KnowledgeNode {
  node_id: string;
  label: string;
  group: "session" | "mode" | "tag" | "source";
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  weight: number;
}

export interface KnowledgeGraphResponse {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

export interface DashboardContext {
  site_id: number;
  station_label: string;
  selected_timestamp?: string | null;
  selected_label?: string | null;
  phase?: "live" | "forecast" | null;
  visible_o3: number;
  visible_no2: number;
  risk: string;
  horizon_hours: number;
  profile_focus: string;
  pollutant_focus: string;
  model_name: string;
  network_scope: "india" | "global";
  selected_city_key?: string | null;
  selected_city_name?: string | null;
  selected_city_label?: string | null;
  selected_city_o3?: number | null;
  selected_city_no2?: number | null;
  selected_city_aqi?: number | null;
  forecast_peak_o3: number;
  forecast_peak_no2: number;
  forecast_peak_o3_time: string;
  forecast_peak_no2_time: string;
  alert_count: number;
  top_alert_pollutant?: string | null;
  top_alert_severity?: string | null;
  baseline_avg_o3?: number | null;
  baseline_avg_no2?: number | null;
}
