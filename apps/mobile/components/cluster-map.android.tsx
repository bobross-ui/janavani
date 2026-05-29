import { useRouter } from "expo-router";
import MapView, { Callout, Marker } from "react-native-maps";
import { StyleSheet, Text, View } from "react-native";
import type { ClusterRead } from "../lib/types";
import { T } from "../lib/theme";

interface Props {
  clusters: ClusterRead[];
  /** If true, tapping a callout navigates to cluster detail. */
  tappable?: boolean;
  /** Container height. Defaults match the existing layout; redesigned screens
   *  can pass 140 (clusters list) or 120 (cluster detail) per the spec. */
  height?: number;
}

export function ClusterMap({ clusters, tappable = false, height = 220 }: Props) {
  const router = useRouter();

  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );

  if (withCoords.length === 0) return null;

  const initialRegion = {
    latitude: withCoords[0].centroid_latitude!,
    longitude: withCoords[0].centroid_longitude!,
    latitudeDelta: 0.05,
    longitudeDelta: 0.05,
  };

  const wards = Array.from(
    new Set(withCoords.map((c) => c.ward).filter((w): w is string => !!w))
  );
  const legendLeft =
    wards.length === 1
      ? `WARD ${wards[0]} · ${withCoords.length} ACTIVE`
      : `${withCoords.length} ACTIVE`;
  const legendRight = `${initialRegion.latitude.toFixed(2)}°N · ${initialRegion.longitude.toFixed(2)}°E`;

  return (
    <View style={[styles.container, { height }]}>
      <MapView
        style={StyleSheet.absoluteFillObject}
        initialRegion={initialRegion}
        customMapStyle={T.mapStyle}
        showsBuildings={false}
        showsCompass={false}
        showsTraffic={false}
        showsIndoors={false}
        toolbarEnabled={false}
      >
        {withCoords.map((c) => {
          const urgent = c.urgency_score > 0.7;
          return (
            <Marker
              key={c.id}
              coordinate={{
                latitude: c.centroid_latitude!,
                longitude: c.centroid_longitude!,
              }}
              tracksViewChanges={false}
              anchor={{ x: 0.5, y: 0.5 }}
              onCalloutPress={
                tappable ? () => router.push(`/cluster/${c.id}`) : undefined
              }
            >
              <View style={urgent ? styles.haloWarn : styles.haloInk}>
                <View style={urgent ? styles.dotWarn : styles.dotInk} />
              </View>
              <Callout tooltip>
                <View style={styles.callout}>
                  <Text style={styles.calloutEyebrow}>
                    {c.issue_category.replace(/_/g, " ").toUpperCase()}
                    {c.ward ? ` · WARD ${c.ward}` : ""}
                  </Text>
                  <Text style={styles.calloutTitle}>{c.title}</Text>
                  <Text style={styles.calloutMeta}>
                    {c.grievance_count} REPORTS
                  </Text>
                </View>
              </Callout>
            </Marker>
          );
        })}
      </MapView>

      <View style={styles.legendLeft} pointerEvents="none">
        <Text style={styles.legendText}>{legendLeft}</Text>
      </View>
      <View style={styles.legendRight} pointerEvents="none">
        <Text style={styles.legendText}>{legendRight}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: "100%",
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
    backgroundColor: T.paperAlt,
    overflow: "hidden",
  },
  haloInk: {
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: T.inkHalo,
    alignItems: "center", justifyContent: "center",
  },
  haloWarn: {
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: T.warnHalo,
    alignItems: "center", justifyContent: "center",
  },
  dotInk: { width: 10, height: 10, borderRadius: 5, backgroundColor: T.ink },
  dotWarn: { width: 10, height: 10, borderRadius: 5, backgroundColor: T.warn },

  callout: {
    width: 220,
    padding: 12,
    backgroundColor: T.paper,
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
  },
  calloutEyebrow: {
    fontFamily: T.mono,
    fontSize: 9.5,
    letterSpacing: 1.4,
    color: T.inkSoft,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  calloutTitle: {
    fontFamily: T.serif,
    fontSize: 15,
    lineHeight: 19,
    color: T.inkDeep,
    letterSpacing: -0.1,
  },
  calloutMeta: {
    fontFamily: T.mono,
    fontSize: 9.5,
    letterSpacing: 1.2,
    color: T.inkMid,
    textTransform: "uppercase",
    marginTop: 8,
  },

  legendLeft: { position: "absolute", left: 12, bottom: 10 },
  legendRight: { position: "absolute", right: 12, bottom: 10 },
  legendText: {
    fontFamily: T.mono,
    fontSize: 9.5,
    letterSpacing: 1.3,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
});
