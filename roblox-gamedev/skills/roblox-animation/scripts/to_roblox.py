"""FK anim spec -> a ready-to-run Luau script that builds the KeyframeSequences in Studio.

  python to_roblox.py kick.json punch.json > build_sequences.lua
  python to_roblox.py a.json b.json --folder ReplicatedStorage.MyGame.Animations --no-verify > build.luau

Paste the output into `execute_luau`. It creates the target folder (default
ReplicatedStorage.CustomAnims, intermediate folders created as needed) holding
one KeyframeSequence per spec, replacing any child of the same name.

  --no-verify   emit a builder with NO yields: it skips the register-and-load
                check (which waits on AnimationTrack.Length) and instead returns
                a summary string built from the sequences it just made - per
                clip: keyframes, length, markers, joints posed. Use this when the
                caller needs execute_luau to return its output.

SPEC FIELDS READ: rbx_name, priority (default Action), loop, duration,
keyframes[], pose_only (contract: Roblox joint names the clip may pose),
markers {name: seconds} (each must coincide with an authored keyframe time;
emitted as KeyframeMarkers on that Keyframe, for GetMarkerReachedSignal).

AXIS MAP - corrected 2026-10-08 (see rbx_axis_check.py, which proves it):
  Roblox: +X right, +Y up, -Z forward. Pose CFrames are built in Blender's Euler
  order, CFrame.Angles(0,0,rz)*CFrame.Angles(0,ry,0)*CFrame.Angles(rx,0,0).
  LIMB bones (FK_UpperArm/LowerArm/Hand, FK_UpperLeg/LowerLeg/Foot) point DOWN;
  their local frame is Roblox's turned 180 degrees about Z, so
        rx = -bx    ry = -by    rz = bz
  BODY bones (TORSO, UpTorso, HEAD) point UP and share Roblox's frame, so
        rx = bx     ry = by     rz = bz
  The pre-2026-10-08 rule (rx=-bx ry=by rz=bz for everything) mirrored every
  limb ROLL and inverted every torso/head LEAN in game, while the Blender
  renders looked right. `--legacy-axes` reproduces it, for rbx_axis_check only.
  Translation (ROOT loc): Blender world (x, y fwd, z up) -> Roblox (x, z, -y).

EASING - corrected 2026-10-08: Enum.PoseEasingDirection In/Out are BACKWARDS
relative to TweenService and every other tool (Roblox docs, "for legacy
compatibility reasons"): PoseEasingDirection.Out applies the curve forward
(slow start, accelerate) and .In is the reversed curve (decelerate into the next
key). The old map sent the spec's "in" (accelerate into the strike) to .In, so
every strike DECELERATED into its contact frame in game - exactly the mushiness
the per-segment ease exists to prevent. Spec "in" -> Out, "out" -> In now.
"""
import argparse, json, sys, os

JOINT = {
    "TORSO": "LowerTorso", "UpTorso": "UpperTorso", "HEAD": "Head",
    "FK_UpperArm.R": "RightUpperArm", "FK_LowerArm.R": "RightLowerArm", "FK_Hand.R": "RightHand",
    "FK_UpperArm.L": "LeftUpperArm",  "FK_LowerArm.L": "LeftLowerArm",  "FK_Hand.L": "LeftHand",
    "FK_UpperLeg.R": "RightUpperLeg", "FK_LowerLeg.R": "RightLowerLeg", "FK_Foot.R": "RightFoot",
    "FK_UpperLeg.L": "LeftUpperLeg",  "FK_LowerLeg.L": "LeftLowerLeg",  "FK_Foot.L": "LeftFoot",
}
BODY = {"TORSO", "UpTorso", "HEAD"}
TREE = [("LowerTorso", "HumanoidRootPart"), ("UpperTorso", "LowerTorso"), ("Head", "UpperTorso"),
        ("LeftUpperArm", "UpperTorso"), ("LeftLowerArm", "LeftUpperArm"), ("LeftHand", "LeftLowerArm"),
        ("RightUpperArm", "UpperTorso"), ("RightLowerArm", "RightUpperArm"), ("RightHand", "RightLowerArm"),
        ("LeftUpperLeg", "LowerTorso"), ("LeftLowerLeg", "LeftUpperLeg"), ("LeftFoot", "LeftLowerLeg"),
        ("RightUpperLeg", "LowerTorso"), ("RightLowerLeg", "RightUpperLeg"), ("RightFoot", "RightLowerLeg")]
