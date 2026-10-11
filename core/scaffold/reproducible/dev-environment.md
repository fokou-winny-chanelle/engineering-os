# Dev environment

The goal: anyone (or any agent) gets the same toolchain in minutes, on any machine, including with poor internet.

| Layer | File | Command |
|---|---|---|
| Runtimes and CLIs | `mise.toml` + `mise.lock` | `mise install --locked` |
| App dependencies | your lockfiles (`uv.lock`, `pnpm-lock.yaml`, `pubspec.lock`, ...) | frozen installs only |
| Full Linux environment (Codespaces, cloud agents, Windows) | `.devcontainer/devcontainer.json` | "Reopen in Container" |
| Local services | `compose.yaml` (`eos scaffold compose`) | `docker compose up -d --wait` |

Rules:

- **Bumping a tool:** `mise lock --bump <tool>`, run the checks, and commit the lockfile diff in its own PR.
- **Production-grade reproducibility:** pin the devcontainer image by digest (`image@sha256:...`). Renovate can keep digests fresh.
- **Parallel agents:** give each task its own git worktree (`git worktree add ../wt-<task> -b <branch>`). Make the app start per worktree (ports and DB names from env), so agents don't collide.
- **Low connectivity:**
  - keep package caches warm (`uv cache`, the pnpm store, the pub cache);
  - vendor key docs into `docs/references/` (e.g. `<lib>-llms.txt`) so agents can read them offline;
  - prefer lockfile installs that hit the cache.
