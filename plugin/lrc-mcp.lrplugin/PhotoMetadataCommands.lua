local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrDate = import 'LrDate'
local Logger = require 'Logger'
local Utils = require 'Utils'

-- Photo metadata read-only commands (E9-S1)
-- References:
-- - Lightroom SDK local docs: .resources/LrC (LrApplication, LrPhoto:getRawMetadata/getFormattedMetadata, catalog access rules)
-- - MCP local docs: .resources/MCP-docs (deterministic schemas and tool behavior)
--
-- Notes:
-- - Read-only paths avoid catalog:withWriteAccessDo, per SDK guidance.
-- - Best-effort parsing of JSON payloads is used (consistent with existing modules).
-- - Deterministic result keys are returned; nulls when unavailable.

local PhotoMetadataCommands = {}

local ALL_FIELDS = {
  "title", "caption", "keywords", "rating", "color_label", "flag", "gps", "capture_time"
}

local function contains(tbl, s)
  if type(tbl) ~= 'table' then return false end
  for _, v in ipairs(tbl) do
    if v == s then return true end
  end
  return false
end

local function parse_fields(json_str)
  -- Extract fields array (["f1","f2",...]); fall back to ALL_FIELDS if missing
  if not json_str or type(json_str) ~= 'string' then return ALL_FIELDS end
  local arr = json_str:match('"%s*fields%s*"%s*:%s*%[(.-)%]')
  if not arr then return ALL_FIELDS end
  local fields = {}
  for s in arr:gmatch('"(.-)"') do
    table.insert(fields, s)
  end
  if #fields == 0 then
    return ALL_FIELDS
  end
  return fields
end

local function parse_get_args(payload_raw)
  -- Expected shape: {"photo":{"local_id":"...","file_path":"..."},"fields":[...]}
  local local_id = nil
  local file_path = nil
  if payload_raw and type(payload_raw) == 'string' then
    -- Try to extract from nested "photo" object with simple patterns
    -- Prefer local_id over file_path
    local photo_block_start = payload_raw:find('"%s*photo%s*"%s*:%s*[{%[]')
    if photo_block_start then
      -- Extract local_id and file_path anywhere after photo key
      local_id = payload_raw:match('"local_id"%s*:%s*"([^"]*)"')
      file_path = payload_raw:match('"file_path"%s*:%s*"([^"]*)"')
    else
      -- Fallback to flat extraction
      local_id = Utils.extract_json_value(payload_raw, "local_id")
      file_path = Utils.extract_json_value(payload_raw, "file_path")
    end
  end
  local fields = parse_fields(payload_raw)
  return {
    photo = { local_id = local_id, file_path = file_path },
    fields = fields
  }
end

local function parse_bulk_args(payload_raw)
  -- Expected shape: {"photos":[{"local_id":"..."},{"file_path":"..."}], "fields":[...]}
  local fields = parse_fields(payload_raw)
  local photos = {}

  if payload_raw and type(payload_raw) == 'string' then
    -- Extract the photos array content
    local start_idx = payload_raw:find('"%s*photos%s*"%s*:%s*%[')
    if start_idx then
      local i = start_idx
      -- Find matching closing bracket for the photos array using a simple stack
      local depth = 0
      local in_string = false
      local escape_next = false
      local content_start = nil
      for pos = start_idx, #payload_raw do
        local ch = payload_raw:sub(pos, pos)
        if not escape_next then
          if ch == '"' then
            in_string = not in_string
          elseif not in_string then
            if ch == '[' then
              depth = depth + 1
              if depth == 1 and not content_start then
                content_start = pos + 1
              end
            elseif ch == ']' then
              depth = depth - 1
              if depth == 0 and content_start then
                local photos_content = payload_raw:sub(content_start, pos - 1)
                -- Parse each object within (best-effort)
                for obj in photos_content:gmatch('{(.-)}') do
                  local lid = obj:match('"local_id"%s*:%s*"([^"]*)"')
                  local fpath = obj:match('"file_path"%s*:%s*"([^"]*)"')
                  table.insert(photos, { local_id = lid, file_path = fpath })
                end
                break
              end
            end
          end
        end
        escape_next = (ch == '\\' and not escape_next)
      end
    end
  end

  if #photos == 0 then
    -- Fallback: attempt a single photo parse (if caller mistakenly used get shape)
    local single = parse_get_args(payload_raw)
    if single and single.photo and (single.photo.local_id or single.photo.file_path) then
      photos = { { local_id = single.photo.local_id, file_path = single.photo.file_path } }
    end
  end

  return { photos = photos, fields = fields }
end