# Enum.PoseEasingStyle is Linear/Constant/Cubic/Elastic/Bounce - there is NO Quad.
# Enum.PoseEasingDirection In/Out are REVERSED vs TweenService (see docstring).
EASE = {"in": ("Cubic", "Out"), "out": ("Cubic", "In"),
        "smooth": ("Cubic", "InOut"), "linear": ("Linear", "In")}
EASE_LEGACY = {"in": ("Cubic", "In"), "out": ("Cubic", "Out"),
               "smooth": ("Cubic", "InOut"), "linear": ("Linear", "In")}


def map_rot(bone, r, legacy=False):
    bx, by, bz = r
    if legacy:
        return [-bx, by, bz]
    if bone in BODY:
        return [bx, by, bz]
    return [-bx, -by, bz]


def convert(path, legacy=False):
    spec = json.load(open(path))
    out = []
    ease = EASE_LEGACY if legacy else EASE
    for k in spec["keyframes"]:
        style, direction = ease[k.get("ease", "smooth")]
        poses = {}
        for bone, data in k["bones"].items():
            j = JOINT.get(bone)
            if j and "rot" in data:
                poses.setdefault(j, {})["r"] = map_rot(bone, data["rot"], legacy)
            if bone == "ROOT" and "loc" in data:
                lx, ly, lz = data["loc"]
                poses.setdefault("LowerTorso", {})["p"] = [lx, lz, -ly]
        out.append({"t": k["t"], "s": style, "d": direction, "poses": poses})
    name = spec.get("rbx_name") or os.path.splitext(os.path.basename(path))[0]
    posed = sorted({j for k in out for j in k["poses"]})
    # `pose_only` (Roblox joint names) is the clip's contract - e.g. an upper-body
    # clip must never pose a leg or the root, or at Action priority it freezes the
    # default walk. Refuse to build a clip that breaks its own contract.
    allowed = spec.get("pose_only")
    if allowed is not None:
        bad = [j for j in posed if j not in allowed]
        if bad:
            raise SystemExit(f"{path}: poses {bad} outside its pose_only contract {allowed}")
    # A marker fires when playback reaches its Keyframe, so it must sit ON one.
    markers = spec.get("markers", {})
    times = [k["t"] for k in out]
    for mname, mt in markers.items():
        if not any(abs(mt - t) < 1e-6 for t in times):
            raise SystemExit(f"{path}: marker {mname!r} at t={mt} is not on an authored keyframe "
                             f"({times}); author a beat at that time")
    last = max(times)
    if abs(last - spec["duration"]) > 1e-6:
        raise SystemExit(f"{path}: last keyframe t={last} != duration {spec['duration']}; Roblox plays "
                         f"a clip for exactly its last keyframe time")
    return {"name": name, "posed": posed, "priority": spec.get("priority", "Action"),
            "loop": bool(spec.get("loop", False)), "duration": spec["duration"], "keyframes": out,
            "markers": markers}


def _n(v):
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


def _kfs(d):
    rows = []
    for k in d["keyframes"]:
        ps = []
        for j, v in sorted(k["poses"].items()):
            bits = []
            if "r" in v:
                bits.append("r={%s}" % ",".join(_n(x) for x in v["r"]))
            if "p" in v:
                bits.append("p={%s}" % ",".join(_n(x) for x in v["p"]))
            ps.append('["%s"]={%s}' % (j, ",".join(bits)))
        ms = [m for m, t in d["markers"].items() if abs(t - k["t"]) < 1e-6]
        mk = ",m={%s}" % ",".join('"%s"' % m for m in sorted(ms)) if ms else ""
        rows.append('{t=%s,s="%s",d="%s",poses={%s}%s}' % (_n(k["t"]), k["s"], k["d"], ",".join(ps), mk))
    return "{" + ",".join(rows) + "}"


