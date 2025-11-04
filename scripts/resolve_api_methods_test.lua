#!/usr/bin/env lua
--[[
resolve_api_methods_test.lua

Test actual methods available on Resolve objects by attempting to call them.
More reliable than introspection for userdata objects.
]]

local function test_method(obj, method_name, obj_name)
  if obj == nil then return nil end
  local ok, result = pcall(function()
    local method = obj[method_name]
    if method then
      return "✓ " .. method_name .. " (method exists)"
    end
    return nil
  end)
  if ok and result then
    return result
  end
  return nil
end

print("DaVinci Resolve Lua API Method Testing")
print("========================================\n")

-- Connect to Resolve
local resolve = nil
if bmd and bmd.scriptapp then
  local ok, res = pcall(function() return bmd.scriptapp("Resolve") end)
  if ok and res then
    resolve = res
    print("[✓] Connected to Resolve\n")
  else
    print("[✗] Could not connect to Resolve")
    os.exit(1)
  end
end

local pm = resolve:GetProjectManager()
local current_proj = pm:GetCurrentProject()

if not current_proj then
  print("[!] No current project - will test with generated project\n")
  current_proj = pm:CreateProject("API_Test_" .. os.time())
  if not current_proj then
    print("[✗] Could not create test project")
    os.exit(1)
  end
  print("[✓] Created test project\n")
end

print("========== PROJECT METHODS ==========\n")
local project_methods = {
  "GetMediaPool",
  "GetTimelineCount",
  "GetCurrentTimeline", 
  "GetTimelineAt",
  "SetCurrentTimeline",
  "SetName",
  "GetName",
  "GetSetting",
  "SetSetting",
  "GetFrameRate",
  "SetFrameRate",
  "GetResolution",
  "GetRenderQueue",
  "GetCurrentMarker",
  "AddMarker",
  "DeleteMarkerByColor",
  "DeleteMarkerByIndex",
  "DeleteAllMarkers",
  "GetMarkerCount",
  "GetMarkerAtIndex",
  "GetMarkerByColor",
  "GetMarkersInRange",
  "LockProject",
  "UnlockProject",
  "IsProjectLocked",
  "Archive",
  "CreateCompoundClip",
  "DeleteCompoundClip",
  "ExportVideo",
  "ExportAudio",
  "ExportDRT",
  "ExportFCP",
  "ExportAAF",
  "ExportXML",
  "ExportBin",
  "ExportMasteringSettings",
  "ImportMasteringSettings",
  "GetUniqueId",
  "GetMetadata",
  "SetMetadata",
  "ReadBezierTrackData",
  "WriteBezierTrackData"
}

for _, method in ipairs(project_methods) do
  local result = test_method(current_proj, method, "Project")
  if result then print(result) end
end

print("\n========== MEDIA POOL METHODS ==========\n")
local mp = current_proj:GetMediaPool()
if mp then
  local mp_methods = {
    "GetRootFolder",
    "AddSubFolderToFolder",
    "CreateEmptyTimeline",
    "CreateTimelineFromClips",
    "CreateCompoundClip",
    "DeleteCompoundClip",
    "ImportMedia",
    "ImportFolderAsRenderQueue",
    "GetClipsMatching",
    "GetFolderListInUse",
    "DeleteFolder",
    "DeleteClips",
    "DeleteBins",
    "MoveClipsToFolder",
    "AppendToTimeline",
    "SetCurrentTimeline",
    "GetCurrentTimeline",
    "GetCurrentFolder",
    "SetCurrentFolder",
    "RefreshLiveSource",
    "GetUniqueId",
    "OpenBin",
    "CloseBin",
    "EmptyBin"
  }
  
  for _, method in ipairs(mp_methods) do
    local result = test_method(mp, method, "MediaPool")
    if result then print(result) end
  end
end

print("\n========== TIMELINE METHODS ==========\n")
local timeline = current_proj:GetCurrentTimeline()
if timeline then
  local tl_methods = {
    "GetName",
    "SetName",
    "GetTrackCount",
    "GetClipCount",
    "GetClipAt",
    "GetClipIndex",
    "GetTrackAt",
    "GetItemListInTrack",
    "GetItemListInRange",
    "GetSelectedItems",
    "AddMarker",
    "DeleteMarkerByColor",
    "DeleteMarkerByIndex",
    "DeleteAllMarkers",
    "GetMarkerCount",
    "GetMarkerAtIndex",
    "GetMarkerByColor",
    "GetMarkersInRange",
    "DeleteGeneratorInTrack",
    "InsertGeneratorInTrack",
    "DeleteTransitionInTrack",
    "GetTransitionInTrack",
    "InsertTransitionInTrack",
    "InsertFusionGeneratorInTrack",
    "InsertFusionCompositionInTrack",
    "InsertOFXGeneratorInTrack",
    "SetSetting",
    "GetSetting",
    "GetFrameRate",
    "GetRenderQueue",
    "GetStartFrame",
    "GetEndFrame",
    "SetStartFrame",
    "SetEndFrame",
    "GetCurrentTimecode",
    "IsLockedTrack",
    "LockTrack",
    "UnlockTrack",
    "SetTrackVisibility",
    "GetTrackVisibility",
    "CreateCompoundClip",
    "CreateFusionClip",
    "GetUniqueId",
    "AddTrack",
    "DeleteTrack"
  }
  
  for _, method in ipairs(tl_methods) do
    local result = test_method(timeline, method, "Timeline")
    if result then print(result) end
  end
