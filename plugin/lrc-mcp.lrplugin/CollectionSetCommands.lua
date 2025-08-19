local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local Logger = require 'Logger'
local WriteLock = require 'WriteLock'
local Utils = require 'Utils'
local CollectionUtils = require 'CollectionUtils'

local CollectionSetCommands = {}

-- Unified collection set command handler
function CollectionSetCommands.handle_unified_collection_set_command(payload_raw)
  local function_name, args = nil, nil
  
  Logger.info('handle_unified_collection_set_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    function_name = Utils.extract_json_value(payload_raw, "function")
    -- Extract args as a JSON string and parse it
    local args_str = Utils.extract_json_value(payload_raw, "args")
    if args_str then
      args = Utils.extract_json_value(args_str)
    end
  end
  
  Logger.info('Parsed values - function: ' .. tostring(function_name) .. ', args: ' .. tostring(args))
  
  if not function_name or function_name == '' then
    return false, nil, 'Function name is required. Received function: ' .. tostring(function_name) .. ', payload: ' .. tostring(payload_raw)
  end
  
  if function_name == 'list' then
    return CollectionSetCommands.handle_collection_set_list_command(args)
  elseif function_name == 'create' then
    return CollectionSetCommands.handle_collection_set_create_command(args)
  elseif function_name == 'edit' then
    return CollectionSetCommands.handle_collection_set_edit_command(args)
  elseif function_name == 'delete' then
    return CollectionSetCommands.handle_collection_set_delete_command(args)
  else
    return false, nil, 'Invalid function. Expected one of: list, create, edit, delete. Received: ' .. tostring(function_name)
  end
end

-- Private helper functions for collection set commands
function CollectionSetCommands.handle_collection_set_list_command(args)
  Logger.info('handle_collection_set_list_command called with args: ' .. tostring(args))
  
  local parent_id = nil
  local parent_path = nil
  local name_contains = nil
  
  if args then
    if type(args) == 'table' then
      parent_id = args.parent_id
      parent_path = args.parent_path
      name_contains = args.name_contains
    elseif type(args) == 'string' then
      parent_id = Utils.extract_json_value(args, "parent_id")
      parent_path = Utils.extract_json_value(args, "parent_path")
      name_contains = Utils.extract_json_value(args, "name_contains")
    end
  end
  
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    Logger.debug('Starting collection set listing - parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path) .. ', name_contains: ' .. tostring(name_contains))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      return
    end
    
    local parent = catalog
    if parent_id and parent_id ~= '' then
      Logger.info('Finding parent collection set by id: ' .. tostring(parent_id))
      parent = CollectionUtils.find_collection_set_by_id(catalog, parent_id)
      if not parent then
        Logger.error('Failed to find parent collection set by id: ' .. tostring(parent_id))
        error_msg = 'Failed to find parent collection set by id: ' .. tostring(parent_id)
        task_success = false
        task_completed = true
        return
      end
    elseif parent_path and parent_path ~= '' then
      Logger.info('Finding parent collection set by path: ' .. tostring(parent_path))
      parent = CollectionUtils.find_collection_set(catalog, parent_path)
      if not parent then
        Logger.error('Failed to find parent collection set by path: ' .. tostring(parent_path))
        error_msg = 'Failed to find parent collection set by path: ' .. tostring(parent_path)
        task_success = false
        task_completed = true
        return
      end
    end
    
    local function collect_sets(node, acc)
      local child_sets = node:getChildCollectionSets()
      if child_sets then
        for _, coll_set in ipairs(child_sets) do
          local set_name = coll_set:getName() or ''
          local full_path = CollectionUtils.get_collection_path(catalog, coll_set)
          
          -- Apply name filter if provided
          if not name_contains or string.find(string.lower(set_name), string.lower(name_contains), 1, true) then
            table.insert(acc, {
              id = coll_set.localIdentifier,
              name = set_name,
              path = full_path
            })
          end
          
          -- Always recurse (include_nested is default behavior now)
          collect_sets(coll_set, acc)
        end
      end
    end
    
    local sets = {}
    collect_sets(parent, sets)
    
    result = { collection_sets = sets }
    task_success = true
    task_completed = true
  end, 'List Collection Sets Task')
  
  local timeout = 10
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('collection set listing timed out after ' .. timeout .. ' seconds')
    return false, nil, 'Collection set listing timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('collection set listing successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to list collection sets: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to list collection sets'
  end
end

function CollectionSetCommands.handle_collection_set_create_command(args)
  Logger.info('handle_collection_set_create_command called with args: ' .. tostring(args))
  
  local name, parent_id, parent_path = nil, nil, nil
  
  if args then
    if type(args) == 'table' then
      name = args.name
      parent_id = args.parent_id
      parent_path = args.parent_path
    elseif type(args) == 'string' then
      name = Utils.extract_json_value(args, "name")
      parent_id = Utils.extract_json_value(args, "parent_id")
      parent_path = Utils.extract_json_value(args, "parent_path")
    end
  end
  
  Logger.info('Parsed values - name: ' .. tostring(name) .. ', parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path))
  
  if not name or name == '' then
    return false, nil, 'Collection set name is required. Received name: ' .. tostring(name)
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    -- Acquire write lock to prevent concurrent write operations
    if not WriteLock.acquire_write_lock('Create Collection Set') then
      Logger.error('Failed to acquire write lock for collection set creation')
      error_msg = 'Failed to acquire write lock for collection set creation'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection set creation - name: ' .. tostring(name) .. ', parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Create Collection Set')
      return
    end
    
    -- Find the parent (outside of write access context)
    local parent = catalog
    Logger.info('Initial parent set to catalog: ' .. tostring(catalog))
    
    -- Precedence: parent_id > parent_path
    if parent_id and parent_id ~= '' then
      Logger.info('Getting parent collection set by id: ' .. tostring(parent_id))
      parent = CollectionUtils.find_collection_set_by_id(catalog, parent_id)
      if not parent then
        Logger.error('Failed to find parent collection set by id: ' .. tostring(parent_id))
        error_msg = 'Failed to find parent collection set by id: ' .. tostring(parent_id)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Create Collection Set')
        return
      end
      Logger.info('Parent collection set found by id: ' .. tostring(parent))
    elseif parent_path and parent_path ~= '' then
      Logger.info('Getting parent collection set by path: ' .. tostring(parent_path))
      parent = CollectionUtils.find_collection_set(catalog, parent_path)
      if not parent then
        Logger.error('Failed to find parent collection set by path: ' .. tostring(parent_path))
        error_msg = 'Failed to find parent collection set by path: ' .. tostring(parent_path)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Create Collection Set')
        return
      end
      Logger.info('Parent collection set found by path: ' .. tostring(parent))
    end
    
    -- Create the collection set within write access context
    local created_collection_set = nil
    local created = false
    Logger.info('About to enter withWriteAccessDo for collection set creation')
    local status, err = catalog:withWriteAccessDo('Create Collection Set', function(context)
      Logger.info('Inside withWriteAccessDo for collection set creation')
      Logger.info('parent inside withWriteAccessDo: ' .. tostring(parent))
      Logger.info('parent type: ' .. type(parent))
      Logger.info('parent has createCollectionSet method: ' .. tostring(type(parent.createCollectionSet)))
      
      -- For root-level collection sets, parent should be nil, not the catalog object
      local collection_set_parent = (parent ~= catalog) and parent or nil
      
      -- Check if collection set already exists
      local existing = nil
      local search_parent = collection_set_parent or catalog
      Logger.info('Searching for existing collection set in: ' .. tostring(search_parent))
      local child_sets = search_parent:getChildCollectionSets()
      Logger.info('getChildCollectionSets result: ' .. tostring(child_sets))
      Logger.info('getChildCollectionSets type: ' .. type(child_sets))
      
      if child_sets then
        for _, coll_set in ipairs(child_sets) do
          if coll_set:getName() == name then
            existing = coll_set
            break
          end
        end
      end
      
      if existing then
        Logger.info('Collection set already exists: ' .. name)
        created_collection_set = existing
        created = false
      else
        Logger.info('Creating new collection set: ' .. name .. ' under parent: ' .. tostring(collection_set_parent))
        if collection_set_parent then
          Logger.info('Creating collection set with parent collection set: ' .. tostring(collection_set_parent))
        else
          Logger.info('Creating collection set at root level (parent = nil)')
        end
        Logger.info('About to call catalog:createCollectionSet(name, parent)')
        created_collection_set = catalog:createCollectionSet(name, collection_set_parent)
        created = true
        Logger.info('Created collection set result: ' .. tostring(created_collection_set))
        Logger.info('Created collection set type: ' .. type(created_collection_set))
        if not created_collection_set then
          Logger.error('createCollectionSet returned nil')
          error('createCollectionSet returned nil')
        end
      end
    end, { timeout = 10 })
    
    if status ~= "executed" then
      Logger.error('Error in collection set creation: ' .. tostring(err))
      error_msg = 'Failed to create collection set: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Create Collection Set')
      return
    end
    
    -- Get collection set info after write access
    local collection_set_info = nil
    if created_collection_set then
      local full_path = CollectionUtils.get_collection_path(catalog, created_collection_set)
      collection_set_info = {
        id = created_collection_set.localIdentifier,
        name = created_collection_set:getName(),
        path = full_path
      }
    end
    
    result = {
      created = created,
      collection_set = collection_set_info
    }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Create Collection Set')
  end, 'Create Collection Set Task')
  
  -- Wait for task to complete (with timeout)
  local timeout = 10 -- Reduced timeout
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection set creation timed out after ' .. timeout .. ' seconds')
    WriteLock.release_write_lock('Create Collection Set') -- Ensure lock is released on timeout
    return false, nil, 'Collection set creation timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection set creation successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to create collection set: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to create collection set'
  end
