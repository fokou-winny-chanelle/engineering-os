## What and why

## How it was tested
- [ ] `python3 -m unittest discover -s tests`
- [ ] `sh tests/selftest.sh` (POSIX) — or explain why not
- [ ] `python3 bin/eos.py budget` (always-on context did not grow) and `library lint --strict` if packs changed

## Risk
- [ ] Touches the guard hook, lanes, test integrity, MCP launchers or generated CI permissions (needs careful review)
- [ ] Changes files that eos writes into projects (mention the `eos update` behaviour)
- [ ] CHANGELOG entry added

AI assistance used: yes / no
