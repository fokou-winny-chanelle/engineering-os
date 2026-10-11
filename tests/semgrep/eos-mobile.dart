// Fixtures for core/scaffold/mobile/semgrep-mobile.yml (Flutter, Dart).
import 'dart:io';

void tls(HttpClient client) {
  // ruleid: eos-dart-bad-certificate-callback
  client.badCertificateCallback = (cert, host, port) => true;
  // ruleid: eos-dart-bad-certificate-callback
  client.badCertificateCallback = (cert, host, port) {
    return true;
  };
  // ok: eos-dart-bad-certificate-callback
  client.badCertificateCallback = (cert, host, port) => host == 'localhost';
}

Future<void> prefs(dynamic sp, String t) async {
  // ruleid: eos-dart-prefs-token
  await sp.setString('access_token', t);
  // ok: eos-dart-prefs-token
  await sp.setString('locale', 'fr');
}

void urls() {
  // ruleid: eos-dart-cleartext-url
  final a = Uri.parse("http://api.example.cm/v1/me");
  // ok: eos-dart-cleartext-url
  final b = Uri.parse("https://api.example.cm/v1/me");
  // ok: eos-dart-cleartext-url
  final c = Uri.parse("http://10.0.2.2:8000/health");
}

void dio() {
  // ruleid: eos-dart-cleartext-url
  final o = BaseOptions(connectTimeout: const Duration(seconds: 15), baseUrl: "http://api.example.cm");
  // ok: eos-dart-cleartext-url
  final p = BaseOptions(baseUrl: "https://api.example.cm");
}
