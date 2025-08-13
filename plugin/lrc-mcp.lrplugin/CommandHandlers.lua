local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local Logger = require 'Logger'
local WriteLock = require 'WriteLock'
local Utils = require 'Utils'
local CollectionUtils = require 'CollectionUtils'

local CommandHandlers = {}

-- Command handlers
function CommandHandlers.handle_noop_command()
  return true, { ok = true }, nil
end

function CommandHandlers.handle_echo_command(payload_raw)
  Logger.info('handle_echo_command called with payload_raw: ' .. tostring(payload_raw))
  local msg = nil
  if payload_raw and type(payload_raw) == 'string' then
    msg = payload_raw:match('\"message\"%s*:%s*\"([^\"]*)\"')
  end
  return true, { echo = msg or '', payload_received = payload_raw }, nil
end

-- New separate handler for creating collection sets only
function CommandHandlers.handle_create_collection_set_command(payload_raw)
  local name, parent_path = nil, nil
  
  Logger.info('handle_create_collection_set_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    name = Utils.extract_json_value(payload_raw, "name")
    parent_path = Utils.extract_json_value(payload_raw, "parent_path")
  end
  
  Logger.info('Parsed values - name: ' .. tostring(name) .. ', parent_path: ' .. tostring(parent_path))
  
  if not name or name == '' then
    return false, nil, 'Collection set name is required. Received name: ' .. tostring(name) .. ', payload: ' .. tostring(payload_raw)
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  -- Use LrTasks.startAsyncTask to ensure we're in the correct context
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
    
    Logger.debug('Starting collection set creation - name: ' .. tostring(name) .. ', parent_path: ' .. tostring(parent_path))
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
    if parent_path and parent_path ~= '' then
      Logger.info('Getting parent collection set path: ' .. parent_path)
      parent = CollectionUtils.find_collection_set(catalog, parent_path)
      if not parent then
        Logger.error('Failed to find parent collection set: ' .. tostring(parent_path))
        error_msg = 'Failed to find parent collection set: ' .. tostring(parent_path)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Create Collection Set')
        return
      end
      Logger.info('Parent collection set found: ' .. tostring(parent))
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

-- Simplified collection creation handler (no automatic parent creation)
function CommandHandlers.handle_create_collection_command(payload_raw)
  local name, parent_path = nil, nil
  
  Logger.info('handle_create_collection_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    name = Utils.extract_json_value(payload_raw, "name")
    parent_path = Utils.extract_json_value(payload_raw, "parent_path")
  end
  
  Logger.info('Parsed values - name: ' .. tostring(name) .. ', parent_path: ' .. tostring(parent_path))
  
  if not name or name == '' then
    return false, nil, 'Collection name is required. Received name: ' .. tostring(name) .. ', payload: ' .. tostring(payload_raw)
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  -- Use LrTasks.startAsyncTask to ensure we're in the correct context
  local result = nil
  local error_msg = nil
  
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    -- Acquire write lock to prevent concurrent write operations
    if not WriteLock.acquire_write_lock('Create Collection') then
      Logger.error('Failed to acquire write lock for collection creation')
      error_msg = 'Failed to acquire write lock for collection creation'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection creation - name: ' .. tostring(name) .. ', parent_path: ' .. tostring(parent_path))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Create Collection')
      return
    end
    
    -- Find the parent (outside of write access context)
    local parent = catalog
    Logger.info('Initial parent set to catalog: ' .. tostring(catalog))
    if parent_path and parent_path ~= '' then
      Logger.info('Getting parent collection set path: ' .. parent_path)
      parent = CollectionUtils.find_collection_set(catalog, parent_path)
      if not parent then
        Logger.error('Failed to find parent collection set: ' .. tostring(parent_path))
        error_msg = 'Failed to find parent collection set: ' .. tostring(parent_path)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Create Collection')
        return
      end
      Logger.info('Parent collection set found: ' .. tostring(parent))
    end
    
    -- Create the collection within write access context
    local created_collection = nil
    local created = false
    Logger.info('About to enter withWriteAccessDo for collection creation')
    local status, err = catalog:withWriteAccessDo('Create Collection', function(context)
      Logger.info('Inside withWriteAccessDo for collection creation')
      Logger.info('parent inside withWriteAccessDo: ' .. tostring(parent))
      Logger.info('parent type: ' .. type(parent))
      Logger.info('parent has createCollection method: ' .. tostring(type(parent.createCollection)))
      
      -- Check if collection already exists
      local existing = nil
      Logger.info('Searching for existing collection in: ' .. tostring(parent))
      local child_collections = parent:getChildCollections()
      Logger.info('getChildCollections result: ' .. tostring(child_collections))
      Logger.info('getChildCollections type: ' .. type(child_collections))
      
      if child_collections then
        for _, coll in ipairs(child_collections) do
          if coll:getName() == name then
            existing = coll
            break
          end
        end
      end
      
      if existing then
        Logger.info('Collection already exists: ' .. name)
        created_collection = existing
        created = false
      else
        Logger.info('Creating new collection: ' .. name .. ' under parent: ' .. tostring(parent))
        -- For root-level collections, parent should be nil, not the catalog object
        local collection_parent = (parent ~= catalog) and parent or nil
        if collection_parent then
          Logger.info('Creating collection with parent collection set: ' .. tostring(collection_parent))
        else
          Logger.info('Creating collection at root level (parent = nil)')
        end
        Logger.info('About to call catalog:createCollection(name, parent, true)')
        created_collection = catalog:createCollection(name, collection_parent, true)
        created = true
        Logger.info('Created collection result: ' .. tostring(created_collection))
        Logger.info('Created collection type: ' .. type(created_collection))
        if not created_collection then
          Logger.error('createCollection returned nil')
          error('createCollection returned nil')
        end
      end
    end, { timeout = 10 })
    
    if status ~= "executed" then
      Logger.error('Error in collection creation: ' .. tostring(err))
      error_msg = 'Failed to create collection: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Create Collection')
      return
    end
    
    -- Get collection info after write access
    local collection_info = nil
    if created_collection then
      local full_path = CollectionUtils.get_collection_path(catalog, created_collection)
      collection_info = {
        id = created_collection.localIdentifier,
        name = created_collection:getName(),
        path = full_path
      }
    end
    
    result = {
      created = created,
      collection = collection_info
    }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Create Collection')
  end, 'Create Collection Task')
  
  -- Wait for task to complete (with timeout)
  local timeout = 10 -- Reduced timeout
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection creation timed out after ' .. timeout .. ' seconds')
    WriteLock.release_write_lock('Create Collection') -- Ensure lock is released on timeout
    return false, nil, 'Collection creation timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection creation successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to create collection: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to create collection'
  end
