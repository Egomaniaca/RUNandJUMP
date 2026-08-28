# Parkour movement — design notes

How movement-platformers / parkour games (Mirror's Edge, Ghostrunner,
Titanfall 2, Neon White, Mario Odyssey, Celeste for the feel) build a
jump that feels good, and what is / isn't done in this project yet.

## Applied to `BP_BOT` (CharacterMovement defaults, saved in the asset)

| Property | Was | Now | Why |
|---|---|---|---|
| `MaxWalkSpeed` | 250 | **600** | 250 is a crawl; parkour needs pace |
| `MaxAcceleration` | 2048 | **2400** | reach top speed fast |
| `BrakingDecelerationWalking` | 2048 | **1800** | a little slide / momentum |
| `JumpZVelocity` | 450 | **720** | 450 barely clears a crate |
| `AirControl` | 0.20 | **0.75** | steer the whole jump arc |
| `GravityScale` | 1.0 | **1.5** | tighter, less floaty arc |
| `JumpMaxCount` | 1 | **2** | air / double jump — recover mistakes, "jump again" |
| `JumpMaxHoldTime` | 0.0 | **0.28** | variable height: tap = hop, hold = full |

Flat jump now clears ~590 uu; more with a run-up, hold, or the second
jump. Re-run `Content/Python/build_obstacle_course.py` after changing
these — the gap widths there are matched to this tuning.

> `JumpMaxHoldTime` only gives variable height if the jump input releases
> call `StopJumping`. Check `BP_BOT`: the `IA_Jump` binding should be
> `Started/Triggered → Jump`, `Completed → Stop Jumping`. If `Completed`
> isn't wired, add it.

## Not done yet — needs event-graph work

These can't be set as properties; they're logic in `BP_BOT` (and
`ABP_BOT`). Recipes below use only stock nodes.

### 1. Coyote time (~0.12 s)
Lets you jump for a fraction of a second after walking off an edge — the
single biggest "why does this feel fair" fix.

- Add float `CoyoteTimer`.
- `Event OnMovementModeChanged`: if new mode is *Falling* **and** the
  character did not just jump (`WasJumping`/`JumpCurrentCount == 0`), set
  `CoyoteTimer = 0.12`.
- `Event Tick`: `CoyoteTimer = FMax(0, CoyoteTimer - DeltaSeconds)`.
- In the jump handler: allow the jump if `IsMovementMode(Walking)`
  **or** `CoyoteTimer > 0`. On a successful coyote jump set
  `CoyoteTimer = 0`.

### 2. Jump buffering (~0.15 s)
Press jump just before you land and it fires on touchdown instead of
being eaten.

- Add float `JumpBufferTimer`.
- Jump input pressed while falling: `JumpBufferTimer = 0.15`.
- `Event Tick`: count it down like the coyote timer.
- `Event OnLanded`: if `JumpBufferTimer > 0`, call `Jump` and reset it.

### 3. Remove the landing input-lock
This project has `Falling_To_Landing`, `Hard_Landing`, `Standing_Up`
and an `ELandingType` enum — a landing-recovery system. If you still
can't jump right after landing, that's the cause (no jump-gating
variable exists on `BP_BOT`, so the lock is animation-side).

- In `ABP_BOT`, the landing / recovery states must **not** use blocking
  root motion and must not sit on screen. Make the recovery pose an
  **additive** layer, or cap its blend to a few frames, or gate it to
  only play on a *hard* landing (fall time > ~0.8 s).
- Never call `DisableInput` / `SetIgnoreMoveInput` on `OnLanded`.
- Keep a cosmetic landing flourish only for big falls; normal landings
  should be instant.

### 4. Fast-fall gravity (optional, snappier)
`Event Tick`: if falling and `Velocity.Z < 0`, set `GravityScale = 2.0`,
else `1.5`. Makes the descent quicker than the rise (a Celeste-ism).

### 5. Air dash (optional)
On a dash input while falling, once per airtime:
`LaunchCharacter(GetActorForwardVector() * 1500, XYOverride=true,
ZOverride=false)`, then block re-dash until `OnLanded`.

### 6. Wall run (optional, bigger feature)
While falling, if a forward/side line trace hits a wall and horizontal
speed > ~400: zero `GravityScale`, add velocity along the wall tangent,
run a 1.2 s timer, restore gravity on timeout / input release / ground.

### 7. Ledge mantle (optional, bigger feature)
While falling near a wall, trace forward then down over the lip. If
there's a standable surface just above the capsule, `MoveComponentTo`
the character onto it (or play a mantle montage with root motion).

## Suggested order

1. Wire `StopJumping` on `IA_Jump` release (if missing).
2. Coyote time + jump buffering — cheap, huge feel gain.
3. Fix the landing lock in `ABP_BOT`.
4. Then the optional toys: fast-fall, air dash, wall run, mantle.
