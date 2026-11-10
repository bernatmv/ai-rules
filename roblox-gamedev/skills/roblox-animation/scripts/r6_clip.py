"""R6 joint-space clip -> posed render of the rig's real mesh parts + numeric checks. No .blend needed.

  blender --background --python-exit-code 1 --python r6_clip.py -- --rig rig.json --glb-dir parts/ --clip clip.json \
      --outdir out/Clip [--hide PartGlbName] [--size 360] [--no-render]

WHY (2026-10-17): a custom-mesh R6 monster rig is (rigid GLB parts welded by
Motor6Ds in Studio) with no .blend, so anim_render.py has nothing to key. A KeyframeSequence
Pose.CFrame IS the Motor6D Transform (world(P1) = P0 * C0 * T * C1:Inverse()), so the clip is
authored in that space (semantic angles, see r6_joint.py) and VERIFIED here by applying exactly
that chain to the shipped meshes. Render and Luau read one conversion (r6_joint.transform).

rig.json: {"hrp": [x,y,z],
           "parts": {"Torso": {"glb": "MonsterTorso"}, ...},           # glb = file stem in --glb-dir
           "joints": [{"name": "RootJoint", "part0": "HumanoidRootPart", "part1": "Torso",
                       "c0": {"pos": [..], "rows": [[..],[..],[..]]}, "c1": {...}}, ...],
           "feet": ["Right Leg", "Left Leg"], "arms": ["Right Arm", "Left Arm"],
           "arm_check_below_y": 4.4}                                    # rest-y below which arm verts are "hands"
  Frame: Roblox studs, +Y up, -Z forward, +X right, feet at y=0. Every part rests UNROTATED at its
  mesh bbox centre (a MeshPart centres on its bbox); the script asserts the C0/C1 chain reproduces it.

clip.json: {"name", "fps": 30, "duration", "loop", "priority", "markers": [[name, t], ...],
            "auto_ground": false,
            "keyframes": [{"t", "ease", "ground": bool, "joints": {"RootJoint": {"pitch":..,"pos":[..]},
                                                                  "Right Shoulder": {"swing":..}, ...}}]}
  "ground": true on a key solves RootJoint pos.y so the lowest foot vertex sits at y=0 on that key.

Writes: frames side_###.png / tq_###.png, report.json (per-frame lowest foot y, per-leg lowest y and
contact-point slide speed, hand-vs-leg/torso triangle overlaps vs the rest baseline) and
resolved.json (Pose CFrames per key, consumed by r6_luau.py). Exits non-zero on any failed assertion.
Pass --python-exit-code 1: without it a Python exception in here still exits Blender with 0.
"""
import bpy, sys, os, json, math, glob, argparse
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r6_joint as RJ  # noqa: E402
import functools
# os._exit() below skips the stdout flush, which silently ate every report line once
print = functools.partial(print, flush=True)  # noqa: A001

A = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--rig", required=True)
ap.add_argument("--glb-dir", required=True)
ap.add_argument("--clip", required=True)
ap.add_argument("--outdir", required=True)
ap.add_argument("--hide", default="")
ap.add_argument("--size", type=int, default=360)
ap.add_argument("--no-render", action="store_true")
a = ap.parse_args(A)
outdir = os.path.abspath(a.outdir)
os.makedirs(outdir, exist_ok=True)


def die(msg):
    print(f"\n!!! FAILED: {msg}", flush=True)
    os._exit(1)


rig = json.load(open(a.rig))
clip = json.load(open(a.clip))
FPS = clip.get("fps", 30)
DUR = clip["duration"]
LOOP = bool(clip.get("loop"))
KEYS = clip["keyframes"]
JOINTS = {j["name"]: j for j in rig["joints"]}
BY_CHILD = {j["part1"]: j for j in rig["joints"]}


def cf(d):
    m = Matrix([list(r) for r in d["rows"]]).to_4x4()
    m.translation = Vector(d["pos"])
    return m


# ---- rest CFrames from the chain, asserted against the mesh bboxes ----
REST = {"HumanoidRootPart": Matrix.Translation(Vector(rig["hrp"]))}
order = []
pending = list(rig["joints"])
while pending:
    for j in list(pending):
        if j["part0"] in REST:
            REST[j["part1"]] = REST[j["part0"]] @ cf(j["c0"]) @ cf(j["c1"]).inverted()
            order.append(j)
            pending.remove(j)
            break
    else:
        die("joint chain does not connect to HumanoidRootPart")

