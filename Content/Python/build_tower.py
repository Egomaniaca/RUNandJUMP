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
    dict(name="Leap",    count=6,  dz=(95, 115),   size=(300, 260), radius=1050, difficulty=0.72),
    dict(name="Pillars", count=8,  dz=(115, 140),  size=(220, 170), radius=740,  difficulty=0.70),
    dict(name="Spire",   count=8,  dz=(120, 145),  size=(190, 150), radius=620,  difficulty=0.78),
    dict(name="Summit",  count=3,  dz=(100, 115),  size=(420, 520), radius=420,  difficulty=0.45),
]

REST_LEDGE_SIZE = 520.0      # a wide breather platform between sections
MOVE_PLAYER_START = True
CLEAR_KILL_Z = True          # push KillZ far below: a fall must NOT kill

LABEL_PREFIX = "OC_"
OUTLINER_FOLDER = "ObstacleCourse"
PAWN_CLASS_PATH = "/Game/Player/BP_BOT.BP_BOT_C"
GRAVITY_CM = 980.0
# ========================================================================

_CUBE = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
_GRID_MAT = unreal.load_asset("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")
_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


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
    smc.set_static_mesh(_CUBE)
    if _GRID_MAT:
        smc.set_material(0, _GRID_MAT)
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
        # A wide rest ledge announces each new section (except the first).
        if s_i > 0:
            dz = 100.0
            reach = jump.reach(dz)
            chord = min(0.40 * reach + prev_half + REST_LEDGE_SIZE * 0.5,
                        2.0 * sec["radius"] * 0.999)
            theta += 2.0 * math.asin(chord / (2.0 * sec["radius"]))
            z += dz
            px = cx + sec["radius"] * math.cos(theta)
            py = cy + sec["radius"] * math.sin(theta)
            add_pad(px, py, z, REST_LEDGE_SIZE,
                    "OC_Rest_%s" % sec["name"])
            prev_half = REST_LEDGE_SIZE * 0.5
            prev_pos = (px, py)

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

            # Edge-to-edge gap we want, converted to a centre-to-centre chord.
            gap = sec["difficulty"] * reach
            chord = gap + prev_half + size * 0.5

            max_chord = 2.0 * radius * 0.999
            if chord > max_chord:
                chord = max_chord
            theta += 2.0 * math.asin(chord / (2.0 * radius))

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

    unreal.log("[tower] built %d platforms, summit at Z=%.0f (%.1f m)"
               % (index, z, (z - base_z) / 100.0))
    if warnings:
        unreal.log_warning("[tower] %d reachability warnings - see above"
                           % warnings)


if __name__ == "__main__":
    build()
