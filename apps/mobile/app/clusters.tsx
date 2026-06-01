import { useEffect, useMemo, useState } from "react";
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
import { USER_WARD } from "../lib/config";
import { humanize, relativeAge } from "../lib/format";
import { BackBtn, TopBar } from "../components/ui";
import { ClusterMap } from "../components/cluster-map";

type FilterKey = "all" | "ward" | "urgent" | string;

export default function ClustersScreen() {
  const router = useRouter();
  const [clusters, setClusters] = useState<ClusterRead[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");

  useEffect(() => {
    listClusters()
      .then(setClusters)
      .catch((e) => setError(e?.message || "Failed to load"));
  }, []);

  const counts = useMemo(() => {
    const all = clusters?.length ?? 0;
    const ward = (clusters ?? []).filter((c) => c.ward === USER_WARD).length;
    const urgent = (clusters ?? []).filter((c) => c.urgency_score > 0.7).length;
    const byCategory: Record<string, number> = {};
    (clusters ?? []).forEach((c) => {
      byCategory[c.issue_category] = (byCategory[c.issue_category] || 0) + 1;
    });
    return { all, ward, urgent, byCategory };
  }, [clusters]);

  const topCategories = useMemo(() => {
    return Object.entries(counts.byCategory)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);
  }, [counts.byCategory]);

  const filtered = useMemo(() => {
    if (!clusters) return [];
    if (filter === "all") return clusters;
    if (filter === "ward") return clusters.filter((c) => c.ward === USER_WARD);
    if (filter === "urgent") return clusters.filter((c) => c.urgency_score > 0.7);
    return clusters.filter((c) => c.issue_category === filter);
  }, [clusters, filter]);

  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 56 }}>
        <TopBar
          leading={<BackBtn onPress={() => router.back()} />}
          eyebrow="Public signal"
          trailing={
            <Text style={styles.trailingCount}>{counts.all || "—"}</Text>
          }
        />

        <View style={{ paddingHorizontal: T.pad, paddingTop: 8, paddingBottom: 22 }}>
          <Text style={styles.h1}>Issues rising</Text>
          <Text style={styles.h1}>near you.</Text>
        </View>

        <View style={{ paddingHorizontal: T.pad, paddingBottom: 18 }}>
          {clusters ? (
            <ClusterMap clusters={filtered} tappable height={140} />
          ) : (
            <View style={[styles.mapPlaceholder, { height: 140 }]}>
              <ActivityIndicator color={T.inkSoft} />
            </View>
          )}
        </View>

        {/* Filter chips */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          <FilterChip
            label="All"
            count={counts.all}
            active={filter === "all"}
            onPress={() => setFilter("all")}
          />
          <FilterChip
            label="Your ward"
            count={counts.ward}
            active={filter === "ward"}
            onPress={() => setFilter("ward")}
          />
          <FilterChip
            label="Urgent"
            count={counts.urgent}
            active={filter === "urgent"}
            onPress={() => setFilter("urgent")}
          />
          {topCategories.map(([cat, n]) => (
            <FilterChip
              key={cat}
              label={humanize(cat)}
              count={n}
              active={filter === cat}
              onPress={() => setFilter(cat)}
            />
          ))}
        </ScrollView>

        {/* Cluster list */}
        <View style={{ paddingHorizontal: T.pad, paddingTop: 14 }}>
          {error ? (
            <Text style={styles.errorText}>{error}</Text>
          ) : clusters === null ? (
            <View style={{ paddingVertical: 32, alignItems: "center" }}>
              <ActivityIndicator color={T.inkSoft} />
            </View>
          ) : filtered.length === 0 ? (
            <Text style={styles.emptyText}>No clusters match this filter.</Text>
          ) : (
            filtered.map((c, i) => (
              <ClusterRow
                key={c.id}
                cluster={c}
                first={i === 0}
                onPress={() => router.push(`/cluster/${c.id}`)}
              />
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function FilterChip({
  label,
  count,
  active,
  onPress,
}: {
  label: string;
  count: number;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}, ${count}`}
      accessibilityState={{ selected: active }}
      style={[
        styles.filterChip,
        active && { backgroundColor: T.ink, borderColor: T.ink },
      ]}
    >
      <Text
        style={{
          fontFamily: T.sansMed,
          fontSize: 12.5,
          color: active ? T.paper : T.inkMid,
        }}
      >
        {label}
      </Text>
      <Text
        style={{
          fontFamily: T.mono,
          fontSize: 10.5,
          color: active ? "rgba(255,255,255,0.55)" : T.inkSoft,
          letterSpacing: 0.5,
        }}
      >
        {count}
      </Text>
    </Pressable>
  );
}

function ClusterRow({
  cluster,
  first,
  onPress,
}: {
  cluster: ClusterRead;
  first: boolean;
  onPress: () => void;
}) {
  const urgent = cluster.urgency_score > 0.7;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={cluster.title}
      style={[
        styles.clusterRow,
        { borderTopColor: first ? T.ink : T.rule, borderTopWidth: 1 },
      ]}
    >
      <View style={styles.clusterMeta}>
        <Text style={styles.clusterMetaText}>
          {humanize(cluster.issue_category)}
          {cluster.area ? ` · ${cluster.area}` : cluster.ward ? ` · Ward ${cluster.ward}` : ""}
          {" · "}
          {relativeAge(cluster.created_at)}
        </Text>
        {urgent ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
            <View style={{ width: 5, height: 5, borderRadius: 3, backgroundColor: T.warn }} />
            <Text style={styles.urgentLabel}>Urgent</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.clusterBody}>
        <View style={{ minWidth: 64 }}>
          <Text style={styles.clusterNum}>{cluster.grievance_count}</Text>
          <Text style={styles.clusterNumLabel}>Reports</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={styles.clusterTitle}>{cluster.title}</Text>
          {cluster.summary ? (
            <Text style={styles.clusterSummary} numberOfLines={2}>
              {cluster.summary}
            </Text>
          ) : null}
          <UrgencyBar value={cluster.urgency_score} />
        </View>
      </View>
    </Pressable>
  );
}

function UrgencyBar({ value }: { value: number }) {
  const fill = value > 0.7 ? T.warn : value > 0.4 ? T.accent : T.inkSoft;
  return (
    <View style={styles.urgencyTrack}>
      <View
        style={{
          width: `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`,
          height: "100%",
          backgroundColor: fill,
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: T.paper },
  trailingCount: {
    fontFamily: T.mono,
    fontSize: 10,
    color: T.inkSoft,
    letterSpacing: 1.4,
  },
  h1: {
    fontFamily: T.serif,
    fontSize: 44,
    lineHeight: 44,
    color: T.inkDeep,
    letterSpacing: -1.1,
  },
  mapPlaceholder: {
    width: "100%",
    backgroundColor: T.paperAlt,
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
    alignItems: "center",
    justifyContent: "center",
  },
  filterRow: {
    paddingHorizontal: T.pad,
    paddingVertical: 4,
    gap: 8,
  },
  filterChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: T.radius.pill,
    borderWidth: 1,
    borderColor: T.rule,
    backgroundColor: "transparent",
  },
  errorText: {
    fontFamily: T.sans,
    fontSize: 13,
    color: T.warn,
    paddingVertical: 24,
    textAlign: "center",
  },
  emptyText: {
    paddingVertical: 32,
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.9,
    textTransform: "uppercase",
    color: T.inkSoft,
    textAlign: "center",
  },

  // Cluster row
  clusterRow: {
    paddingTop: 20,
    paddingBottom: 22,
  },
  clusterMeta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  clusterMetaText: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  urgentLabel: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: T.warn,
    textTransform: "uppercase",
  },
  clusterBody: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 16,
  },
  clusterNum: {
    fontFamily: T.mono,
    fontSize: 34,
    color: T.inkDeep,
    lineHeight: 34,
    letterSpacing: -1.36,
    fontVariant: ["tabular-nums"],
  },
  clusterNumLabel: {
    marginTop: 4,
    fontFamily: T.mono,
    fontSize: 9,
    letterSpacing: 1.26,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  clusterTitle: {
    fontFamily: T.serif,
    fontSize: 20,
    lineHeight: 23,
    color: T.inkDeep,
    letterSpacing: -0.3,
  },
  clusterSummary: {
    marginTop: 6,
    fontFamily: T.sans,
    fontSize: 13,
    lineHeight: 19,
    color: T.inkSoft,
  },
  urgencyTrack: {
    marginTop: 12,
    width: "100%",
    height: 3,
    backgroundColor: T.paperDim,
    borderRadius: 2,
    overflow: "hidden",
  },
});
