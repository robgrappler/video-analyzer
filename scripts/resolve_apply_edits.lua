#!/usr/bin/env lua
--[[
resolve_apply_edits.lua

Translate a Gemini-generated editing_guide.json into DaVinci Resolve (Free) timeline actions.
V1 focuses on: project/timeline creation (30fps), media import/placement, markers, and
best-effort stubs for effect application. Audio SFX/ducking are skipped (TODO markers only).

Usage:
  fuscript -l lua resolve_apply_edits.lua --json /path/to/{stem}_editing_guide.json \
      [--project-name NAME] [--dry-run] \
      [--color-preset PunchyContrast] [--vignette-preset VignetteMedium]

Or via environment variable:
  EDITING_GUIDE_JSON=/path/to/guide.json fuscript -l lua resolve_apply_edits.lua [options]

Notes:
- Timecodes in JSON are interpreted relative to timeline start (00:00:00) at 30fps.
- This script aims to be safe: most Resolve API calls are wrapped; failures become TODOs in the log.
- V1 does not guarantee true retime curves; segment-level speed changes are approximations and may be
  logged as TODOs if the API is unavailable in your environment.
]]

-- ============================================================================
-- EMBEDDED PURE-LUA JSON PARSER (via dkjson-inspired simple implementation)
-- ============================================================================

local json = {}

local function encode_value(v, seen)
  seen = seen or {}
  if seen[v] then
    error("Circular reference in JSON encoding")
  end
  
  if type(v) == "nil" then
    return "null"
  elseif type(v) == "boolean" then
    return v and "true" or "false"
  elseif type(v) == "number" then
    if v ~= v then return "null" end -- NaN
    if v == math.huge or v == -math.huge then return "null" end
    return tostring(v)
  elseif type(v) == "string" then
    local escaped = v:gsub("\\", "\\\\")
                     :gsub('"', '\\"')
                     :gsub("\b", "\\b")
                     :gsub("\f", "\\f")
                     :gsub("\n", "\\n")
                     :gsub("\r", "\\r")
                     :gsub("\t", "\\t")
    return '"' .. escaped .. '"'
  elseif type(v) == "table" then
    seen[v] = true
    local is_array = false
    local max_idx = 0
    for k in pairs(v) do
      if type(k) == "number" and k > 0 and k == math.floor(k) then
        max_idx = math.max(max_idx, k)
      end
    end
    is_array = (max_idx > 0)
    
    if is_array and next(v, max_idx) == nil then
      -- Array
      local parts = {}
      for i = 1, max_idx do
        parts[i] = encode_value(v[i], seen)
      end
      seen[v] = nil
      return "[" .. table.concat(parts, ",") .. "]"
    else
      -- Object
      local parts = {}
      for k, val in pairs(v) do
        if type(k) == "string" then
          table.insert(parts, encode_value(k, seen) .. ":" .. encode_value(val, seen))
        end
      end
      seen[v] = nil
      return "{" .. table.concat(parts, ",") .. "}"
    end
  else
    return "null"
  end
end

function json.encode(v)
  return encode_value(v)
end

local function skip_whitespace(str, pos)
  while pos <= #str and str:sub(pos, pos):match("%s") do
    pos = pos + 1
  end
  return pos
end

local function parse_string(str, pos)
  pos = pos + 1 -- skip opening "
  local chars = {}
  while pos <= #str do
    local ch = str:sub(pos, pos)
    if ch == '"' then
      return table.concat(chars), pos + 1
    elseif ch == "\\" then
      pos = pos + 1
      if pos <= #str then
        local esc = str:sub(pos, pos)
        if esc == '"' then table.insert(chars, '"')
        elseif esc == "\\" then table.insert(chars, "\\")
        elseif esc == "/" then table.insert(chars, "/")
        elseif esc == "b" then table.insert(chars, "\b")
        elseif esc == "f" then table.insert(chars, "\f")
        elseif esc == "n" then table.insert(chars, "\n")
        elseif esc == "r" then table.insert(chars, "\r")
        elseif esc == "t" then table.insert(chars, "\t")
        elseif esc == "u" then
          local hex = str:sub(pos + 1, pos + 4)
          if hex:len() == 4 and hex:match("^%x%x%x%x$") then
            table.insert(chars, string.char(tonumber(hex, 16)))
            pos = pos + 4
          end
        else
          table.insert(chars, esc)
        end
      end
      pos = pos + 1
    else
      table.insert(chars, ch)
      pos = pos + 1
    end
  end
  error("Unterminated string in JSON")
