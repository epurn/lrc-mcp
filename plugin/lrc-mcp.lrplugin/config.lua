-- Lightroom logger configuration for lrc_mcp
-- Ensures verbose logging and file output are enabled for our logger.

loggers = loggers or {}
-- Match the logger name used in Logger.lua (LrLogger('lrc_mcp'))
loggers.lrc_mcp = {
  logLevel = 'trace',
  action = 'logfile',
}


