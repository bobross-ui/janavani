import { useRouter } from "expo-router";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

export default function HomeScreen() {
  const router = useRouter();
  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <Text style={styles.heroTitle}>Janavani</Text>
        <Text style={styles.heroSubtitle}>Speak your grievance. See the bigger civic signal.</Text>
        <Text style={styles.heroBody}>Janavani turns spoken grievances into structured public issue clusters that citizens can join and officials can act on.</Text>
      </View>
      <View style={styles.actions}>
        <TouchableOpacity style={styles.primaryButton} onPress={() => router.push("/submit")}>
          <Text style={styles.primaryButtonText}>Submit a grievance</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryButton} onPress={() => router.push("/clusters")}>
          <Text style={styles.secondaryButtonText}>View nearby public issues</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.linkButton} onPress={() => router.push("/submit")}>
          <Text style={styles.linkButtonText}>View my issues</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 24, justifyContent: "center" },
  hero: { marginBottom: 48 },
  heroTitle: { fontSize: 36, fontWeight: "800", color: "#1a365d", marginBottom: 12 },
  heroSubtitle: { fontSize: 18, fontWeight: "600", color: "#2b6cb0", marginBottom: 12 },
  heroBody: { fontSize: 15, color: "#4a5568", lineHeight: 22 },
  actions: { gap: 12 },
  primaryButton: { backgroundColor: "#2b6cb0", paddingVertical: 16, borderRadius: 12, alignItems: "center" },
  primaryButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  secondaryButton: { backgroundColor: "#E6F4FE", paddingVertical: 16, borderRadius: 12, alignItems: "center" },
  secondaryButtonText: { color: "#2b6cb0", fontSize: 16, fontWeight: "600" },
  linkButton: { alignItems: "center", paddingVertical: 8 },
  linkButtonText: { color: "#2b6cb0", fontSize: 14, fontWeight: "500" },
});
