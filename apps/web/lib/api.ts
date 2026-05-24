import type { ClusterDetail, ClusterRead, ComplaintDraftRead } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

export function listClusters(filters?: {
  ward?: string;
  category?: string;
  status?: string;
}): Promise<ClusterRead[]> {
  const params = new URLSearchParams();
  if (filters?.ward) params.set("ward", filters.ward);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.status) params.set("status", filters.status);
  const query = params.toString();
  return request<ClusterRead[]>(`/clusters${query ? `?${query}` : ""}`);
}

export function getCluster(id: string): Promise<ClusterDetail> {
  return request<ClusterDetail>(`/clusters/${id}`);
}

export function listAdminClusters(): Promise<ClusterRead[]> {
  return request<ClusterRead[]>("/admin/clusters");
}

export function createComplaintDraft(clusterId: string): Promise<ComplaintDraftRead> {
  return request<ComplaintDraftRead>(`/admin/clusters/${clusterId}/draft`, {
    method: "POST",
  });
}

export function updateClusterStatus(clusterId: string, status: string): Promise<{ id: string; status: string }> {
  const params = new URLSearchParams({ status });
  return request<{ id: string; status: string }>(`/admin/clusters/${clusterId}/status?${params.toString()}`, {
    method: "PATCH",
  });
}

export { API_BASE_URL };
