local LrPathUtils = import 'LrPathUtils'
local LrDate = import 'LrDate'
local Logger = require 'Logger'

local Utils = {}

-- Common utilities
function Utils.iso8601()
  return LrDate.timeToW3CDate(LrDate.currentTime())
end

function Utils.json_escape(str)
  if str == nil then return nil end
  -- First escape the backslash itself to avoid double escaping
  str = str:gsub('\\', '\\\\')
  -- Then escape the double quote
  str = str:gsub('"', '\\"')
  -- Escape common control characters with short escapes
  str = str:gsub('\b', '\\b')
  str = str:gsub('\f', '\\f')
  str = str:gsub('\n', '\\n')
  str = str:gsub('\r', '\\r')
  str = str:gsub('\t', '\\t')
  -- Escape any remaining control chars < 0x20 as \u00XX
  str = str:gsub('[%z\1-\31]', function(c)
    return string.format('\\u%04X', string.byte(c))
  end)
  return str
end

function Utils.json_string(s)
  if s == nil then return 'null' end
  return '\"' .. Utils.json_escape(s) .. '\"'
end

function Utils.readToken(log)
  -- Optionally read token from %APPDATA%/lrc-mcp/config.json (raw text token)
  local appData = LrPathUtils.getStandardFilePath('appData')
  if not appData then
    if log and log.warn then log:warn('appData path unavailable; plugin token unavailable') end
    return nil
  end
  local configPath = LrPathUtils.child(appData, 'lrc-mcp/config.json')
  local f = io.open(configPath, 'r')
  if not f then
    if log and log.trace then log:trace('No token file at ' .. configPath) end
    return nil
  end
  local content = f:read('*a')
  f:close()
  if not content then return nil end
  -- trim whitespace
  content = content:gsub('^%s+', ''):gsub('%s+$', '')
  if content == '' then return nil end
  return content
end

-- Build headers (Content-Type and optional X-Plugin-Token)
function Utils.build_headers()
  local token = Utils.readToken({ warn = function(_, m) Logger.warn(m) end, trace = function(_, m) Logger.debug(m) end })
  local headers = { ['Content-Type'] = 'application/json' }
  if token then
    headers['X-Plugin-Token'] = token
  end
  return headers
end

-- JSON value extraction utility
function Utils.extract_json_value(json_str, key)
  if not json_str or not key then 
    Logger.info('extract_json_value: nil input for key: ' .. tostring(key))
    return nil 
  end
  
  Logger.info('extract_json_value: parsing key "' .. key .. '" from json_str: ' .. json_str)
  
  -- Handle null values first
  if json_str:match('"' .. key .. '"%s*:%s*null') then
    Logger.info('extract_json_value: found null for key "' .. key .. '"')
    return nil
  end
  
  -- Handle string values: "key":"value" - simpler pattern for basic strings
  local pattern = '"' .. key .. '"%s*:%s*"([^"]*)"'
  local match = json_str:match(pattern)
  if match then
    Logger.info('extract_json_value: found string match for key "' .. key .. '": ' .. match)
    -- Unescape the matched string
    match = match:gsub('\\"', '"'):gsub('\\\\', '\\')
    Logger.info('extract_json_value: unescaped match: ' .. match)
    return match
  end
  
  -- Handle boolean values
  local bool_true = json_str:match('"' .. key .. '"%s*:%s*true')
  if bool_true then
    Logger.info('extract_json_value: found true for key "' .. key .. '"')
    return true
  end
  local bool_false = json_str:match('"' .. key .. '"%s*:%s*false')
  if bool_false then
    Logger.info('extract_json_value: found false for key "' .. key .. '"')
    return false
  end

  -- Handle numeric values (integers/floats)
  local num_match = json_str:match('"' .. key .. '"%s*:%s*(-?%d+%.?%d*)')
  if num_match then
    Logger.info('extract_json_value: found number match for key "' .. key .. '": ' .. num_match)
    -- Return as string to keep downstream comparisons simple (tostring on IDs)
    return num_match
  end
  
  Logger.info('extract_json_value: no match found for key "' .. key .. '"')
  return nil
end

-- Determine if a Lua table is an array (1..n contiguous integer keys)
function Utils.is_array(tbl)
  if type(tbl) ~= 'table' then return false end
  local max_index = 0
  local count = 0
  for k, _ in pairs(tbl) do
    if type(k) ~= 'number' then
      return false
    end
    if k > max_index then max_index = k end
    count = count + 1
  end
  return max_index == count
end

-- JSON encoder that supports nested tables (arrays/objects), numbers, booleans, strings, and nil
function Utils.json_encode(value)
  local t = type(value)
  if t == 'nil' then
    return 'null'
  elseif t == 'boolean' then
    return value and 'true' or 'false'
  elseif t == 'number' then
    return tostring(value)
  elseif t == 'string' then
    return Utils.json_string(value)
  elseif t == 'table' then
    if Utils.is_array(value) then
      local parts = {}
      for i = 1, #value do
        table.insert(parts, Utils.json_encode(value[i]))
      end
      return '[' .. table.concat(parts, ',') .. ']'
    else
      local parts = {}
      for k, v in pairs(value) do
        local key = Utils.json_string(tostring(k))
        table.insert(parts, key .. ':' .. Utils.json_encode(v))
      end
      return '{' .. table.concat(parts, ',') .. '}'
    end
  else
    -- Fallback: stringify and quote
    return Utils.json_string(tostring(value))
  end
end

return Utils
