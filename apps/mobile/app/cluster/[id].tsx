import { useEffect, useState, useCallback } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { getCluster, supportCluster } from "../../lib/api";
import type { ClusterDetail, Grievance } from "../../lib/types";
import { T } from "../../lib/theme";
import { MOCK_USER_ID } from "../../lib/config";
import { humanize, humanLanguage, relativeAge } from "../../lib/format";
import {
  BackBtn,
  CTA,
  Chip,
  CircleBtn,
  Icon,
  RedactedText,
  Rule,
  SectionLabel,
  Stat,
  TopBar,
} from "../../components/ui";
import { ClusterMap } from "../../components/cluster-map";

export default function ClusterDetailScreen() {
  const router = useRouter();
  const { id, grievance_id: routeGrievanceId } = useLocalSearchParams<{ id: string; grievance_id?: string }>();
  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [error, setError] = useState("");
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getCluster(id, MOCK_USER_ID)
      .then((c) => {
        setCluster(c);
        setJoined(c.viewer_has_supported);
      })
      .catch((e) => setError(e?.message || "Not found"));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleJoin = useCallback(async () => {
    if (!cluster) return;
    if (!routeGrievanceId) return;
    setJoining(true);
    try {
      console.log("[join-cluster] supportCluster", {
        clusterId: cluster.id,
        grievanceId: routeGrievanceId,
        user_id: MOCK_USER_ID,
      });
      await supportCluster(cluster.id, {
        user_id: MOCK_USER_ID,
        grievance_id: routeGrievanceId,
        consent_to_file: true,
      });
      setJoined(true);
      load();
    } catch (e: any) {
      console.log("[join-cluster] ERROR:", JSON.stringify({
        message: e?.message,
        name: e?.name,
      }));
      setError(e?.message || "Could not join.");
    } finally {
      setJoining(false);
    }
  }, [cluster, load, routeGrievanceId]);

  if (error || (!cluster && !id)) {
    return (
      <SafeAreaView style={styles.shell} edges={["top"]}>
        <TopBar
          leading={<BackBtn onPress={() => router.back()} />}
          eyebrow="Cluster"
        />
        <View style={{ paddingHorizontal: T.pad, paddingTop: 32 }}>
          <Text style={styles.errorEyebrow}>Error</Text>
          <Text style={styles.errorTitle}>{error || "Cluster not found."}</Text>
          <View style={{ marginTop: 24 }}>
            <CTA tone="ghost" icon="arrow-right" onPress={load}>
              Retry
            </CTA>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  if (!cluster) {
    return (
      <SafeAreaView style={styles.shell} edges={["top"]}>
        <TopBar leading={<BackBtn onPress={() => router.back()} />} eyebrow="Cluster" />
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={T.inkSoft} />
        </View>
      </SafeAreaView>
    );
  }

  const urgent = cluster.urgency_score > 0.7;
  const shortId = cluster.id.slice(0, 8);

  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 56 }}>
        <TopBar
          leading={<BackBtn onPress={() => router.back()} />}
          eyebrow={`Cluster · #${shortId}`}
          trailing={
            <CircleBtn accessibilityLabel="Open external">
              <Text style={{ fontFamily: T.mono, fontSize: 13, color: T.ink, lineHeight: 13 }}>
                ↗
              </Text>
            </CircleBtn>
          }
        />

        <View style={{ paddingHorizontal: T.pad, paddingTop: 4, paddingBottom: 18 }}>
          <View style={{ flexDirection: "row", gap: 8, marginBottom: 14 }}>
            {urgent ? (
              <Chip tone="warn" mono size="xs">
                Urgent
              </Chip>
            ) : null}
            <Chip tone="default" mono size="xs">
              {humanize(cluster.issue_category)}
              {cluster.department ? ` · ${cluster.department}` : ""}
            </Chip>
            <Chip tone="outline" mono size="xs">
              {cluster.status ? humanize(cluster.status) : "Open"}
            </Chip>
          </View>
          <Text style={styles.title}>{cluster.title}</Text>
          {cluster.summary ? (
            <Text style={styles.lede}>{cluster.summary}</Text>
          ) : null}
        </View>

        <View style={{ paddingHorizontal: T.pad, paddingBottom: 24 }}>
          <ClusterMap clusters={[cluster]} height={120} />
        </View>

        {/* Stats row */}
        <View style={styles.statsRow}>
          <View style={{ flex: 1, paddingRight: 12 }}>
            <Stat value={cluster.grievance_count} label="Reports" size="md" />
          </View>
          <Rule vertical />
          <View style={{ flex: 1, paddingHorizontal: 12 }}>
            <Stat value={cluster.support_count} label="Supporters" size="md" />
          </View>
          <Rule vertical />
          <View style={{ flex: 1, paddingLeft: 12 }}>
            <Stat
              value={cluster.urgency_score.toFixed(2)}
              label="Urgency"
              size="md"
              valueColor={urgent ? T.warn : T.inkDeep}
            />
          </View>
        </View>

        {/* Voices */}
        {cluster.sample_grievances.length > 0 ? (
          <View style={{ marginTop: 28 }}>
            <SectionLabel n="01">Voices · redacted</SectionLabel>
            <View style={{ paddingHorizontal: T.pad, paddingTop: 14, gap: 14 }}>
              {cluster.sample_grievances.slice(0, 4).map((g) => (
                <Voice key={g.id} g={g} />
              ))}
            </View>
          </View>
        ) : null}

        {/* Action */}
        <View style={{ paddingHorizontal: T.pad, paddingTop: 28 }}>
          {joined ? (
            <View style={styles.joinedRow}>
              <Icon name="check" size={16} stroke={T.good} />
              <Text style={styles.joinedText}>You joined this signal</Text>
            </View>
          ) : routeGrievanceId ? (
            <CTA tone="accent" icon="plus" iconSide="left" onPress={handleJoin} disabled={joining}>
              {joining ? "Joining…" : "Add your voice"}
            </CTA>
          ) : null}
          <Text style={styles.joinFootnote}>
            {cluster.support_count} CITIZENS JOINED · JOINS ARE PUBLIC
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Voice({ g }: { g: Grievance }) {
  return (
    <View style={styles.voice}>
      <RedactedText style={styles.voiceText}>
        {`"${g.pii_redacted_text || g.normalized_text}"`}
      </RedactedText>
      <Text style={styles.voiceMeta}>
        — ANONYMOUS · {humanLanguage(g.language)} · {relativeAge(g.created_at)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: T.paper },

  title: {
    fontFamily: T.serif,
    fontSize: 38,
    lineHeight: 39,
    color: T.inkDeep,
    letterSpacing: -0.84,
  },
  lede: {
    marginTop: 14,
    fontFamily: T.sans,
    fontSize: 14,
    lineHeight: 21,
    color: T.inkSoft,
    maxWidth: 340,
  },

  statsRow: {
    marginHorizontal: T.pad,
    paddingVertical: 18,
    borderTopWidth: 1,
    borderTopColor: T.ink,
    borderBottomWidth: 1,
    borderBottomColor: T.rule,
    flexDirection: "row",
    alignItems: "center",
  },

  voice: {
    paddingLeft: 14,
    borderLeftWidth: 2,
    borderLeftColor: T.accent,
  },
  voiceText: {
    fontFamily: T.serif,
    fontSize: 16.5,
    lineHeight: 24,
    color: T.inkDeep,
    letterSpacing: -0.085,
  },
  voiceMeta: {
    marginTop: 6,
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    color: T.inkSoft,
    textTransform: "uppercase",
  },

  joinedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 18,
    justifyContent: "center",
  },
  joinedText: {
    fontFamily: T.mono,
    fontSize: 11,
    letterSpacing: 1.0,
    color: T.good,
    textTransform: "uppercase",
  },
  joinFootnote: {
    marginTop: 12,
    textAlign: "center",
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: T.inkSoft,
    textTransform: "uppercase",
  },

  errorEyebrow: {
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.9,
    color: T.warn,
    textTransform: "uppercase",
    marginBottom: 12,
  },
  errorTitle: {
    fontFamily: T.serif,
    fontSize: 22,
    color: T.inkDeep,
    lineHeight: 28,
    letterSpacing: -0.22,
  },
});
