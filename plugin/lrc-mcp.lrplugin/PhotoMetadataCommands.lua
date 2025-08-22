local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
<<<<<<< HEAD
local LrProgressScope = import 'LrProgressScope'
local Logger = require 'Logger'
local Utils = require 'Utils'
local WriteLock = require 'WriteLock'

local PhotoMetadataCommands = {}

-- Utility: parse a JSON array of strings for a given key from a raw JSON string
local function parse_json_array_of_strings(json_str, key)
  local list = {}
  if type(json_str) ~= 'string' or not key then return list end
  local array_content = json_str:match('"' .. key .. '"%s*:%s*%[(.-)%]')
  if not array_content then return list end
  for v in array_content:gmatch('"(.-)"') do
    table.insert(list, v)
  end
  return list
end

local function extract_photo_ids(arg)
  if type(arg) == 'table' then
    return arg.photo_ids or {}
  elseif type(arg) == 'string' then
    local ids = parse_json_array_of_strings(arg, 'photo_ids')
    if #ids == 0 then
      -- Fallback single id under "photo_id"
      local single = Utils.extract_json_value(arg, 'photo_id')
      if single then table.insert(ids, single) end
    end
    return ids
  end
  return {}
end

local function extract_fields_list(arg)
  if type(arg) == 'table' then
    return arg.fields or {}
  elseif type(arg) == 'string' then
    return parse_json_array_of_strings(arg, 'fields')
  end
  return {}
end

local function build_placeholder_item(photo_id, fields)
  -- Placeholder structure for read operations; actual field mapping implemented in later stories
  return {
    photo_id = tostring(photo_id),
    fields = {}, -- deterministic placeholder
  }
end

