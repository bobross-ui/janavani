import { useRouter } from "expo-router";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

const MOCK_USER = {
  display_name: "Demo Citizen",
  phone: "9876543210",
  ward: "8",
  language: "Hinglish",
};

export default function ProfileScreen() {
  const router = useRouter();
  return (
    <View style={styles.container}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>
          {MOCK_USER.display_name.slice(0, 1)}
        </Text>
      </View>
      <Text style={styles.name}>{MOCK_USER.display_name}</Text>
      <Text style={styles.phone}>+91 {MOCK_USER.phone}</Text>

      <View style={styles.infoCard}>
        <Row label="Ward" value={MOCK_USER.ward} />
        <Row label="Preferred language" value={MOCK_USER.language} />
        <Row label="Account" value="Demo (mock login)" />
      </View>

      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => router.push("/submit")}
        >
          <Text style={styles.primaryButtonText}>Submit a new grievance</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => router.push("/clusters")}
        >
          <Text style={styles.secondaryButtonText}>Browse public issues</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.footnote}>
        This is a demo profile. Real OTP login, identity verification, and a
        full submission history are out of scope for the MVP.
      </Text>
    </View>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff", padding: 24 },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#2b6cb0",
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    marginTop: 12,
  },
  avatarText: { color: "#fff", fontSize: 32, fontWeight: "800" },
  name: {
    fontSize: 22,
    fontWeight: "800",
    color: "#1a365d",
    textAlign: "center",
    marginTop: 12,
  },
  phone: { fontSize: 14, color: "#718096", textAlign: "center", marginTop: 4 },
  infoCard: {
    marginTop: 28,
    borderRadius: 12,
    backgroundColor: "#f7fafc",
    padding: 16,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 8,
  },
  rowLabel: { fontSize: 14, color: "#4a5568" },
  rowValue: { fontSize: 14, color: "#1a202c", fontWeight: "600" },
  actions: { marginTop: 24, gap: 12 },
  primaryButton: {
    backgroundColor: "#2b6cb0",
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
  },
  primaryButtonText: { color: "#fff", fontSize: 15, fontWeight: "700" },
  secondaryButton: {
    backgroundColor: "#E6F4FE",
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: "center",
  },
  secondaryButtonText: { color: "#2b6cb0", fontSize: 15, fontWeight: "600" },
  footnote: {
    fontSize: 12,
    color: "#a0aec0",
    textAlign: "center",
    marginTop: 32,
    lineHeight: 18,
  },
});
