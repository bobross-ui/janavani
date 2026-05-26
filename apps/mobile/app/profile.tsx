import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { listMyGrievances } from "../lib/api";
import type { Grievance } from "../lib/types";

const USER_ID = "demo-user-1";

function statusColor(status: string): string {
  if (status === "clustered") return "#38a169";
  if (status === "submitted") return "#d69e2e";
  return "#a0aec0";
}

export default function ProfileScreen() {
  const router = useRouter();
  const [reports, setReports] = useState<Grievance[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const fetchReports = () => {
    listMyGrievances(USER_ID)
      .then(setReports)
      .then(() => setError(""))
      .catch((e) => setError(e.message))
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  };

  useEffect(() => { fetchReports(); }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchReports();
  };

  return (
    <FlatList
      data={reports}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      ListHeaderComponent={
        <View style={styles.header}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>D</Text>
          </View>
          <Text style={styles.name}>Demo Citizen</Text>
          <Text style={styles.subtitle}>My Reports</Text>
          <TouchableOpacity
            style={styles.submitButton}
            onPress={() => router.push("/submit")}
          >
            <Text style={styles.submitButtonText}>+ New Report</Text>
          </TouchableOpacity>
        </View>
      }
      ListEmptyComponent={
        error ? (
          <View style={styles.empty}>
            <Text style={styles.errorText}>Could not load reports</Text>
            <Text style={styles.emptySub}>{error}</Text>
            <TouchableOpacity style={styles.emptyButton} onPress={onRefresh}>
              <Text style={styles.emptyButtonText}>Retry</Text>
            </TouchableOpacity>
          </View>
        ) : !loading ? (
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No reports yet</Text>
            <Text style={styles.emptySub}>
              Submit your first grievance to see it here.
            </Text>
            <TouchableOpacity
              style={styles.emptyButton}
              onPress={() => router.push("/submit")}
            >
              <Text style={styles.emptyButtonText}>Submit a report</Text>
            </TouchableOpacity>
          </View>
        ) : null
      }
      renderItem={({ item }) => (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.cardText} numberOfLines={2}>
              {item.pii_redacted_text || item.normalized_text || item.raw_text}
            </Text>
            <View
              style={[
                styles.statusPill,
                { backgroundColor: statusColor(item.status) + "20" },
              ]}
            >
              <Text
                style={[
                  styles.statusText,
                  { color: statusColor(item.status) },
                ]}
              >
                {item.status === "clustered" ? "Clustered" : item.status === "submitted" ? "Submitted" : item.status}
              </Text>
            </View>
          </View>
          <View style={styles.cardMeta}>
            <Text style={styles.metaText}>
              {(item.issue_category || "other").replace(/_/g, " ")} · {item.urgency}
            </Text>
            {item.ward ? (
              <Text style={styles.metaText}>Ward {item.ward}</Text>
            ) : null}
            <Text style={styles.metaText}>
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { paddingBottom: 40 },
  header: {
    alignItems: "center",
    paddingTop: 20,
    paddingBottom: 16,
    paddingHorizontal: 24,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#2b6cb0",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },
  avatarText: { color: "#fff", fontSize: 28, fontWeight: "800" },
  name: { fontSize: 18, fontWeight: "700", color: "#1a365d" },
  subtitle: { fontSize: 13, color: "#718096", marginTop: 2 },
  submitButton: {
    marginTop: 14,
    backgroundColor: "#2b6cb0",
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 12,
  },
  submitButtonText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  empty: { alignItems: "center", padding: 40 },
  emptyTitle: { fontSize: 16, fontWeight: "700", color: "#1a365d" },
  emptySub: { fontSize: 13, color: "#718096", marginTop: 4 },
  errorText: { fontSize: 15, fontWeight: "700", color: "#e53e3e", marginBottom: 4 },
  emptyButton: {
    marginTop: 16,
    backgroundColor: "#2b6cb0",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 12,
  },
  emptyButtonText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  card: {
    backgroundColor: "#fff",
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  cardText: { fontSize: 14, color: "#1a202c", flex: 1, lineHeight: 20 },
  statusPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  statusText: { fontSize: 11, fontWeight: "600", textTransform: "capitalize" },
  cardMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 10,
  },
  metaText: { fontSize: 11, color: "#718096" },
});