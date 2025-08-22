local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrTasks = import 'LrTasks'
local LrFunctionContext = import 'LrFunctionContext'
local plugin_dir = _PLUGIN and _PLUGIN.path or nil
if plugin_dir then
  local logs_dir = LrPathUtils.child(plugin_dir, 'logs')
  local log_file = LrPathUtils.child(logs_dir, 'lrc_mcp.log')
  LrFileUtils.createAllDirectories(logs_dir)
  local fh = io.open(log_file, 'w')
  if fh then
    fh:write(os.date('!%Y-%m-%dT%H:%M:%SZ'), ' [INIT] direct write before Logger\n')
    fh:close()
  end
end

local Logger = require 'Logger'
Logger.info('Init.lua: starting plugin initialization')

local ok_mcp, MCPBridge_or_err = pcall(require, 'MCPBridge')
if not ok_mcp then
  Logger.error('Init.lua: failed to require MCPBridge: ' .. tostring(MCPBridge_or_err))
  return true
end
local MCPBridge = MCPBridge_or_err

local probe = Logger.test_write()
Logger.info('lrc_mcp plugin initialized; plugin_write_ok=' .. tostring(probe and probe.plugin_write_ok))

-- Defer starting background work until after init completes, to ensure a yield-safe context.
-- Use LrTasks.startAsyncTask to improve reliability of background loop startup.
LrTasks.startAsyncTask(function()
  Logger.info('Init.lua: launching MCPBridge loops via LrTasks.startAsyncTask')
  local ok_start, start_err = pcall(function() MCPBridge.start() end)
  if not ok_start then
    Logger.error('Init.lua: MCPBridge.start() failed: ' .. tostring(start_err))
  end
end, 'MCP Background Loops')

Logger.info('Init.lua: plugin initialization complete')
return true
