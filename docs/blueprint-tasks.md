# Blueprint tasks — climb game (Only Up shape)

Step-by-step work for `BP_BOT`, `ABP_BOT`, the HUD and the game mode.
Everything here uses stock nodes; no C++ needed.

Order matters — 1 and 2 are what make a precision climber feel fair, and
3 is probably the bug you already feel.

---

## 0. Decision first: keep the double jump?

I set `JumpMaxCount = 2` when you asked to be able to jump again. For a
climbing game that is a real design choice:

| | With double jump | Without (`JumpMaxCount = 1`) |
|---|---|---|
| Feel | forgiving, recover from bad jumps | every jump commits, real tension |
| Genre fit | closer to Mario Odyssey | closer to Only Up / Jump King |
| Tower | current gaps stay easy | gaps are already sized for a single jump, still works |

The tower is built and validated for the **single** jump, so switching to
1 breaks nothing. Tell me which you want and I flip it in one command.

---

## 1. Coyote time (~0.12 s)

Lets you still jump for a fraction of a second after walking off a ledge.
In a climbing game this removes most "but I *was* on it!" deaths.

In **`BP_BOT`**:

1. Add float variable `CoyoteTimer` (default 0).
2. Add float variable `CoyoteWindow` (default `0.12`), so you can tune it.
3. Add event **`On Movement Mode Changed`** (right-click graph → search it):
   - `Prev Movement Mode` **Equal** `Walking`  →  Branch
   - True: `Set CoyoteTimer = CoyoteWindow`
4. On **`Event Tick`**:
   - `CoyoteTimer` → `FMax(CoyoteTimer - Delta Seconds, 0.0)` → `Set CoyoteTimer`
5. Where the jump input is handled (`IA_Jump`, Triggered):
   - Get `Character Movement` → `Is Falling`
   - Branch:
     - **False** (on ground) → `Jump`
     - **True** → check `CoyoteTimer > 0` → if yes: `Set CoyoteTimer = 0`, then `Jump`

> `Jump` refuses to fire while falling if `JumpCurrentCount` is spent. With
> `JumpMaxCount = 2` the air jump covers this anyway; with 1, the coyote
> branch is what saves you.

---

## 2. Jump buffering (~0.15 s)

Press jump slightly before landing and it fires on touchdown instead of
being swallowed.

In **`BP_BOT`**:

1. Add float `JumpBufferTimer` (default 0), float `JumpBufferWindow` (0.15).
2. In the `IA_Jump` handler, on the branch where the jump could **not**
   happen (falling, no coyote, no air jump left):
   - `Set JumpBufferTimer = JumpBufferWindow`
3. On `Event Tick`, count it down the same way as `CoyoteTimer`.
4. Add event **`On Landed`**:
   - Branch on `JumpBufferTimer > 0`
   - True → `Set JumpBufferTimer = 0` → `Jump`

---

## 3. Remove the landing lock  ← the "can't jump right after landing" bug

This project has `Falling_To_Landing`, `Hard_Landing`, `Standing_Up` and
the `ELandingType` enum. There is **no** jump-gating variable on `BP_BOT`,
so whatever blocks the next jump is animation-side, in `ABP_BOT`.

Open **`ABP_BOT`** and check, in the landing states:

1. **Root motion.** If the landing / recovery montage or state uses root
   motion, it owns the capsule and eats input. Either:
   - turn root motion off for the normal landing, or
   - make the recovery an **additive** layer over locomotion, or
   - cap the state's blend-out to ~0.1 s.
2. **Which landings play it.** A recovery animation should only fire on a
   *hard* landing. Gate the transition on fall time or impact velocity,
   e.g. only when `|Velocity.Z|` on landing exceeds ~900. Normal hops go
   straight back to the locomotion state.
3. **Never** call `Disable Input` or `Set Ignore Move Input` on `On Landed`
   in `BP_BOT`. If that exists, delete it.

Test: land from a small hop and press jump immediately. It should fire on
the same frame you touch down.

---

## 4. Jump input release (needed for variable jump height)

I set `JumpMaxHoldTime = 0.28`, which only does something if the input
release calls `Stop Jumping`.

In **`BP_BOT`**, on the `IA_Jump` Enhanced Input node:
- `Started` / `Triggered` → `Jump`
- **`Completed`** → **`Stop Jumping`**   ← add this if missing

Result: tap = short hop, hold = full height. Essential for a climber where
you often want a *small* hop onto a close ledge.

---

## 5. Height HUD — the core of the genre

Only Up lives on the number going up.

1. Create Widget Blueprint `WBP_Climb`:
   - `Text` block `Txt_Height`, big, top-centre
   - `Text` block `Txt_Best`, smaller, under it
2. In `WBP_Climb` graph, on **`Event Tick`** (or a 0.1 s timer):
   - `Get Player Pawn` → `Get Actor Location` → break → `Z`
   - `(Z - GroundZ) / 100` → `Format Text` `"{0} m"` → `Set Text (Txt_Height)`
   - store `GroundZ` as a variable; the tower base is at Z = 0
3. In `BP_BOT` `Event BeginPlay`: `Create Widget (WBP_Climb)` → `Add to Viewport`.

**Best height** (the thing you're afraid to lose):
- In `GM_MainGame` add float `BestHeight`.
- On tick, `BestHeight = FMax(BestHeight, CurrentHeight)`.
- Show it in `Txt_Best` as `"Best: {0} m"`.
- Do **not** reset it on a fall — that's the whole point.

---

## 6. Fall = lost progress, not death

Already handled on the level side: `KillZ` is pushed to -100000 and a wide
`OC_Ground` floor catches every fall, so you survive and re-climb.

Check in `BP_BOT` that nothing applies fall damage or kills on landing.
`ACharacter` has none by default, so this should be nothing to do.

---

## 7. Optional mechanic — ledge mantle

The one mechanic that most improves a climber: when you *almost* make a
ledge, you pull up instead of sliding off.

In `BP_BOT`, on `Event Tick` while `Is Falling` and `Velocity.Z < 0`:

1. `Line Trace By Channel` forward from chest height, length ~70.
   - No hit → done.
2. From `HitLocation + ForwardVector * 40 + Up * 120`, trace **down** 160.
   - No hit → done (nothing to stand on).
3. If the second hit's `ImpactNormal.Z > 0.7` (flat enough to stand on):
   - `Set Movement Mode = Flying` (stops the fall)
   - `Move Component To` the capsule to `SecondHit.ImpactPoint + Up * 90`
     over ~0.25 s
   - On finish: `Set Movement Mode = Walking`
4. Add a bool `bMantling` so it can't retrigger mid-pull.

Later you can swap the `Move Component To` for a mantle montage with root
motion; the trace logic stays the same.

---

## 8. Optional — fast fall

Makes the descent snappier than the rise (a Celeste-ism), which reads much
better in a climbing game because you spend a lot of time falling.

On `Event Tick`:
- `Is Falling` **and** `Velocity.Z < 0` → `Set Gravity Scale = 2.0`
- else → `Set Gravity Scale = 1.5`

> If you do this, re-run `build_tower.py` afterwards. The generator reads
> `GravityScale` to size every gap, so changing it changes the tower.