end

function CollectionSetCommands.handle_collection_set_edit_command(args)
  Logger.info('handle_collection_set_edit_command called with args: ' .. tostring(args))
  
  local target_id, target_path, new_name, new_parent_id, new_parent_path = nil, nil, nil, nil, nil
  
  if args then
    if type(args) == 'table' then
      target_id = args.id
      target_path = args.path or args.collection_set_path  -- Accept legacy name
      new_name = args.new_name
      new_parent_id = args.new_parent_id
      new_parent_path = args.new_parent_path
    elseif type(args) == 'string' then
      target_id = Utils.extract_json_value(args, "id")
      target_path = Utils.extract_json_value(args, "path") or Utils.extract_json_value(args, "collection_set_path")
      new_name = Utils.extract_json_value(args, "new_name")
      new_parent_id = Utils.extract_json_value(args, "new_parent_id")
      new_parent_path = Utils.extract_json_value(args, "new_parent_path")
    end
  end
  
  -- Precedence: id > path
  local target_identifier = nil
  if target_id and target_id ~= '' then
    target_identifier = target_id
    Logger.info('Editing collection set by id: ' .. tostring(target_id))
  elseif target_path and target_path ~= '' then
    target_identifier = target_path
    Logger.info('Editing collection set by path: ' .. tostring(target_path))
  else
    return false, nil, 'Collection set id or path is required for edit'
  end
  
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    if not WriteLock.acquire_write_lock('Edit Collection Set') then
      Logger.error('Failed to acquire write lock for collection set edit')
      error_msg = 'Failed to acquire write lock for collection set edit'
      task_success = false
      task_completed = true
      return
    end
    
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Edit Collection Set')
      return
    end
    
    local updated = false
    local target_name = nil
    local moved_parent_path = nil
    
    -- Handle move (change parent) - find new parent collection set outside of write access context
    local new_parent = nil
    if new_parent_id ~= nil then
      if new_parent_id == '' or new_parent_id == nil then
        -- Move to root
        new_parent = catalog
        moved_parent_path = ''
      else
        -- Find new parent collection set by id
        new_parent = CollectionUtils.find_collection_set_by_id(catalog, new_parent_id)
        if not new_parent then
          Logger.error('Failed to find new parent collection set by id: ' .. tostring(new_parent_id))
          error_msg = 'Failed to find new parent collection set by id: ' .. tostring(new_parent_id)
          task_success = false
          task_completed = true
          WriteLock.release_write_lock('Edit Collection Set')
          return
        end
        moved_parent_path = 'id:' .. new_parent_id  -- Placeholder, will be resolved later
      end
    elseif new_parent_path ~= nil then
      if new_parent_path == '' or new_parent_path == nil then
        -- Move to root
        new_parent = catalog
        moved_parent_path = ''
      else
        -- Find new parent collection set by path
        new_parent = CollectionUtils.find_collection_set(catalog, new_parent_path)
        if not new_parent then
          Logger.error('Failed to find new parent collection set by path: ' .. tostring(new_parent_path))
          error_msg = 'Failed to find new parent collection set by path: ' .. tostring(new_parent_path)
          task_success = false
          task_completed = true
          WriteLock.release_write_lock('Edit Collection Set')
          return
        end
        moved_parent_path = new_parent_path
      end
    end
    
    local status, err = catalog:withWriteAccessDo('Edit Collection Set', function(context)
      -- Find the target collection set within the write access context
      local target_set = nil
      if target_id and target_id ~= '' then
        target_set = CollectionUtils.find_collection_set_by_id(catalog, target_id)
      else
        target_set = CollectionUtils.find_collection_set(catalog, target_path)
      end
      
      if not target_set then
        Logger.debug('Collection set not found for editing: ' .. tostring(target_identifier))
        result = { updated = false, collection_set = nil }
        task_success = true
        task_completed = true
        return
      end
      
      target_name = target_set:getName()
      
      if new_name and new_name ~= '' and new_name ~= target_name then
        target_set:setName(new_name)
        target_name = new_name
        updated = true
        Logger.debug('Collection set renamed to: ' .. tostring(new_name))
      end
      
      if new_parent ~= nil then
        if new_parent ~= target_set:getParent() then
          target_set:setParent(new_parent)
          updated = true
          Logger.debug('Collection set moved to new parent')
        end
      end
    end, { timeout = 10 })
    
    if status ~= "executed" then
      Logger.error('Error in collection set edit: ' .. tostring(err))
      error_msg = 'Failed to edit collection set: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Edit Collection Set')
      return
    end
    
    -- Reconstruct search path for finding the updated collection set
    local search_path = nil
    if target_id and target_id ~= '' then
      -- If we had an id, we need to find by id again
      search_path = 'id:' .. target_id
    else
      search_path = target_path
    end
    
    if updated then
      -- For moved collection sets, we need to reconstruct the new path
      -- This is complex because we need to get the actual new parent path
      -- For now, we'll just try to find it by the identifier we have
      if target_id and target_id ~= '' then
        search_path = 'id:' .. target_id
      else
        search_path = target_path  -- This might be stale, but we'll try
      end
    end
    
    local re_fetched = CollectionUtils.find_collection_set(catalog, search_path)
    local info = nil
    if re_fetched then
      local full_path = CollectionUtils.get_collection_path(catalog, re_fetched)
      info = {
        id = re_fetched.localIdentifier,
        name = re_fetched:getName(),
        path = full_path
      }
    end
    
    result = {
      updated = updated,
      collection_set = info
    }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Edit Collection Set')
  end, 'Edit Collection Set Task')
  
  local timeout = 10
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection set edit timed out after ' .. timeout .. ' seconds')
    WriteLock.release_write_lock('Edit Collection Set') -- Ensure lock is released on timeout
    return false, nil, 'Collection set edit timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection set edit successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to edit collection set: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to edit collection set'
  end
