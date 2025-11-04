#!/usr/bin/env lua
--[[
resolve_api_discovery.lua

Explore and document the DaVinci Resolve Lua API available in fuscript.
Discovers available objects, methods, and properties for workflow optimization.

Usage:
  fuscript -l lua resolve_api_discovery.lua > resolve_api_capabilities.txt 2>&1
]]

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

local function get_type(obj)
  if obj == nil then return "nil" end
  local t = type(obj)
  if t == "userdata" or t == "table" then
    local mt = getmetatable(obj)
    if mt and mt.__name then
      return mt.__name
    end
  end
  return t
end

local function get_methods(obj, name)
  local methods = {}
  if type(obj) == "userdata" or type(obj) == "table" then
    for k, v in pairs(obj) do
      if type(v) == "function" or (type(v) == "userdata") then
        table.insert(methods, {key = k, type = get_type(v)})
      end
    end
  end
  return methods
end

local function print_section(title)
  print("\n" .. string.rep("=", 80))
  print("  " .. title)
  print(string.rep("=", 80))
end

local function print_subsection(title)
  print("\n" .. string.rep("-", 80))
  print(title)
  print(string.rep("-", 80))
end

-- ============================================================================
-- DISCOVERY
-- ============================================================================

print("DaVinci Resolve Lua API Discovery")
print("Generated: " .. os.date("%Y-%m-%d %H:%M:%S"))

-- Check for BMD global
print_section("BMD Global Object")
if bmd then
  print("✓ BMD global available")
  print("\nBMD methods/properties:")
  local bmd_methods = get_methods(bmd, "bmd")
  for _, method in ipairs(bmd_methods) do
    print("  - " .. method.key .. " (" .. method.type .. ")")
  end
else
  print("✗ BMD global NOT available")
end

-- Check for Resolve connection
print_section("Resolve Object")
local resolve = nil
if bmd and bmd.scriptapp then
  local ok, res = pcall(function() return bmd.scriptapp("Resolve") end)
  if ok and res then
    resolve = res
    print("✓ Resolve object available via bmd.scriptapp('Resolve')")
    print("\nResolve methods/properties:")
    local resolve_methods = get_methods(resolve, "resolve")
    for _, method in ipairs(resolve_methods) do
      print("  - " .. method.key .. " (" .. method.type .. ")")
    end
  else
    print("✗ Could not get Resolve object: " .. tostring(res))
  end
else
  print("✗ bmd.scriptapp not available")
end

