local Logger = require 'Logger'
local Utils = require 'Utils'

local UtilityCommands = {}

-- Command handlers
function UtilityCommands.handle_noop_command()
  return true, { ok = true }, nil
end

function UtilityCommands.handle_echo_command(payload_raw)
  Logger.info('handle_echo_command called with payload_raw: ' .. tostring(payload_raw))
  local msg = nil
  if payload_raw and type(payload_raw) == 'string' then
    msg = payload_raw:match('\"message\"%s*:%s*\"([^\"]*)\"')
  end
  return true, { echo = msg or '', payload_received = payload_raw }, nil
end

return UtilityCommands