# ---- import meshes; Blender = Q * Roblox, Q:(X,Y,Z)->(-X,Z,Y) (glTF +Z-front file, Roblox front -Z) ----
bpy.ops.wm.read_factory_settings(use_empty=True)
Q = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).to_4x4()
QI = Q.inverted()
hidden = {h for h in a.hide.split(",") if h}
OBJ, VERTS, POLYS = {}, {}, {}
for pname, pd in rig["parts"].items():
    f = os.path.join(a.glb_dir, pd["glb"] + ".glb")
    if not os.path.exists(f):
        die(f"missing {f}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if len(meshes) != 1:
        die(f"{f}: expected one mesh, got {len(meshes)}")
    o = meshes[0]
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    o.parent = None
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for x in new:
        if x is not o:
            bpy.data.objects.remove(x, do_unlink=True)
    o.name = pname
    vb = np.array([tuple(v.co) for v in o.data.vertices])
    vr = vb @ np.array(QI.to_3x3()).T          # rest verts in Roblox frame
    VERTS[pname] = vr
    POLYS[pname] = [tuple(p.vertices) for p in o.data.polygons]
    c = (vr.min(0) + vr.max(0)) / 2
    err = (Vector(c) - REST[pname].translation).length
    print(f"=== {pname:10s} bbox centre {np.round(c, 3)}  chain rest {np.round(np.array(REST[pname].translation), 3)}  err {err:.4f}")
    if err > 0.03:
        die(f"{pname}: the C0/C1 chain puts the part {err:.3f} studs from its mesh bbox centre - wrong C0/C1 or frame")
    OBJ[pname] = o
for h in hidden:
    if h in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[h], do_unlink=True)


# ---- keyframes -> joint Transforms ----
keyed = set(KEYS[0]["joints"])
for k in KEYS:
    for jn, sem in k["joints"].items():
        if jn not in JOINTS:
            die(f"unknown joint {jn!r}")
        RJ.check_semantics(jn, sem)
    late = set(k["joints"]) - keyed
    if late:
        die(f"joints {sorted(late)} keyed at t={k['t']} but not in the first key")
if abs(KEYS[-1]["t"] - DUR) > 1e-6:
    die(f"last key t={KEYS[-1]['t']} != duration {DUR}")
if LOOP and json.dumps(KEYS[0]["joints"], sort_keys=True) != json.dumps(KEYS[-1]["joints"], sort_keys=True):
    die("loop clip: first and last keys differ - it would snap on every wrap")


def key_transforms(k):
    out = {}
    for jn in keyed:
        sem = k["joints"].get(jn, {})
        p, R = RJ.transform(JOINTS[jn], sem)
        m = Matrix(R).to_4x4()
        m.translation = Vector(p)
        out[jn] = m
    return out


def pose_world(T):
    W = {"HumanoidRootPart": REST["HumanoidRootPart"]}
    for j in order:
        t = T.get(j["name"], Matrix.Identity(4))
        W[j["part1"]] = W[j["part0"]] @ cf(j["c0"]) @ t @ cf(j["c1"]).inverted()
    return W


def posed_verts(W, p):
    M = W[p] @ REST[p].inverted()
    R = np.array(M.to_3x3())
    return VERTS[p] @ R.T + np.array(M.translation)


FEET = rig.get("feet", [])

# ground solve per key (RootJoint pos.y): lowest foot vertex -> y = 0
for k in KEYS:
    if k.get("ground") or (clip.get("auto_ground") and k.get("ground") is not False):
        rj = k["joints"].setdefault("RootJoint", {})
        pos = list(rj.get("pos", [0, 0, 0]))
        pos[1] = 0.0
        rj["pos"] = pos
        W = pose_world(key_transforms(k))
        low = min(posed_verts(W, f)[:, 1].min() for f in FEET)
        pos[1] = round(-low, 4)
        rj["pos"] = pos
KT = [key_transforms(k) for k in KEYS]