HEAD = '''local ReplicatedStorage = game:GetService("ReplicatedStorage")
local KSP = game:GetService("KeyframeSequenceProvider")
local TREE = %s
local PARENT = {}
for _, pair in ipairs(TREE) do PARENT[pair[1]] = pair[2] end
local function build(name, priority, loopAnim, KFS)
\tlocal seq = Instance.new("KeyframeSequence")
\tseq.Name, seq.Priority, seq.Loop = name, Enum.AnimationPriority[priority], loopAnim
\tfor _, k in ipairs(KFS) do
\t\tlocal kf = Instance.new("Keyframe")
\t\tkf.Name, kf.Time = "KF" .. tostring(k.t), k.t
\t\tlocal poses = {}
\t\tlocal root = Instance.new("Pose")
\t\troot.Name, root.CFrame = "HumanoidRootPart", CFrame.new()
\t\tposes.HumanoidRootPart = root
\t\tfor _, pair in ipairs(TREE) do
\t\t\tlocal p = Instance.new("Pose")
\t\t\tp.Name = pair[1]
\t\t\tif not k.poses[pair[1]] then p.Weight = 0 end
\t\t\tlocal d, cf = k.poses[pair[1]], CFrame.new()
\t\t\tif d then
\t\t\t\tif d.r then
\t\t\t\t\tcf = CFrame.Angles(0,0,math.rad(d.r[3])) * CFrame.Angles(0,math.rad(d.r[2]),0) * CFrame.Angles(math.rad(d.r[1]),0,0)
\t\t\t\tend
\t\t\t\tif d.p then
\t\t\t\t\tcf = CFrame.new(d.p[1], d.p[2], d.p[3]) * cf
\t\t\t\tend
\t\t\tend
\t\t\tp.CFrame = cf
\t\t\tp.EasingStyle = Enum.PoseEasingStyle[k.s]
\t\t\tp.EasingDirection = Enum.PoseEasingDirection[k.d]
\t\t\tposes[pair[1]] = p
\t\tend
\t\t-- A joint the clip never keys gets NO Pose. The old builder wrote the full
\t\t-- tree at identity, so an upper-body clip at Action priority pinned both legs
\t\t-- straight and froze the default walk. Keep only keyed joints plus the
\t\t-- ancestors that hold them (those as Weight-0 containers).
\t\tlocal keep = {}
\t\tfor _, pair in ipairs(TREE) do
\t\t\tif k.poses[pair[1]] then
\t\t\t\tlocal j = pair[1]
\t\t\t\twhile j and j ~= "HumanoidRootPart" do keep[j] = true j = PARENT[j] end
\t\t\tend
\t\tend
\t\tfor _, pair in ipairs(TREE) do
\t\t\tif keep[pair[1]] then poses[pair[1]].Parent = poses[pair[2]] else poses[pair[1]]:Destroy() end
\t\tend
\t\troot.Parent = kf
\t\tif k.m then
\t\t\tfor _, mname in ipairs(k.m) do
\t\t\t\tlocal mk = Instance.new("KeyframeMarker")
\t\t\t\tmk.Name, mk.Value = mname, ""
\t\t\t\tkf:AddMarker(mk)
\t\t\tend
\t\tend
\t\tkf.Parent = seq
\tend
\treturn seq
end
local folder = ReplicatedStorage
for _, seg in ipairs(%s) do
\tlocal nxt = folder:FindFirstChild(seg)
\tif not nxt then
\t\tnxt = Instance.new("Folder")
\t\tnxt.Name = seg
\t\tnxt.Parent = folder
\tend
\tfolder = nxt
end
local report = {}
local built = {}
'''