end

local function parse_number(str, pos)
  local start = pos
  if str:sub(pos, pos) == "-" then pos = pos + 1 end
  while pos <= #str and str:sub(pos, pos):match("[0-9]") do pos = pos + 1 end
  if pos <= #str and str:sub(pos, pos) == "." then
    pos = pos + 1
    while pos <= #str and str:sub(pos, pos):match("[0-9]") do pos = pos + 1 end
  end
  if pos <= #str and str:sub(pos, pos):match("[eE]") then
    pos = pos + 1
    if pos <= #str and str:sub(pos, pos):match("[+-]") then pos = pos + 1 end
    while pos <= #str and str:sub(pos, pos):match("[0-9]") do pos = pos + 1 end
  end
  return tonumber(str:sub(start, pos - 1)), pos
end

local function parse_value(str, pos)
  pos = skip_whitespace(str, pos)
  if pos > #str then error("Unexpected end of JSON") end
  
  local ch = str:sub(pos, pos)
  
  if ch == '"' then
    return parse_string(str, pos)
  elseif ch == "{" then
    local obj = {}
    pos = pos + 1
    pos = skip_whitespace(str, pos)
    
    if str:sub(pos, pos) == "}" then
      return obj, pos + 1
    end
    
    while true do
      pos = skip_whitespace(str, pos)
      local key, new_pos = parse_string(str, pos)
      pos = skip_whitespace(str, new_pos)
      
      if str:sub(pos, pos) ~= ":" then error("Expected ':' in JSON object") end
      pos = skip_whitespace(str, pos + 1)
      
      local val
      val, pos = parse_value(str, pos)
      obj[key] = val
      
      pos = skip_whitespace(str, pos)
      local next_ch = str:sub(pos, pos)
      
      if next_ch == "}" then
        return obj, pos + 1
      elseif next_ch == "," then
        pos = pos + 1
      else
        error("Expected ',' or '}' in JSON object")
      end
    end
  elseif ch == "[" then
    local arr = {}
    pos = pos + 1
    pos = skip_whitespace(str, pos)
    
    if str:sub(pos, pos) == "]" then
      return arr, pos + 1
    end
    
    local idx = 1
    while true do
      local val
      val, pos = parse_value(str, pos)
      arr[idx] = val
      idx = idx + 1
      
      pos = skip_whitespace(str, pos)
      local next_ch = str:sub(pos, pos)
      
      if next_ch == "]" then
        return arr, pos + 1
      elseif next_ch == "," then
        pos = pos + 1
      else
        error("Expected ',' or ']' in JSON array")
      end
    end
  elseif ch == "t" and str:sub(pos, pos + 3) == "true" then
    return true, pos + 4
  elseif ch == "f" and str:sub(pos, pos + 4) == "false" then
    return false, pos + 5
  elseif ch == "n" and str:sub(pos, pos + 3) == "null" then
    return nil, pos + 4
  elseif ch == "-" or ch:match("[0-9]") then
    return parse_number(str, pos)
  else
    error("Unexpected character '" .. ch .. "' in JSON")
  end
end

function json.decode(str)
  local val, pos = parse_value(str, 1)
  pos = skip_whitespace(str, pos)
  if pos <= #str then
    error("Extra characters after JSON value")
  end
  return val
end

-- ============================================================================
-- GLOBAL CONSTANTS & CONFIGURATION
-- ============================================================================

local FPS = 30
local DEFAULT_COLOR_PRESET = "PunchyContrast"
local DEFAULT_VIGNETTE_PRESET = "VignetteMedium"

local INTENSITY_COLOR = {
  [1] = "Green",
  [2] = "Cyan",
  [3] = "Yellow",
  [4] = "Orange",
  [5] = "Red",
}

-- ============================================================================
-- UTILITY: PATH OPERATIONS
-- ============================================================================

local function basename(path)
  return path:match("^.*/(.+)$") or path
