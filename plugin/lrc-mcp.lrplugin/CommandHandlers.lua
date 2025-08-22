local CollectionCommands = require 'CollectionCommands'
local CollectionSetCommands = require 'CollectionSetCommands'
local UtilityCommands = require 'UtilityCommands'
local TestCommands = require 'TestCommands'
local PhotoMetadataCommands = require 'PhotoMetadataCommands'
local PhotoMetadataCommands = require 'PhotoMetadataCommands'

local CommandHandlers = {}

-- Thin dispatcher that delegates to the individual command modules
function CommandHandlers.handle_noop_command()
  return UtilityCommands.handle_noop_command()
end

function CommandHandlers.handle_echo_command(payload_raw)
  return UtilityCommands.handle_echo_command(payload_raw)
end

function CommandHandlers.handle_run_tests_command()
  return TestCommands.handle_run_tests_command()
end

function CommandHandlers.handle_unified_collection_command(payload_raw)
  return CollectionCommands.handle_unified_collection_command(payload_raw)
end

function CommandHandlers.handle_unified_collection_set_command(payload_raw)
  return CollectionSetCommands.handle_unified_collection_set_command(payload_raw)
end

-- Action-specific dispatchers for new command types (collection.* and collection_set.*)
function CommandHandlers.handle_collection_list_command(payload_raw)
  return CollectionCommands.handle_collection_list_command(payload_raw)
end

function CommandHandlers.handle_collection_create_command(payload_raw)
  return CollectionCommands.handle_collection_create_command(payload_raw)
end

function CommandHandlers.handle_collection_edit_command(payload_raw)
  return CollectionCommands.handle_collection_edit_command(payload_raw)
end

function CommandHandlers.handle_collection_remove_command(payload_raw)
  return CollectionCommands.handle_collection_remove_command(payload_raw)
end

function CommandHandlers.handle_collection_set_list_command(payload_raw)
  return CollectionSetCommands.handle_collection_set_list_command(payload_raw)
end

function CommandHandlers.handle_collection_set_create_command(payload_raw)
  return CollectionSetCommands.handle_collection_set_create_command(payload_raw)
end

function CommandHandlers.handle_collection_set_edit_command(payload_raw)
  return CollectionSetCommands.handle_collection_set_edit_command(payload_raw)
end

function CommandHandlers.handle_collection_set_remove_command(payload_raw)
  return CollectionSetCommands.handle_collection_set_remove_command(payload_raw)
end

-- Photo metadata command dispatchers
function CommandHandlers.handle_photo_metadata_get_command(payload_raw)
  return PhotoMetadataCommands.get(payload_raw)
end

function CommandHandlers.handle_photo_metadata_bulk_get_command(payload_raw)
  return PhotoMetadataCommands.bulk_get(payload_raw)
end

function CommandHandlers.handle_photo_metadata_update_command(payload_raw)
  return PhotoMetadataCommands.update(payload_raw)
end

function CommandHandlers.handle_photo_metadata_bulk_update_command(payload_raw)
  return PhotoMetadataCommands.bulk_update(payload_raw)
end

return CommandHandlers
