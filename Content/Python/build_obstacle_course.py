"""
build_obstacle_course.py

Procedurally builds a parkour / obstacle course in the currently open level
using engine BasicShapes (scaled cubes). It creates:

  - a start pad
  - a run of jump gaps that get progressively wider
  - a ramp up to a raised tier, then a drop-gap back down
  - three laterally offset stepping stones (forces side-to-side weaving)
  - a narrow beam over the void
  - a ramp down to a large finish pad

KillZ is lowered just under the course, so falling off = respawn.

--------------------------------------------------------------------------
HOW TO RUN (inside the Unreal Editor, with Level_01 open)

  Tools > Execute Python Script...    -> pick this file
      or, in the Output Log console:
  py "D:/GAMEDEV/RUNandJUMP/Content/Python/build_obstacle_course.py"

Re-running is safe: every generated actor is labelled with the prefix
"OC_" and put in the "ObstacleCourse" outliner folder, and the script
deletes those first. Tweak CONFIG below and run again to iterate.
Press Ctrl+S afterwards to save the level.
--------------------------------------------------------------------------
"""

import math
import unreal

# ============================================================ CONFIG =====
# Top surface of the start pad, in world units. Move this if the course
# overlaps existing level geometry.
COURSE_ORIGIN = unreal.Vector(0.0, 0.0, 300.0)

WALK_WIDTH   = 400.0   # normal walkable platform width (Y)
BEAM_WIDTH   = 130.0   # narrow beam width
STONE_SIZE   = 220.0   # stepping-stone footprint
PLATE_THICK  = 40.0    # platform slab thickness
RAMP_THICK   = 30.0    # ramp slab thickness

# Jump gaps, front to back. BP_BOT with UE defaults clears roughly 450-550
# uu at run speed; the last gaps are meant to be scary. Re-tune to taste.
JUMP_GAPS    = [320.0, 360.0, 400.0, 460.0, 520.0]

MOVE_PLAYER_START = True    # snap the first PlayerStart onto the start pad
SET_KILL_Z        = True    # destroy anything that falls below the course

LABEL_PREFIX      = "OC_"
OUTLINER_FOLDER   = "ObstacleCourse"
# ========================================================================

_CUBE = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
_GRID_MAT = unreal.load_asset("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial")
_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _spawn_box(center, scale, pitch=0.0, label="OC_box"):
    """Spawn one scaled cube. `scale` is an unreal.Vector (cube base = 100^3)."""
    actor = _actors.spawn_actor_from_class(unreal.StaticMeshActor, center)
    smc = actor.static_mesh_component
    smc.set_mobility(unreal.ComponentMobility.MOVABLE)
    smc.set_static_mesh(_CUBE)
    if _GRID_MAT:
        smc.set_material(0, _GRID_MAT)
    if abs(pitch) > 1e-4:
        rot = unreal.Rotator()
        rot.pitch = pitch
        actor.set_actor_rotation(rot, False)
    actor.set_actor_scale3d(scale)
    smc.set_mobility(unreal.ComponentMobility.STATIC)
    actor.set_actor_label(label)
    actor.set_folder_path(OUTLINER_FOLDER)
    return actor


def add_platform(x0, x1, top_z, width=WALK_WIDTH, thickness=PLATE_THICK,
                 y=0.0, label="OC_Platform"):
    """Axis-aligned slab; its top surface sits at `top_z`, spanning x0..x1."""
    length = x1 - x0
    center = unreal.Vector((x0 + x1) * 0.5, y, top_z - thickness * 0.5)
    scale = unreal.Vector(length / 100.0, width / 100.0, thickness / 100.0)
    return _spawn_box(center, scale, label=label)


def add_ramp(x0, z0, x1, z1, width=WALK_WIDTH, thickness=RAMP_THICK,
             y=0.0, label="OC_Ramp"):
    """Sloped slab connecting top-surface point (x0,z0) to (x1,z1)."""
    run = x1 - x0
    rise = z1 - z0
    slope_len = math.hypot(run, rise)
    pitch = -math.degrees(math.atan2(rise, run))   # +X end goes up for rise>0
    center = unreal.Vector((x0 + x1) * 0.5, y, (z0 + z1) * 0.5 - thickness * 0.5)
    scale = unreal.Vector(slope_len / 100.0, width / 100.0, thickness / 100.0)
    return _spawn_box(center, scale, pitch=pitch, label=label)


def clear_course():
    removed = 0
    for a in _actors.get_all_level_actors():
        if a.get_actor_label().startswith(LABEL_PREFIX):
            _actors.destroy_actor(a)
            removed += 1
    if removed:
        unreal.log("[course] removed %d existing actors" % removed)


def move_player_start(location):
    for a in _actors.get_all_level_actors():
        if isinstance(a, unreal.PlayerStart):
            a.set_actor_location(location, False, True)
            unreal.log("[course] PlayerStart moved to %s" % location)
            return
    unreal.log_warning("[course] no PlayerStart found - drag one onto OC_Start")


def set_kill_z(z):
    for a in _actors.get_all_level_actors():
        if isinstance(a, unreal.WorldSettings):
            a.set_editor_property("kill_z", z)
            unreal.log("[course] KillZ = %.0f" % z)
            return
    unreal.log_warning("[course] WorldSettings not found - KillZ unchanged")


def build():
    clear_course()

    x = COURSE_ORIGIN.x
    z = COURSE_ORIGIN.z
    y = COURSE_ORIGIN.y

    # 1) start pad
    add_platform(x, x + 600.0, z, width=600.0, label="OC_Start")
    x += 600.0

    # 2) progressively wider jump gaps
    for i, gap in enumerate(JUMP_GAPS):
        x += gap
        add_platform(x, x + 400.0, z, label="OC_Jump_%02d" % (i + 1))
        x += 400.0

    # 3) ramp up to a raised tier
    add_ramp(x, z, x + 520.0, z + 260.0, label="OC_RampUp")
    x += 520.0
    z += 260.0
    add_platform(x, x + 500.0, z, label="OC_HighPad")
    x += 500.0

    # 4) drop-gap: jump the gap AND lose height
    x += 460.0
    z -= 160.0
    add_platform(x, x + 460.0, z, label="OC_DropPad")
    x += 460.0

    # 5) three offset stepping stones - weave left/right
    for i, side in enumerate((1.0, -1.0, 1.0)):
        x += 360.0
        add_platform(x, x + STONE_SIZE, z, width=STONE_SIZE,
                     y=y + side * 170.0, label="OC_Stone_%02d" % (i + 1))
    x += STONE_SIZE

    # 6) re-align onto the centre line
    x += 360.0
    add_platform(x, x + 380.0, z, label="OC_Realign")
    x += 380.0

    # 7) narrow beam over the void
    x += 300.0
    add_platform(x, x + 950.0, z, width=BEAM_WIDTH, label="OC_Beam")
    x += 950.0

    # 8) ramp down to the finish
    add_ramp(x, z, x + 560.0, z - 320.0, label="OC_RampDown")
    x += 560.0
    z -= 320.0
    add_platform(x, x + 900.0, z, width=800.0, label="OC_Finish")

    if SET_KILL_Z:
        set_kill_z(COURSE_ORIGIN.z - 1500.0)
    if MOVE_PLAYER_START:
        move_player_start(unreal.Vector(COURSE_ORIGIN.x + 220.0, y,
                                        COURSE_ORIGIN.z + 130.0))

    unreal.log("[course] done - finish pad at X=%.0f Z=%.0f" % (x, z))


if __name__ == "__main__":
    build()
