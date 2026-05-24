import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

const LANGUAGES = [
  { key: "hi-Latn", label: "Hinglish" },
  { key: "hi", label: "Hindi" },
  { key: "mr", label: "Marathi" },
  { key: "ta", label: "Tamil" },
];

interface Props {
  text: string;
  onTextChange: (v: string) => void;
  language: string;
  onLanguageChange: (v: string) => void;
  phone: string;
  loading: boolean;
  onSubmit: () => void;
}

export function GrievanceForm({
  text,
  onTextChange,
  language,
  onLanguageChange,
  phone,
  loading,
  onSubmit,
}: Props) {
  const canSubmit = text.trim().length > 0 && !loading;

  return (
    <View>
      <Text style={styles.label}>Phone number</Text>
      <TextInput style={styles.input} value={phone} editable={false} />

      <Text style={styles.label}>Language</Text>
      <View style={styles.langRow}>
        {LANGUAGES.map((l) => (
          <TouchableOpacity
            key={l.key}
            style={[styles.langChip, language === l.key && styles.langChipActive]}
            onPress={() => onLanguageChange(l.key)}
          >
            <Text
              style={[
                styles.langChipText,
                language === l.key && styles.langChipTextActive,
              ]}
            >
              {l.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>Your grievance</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        multiline
        numberOfLines={5}
        placeholder="Describe the issue..."
        value={text}
        onChangeText={onTextChange}
      />

      <TouchableOpacity
        style={[styles.button, !canSubmit && styles.buttonDisabled]}
        onPress={onSubmit}
        disabled={!canSubmit}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>
            {text.trim() ? "Submit grievance" : "Type your grievance above"}
          </Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#4a5568",
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: "#cbd5e0",
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    backgroundColor: "#f7fafc",
  },
  textArea: { height: 120, textAlignVertical: "top" },
  langRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  langChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#cbd5e0",
  },
  langChipActive: { backgroundColor: "#2b6cb0", borderColor: "#2b6cb0" },
  langChipText: { fontSize: 13, color: "#4a5568" },
  langChipTextActive: { color: "#fff" },
  button: {
    backgroundColor: "#2b6cb0",
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: "center",
    marginTop: 24,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
