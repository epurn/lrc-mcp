local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
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
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end

  if not completed then
    Logger.error('photo_metadata.bulk_update timed out after ' .. tostring(timeout) .. ' seconds')
    return false, nil, 'Photo metadata bulk update timed out after ' .. tostring(timeout) .. ' seconds'
  end

  local result = { updated = updated, errors = errors, debug_async = true }
  Logger.info('photo_metadata.bulk_update end updated=' .. tostring(#updated))
  return true, result, nil
end

return PhotoMetadataCommands
