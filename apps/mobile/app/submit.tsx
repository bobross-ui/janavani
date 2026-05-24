import { useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { submitGrievance } from "../lib/api";

const MOCK_USER_ID = "demo-user-1";

export default function SubmitScreen() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("hi-Latn");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<null | { category: string; department: string; ward: string; urgency: string; action: string; clusterTitle: string | null }>(null);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await submitGrievance({ user_id: MOCK_USER_ID, text: text.trim(), language, consent_public: true });
      setResult({ category: res.extraction.category, department: res.extraction.department, ward: res.extraction.ward, urgency: res.extraction.urgency, action: res.suggested_action, clusterTitle: res.matched_cluster_title });
    } catch (e: any) {
      setError(e.message || "Failed to submit");
    } finally { setLoading(false); }
  };

  return (
    <ScrollView style={styles.container} keyboardShouldPersistTaps="handled">
      <Text style={styles.label}>Phone number</Text>
      <TextInput style={styles.input} value="9876543210" editable={false} />
      <Text style={styles.label}>Language</Text>
      <View style={styles.langRow}>
        {[{ key: "hi-Latn", label: "Hinglish" }, { key: "hi", label: "Hindi" }, { key: "mr", label: "Marathi" }, { key: "ta", label: "Tamil" }].map((l) => (
          <TouchableOpacity key={l.key} style={[styles.langChip, language === l.key && styles.langChipActive]} onPress={() => setLanguage(l.key)}>
            <Text style={[styles.langChipText, language === l.key && styles.langChipTextActive]}>{l.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={styles.label}>Your grievance</Text>
      <TextInput style={[styles.input, styles.textArea]} multiline numberOfLines={5} placeholder="Describe the issue..." value={text} onChangeText={setText} />
      <TouchableOpacity style={[styles.button, loading && styles.buttonDisabled]} onPress={handleSubmit} disabled={loading || !text.trim()}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Submit grievance</Text>}
      </TouchableOpacity>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {result && (
        <View style={styles.resultCard}>
          <Text style={styles.resultTitle}>Result</Text>
          <View style={styles.resultRow}><Text style={styles.resultLabel}>Category:</Text><Text style={styles.resultValue}>{result.category}</Text></View>
          <View style={styles.resultRow}><Text style={styles.resultLabel}>Department:</Text><Text style={styles.resultValue}>{result.department}</Text></View>
          <View style={styles.resultRow}><Text style={styles.resultLabel}>Ward:</Text><Text style={styles.resultValue}>{result.ward || "N/A"}</Text></View>
          <View style={styles.resultRow}><Text style={styles.resultLabel}>Urgency:</Text><Text style={styles.resultValue}>{result.urgency}</Text></View>
          {result.action === "join_cluster" && result.clusterTitle ? (
            <View style={styles.clusterMatch}>
              <Text style={styles.clusterMatchText}>Similar issue found: "{result.clusterTitle}" - Join to add your voice.</Text>
              <TouchableOpacity style={styles.joinButton}><Text style={styles.joinButtonText}>Join this cluster</Text></TouchableOpacity>
            </View>
          ) : result.action === "create_cluster" ? (
            <Text style={styles.newClusterText}>New issue detected. A cluster will be created for this.</Text>
          ) : null}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 20 },
  label: { fontSize: 14, fontWeight: "600", color: "#4a5568", marginBottom: 6, marginTop: 12 },
  input: { borderWidth: 1, borderColor: "#cbd5e0", borderRadius: 10, padding: 14, fontSize: 16, backgroundColor: "#f7fafc" },
  textArea: { height: 120, textAlignVertical: "top" },
  langRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  langChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: "#cbd5e0" },
  langChipActive: { backgroundColor: "#2b6cb0", borderColor: "#2b6cb0" },
  langChipText: { fontSize: 13, color: "#4a5568" },
  langChipTextActive: { color: "#fff" },
  button: { backgroundColor: "#2b6cb0", paddingVertical: 16, borderRadius: 12, alignItems: "center", marginTop: 24 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  error: { color: "#e53e3e", marginTop: 12, fontSize: 14 },
  resultCard: { marginTop: 24, backgroundColor: "#f0fff4", borderRadius: 12, padding: 16, borderWidth: 1, borderColor: "#c6f6d5" },
  resultTitle: { fontSize: 16, fontWeight: "700", color: "#22543d", marginBottom: 8 },
  resultRow: { flexDirection: "row", marginBottom: 4 },
  resultLabel: { fontSize: 14, fontWeight: "500", color: "#4a5568", width: 100 },
  resultValue: { fontSize: 14, color: "#1a202c" },
  clusterMatch: { marginTop: 12, backgroundColor: "#ebf8ff", borderRadius: 8, padding: 12 },
  clusterMatchText: { fontSize: 14, color: "#2b6cb0", marginBottom: 8 },
  joinButton: { backgroundColor: "#2b6cb0", paddingVertical: 12, borderRadius: 8, alignItems: "center" },
  joinButtonText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  newClusterText: { marginTop: 12, fontSize: 14, color: "#22543d", fontStyle: "italic" },
});
