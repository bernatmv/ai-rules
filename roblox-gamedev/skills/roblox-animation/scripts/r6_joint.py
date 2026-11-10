"""R6 joint-space clip maths, pure Python (no bpy): semantic angles -> Motor6D Transform CFrames.

Shared by r6_clip.py (the Blender renderer/verifier) and r6_luau.py (the KeyframeSequence
builder), so the render and the game read ONE conversion and cannot drift apart.

WHY (2026-10-17): a custom-mesh R6 monster rig is (rigid GLB parts,
Motor6Ds built in Studio) with NO .blend, so anim_render.py's FK-bone route does not
exist for it. A KeyframeSequence Pose.CFrame IS the Motor6D Transform:
    world(Part1) = Part0.CFrame * C0 * Transform * C1:Inverse()
so clips are authored straight in that space, from the probed C0/C1.

SEMANTIC ANGLES (degrees), all measured in the PARENT part's rest axes, Roblox frame
(+X character right, +Y up, -Z forward):
  up-pointing joints (RootJoint, Neck - the child sits ABOVE the pivot):
    pitch  + = top tips FORWARD (bow)      lean + = top tips to the character's LEFT
    turn   + = face turns LEFT (about up)
  limb joints (Shoulders, Hips - the child hangs BELOW the pivot):
    swing  + = limb swings FORWARD          spread + = limb swings OUTWARD (away from body)
    twist  + = about the up axis (limb front face turns left)
  pos = [dx, dy, dz] studs, parent-frame offset of the child (RootJoint bob).
World rotation W = Ry(turn|twist) * Rz(lean|+-spread) * Rx(-pitch|+swing); the Transform is
T = R0^T W R0 with R0 the C0 rotation, so W is a rotation about the joint point in the
parent's axes regardless of how C0 happens to be oriented. Which side a limb is on is read
from C0's position (x > 0 = right), never from a mirror rule.

Note what a torso pitch does to its children: pitching the torso forward swings hanging
arms and legs BACKWARD (their bottoms move back); compensate in the child joints.
"""
import math

UP_JOINTS = {"RootJoint", "Neck"}


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def world_rot(joint_name, side_sign, sem):
    """Semantic dict -> W (3x3), rotation in the parent's rest axes."""
    d = math.radians
    if joint_name in UP_JOINTS:
        a = d(-sem.get("pitch", 0.0))
        b = d(sem.get("lean", 0.0))
        c = d(sem.get("turn", 0.0))
    else:
        a = d(sem.get("swing", 0.0))
        b = d(sem.get("spread", 0.0)) * side_sign
        c = d(sem.get("twist", 0.0))
    return mm(ry(c), mm(rz(b), rx(a)))


def transform(joint, sem):
    """joint = {"name", "c0": {"pos", "rows"}} ; returns (pos[3], rows[3][3]) of the Pose CFrame."""
    R0 = joint["c0"]["rows"]
    side = 1.0 if joint["c0"]["pos"][0] >= 0 else -1.0
    W = world_rot(joint["name"], side, sem)
    T = mm(tr(R0), mm(W, R0))
    p = sem.get("pos", [0.0, 0.0, 0.0])
    tp = mv(tr(R0), p)
    return tp, T


def check_semantics(joint_name, sem):
    allowed = {"pitch", "lean", "turn", "pos"} if joint_name in UP_JOINTS else {"swing", "spread", "twist", "pos"}
    bad = set(sem) - allowed
    if bad:
        raise SystemExit(f"{joint_name}: unknown semantic keys {sorted(bad)}; allowed {sorted(allowed)}")


def ease(name, u):
    if name == "linear":
        return u
    if name == "constant":
        return 0.0
    if name == "in":      # accelerate INTO the next key (Roblox PoseEasingDirection.Out - reversed enum)
        return u ** 3
    if name == "out":     # decelerate into the next key (Roblox PoseEasingDirection.In)
        return 1 - (1 - u) ** 3
    if name == "smooth":
        return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    raise SystemExit(f"unknown ease {name!r}")


# spec ease -> (Enum.PoseEasingStyle, Enum.PoseEasingDirection). Direction In/Out are BACKWARDS
# in Roblox's Pose enum (docs: "for legacy compatibility reasons"), see traps.md #36.
ROBLOX_EASE = {"linear": ("Linear", "In"), "constant": ("Constant", "In"),
               "in": ("Cubic", "Out"), "out": ("Cubic", "In"), "smooth": ("Cubic", "InOut")}
