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
            -- Extract payload as JSON object and convert to string
            local payload_start, payload_end = body:find('"payload"%s*:%s*')
            if payload_start and payload_end then
              -- Find the start of the payload (after the colon and whitespace)
              local payload_content_start = payload_end + 1
              local payload_str = nil
              
              -- Check if payload starts with { (object) or [ (array)
              local first_char = body:sub(payload_content_start, payload_content_start)
              if first_char == '{' or first_char == '[' then
                -- Parse JSON object/array by finding matching closing bracket
                local bracket_stack = 0
                local in_string = false
                local escape_next = false
                local start_pos = payload_content_start
                
                for i = payload_content_start, #body do
                  local char = body:sub(i, i)
                  if not escape_next then
                    if char == '"' then
                      in_string = not in_string
                    elseif not in_string then
                      if char == '{' or char == '[' then
                        bracket_stack = bracket_stack + 1
                      elseif char == '}' or char == ']' then
                        bracket_stack = bracket_stack - 1
                        if bracket_stack <= 0 then
                          payload_str = body:sub(start_pos, i)
                          break
                        end
                      end
                    end
                  end
                  escape_next = (char == '\\' and not escape_next)
                end
              else
                -- Handle simple values (null, string, number, boolean)
                local remaining = body:sub(payload_content_start)
                local simple_end = remaining:find('[,}]')
                if simple_end then
                  payload_str = remaining:sub(1, simple_end - 1)
                else
                  payload_str = remaining
                end
              end
              
              Logger.info('Parsed command - id: ' .. tostring(id) .. ', type: ' .. tostring(ctype) .. ', payload_str: ' .. tostring(payload_str))
              if id and ctype then
                cmd = { id = id, type = ctype, payload_raw = payload_str }
              end
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
          elseif cmd.type == 'run_tests' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_run_tests_command()
          -- Action-specific collection commands
          elseif cmd.type == 'collection.list' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_list_command(cmd.payload_raw)
          elseif cmd.type == 'collection.create' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_create_command(cmd.payload_raw)
          elseif cmd.type == 'collection.edit' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_edit_command(cmd.payload_raw)
          elseif cmd.type == 'collection.remove' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_remove_command(cmd.payload_raw)
          -- Action-specific collection set commands
          elseif cmd.type == 'collection_set.list' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_set_list_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.create' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_set_create_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.edit' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_set_edit_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set.remove' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_collection_set_remove_command(cmd.payload_raw)
          -- Photo metadata commands
          elseif cmd.type == 'photo_metadata.get' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_photo_metadata_get_command(cmd.payload_raw)
          elseif cmd.type == 'photo_metadata.bulk_get' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_photo_metadata_bulk_get_command(cmd.payload_raw)
          elseif cmd.type == 'photo_metadata.update' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_photo_metadata_update_command(cmd.payload_raw)
          elseif cmd.type == 'photo_metadata.bulk_update' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_photo_metadata_bulk_update_command(cmd.payload_raw)
          -- Legacy unified handlers for backward compatibility
          elseif cmd.type == 'collection' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_unified_collection_command(cmd.payload_raw)
          elseif cmd.type == 'collection_set' then
            cmdOk, resultTable, errMsg = CommandHandlers.handle_unified_collection_set_command(cmd.payload_raw)
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
