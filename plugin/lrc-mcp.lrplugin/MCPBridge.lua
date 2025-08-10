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


local function readToken(log)
  -- Optionally read token from %APPDATA%/lrc-mcp/config.json (raw text token)
  local appData = os.getenv('APPDATA')
  if not appData then
    log:warn('APPDATA not set; plugin token unavailable')
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

    local payload = string.format('{"plugin_version":"%s","lr_version":"%s","catalog_path":%s,"timestamp":"%s"}',
      '0.1.0', LrApplication.versionString(), catPath and string.format('"%s"', catPath) or 'null', iso8601())

    if sendCount == 0 then
      local msg = 'Sending first heartbeat; lr_version=' .. LrApplication.versionString()
      Logger.debug(msg)
    end

    local ok, result, hdrs = pcall(function() return LrHttp.post( endpoint, payload, headers, 5 ) end)
    if not ok or not result then
      Logger.error('Heartbeat post failed')
    else
      if (sendCount % 12) == 0 then -- every ~60s at 5s interval
        Logger.debug('Heartbeat ok')
      end
    end
    sendCount = sendCount + 1
    LrTasks.sleep(5)
  end
end

return MCPBridge

