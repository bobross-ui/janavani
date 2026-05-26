import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { listClusters } from "../lib/api";
import type { ClusterRead } from "../lib/types";
import { ClusterMap } from "../../components/cluster-map";

export default function ClustersScreen() {
  const router = useRouter();
  const [clusters, setClusters] = useState<ClusterRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listClusters()
      .then(setClusters)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2b6cb0" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={clusters}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      ListHeaderComponent={
        <ClusterMap clusters={clusters} tappable />
      }
      ListEmptyComponent={
        <View style={styles.center}>
          <Text style={styles.empty}>No clusters yet.</Text>
          <Text style={styles.emptySub}>Submit a grievance to create one.</Text>
        </View>
      }
      renderItem={({ item }) => (
        <TouchableOpacity
          style={styles.card}
          onPress={() => router.push(`/cluster/${item.id}`)}
        >
          <Text style={styles.title}>{item.title}</Text>
          <View style={styles.metaRow}>
            <View style={styles.chip}>
              <Text style={styles.chipText}>{item.issue_category}</Text>
            </View>
            <View style={styles.chip}>
              <Text style={styles.chipText}>Ward {item.ward}</Text>
            </View>
            {item.urgency_score > 0.7 && (
              <View style={[styles.chip, styles.urgentChip]}>
                <Text style={[styles.chipText, styles.urgentText]}>Urgent</Text>
              </View>
            )}
          </View>
          <Text style={styles.summary} numberOfLines={2}>
            {item.summary}
          </Text>
          <View style={styles.stats}>
            <Text style={styles.stat}>{item.grievance_count} reports</Text>
            <Text style={styles.stat}>{item.support_count} supporters</Text>
          </View>
        </TouchableOpacity>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 20 },
  error: { color: "#e53e3e", fontSize: 14 },
  empty: { fontSize: 16, fontWeight: "600", color: "#4a5568" },
  emptySub: { fontSize: 13, color: "#a0aec0", marginTop: 4 },
  list: { padding: 16, gap: 12 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  title: { fontSize: 16, fontWeight: "700", color: "#1a365d", marginBottom: 8 },
  metaRow: { flexDirection: "row", gap: 6, marginBottom: 8 },
  chip: {
    backgroundColor: "#E6F4FE",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  chipText: { fontSize: 11, color: "#2b6cb0" },
  urgentChip: { backgroundColor: "#fed7d7" },
  urgentText: { color: "#c53030" },
  summary: { fontSize: 13, color: "#4a5568", lineHeight: 18, marginBottom: 8 },
  stats: { flexDirection: "row", gap: 16 },
  stat: { fontSize: 12, color: "#718096" },
});
