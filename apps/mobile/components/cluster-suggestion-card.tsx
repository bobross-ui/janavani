import { useRouter } from "expo-router";
import { useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { supportCluster } from "../lib/api";

type Action = "join_cluster" | "create_cluster";

interface Props {
  action: Action;
  clusterId: string | null;
  clusterTitle: string | null;
  userId: string;
  grievanceId: string;
}

export function ClusterSuggestionCard({
  action,
  clusterId,
  clusterTitle,
  userId,
  grievanceId,
}: Props) {
  const router = useRouter();
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);
  const [error, setError] = useState("");

  if (action === "create_cluster") {
    return (
      <View style={[styles.card, styles.newCard]}>
        <Text style={styles.newTitle}>New civic issue</Text>
        <Text style={styles.newBody}>
          No similar reports nearby. A new cluster has been created for this
          grievance — other citizens can join it.
        </Text>
      </View>
    );
  }

  if (!clusterId) return null;

  const handleJoin = async () => {
    setJoining(true);
    setError("");
    try {
      await supportCluster(clusterId, {
        user_id: userId,
        grievance_id: grievanceId,
        consent_to_file: true,
      });
      setJoined(true);
    } catch (e: any) {
      setError(e?.message || "Could not join cluster");
    } finally {
      setJoining(false);
    }
  };

  return (
    <View style={[styles.card, styles.joinCard]}>
      <Text style={styles.joinHeader}>Similar issue nearby</Text>
      <Text style={styles.joinTitle}>{clusterTitle}</Text>
      <Text style={styles.joinBody}>
        Add your voice so officials see this as one collective signal.
      </Text>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {joined ? (
        <View style={styles.joinedRow}>
          <Text style={styles.joinedBadge}>✓ Joined</Text>
          <TouchableOpacity
            style={styles.viewButton}
            onPress={() => router.push(`/cluster/${clusterId}`)}
          >
            <Text style={styles.viewButtonText}>View cluster</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity
          style={[styles.joinButton, joining && styles.joinButtonDisabled]}
          onPress={handleJoin}
          disabled={joining}
        >
          {joining ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.joinButtonText}>Join this cluster</Text>
          )}
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: 16, borderRadius: 12, padding: 16 },
  joinCard: { backgroundColor: "#ebf8ff", borderWidth: 1, borderColor: "#bee3f8" },
  newCard: { backgroundColor: "#fefcbf", borderWidth: 1, borderColor: "#faf089" },
  joinHeader: {
    fontSize: 12,
    fontWeight: "700",
    color: "#2b6cb0",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  joinTitle: { fontSize: 15, fontWeight: "700", color: "#1a365d", marginBottom: 6 },
  joinBody: { fontSize: 13, color: "#2c5282", marginBottom: 12, lineHeight: 18 },
  joinButton: {
    backgroundColor: "#2b6cb0",
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  joinButtonDisabled: { opacity: 0.6 },
  joinButtonText: { color: "#fff", fontSize: 14, fontWeight: "700" },
  joinedRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  joinedBadge: {
    fontSize: 14,
    fontWeight: "700",
    color: "#22543d",
    backgroundColor: "#c6f6d5",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  viewButton: {
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: "#2b6cb0",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  viewButtonText: { color: "#2b6cb0", fontSize: 14, fontWeight: "600" },
  newTitle: { fontSize: 15, fontWeight: "700", color: "#744210", marginBottom: 6 },
  newBody: { fontSize: 13, color: "#744210", lineHeight: 18 },
  error: {
    color: "#c53030",
    fontSize: 13,
    marginBottom: 8,
    backgroundColor: "#fff5f5",
    padding: 8,
    borderRadius: 6,
  },
});
