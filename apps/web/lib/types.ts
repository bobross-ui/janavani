export interface GrievanceRead {
  id: string;
  user_id: string;
  raw_text: string;
  transcript_text: string;
  normalized_text: string;
  language: string;
  issue_category: string;
  department: string;
  urgency: string;
  ward: string;
  landmark: string;
  latitude: number | null;
  longitude: number | null;
  pii_redacted_text: string;
  cluster_id: string | null;
  status: string;
  consent_public: boolean;
  created_at: string;
}

export interface ClusterRead {
  id: string;
  title: string;
  summary: string;
  issue_category: string;
  department: string;
  ward: string;
  landmark: string;
  status: string;
  support_count: number;
  grievance_count: number;
  urgency_score: number;
  centroid_latitude: number | null;
  centroid_longitude: number | null;
  created_at: string;
  updated_at: string;
}

export interface RedactedGrievanceSample {
  id: string;
  language: string;
  issue_category: string;
  department: string;
  urgency: string;
  ward: string;
  landmark: string;
  pii_redacted_text: string;
  status: string;
  created_at: string;
}

export interface ClusterDetail extends ClusterRead {
  sample_grievances: RedactedGrievanceSample[];
}

export interface ComplaintDraftRead {
  id: string;
  cluster_id: string;
  title: string;
  body: string;
  department: string;
  language: string;
  source_grievance_ids: string;
  status: string;
  created_at: string;
}

export interface DashboardStats {
  totalClusters: number;
  totalReports: number;
  totalSupporters: number;
  urgentClusters: number;
  openClusters: number;
}