end

local function dirname(path)
  return path:match("^(.*)/[^/]+$") or "."
end

local function stem_name(path)
  local base = basename(path)
  return base:match("^(.+)%..+$") or base
end

local function file_exists(path)
  local f = io.open(path, "r")
  if f then
    f:close()
    return true
  end
  return false
end

local function expand_path(path)
  if path:sub(1, 1) == "~" then
    local home = os.getenv("HOME") or os.getenv("USERPROFILE")
    if home then
      return home .. path:sub(2)
    end
  end
  return path
end

local function read_file(path)
  local f, err = io.open(path, "r")
  if not f then
    return nil, err
  end
  local content = f:read("*a")
  f:close()
  return content
end

local function write_file(path, content)
  -- Ensure directory exists
  local dir = dirname(path)
  if dir ~= "." then
    os.execute("mkdir -p '" .. dir:gsub("'", "'\\''") .. "' 2>/dev/null")
  end
  
  local f, err = io.open(path, "w")
  if not f then
    return false, err
  end
  f:write(content)
  f:close()
  return true
end

-- ============================================================================
-- UTILITY: TIMECODE CONVERSION
-- ============================================================================

local function parse_timecode_to_seconds(tc)
  if not tc or tc == "" then return 0 end
  
  -- Try to parse as pure number (seconds)
  local num = tonumber(tc)
  if num then return num end
  
  -- Parse HH:MM:SS or MM:SS or SS
  local parts = {}
  for part in tc:gmatch("[^:%.]+") do
    table.insert(parts, tonumber(part) or 0)
  end
  
  if #parts == 3 then
    return parts[1] * 3600 + parts[2] * 60 + parts[3]
  elseif #parts == 2 then
    return parts[1] * 60 + parts[2]
  elseif #parts == 1 then
    return parts[1]
  else
    return 0
  end
end

local function seconds_to_frames(seconds, fps)
  fps = fps or FPS
  return math.floor(seconds * fps + 0.5)
end

local function frames_to_timecode(frames, fps)
  fps = fps or FPS
  local total_seconds = math.floor(frames / fps)
  local frame_in_sec = frames % fps
  local hours = math.floor(total_seconds / 3600)
  local minutes = math.floor((total_seconds % 3600) / 60)
  local seconds = total_seconds % 60
  return string.format("%02d:%02d:%02d:%02d", hours, minutes, seconds, frame_in_sec)
end

-- ============================================================================
-- UTILITY: SAFE RESOLVE API CALLS
-- ============================================================================

local function safe_call(description, fn, ...)
  local ok, result = pcall(fn, ...)
  if not ok then
    print("[WARN] " .. description .. ": " .. tostring(result))
    return nil, result
  end
  return result
end

-- ============================================================================
-- UTILITY: CONSOLE OUTPUT & HELPERS
-- ============================================================================

local function print_usage()
  print([[
resolve_apply_edits.lua v1.0

Apply Gemini editing guide to DaVinci Resolve (Free) at 30fps.

Usage:
  fuscript -l lua resolve_apply_edits.lua --json <path> [options]
  EDITING_GUIDE_JSON=<path> fuscript -l lua resolve_apply_edits.lua [options]

Options:
  --json PATH              Path to {stem}_editing_guide.json (or use EDITING_GUIDE_JSON env var)
  --project-name NAME      DaVinci Resolve project name (default: Auto-generated from stem)
  --dry-run                Plan and log without mutating Resolve
  --color-preset PRESET    Color grading preset name (logged; not applied in v1)
  --vignette-preset PRESET Vignette preset name (logged; not applied in v1)
  --help                   Show this help message

Exit codes:
  0 - Success
  1 - JSON parse error or unrecoverable I/O failure
  2 - CLI usage error
]])
end

local function current_timestamp()
  -- Simple ISO 8601-like format
  local t = os.date("*t")
  return string.format("%04d-%02d-%02dT%02d:%02d:%02d",
    t.year, t.month, t.day, t.hour, t.min, t.sec)
end

-- ============================================================================
-- CLI & ARGUMENT PARSING
-- ============================================================================

