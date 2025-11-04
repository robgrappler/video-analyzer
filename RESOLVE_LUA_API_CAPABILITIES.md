# DaVinci Resolve Lua API Capabilities & Automation Opportunities

## Available Objects & Methods

### PROJECT METHODS ✓
- `GetMediaPool()` - Access media management
- `GetTimelineCount()` - Count timelines
- `GetCurrentTimeline()` - Get active timeline
- `SetCurrentTimeline()` - Switch timelines
- `SetName()` / `GetName()` - Rename/query project
- `GetSetting()` / `SetSetting()` - Project configuration
- `GetUniqueId()` - Unique identifier

### MEDIA POOL METHODS ✓
- `GetRootFolder()` - Root media folder access
- `CreateEmptyTimeline()` - Create new timeline
- `CreateTimelineFromClips()` - Create timeline from clips
- `ImportMedia()` - Import footage
- `DeleteClips()` - Remove clips
- `AppendToTimeline()` - Add clips to timeline
- `GetCurrentFolder()` / `SetCurrentFolder()` - Navigate folders
- `GetUniqueId()` - Unique identifier

### TIMELINE METHODS ✓
- `GetName()` / `SetName()` - Timeline naming
- `GetTrackCount()` - Count video/audio tracks
- `GetItemListInTrack()` - Get items in track
- **`AddMarker()`** - **Create markers** ✓ (already using)
- `SetSetting()` / `GetSetting()` - Timeline config (fps, resolution)
- `GetStartFrame()` / `GetEndFrame()` - Timeline bounds
- `GetCurrentTimecode()` - Playhead position
- `CreateCompoundClip()` - Create nested sequences
- **`CreateFusionClip()`** - **Create effect layers**
- `AddTrack()` / `DeleteTrack()` - Track management
- `GetUniqueId()` - Unique identifier

### CLIP METHODS (Limited)
- Timeline doesn't expose GetClipAt() in current API version
- But clips can be manipulated via track iteration

---

## RECOMMENDED AUTOMATIONS FOR YOUR WORKFLOW

### 1. **SPEED RAMPS** ✓ Possible via Fusion
- Use `CreateFusionClip()` to add effect layer
- Create retime curve in Fusion composition
- Apply speed keyframes based on JSON parameters

```lua
-- Pseudocode
local fusion_clip = timeline:CreateFusionClip()
-- Configure speed ramp keyframes
```

### 2. **CLIP COLORING BY INTENSITY** ✓ Easy
- Create separate video tracks for each intensity level
- Color-code tracks and clips for visual organization
- Lock non-active tracks to prevent accidents

```lua
-- Create intensity-based tracks
timeline:AddTrack()
timeline:AddTrack()
timeline:AddTrack()
timeline:AddTrack()
timeline:AddTrack()
-- Each for intensity 1-5
```

### 3. **AUDIO TRACK CREATION** ✓ Possible
- Add audio tracks via `AddTrack()`
- Use track settings to control audio properties

```lua
timeline:AddTrack("audio") -- Create audio track
```

### 4. **TIMELINE ORGANIZATION** ✓ Easy
- Rename timeline by edit type/project
- Set timeline frame rate to 30fps via `SetSetting()`
- Create compound clips for grouping related edits

```lua
timeline:SetSetting("timelineFrameRate", "30")
timeline:SetName("Match3 Nocturmex - Editing")
```

### 5. **MARKER ENHANCEMENTS** ✓ Already Doing
- Current implementation is solid
- Could add marker querying for review workflow

```lua
local marker_count = timeline:GetMarkerCount()
local marker = timeline:GetMarkerAtIndex(i)
```

### 6. **FUSION EFFECTS** ⚠️ Limited but Possible
- `CreateFusionClip()` - Create effect node
- `InsertFusionGeneratorInTrack()` - Add Fusion generator
- `InsertOFXGeneratorInTrack()` - Third-party effects

```lua
timeline:InsertFusionGeneratorInTrack("video", 1, "Blur", start_frame)
```

---

## WORKFLOW ENHANCEMENT SUGGESTIONS

### Phase 1: Immediate (Easy wins)
- ✓ Markers (already done)
- [ ] Rename timeline to project/video name
- [ ] Create intensity-based tracks
- [ ] Color-code track by intensity
- [ ] Set timeline to 30fps via SetSetting()

### Phase 2: Medium (Track management)
- [ ] Add audio tracks
- [ ] Lock video tracks by intensity
- [ ] Create compound clips for scene grouping
- [ ] Add metadata tags to markers

### Phase 3: Advanced (Effects)
- [ ] CreateFusionClip() for speed ramps
- [ ] Retime keyframes via Fusion
- [ ] Zoom effects via pan/scale
- [ ] Color grading via color nodes

---

## API LIMITATIONS (macOS fuscript)

### What Works Well
- ✓ Timeline/project navigation
- ✓ Marker creation and querying
- ✓ Track management (add/delete/lock)
- ✓ Clip import and timeline append
- ✓ Settings and configuration
- ✓ Fusion clip creation

### What's Limited/Unavailable
- ❌ Direct clip property modification (SetSpeed, SetOpacity, etc. not exposed)
- ❌ Full Color page access
- ❌ Advanced Fusion node manipulation
- ❌ Render queue automation
- ❌ Memory/performance intensive operations

### Workarounds
- Use Fusion compositions for effects instead of direct clip properties
- Manually apply properties that can't be automated
- Log detailed TODOs in JSON for manual follow-up (current approach)

---

## CODE EXAMPLES FOR NEXT FEATURES

### Example: Create Intensity-Based Tracks
```lua
local track_names = {
  [1] = "Intensity 1 - Green",
  [2] = "Intensity 2 - Cyan", 
  [3] = "Intensity 3 - Yellow",
  [4] = "Intensity 4 - Orange",
  [5] = "Intensity 5 - Red"
}

for intensity = 1, 5 do
  local track = timeline:AddTrack("video")
  if track then
    print("Created track for intensity " .. intensity)
  end
end
```

### Example: Set Timeline to 30fps
```lua
local success = timeline:SetSetting("timelineFrameRate", "30")
if success then
  print("Timeline frame rate set to 30fps")
end
```

### Example: Rename Timeline
```lua
local project_name = "Match3 Nocturmex 25K"
timeline:SetName(project_name .. " - Editing Guide")
```

### Example: Create Fusion Effect Layer
```lua
local fusion_clip = timeline:CreateFusionClip()
if fusion_clip then
  -- Fusion clip created for effects
  print("Created Fusion composition layer")
end
```

---

## RECOMMENDED NEXT STEPS

1. **Immediate**: Enhance marker creation to include metadata
2. **Short-term**: Add intensity-based track organization
3. **Medium-term**: Implement Fusion clip creation for speed ramps
4. **Long-term**: Develop full effect automation framework

## Summary

The Resolve Lua API via fuscript is **functional and useful** for our workflow:
- ✅ Markers working perfectly
- ✅ Track management available
- ✅ Timeline configuration possible
- ✅ Fusion clip creation for effects
- ⚠️ Some advanced features require manual intervention

**Recommendation**: Focus on track organization and timeline setup automation first, as these provide immediate value and don't require complex effect manipulation.
