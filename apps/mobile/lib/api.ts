import { Platform } from "react-native";
import type { Grievance, GrievanceResponse, ClusterRead, ClusterDetail } from "./types";

const BASE_URL = Platform.select({
  android: "http://10.0.2.2:8000",
  ios: "http://192.168.29.73:8000",
  default: "http://192.168.29.73:8000",
});

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
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

export function getCluster(id: string): Promise<ClusterDetail> {
  return request<ClusterDetail>(`/clusters/${id}`);
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

export async function requestTTS(body: {
  text: string;
  language: string;
}): Promise<string> {
  const res = await fetch(`${BASE_URL}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  // Convert the audio response to a blob and then to a local data URI
  // that expo-av can play via Audio.Sound.createAsync.
  const arrayBuffer = await res.arrayBuffer();
  const base64 = arrayBufferToBase64(arrayBuffer);
  // Assume the server returns audio/mpeg or audio/wav; default to mp3.
  const contentType = res.headers.get("content-type") || "audio/mpeg";
  return `data:${contentType};base64,${base64}`;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function btoa(input: string): string {
  const base64Chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let output = "";
  const bytes = new Uint8Array(input.length);
  for (let i = 0; i < input.length; i++) {
    bytes[i] = input.charCodeAt(i) & 0xff;
  }
  const len = bytes.length;
  for (let i = 0; i < len; i += 3) {
    const b1 = bytes[i];
    const b2 = i + 1 < len ? bytes[i + 1] : 0;
    const b3 = i + 2 < len ? bytes[i + 2] : 0;
    const enc1 = b1 >> 2;
    const enc2 = ((b1 & 3) << 4) | (b2 >> 4);
    const enc3 = ((b2 & 15) << 2) | (b3 >> 6);
    const enc4 = b3 & 63;
    output += base64Chars[enc1] + base64Chars[enc2];
    if (i + 1 < len) output += base64Chars[enc3];
    else output += "=";
    if (i + 2 < len) output += base64Chars[enc4];
    else output += "=";
  }
  return output;
}

export function listMyGrievances(userId: string): Promise<Grievance[]> {
  return request<Grievance[]>(`/grievances?user_id=${encodeURIComponent(userId)}&limit=50`);
}
