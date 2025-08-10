local LrApplication = import 'LrApplication'
local LrHttp = import 'LrHttp'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrDate = import 'LrDate'
local Logger = require 'Logger'

local MCPBridge = {}

local function iso8601()
  return LrDate.timeToW3CDate( LrDate.currentTime() )
end

local function json_escape(str)
  if str == nil then return nil end
  -- Escape backslash and double quote first
  str = str:gsub('\\', '\\\\')
  str = str:gsub('"', '\\"')
  -- Escape control characters
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

local function json_string(s)
  if s == nil then return 'null' end
  return '"' .. json_escape(s) .. '"'
end


local function readToken(log)
  -- Optionally read token from %APPDATA%/lrc-mcp/config.json (raw text token)
  -- Lightroom's Lua sandbox does not expose os.getenv; use LrPathUtils instead
  local appData = LrPathUtils.getStandardFilePath('appData')
  if not appData then
    log:warn('appData path unavailable; plugin token unavailable')
    return nil
  end
  local configPath = LrPathUtils.child(appData, 'lrc-mcp/config.json')
  local f = io.open(configPath, 'r')
  if not f then
    log:trace('No token file at ' .. configPath)
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

function MCPBridge.start()
  Logger.info('MCPBridge.start: initializing heartbeat loop')

  local token = readToken({ warn = function(_, m) Logger.warn(m) end, trace = function(_, m) Logger.debug(m) end })
  local headers = { ['Content-Type'] = 'application/json' }
  if token then
    headers['X-Plugin-Token'] = token
    Logger.debug('Token present (length=' .. tostring(#token) .. ')')
  else
    Logger.debug('Token not present; proceeding without auth header')
  end
  local endpoint = 'http://127.0.0.1:8765/plugin/heartbeat'
  Logger.debug('Heartbeat endpoint: ' .. endpoint)

  local sendCount = 0
  while true do
    local cat = LrApplication.activeCatalog()
    local catPath = nil
    if cat and cat.getPath then
      local ok, val = pcall(function() return cat:getPath() end)
      if ok then catPath = val end
    end

    local payload = string.format('{"plugin_version":%s,"lr_version":%s,"catalog_path":%s,"timestamp":%s}',
      json_string('0.1.0'), json_string(LrApplication.versionString()), catPath and json_string(catPath) or 'null', json_string(iso8601()))

    if sendCount == 0 then
      local msg = 'Sending first heartbeat; lr_version=' .. LrApplication.versionString()
      Logger.info(msg)
    end

    local result, hdrs = LrHttp.post( endpoint, payload, headers, 5 )
    local statusCode = nil
    if hdrs then
      statusCode = tonumber(hdrs.status) or tonumber(hdrs.statusCode) or tonumber(hdrs.code)
    end
    if not result or not statusCode or statusCode < 200 or statusCode >= 300 then
      local bodySnippet = ''
      if type(result) == 'string' and #result > 0 then
        local max = 200
        bodySnippet = ' body=' .. string.sub(result, 1, max)
      end
      Logger.error('Heartbeat post failed' .. (statusCode and (' (status=' .. tostring(statusCode) .. ')') or '') .. bodySnippet)
    else
      Logger.info('Heartbeat ok (status=' .. tostring(statusCode) .. ')')
    end
    sendCount = sendCount + 1
    LrTasks.sleep(5)
  end
end

return MCPBridge

