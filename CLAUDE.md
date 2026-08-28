# RUNandJUMP

Vertical climbing game in the **Only Up / Jump King** shape: spiral up a
tower, one fall costs a section of the climb. Unreal Engine **5.8**,
**Blueprint-only** (no `Source/`, no C++ module).

Repo: <https://github.com/Egomaniaca/RUNandJUMP> (public)

> The user writes in Russian — reply in Russian.

## Design rules (decided with the user, don't quietly break them)

- **Progress is height.** Vertical, not a horizontal course.
- **A fall must not kill.** `KillZ` is pushed to -100000 and there is a
  60 m catch floor at the base. Falling costs progress, not a life.
- **Catch tiers**, one per section: a 30 m disc on the tower axis, so a
  fall drops you one section rather than to the ground.
- **Single jump.** `JumpMaxCount = 1` — deliberate; the air jump killed
  the tension the genre lives on.
- Camera stays **third person**.
- Art comes from **free Fab / Megascans** content; grey boxes for now.

## Layout

| Path | What |
|---|---|
| `Content/Maps/Level_01` | the only level, default startup map |
| `Content/Player/BP_BOT` | player character (stock Third Person template, retuned) |
| `Content/Player/ABP_BOT` | anim blueprint; landing states + `ELandingType` |
| `Content/Data/GM_MainGame` | game mode |
| `Content/Data/Inputs/` | Enhanced Input: `IA_Move/Look/Jump/Run`, `IMC_Default` |
| `Content/Python/build_tower.py` | **generates the whole tower** |
| `docs/blueprint-tasks.md` | event-graph work the user does by hand |
| `docs/parkour-movement.md` | movement design notes |
| `docs/mcp-unreal-setup.md` | MCP bridge setup |

## The tower generator

`Content/Python/build_tower.py` builds every platform. **Edit the script,
never hand-place actors** — a re-run deletes everything labelled `OC_`.

It reads the pawn's real `MaxWalkSpeed` / `JumpZVelocity` / `GravityScale`
and solves the jump arc, so gaps are expressed as a *fraction of actual
reach*. Retuning the character retunes the tower; re-run after any
movement change.

Current build: 74 actors, summit **83 m**, hardest jump **78%** of reach,
zero unreachable gaps.

Tuning knobs at the top: `SECTIONS` (count / dz / size / radius /
difficulty), `TIER_*`, `PLATFORM_MESH`, `MATERIALS`.

> Geometry gotcha already paid for: two points on circles of radius r1 and
> r2 are never closer than |r1-r2|. That is why reaching an axis-centred
> tier needs the outward `OC_Shelf_*` pads — a direct jump to the rim was
> 127-172% of reach.

## Driving the editor (MCP)

`mcp-unreal` is connected over the editor's **Remote Control API**
(`localhost:30010`). The optional C++ plugin (port 8090) is **not**
installed, so `spawn_actor`, `get_level_actors`, `run_console_command`,
`execute_script`, `search_assets` and `fab_ops` all fail.

**Everything is done through one call instead:**

```
mcp__mcp-unreal__call_function
  object_path:   /Script/PythonScriptPlugin.Default__PythonScriptLibrary
  function_name: ExecutePythonCommand
  parameters:    {"PythonCommand": "<python>"}
```

Two quirks to know:

1. The tool **always reports a schema validation error** — mcp-unreal's
   output schema rejects `{"ReturnValue": true}`. The call still ran.
   `true` = the Python succeeded, `false` = it raised.
2. Because of that you never see stdout. **Write results to a probe file
   and read it locally:**

```python
import unreal, json, traceback
out = {}
try:
    ...
except Exception:
    out['error'] = traceback.format_exc()[-700:]
open('D:/GAMEDEV/RUNandJUMP/Saved/probe.json','w').write(
    json.dumps(out, indent=1, default=str))
```

then `Read`/`node -e` that file and delete it. Wrap work in try/except or
a failure is invisible.

Run the generator:

```python
exec(open('D:/GAMEDEV/RUNandJUMP/Content/Python/build_tower.py',
          encoding='utf-8').read())
```

**Verify geometry with measurements, not assumptions** — read
`get_actor_bounds` and compare gaps against the solved reach. A sign error
in a ramp pitch shipped once because it looked fine in code.

The editor must be running with the level open. Requires (already on in
Project Settings → Remote Control): **Allow Any Remote Function Call** and
**Enable Remote Python Execution**.

### Lead: Epic's own MCP server

UE 5.8 ships `ModelContextProtocol` ("Unreal MCP", by Epic, Experimental)
— HTTP+SSE on port **8000**, path `/mcp`. The plugin is enabled in the
`.uproject` but the server is **not started** (no listener on 8000; it
needs `StartServer`). This would likely beat the third-party bridge —
worth finishing if editor control gets limiting.

## What cannot be done over the bridge

**Blueprint event graphs.** Properties and actors only. Anything needing
nodes (coyote time, jump buffering, the landing lock, HUD) is written up
as step-by-step instructions in `docs/blueprint-tasks.md` and the **user
does it in the editor** — that's the agreed split.

Known open item: the user reports not being able to jump immediately after
landing. There is no jump-gating variable on `BP_BOT`, so it is
animation-side in `ABP_BOT` (`Falling_To_Landing` / `Hard_Landing`).

## Movement values (in `BP_BOT`, set via MCP)

| | |
|---|---|
| MaxWalkSpeed | 600 |
| JumpZVelocity | 720 |
| GravityScale | 1.5 |
| AirControl | 0.75 |
| MaxAcceleration | 2400 |
| JumpMaxCount | **1** |
| JumpMaxHoldTime | 0.28 (needs `Stop Jumping` wired on input release) |

Derived: max jump height **176 uu**, flat reach **~490 uu**.

## Git

- **Git LFS** holds every `.uasset` / `.umap`. If assets on disk are
  ~131 bytes they are pointers, not content, and Unreal fails with
  *"appears to be an asset file"*. Fix: `git lfs pull`.
- `main` is protected: PR required, force-push and deletion blocked,
  `repo-hygiene` check must pass. Branch → PR → merge.
- CI (`.github/workflows/checks.yml`) fails on committed generated
  folders, non-LFS assets, non-LFS files > 1 MB, invalid `.uproject`.
- `gh` lives at `C:\Program Files\GitHub CLI` and is often not on PATH —
  prepend it.
- **Never commit `Level_01.umap` on the user's behalf.** Spawned actors
  live in memory until they press Ctrl+S; committing guesses at what the
  map contains. Ask them to save, then commit.
- Push / merge / force-push get blocked by the permission classifier —
  run them as isolated single commands and expect to hand them over.

## Working agreement

The user is the client, not the engineer: ask about design decisions
rather than guessing, and hand back a short list of what only they can do
(editor work, downloads, merges).
