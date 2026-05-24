import { useState } from "react";
import { ScrollView, StyleSheet, Text } from "react-native";
import { AudioRecorder } from "../components/audio-recorder";
import { ClusterSuggestionCard } from "../components/cluster-suggestion-card";
import { GrievanceForm } from "../components/grievance-form";
import { TranscriptReview } from "../components/transcript-review";
import { submitGrievance } from "../lib/api";
import type { GrievanceResponse } from "../lib/types";

const MOCK_USER_ID = "demo-user-1";
const MOCK_PHONE = "9876543210";

export default function SubmitScreen() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("hi-Latn");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GrievanceResponse | null>(null);
  const [error, setError] = useState("");

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
      });
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
      <AudioRecorder />
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
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 20 },
  error: {
    color: "#e53e3e",
    marginTop: 12,
    fontSize: 14,
    backgroundColor: "#fff5f5",
    padding: 12,
    borderRadius: 8,
  },
});
