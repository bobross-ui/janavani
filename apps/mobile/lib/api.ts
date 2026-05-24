import {
  Grievance,
  GrievanceResponse,
  ClusterRead,
  ClusterDetail,
  ComplaintDraft,
} from "./types";

const BASE_URL = "http://10.0.2.2:8000"; // Android emulator → host machine

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export function submitGrievance(body: {
  user_id: string;
  text: string;
  language: string;
  consent_public: boolean;
}): Promise<GrievanceResponse> {
  return request<GrievanceResponse>("/grievances", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getGrievance(id: string): Promise<Grievance> {
  return request<Grievance>(`/grievances/${id}`);
}

export function listClusters(params?: {
  ward?: string;
  category?: string;
  status?: string;
}): Promise<ClusterRead[]> {
  const query = new URLSearchParams();
  if (params?.ward) query.set("ward", params.ward);
  if (params?.category) query.set("category", params.category);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return request<ClusterRead[]>(`/clusters${qs ? `?${qs}` : ""}`);
}

export function getCluster(id: string): Promise<ClusterDetail> {
  return request<ClusterDetail>(`/clusters/${id}`);
}

export function supportCluster(
  clusterId: string,
  body: { user_id: string; grievance_id: string; consent_to_file: boolean }
): Promise<{ status: string; support_count: number }> {
  return request<{ status: string; support_count: number }>(
    `/clusters/${clusterId}/support`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export function generateDraft(clusterId: string): Promise<ComplaintDraft> {
  return request<ComplaintDraft>(`/admin/clusters/${clusterId}/draft`, {
    method: "POST",
  });
}
