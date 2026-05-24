import { useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { getCluster } from "../../lib/api";
import { ClusterDetail } from "../../lib/types";

export default function ClusterScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    getCluster(id).then(setCluster).catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color="#2b6cb0" /></View>;
  if (error || !cluster) return <View style={styles.center}><Text style={styles.error}>{error || "Cluster not found"}</Text></View>;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{cluster.title}</Text>
      <View style={styles.metaRow}>
        <View style={styles.metaChip}><Text style={styles.metaText}>{cluster.issue_category}</Text></View>
        <View style={styles.metaChip}><Text style={styles.metaText}>Ward {cluster.ward}</Text></View>
        <View style={[styles.metaChip, cluster.urgency_score > 0.7 && styles.urgentChip]}>
          <Text style={[styles.metaText, cluster.urgency_score > 0.7 && styles.urgentText]}>
            {cluster.urgency_score > 0.7 ? "High urgency" : "Active"}
          </Text>
        </View>
      </View>
      <Text style={styles.summary}>{cluster.summary}</Text>
      <View style={styles.statsRow}>
        <View style={styles.stat}><Text style={styles.statNumber}>{cluster.grievance_count}</Text><Text style={styles.statLabel}>Reports</Text></View>
        <View style={styles.stat}><Text style={styles.statNumber}>{cluster.support_count}</Text><Text style={styles.statLabel}>Supporters</Text></View>
      </View>
      {cluster.sample_grievances.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Representative reports (redacted)</Text>
          {cluster.sample_grievances.map((g) => (
            <View key={g.id} style={styles.grievanceCard}>
              <Text style={styles.grievanceText}>{g.pii_redacted_text || g.normalized_text}</Text>
              <Text style={styles.grievanceMeta}>{g.language} &middot; {new Date(g.created_at).toLocaleDateString()}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 20 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  error: { color: "#e53e3e", fontSize: 14 },
  title: { fontSize: 22, fontWeight: "800", color: "#1a365d", marginBottom: 12 },
  metaRow: { flexDirection: "row", gap: 8, marginBottom: 16, flexWrap: "wrap" },
  metaChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, backgroundColor: "#E6F4FE" },
  urgentChip: { backgroundColor: "#fed7d7" },
  metaText: { fontSize: 12, color: "#2b6cb0" },
  urgentText: { color: "#c53030" },
  summary: { fontSize: 15, color: "#4a5568", lineHeight: 22, marginBottom: 16 },
  statsRow: { flexDirection: "row", gap: 24, marginBottom: 20 },
  stat: { alignItems: "center" },
  statNumber: { fontSize: 28, fontWeight: "800", color: "#2b6cb0" },
  statLabel: { fontSize: 12, color: "#718096" },
  section: { marginTop: 8 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#2d3748", marginBottom: 10 },
  grievanceCard: { backgroundColor: "#f7fafc", borderRadius: 8, padding: 12, marginBottom: 8 },
  grievanceText: { fontSize: 14, color: "#1a202c", marginBottom: 4 },
  grievanceMeta: { fontSize: 11, color: "#a0aec0" },
});
