import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

export function AudioRecorder() {
  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.micButton} disabled>
        <Text style={styles.micIcon}>🎤</Text>
      </TouchableOpacity>
      <View style={styles.info}>
        <Text style={styles.title}>Voice grievance</Text>
        <Text style={styles.subtitle}>
          Coming soon — speak in Hindi, Marathi or Tamil.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f7fafc",
    borderRadius: 12,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderStyle: "dashed",
  },
  micButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#E6F4FE",
    alignItems: "center",
    justifyContent: "center",
    opacity: 0.6,
  },
  micIcon: { fontSize: 22 },
  info: { marginLeft: 14, flex: 1 },
  title: { fontSize: 14, fontWeight: "700", color: "#2d3748" },
  subtitle: { fontSize: 12, color: "#718096", marginTop: 2 },
});
