import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#E6F4FE" },
          headerTintColor: "#1a365d",
          headerTitleStyle: { fontWeight: "bold" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "Janavani" }} />
        <Stack.Screen name="submit" options={{ title: "Submit Grievance" }} />
        <Stack.Screen name="cluster/[id]" options={{ title: "Issue Cluster" }} />
      </Stack>
    </>
  );
}
