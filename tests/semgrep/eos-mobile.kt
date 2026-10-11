// Fixtures for core/scaffold/mobile/semgrep-mobile.yml (Android, Kotlin).
import android.content.Context
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.X509TrustManager

class TrustAll : X509TrustManager {
    // ruleid: eos-kotlin-empty-trust-manager
    override fun checkServerTrusted(chain: Array<java.security.cert.X509Certificate>, authType: String) {}
}

fun verifiers(builder: okhttp3.OkHttpClient.Builder) {
    // ruleid: eos-kotlin-trust-all-hostname
    val v = HostnameVerifier { _, _ -> true }
    // ruleid: eos-kotlin-trust-all-hostname
    builder.hostnameVerifier { _, _ -> true }
    // ok: eos-kotlin-trust-all-hostname
    builder.hostnameVerifier { host, _ -> host == "api.example.cm" }
}

fun files(ctx: Context, token: String) {
    // ruleid: eos-kotlin-world-readable
    ctx.openFileOutput("x.txt", Context.MODE_WORLD_READABLE)
    // ok: eos-kotlin-world-readable
    ctx.openFileOutput("x.txt", Context.MODE_PRIVATE)
    val e = ctx.getSharedPreferences("app", Context.MODE_PRIVATE).edit()
    // ruleid: eos-kotlin-prefs-token
    e.putString("auth_token", token)
    // ok: eos-kotlin-prefs-token
    e.putString("theme", "dark")
}

fun web(w: android.webkit.WebView) {
    // ruleid: eos-kotlin-webview-file-access
    w.settings.setAllowUniversalAccessFromFileURLs(true)
    // ruleid: eos-kotlin-webview-file-access
    w.settings.allowFileAccessFromFileURLs = true
    // ok: eos-kotlin-webview-file-access
    w.settings.allowFileAccessFromFileURLs = false
}