end

function CommandHandlers.handle_remove_collection_command(payload_raw)
  local collection_path = nil
  
  Logger.info('handle_remove_collection_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    collection_path = Utils.extract_json_value(payload_raw, "collection_path")
  end
  
  Logger.info('Parsed collection_path: ' .. tostring(collection_path))
  
  if not collection_path or collection_path == '' then
    return false, nil, 'Collection path is required. Received path: ' .. tostring(collection_path)
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  -- Use LrTasks.startAsyncTask to ensure we're in the correct context
  local result = nil
  local error_msg = nil
  
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    -- Acquire write lock to prevent concurrent write operations
    if not WriteLock.acquire_write_lock('Remove Collection') then
      Logger.error('Failed to acquire write lock for collection removal')
      error_msg = 'Failed to acquire write lock for collection removal'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection removal - path: ' .. tostring(collection_path))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Remove Collection')
      return
    end
    local removed = false
    
    -- Perform the entire operation within the write access context to avoid timing issues
    local status, err = catalog:withWriteAccessDo('Remove Collection', function(context)
      -- Find the collection within the write access context to ensure proper handling
      local target_collection = CollectionUtils.find_collection_by_path(catalog, collection_path)
      if target_collection then
        target_collection:delete()
        removed = true
        Logger.debug('Collection removed successfully: ' .. tostring(collection_path))
      else
        Logger.debug('Collection not found for removal: ' .. tostring(collection_path))
      end
    end, { timeout = 10 }) -- Reduced timeout to 10 seconds
    
    if status ~= "executed" then
      Logger.error('Error in collection removal: ' .. tostring(err))
      error_msg = 'Failed to remove collection: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Remove Collection')
      return
    end
    
    result = { removed = removed }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Remove Collection')
  end, 'Remove Collection Task')
  
  -- Wait for task to complete (with timeout)
  local timeout = 10 -- Reduced timeout
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection removal timed out after ' .. timeout .. ' seconds')
    return false, nil, 'Collection removal timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection removal successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to remove collection: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to remove collection'
  end
end

