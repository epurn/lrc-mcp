local CollectionCommands = require 'CollectionCommands'
local UtilityCommands = require 'UtilityCommands'
local TestCommands = require 'TestCommands'

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

function CommandHandlers.handle_remove_collection_set_command(payload_raw)
  return CollectionCommands.handle_remove_collection_set_command(payload_raw)
end

function CommandHandlers.handle_edit_collection_command(payload_raw)
  return CollectionCommands.handle_edit_collection_command(payload_raw)
end

function CommandHandlers.handle_run_tests_command()
  return TestCommands.handle_run_tests_command()
end

function CommandHandlers.handle_list_collections_command(payload_raw)
  return CollectionCommands.handle_list_collections_command(payload_raw)
end

function CommandHandlers.handle_list_collection_sets_command(payload_raw)
  return CollectionCommands.handle_list_collection_sets_command(payload_raw)
end

function CommandHandlers.handle_edit_collection_set_command(payload_raw)
  return CollectionCommands.handle_edit_collection_set_command(payload_raw)
end

return CommandHandlers
