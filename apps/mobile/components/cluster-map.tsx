import { useRouter } from "expo-router";
import MapView, { Callout, Marker } from "react-native-maps";
import { StyleSheet, Text, View } from "react-native";
import type { ClusterRead } from "../lib/types";

function urgencyColor(score: number): string {
  if (score >= 0.8) return "#e53e3e";
  if (score >= 0.6) return "#dd6b20";
  if (score >= 0.4) return "#d69e2e";
  return "#38a169";
}

interface Props {
  clusters: ClusterRead[];
  /** If true, tapping a marker navigates to cluster detail */
  tappable?: boolean;
}

export function ClusterMap({ clusters, tappable = false }: Props) {
  const router = useRouter();

  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );

  if (withCoords.length === 0) return null;

  // Mumbai default center if only one marker
  const initialRegion = {
    latitude: withCoords[0].centroid_latitude!,
    longitude: withCoords[0].centroid_longitude!,
    latitudeDelta: 0.05,
    longitudeDelta: 0.05,
  };

  return (
    <MapView style={styles.map} initialRegion={initialRegion}>
      {withCoords.map((c) => (
        <Marker
          key={c.id}
          coordinate={{
            latitude: c.centroid_latitude!,
            longitude: c.centroid_longitude!,
          }}
          pinColor={urgencyColor(c.urgency_score)}
          onCalloutPress={
            tappable ? () => router.push(`/cluster/${c.id}`) : undefined
          }
        >
          <Callout>
            <View style={styles.callout}>
              <Text style={styles.calloutTitle}>{c.title}</Text>
              <Text style={styles.calloutSub}>
                {c.ward ? `Ward ${c.ward} · ` : ""}
                {c.issue_category.replace(/_/g, " ")} · {c.grievance_count}{" "}
                reports
              </Text>
            </View>
          </Callout>
        </Marker>
      ))}
    </MapView>
  );
}

const styles = StyleSheet.create({
  map: {
    width: "100%",
    height: 220,
    borderRadius: 12,
  },
  callout: {
    width: 180,
    padding: 4,
  },
  calloutTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1a365d",
  },
  calloutSub: {
    fontSize: 11,
    color: "#4a5568",
    marginTop: 2,
  },
});