def sample(t):
    if t <= KEYS[0]["t"]:
        return KT[0]
    for i in range(len(KEYS) - 1):
        a0, a1 = KEYS[i]["t"], KEYS[i + 1]["t"]
        if a0 <= t <= a1:
            u = RJ.ease(KEYS[i].get("ease", "smooth"), (t - a0) / (a1 - a0) if a1 > a0 else 1.0)
            out = {}
            for jn in keyed:
                m0, m1 = KT[i][jn], KT[i + 1][jn]
                q = m0.to_quaternion().slerp(m1.to_quaternion(), u)   # Roblox slerps the CFrame
                m = q.to_matrix().to_4x4()
                m.translation = m0.translation.lerp(m1.translation, u)
                out[jn] = m
            return out
    return KT[-1]


n = int(round(DUR * FPS)) + (0 if LOOP else 1)
times = [i / FPS for i in range(n)]

# ---- checks ----
ARMS = rig.get("arms", [])
cut = rig.get("arm_check_below_y", 4.4)


def subset_polys(p, mask):
    return [pl for pl in POLYS[p] if all(mask[v] for v in pl)]


ARM_POLYS = {p: subset_polys(p, VERTS[p][:, 1] < cut) for p in ARMS}
TORSO_NAME = "Torso"


def overlaps(W):
    vs = {p: posed_verts(W, p) for p in ARMS + FEET + [TORSO_NAME]}
    trees = {p: BVHTree.FromPolygons([tuple(v) for v in vs[p]], POLYS[p] if p not in ARMS else ARM_POLYS[p])
             for p in vs}
    res = {}
    for arm_p in ARMS:
        for other in FEET + [TORSO_NAME]:
            res[f"{arm_p}~{other}"] = len(trees[arm_p].overlap(trees[other]))
    return res


base = overlaps(pose_world({}))
print(f"=== rest-pose hand/claw overlaps (baseline): {base}")
frames = []
LEGV = {f: [] for f in FEET}
for i, t in enumerate(times):
    W = pose_world(sample(t))
    rec = {"f": i, "t": round(t, 4), "legs": {}}
    for f in FEET:
        v = posed_verts(W, f)
        LEGV[f].append(v)
        lo = v[:, 1].min()
        sel = v[v[:, 1] < lo + 0.03]
        rec["legs"][f] = {"low_y": round(float(lo), 4), "contact_xz": [round(float(sel[:, 0].mean()), 4),
                                                                        round(float(sel[:, 2].mean()), 4)]}
    rec["lowest_foot_y"] = min(r["low_y"] for r in rec["legs"].values())
    rec["hands"] = {}
    for ap_ in ARMS:
        v = posed_verts(W, ap_)
        rv = VERTS[ap_][:, 1]
        tip = v[rv < rv.min() + 0.6]            # the claws: rest-lowest 0.6 studs of the arm
        rec["hands"][ap_] = {"claw_centre": [round(float(x), 3) for x in tip.mean(0)],
                             "low_y": round(float(v[:, 1].min()), 3)}
    ov = overlaps(W)
    rec["hand_overlaps"] = {k: v for k, v in ov.items() if v > base.get(k, 0)}
    frames.append(rec)

# STANCE SLIP, measured on the MATERIAL point in contact (the lowest vertex at frame i, followed
# to frame i+1). The lowest-point LOCATION is useless here: a rigid foot rolls heel -> toe, so the
# contact location jumps along the sole while nothing slips. For no skating that vertex must move
# backward (+Z) at the character's ground speed. Frames wrap for a loop.
slides = []
nf = len(times)
for f in FEET:
    for i in range(nf - (0 if LOOP else 1)):
        j = (i + 1) % nf
        v0, v1 = LEGV[f][i], LEGV[f][j]
        k = int(np.argmin(v0[:, 1]))
        if v0[k, 1] < 0.06 and v1[k, 1] < 0.06:
            slides.append(float((v1[k, 2] - v0[k, 2]) * FPS))
slide = {"samples": len(slides), "mean_backward_speed": round(float(np.mean(slides)), 3) if slides else None,
         "median": round(float(np.median(slides)), 3) if slides else None,
         "min": round(float(np.min(slides)), 3) if slides else None,
         "max": round(float(np.max(slides)), 3) if slides else None}
