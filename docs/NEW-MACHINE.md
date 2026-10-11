# New machine: from a blank PC to Cursor + Cline + eos

One page, about 15 minutes. You need an internet connection and your keys (see step 5). The steps are written for **Windows 10/11**; macOS and Linux notes are at the end. Commands go in a **terminal** (on Windows: PowerShell). Paste one line, press Enter, wait for it to finish.

## 1. Install the three programs
1. **Cursor**: download it from [cursor.com](https://cursor.com) and install it. Open it once and sign in, then close it.
2. **Git** and **Python** (3.11 or newer). Open PowerShell (Start menu, type `PowerShell`) and run:
   ```powershell
   winget install --id Git.Git -e
   winget install --id Python.Python.3.13 -e
   ```
   If you use the python.org installer instead, tick **Add python.exe to PATH** on its first screen.
3. **Close PowerShell and open a new one**, so it sees the new programs. Check: `git --version` and `python --version` both print a version.

## 2. Download engineering-os
Pick a folder for your projects. This guide uses `C:\Projects`; any folder works (a path with spaces is fine).
```powershell
mkdir C:\Projects -Force
git clone https://github.com/fokou-winny-chanelle/engineering-os C:\Projects\engineering-os
```

## 3. Run the setup script
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Projects\engineering-os\bootstrap.ps1" --tools "cursor,cline"
```
It installs `uv` and `pre-commit` if missing, creates the `eos` command, writes the shared rules and connector (MCP) settings for Cursor and Cline, **installs the Cline extension into Cursor**, and creates your private keys file. It's safe to run again at any time. At the end it prints **"What only you can do now"**: that list is the rest of this guide, adapted to your machine.

## 4. Open a new terminal
Close PowerShell and open a new one, so the `eos` command is found. Run `eos doctor`. Every line that isn't `ok` ends with the fix.

## 5. Put your keys back
Keys (passwords for services) are never stored in Git, so a new machine starts without them.
1. Open the keys file: `notepad "$HOME\.config\engineering-os\secrets.env"`
2. Fill in the empty lines the setup script listed, for example `CONTEXT7_API_KEY=...` (free key from [context7.com](https://context7.com)). Others, like `GITHUB_MCP_PAT`, are only needed when you switch on more connectors (`eos mcp use build`).
3. Save, then run the setup script from step 3 again. On Windows it also copies the keys Cursor needs into your user environment variables (it never prints them). **Restart Cursor** (close every window) afterwards.

Keep a copy of every key in a password manager. Never paste keys into a chat, a commit or a file inside a project. Your **OpenRouter** key does not go in this file; it goes into Cline (step 6).

## 6. Set up Cline (the cheaper agent)
1. Open Cursor. Press `Ctrl+Shift+P`, type `cline focus`, click **Cline: Focus on View**. The Cline panel opens on the left.
   (No Cline commands? Restart Cursor. Still none? Install it by hand: `Ctrl+Shift+X`, search `Cline`, Install.)
2. On Cline's welcome screen choose **Bring my own API key**, then **Continue**.
3. **API Provider**: choose **OpenRouter**. Paste your OpenRouter key (create one at [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys); give it a spending limit, and add credit under Credits).
4. Tick **Use different models for Plan and Act modes** and set:

   | Mode | Model | Reasoning effort | Price per million tokens, in / out (OpenRouter, as of Oct 2026) |
   |---|---|---|---|
   | Act (edits files) | `anthropic/claude-haiku-5.5` | None | $0.10 / $0.50 |
   | Plan (thinks) | `anthropic/claude-sonnet-5.5` | Low | $2 / $10 |

   Pick the plain version number, not "latest". You can change models any time from the model name under Cline's chat box.
5. Click **Continue**. Type `say hello` in Cline's chat. A reply means it works.

## 7. Check everything
- `eos doctor`: machine setup, tools, keys.
- `eos mcp status`: which connectors each tool has switched on.
- In Cline, the connectors icon (**MCP Servers**) should list `context7` as connected.

## 8. Start working
Open a project folder in Cursor (File > Open Folder), open its terminal (`` Ctrl+` ``) and run:
- `eos adopt` for existing code (it changes none of your files; it writes a map, a report and a plan), or
- `eos start` for a new idea.

Then `eos next` tells you the one next step and the sentence to give your agent. The plain-language guide is [GUIDE.md](GUIDE.md).

## Troubleshooting
- **`eos` is not recognized**: open a new terminal (the setup added it to your PATH). Still missing? Run `eos doctor` via `python C:\Projects\engineering-os\bin\eos.py doctor`; it prints the PATH fix.
- **"running scripts is disabled on this system"**: use the exact `powershell -ExecutionPolicy Bypass -File ...` line from step 3, or allow your own scripts once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Cline or connectors don't show up**: restart Cursor (close every window, not just one). Cursor reads environment variables and extensions only at start.
- **`python` opens the Microsoft Store**: that's a Windows shortcut, not Python. Install Python as in step 1, then open a new terminal.
- **Cline replies with an error about credit or the key**: check your balance and key on OpenRouter, then paste the key again in Cline's settings (gear icon).

## macOS and Linux
- Install Cursor from [cursor.com](https://cursor.com). Git and Python: macOS `xcode-select --install` and `brew install python`; Debian/Ubuntu `sudo apt-get install -y git python3`.
- Steps 2 and 3: `git clone https://github.com/fokou-winny-chanelle/engineering-os ~/Projects/engineering-os`, then `~/Projects/engineering-os/bootstrap.sh --tools cursor,cline`.
- If Cline isn't installed automatically, in Cursor run `Shell Command: Install 'cursor' command in PATH` (macOS) and re-run the script, or install Cline from the Extensions panel.
- Keys file: `~/.config/engineering-os/secrets.env`. Cursor started from the Dock may not see your shell's variables: start it from a terminal (`cursor .`) or see [bootstrap.md](bootstrap.md#caveats).
- Shortcuts use `Cmd` instead of `Ctrl` on macOS. Everything else is the same.

More detail (what goes where, per-OS notes): [bootstrap.md](bootstrap.md).
