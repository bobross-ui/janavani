import { Platform } from "react-native";
import type { Grievance, GrievanceResponse, ClusterRead, ClusterDetail } from "./types";

const BASE_URL = Platform.select({
  android: "http://10.0.2.2:8000",
  ios: "http://192.168.29.73:8000",
  default: "http://192.168.29.73:8000",
});

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const fetchOptions: RequestInit = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  console.log("[api] request", url, fetchOptions.method || "GET");
  try {
    const res = await fetch(url, fetchOptions);
    if (!res.ok) {
      const text = await res.text();
      console.log("[api] request FAIL", res.status, text.slice(0, 200));
      throw new Error(`${res.status}: ${text}`);
    }
    const data = await res.json();
    console.log("[api] request OK", res.status, typeof data, Array.isArray(data) ? `[${data.length} items]` : "");
    return data;
  } catch (e: any) {
    // Distinguish fetch-level error from HTTP error
    if (e instanceof TypeError || e?.message?.includes("Network")) {
      console.log("[api] request NETWORK ERROR:", { url, message: e?.message, name: e?.name, cause: e?.cause });
      throw new Error(`Network error: ${e?.message} (${url})`);
    }
    throw e;
  }
}

export function submitGrievance(body: {
  user_id: string; text: string; language: string; consent_public: boolean;
  latitude?: number; longitude?: number;
}): Promise<GrievanceResponse> {
  return request<GrievanceResponse>("/grievances", { method: "POST", body: JSON.stringify(body) });
}

export function getGrievance(id: string): Promise<Grievance> {
  return request<Grievance>(`/grievances/${id}`);
}

export function listClusters(params?: { ward?: string; category?: string; status?: string }): Promise<ClusterRead[]> {
  const query = new URLSearchParams();
  if (params?.ward) query.set("ward", params.ward);
  if (params?.category) query.set("category", params.category);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return request<ClusterRead[]>(`/clusters${qs ? `?${qs}` : ""}`);
}

export function getCluster(id: string, userId?: string): Promise<ClusterDetail> {
  const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return request<ClusterDetail>(`/clusters/${id}${qs}`);
}

export function supportCluster(
  clusterId: string, body: { user_id: string; grievance_id: string; consent_to_file: boolean }
): Promise<{ status: string; support_count: number }> {
  return request(`/clusters/${clusterId}/support`, { method: "POST", body: JSON.stringify(body) });
}

export async function uploadAudioGrievance(formData: FormData): Promise<GrievanceResponse> {
  const res = await fetch(`${BASE_URL}/grievances/audio`, {
    method: "POST",
    body: formData,
    // No Content-Type header so browser/RN sets multipart boundary.
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export function listMyGrievances(userId: string): Promise<Grievance[]> {
  return request<Grievance[]>(`/grievances?user_id=${encodeURIComponent(userId)}&limit=50`);
}
