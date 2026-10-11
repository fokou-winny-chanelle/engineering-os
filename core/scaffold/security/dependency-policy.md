# Dependency policy
1. **Need first.** Prefer the standard library or an existing dependency. A new one needs a reason in the PR.
2. **Check before adding:** it exists under that exact name (typosquats), is maintained (release in the last 12 months), has more than one maintainer or a backing org, has an OSI licence we allow (no AGPL in services without legal sign-off), and its install size is reasonable.
3. **Pin and lock.** Lockfiles are committed; CI installs frozen (`uv sync --locked`, `--frozen-lockfile`).
4. **Updates** come from Renovate (`.github/renovate.json`): grouped minors weekly, majors one at a time with release notes read. Security fixes skip the queue.
5. **Scanning:** `pip-audit` / package-manager audit in CI, dependency review on PRs, SBOM on main (`security.yml`).
6. **Removal.** Unused dependencies are removed in the same PR that stops using them.
