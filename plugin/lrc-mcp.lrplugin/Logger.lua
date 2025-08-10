local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'

local logger

local function get_logger()
  if not logger then
    logger = LrLogger('lrc_mcp')
    logger:enable('logfile')
    logger:enable('print')
  end
  return logger
end

local function write_plugin_file(message)
  local ok = pcall(function()
    local plugin_dir = _PLUGIN and _PLUGIN.path or nil
    if not plugin_dir then return end
    local logs_dir = LrPathUtils.child(plugin_dir, 'logs')
    local log_file = LrPathUtils.child(logs_dir, 'lrc_mcp.log')
    LrFileUtils.createAllDirectories(logs_dir)
    local fh = io.open(log_file, 'a')
    if fh then
      fh:write(os.date('!%Y-%m-%dT%H:%M:%SZ'), ' ', message, '\n')
      fh:close()
    end
  end)
end

-- optional secondary location (Documents), not required for normal operation
local function write_documents_file(message)
  local documents = LrPathUtils.getStandardFilePath and LrPathUtils.getStandardFilePath('documents') or nil
  if not documents then
    -- Fallback for environments where Lightroom cannot resolve Documents
    local userprofile = os.getenv('USERPROFILE')
    if userprofile then
      documents = LrPathUtils.child(userprofile, 'Documents')
    end
  end
  if not documents then return end
  local logs_dir = LrPathUtils.child(documents, 'lrClassicLogs')
  local log_file = LrPathUtils.child(logs_dir, 'lrc_mcp.log')
  LrFileUtils.createAllDirectories(logs_dir)
  local fh = io.open(log_file, 'a')
  if fh then
    fh:write(os.date('!%Y-%m-%dT%H:%M:%SZ'), ' ', message, '\n')
    fh:close()
  end
end

local M = {}

function M.get_paths()
  local plugin_dir = _PLUGIN and _PLUGIN.path or nil
  local plugin_logs, plugin_file
  if plugin_dir then
    plugin_logs = LrPathUtils.child(plugin_dir, 'logs')
    plugin_file = LrPathUtils.child(plugin_logs, 'lrc_mcp.log')
  end
  return {
    plugin_logs_dir = plugin_logs,
    plugin_log_file = plugin_file,
  }
end

function M.test_write()
  local paths = M.get_paths()
  local plugin_ok = false
  local ok1 = pcall(function()
    if paths.plugin_logs_dir and paths.plugin_log_file then
      LrFileUtils.createAllDirectories(paths.plugin_logs_dir)
      local fh = io.open(paths.plugin_log_file, 'a')
      if fh then
        fh:write(os.date('!%Y-%m-%dT%H:%M:%SZ'), ' [PROBE] plugin log write test\n')
        fh:close()
        plugin_ok = true
      end
    end
  end)
  return {
    plugin_write_ok = plugin_ok and ok1 or false,
    paths = paths,
  }
end

function M.info(...)
  local msg = table.concat({ ... }, ' ')
  get_logger():info(msg)
  write_plugin_file('[INFO] ' .. msg)
  write_documents_file('[INFO] ' .. msg)
end

function M.warn(...)
  local msg = table.concat({ ... }, ' ')
  get_logger():warn(msg)
  write_plugin_file('[WARN] ' .. msg)
  write_documents_file('[WARN] ' .. msg)
end

function M.error(...)
  local msg = table.concat({ ... }, ' ')
  get_logger():error(msg)
  write_plugin_file('[ERROR] ' .. msg)
  write_documents_file('[ERROR] ' .. msg)
end

function M.debug(...)
  local msg = table.concat({ ... }, ' ')
  get_logger():trace(msg)
end

return M