local function parse_args(arg)
  local result = {
    json_path = nil,
    project_name = nil,
    dry_run = false,
    color_preset = DEFAULT_COLOR_PRESET,
    vignette_preset = DEFAULT_VIGNETTE_PRESET,
  }
  
  local i = 1
  while i <= #arg do
    local opt = arg[i]
    
    if opt == "--help" or opt == "-h" then
      print_usage()
      os.exit(0)
    elseif opt == "--json" then
      i = i + 1
      result.json_path = arg[i]
    elseif opt == "--project-name" then
      i = i + 1
      result.project_name = arg[i]
    elseif opt == "--dry-run" then
      result.dry_run = true
    elseif opt == "--color-preset" then
      i = i + 1
      result.color_preset = arg[i]
    elseif opt == "--vignette-preset" then
      i = i + 1
      result.vignette_preset = arg[i]
    else
      print("[ERROR] Unknown option: " .. opt)
      print_usage()
      os.exit(2)
    end
    
    i = i + 1
  end
  
  -- Try environment variable if not provided
  if not result.json_path then
    result.json_path = os.getenv("EDITING_GUIDE_JSON")
  end
  
  if not result.json_path then
    print("[ERROR] No JSON path provided. Use --json or set EDITING_GUIDE_JSON environment variable.")
    print_usage()
    os.exit(2)
  end
  
  result.json_path = expand_path(result.json_path)
  
  if not file_exists(result.json_path) then
    print("[ERROR] JSON file not found: " .. result.json_path)
    os.exit(2)
  end
  
  return result
end

-- ============================================================================
-- RESOLVE API DETECTION & INITIALIZATION
-- ============================================================================

local function detect_resolve_api()
  local api_available = false
  local resolve = nil
  local pm = nil
  local capabilities = {}
  
  -- Attempt to access Resolve via BMD global
  if bmd and bmd.scriptapp then
    local ok, res = pcall(function() return bmd.scriptapp("Resolve") end)
    if ok and res then
      resolve = res
      capabilities.resolve_available = true
      
      -- Try to get ProjectManager
      if resolve.GetProjectManager then
        ok, res = pcall(function() return resolve:GetProjectManager() end)
        if ok and res then
          pm = res
          capabilities.project_manager_available = true
          api_available = true
        else
          capabilities.project_manager_failed = tostring(res)
        end
      end
    else
      capabilities.resolve_connection_failed = tostring(res)
    end
  end
  
  if not api_available then
    print("[INFO] Resolve Scripting API not available (expected on macOS with fuscript).")
    print("       Proceeding in dry-run mode; run log will still be generated.")
  end
  
  return api_available, resolve, pm, capabilities
end

-- ============================================================================
-- PROJECT & TIMELINE MANAGEMENT
-- ============================================================================

local function load_or_create_project(pm, project_name, fps, run_log)
  if not pm or not project_name then
    return nil
  end
  
  local project = safe_call("Load project '" .. project_name .. "'", function()
    return pm:LoadProject(project_name)
  end)
  
  if not project then
    project = safe_call("Create project '" .. project_name .. "'", function()
      return pm:CreateProject(project_name)
    end)
  end
  
  if project then
    -- Attempt to set frame rate
    safe_call("Set project frame rate to " .. tostring(fps), function()
      project:SetSetting("timelineFrameRate", tostring(fps))
    end)
    
    table.insert(run_log.warnings, "Project loaded/created: " .. project_name)
  else
    table.insert(run_log.warnings, "Could not load or create project: " .. project_name)
  end
  
  return project
end

local function ensure_timeline(project, timeline_name, fps, run_log)
  if not project then
    return nil
  end
  
  -- Check for existing timeline
  local timeline = safe_call("Get current timeline", function()
    return project:GetCurrentTimeline()
  end)
  
  if timeline then
    table.insert(run_log.warnings, "Using existing timeline")
    return timeline
  end
  
  -- Create empty timeline
  local mp = safe_call("Get media pool", function()
    return project:GetMediaPool()
  end)
  
  if mp then
    timeline = safe_call("Create empty timeline '" .. timeline_name .. "'", function()
      return mp:CreateEmptyTimeline(timeline_name)
    end)
  end
  
  if timeline then
    table.insert(run_log.warnings, "Created timeline: " .. timeline_name)
    return timeline
  end
  
  timeline = safe_call("Get current timeline after creation attempt", function()
    return project:GetCurrentTimeline()
  end)
  
  return timeline
