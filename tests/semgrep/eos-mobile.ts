// Fixtures for core/scaffold/mobile/semgrep-mobile.yml (React Native / Expo, TypeScript).
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { Linking } from "react-native";
import axios from "axios";

async function store(token: string) {
  // ruleid: eos-rn-asyncstorage-token
  await AsyncStorage.setItem("refresh_token", token);
  // ruleid: eos-rn-asyncstorage-token
  await AsyncStorage.setItem("userPin", "1234");
  // ok: eos-rn-asyncstorage-token
  await AsyncStorage.setItem("onboarding_done", "1");
  // ok: eos-rn-asyncstorage-token
  await SecureStore.setItemAsync("refresh_token", token);
}

// ruleid: eos-rn-public-env-secret
const stripe = process.env.EXPO_PUBLIC_STRIPE_SECRET_KEY;
// ruleid: eos-rn-public-env-secret
const admin = process.env.EXPO_PUBLIC_SUPABASE_SERVICE_ROLE_KEY;
// ok: eos-rn-public-env-secret
const api = process.env.EXPO_PUBLIC_API_URL;

async function net() {
  // ruleid: eos-rn-cleartext-url
  await fetch("http://api.example.cm/v1/invoices");
  // ruleid: eos-rn-cleartext-url
  await axios.get("http://api.example.cm/v1/me");
  // ruleid: eos-rn-cleartext-url
  const c = axios.create({ timeout: 15000, baseURL: "http://api.example.cm" });
  // ok: eos-rn-cleartext-url
  await fetch("https://api.example.cm/v1/invoices");
  // ok: eos-rn-cleartext-url
  await fetch("http://10.0.2.2:8000/health");
  // ok: eos-rn-cleartext-url
  await fetch("http://localhost:8081/status");
}

const ALLOWED = new Set(["https://pay.example.cm"]);
const allowedUrl = (u: string, ok: Set<string>) => (ok.has(u) ? u : "https://example.cm");
function useLink(route: any) {
  const { next } = route.params;
  // ruleid: eos-rn-deeplink-to-sink
  Linking.openURL(next);
  // ok: eos-rn-deeplink-to-sink
  Linking.openURL(allowedUrl(next, ALLOWED));
  // ok: eos-rn-deeplink-to-sink
  Linking.openURL("https://example.cm/help");
}
