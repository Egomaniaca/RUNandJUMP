"""
build_tower.py

Builds a vertical climbing tower in the currently open level -- the
"Only Up" / Jump King shape: you spiral upward, every jump is precise,
and a single fall costs you the climb.

Genre rules this follows:

  * VERTICAL, not horizontal. Progress is height.
  * NO KillZ. Falling must not kill -- it drops you back down the tower,
    which is the whole punishment. A wide catch floor sits at the base.
  * Reach is computed from the pawn's real CharacterMovement values by
    solving the jump arc, not guessed. Every gap is validated against it
    and the script warns if a section is unreachable.
  * Difficulty is expressed as a FRACTION of max reach per section, so
    retuning the character automatically retunes the tower.
  * Platforms shrink and gaps widen as you climb; short "rest" ledges
    break the tension before each harder section.

--------------------------------------------------------------------------
HOW TO RUN (inside the Unreal Editor, with the level open)

  Tools > Execute Python Script...    -> pick this file
      or, in the Output Log console:
  py "D:/GAMEDEV/RUNandJUMP/Content/Python/build_tower.py"

Re-running is safe: generated actors carry the "OC_" prefix and live in
the "ObstacleCourse" outliner folder; they are deleted first.
Press Ctrl+S afterwards to save the level.
--------------------------------------------------------------------------
"""

import math
import unreal

# ============================================================ CONFIG =====
TOWER_ORIGIN = unreal.Vector(0.0, 0.0, 0.0)   # centre of the tower, base level

PLATE_THICK = 40.0
CATCH_FLOOR_SIZE = 6000.0   # wide floor at the base that catches every fall

# Each section: how many platforms, the vertical step range, the platform
# size range, the spiral radius, and difficulty as a fraction of the
# character's maximum horizontal reach for that vertical step.
#   difficulty 0.45 = comfortable, 0.75 = tight, 0.85 = cruel
SECTIONS = [
    dict(name="Base",    count=6,  dz=(90, 110),   size=(460, 400), radius=760,  difficulty=0.42),
    dict(name="Spiral",  count=8,  dz=(105, 125),  size=(380, 320), radius=820,  difficulty=0.52),
    dict(name="Narrow",  count=8,  dz=(110, 130),  size=(300, 240), radius=780,  difficulty=0.60),
    dict(name="Leap",    count=6,  dz=(95, 115),   size=(300, 260), radius=1000, difficulty=0.72),
    dict(name="Pillars", count=8,  dz=(115, 140),  size=(220, 170), radius=740,  difficulty=0.70),
    dict(name="Spire",   count=8,  dz=(120, 145),  size=(190, 150), radius=620,  difficulty=0.78),
    dict(name="Summit",  count=3,  dz=(100, 115),  size=(420, 520), radius=420,  difficulty=0.45),
]

# ---- ART -----------------------------------------------------------------
# Swap in downloaded Fab / Megascans content here; the layout never changes.
# Anything that fails to load falls back to the grid material, so a missing
# asset degrades gracefully instead of breaking the build.
#
# MESH: any static mesh works, but it must be a UNIT-ish shape that scales
# cleanly -- a cube is ideal. A decorative rock will stretch.
PLATFORM_MESH = "/Engine/BasicShapes/Cube.Cube"

# MATERIALS: assign per section name; "*" is the fallback for anything
# unnamed (tiers, shelves, ground). Example once Megascans are imported:
#   "Base": "/Game/Megascans/Surfaces/Rock_Cliff/MI_Rock_Cliff",
MATERIALS = {
    "*": "/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial",
}

# Catch tiers: a wide disc on the tower axis that stops a fall partway.
#
# EMPTY BY DESIGN. A tier is a ceiling as well as a floor: the platforms
# below it sit inside its footprint, so the climb runs head-first into its
# underside. Tiers must therefore be RARE and placed only where the spiral
# is clear of them. List the section names to cap, e.g. ["Narrow"], once
# you have picked spots.
TIER_AFTER_SECTIONS = []

