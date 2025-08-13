local CollectionCommands = require 'CollectionCommands'
local UtilityCommands = require 'UtilityCommands'

local CommandHandlers = {}

-- Thin dispatcher that delegates to the individual command modules
function CommandHandlers.handle_noop_command()
  return UtilityCommands.handle_noop_command()
end

function CommandHandlers.handle_echo_command(payload_raw)
  return UtilityCommands.handle_echo_command(payload_raw)
end

function CommandHandlers.handle_create_collection_set_command(payload_raw)
  return CollectionCommands.handle_create_collection_set_command(payload_raw)
end

function CommandHandlers.handle_create_collection_command(payload_raw)
  return CollectionCommands.handle_create_collection_command(payload_raw)
end

function CommandHandlers.handle_remove_collection_command(payload_raw)
  return CollectionCommands.handle_remove_collection_command(payload_raw)
end

function CommandHandlers.handle_edit_collection_command(payload_raw)
  return CollectionCommands.handle_edit_collection_command(payload_raw)
end

return CommandHandlers
