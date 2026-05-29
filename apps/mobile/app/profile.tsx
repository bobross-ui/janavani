import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { listMyGrievances } from "../lib/api";
import type { Grievance } from "../lib/types";
import { T } from "../lib/theme";
import { CITY_LABEL, MOCK_USER_ID, WARD_LABEL } from "../lib/config";
import { humanize, relativeAge } from "../lib/format";
import {
  BackBtn,
  CTA,
  CircleBtn,
  RedactedText,
  Rule,
  SectionLabel,
  Stat,
  TopBar,
} from "../components/ui";

export default function ProfileScreen() {
  const router = useRouter();
  const [reports, setReports] = useState<Grievance[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const fetchReports = useCallback(() => {
    return listMyGrievances(MOCK_USER_ID)
      .then((rs) => {
        setReports(rs);
        setError("");
      })
      .catch((e) => setError(e?.message || "Could not load."));
  }, []);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchReports().finally(() => setRefreshing(false));
  }, [fetchReports]);

  const stats = aggregate(reports);

  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <FlatList<Grievance>
        data={reports ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingBottom: 40 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={T.inkSoft}
          />
        }
        ListHeaderComponent={
          <>
            <TopBar
              leading={<BackBtn onPress={() => router.back()} />}
              eyebrow="Profile"
              trailing={
                <CircleBtn accessibilityLabel="More options">
                  <Text style={{ fontFamily: T.mono, fontSize: 13, color: T.ink, lineHeight: 13 }}>
                    ···
                  </Text>
                </CircleBtn>
              }
            />

            {/* Identity */}
            <View style={styles.identity}>
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>D</Text>
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={styles.name}>Demo Citizen</Text>
                <RedactedText style={styles.identityMeta}>
                  {`+91 ███ ██ 3210 · ${WARD_LABEL} · ${CITY_LABEL}`}
                </RedactedText>
              </View>
            </View>

            {/* Lifetime stats */}
            <View style={styles.statsRow}>
              <View style={{ flex: 1, paddingRight: 12 }}>
                <Stat value={stats.total} label="Reports" size="md" />
              </View>
              <Rule vertical />
              <View style={{ flex: 1, paddingHorizontal: 12 }}>
                <Stat value={stats.clustered} label="Clustered" size="md" />
              </View>
              <Rule vertical />
              <View style={{ flex: 1, paddingLeft: 12 }}>
                <Stat value={stats.pending} label="Pending" size="md" />
              </View>
            </View>

            {/* Primary action */}
            <View style={{ paddingHorizontal: T.pad, paddingTop: 20, paddingBottom: 8 }}>
              <CTA tone="ink" icon="plus" iconSide="left" onPress={() => router.push("/submit")}>
                New grievance
              </CTA>
            </View>

            <View style={{ marginTop: 16 }}>
              <SectionLabel n="01">Your reports</SectionLabel>
            </View>
          </>
        }
        ListEmptyComponent={
          reports === null ? (
            <View style={{ paddingVertical: 48, alignItems: "center" }}>
              <ActivityIndicator color={T.inkSoft} />
            </View>
          ) : error ? (
            <View style={{ padding: 32, alignItems: "center" }}>
              <Text style={styles.errorEyebrow}>Error</Text>
              <Text style={styles.errorMsg}>{error}</Text>
              <View style={{ marginTop: 18, width: "100%" }}>
                <CTA tone="ghost" icon="arrow-right" onPress={onRefresh}>
                  Retry
                </CTA>
              </View>
            </View>
          ) : (
            <View style={{ padding: 32, alignItems: "center" }}>
              <Text style={styles.emptyEyebrow}>No reports yet</Text>
              <Text style={styles.emptyMsg}>
                Submit your first grievance to see it appear here.
              </Text>
            </View>
          )
        }
        renderItem={({ item }) => <ReportRow g={item} />}
      />
    </SafeAreaView>
  );
}

function ReportRow({ g }: { g: Grievance }) {
  const clustered = !!g.cluster_id;
  return (
    <View style={styles.reportRow}>
      <View style={{ minWidth: 44 }}>
        <Text style={styles.reportTime}>{relativeAge(g.created_at)}</Text>
        <View
          style={{
            marginTop: 6,
            width: 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: clustered ? T.good : T.accent,
          }}
        />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <RedactedText style={styles.reportText} numberOfLines={2}>
          {`"${g.pii_redacted_text || g.normalized_text || g.raw_text}"`}
        </RedactedText>
        <View style={{ marginTop: 10, gap: 4 }}>
          <Text style={styles.reportMeta}>
            {humanize(g.issue_category)}
            {g.ward ? ` · Ward ${g.ward}` : ""}
          </Text>
          {clustered ? (
            <Text style={[styles.reportStatus, { color: T.good }]}>
              → JOINED #{(g.cluster_id || "").slice(0, 8)}
            </Text>
          ) : (
            <Text style={[styles.reportStatus, { color: T.accentDeep }]}>
              AWAITING CLUSTER MATCH
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

function aggregate(reports: Grievance[] | null) {
  if (!reports) return { total: "—", clustered: "—", pending: "—" };
  const total = reports.length;
  const clustered = reports.filter((g) => !!g.cluster_id).length;
  // "Joined yours" (spec) needs a backend aggregate we don't expose yet, so we
  // surface "Pending" instead — reports still awaiting a cluster match.
  return {
    total: total.toString(),
    clustered: clustered.toString(),
    pending: (total - clustered).toString(),
  };
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: T.paper },

  identity: {
    paddingHorizontal: T.pad,
    paddingTop: 4,
    paddingBottom: 24,
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: T.ink,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    color: T.paper,
    fontFamily: T.serif,
    fontSize: 28,
    letterSpacing: -0.56,
  },
  name: {
    fontFamily: T.serif,
    fontSize: 24,
    color: T.inkDeep,
    letterSpacing: -0.36,
    lineHeight: 27,
  },
  identityMeta: {
    marginTop: 4,
    fontFamily: T.mono,
    fontSize: 10.5,
    color: T.inkSoft,
    letterSpacing: 1.3,
    textTransform: "uppercase",
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

  reportRow: {
    marginHorizontal: T.pad,
    paddingVertical: 18,
    borderBottomWidth: 1,
    borderBottomColor: T.rule,
    flexDirection: "row",
    gap: 14,
  },
  reportTime: {
    fontFamily: T.mono,
    fontSize: 10,
    color: T.inkSoft,
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  reportText: {
    fontFamily: T.serif,
    fontSize: 16,
    lineHeight: 22,
    color: T.inkDeep,
    letterSpacing: -0.08,
  },
  reportMeta: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  reportStatus: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.4,
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
  errorMsg: {
    fontFamily: T.serif,
    fontSize: 18,
    color: T.inkDeep,
    lineHeight: 24,
    textAlign: "center",
  },
  emptyEyebrow: {
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.9,
    color: T.inkSoft,
    textTransform: "uppercase",
    marginBottom: 12,
  },
  emptyMsg: {
    fontFamily: T.serif,
    fontSize: 18,
    color: T.inkDeep,
    lineHeight: 24,
    textAlign: "center",
  },
});