local function find_photo_by_local_id(catalog, local_id)
  if not catalog or not local_id or local_id == '' then return nil end
  local ok, photo = pcall(function()
    -- Not all SDK versions expose this; guard with pcall
    if catalog.photoByLocalIdentifier then
      return catalog:photoByLocalIdentifier(local_id)
    end
    return nil
  end)
  if ok then return photo end
  return nil
end

local function find_photo_by_path(catalog, file_path)
  if not catalog or not file_path or file_path == '' then return nil end
  local ok, photo = pcall(function()
    if catalog.findPhotoByPath then
      return catalog:findPhotoByPath(file_path)
    end
    return nil
  end)
  if ok then return photo end
  return nil
end

local function resolve_photo(catalog, local_id, file_path)
  if local_id and local_id ~= '' then
    local p = find_photo_by_local_id(catalog, local_id)
    if p then return p end
  end
  if file_path and file_path ~= '' then
    local p = find_photo_by_path(catalog, file_path)
    if p then return p end
  end
  return nil
end

local function read_metadata_for_fields(photo, fields)
  -- Deterministic result object; keep all keys in a fixed set
  local res = {
    title = nil,
    caption = nil,
    keywords = nil,
    rating = nil,
    color_label = nil,
    flag = nil,
    gps = nil,
    capture_time = nil
  }

  if not photo then
    return res
  end

  local function want(name) return contains(fields, name) end

  -- title
  if want("title") then
    local ok, v = pcall(function() return photo:getFormattedMetadata("title") end)
    res.title = (ok and v and v ~= "") and v or nil
  end

  -- caption
  if want("caption") then
    local ok, v = pcall(function() return photo:getFormattedMetadata("caption") end)
    res.caption = (ok and v and v ~= "") and v or nil
  end

  -- keywords
  if want("keywords") then
    local names = {}
    local ok, kws = pcall(function() return photo:getRawMetadata("keywords") end)
    if ok and type(kws) == 'table' then
      for _, kw in ipairs(kws) do
        local okn, nm = pcall(function()
          if kw and kw.getName then return kw:getName() end
          return nil
        end)
        if okn and nm and nm ~= "" then
          table.insert(names, nm)
        end
      end
    end
    -- Deduplicate + sort for determinism
    if #names > 0 then
      local seen = {}
      local unique = {}
      for _, n in ipairs(names) do
        if not seen[n] then
          seen[n] = true
          table.insert(unique, n)
        end
      end
      table.sort(unique)
      res.keywords = unique
    else
      res.keywords = {}
    end
  end

  -- rating (0..5)
  if want("rating") then
    local ok, v = pcall(function() return photo:getRawMetadata("rating") end)
    if ok and type(v) == 'number' then
      res.rating = v
    else
      res.rating = nil
    end
  end

  -- color_label (none, red, yellow, green, blue, purple)
  if want("color_label") then
    local ok, v = pcall(function() return photo:getRawMetadata("colorNameForLabel") end)
    if ok and v and v ~= "" then
      -- Lightroom returns localized names sometimes; pass through raw name for now
      res.color_label = v
    else
      res.color_label = nil
    end
  end

  -- flag (picked, rejected, none)
  if want("flag") then
    local state = "none"
    local okPick, pick = pcall(function() return photo:getRawMetadata("pickStatus") end)
    local okFlag, isFlagged = pcall(function() return photo:getRawMetadata("isFlagged") end)
    local okRej, rejected = pcall(function() return photo:getRawMetadata("rejectStatus") end)
    if okRej and (rejected == true) then
      state = "rejected"
    elseif (okPick and type(pick) == 'number' and pick == 1) or (okFlag and isFlagged == true) then
      state = "picked"
    else
      state = "none"
    end
    res.flag = state
  end

  -- gps { lat, lon, alt }
  if want("gps") then
    local lat, lon, alt = nil, nil, nil
    local okGpsTbl, gpsTbl = pcall(function() return photo:getRawMetadata("gps") end)
    if okGpsTbl and type(gpsTbl) == 'table' then
      lat = gpsTbl.latitude or gpsTbl.lat or gpsTbl[1]
      lon = gpsTbl.longitude or gpsTbl.lon or gpsTbl[2]
      alt = gpsTbl.altitude or gpsTbl.alt or gpsTbl[3]
    else
      local okLat, vLat = pcall(function() return photo:getRawMetadata("gpsLatitude") end)
      local okLon, vLon = pcall(function() return photo:getRawMetadata("gpsLongitude") end)
      local okAlt, vAlt = pcall(function() return photo:getRawMetadata("gpsAltitude") end)
      if okLat then lat = vLat end
      if okLon then lon = vLon end
      if okAlt then alt = vAlt end
    end
    if lat ~= nil or lon ~= nil or alt ~= nil then
      res.gps = { lat = lat, lon = lon, alt = alt }
    else
      res.gps = nil
    end
  end

  -- capture_time (ISO 8601)
  if want("capture_time") then
    local iso = nil
    local okNum, ts = pcall(function() return photo:getRawMetadata("dateTimeOriginal") end)
    if okNum and ts then
      if type(ts) == 'number' then
        iso = LrDate.timeToW3CDate(ts)
      elseif type(ts) == 'string' then
        -- Assume already formatted; pass through
        iso = ts
      end
    else
      -- Fallback: some catalogs expose "time" or "captureTime"
      local okT, t2 = pcall(function() return photo:getRawMetadata("time") end)
      if okT and type(t2) == 'number' then
        iso = LrDate.timeToW3CDate(t2)
      end
    end
    res.capture_time = iso
  end

  return res
