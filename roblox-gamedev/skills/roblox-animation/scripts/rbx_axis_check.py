"""Does the Roblox KeyframeSequence pose the part the way Blender rendered it?

  blender --background <rig>.blend --enable-autoexec --python rbx_axis_check.py -- spec.json [spec2.json ...]

THE DEFECT THIS EXISTS FOR (found 2026-10-08):
to_roblox.py converted every FK bone with one rule, rx=-bx ry=by rz=bz. Probing
the community R15 rig showed that rule is only right for X and Z on the LIMBS:

  * limb bones point DOWN, so their local frame is the Roblox frame turned 180
    degrees about Z. That makes ry = -by, not +by: Blender FK_UpperArm.R Y=+90
    swings the elbow BACKWARD, Roblox Ry(+90) on RightShoulder swings it FORWARD.
    Any arm roll (cocked throw, hand on hip) came out mirrored in game.
  * torso/head bones point UP and share Roblox's frame, so their map is the
    identity. UpTorso X=+20 leans the head BACK in Blender (measured, head tip
    y -0.89); Roblox Rx(+) on the Waist also leans back - but the old rule sent
    -20, so every authored lean played the OTHER way in game.

The contact sheet cannot see this: it only proves the render matches the spec.
Studio was the only place it would show, and only if someone compared.

WHAT IT DOES: for every authored beat it poses the Blender rig exactly as the
spec says, reads each deform part's world rotation (delta from rest), and
compares it with the rotation Roblox will compute from to_roblox.convert()'s
numbers - composed down the Motor6D chain as Pose CFrames
(CFrame.Angles(0,0,rz)*CFrame.Angles(0,ry,0)*CFrame.Angles(rx,0,0)), assuming
R15 rig attachments are axis-aligned (true for the stock R15 rig). Full
rotation, so ROLL is checked as well as direction. Prints the worst error per
part and exits non-zero if any part is off by more than --tol degrees (2.0).

--mid adds the segment-midpoint comparison (Euler lerp vs CFrame slerp), which
is a REPORT, not a gate: it says where the in-game path will leave the render's.

It must be able to FAIL: run it with --legacy to use the old rule and it should
report the torso/limb-roll errors. A checker that cannot fail proves nothing.
"""
import bpy, sys, os, json, math, argparse
from mathutils import Euler, Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("specs", nargs="+")
# 2.0, not 0: the community R15 rig's FK limb bones are built slightly off-axis (measured
# from the bone matrices: upper arms 0.74 deg, lower arms 0.49 deg, upper legs
# 0.68 deg), so a perfect conversion still leaves ~1.4 deg at 150 deg of swing.
# The defect this hunts is 12-170 deg. Do not raise this to pass a spec.
ap.add_argument("--tol", type=float, default=2.0, help="max allowed rotation error, degrees")
ap.add_argument("--mid", action="store_true",
                help="also compare the MIDPOINT of every segment: Blender lerps Euler angles, "
                     "Roblox slerps CFrames, so a big multi-axis move can take a different PATH "
                     "in game than in the render even when every key matches")
ap.add_argument("--legacy", action="store_true", help="use the pre-2026-10-08 axis rule (should FAIL)")
args = ap.parse_args(argv)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import to_roblox  # noqa: E402

TREE = dict(to_roblox.TREE)  # child -> parent
R15 = set(TREE) | {"HumanoidRootPart"}


def die(msg):
    print(f"\n!!! FAILED: {msg}", flush=True)
    os._exit(1)


arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"
            and len({b.name for b in o.data.bones} & R15) >= 12), None)
if arm is None:
    die("no R15 armature")
M = arm.matrix_world
sc = bpy.context.scene
act = arm.animation_data.action if arm.animation_data else None
if act is None:
    die("rig has no action to key into (see traps #1)")

# world -> Roblox: world +X right, +Y forward, +Z up  ->  Roblox +X right, +Y up, -Z forward
P = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))


def world_rot(b):
    return (M @ arm.pose.bones[b].matrix).to_3x3().normalized()


def cf(r):
    rx, ry, rz = (math.radians(v) for v in r)
    return Matrix.Rotation(rz, 3, "Z") @ Matrix.Rotation(ry, 3, "Y") @ Matrix.Rotation(rx, 3, "X")


