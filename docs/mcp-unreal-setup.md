# Unreal Engine MCP setup (mcp-unreal)

This connects an MCP client (Claude Code, Cursor, …) to the running Unreal
Editor so it can read/set properties, drive Play-In-Editor, run headless
builds/tests, and — with the optional C++ plugin — edit Blueprints.

Server used: [`remiphilippe/mcp-unreal`](https://github.com/remiphilippe/mcp-unreal)
(Apache-2.0, community-maintained, **not affiliated with Epic**).

> ⚠️ **Caveats for this project**
> - The server documents **UE 5.7**; this project is on **5.8**. The
>   Remote Control path below still works, but the optional C++ plugin may
>   not compile without changes.
> - The optional `MCPUnreal` C++ plugin turns this Blueprint-only project
>   into a C++ project (needs a compiler + `Rebuild`). Only add it if you
>   actually need Blueprint-graph editing.
> - Both bridges listen on `localhost` HTTP (`30010`, `8090`). Anything
>   able to reach those ports can drive your editor. Don't forward them.

---

## 1. Enable Remote Control API (done in this repo)

`RUNandJUMP.uproject` now lists the `RemoteControl` plugin. On next editor
launch it is active. Verify while the editor is open:

```bash
curl http://localhost:30010/remote/info
```

A JSON response = the bridge is up. If the port differs, set `RC_API_PORT`
in the MCP config (step 4).

## 2. Install the MCP server binary

Pick one. **This step is yours to run** — it installs/executes a
third-party binary.

**Option A — build from source (needs [Go 1.25+](https://go.dev/dl/)):**

```bash
go install github.com/remiphilippe/mcp-unreal/cmd/mcp-unreal@latest
```

Binary lands in `%USERPROFILE%\go\bin\mcp-unreal.exe`.

**Option B — prebuilt binary:** download `windows-amd64` from
<https://github.com/remiphilippe/mcp-unreal/releases> and put it somewhere
stable, e.g. `%USERPROFILE%\bin\mcp-unreal.exe`.

Then build the docs index once:

```bash
mcp-unreal --build-index
```

## 3. (Optional) advanced Blueprint editing — C++ plugin

Only if you need graph-level Blueprint edits:

1. Copy the repo's `plugin/` folder to `Plugins/MCPUnreal/` in this project.
2. Regenerate project files, rebuild (needs Visual Studio + the UE 5.8
   toolchain). This creates a `Source/` module — the project is no longer
   Blueprint-only.
3. The plugin serves on `localhost:8090`.

If it fails to build against 5.8, skip it and stay on the Remote Control
feature set.

## 4. Register the server with Claude Code

Use **user scope** (do not commit `.mcp.json` — this repo is public and the
path is machine-local):

```bash
claude mcp add --scope user mcp-unreal -- "C:/Users/<you>/go/bin/mcp-unreal.exe"
```

Or edit your user MCP config directly:

```json
{
  "mcpServers": {
    "mcp-unreal": {
      "type": "stdio",
      "command": "C:/Users/<you>/go/bin/mcp-unreal.exe",
      "env": {
        "MCP_UNREAL_PROJECT": "D:/GAMEDEV/RUNandJUMP/RUNandJUMP.uproject"
      }
    }
  }
}
```

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_UNREAL_PROJECT` | auto-detected | path to the `.uproject` |
| `UE_EDITOR_PATH` | platform default | path to `UnrealEditor-Cmd.exe` (needed for headless build/test) |
| `RC_API_PORT` | `30010` | Remote Control API port |
| `PLUGIN_PORT` | `8090` | `MCPUnreal` plugin port |
| `MCP_UNREAL_LOG_LEVEL` | `info` | `debug` \| `info` \| `warn` \| `error` |

For headless build/test tools, also set (adjust to your install):

```
UE_EDITOR_PATH=D:/EpicGames/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe
```

## 5. Use it

1. Open `RUNandJUMP.uproject` in the editor.
2. Confirm `curl http://localhost:30010/remote/info` responds.
3. Restart the MCP client so it picks up the server.
4. The `mcp-unreal` tools should now be listed.

## Troubleshooting

- **No response on 30010** — plugin not enabled, or editor not running, or
  port in use. Check **Edit > Plugins > Remote Control API**.
- **MCP server starts but no editor tools work** — `MCP_UNREAL_PROJECT`
  wrong, or the editor was launched after the server; restart the client.
- **Headless build/test fail** — `UE_EDITOR_PATH` unset or wrong.
- **`go` not found** — install Go 1.25+ or use the prebuilt binary.