worst_ov = max((sum(fr["hand_overlaps"].values()) for fr in frames), default=0)
report = {"clip": clip["name"], "frames": len(frames), "baseline_overlaps": base,
          "lowest_foot_y_min": min(fr["lowest_foot_y"] for fr in frames),
          "lowest_foot_y_max": max(fr["lowest_foot_y"] for fr in frames),
          "stance_slide": slide,
          "lowest_hand_y": min(h["low_y"] for fr in frames for h in fr["hands"].values()), "worst_extra_hand_overlap_tris": worst_ov,
          "frames_with_hand_overlap": [fr["f"] for fr in frames if fr["hand_overlaps"]],
          "per_frame": frames}
json.dump(report, open(os.path.join(outdir, "report.json"), "w"), indent=1)
print(f"=== lowest foot y over the clip: {report['lowest_foot_y_min']:.3f} .. {report['lowest_foot_y_max']:.3f}")
print(f"=== stance contact slide (studs/s, +=backward): {slide}")
print(f"=== frames with NEW hand/claw overlaps: {report['frames_with_hand_overlap']} (worst {worst_ov} tri pairs)")

# resolved keys for the Luau builder
res = {"name": clip["name"], "priority": clip.get("priority", "Action"), "loop": LOOP, "duration": DUR,
       "markers": clip.get("markers", []), "keyed": sorted(keyed),
       "keys": [{"t": k["t"], "ease": k.get("ease", "smooth"),
                 "poses": {jn: {"pos": [round(x, 5) for x in KT[i][jn].translation],
                                "rows": [[round(KT[i][jn][r][c], 6) for c in range(3)] for r in range(3)]}
                           for jn in sorted(keyed)}} for i, k in enumerate(KEYS)]}
json.dump(res, open(os.path.join(outdir, "resolved.json"), "w"), indent=1)

if a.no_render:
    print("=== no render requested")
    os._exit(0)

# ---- render: plain clay, floor at y=0, orthographic, framed on the whole clip ----
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT"
sc.render.resolution_x = sc.render.resolution_y = a.size
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.45, 0.5, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6


def mat(name, col):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = 0.7
    return m


COL = {"Torso": (0.16, 0.16, 0.18), "Head": (0.75, 0.62, 0.42)}
for p, o in OBJ.items():
    if o.name not in bpy.data.objects:
        continue
    o.data.materials.clear()
    o.data.materials.append(mat(p + "_m", COL.get(p, (0.72, 0.74, 0.70))))
bpy.ops.mesh.primitive_plane_add(size=60)
fl = bpy.context.active_object
fl.data.materials.append(mat("floor", (0.25, 0.27, 0.25)))
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
sc.collection.objects.link(sun)

poses = [pose_world(sample(t)) for t in times]
pts = []
for W in poses:
    for p in OBJ:
        if OBJ[p].name in bpy.data.objects:
            v = posed_verts(W, p)
            pts += [v.min(0), v.max(0)]
pts = np.array(pts)
lo, hi = pts.min(0), pts.max(0)
lo[1] = min(lo[1], 0.0)
ctr = (lo + hi) / 2
ext = float((hi - lo).max()) * 1.12
# view dirs in Roblox frame (from target to camera): side = character's right, tq = front-right
VIEWS = {"side": (1.0, 0.0, 0.0), "tq": (0.75, 0.25, -0.75)}
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = ext
for vn, d in VIEWS.items():
    dv = Vector(d).normalized()
    c_r = Vector(ctr.tolist())
    pos_r = c_r + dv * 40
    cam.location = Q.to_3x3() @ pos_r
    cam.rotation_euler = (Q.to_3x3() @ (c_r - pos_r)).to_track_quat("-Z", "Y").to_euler()
    for i, W in enumerate(poses):
        for p, o in OBJ.items():
            if o.name in bpy.data.objects:
                o.matrix_world = Q @ (W[p] @ REST[p].inverted()) @ QI
        sc.render.filepath = os.path.join(outdir, f"{vn}_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
missing = [f for vn in VIEWS for f in (os.path.join(outdir, f"{vn}_{i:03d}.png") for i in range(n)) if not os.path.exists(f)]
if missing:
    die(f"{len(missing)} frames not written, e.g. {missing[0]}")
print(f"=== done: {n} frames x {len(VIEWS)} views -> {outdir}")
os._exit(0)
