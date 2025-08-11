local LrApplication = import 'LrApplication'
local LrHttp = import 'LrHttp'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrDate = import 'LrDate'
local Logger = require 'Logger'

local MCPBridge = {}

-- -----------------
-- Common utilities
-- -----------------
local function iso8601()
  return LrDate.timeToW3CDate( LrDate.currentTime() )
end

local function json_escape(str)
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

local function json_string(s)
  if s == nil then return 'null' end
  return '\"' .. json_escape(s) .. '\"'
end

local function readToken(log)
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
local function build_headers()
  local token = readToken({ warn = function(_, m) Logger.warn(m) end, trace = function(_, m) Logger.debug(m) end })
  local headers = { ['Content-Type'] = 'application/json' }
  if token then
    headers['X-Plugin-Token'] = token
  end
  return headers
end

-- -----------------
-- Heartbeat (Step 3)
-- -----------------
-- (Implementation moved to MCPBridge.start for direct async task context)

local LrFunctionContext = import 'LrFunctionContext'

function MCPBridge.start()
  Logger.info('MCPBridge.start: initializing heartbeat + command loops')

  -- Start command loop in background
  LrTasks.startAsyncTask(function()
    local claim_url = 'http://127.0.0.1:8765/plugin/commands/claim'
    local function result_url(id)
      return 'http://127.0.0.1:8765/plugin/commands/' .. tostring(id) .. '/result'
    end

    while true do
      -- Claim at most one command
      local claim_body = '{\"worker\":\"lrc-plugin\",\"max\":1}'
      local respBody, respHdrs = LrHttp.post(claim_url, claim_body, build_headers(), 5)
      local statusCode = nil
      if respHdrs then
        statusCode = tonumber(respHdrs.status) or tonumber(respHdrs.statusCode) or tonumber(respHdrs.code)
      end
      statusCode = statusCode or 0

      if statusCode == 204 then
        -- No work
        LrTasks.sleep(1.5)
      elseif statusCode >= 200 and statusCode < 300 then
        local body = respBody or ''
        local cmd = nil
        if type(body) == 'string' and #body > 0 then
          -- Parse command from body
          local id = body:match('\"id\"%s*:%s*\"([^\"]+)\"')
          local ctype = body:match('\"type\"%s*:%s*\"([^\"]+)\"')
          local payloadStr = body:match('\"payload\"%s*:%s*({.-})')
          if id and ctype then
            cmd = { id = id, type = ctype, payload_raw = payloadStr }
          end
        end
        if not cmd then
          -- No commands in body
          LrTasks.sleep(1.0)
        else
          local cmdOk, resultTable, errMsg = nil, nil, nil
          if cmd.type == 'noop' then
            cmdOk, resultTable, errMsg = true, { ok = true }, nil
          elseif cmd.type == 'echo' then
            local msg = nil
            if cmd.payload_raw and type(cmd.payload_raw) == 'string' then
              msg = cmd.payload_raw:match('\"message\"%s*:%s*\"([^\"]*)\"')
            end
            cmdOk, resultTable, errMsg = true, { echo = msg or '' }, nil
          else
            cmdOk, resultTable, errMsg = false, nil, 'unknown command type: ' .. tostring(cmd.type)
          end
          
          local resultJson = 'null'
          if cmdOk and resultTable then
            local parts = {}
            for k, v in pairs(resultTable) do
              local val
              if type(v) == 'string' then
                val = json_string(v)
              elseif type(v) == 'number' then
                val = tostring(v)
              elseif type(v) == 'boolean' then
                val = v and 'true' or 'false'
              elseif v == nil then
                val = 'null'
              else
                val = json_string(tostring(v))
              end
              table.insert(parts, '\"' .. tostring(k) .. '\"' .. ':' .. val)
            end
            resultJson = '{' .. table.concat(parts, ',') .. '}'
          end
          
          local payload = string.format('{\"ok\":%s,\"result\":%s,\"error\":%s}', cmdOk and 'true' or 'false', resultJson, errMsg and json_string(errMsg) or 'null')
          local resultRespBody, resultRespHdrs = LrHttp.post(result_url(cmd.id), payload, build_headers(), 5)
          local resultStatusCode = nil
          if resultRespHdrs then
            resultStatusCode = tonumber(resultRespHdrs.status) or tonumber(resultRespHdrs.statusCode) or tonumber(resultRespHdrs.code)
          end
          resultStatusCode = resultStatusCode or 0
          
          if resultStatusCode < 200 or resultStatusCode >= 300 then
            Logger.error('Result post failed for command ' .. tostring(cmd.id) .. ' status=' .. tostring(resultStatusCode))
          else
            Logger.info('Command ' .. tostring(cmd.id) .. ' completed ok=' .. tostring(cmdOk))
          end
          -- Immediately try to claim next (if any)
        end
      else
        Logger.error('Claim request failed (status=' .. tostring(statusCode) .. ')')
        Logger.error('Body: ' .. tostring(respBody))
        LrTasks.sleep(15.0)
      end
    end
  end, 'MCP Command Loop')

  -- Start heartbeat loop in background
  LrTasks.startAsyncTask(function()
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

      local payload = string.format('{\"plugin_version\":%s,\"lr_version\":%s,\"catalog_path\":%s,\"timestamp\":%s}',
        json_string('0.1.0'), json_string(LrApplication.versionString()), catPath and json_string(catPath) or 'null', json_string(iso8601()))

      if sendCount == 0 then
        Logger.info('Sending first heartbeat; lr_version=' .. LrApplication.versionString())
      end

      local respBody, respHdrs = LrHttp.post(endpoint, payload, build_headers(), 5)
      local statusCode = nil
      if respHdrs then
        statusCode = tonumber(respHdrs.status) or tonumber(respHdrs.statusCode) or tonumber(respHdrs.code)
      end
      statusCode = statusCode or 0
      
      if statusCode < 200 or statusCode >= 300 then
        Logger.error('Heartbeat post failed (status=' .. tostring(statusCode) .. ')')
      elseif sendCount == 0 then
        Logger.info('Heartbeat ok (status=' .. tostring(statusCode) .. ')')
      end

      sendCount = sendCount + 1
      LrTasks.sleep(5)  -- Sleep for 5 seconds
    end
  end, 'MCP Heartbeat Loop')
end

return MCPBridge
