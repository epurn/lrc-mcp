local LrApplication = import 'LrApplication'
local LrHttp = import 'LrHttp'
local LrTasks = import 'LrTasks'
local Logger = require 'Logger'
local Utils = require 'Utils'
local CommandHandlers = require 'CommandHandlers'

local MCPBridge = {}

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
      local claim_body = '{"worker":"lrc-plugin","max":1}'
      local respBody, respHdrs = LrHttp.post(claim_url, claim_body, Utils.build_headers(), 5)
      local statusCode = nil
      if respHdrs then
        statusCode = tonumber(respHdrs.status) or tonumber(respHdrs.statusCode) or tonumber(respHdrs.code)
      end
      statusCode = statusCode or 0

      if statusCode == 204 then
        -- No work
        LrTasks.sleep(0.5)
      elseif statusCode >= 200 and statusCode < 300 then
        local body = respBody or ''
        local cmd = nil
        if type(body) == 'string' and #body > 0 then
          -- Parse command from body
          Logger.info('Parsing command from body: ' .. tostring(body))
          local id = body:match('"id"%s*:%s*"([^"]*)"')
          local ctype = body:match('"type"%s*:%s*"([^"]*)"')
          -- Fix payload extraction - handle the full JSON object properly
          local payloadStr = body:match('"payload"%s*:%s*(%b{})')
          if not payloadStr then
            -- Try alternative pattern for payload extraction
            payloadStr = body:match('"payload"%s*:%s*({.*})')
          end
          Logger.info('Parsed command - id: ' .. tostring(id) .. ', type: ' .. tostring(ctype) .. ', payloadStr: ' .. tostring(payloadStr))
          if id and ctype then
            cmd = { id = id, type = ctype, payload_raw = payloadStr }
          end
        end
        if not cmd then
          -- No commands in body
          LrTasks.sleep(0.5)
        else
          local cmdOk, resultTable, errMsg = nil, nil, nil
          if cmd.type == 'noop' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_noop_command()
          elseif cmd.type == 'echo' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_echo_command(cmd.payload_raw)
          elseif cmd.type == 'collection.create' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_create_collection_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.create' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_create_collection_set_command(cmd.payload_raw)
          elseif cmd.type == 'collection.list' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_list_collections_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.list' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_list_collection_sets_command(cmd.payload_raw)
          elseif cmd.type == 'collection.remove' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_remove_collection_command(cmd.payload_raw)
          elseif cmd.type == 'collection.edit' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_edit_collection_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.edit' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_edit_collection_set_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.remove' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_remove_collection_set_command(cmd.payload_raw)
          elseif cmd.type == 'run_tests' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_run_tests_command()
          else
            cmdOk, resultTable, errMsg = false, nil, 'unknown command type: ' .. tostring(cmd.type)
          end
          
          local resultJson = 'null'
          if cmdOk and resultTable then
            resultJson = Utils.json_encode(resultTable)
          end
          
          local payload = string.format('{"ok":%s,"result":%s,"error":%s}', cmdOk and 'true' or 'false', resultJson, errMsg and Utils.json_string(errMsg) or 'null')
          local resultRespBody, resultRespHdrs = LrHttp.post(result_url(cmd.id), payload, Utils.build_headers(), 5)
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
          -- Add a small delay between commands to prevent write access conflicts
          LrTasks.sleep(0.1)
        end
      else
        Logger.error('Claim request failed (status=' .. tostring(statusCode) .. ')')
        Logger.error('Body: ' .. tostring(respBody))
        LrTasks.sleep(2.0)
      end
    end
  end, 'MCP Command Loop')

  -- Start heartbeat loop in background
  LrTasks.startAsyncTask(function()
    local endpoint = 'http://127.0.0.1:8765/plugin/heartbeat'
    Logger.info('Heartbeat endpoint: ' .. endpoint)

    local sendCount = 0
    while true do
      local cat = LrApplication.activeCatalog()
      local catPath = nil
      if cat and cat.getPath then
        local ok, val = pcall(function() return cat:getPath() end)
        if ok then catPath = val end
      end

      local payload = string.format('{"plugin_version":%s,"lr_version":%s,"catalog_path":%s,"timestamp":%s}',
        Utils.json_string('0.1.0'), Utils.json_string(LrApplication.versionString()), catPath and Utils.json_string(catPath) or 'null', Utils.json_string(Utils.iso8601()))

      if sendCount == 0 then
        Logger.info('Sending first heartbeat; lr_version=' .. LrApplication.versionString())
      end

      local respBody, respHdrs = LrHttp.post(endpoint, payload, Utils.build_headers(), 5)
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