sc.frame_set(0)
bpy.context.view_layer.update()
REST = {b: world_rot(b) for b in TREE}
frame = 2000
worst_all = 0.0
for path in args.specs:
    spec = json.load(open(path))
    conv = to_roblox.convert(path, legacy=args.legacy)
    props = spec.get("properties", {})
    pbp = next((pb for pb in arm.pose.bones if props and all(k in pb.keys() for k in props)), None)
    bones = sorted({b for k in spec["keyframes"] for b in k["bones"]})
    worst = {}
    def pose_compare(bl_rot, rb_rot, locs):
        """bl_rot: {bone: euler deg}; rb_rot: {joint: 3x3 local rotation}. Returns {part: err}."""
        global frame
        frame += 5
        sc.frame_set(frame)
        for p, v in props.items():
            pbp[p] = v
            pbp.keyframe_insert(f'["{p}"]', frame=frame)
        for b in bones:
            pb = arm.pose.bones[b]
            if pb.rotation_mode == "QUATERNION":
                pb.rotation_mode = "XYZ"
            pb.rotation_euler = Euler([math.radians(v) for v in bl_rot.get(b, (0, 0, 0))], "XYZ")
            pb.keyframe_insert("rotation_euler", frame=frame)
            if b in locs:
                pb.location = Vector(locs[b])
                pb.keyframe_insert("location", frame=frame)
        sc.frame_set(frame)
        bpy.context.view_layer.update()
        rbx_world = {"HumanoidRootPart": Matrix.Identity(3)}
        for child, parent in to_roblox.TREE:  # parents precede children
            rbx_world[child] = rbx_world[parent] @ rb_rot.get(child, Matrix.Identity(3))
        errs = {}
        for part in TREE:
            d_bl = world_rot(part) @ REST[part].inverted()
            d_bl = P @ d_bl @ P.transposed()
            e = math.degrees((rbx_world[part].transposed() @ d_bl).to_quaternion().angle)
            errs[part] = min(e, 360 - e)
        return errs

    def bl_of(k):
        return {b: d.get("rot", (0, 0, 0)) for b, d in k["bones"].items()}

    def rb_of(ck):
        return {j: cf(v.get("r", (0, 0, 0))) for j, v in ck["poses"].items()}

    def locs_of(k):
        return {b: d["loc"] for b, d in k["bones"].items() if "loc" in d}

    for k, ck in zip(spec["keyframes"], conv["keyframes"]):
        for part, err in pose_compare(bl_of(k), rb_of(ck), locs_of(k)).items():
            if err > worst.get(part, (0, 0))[0]:
                worst[part] = (err, k["t"])
    if args.mid:
        mids = []
        K, C = spec["keyframes"], conv["keyframes"]
        for a, b, ca, cb in zip(K, K[1:], C, C[1:]):
            ba, bb = bl_of(a), bl_of(b)
            bl_mid = {n: [(x + y) / 2 for x, y in zip(ba.get(n, (0, 0, 0)), bb.get(n, (0, 0, 0)))]
                      for n in set(ba) | set(bb)}
            ra, rbb = rb_of(ca), rb_of(cb)
            rb_mid = {}
            for j in set(ra) | set(rbb):
                qa = ra.get(j, Matrix.Identity(3)).to_quaternion()
                qb = rbb.get(j, Matrix.Identity(3)).to_quaternion()
                rb_mid[j] = qa.slerp(qb, 0.5).to_matrix()
                # (mathutils slerp takes the short arc, as CFrame:Lerp does)
            la, lb = locs_of(a), locs_of(b)
            lm = {n: [(x + y) / 2 for x, y in zip(la[n], lb[n])] for n in la if n in lb}
            errs = pose_compare(bl_mid, rb_mid, lm)
            part = max(errs, key=errs.get)
            mids.append((errs[part], part, a["t"], b["t"]))
            if errs[part] > 10:
                # The cure is a beat AT the midpoint holding the pose Roblox will
                # actually pass through, so the render shows the in-game path.
                # Roblox local rotation -> Blender Euler: limbs conjugate by
                # C = diag(-1,-1,1) (180 deg about Z), body bones are the identity.
                Cm = Matrix(((-1, 0, 0), (0, -1, 0), (0, 0, 1)))
                inv = {v: k for k, v in to_roblox.JOINT.items()}
                sug = {}
                for j, R in sorted(rb_mid.items()):
                    bn = inv.get(j)
                    if bn is None:
                        continue
                    Rb = R if bn in to_roblox.BODY else Cm @ R @ Cm
                    sug[bn] = [round(math.degrees(v), 1) for v in Rb.to_euler("XYZ")]
                print(f"    suggest beat at t={(a['t'] + b['t']) / 2:.4f}: {json.dumps(sug)}")
        for e, part, ta, tb in mids:
            flag = "  <-- in-game path differs from the render" if e > 10 else ""
            print(f"    mid {ta:.4f}->{tb:.4f}: worst {part} {e:.1f} deg{flag}")
    bad = {p: v for p, v in worst.items() if v[0] > args.tol}
    print(f"=== {os.path.basename(path)} ({conv['name']}): worst part error "
          f"{max([v[0] for v in worst.values()] or [0]):.2f} deg")
    # Every part, not only the failures: a PASS that prints nothing per part
    # cannot show how close each joint came to the tolerance.
    for p, (e, t) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        print(f"    {p:15s} {e:7.2f} deg at t={t}" + ("  <-- FAIL" if p in bad else ""))
    worst_all = max([worst_all] + [v[0] for v in worst.values()])
print(f"=== RESULT: worst {worst_all:.2f} deg (tol {args.tol}) - "
      + ("PASS" if worst_all <= args.tol else "FAIL"), flush=True)
os._exit(0 if worst_all <= args.tol else 1)