function CommandHandlers.handle_edit_collection_command(payload_raw)
  local collection_path, new_name, new_parent_path = nil, nil, nil
  
  Logger.info('handle_edit_collection_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    collection_path = Utils.extract_json_value(payload_raw, "collection_path")
    new_name = Utils.extract_json_value(payload_raw, "new_name")
    new_parent_path = Utils.extract_json_value(payload_raw, "new_parent_path")
  end
  
  Logger.info('Parsed values - collection_path: ' .. tostring(collection_path) .. ', new_name: ' .. tostring(new_name) .. ', new_parent_path: ' .. tostring(new_parent_path))
  
  if not collection_path or collection_path == '' then
    return false, nil, 'Collection path is required. Received path: ' .. tostring(collection_path)
  end
  
  local LrFunctionContext = import 'LrFunctionContext'
  local LrApplication = import 'LrApplication'
  local LrTasks = import 'LrTasks'
  
  -- Use LrTasks.startAsyncTask to ensure we're in the correct context
  local result = nil
  local error_msg = nil
  
  local task_completed = false
  local task_success = false
  
  LrTasks.startAsyncTask(function()
    -- Acquire write lock to prevent concurrent write operations
    if not WriteLock.acquire_write_lock('Edit Collection') then
      Logger.error('Failed to acquire write lock for collection edit')
      error_msg = 'Failed to acquire write lock for collection edit'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection edit - path: ' .. tostring(collection_path) .. ', new_name: ' .. tostring(new_name) .. ', new_parent_path: ' .. tostring(new_parent_path))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Edit Collection')
      return
    end
    local updated = false
    local collection_info = nil
    local new_parent = nil
    
    -- Handle move (change parent) - find new parent collection set outside of write access context
    if new_parent_path ~= nil then
      if new_parent_path == '' or new_parent_path == nil then
        -- Move to root
        new_parent = catalog
      else
        -- Find new parent collection set
        new_parent = CollectionUtils.find_collection_set(catalog, new_parent_path)
      end
      
      if not new_parent then
        Logger.error('Failed to find new parent collection set: ' .. tostring(new_parent_path))
        error_msg = 'Failed to find new parent collection set: ' .. tostring(new_parent_path)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Edit Collection')
        return
      end
    end
    
    -- Perform the collection edit within a single write access context
    local status, err = catalog:withWriteAccessDo('Edit Collection', function(context)
      -- Find the collection within the write access context to ensure proper handling
      local target_collection = CollectionUtils.find_collection_by_path(catalog, collection_path)
      if not target_collection then
        Logger.debug('Collection not found for editing: ' .. tostring(collection_path))
        result = { updated = false, collection = nil }
        task_success = true
        task_completed = true
        return
      end
      
      local target_name = target_collection:getName()
      
      -- Handle rename
      if new_name and new_name ~= '' and new_name ~= target_name then
        target_collection:setName(new_name)
        target_name = new_name
        updated = true
        Logger.debug('Collection renamed to: ' .. tostring(new_name))
      end
    
      -- Handle move (change parent) - now we can use the pre-found parent
      if new_parent_path ~= nil then
        if new_parent ~= target_collection:getParent() then
          target_collection:setParent(new_parent)
          updated = true
          Logger.debug('Collection moved to new parent: ' .. tostring(new_parent_path))
        end
      end
      
      -- Note: We can't build collection info here because changes aren't visible until after write access completes
      -- Collection info will be built after the withWriteAccessDo block
    end, { timeout = 10 }) -- Reduced timeout to 10 seconds
    
    if status ~= "executed" then
      Logger.error('Error in collection edit: ' .. tostring(err))
      error_msg = 'Failed to edit collection: ' .. tostring(err)
      task_success = false
      task_completed = true
      WriteLock.release_write_lock('Edit Collection')
      return
    end
    
    -- Re-fetch the collection after write operation to get updated information
    local re_fetched_collection = nil
    local search_path = collection_path
    
    -- If the collection was renamed or moved, we need to find it at its new location
    if updated then
      -- Get the current name of the collection (it might have been renamed)
      -- We need to re-find the collection to get the updated name
      local target_collection = CollectionUtils.find_collection_by_path(catalog, collection_path)
      if target_collection then
        local current_name = target_collection:getName()
        
        -- Reconstruct the new path if moved
        if new_parent_path ~= nil then
          if new_parent_path == '' or new_parent_path == nil then
            search_path = current_name  -- Moved to root
          else
            search_path = new_parent_path .. "/" .. current_name  -- Moved to new parent
          end
        else
          -- Only renamed, not moved - reconstruct path with new name
          -- We need to find the parent path and append the new name
          local parent = target_collection:getParent()
          if parent and parent ~= catalog then
            local parent_path = CollectionUtils.get_collection_path(catalog, parent)
            search_path = parent_path .. "/" .. current_name
          else
            search_path = current_name  -- At root level
          end
        end
        re_fetched_collection = CollectionUtils.find_collection_by_path(catalog, search_path)
      end
    else
      re_fetched_collection = CollectionUtils.find_collection_by_path(catalog, collection_path)
    end
    
    if re_fetched_collection then
      -- Build updated collection info
      local full_path = CollectionUtils.get_collection_path(catalog, re_fetched_collection)
      collection_info = {
        id = re_fetched_collection.localIdentifier,
        name = re_fetched_collection:getName(),
        path = full_path
      }
    end
    
    result = {
      updated = updated,
      collection = collection_info
    }
    task_success = true
    task_completed = true
    WriteLock.release_write_lock('Edit Collection')
  end, 'Edit Collection Task')
  
  -- Wait for task to complete (with timeout)
  local timeout = 10 -- Reduced timeout
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('Collection edit timed out after ' .. timeout .. ' seconds')
    return false, nil, 'Collection edit timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('Collection edit successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to edit collection: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to edit collection'
  end
end

return CommandHandlers
