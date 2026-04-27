export interface SiteSummary {
  site_id: number;
  latitude: number;
  longitude: number;
  train_rows: number;
  unseen_rows: number;
  train_start: string;
  train_end: string;
}

export interface DatasetSummaryResponse {
  total_sites: number;
  total_train_rows: number;
  total_unseen_rows: number;
  features: string[];
  targets: string[];
  sites: SiteSummary[];
}

export interface PollutantPoint {
  timestamp: string;
  o3: number;
  no2: number;
  source: string;
  us_aqi?: number | null;
  european_aqi?: number | null;
}

export interface TrendResponse {
  site_id: number;
  points: PollutantPoint[];
}

export interface ForecastPoint {
  timestamp: string;
  o3: number;
  no2: number;
  o3_lower: number;
  o3_upper: number;
  no2_lower: number;
  no2_upper: number;
}

export interface ForecastResponse {
  site_id: number;
  horizon_hours: number;
  model_name: string;
  generated_at: string;
  points: ForecastPoint[];
}

export interface LiveResponse {
  site_id: number;
  current: PollutantPoint;
  recent: PollutantPoint[];
  playback_position: number;
  mode: string;
  provider: string;
  source_label: string;
  fallback_used: boolean;
  last_updated: string;
}

export interface LiveNetworkLocation {
  key: string;
  name: string;
  country: string;
  region: string;
  latitude: number;
  longitude: number;
  current: PollutantPoint;
  recent: PollutantPoint[];
  provider: string;
  source_label: string;
  fallback_used: boolean;
  last_updated: string;
}

export interface LiveNetworkResponse {
  scope: "india" | "global";
  generated_at: string;
  locations: LiveNetworkLocation[];
}

export interface AlertItem {
  site_id: number;
  pollutant: "O3" | "NO2";
  severity: "info" | "warning" | "critical";
  message: string;
  timestamp: string;
  value: number;
  threshold: number;
}

export interface AlertsResponse {
  site_id?: number;
  alerts: AlertItem[];
}

export interface ModelMetadataResponse {
  active_model: string;
  available_models: string[];
  metrics: Record<string, Record<string, Record<string, number>>>;
  feature_columns: string[];
  model_feature_columns?: Record<string, string[]>;
  training_data_sources?: string[];
  external_feature_columns?: string[];
  targets: string[];
}
