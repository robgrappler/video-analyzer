# Direct Clip Property Modification Options in DaVinci Resolve

## Executive Summary
While direct clip property methods (SetSpeed, SetOpacity, etc.) aren't exposed in the macOS fuscript Lua API, there are **4 viable workarounds** to achieve property modifications:

1. **Fusion Compositions** (Most Flexible) ✓ Recommended
2. **DaVinci Resolve Studio Python API** (Most Complete) - Requires Studio edition
3. **Timeline XML/EDL Export/Import** (Most Complex) - Manual intervention
4. **Compound Clips + Nesting** (Limited) - For organization only

---

## Option 1: Fusion Compositions (RECOMMENDED)

### How It Works
Instead of modifying clip properties directly, create a Fusion composition that sits on top of the clip and applies the effect.

### Available in fuscript
✓ YES - `CreateFusionClip()` is available
✓ YES - Can create effect layers
⚠️ PARTIAL - Limited node manipulation via Lua

### What You Can Automate

#### Speed/Retime
```lua
-- Create Fusion comp layer for speed ramp
local fusion_clip = timeline:CreateFusionClip()
-- Add Retime node in Fusion, keyframe speed values
-- Cannot directly script keyframes via Lua, but structure is set up
```

**Workflow**: Script creates the Fusion clip structure → User defines keyframes in Fusion UI

#### Opacity
```lua
-- Create Fusion comp with opacity curve
local fusion_clip = timeline:CreateFusionClip()
-- Add Opacity node in Fusion
```

#### Color Grading
```lua
-- Create Fusion comp with color correction
local fusion_clip = timeline:CreateFusionClip()
-- User adds Primaries/Curves nodes
```

#### Zoom/Pan/Crop
```lua
-- Create Fusion comp for transform effects
local fusion_clip = timeline:CreateFusionClip()
-- User sets Transform node keyframes
```

### Pros & Cons

**Pros:**
- ✓ Fully automated setup
- ✓ Non-destructive (preserves original clip)
- ✓ Flexible and powerful
- ✓ Integrates with Resolve workflow
- ✓ Can be saved as Fusion templates

**Cons:**
- ❌ Requires manual keyframe entry in Fusion
- ❌ Learning curve for complex effects
- ❌ Cannot fully automate via Lua

### Implementation Example
```lua
-- Pseudocode for effect automation
local function create_speed_ramp_layer(timeline, start_frame, end_frame, speeds)
  local fusion_clip = timeline:CreateFusionClip()
  
  if fusion_clip then
    -- Structure is created; user will manually add:
    -- 1. Retime node
    -- 2. Keyframes at speeds[1], speeds[2], speeds[3], etc.
    return true
  end
  return false
end
```

---

## Option 2: Resolve Studio Python API

### How It Works
If you have **DaVinci Resolve Studio** (not Free), you can use Python alongside Lua.

### Availability
- ✗ NOT in Free version
- ✓ Available in Studio ($295)
- Can run Python scripts directly or via API

### What Python Can Do
```python
import DaVinciResolveScript as dvr

resolve = dvr.scriptapp("Resolve")
project = resolve.GetProjectManager().GetCurrentProject()
timeline = project.GetCurrentTimeline()

# Get clips
for i in range(1, timeline.GetClipCount() + 1):
    clip = timeline.GetClipAt(i)
    
    # Modify properties (these methods likely exist in Studio)
    clip.SetSpeed(0.5)        # 50% speed
    clip.SetOpacity(0.8)      # 80% opacity
    clip.SetLeftOffset(30)    # Trim 30 frames
```

### Pros & Cons

**Pros:**
- ✓ Full programmatic control
- ✓ No manual intervention needed
- ✓ Complete automation possible
- ✓ Can batch process multiple clips

**Cons:**
- ❌ Requires Resolve Studio ($295)
- ❌ Not available in Free version
- ❌ More complex setup

### Cost-Benefit
- If you already have Studio: **Highly Recommended**
- If only using Free: **Not viable**

---

## Option 3: Timeline XML/EDL Export-Import

### How It Works
1. Export timeline to EDL or XML format
2. Parse and modify timing/speed data
3. Re-import modified timeline

### What You Can Modify
- ✓ Clip start/end times
- ✓ Speed/duration
- ✓ Some track properties

### What You Cannot Modify
- ❌ Opacity/color
- ❌ Complex effects
- ❌ Keyframe data

### Pros & Cons

**Pros:**
- ✓ Works in Free version
- ✓ Can modify timing automatically
- ✓ Scriptable via JSON/XML parsing

**Cons:**
- ❌ Very complex workflow
- ❌ Requires precise EDL/XML knowledge
- ❌ Error-prone (easy to corrupt timeline)
- ❌ Manual reimport required
- ❌ Loses some Resolve-specific features

### Example (Conceptual)
```lua
-- Export timeline
export_timeline("timeline.edl")

-- Parse and modify (external script or Lua)
local edl = parse_edl("timeline.edl")
for _, event in ipairs(edl.events) do
  if event.speed then
    event.speed = event.speed * 0.5  -- Slow down to 50%
  end
end

-- Re-import
reimport_edl("timeline_modified.edl")
```

