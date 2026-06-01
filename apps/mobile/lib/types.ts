export interface ExtractionResult {
  category: string;
  department: string;
  urgency: string;
  ward: string;
  landmark: string;
  language: string;
  normalized_text: string;
  pii_redacted_text: string;
}

export interface Grievance {
  id: string;
  user_id: string;
  raw_text: string;
  normalized_text: string;
  language: string;
  issue_category: string;
  department: string;
  urgency: string;
  ward: string;
  landmark: string;
  pii_redacted_text: string;
  cluster_id: string | null;
  status: string;
  consent_public: boolean;
  audio_key?: string;
  created_at: string;
}

export interface GrievanceResponse {
  grievance: Grievance;
  extraction: ExtractionResult;
  matched_cluster_id: string | null;
  matched_cluster_title: string | null;
  suggested_action: "create_cluster" | "join_cluster";
}

export interface ClusterRead {
  id: string;
  title: string;
  summary: string;
  issue_category: string;
  department: string;
  ward: string;
  area: string;
  area_source: string;
  suburb: string;
  road: string;
  sector: string;
  landmark: string;
  status: string;
  support_count: number;
  grievance_count: number;
  urgency_score: number;
  centroid_latitude: number | null;
  centroid_longitude: number | null;
  created_at: string;
}

export interface ClusterDetail extends ClusterRead {
  sample_grievances: Grievance[];
  viewer_has_supported: boolean;
}
