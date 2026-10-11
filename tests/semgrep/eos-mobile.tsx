// Fixtures for core/scaffold/mobile/semgrep-mobile.yml (JSX sinks).
import { WebView } from "react-native-webview";
import { useLocalSearchParams } from "expo-router";

export function Help() {
  const { url } = useLocalSearchParams();
  // ruleid: eos-rn-deeplink-to-sink
  const a = <WebView source={{ uri: url }} />;
  // ok: eos-rn-deeplink-to-sink
  const b = <WebView source={{ uri: "https://help.example.cm" }} />;
  // ruleid: eos-rn-webview-any-origin
  const c = <WebView originWhitelist={["*"]} source={{ uri: "https://help.example.cm" }} />;
  // ok: eos-rn-webview-any-origin
  const d = <WebView originWhitelist={["https://help.example.cm"]} source={{ uri: "https://help.example.cm" }} />;
  return [a, b, c, d];
}
