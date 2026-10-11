#!/usr/bin/env sh
# A multi-repo workspace: 4 sibling git repos (contracts, api, web, infra) in one parent folder.
set -eu
d="$1"; rm -rf "$d"; mkdir -p "$d" && cd "$d"
mk() { mkdir -p "$1" && (cd "$1" && git init -q -b main && shift && "$@" && git add -A && git -c user.name=t -c user.email=t@x commit -qm init); }
contracts() { printf 'openapi: 3.1.0\ninfo: {title: shop, version: 1.0.0}\npaths: {}\n' > openapi.yaml; printf '# contracts\n' > README.md; }
api() {
  mkdir -p app tests
  printf '[project]\nname = "shop-api"\nversion = "0.1.0"\ndependencies = ["fastapi"]\n' > pyproject.toml
  printf 'from fastapi import FastAPI\napp = FastAPI()\n' > app/main.py
  for i in 1 2 3 4; do printf 'def f%s():\n    return %s\n' "$i" "$i" > app/m$i.py; done
  printf 'def test_ok():\n    assert True\n' > tests/test_main.py
}
web() {
  mkdir -p src
  printf '{"name":"shop-web","private":true,"scripts":{"build":"next build","lint":"eslint .","typecheck":"tsc --noEmit","test":"vitest run"},"dependencies":{"next":"15.0.0","react":"19.0.0"}}\n' > package.json
  printf 'API_URL=http://api:8000  # shop api\nAPI_SERVICE=api\n' > .env.example
  printf '{"compilerOptions":{"strict":true}}\n' > tsconfig.json
  printf 'export default function Page() { return null }\n' > src/page.tsx
}
infra() { printf 'terraform {}\n' > main.tf; printf '# infra\n' > README.md; }
mk contracts contracts
mk api api
mk web web
mk infra infra
