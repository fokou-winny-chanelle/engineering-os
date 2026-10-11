#!/usr/bin/env python3
"""Measure an MCP stdio server's tool-schema size (what Cline sends every request).

Usage: python3 tests/bench/mcp_schema_tokens.py [--json] -- <command> [args...]

Starts the server, sends initialize + tools/list over stdio (newline-delimited
JSON-RPC) and reports, per tool, name + description + JSON input schema at
chars/4 (the same method as the v0.6 numbers in mcp/README.md). It never calls
a tool. `McpClient` is reused by the tool tests to call tools.
"""

import json
import subprocess
import sys
import threading
import time


class McpClient:
    def __init__(self, cmd, env=None, cwd=None, timeout=180.0):
        self.timeout = timeout
        self.p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=cwd,
        )
        self.err = []
        self.msgs = {}
        self.cv = threading.Condition()
        self.next_id = 1
        threading.Thread(target=self._read_err, daemon=True).start()
        threading.Thread(target=self._read_out, daemon=True).start()

    def _read_err(self):
        for line in self.p.stderr:
            self.err.append(line)

    def _read_out(self):
        for line in self.p.stdout:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            with self.cv:
                if "id" in o:
                    self.msgs[o["id"]] = o
                self.cv.notify_all()
        with self.cv:
            self.cv.notify_all()

    def request(self, method, params=None):
        i = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})
        end = time.time() + self.timeout
        with self.cv:
            while i not in self.msgs:
                if time.time() > end or self.p.poll() is not None:
                    raise RuntimeError(
                        "no response to {} (exit={}): {}".format(method, self.p.poll(), "".join(self.err)[-3000:])
                    )
                self.cv.wait(0.5)
            return self.msgs.pop(i)

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def initialize(self):
        r = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "eos-measure", "version": "1"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r

    def list_tools(self):
        tools, cursor = [], None
        while True:
            r = self.request("tools/list", {"cursor": cursor} if cursor else {})
            res = r.get("result") or {}
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                return tools

    def call(self, name, args=None):
        r = self.request("tools/call", {"name": name, "arguments": args or {}})
        res = r.get("result") or {}
        text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        return res, text, r.get("error")

    def close(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait(5)
        for f in (self.p.stdout, self.p.stderr):
            try:
                f.close()
            except (OSError, ValueError):
                pass


def schema_tokens(tools):
    rows = []
    for t in tools:
        chars = len(t.get("name", "")) + len(t.get("description", "") or "")
        chars += len(json.dumps(t.get("inputSchema", {}), separators=(",", ":")))
        rows.append((t.get("name"), round(chars / 4)))
    return rows


def measure(cmd, env=None, timeout=180.0):
    c = McpClient(cmd, env=env, timeout=timeout)
    t0 = time.time()
    try:
        init = c.initialize()
        startup = time.time() - t0
        tools = c.list_tools()
    finally:
        c.close()
    rows = schema_tokens(tools)
    info = (init.get("result") or {}).get("serverInfo", {})
    return {
        "server": info,
        "startup_s": round(startup, 2),
        "tools": len(rows),
        "tokens": sum(r[1] for r in rows),
        "per_tool": rows,
    }


def main(argv):
    if "--" not in argv:
        print(__doc__)
        return 2
    r = measure(argv[argv.index("--") + 1 :])
    if "--json" in argv[: argv.index("--")]:
        print(json.dumps(r, indent=1))
        return 0
    s = r["server"]
    print(
        f"{s.get('name')} {s.get('version')}: {r['tools']} tools, ~{r['tokens']} tokens (startup {r['startup_s']:.2f}s)"
    )
    for name, tok in r["per_tool"]:
        print(f"  {name:<36} {tok:5d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