TIER_SIZE = 3000.0           # must cover the spiral radius so falls land on it
TIER_THICK = 90.0
TIER_APPROACH_SIZE = 440.0   # ledge just outside the tier rim, to jump on from
TIER_APPROACH_GAP = 240.0    # how far outside the rim that ledge sits
TIER_STEP_SIZE = 380.0       # pads of the shelf that walks out to that ledge

MOVE_PLAYER_START = True
CLEAR_KILL_Z = True          # push KillZ far below: a fall must NOT kill

LABEL_PREFIX = "OC_"
OUTLINER_FOLDER = "ObstacleCourse"
PAWN_CLASS_PATH = "/Game/Player/BP_BOT.BP_BOT_C"
GRAVITY_CM = 980.0
# ========================================================================

_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _load(path, what):
    """Load an asset, warning once and returning None if it isn't there."""
    if not path:
        return None
    asset = unreal.load_asset(path)
    if asset is None:
        unreal.log_warning("[tower] %s not found: %s" % (what, path))
    return asset


_MESH = (_load(PLATFORM_MESH, "mesh")
         or unreal.load_asset("/Engine/BasicShapes/Cube.Cube"))
_MAT_CACHE = {}


def _material_for(label):
    """Material for a pad, chosen by the section name inside its label."""
    for name, path in MATERIALS.items():
        if name != "*" and name in label:
            if path not in _MAT_CACHE:
                _MAT_CACHE[path] = _load(path, "material")
            if _MAT_CACHE[path]:
                return _MAT_CACHE[path]
            break
    fallback = MATERIALS.get("*")
    if fallback not in _MAT_CACHE:
        _MAT_CACHE[fallback] = _load(fallback, "material")
    return _MAT_CACHE[fallback]


# ------------------------------------------------------------ jump math --
class Jump(object):
    """Solves the character's real jump arc from CharacterMovement values."""

    def __init__(self):
        try:
            cls = unreal.load_class(None, PAWN_CLASS_PATH)
            cdo = unreal.get_default_object(cls)
            cmc = cdo.get_editor_property("character_movement")
            self.speed = float(cmc.get_editor_property("max_walk_speed"))
            self.jump_z = float(cmc.get_editor_property("jump_z_velocity"))
            self.grav_scale = float(cmc.get_editor_property("gravity_scale"))
            self.jump_count = int(cdo.get_editor_property("jump_max_count"))
            self.step_height = float(cmc.get_editor_property("max_step_height"))
        except Exception as exc:
            unreal.log_warning("[tower] cannot read pawn movement (%s)" % exc)
            self.speed, self.jump_z = 600.0, 720.0
            self.grav_scale, self.jump_count, self.step_height = 1.5, 2, 45.0
        self.g = GRAVITY_CM * self.grav_scale

    @property
    def max_rise(self):
        """Peak height of a single jump."""
        return self.jump_z ** 2 / (2.0 * self.g)

    def reach(self, rise):
        """Max horizontal distance while ending `rise` units higher.

        Solves  jump_z*t - g/2*t^2 = rise  and takes the descending root,
        so the character is falling onto the ledge rather than still rising.
        """
        if rise >= self.max_rise:
            return 0.0
        disc = self.jump_z ** 2 - 2.0 * self.g * rise
        t = (self.jump_z + math.sqrt(max(disc, 0.0))) / self.g
        return self.speed * t

    def describe(self):
        return ("speed=%.0f jump_z=%.0f grav=%.2f jumps=%d | max_rise=%.0f "
                "reach(flat)=%.0f" % (self.speed, self.jump_z, self.grav_scale,
                                      self.jump_count, self.max_rise,
                                      self.reach(0.0)))


# ------------------------------------------------------------- spawning --
def _spawn_box(location, scale, label):
    actor = _actors.spawn_actor_from_class(unreal.StaticMeshActor, location)
    smc = actor.static_mesh_component
    smc.set_mobility(unreal.ComponentMobility.MOVABLE)
    smc.set_static_mesh(_MESH)
    mat = _material_for(label)
    if mat:
        smc.set_material(0, mat)
    actor.set_actor_scale3d(scale)
    smc.set_mobility(unreal.ComponentMobility.STATIC)
    actor.set_actor_label(label)
    actor.set_folder_path(OUTLINER_FOLDER)
    return actor


