import { StyleSheet, Text, View } from "react-native";
import type { ExtractionResult } from "../lib/types";

interface Props {
  extraction: ExtractionResult;
}

export function TranscriptReview({ extraction }: Props) {
  return (
    <View style={styles.card}>
      <Text style={styles.title}>What we understood</Text>
      <Row label="Category" value={extraction.category} />
      <Row label="Department" value={extraction.department} />
      <Row label="Ward" value={extraction.ward || "Not detected"} />
      <Row label="Urgency" value={extraction.urgency} />
      {extraction.landmark ? (
        <Row label="Landmark" value={extraction.landmark} />
      ) : null}
      {extraction.pii_redacted_text ? (
        <View style={styles.transcriptBlock}>
          <Text style={styles.transcriptLabel}>Public text (redacted)</Text>
          <Text style={styles.transcriptText}>{extraction.pii_redacted_text}</Text>
        </View>
      ) : null}
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
  card: {
    marginTop: 24,
    backgroundColor: "#f0fff4",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#c6f6d5",
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: "#22543d",
    marginBottom: 10,
  },
  row: { flexDirection: "row", marginBottom: 6 },
  rowLabel: { fontSize: 14, fontWeight: "500", color: "#4a5568", width: 110 },
  rowValue: { fontSize: 14, color: "#1a202c", flex: 1 },
  transcriptBlock: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#c6f6d5",
  },
  transcriptLabel: { fontSize: 12, color: "#4a5568", marginBottom: 4 },
  transcriptText: { fontSize: 13, color: "#1a202c", lineHeight: 18 },
});