-- Explore ProjectManager
print_section("ProjectManager Object")
if resolve then
  local ok, pm = pcall(function() return resolve:GetProjectManager() end)
  if ok and pm then
    print("✓ ProjectManager available via resolve:GetProjectManager()")
    print("\nProjectManager methods/properties:")
    local pm_methods = get_methods(pm, "pm")
    for _, method in ipairs(pm_methods) do
      print("  - " .. method.key .. " (" .. method.type .. ")")
    end
    
    -- Try to get current project
    local current_proj = nil
    local proj_ok, proj = pcall(function() return pm:GetCurrentProject() end)
    if proj_ok and proj then
      current_proj = proj
      print("\n✓ Current project available")
    else
      print("\n✗ No current project or GetCurrentProject not available")
    end
    
    -- Explore Project
    if current_proj then
      print_subsection("Project Object")
      print("✓ Project object available")
      print("\nProject methods/properties:")
      local proj_methods = get_methods(current_proj, "project")
      for _, method in ipairs(proj_methods) do
        print("  - " .. method.key .. " (" .. method.type .. ")")
      end
      
      -- Try to get MediaPool
      local mp_ok, mp = pcall(function() return current_proj:GetMediaPool() end)
      if mp_ok and mp then
        print_subsection("MediaPool Object")
        print("✓ MediaPool available via project:GetMediaPool()")
        print("\nMediaPool methods/properties:")
        local mp_methods = get_methods(mp, "mp")
        for _, method in ipairs(mp_methods) do
          print("  - " .. method.key .. " (" .. method.type .. ")")
        end
      end
      
      -- Try to get current Timeline
      local tl_ok, tl = pcall(function() return current_proj:GetCurrentTimeline() end)
      if tl_ok and tl then
        print_subsection("Timeline Object")
        print("✓ Timeline available via project:GetCurrentTimeline()")
        print("\nTimeline methods/properties:")
        local tl_methods = get_methods(tl, "tl")
        for _, method in ipairs(tl_methods) do
          print("  - " .. method.key .. " (" .. method.type .. ")")
        end
        
        -- Try to get TrackCount
        local track_count_ok, track_count = pcall(function() return tl:GetTrackCount("video") end)
        if track_count_ok then
          print("\nVideo tracks: " .. tostring(track_count))
          
          -- Try to get first video track
          if track_count and track_count > 0 then
            local track_ok, track = pcall(function() return tl:GetTrackAt("video", 1) end)
            if track_ok and track then
              print_subsection("Track Object (Video Track 1)")
              print("✓ Track available via timeline:GetTrackAt('video', 1)")
              print("\nTrack methods/properties:")
              local track_methods = get_methods(track, "track")
              for _, method in ipairs(track_methods) do
                print("  - " .. method.key .. " (" .. method.type .. ")")
              end
            end
          end
        end
        
        -- Try to get clips
        local clips_ok, clips = pcall(function() return tl:GetClipCount() end)
        if clips_ok and clips then
          print("\nClips in timeline: " .. tostring(clips))
          
          if clips > 0 then
            local clip_ok, clip = pcall(function() return tl:GetClipAt(1) end)
            if clip_ok and clip then
              print_subsection("Clip Object (Clip 1)")
              print("✓ Clip available via timeline:GetClipAt(1)")
              print("\nClip methods/properties:")
              local clip_methods = get_methods(clip, "clip")
              for _, method in ipairs(clip_methods) do
                print("  - " .. method.key .. " (" .. method.type .. ")")
              end
            end
          end
        end
      end
    end
  else
    print("✗ Could not get ProjectManager: " .. tostring(pm))
  end
end

-- Check for Fusion (effects/compositing)
print_section("Fusion Object (Effects/Compositing)")
local fusion_ok, fusion = pcall(function() return bmd.scriptapp("Fusion") end)
if fusion_ok and fusion then
  print("✓ Fusion object available via bmd.scriptapp('Fusion')")
  print("\nFusion methods/properties:")
  local fusion_methods = get_methods(fusion, "fusion")
  for _, method in ipairs(fusion_methods) do
    print("  - " .. method.key .. " (" .. method.type .. ")")
  end
else
  print("✗ Fusion object not available: " .. tostring(fusion))
end

-- Check for other possible apps
print_section("Other Available scriptapp Resources")
local apps = {"MediaStorage", "Workspace", "UI", "Console"}
for _, app_name in ipairs(apps) do
  local app_ok, app = pcall(function() return bmd.scriptapp(app_name) end)
  if app_ok and app then
    print("✓ " .. app_name .. " available")
    print("  Methods/properties:")
    local app_methods = get_methods(app, app_name)
    for _, method in ipairs(app_methods) do
      print("    - " .. method.key .. " (" .. method.type .. ")")
    end
  end
end

print_section("WORKFLOW SUGGESTIONS")
print([[
Based on the API exploration above, consider these opportunities:

1. MARKERS & ORGANIZATION
   - Use Timeline methods to create/edit markers
   - Color-code by intensity (already doing this!)
   - Add notes/descriptions to markers

2. CLIP MANIPULATION
   - Set clip properties (speed, opacity, etc.)
   - Arrange clips in timeline
   - Set clip in/out points

3. EFFECTS & COMPOSITING
   - Access Fusion page for visual effects
   - Create color correction nodes
   - Apply transitions

4. TRACK MANAGEMENT
   - Add/delete tracks
   - Lock/unlock tracks
   - Adjust track height

5. METADATA & TAGS
   - Add custom metadata to clips
   - Use keywords for organization
   - Create selection groups

6. AUTOMATION
   - Batch process multiple edits
   - Apply presets to clips
   - Export/render operations
]])

print("\n" .. string.rep("=", 80))
print("Discovery Complete")
print(string.rep("=", 80))
