import { StyleSheet, Text, View } from "react-native";
import type { ClusterRead } from "../lib/types";

interface Props {
  clusters: ClusterRead[];
  tappable?: boolean;
}

/** Web stub — react-native-maps is native-only. Shows a location summary instead. */
export function ClusterMap({ clusters }: Props) {
  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );

  if (withCoords.length === 0) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.count}>
        {withCoords.length} cluster{withCoords.length !== 1 ? "s" : ""} on map
      </Text>
      {withCoords.slice(0, 5).map((c) => (
        <Text key={c.id} style={styles.item}>
          📍 {c.title} — Ward {c.ward}
        </Text>
      ))}
      {withCoords.length > 5 && (
        <Text style={styles.more}>+{withCoords.length - 5} more</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#f7fafc",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginBottom: 12,
  },
  count: {
    fontSize: 14,
    fontWeight: "700",
    color: "#2b6cb0",
    marginBottom: 8,
  },
  item: {
    fontSize: 13,
    color: "#4a5568",
    marginBottom: 4,
  },
  more: {
    fontSize: 12,
    color: "#a0aec0",
    marginTop: 4,
  },
});