end

local function import_media(project, source_path, run_log)
  if not project or not source_path or not file_exists(source_path) then
    if not file_exists(source_path) then
      table.insert(run_log.warnings, "Source media file not found: " .. source_path)
    end
    return nil
  end
  
  local mp = safe_call("Get media pool for import", function()
    return project:GetMediaPool()
  end)
  
  if not mp then
    table.insert(run_log.warnings, "Could not get media pool for import")
    return nil
  end
  
  local items = safe_call("Import media '" .. basename(source_path) .. "'", function()
    return mp:ImportMedia({source_path})
  end)
  
  if items and #items > 0 then
    table.insert(run_log.warnings, "Imported " .. tostring(#items) .. " clip(s)")
    return items
  else
    table.insert(run_log.warnings, "Import succeeded but no clips returned")
    return nil
  end
end

-- ============================================================================
-- MARKER CREATION
-- ============================================================================

local function add_marker(timeline, frame, color, name, note, duration_frames)
  if not timeline then
    return false
  end
  
  local success = safe_call("Add marker '" .. name .. "' at frame " .. tostring(frame), function()
    timeline:AddMarker(frame, color, name, note, duration_frames or 0)
  end)
  
  return success ~= nil
end

-- ============================================================================
-- EDIT PROCESSING & MARKER APPLICATION
-- ============================================================================

local function normalize_edits(data, run_log)
  local edits = {}
  
  local raw_edits = data.edits or {}
  if not raw_edits or type(raw_edits) ~= "table" then
    table.insert(run_log.warnings, "No edits array found in JSON")
    return edits
  end
  
  for idx, raw in ipairs(raw_edits) do
    local start_sec = parse_timecode_to_seconds(raw.start or raw.start_time or "00:00:00")
    local end_sec = parse_timecode_to_seconds(raw["end"] or raw.end_time or "00:00:00")
    
    local start_f = seconds_to_frames(start_sec, FPS)
    local end_f = seconds_to_frames(end_sec, FPS)
    
    if end_f <= start_f then
      end_f = start_f + FPS -- At least ~1 second
    end
    
    local edit = {
      id = tostring(raw.id or ("E" .. string.format("%03d", idx))),
      label = tostring(raw.label or "Edit " .. idx),
      type = tostring(raw.type or "unknown"),
      start = tostring(raw.start or raw.start_time or "00:00:00"),
      end_time = tostring(raw.end_time or raw["end"] or "00:00:00"),
      start_sec = start_sec,
      end_sec = end_sec,
      start_f = start_f,
      end_f = end_f,
      intensity_1_5 = math.max(1, math.min(5, tonumber(raw.intensity_1_5) or 3)),
      why_this_works = tostring(raw.why_this_works or ""),
      effects_map = raw.effects_map or raw.resolve_hint or {},
      techniques = raw.edits or {},
    }
    
    table.insert(edits, edit)
  end
  
  -- Sort by start frame
  table.sort(edits, function(a, b)
    return a.start_f < b.start_f
  end)
  
  return edits
end

local function process_edits(timeline, edits, run_log, api_available, dry_run, color_preset, vignette_preset)
  local markers_added = 0
  local todos_logged = 0
  
  -- Process in reverse to minimize time shifts
  for i = #edits, 1, -1 do
    local edit = edits[i]
    local entry = {
      id = edit.id,
      label = edit.label,
      type = edit.type,
      start = edit.start,
      end_time = edit.end_time,
      start_f = edit.start_f,
      end_f = edit.end_f,
      duration_f = edit.end_f - edit.start_f,
      intensity_1_5 = edit.intensity_1_5,
      color = INTENSITY_COLOR[edit.intensity_1_5] or "Blue",
      status = (dry_run and "dry_run") or (api_available and "marker_added_attempt") or "api_unavailable",
      actions = {},
      warnings = {},
      todos = {},
    }
    
    -- Compose marker
    local marker_name = entry.id .. " " .. entry.label .. " (intensity " .. entry.intensity_1_5 .. ")"
    local marker_note_parts = {}
    
    if edit.why_this_works and edit.why_this_works ~= "" then
      table.insert(marker_note_parts, edit.why_this_works)
    end
    
    -- Serialize effects_map
    if edit.effects_map then
      if type(edit.effects_map) == "string" then
        table.insert(marker_note_parts, "Effects: " .. edit.effects_map)
      elseif type(edit.effects_map) == "table" then
        local ok, json_str = pcall(json.encode, edit.effects_map)
        if ok then
          local truncated = json_str:sub(1, 600)
          table.insert(marker_note_parts, "Effects: " .. truncated)
        end
      end
    end
    
    -- Add preset hints if any techniques present
    if #edit.techniques > 0 then
      if color_preset ~= DEFAULT_COLOR_PRESET then
        table.insert(marker_note_parts, "Color preset: " .. color_preset)
      end
      if vignette_preset ~= DEFAULT_VIGNETTE_PRESET then
        table.insert(marker_note_parts, "Vignette preset: " .. vignette_preset)
      end
    end
    
    local marker_note = table.concat(marker_note_parts, " | ")
    
    -- Check for audio-only techniques
    local has_audio_only = false
    local has_visual_fx = false
    local visual_fx_types = {}
    
    for _, tech in ipairs(edit.techniques) do
      local tech_type = tech.type or "unknown"
      if tech_type == "sfx" or tech_type == "audio_ducking" then
        has_audio_only = true
        table.insert(entry.todos, "apply:audio:" .. tech_type)
      elseif tech_type == "slow_motion" or tech_type == "speed_ramp" or 
             tech_type == "zoom" or tech_type == "crop_reframe" or 
             tech_type == "color_grade" or tech_type == "vignette" then
        has_visual_fx = true
        table.insert(visual_fx_types, tech_type)
        table.insert(entry.todos, "apply:visual:" .. tech_type .. " (v1 best-effort)")
      else
        table.insert(entry.todos, "apply:unknown:" .. tech_type)
      end
    end
    
    -- Adjust marker color for TODO-only markers
    if has_audio_only and not has_visual_fx then
      entry.color = "Purple"
      marker_name = "TODO AUDIO " .. marker_name
    elseif has_visual_fx and #entry.todos > 0 then
      -- Mix: note it's a complex edit
      table.insert(entry.actions, "marker:complex_edit_noted")
    end
    
    -- Add marker if API available and not dry-run
    if api_available and not dry_run and timeline then
      local marker_ok = add_marker(timeline, entry.start_f, entry.color, marker_name, marker_note, entry.duration_f)
      if marker_ok then
        table.insert(entry.actions, "marker:added")
        markers_added = markers_added + 1
        entry.status = "marker_added"
      else
        table.insert(entry.warnings, "Marker add failed (API may not support this)")
        entry.status = "marker_failed"
      end
    elseif dry_run then
      table.insert(entry.actions, "marker:dry_run_skipped")
      entry.status = "dry_run"
    else
      table.insert(entry.actions, "marker:api_unavailable_skipped")
      entry.status = "api_unavailable"
    end
    
    todos_logged = todos_logged + #entry.todos
    table.insert(run_log.edits, entry)
  end
  
  return markers_added, todos_logged
end

-- ============================================================================
-- MAIN
-- ============================================================================

local function main()
  local args = parse_args(arg)
  
  print("[INFO] resolve_apply_edits.lua v1.0")
  print("[INFO] JSON path: " .. args.json_path)
  print("[INFO] Dry run: " .. (args.dry_run and "yes" or "no"))
  
  -- Initialize run log
  local run_log = {
    timestamp = current_timestamp(),
    json_path = args.json_path,
    project_name = args.project_name,
    fps = FPS,
    dry_run = args.dry_run,
    color_preset = args.color_preset,
    vignette_preset = args.vignette_preset,
    edits = {},
    warnings = {},
  }
  
  -- Read JSON
  print("[INFO] Reading JSON file...")
  local json_content, read_err = read_file(args.json_path)
  if not json_content then
    print("[ERROR] Failed to read JSON: " .. read_err)
    run_log.error = "Failed to read JSON file: " .. read_err
    run_log.status = "read_error"
    write_file(dirname(args.json_path) .. "/" .. stem_name(args.json_path) .. "_resolve_apply_log.json", json.encode(run_log))
    os.exit(1)
  end
  
  print("[INFO] JSON size: " .. tostring(#json_content) .. " bytes")
  
  -- Parse JSON
  print("[INFO] Parsing JSON...")
  local data
  local parse_ok, parse_err = pcall(function()
    data = json.decode(json_content)
  end)
  
  if not parse_ok then
    print("[ERROR] JSON parse error: " .. parse_err)
    run_log.error = "JSON parse error: " .. parse_err
    run_log.status = "parse_error"
    write_file(dirname(args.json_path) .. "/" .. stem_name(args.json_path) .. "_resolve_apply_log.json", json.encode(run_log))
    os.exit(1)
  end
  
  if not data or type(data) ~= "table" then
    print("[ERROR] JSON is not an object")
    run_log.error = "JSON root is not an object"
    run_log.status = "parse_error"
    write_file(dirname(args.json_path) .. "/" .. stem_name(args.json_path) .. "_resolve_apply_log.json", json.encode(run_log))
    os.exit(1)
  end
  
  print("[INFO] JSON parsed successfully")
  
  -- Detect Resolve API
  print("[INFO] Detecting Resolve API...")
  local api_available, resolve, pm, capabilities = detect_resolve_api()
  run_log.api_available = api_available
  run_log.capabilities = capabilities
  
  if api_available then
    print("[INFO] Resolve API available; will attempt marker creation")
  else
    print("[WARN] Resolve API unavailable; proceeding in dry-run mode")
  end
  
  -- Normalize edits
  print("[INFO] Normalizing edits...")
  local edits = normalize_edits(data, run_log)
  print("[INFO] Found " .. tostring(#edits) .. " edit(s)")
  
  -- Determine project name
  local effective_project_name = args.project_name or data.project_name or stem_name(args.json_path) .. "_autoedit"
  run_log.effective_project_name = effective_project_name
  print("[INFO] Project name: " .. effective_project_name)
  
  -- Load/create project
  local project = nil
  local timeline = nil
  
  if api_available and pm and not args.dry_run then
    print("[INFO] Loading/creating project...")
    project = load_or_create_project(pm, effective_project_name, FPS, run_log)
    
    if project then
      print("[INFO] Creating/getting timeline...")
      timeline = ensure_timeline(project, "EG 30fps", FPS, run_log)
    end
    
    -- Try to import media
    local source_path = data.video and data.video.source_path
    if source_path and project then
      print("[INFO] Importing source media...")
      import_media(project, source_path, run_log)
    end
  else
    if args.dry_run then
      print("[INFO] Dry-run mode; skipping project/timeline/media operations")
    end
  end
  
  -- Process edits
  print("[INFO] Processing edits...")
  local markers_added, todos_logged = process_edits(timeline, edits, run_log, api_available, args.dry_run, args.color_preset, args.vignette_preset)
  
  -- Derive sidecar path
  local stem = stem_name(args.json_path)
  if stem:match("_editing_guide$") then
    stem = stem:gsub("_editing_guide$", "")
  end
  local sidecar_path = dirname(args.json_path) .. "/" .. stem .. "_resolve_apply_log.json"
  run_log.sidecar_path = sidecar_path
  
  -- Write run log
  print("[INFO] Writing run log...")
  local encode_ok, json_output = pcall(json.encode, run_log)
  if not encode_ok then
    print("[ERROR] Failed to encode run log JSON: " .. tostring(json_output))
    os.exit(1)
  end
  
  local write_ok, write_err = write_file(sidecar_path, json_output)
  if not write_ok then
    print("[ERROR] Failed to write run log: " .. write_err)
    os.exit(1)
  end
  
  print("[INFO] Run log written: " .. sidecar_path)
  print("[INFO] Summary: " .. tostring(#edits) .. " edits processed, " .. 
        tostring(markers_added) .. " marker(s) created, " .. 
        tostring(todos_logged) .. " TODO(s) logged")
  
  if api_available and not args.dry_run then
    print("[INFO] Complete. Check DaVinci Resolve for markers.")
  else
    print("[INFO] Complete. Review run log for details.")
  end
  
  os.exit(0)
end

-- Run main
main()
