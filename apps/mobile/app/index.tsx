import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { listClusters } from "../lib/api";
import type { ClusterRead } from "../lib/types";
import { T } from "../lib/theme";
import { CITY_LABEL, WARD_LABEL } from "../lib/config";
import { humanize } from "../lib/format";
import {
  CTA,
  CircleBtn,
  Icon,
  Rule,
  SectionLabel,
  Stat,
  TopBar,
} from "../components/ui";

export default function HomeScreen() {
  const router = useRouter();
  const [clusters, setClusters] = useState<ClusterRead[] | null>(null);

  useEffect(() => {
    listClusters()
      .then(setClusters)
      .catch(() => setClusters([]));
  }, []);

  const counts = aggregate(clusters);
  const rising = (clusters ?? [])
    .slice()
    .sort((a, b) => b.grievance_count - a.grievance_count)
    .slice(0, 3);

  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 48 }}>
        <TopBar
          leading={<Text style={styles.versionTag}>v0.2</Text>}
          eyebrow="जनवाणी · janavāṇī"
          trailing={
            <CircleBtn onPress={() => router.push("/profile")} accessibilityLabel="Profile">
              <Icon name="user" size={15} stroke={T.ink} />
            </CircleBtn>
          }
        />

        {/* Editorial hero */}
        <View style={styles.hero}>
          <Text style={styles.heroLine1}>Many voices,</Text>
          <Text style={styles.heroLine2}>one signal.</Text>
          <Text style={styles.heroBody}>
            Speak a civic grievance in your language. We turn thousands of voices into
            one public signal that officials can act on.
          </Text>
        </View>

        {/* Tonal divider with mono inscription */}
        <View style={styles.inscriptionRow}>
          <Text style={styles.inscription}>This week · {WARD_LABEL}</Text>
          <Text style={styles.inscription}>{CITY_LABEL}</Text>
        </View>

        {/* Live signal strip */}
        <View style={styles.statsRow}>
          <View style={styles.statCell}>
            <Stat value={counts.reports} label="Reports" size="md" />
          </View>
          <Rule vertical />
          <View style={[styles.statCell, { paddingHorizontal: 16 }]}>
            <Stat value={counts.clusters} label="Clusters" size="md" />
          </View>
          <Rule vertical />
          <View style={[styles.statCell, { paddingLeft: 16 }]}>
            <Stat
              value={
                <Text>
                  {counts.urgent}
                  <Text style={{ color: T.accentDeep }}>↑</Text>
                </Text>
              }
              label="Urgent"
              size="md"
            />
          </View>
        </View>

        {/* Primary actions */}
        <View style={styles.actions}>
          <CTA tone="ink" icon="mic" iconSide="left" onPress={() => router.push("/submit")}>
            Speak your grievance
          </CTA>
          <CTA
            tone="ghost"
            icon="arrow-right"
            onPress={() => router.push("/clusters")}
          >
            See what's rising nearby
          </CTA>
        </View>

        {/* Trending strip */}
        <View style={{ marginTop: 40 }}>
          <SectionLabel n="01">Rising near you</SectionLabel>
          <View style={styles.trendingList}>
            {clusters === null ? (
              <View style={styles.loadingRow}>
                <ActivityIndicator color={T.inkSoft} />
              </View>
            ) : rising.length === 0 ? (
              <Text style={styles.emptyText}>No public signal yet.</Text>
            ) : (
              rising.map((c) => (
                <Pressable
                  key={c.id}
                  onPress={() => router.push(`/cluster/${c.id}`)}
                  accessibilityRole="button"
                  accessibilityLabel={`${c.title}, ${c.grievance_count} reports`}
                  style={({ pressed }) => [
                    styles.trendingRow,
                    { opacity: pressed ? 0.6 : 1 },
                  ]}
                >
                  <Text style={styles.trendingNum}>{c.grievance_count}</Text>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={styles.trendingTitle} numberOfLines={1}>
                      {c.title}
                    </Text>
                    <Text style={styles.trendingMeta} numberOfLines={1}>
                      {humanize(c.issue_category)}
                      {c.ward ? ` · Ward ${c.ward}` : ""}
                    </Text>
                  </View>
                  {c.urgency_score > 0.7 ? <View style={styles.urgentDot} /> : null}
                </Pressable>
              ))
            )}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function aggregate(clusters: ClusterRead[] | null) {
  if (!clusters) return { reports: "—", clusters: "—", urgent: "—" };
  const reports = clusters.reduce((s, c) => s + c.grievance_count, 0);
  const urgent = clusters.filter((c) => c.urgency_score > 0.7).length;
  return {
    reports: reports.toLocaleString("en-IN"),
    clusters: clusters.length.toString(),
    urgent: urgent.toString(),
  };
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: T.paper },
  versionTag: {
    fontFamily: T.mono,
    fontSize: 10,
    color: T.inkSoft,
    letterSpacing: 1.4,
  },
  hero: { paddingHorizontal: T.pad, paddingTop: 24, paddingBottom: 28 },
  heroLine1: {
    fontFamily: T.serif,
    fontSize: 58,
    lineHeight: 58,
    color: T.inkDeep,
    letterSpacing: -1.45,
  },
  heroLine2: {
    fontFamily: T.serif,
    fontSize: 58,
    lineHeight: 58,
    color: T.accentDeep,
    letterSpacing: -1.45,
  },
  heroBody: {
    marginTop: 22,
    maxWidth: 320,
    fontFamily: T.sans,
    fontSize: 14.5,
    lineHeight: 22,
    color: T.inkSoft,
  },
  inscriptionRow: {
    marginHorizontal: T.pad,
    marginBottom: 24,
    borderTopWidth: 1,
    borderTopColor: T.rule,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 12,
  },
  inscription: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  statsRow: {
    paddingHorizontal: T.pad,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 32,
  },
  statCell: {
    flex: 1,
    paddingRight: 16,
  },
  actions: {
    paddingHorizontal: T.pad,
    gap: 10,
  },
  trendingList: {
    paddingHorizontal: T.pad,
    paddingTop: 6,
  },
  loadingRow: { paddingVertical: 32, alignItems: "center" },
  emptyText: {
    paddingVertical: 24,
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.9,
    textTransform: "uppercase",
    color: T.inkSoft,
    textAlign: "center",
  },
  trendingRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 14,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: T.rule,
  },
  trendingNum: {
    fontFamily: T.mono,
    fontSize: 22,
    color: T.inkDeep,
    minWidth: 44,
    letterSpacing: -0.44,
    fontVariant: ["tabular-nums"],
  },
  trendingTitle: {
    fontFamily: T.serif,
    fontSize: 17,
    color: T.inkDeep,
    lineHeight: 22,
    letterSpacing: -0.17,
    marginBottom: 4,
  },
  trendingMeta: {
    fontFamily: T.mono,
    fontSize: 10.5,
    color: T.inkSoft,
    letterSpacing: 0.63,
    textTransform: "uppercase",
  },
  urgentDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: T.warn,
    marginTop: 8,
  },
});
