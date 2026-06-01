# Janavani — Mobile (Expo)

Citizen app — Expo React Native, Android-first, iOS via Expo Go / EAS.

## Run (dev)

```bash
# from the repo root, start the API (binds 0.0.0.0 so devices can reach it)
make api-dev

# then, in another shell
cd apps/mobile
npx expo start          # open in Expo Go, or press i / a for simulators
```

## API base URL

Resolved in `lib/api.ts`, in priority order:

1. **`EXPO_PUBLIC_API_BASE_URL`** — explicit override (set in `.env`; see `.env.example`).
2. **Auto-derived LAN IP** from the Expo dev server — works in Expo Go on
   simulators *and* physical devices with no config (a phone's `localhost`
   is the phone, not your machine, so we use the host the device already
   connected to).
3. Emulator/simulator defaults (`10.0.2.2` / `localhost`).

Standalone/EAS builds have no dev server, so set the URL per build profile in
`eas.json` (the `preview`/`production` URLs there are placeholders — replace
them with your deployed API). `EXPO_PUBLIC_*` is inlined at build time, so
restart `expo start` after changing `.env`.