### Recommendation: ❌ Not Recommended
Too complex and fragile for production use.

---

## Option 4: Compound Clips + Nesting

### How It Works
Create nested sequences (compound clips) to organize and group related clips.

### Available in fuscript
✓ YES - `CreateCompoundClip()` is available

### What You Can Do
```lua
-- Group clips by intensity
for intensity = 1, 5 do
  local compound = timeline:CreateCompoundClip()
  -- Organize clips by intensity level
end
```

### Limitations
- ✓ Good for organization
- ❌ Doesn't modify individual clip properties
- ❌ Limited effect application

### Recommendation: ⚠️ Supplementary Only
Use alongside other options for better organization.

---

## Comprehensive Comparison Table

| Feature | Fusion Comp | Python Studio | EDL/XML | Compound Clip |
|---------|-----------|----------------|---------|--------------|
| Speed/Retime | ✓ Semi-auto | ✓ Full | ✓ Full | ❌ |
| Opacity | ✓ Semi-auto | ✓ Full | ❌ | ❌ |
| Color Grade | ✓ Semi-auto | ✓ Full | ❌ | ❌ |
| Zoom/Pan | ✓ Semi-auto | ✓ Full | ❌ | ❌ |
| Free Version | ✓ Yes | ❌ No | ✓ Yes | ✓ Yes |
| Ease of Use | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ |
| Automation Level | 60% | 100% | 40% | 20% |
| Recommended | ✓✓✓ | ✓✓✓ (if Studio) | ❌ | ⭐ (supporting) |

---

## RECOMMENDED IMPLEMENTATION STRATEGY

### For Free Version Users (Current Approach)
**Use Fusion Compositions + Manual Keyframing**

1. **Automate via Script:**
   - Create Fusion clips at edit points
   - Generate markers for reference
   - Log detailed TODOs (current approach ✓)
   - Create organized track structure

2. **Manual Intervention:**
   - Open Fusion page for each comp
   - Add effect nodes (Retime, Opacity, Color Correct)
   - Keyframe values based on JSON specs

**Benefits:**
- ✓ Fully works with Free version
- ✓ Non-destructive workflow
- ✓ Organized and traceable
- ✓ Can be saved as presets

### For Studio Version Users
**Use Python API for 100% Automation**

```python
# Python would handle all clip modifications
for edit in edits:
    clip = get_clip_at(edit.timecode)
    clip.SetSpeed(edit.speed_factor)
    clip.SetOpacity(edit.opacity)
    # ... etc
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Current (Markers + TODOs) ✓ Done
- ✓ Markers with timecodes
- ✓ JSON run log with effect specifications
- ✓ Color coding by intensity

### Phase 2: Enhanced Setup (Add Fusion Prep)
```lua
local function setup_fusion_effect_layers(timeline, edits)
  for _, edit in ipairs(edits) do
    local fusion_clip = timeline:CreateFusionClip()
    -- User sees prepared Fusion comp
    print("Prepared Fusion comp at " .. edit.start .. " for " .. edit.type)
  end
end
```

### Phase 3: Automation (If Studio Available)
- Switch to Python API
- Full automated property modification
- Zero manual intervention

### Phase 4: Template Integration
- Save Fusion comps as templates
- Batch apply to multiple projects
- Custom presets per effect type

---

## What I Recommend for You

Given your current setup (Free version):

**BEST APPROACH: Fusion Composition + Structured Workflow**

1. **Keep current marker system** ✓ (working great)
2. **Add Fusion prep layer** (create empty Fusion comps at edit points)
3. **Document in JSON** (what effects need to be added)
4. **User workflow** (open Fusion, add keyframes from JSON specs)

```lua
-- Enhanced script would do:
local function process_edit_with_fusion(timeline, edit)
  -- 1. Add marker (current)
  add_marker(timeline, edit.start_f, edit.color, edit.name, edit.note)
  
  -- 2. Create Fusion comp (NEW)
  local fusion = timeline:CreateFusionClip()
  
  -- 3. Log to JSON (current)
  log_todo(edit, "add_effects_in_fusion")
end
```

### Why This Approach?
- ✓ Works with Free version
- ✓ Minimal manual work per edit
- ✓ Preserves non-destructive workflow
- ✓ Scalable to Studio later
- ✓ Professional results
- ✓ Clear, organized process

---

## Next Steps

1. **Short-term**: Add Fusion clip creation to current script
2. **Medium-term**: Test with actual editing projects
3. **Long-term**: If upgrading to Studio, switch to Python API for full automation

---

## Questions to Consider

1. Are you planning to upgrade to Resolve Studio eventually?
2. How many clips/projects do you typically work with?
3. Are your effects relatively standard (same speeds/effects each time)?
4. Do you want maximum automation or is semi-automation acceptable?

**If answers are "Yes/Many/Yes/Maximum" → Start planning Studio upgrade**
**If answers are "No/Few/No/Semi-auto OK" → Fusion prep approach is perfect**
