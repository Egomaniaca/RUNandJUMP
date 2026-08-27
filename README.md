# RUNandJUMP

A third-person movement prototype built in **Unreal Engine 5.8**. The
project is Blueprint-only — there is no C++ `Source/` module.

## Overview

The player controls a locomotion-driven character (`BP_BOT`) across a single
test level. Movement, running, jumping and a set of falling / landing states
are wired up through Unreal's **Enhanced Input** system and an animation
blueprint with a locomotion blend space.

## Project layout

| Path | Contents |
|------|----------|
| `Config/` | Engine, game and input settings (`Default*.ini`) |
| `Content/Maps/Level_01` | The test level and default startup map |
| `Content/Data/GM_MainGame` | Default game mode |
| `Content/Data/Inputs/` | Enhanced Input actions (`IA_Move`, `IA_Look`, `IA_Jump`, `IA_Run`) and the `IMC_Default` mapping context |
| `Content/Player/` | Character blueprint, animation blueprint (`ABP_BOT`), skeleton, physics asset, blend space and locomotion / landing animations |

## Requirements

- Unreal Engine **5.8**
- `ModelingToolsEditorMode` plugin (bundled with the engine, enabled for the editor)

## Getting started

1. Clone the repository.
2. Open `RUNandJUMP.uproject` with Unreal Engine 5.8.
3. Press **Play** — `Level_01` is the default map.

### Default controls

| Action | Input |
|--------|-------|
| Move | `WASD` / left stick |
| Look | Mouse / right stick |
| Jump | `Space` / gamepad bottom face button |
| Run | `Left Shift` / gamepad left shoulder |

> Bindings are defined in `Content/Data/Inputs/IMC_Default`; open it in the
> editor to see or change the exact keys.

## Notes

Generated folders (`Binaries/`, `Intermediate/`, `DerivedDataCache/`,
`Saved/`) are excluded via `.gitignore` and are recreated by the editor on
first open. Unreal binary assets (`.uasset`, `.umap`) are marked as binary
in `.gitattributes` so Git never tries to diff or merge them.
