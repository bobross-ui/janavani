import { Platform } from "react-native";
import Constants from "expo-constants";
import type { Grievance, GrievanceResponse, ClusterRead, ClusterDetail } from "./types";

const API_PORT = 8000;

// On a physical device, "localhost" is the device itself, not the dev machine.
// Expo's dev server already told the device the Mac's LAN host, so derive the
// API URL from it (works in Expo Go on a real phone without hardcoding an IP).
// Returns undefined under tunnel mode or a production build (no Metro host).
function devHostApiUrl(): string | undefined {
  const c = Constants as any;
  const hostUri: string | undefined =
    Constants.expoConfig?.hostUri ??
    c.expoGoConfig?.debuggerHost ??
    c.manifest2?.extra?.expoGo?.debuggerHost ??
    c.manifest?.debuggerHost;
  const host = hostUri?.split(":")[0];
  // Ignore tunnel hosts (e.g. *.exp.direct) — those only proxy Metro, not :8000.
  if (!host || host.endsWith(".exp.direct")) return undefined;
  return `http://${host}:${API_PORT}`;
}

// Resolution order: explicit env override → dev machine's LAN IP →
// emulator/simulator defaults.
const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  devHostApiUrl() ??
  Platform.select({
    android: `http://10.0.2.2:${API_PORT}`,
    default: `http://localhost:${API_PORT}`,
  });

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const fetchOptions: RequestInit = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  try {
    const res = await fetch(url, fetchOptions);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    return await res.json();
  } catch (e: any) {
    // Distinguish fetch-level error from HTTP error
    if (e instanceof TypeError || e?.message?.includes("Network")) {
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
