-- dump_kfs.luau - serialise every KeyframeSequence under a folder to JSON, for
-- upload_animation.py. Run in EDIT mode via execute_luau; returns one JSON string.
-- Set FOLDER below (upload_animation.py --emit-dump writes a copy with it filled in).
local FOLDER = "{{FOLDER}}"

local node: Instance = game
for seg in string.gmatch(FOLDER, "[^%.]+") do
	if seg ~= "game" then
		node = (node :: Instance):FindFirstChild(seg) :: Instance
		assert(node, "folder not found: " .. FOLDER)
	end
end

local function pose(p: Pose)
	local c = { p.CFrame:GetComponents() }
	local kids = {}
	for _, ch in p:GetChildren() do
		if ch:IsA("Pose") then
			table.insert(kids, pose(ch))
		end
	end
	return {
		name = p.Name,
		cf = c,
		style = p.EasingStyle.Value,
		dir = p.EasingDirection.Value,
		weight = p.Weight,
		children = kids,
	}
end

local out = {}
for _, kfs in (node :: Instance):GetChildren() do
	if kfs:IsA("KeyframeSequence") then
		local frames = {}
		for _, kf in kfs:GetChildren() do
			if kf:IsA("Keyframe") then
				local poses, markers = {}, {}
				for _, ch in kf:GetChildren() do
					if ch:IsA("Pose") then
						table.insert(poses, pose(ch))
					elseif ch:IsA("KeyframeMarker") then
						table.insert(markers, { name = ch.Name, value = ch.Value })
					end
				end
				table.insert(frames, { name = kf.Name, time = kf.Time, poses = poses, markers = markers })
			end
		end
		table.insert(out, {
			name = kfs.Name,
			priority = kfs.Priority.Value,
			loop = kfs.Loop,
			keyframes = frames,
		})
	end
end
return game:GetService("HttpService"):JSONEncode(out)