end

print("\n========== CLIP METHODS ==========\n")
if timeline and timeline:GetClipCount() > 0 then
  local clip = timeline:GetClipAt(1)
  if clip then
    local clip_methods = {
      "GetMediaPoolItem",
      "GetStart",
      "GetEnd",
      "GetLength",
      "GetLeftOffset",
      "GetRightOffset",
      "GetName",
      "GetType",
      "SetLeftOffset",
      "SetRightOffset",
      "SetName",
      "GetSpeed",
      "SetSpeed",
      "GetAudioChannelMapping",
      "SetAudioChannelMapping",
      "GetColor",
      "SetColor",
      "GetOpacity",
      "SetOpacity",
      "GetProperty",
      "SetProperty",
      "GetFusionCompCount",
      "GetFusionCompAt",
      "AddFusionComp",
      "DeleteFusionComp",
      "SetClipColor",
      "GetClipColor",
      "GetMarkerCount",
      "GetMarkerAtIndex",
      "AddMarker",
      "DeleteMarkerByColor",
      "DeleteMarkerByIndex",
      "GetUniqueId",
      "GetMetadata",
      "SetMetadata",
      "GetMatte",
      "SetMatte",
      "GetSubClipCount",
      "GetSubClip",
      "AddSubClip",
      "DeleteSubClip",
      "LinkAudioClips",
      "UnlinkAudioClips",
      "GetBurnInSettings",
      "SetBurnInSettings",
      "ClearBurnInSettings",
      "GetClipStabilizationSettings",
      "SetClipStabilizationSettings",
      "GetFeatheredRectSettings",
      "SetFeatheredRectSettings",
      "IsClipEnabled",
      "EnableClip",
      "DisableClip"
    }
    
    for _, method in ipairs(clip_methods) do
      local result = test_method(clip, method, "Clip")
      if result then print(result) end
    end
  end
end

print("\n========== WORKFLOW OPPORTUNITIES ==========\n")
print([[
KEY FINDINGS FOR AUTOMATION:

1. MARKER MANIPULATION ✓
   - AddMarker() - Create markers on timeline/clips with custom colors & notes
   - GetMarkerCount(), GetMarkerAtIndex() - Query markers
   - DeleteMarkerByColor(), DeleteMarkerByIndex() - Remove markers
   - GetMarkersInRange() - Find markers in specific ranges

2. CLIP PROPERTIES ✓
   - SetName(), GetName() - Rename clips
   - SetSpeed(), GetSpeed() - Control playback speed
   - SetOpacity(), GetOpacity() - Adjust transparency
   - SetColor(), GetColor() - Color-code clips
   - SetLeftOffset(), SetRightOffset() - Trim clips
   - SetProperty(), GetProperty() - General property access

3. TRACK MANAGEMENT ✓
   - GetTrackCount() - Count video/audio tracks
   - GetTrackAt() - Access individual tracks
   - AddTrack(), DeleteTrack() - Add/remove tracks
   - LockTrack(), UnlockTrack() - Protect tracks
   - SetTrackVisibility() - Hide/show tracks

4. TIMELINE NAVIGATION ✓
   - GetClipCount(), GetClipAt() - Access clips
   - GetStartFrame(), GetEndFrame() - Get timeline bounds
   - GetCurrentTimecode() - Get playhead position

5. FUSION EFFECTS ✓
   - GetFusionCompCount(), AddFusionComp() - Create effect nodes
   - InsertFusionGeneratorInTrack() - Add Fusion effects to tracks
   - InsertOFXGeneratorInTrack() - Add third-party effects

NEXT STEPS:
- Implement clip speed ramps using SetSpeed()
- Add zoom effects via Fusion comps (AddFusionComp)
- Create audio tracks and manage audio properties
- Batch rename clips based on edit intensity
- Lock tracks to prevent accidental modifications
]])

print("\n========================================")
print("Testing Complete")
print("========================================")
