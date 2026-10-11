// Fixtures for core/scaffold/mobile/semgrep-mobile.yml (iOS, Swift).
import Foundation

func save(token: String) {
    // ruleid: eos-swift-userdefaults-token
    UserDefaults.standard.set(token, forKey: "accessToken")
    // ok: eos-swift-userdefaults-token
    UserDefaults.standard.set(true, forKey: "onboardingDone")
}