TAIL_VERIFY = '''
-- VERIFY: each sequence must load at its authored duration. Length reads 0 until
-- the asset loads, so wait before believing it.
local rig
for _, m in ipairs(workspace:GetDescendants()) do
\tif m:IsA("Humanoid") and m:FindFirstChildOfClass("Animator") then rig = m break end
end
if rig then
\tfor _, seq in ipairs(built) do
\t\tlocal a = Instance.new("Animation")
\t\ta.AnimationId = KSP:RegisterKeyframeSequence(seq)   -- BARE id; hash:// and rbxasset:// both fail
\t\tlocal t = rig:FindFirstChildOfClass("Animator"):LoadAnimation(a)
\t\tlocal w = 0
\t\twhile t.Length == 0 and w < 3 do task.wait(0.1) w += 0.1 end
\t\ttable.insert(report, ("%s: %d kf, loads %.2fs"):format(seq.Name, #seq:GetChildren(), t.Length))
\t\tt:Destroy() a:Destroy()
\tend
else
\ttable.insert(report, "no Humanoid+Animator in Workspace to verify against")
end
return table.concat(report, " | ")
'''

# No yields: read the structure of what was just built and say so.
TAIL_SUMMARY = '''
for _, seq in ipairs(built) do
\tlocal n, len, markers, posed, holders = 0, 0, {}, {}, {}
\tfor _, kf in ipairs(seq:GetChildren()) do
\t\tif kf:IsA("Keyframe") then
\t\t\tn += 1
\t\t\tif kf.Time > len then len = kf.Time end
\t\t\tfor _, mk in ipairs(kf:GetMarkers()) do table.insert(markers, ("%s@%.3f"):format(mk.Name, kf.Time)) end
\t\t\tfor _, p in ipairs(kf:GetDescendants()) do
\t\t\t\tif p:IsA("Pose") and p.Name ~= "HumanoidRootPart" then  -- root carries no motor
\t\t\t\t\tif p.Weight > 0 then posed[p.Name] = true else holders[p.Name] = true end
\t\t\t\tend
\t\t\tend
\t\tend
\tend
\tlocal pl, hl = {}, {}
\tfor k in pairs(posed) do table.insert(pl, k) end
\tfor k in pairs(holders) do if not posed[k] then table.insert(hl, k) end end
\ttable.sort(pl) table.sort(hl)
\ttable.insert(report, ("%s: %d kf, length %.3fs, priority %s, loop %s, markers [%s], posed [%s], weight-0 holders [%s], parent %s")
\t\t:format(seq.Name, n, len, seq.Priority.Name, tostring(seq.Loop), table.concat(markers, ","),
\t\t\ttable.concat(pl, ","), table.concat(hl, ","), seq.Parent:GetFullName()))
end
return table.concat(report, "\\n")
'''


def builder(paths, folder="ReplicatedStorage.CustomAnims", verify=True, legacy=False):
    tree = "{" + ",".join('{"%s","%s"}' % (c, p) for c, p in TREE) + "}"
    segs = folder.split(".")
    if segs[0] == "ReplicatedStorage":
        segs = segs[1:]
    if not segs:
        raise SystemExit("--folder must name a folder under ReplicatedStorage")
    segs_lua = "{" + ",".join('"%s"' % s for s in segs) + "}"
    body = []
    for p in paths:
        d = convert(p, legacy=legacy)
        body.append('do local s = build("%s","%s",%s,%s) local old = folder:FindFirstChild(s.Name) '
                    'while old do old:Destroy() old = folder:FindFirstChild(s.Name) end '
                    's.Parent = folder table.insert(built, s) end'
                    % (d["name"], d["priority"], str(d["loop"]).lower(), _kfs(d)))
    return (HEAD % (tree, segs_lua)) + "\n".join(body) + (TAIL_VERIFY if verify else TAIL_SUMMARY)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--folder", default="ReplicatedStorage.CustomAnims")
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--legacy-axes", action="store_true", help="pre-2026-10-08 axis/ease map (wrong; for checks)")
    a = ap.parse_args()
    sys.stdout.write(builder(a.specs, a.folder, verify=not a.no_verify, legacy=a.legacy_axes))
