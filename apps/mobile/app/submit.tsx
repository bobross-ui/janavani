import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity } from "react-native";
import * as Location from "expo-location";
import { AudioRecorder } from "../components/audio-recorder";
import { ClusterSuggestionCard } from "../components/cluster-suggestion-card";
import { GrievanceForm } from "../components/grievance-form";
import { TranscriptReview } from "../components/transcript-review";
import { submitGrievance, uploadAudioGrievance } from "../lib/api";
import type { GrievanceResponse } from "../lib/types";

const MOCK_USER_ID = "demo-user-1";
const MOCK_PHONE = "9876543210";

export default function SubmitScreen() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("hi-Latn");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GrievanceResponse | null>(null);
  const [error, setError] = useState("");
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [locationConsent, setLocationConsent] = useState<string | null>(null); // "granted" | "denied"

  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationConsent(status);
      if (status === "granted") {
        try {
          const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
          setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        } catch {
          // GPS may be unavailable; submit without location fallback
        }
      }
    })();
  }, []);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await submitGrievance({
        user_id: MOCK_USER_ID,
        text: text.trim(),
        language,
        consent_public: true,
        ...(coords ? { latitude: coords.latitude, longitude: coords.longitude } : {}),
      });
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleAudioComplete = async (uri: string) => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("audio", {
        uri,
        type: "audio/m4a",
        name: "recording.m4a",
      } as any);
      formData.append("user_id", MOCK_USER_ID);
      formData.append("consent_public", "true");
      if (coords) {
        formData.append("latitude", String(coords.latitude));
        formData.append("longitude", String(coords.longitude));
      }

      const res = await uploadAudioGrievance(formData);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <GrievanceForm
        text={text}
        onTextChange={setText}
        language={language}
        onLanguageChange={setLanguage}
        phone={MOCK_PHONE}
        loading={loading}
        onSubmit={handleSubmit}
      />

      {/* Location status chip */}
      {locationConsent === "granted" && coords ? (
        <Text style={styles.locationChip}>
          📍 Location used — {coords.latitude.toFixed(4)}, {coords.longitude.toFixed(4)}
        </Text>
      ) : locationConsent === "denied" ? (
        <TouchableOpacity
          onPress={async () => {
            const { status } = await Location.requestForegroundPermissionsAsync();
            setLocationConsent(status);
          }}
        >
          <Text style={styles.locationChip}>
            📍 Location not shared — tap to enable
          </Text>
        </TouchableOpacity>
      ) : null}

      <AudioRecorder onRecordingComplete={handleAudioComplete} />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {result ? (
        <>
          <TranscriptReview extraction={result.extraction} />
          <ClusterSuggestionCard
            action={result.suggested_action}
            clusterId={result.matched_cluster_id}
            clusterTitle={result.matched_cluster_title}
            userId={MOCK_USER_ID}
            grievanceId={result.grievance.id}
          />
          <TouchableOpacity
            style={styles.viewReportsButton}
            onPress={() => router.push("/profile")}
          >
            <Text style={styles.viewReportsText}>View My Reports</Text>
          </TouchableOpacity>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 20 },
  locationChip: {
    fontSize: 12,
    color: "#4a5568",
    backgroundColor: "#edf2f7",
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    alignSelf: "flex-start",
    marginBottom: 16,
  },
  error: {
    color: "#e53e3e",
    marginTop: 12,
    fontSize: 14,
    backgroundColor: "#fff5f5",
    padding: 12,
    borderRadius: 8,
  },
  viewReportsButton: {
    backgroundColor: "#E6F4FE",
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 12,
  },
  viewReportsText: { color: "#2b6cb0", fontSize: 15, fontWeight: "600" },
});