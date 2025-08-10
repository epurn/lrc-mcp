local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local plugin_dir = _PLUGIN and _PLUGIN.path or nil
if plugin_dir then
  local logs_dir = LrPathUtils.child(plugin_dir, 'logs')
  local log_file = LrPathUtils.child(logs_dir, 'lrc_mcp.log')
  LrFileUtils.createAllDirectories(logs_dir)
  local fh = io.open(log_file, 'a')
  if fh then
    fh:write(os.date('!%Y-%m-%dT%H:%M:%SZ'), ' [INIT] direct write before Logger\n')
    fh:close()
  end
end

local Logger = require 'Logger'
local probe = Logger.test_write()
Logger.info('lrc_mcp plugin initialized; plugin_write_ok=' .. tostring(probe and probe.plugin_write_ok))
return true