def add_pad(x, y, top_z, size, label, thickness=PLATE_THICK):
    """Square pad centred on (x,y) whose TOP surface sits at `top_z`."""
    loc = unreal.Vector(x, y, top_z - thickness * 0.5)
    scale = unreal.Vector(size / 100.0, size / 100.0, thickness / 100.0)
    return _spawn_box(loc, scale, label)


# -------------------------------------------------------------- helpers --
def clear_tower():
    removed = 0
    for a in _actors.get_all_level_actors():
        if a.get_actor_label().startswith(LABEL_PREFIX):
            _actors.destroy_actor(a)
            removed += 1
    if removed:
        unreal.log("[tower] removed %d existing actors" % removed)


def move_player_start(location):
    for a in _actors.get_all_level_actors():
        if isinstance(a, unreal.PlayerStart):
            a.set_actor_location(location, False, True)
            unreal.log("[tower] PlayerStart moved to %s" % location)
            return
    unreal.log_warning("[tower] no PlayerStart found - place one on OC_Ground")


def clear_kill_z():
    """A fall must cost progress, not life. Push KillZ far out of reach."""
    for a in _actors.get_all_level_actors():
        if isinstance(a, unreal.WorldSettings):
            a.set_editor_property("kill_z", TOWER_ORIGIN.z - 100000.0)
            unreal.log("[tower] KillZ pushed to %.0f (falls are survivable)"
                       % (TOWER_ORIGIN.z - 100000.0))
            return
    unreal.log_warning("[tower] WorldSettings not found - KillZ unchanged")


def lerp(a, b, t):
    return a + (b - a) * t


def advance(cx, cy, prev_pos, radius, want_dist):
    """Angle step that puts the next point `want_dist` from the previous one.

    The previous point may sit on a different radius (sections change radius,
    and shelves walk outward), so this solves the triangle properly instead of
    assuming a common circle:

        d^2 = r_prev^2 + R^2 - 2*r_prev*R*cos(dtheta)

    Two points on circles of radius r_prev and R can never be closer than
    |R - r_prev|; if `want_dist` asks for less, the step collapses to 0 and
    the caller gets that minimum. Returns (dtheta, achievable_distance).
    """
    r_prev = math.hypot(prev_pos[0] - cx, prev_pos[1] - cy)
    if r_prev < 1e-3 or radius < 1e-3:
        return 0.0, abs(radius - r_prev)
    cos_d = (r_prev ** 2 + radius ** 2 - want_dist ** 2) / (2.0 * r_prev * radius)
    cos_d = max(-1.0, min(1.0, cos_d))
    dtheta = math.acos(cos_d)
    actual = math.sqrt(max(r_prev ** 2 + radius ** 2
                           - 2.0 * r_prev * radius * math.cos(dtheta), 0.0))
    return dtheta, actual