end

function PhotoMetadataCommands.handle_photo_get_command(payload_raw)
  Logger.info('handle_photo_get_command payload_raw: ' .. tostring(payload_raw))

  local args = parse_get_args(payload_raw)
  local requested_fields = args.fields or ALL_FIELDS
  local in_local_id = args.photo and args.photo.local_id or nil
  local in_file_path = args.photo and args.photo.file_path or nil

  local LrTasks = import 'LrTasks'

  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false

  LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      return
    end

    local photo = resolve_photo(catalog, in_local_id, in_file_path)

    if not photo then
      result = {
        photo = { local_id = in_local_id, file_path = in_file_path },
        result = nil,
        error = { code = 'PHOTO_NOT_FOUND', message = 'Photo not found' }
      }
      task_success = true
      task_completed = true
      return
    end

    local res = read_metadata_for_fields(photo, requested_fields)
    -- Ensure deterministic keys
    result = {
      photo = { local_id = in_local_id, file_path = in_file_path },
      result = res,
      error = nil
    }
    task_success = true
    task_completed = true
  end, 'Get Photo Metadata Task')

  local timeout = 10
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end

  if not task_completed then
    return false, nil, 'Photo metadata get timed out after ' .. timeout .. ' seconds'
  end

  if task_success and result then
    return true, result, nil
  else
    return false, nil, error_msg or 'Failed to read photo metadata'
  end
end

function PhotoMetadataCommands.handle_photo_bulk_get_command(payload_raw)
  Logger.info('handle_photo_bulk_get_command payload_raw: ' .. tostring(payload_raw))

  local args = parse_bulk_args(payload_raw)
  local requested_fields = args.fields or ALL_FIELDS
  local photos_in = args.photos or {}

  local LrTasks = import 'LrTasks'

  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false

  LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      return
    end

    local items = {}
    local errors_aggregated = {}
    local succeeded = 0
    local failed = 0

    local start_ms = LrDate.currentTime() * 1000

    for idx, p in ipairs(photos_in) do
      local lid = p.local_id
      local fpath = p.file_path

      local photo = resolve_photo(catalog, lid, fpath)
      if not photo then
        table.insert(items, {
          photo = { local_id = lid, file_path = fpath },
          result = nil,
          error = { code = 'PHOTO_NOT_FOUND', message = 'Photo not found' }
        })
        table.insert(errors_aggregated, { index = idx, code = 'PHOTO_NOT_FOUND', message = 'Photo not found' })
        failed = failed + 1
      else
        local res = read_metadata_for_fields(photo, requested_fields)
        table.insert(items, {
          photo = { local_id = lid, file_path = fpath },
          result = res,
          error = nil
        })
        succeeded = succeeded + 1
      end

      -- Yield periodically for UI responsiveness
      if (idx % 50) == 0 then
        LrTasks.sleep(0.0)
      end
    end

    local duration_ms = math.floor((LrDate.currentTime() * 1000) - start_ms)
    result = {
      items = items,
      errors_aggregated = errors_aggregated,
      stats = { requested = #photos_in, succeeded = succeeded, failed = failed, duration_ms = duration_ms }
    }
    task_success = true
    task_completed = true
  end, 'Bulk Get Photo Metadata Task')

  local timeout = 10
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end

  if not task_completed then
    return false, nil, 'Photo metadata bulk_get timed out after ' .. timeout .. ' seconds'
  end

  if task_success and result then
    return true, result, nil
  else
    return false, nil, error_msg or 'Failed to bulk read photo metadata'
  end
end

return PhotoMetadataCommands