end

function CollectionSetCommands.handle_collection_set_delete_command(args)
  Logger.info('handle_collection_set_delete_command called with args: ' .. tostring(args))
  
  local target_id, target_path = nil, nil
  
  if args then
    if type(args) == 'table' then
      target_id = args.id
      target_path = args.path or args.collection_set_path  -- Accept legacy name
    elseif type(args) == 'string' then
      target_id = Utils.extract_json_value(args, "id")
      target_path = Utils.extract_json_value(args, "path") or Utils.extract_json_value(args, "collection_set_path")
    end
  end
  
  -- Precedence: id > path
  local target_identifier = nil
  if target_id and target_id ~= '' then
    target_identifier = target_id
    Logger.info('Deleting collection set by id: ' .. tostring(target_id))
  elseif target_path and target_path ~= '' then
    target_identifier = target_path
    Logger.info('Deleting collection set by path: ' .. tostring(target_path))
  else
    return false, nil, 'Collection set id or path is required for delete'
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  local result = nil
  local error_msg = nil
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    -- Acquire write lock to prevent concurrent write operations
    if not WriteLock.acquire_write_lock('Remove Collection Set') then
      Logger.error('Failed to acquire write lock for collection set removal')
      error_msg = 'Failed to acquire write lock for collection set removal'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection set removal - id: ' .. tostring(target_id) .. ', path: ' .. tostring(target_path))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Remove Collection Set')
      return
    end
    local removed = false
    
    -- Perform the entire operation within the write access context to avoid timing issues
    local status, err = catalog:withWriteAccessDo('Remove Collection Set', function(context)
      -- Find the collection set within the write access context to ensure proper handling
      local target_collection_set = nil
      if target_id and target_id ~= '' then
        target_collection_set = CollectionUtils.find_collection_set_by_id(catalog, target_id)
      else
        target_collection_set = CollectionUtils.find_collection_set(catalog, target_path)
      end
      
      if target_collection_set and target_collection_set ~= catalog then
        target_collection_set:delete()
        removed = true
        Logger.debug('Collection set removed successfully: ' .. tostring(target_identifier))
      else
        Logger.debug('Collection set not found for removal: ' .. tostring(target_identifier))
      end
    end, { timeout = 10 }) -- Reduced timeout to 10 seconds
    
    if status ~= "executed" then
      Logger.error('Error in collection set removal: ' .. tostring(err))
      error_msg = 'Failed to remove collection set: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Remove Collection Set')
      return
    end
    
    result = { removed = removed }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Remove Collection Set')
  end, 'Remove Collection Set Task')
  
  -- Wait for task to complete (with timeout)
  local timeout = 10 -- Reduced timeout
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection set removal timed out after ' .. timeout .. ' seconds')
    WriteLock.release_write_lock('Remove Collection Set') -- Ensure lock is released on timeout
    return false, nil, 'Collection set removal timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection set removal successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to remove collection set: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to remove collection set'
  end
end

-- Action-specific entry points for MCP action types (collection_set.*)

function CollectionSetCommands.handle_collection_set_remove_command(payload_raw)
  Logger.info('handle_collection_set_remove_command payload_raw: ' .. tostring(payload_raw))
  local args = nil
  if payload_raw and type(payload_raw) == 'string' and #payload_raw > 0 then
    args = Utils.extract_json_value(payload_raw)
  end
  return CollectionSetCommands.handle_collection_set_delete_command(args)
end

return CollectionSetCommands