# ---------------------------------------------------------------- build --
def build():
    clear_tower()
    jump = Jump()
    unreal.log("[tower] %s" % jump.describe())

    cx, cy, base_z = TOWER_ORIGIN.x, TOWER_ORIGIN.y, TOWER_ORIGIN.z

    # Wide floor: every fall lands here instead of killing.
    add_pad(cx, cy, base_z, CATCH_FLOOR_SIZE, "OC_Ground", thickness=200.0)

    theta = 0.0
    z = base_z
    prev_half = CATCH_FLOOR_SIZE * 0.5
    prev_pos = (cx, cy)
    index = 0
    warnings = 0

    for s_i, sec in enumerate(SECTIONS):
        # A catch tier caps this section only if it was asked for. A tier is
        # also a ceiling, so it is opt-in per section rather than automatic.
        if s_i > 0 and SECTIONS[s_i - 1]["name"] in TIER_AFTER_SECTIONS:
            tier_half = TIER_SIZE * 0.5
            appr_r = tier_half + TIER_APPROACH_GAP

            # 1) A shelf that walks outward from the spiral to just past the
            #    tier rim. Without it the approach ledge would be further
            #    from the spiral than one jump can cover: two points on
            #    circles of radius r1 and r2 are never closer than |r1-r2|.
            r_now = math.hypot(prev_pos[0] - cx, prev_pos[1] - cy)
            step_i = 0
            while r_now < appr_r - 1.0:
                dz = 90.0
                reach = jump.reach(dz)
                want = 0.40 * reach + prev_half + TIER_STEP_SIZE * 0.5
                r_next = min(r_now + want, appr_r)
                theta += 0.10          # a little swing so it reads as a shelf
                z += dz
                sx = cx + r_next * math.cos(theta)
                sy = cy + r_next * math.sin(theta)
                step_i += 1
                add_pad(sx, sy, z, TIER_STEP_SIZE,
                        "OC_Shelf_%s_%02d" % (sec["name"], step_i))
                prev_half = TIER_STEP_SIZE * 0.5
                prev_pos = (sx, sy)
                r_now = r_next

            # 2) approach ledge, sitting just outside the tier rim
            dz = 95.0
            z += dz
            ax = cx + appr_r * math.cos(theta)
            ay = cy + appr_r * math.sin(theta)
            add_pad(ax, ay, z, TIER_APPROACH_SIZE,
                    "OC_Approach_%s" % sec["name"])

            # 3) the tier itself: jump inward and up onto its rim
            z += 110.0
            add_pad(cx, cy, z, TIER_SIZE, "OC_Tier_%s" % sec["name"],
                    thickness=TIER_THICK)

            # Standing anywhere on the tier, so the next jump starts from
            # directly under the first platform of the section: purely
            # vertical, no horizontal gap.
            prev_half = 0.0
            prev_pos = (cx + sec["radius"] * math.cos(theta),
                        cy + sec["radius"] * math.sin(theta))

        for i in range(sec["count"]):
            t = i / float(max(sec["count"] - 1, 1))
            dz = lerp(sec["dz"][0], sec["dz"][1], t)
            size = lerp(sec["size"][0], sec["size"][1], t)
            radius = sec["radius"]

            reach = jump.reach(dz)
            if reach <= 0.0:
                unreal.log_warning(
                    "[tower] %s #%d: rise %.0f exceeds max jump %.0f"
                    % (sec["name"], i, dz, jump.max_rise))
                warnings += 1
                dz = jump.max_rise * 0.75
                reach = jump.reach(dz)

            # Edge-to-edge gap we want, as a centre-to-centre distance.
            want = sec["difficulty"] * reach + prev_half + size * 0.5
            dtheta, _ = advance(cx, cy, prev_pos, radius, want)
            theta += dtheta

            z += dz
            px = cx + radius * math.cos(theta)
            py = cy + radius * math.sin(theta)

            actual = math.hypot(px - prev_pos[0], py - prev_pos[1]) \
                - prev_half - size * 0.5
            if actual > reach * 0.92:
                unreal.log_warning(
                    "[tower] %s #%d: gap %.0f vs reach %.0f - very tight"
                    % (sec["name"], i, actual, reach))
                warnings += 1

            index += 1
            add_pad(px, py, z, size,
                    "OC_%s_%02d" % (sec["name"], i + 1))
            prev_half = size * 0.5
            prev_pos = (px, py)

    # Summit marker: a tall thin pillar you can see from the ground.
    add_pad(prev_pos[0], prev_pos[1], z + 400.0, 90.0, "OC_SummitFlag",
            thickness=400.0)

    if CLEAR_KILL_Z:
        clear_kill_z()
    if MOVE_PLAYER_START:
        move_player_start(unreal.Vector(cx, cy, base_z + 130.0))

    unreal.log("[tower] built %d platforms + %d catch tiers, summit at "
               "Z=%.0f (%.1f m)"
               % (index, len(TIER_AFTER_SECTIONS), z, (z - base_z) / 100.0))
    if warnings:
        unreal.log_warning("[tower] %d reachability warnings - see above"
                           % warnings)


if __name__ == "__main__":
    build()