-- READ: single get (no write access, no async required)
function PhotoMetadataCommands.get(payload_raw)
  Logger.info('photo_metadata.get start payload_raw: ' .. tostring(payload_raw))
  local photo_ids = extract_photo_ids(payload_raw)
  local fields = extract_fields_list(payload_raw)

  local items = {}
  for _, pid in ipairs(photo_ids) do
    table.insert(items, build_placeholder_item(pid, fields))
  end

  local result = { items = items, errors = {} }
  Logger.info('photo_metadata.get end count=' .. tostring(#items))
  return true, result, nil
end

-- READ: bulk_get (no write access, run in async task with progress + cancel support)
function PhotoMetadataCommands.bulk_get(payload_raw)
  Logger.info('photo_metadata.bulk_get start payload_raw: ' .. tostring(payload_raw))
  local photo_ids = extract_photo_ids(payload_raw)
  local fields = extract_fields_list(payload_raw)

  local items = {}
  local errors = {}
  local total = #photo_ids
  local completed = false

  LrTasks.startAsyncTask(function()
    local progress = LrProgressScope { title = 'Photo Metadata Bulk Get', caption = 'Initializing...' }
    for i, pid in ipairs(photo_ids) do
      if progress:isCanceled() then
        Logger.info('photo_metadata.bulk_get canceled at index ' .. tostring(i))
        break
      end
      table.insert(items, build_placeholder_item(pid, fields))
      progress:setPortionComplete(i, total)
      progress:setCaption(string.format('Reading %d/%d', i, total))
      LrTasks.sleep(0.001) -- yield
    end
    progress:done()
    completed = true
  end, 'Photo Metadata Bulk Get Task')

  -- Wait briefly for async to complete (bounded)
  local timeout = 5
  local elapsed = 0
  while not completed and elapsed < timeout do
    LrTasks.sleep(0.05)
    elapsed = elapsed + 0.05
  end

  local result = { items = items, errors = errors }
  Logger.info('photo_metadata.bulk_get end count=' .. tostring(#items))
  return true, result, nil
end

-- WRITE: update (must be fully wrapped in catalog:withWriteAccessDo)
function PhotoMetadataCommands.update(payload_raw)
  Logger.info('photo_metadata.update start payload_raw: ' .. tostring(payload_raw))
  local photo_ids = extract_photo_ids(payload_raw)

  local catalog = LrApplication.activeCatalog()
  if not catalog then
    Logger.error('photo_metadata.update: no active catalog')
    return false, nil, 'No active catalog found'
  end

  if not WriteLock.acquire_write_lock('Photo Metadata Update') then
    Logger.error('photo_metadata.update: failed to acquire write lock')
    return false, nil, 'Failed to acquire write lock for photo metadata update'
  end

  local updated = {}
  local errors = {}
  local write_scope_executed = false

  local status, err = catalog:withWriteAccessDo('Photo Metadata Update', function(context)
    write_scope_executed = true
    -- Placeholder no-op writes; actual field updates delivered by later stories
    for _, pid in ipairs(photo_ids) do
      table.insert(updated, tostring(pid))
    end
  end, { timeout = 10 })

  WriteLock.release_write_lock('Photo Metadata Update')

  if status ~= 'executed' then
    Logger.error('photo_metadata.update error: ' .. tostring(err))
    return false, nil, 'Photo metadata update failed: ' .. tostring(err)
  end

  local result = { updated = updated, errors = errors, debug_write_scope = write_scope_executed }
  Logger.info('photo_metadata.update end updated=' .. tostring(#updated))
  return true, result, nil
end

-- WRITE: bulk_update (async + progress + cancel + withWriteAccessDo)
function PhotoMetadataCommands.bulk_update(payload_raw)
  Logger.info('photo_metadata.bulk_update start payload_raw: ' .. tostring(payload_raw))
  local photo_ids = extract_photo_ids(payload_raw)

  local catalog = LrApplication.activeCatalog()
  if not catalog then
    Logger.error('photo_metadata.bulk_update: no active catalog')
    return false, nil, 'No active catalog found'
  end

  if not WriteLock.acquire_write_lock('Photo Metadata Bulk Update') then
    Logger.error('photo_metadata.bulk_update: failed to acquire write lock')
    return false, nil, 'Failed to acquire write lock for photo metadata bulk update'
  end

  local updated = {}
  local errors = {}
  local completed = false

  LrTasks.startAsyncTask(function()
    local progress = LrProgressScope { title = 'Photo Metadata Bulk Update', caption = 'Starting...' }
    local status, err = catalog:withWriteAccessDo('Photo Metadata Bulk Update', function(context)
      for i, pid in ipairs(photo_ids) do
        if progress:isCanceled() then
          Logger.info('photo_metadata.bulk_update canceled at index ' .. tostring(i))
          break
        end
        -- Placeholder no-op update
        table.insert(updated, tostring(pid))
        progress:setPortionComplete(i, #photo_ids)
        progress:setCaption(string.format('Updating %d/%d', i, #photo_ids))
        LrTasks.sleep(0.001) -- yield
      end
    end, { timeout = 15 })

    if status ~= 'executed' then
      table.insert(errors, { message = tostring(err) })
      Logger.error('photo_metadata.bulk_update write scope failed: ' .. tostring(err))
    end

    progress:done()
    completed = true
    WriteLock.release_write_lock('Photo Metadata Bulk Update')
  end, 'Photo Metadata Bulk Update Task')

  -- Wait for completion (bounded)
  local timeout = 10
  local elapsed = 0
  while not completed and elapsed < timeout do
=======
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
>>>>>>> main
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end

<<<<<<< HEAD
  if not completed then
    Logger.error('photo_metadata.bulk_update timed out after ' .. tostring(timeout) .. ' seconds')
    return false, nil, 'Photo metadata bulk update timed out after ' .. tostring(timeout) .. ' seconds'
  end

  local result = { updated = updated, errors = errors, debug_async = true }
  Logger.info('photo_metadata.bulk_update end updated=' .. tostring(#updated))
  return true, result, nil
=======
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
>>>>>>> main
end

return PhotoMetadataCommands
