local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local Logger = require 'Logger'
local WriteLock = require 'WriteLock'
local Utils = require 'Utils'
local CollectionUtils = require 'CollectionUtils'

local CollectionCommands = {}

-- Unified collection command handler
function CollectionCommands.handle_unified_collection_command(payload_raw)
  local function_name, args = nil, nil
  
  Logger.info('handle_unified_collection_command called with payload_raw: ' .. tostring(payload_raw))
  
  if payload_raw and type(payload_raw) == 'string' then
    function_name = Utils.extract_json_value(payload_raw, "function")
    -- Extract args as a JSON string; pass as raw for downstream parsing
    local args_str = Utils.extract_json_value(payload_raw, "args")
    if args_str then
      args = args_str
    end
  end
  
  Logger.info('Parsed values - function: ' .. tostring(function_name) .. ', args: ' .. tostring(args))
  
  if not function_name or function_name == '' then
    return false, nil, 'Function name is required. Received function: ' .. tostring(function_name) .. ', payload: ' .. tostring(payload_raw)
  end
  
  -- Handle deprecated 'remove' alias
  local deprecation = nil
  if function_name == 'remove' then
    Logger.warning('handle_unified_collection_command: "remove" is deprecated; use "delete" instead.')
    function_name = 'delete'
    deprecation = 'Function "remove" is deprecated; use "delete" instead.'
  end
  
  if function_name == 'list' then
    return CollectionCommands.handle_collection_list_command(args)
  elseif function_name == 'create' then
    return CollectionCommands.handle_collection_create_command(args)
  elseif function_name == 'edit' then
    return CollectionCommands.handle_collection_edit_command(args)
  elseif function_name == 'delete' then
    return CollectionCommands.handle_collection_delete_command(args)
  else
    return false, nil, 'Invalid function. Expected one of: list, create, edit, delete. Received: ' .. tostring(function_name)
  end
end

-- functions for collection commands
function CollectionCommands.handle_collection_list_command(args)
  Logger.info('handle_collection_list_command called with args: ' .. tostring(args))
  
  local parent_id = nil
  local parent_path = nil
  local name_contains = nil
  
  if args then
    if type(args) == 'table' then
      parent_id = args.parent_id or args.set_id  -- Accept legacy name
      parent_path = args.parent_path
      name_contains = args.name_contains
    elseif type(args) == 'string' then
      parent_id = Utils.extract_json_value(args, "parent_id") or Utils.extract_json_value(args, "set_id")
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
    Logger.debug('Starting collection listing - parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path) .. ', name_contains: ' .. tostring(name_contains))
    local catalog = LrApplication.activeCatalog()
    if not catalog then
      Logger.error('No active catalog found')
      error_msg = 'No active catalog found'
      task_success = false
      task_completed = true
      return
    end
    
    local root = catalog
    -- Precedence: parent_id > parent_path
    if parent_id and parent_id ~= '' then
      local parent_set = CollectionUtils.find_collection_set_by_id(catalog, parent_id)
      if not parent_set then
        Logger.error('Failed to find parent collection set by id: ' .. tostring(parent_id))
        error_msg = 'Failed to find parent collection set by id: ' .. tostring(parent_id)
        task_success = false
        task_completed = true
        return
      end
      root = parent_set
    elseif parent_path and parent_path ~= '' then
      local parent_set = CollectionUtils.find_collection_set(catalog, parent_path)
      if not parent_set then
        Logger.error('Failed to find parent collection set by path: ' .. tostring(parent_path))
        error_msg = 'Failed to find parent collection set by path: ' .. tostring(parent_path)
        task_success = false
        task_completed = true
        return
      end
      root = parent_set
    end
    
    local lc_name_contains = nil
    if name_contains and type(name_contains) == 'string' then
      lc_name_contains = string.lower(name_contains)
    end
    
    local function matches_filters(coll)
      if lc_name_contains then
        local nm = string.lower(coll:getName() or '')
        if not string.find(nm, lc_name_contains, 1, true) then
          return false
        end
      end
      return true
    end
    
    local function collect_from_node(node, acc)
      local cols = node:getChildCollections()
      if cols then
        for _, coll in ipairs(cols) do
          if matches_filters(coll) then
            local parent = coll:getParent()
            local full_path = CollectionUtils.get_collection_path(catalog, coll)
            
            -- Detect smart collection (best-effort)
            local is_smart = false
            local ok_has, _ = pcall(function() return coll.getSearchDescription ~= nil end)
            if ok_has and coll.getSearchDescription then
              local ok_desc, desc = pcall(function() return coll:getSearchDescription() end)
              if ok_desc and desc ~= nil then
                is_smart = true
              end
            end
            
            -- Photo count (best-effort)
            local photo_count = 0
            local ok_photos, photos = pcall(function() return coll:getPhotos() end)
            if ok_photos and type(photos) == 'table' then
              photo_count = #photos
            end
            
            table.insert(acc, {
              id = coll.localIdentifier,
              name = coll:getName(),
              set_id = (parent and parent ~= catalog) and tostring(parent.localIdentifier) or nil,
              smart = is_smart,
              photo_count = photo_count,
              path = full_path
            })
          end
        end
      end
      local child_sets = node:getChildCollectionSets()
      if child_sets then
        for _, child in ipairs(child_sets) do
          collect_from_node(child, acc)
        end
      end
    end
    
    local list = {}
    collect_from_node(root, list)
    result = { collections = list }
    task_success = true
    task_completed = true
  end, 'List Collections Task')
  
  local timeout = 10
  local elapsed = 0
  while not task_completed and elapsed < timeout do
    LrTasks.sleep(0.1)
    elapsed = elapsed + 0.1
  end
  
  if not task_completed then
    Logger.error('collection listing timed out after ' .. timeout .. ' seconds')
    return false, nil, 'Collection listing timed out after ' .. timeout .. ' seconds'
  end
  
  if task_success and result then
    Logger.debug('collection listing successful: ' .. tostring(result))
    return true, result, nil
  else
    Logger.error('Failed to list collections: ' .. tostring(error_msg))
    return false, nil, error_msg or 'Failed to list collections'
  end
end

function CollectionCommands.handle_collection_create_command(args)
  Logger.info('handle_collection_create_command called with args: ' .. tostring(args))
  
  local name, parent_id, parent_path, smart = nil, nil, nil, nil
  
  if args then
    if type(args) == 'table' then
      name = args.name
      parent_id = args.parent_id
      parent_path = args.parent_path
      smart = args.smart
    elseif type(args) == 'string' then
      name = Utils.extract_json_value(args, "name")
      parent_id = Utils.extract_json_value(args, "parent_id")
      parent_path = Utils.extract_json_value(args, "parent_path")
      smart = Utils.extract_json_value(args, "smart")
    end
  end
  
  Logger.info('Parsed values - name: ' .. tostring(name) .. ', parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path) .. ', smart: ' .. tostring(smart))
  
  if not name or name == '' then
    return false, nil, 'Collection name is required. Received name: ' .. tostring(name)
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
    if not WriteLock.acquire_write_lock('Create Collection') then
      Logger.error('Failed to acquire write lock for collection creation')
      error_msg = 'Failed to acquire write lock for collection creation'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection creation - name: ' .. tostring(name) .. ', parent_id: ' .. tostring(parent_id) .. ', parent_path: ' .. tostring(parent_path))
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
    
    -- Precedence: parent_id > parent_path
    if parent_id and parent_id ~= '' then
      Logger.info('Getting parent collection set by id: ' .. tostring(parent_id))
      parent = CollectionUtils.find_collection_set_by_id(catalog, parent_id)
      if not parent then
        Logger.error('Failed to find parent collection set by id: ' .. tostring(parent_id))
        error_msg = 'Failed to find parent collection set by id: ' .. tostring(parent_id)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Create Collection')
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
        WriteLock.release_write_lock('Create Collection')
        return
      end
      Logger.info('Parent collection set found by path: ' .. tostring(parent))
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

function CollectionCommands.handle_collection_edit_command(args)
  Logger.info('handle_collection_edit_command called with args: ' .. tostring(args))
  
  local target_id, target_path, new_name, new_parent_id, new_parent_path = nil, nil, nil, nil, nil
  
  if args then
    if type(args) == 'table' then
      target_id = args.id
      target_path = args.path or args.collection_path  -- Accept legacy name
      new_name = args.new_name
      new_parent_id = args.new_parent_id
      new_parent_path = args.new_parent_path
    elseif type(args) == 'string' then
      target_id = Utils.extract_json_value(args, "id")
      target_path = Utils.extract_json_value(args, "path") or Utils.extract_json_value(args, "collection_path")
      new_name = Utils.extract_json_value(args, "new_name")
      new_parent_id = Utils.extract_json_value(args, "new_parent_id")
      new_parent_path = Utils.extract_json_value(args, "new_parent_path")
    end
  end
  
  -- Precedence: id > path
  local target_identifier = nil
  if target_id and target_id ~= '' then
    target_identifier = target_id
    Logger.info('Editing collection by id: ' .. tostring(target_id))
  elseif target_path and target_path ~= '' then
    target_identifier = target_path
    Logger.info('Editing collection by path: ' .. tostring(target_path))
  else
    return false, nil, 'Collection id or path is required for edit'
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
    if not WriteLock.acquire_write_lock('Edit Collection') then
      Logger.error('Failed to acquire write lock for collection edit')
      error_msg = 'Failed to acquire write lock for collection edit'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection edit - id: ' .. tostring(target_id) .. ', path: ' .. tostring(target_path) .. ', new_name: ' .. tostring(new_name) .. ', new_parent_id: ' .. tostring(new_parent_id) .. ', new_parent_path: ' .. tostring(new_parent_path))
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
    -- Precedence: new_parent_id > new_parent_path
    if new_parent_id ~= nil then
      if new_parent_id == '' or new_parent_id == nil then
        -- Move to root
        new_parent = catalog
      else
        -- Find new parent collection set by id
        new_parent = CollectionUtils.find_collection_set_by_id(catalog, new_parent_id)
      end
      
      if not new_parent then
        Logger.error('Failed to find new parent collection set by id: ' .. tostring(new_parent_id))
        error_msg = 'Failed to find new parent collection set by id: ' .. tostring(new_parent_id)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Edit Collection')
        return
      end
    elseif new_parent_path ~= nil then
      if new_parent_path == '' or new_parent_path == nil then
        -- Move to root
        new_parent = catalog
      else
        -- Find new parent collection set by path
        new_parent = CollectionUtils.find_collection_set(catalog, new_parent_path)
      end
      
      if not new_parent then
        Logger.error('Failed to find new parent collection set by path: ' .. tostring(new_parent_path))
        error_msg = 'Failed to find new parent collection set by path: ' .. tostring(new_parent_path)
        task_success = false
        task_completed = true
        WriteLock.release_write_lock('Edit Collection')
        return
      end
    end
    
    -- Perform the collection edit within a single write access context
    local status, err = catalog:withWriteAccessDo('Edit Collection', function(context)
      -- Find the collection within the write access context to ensure proper handling
      local target_collection = nil
      if target_id and target_id ~= '' then
        target_collection = CollectionUtils.find_collection_by_id(catalog, target_id)
      else
        target_collection = CollectionUtils.find_collection_by_path(catalog, target_path)
      end
      
      if not target_collection then
        Logger.debug('Collection not found for editing: ' .. tostring(target_identifier))
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
      if new_parent ~= nil then
        if new_parent ~= target_collection:getParent() then
          target_collection:setParent(new_parent)
          updated = true
          Logger.debug('Collection moved to new parent')
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

    -- Prefer lookup by id if provided
    if target_id and target_id ~= '' then
      re_fetched_collection = CollectionUtils.find_collection_by_id(catalog, target_id)
    end

    if not re_fetched_collection then
      -- Determine original path (may be nil)
      local original_path = target_path

      local search_path = original_path

      if updated then
        -- Compute current name (prefer new_name)
        local current_name = new_name
        if not current_name then
          -- Try to read from the original location
          local tmp = original_path and CollectionUtils.find_collection_by_path(catalog, original_path) or nil
          if tmp then
            current_name = tmp:getName()
          end
        end

        -- Fallback to last segment of original path
        if not current_name and original_path and #original_path > 0 then
          local last = nil
          for part in string.gmatch(original_path, "([^/]+)") do last = part end
          current_name = last
        end

        -- Build new search path depending on move target
        if new_parent_path ~= nil then
          if new_parent_path == '' or new_parent_path == nil then
            search_path = current_name
          else
            search_path = (new_parent_path and #new_parent_path > 0) and (new_parent_path .. "/" .. current_name) or current_name
          end
        else
          -- Only rename
          if original_path and #original_path > 0 then
            -- parent path is original_path minus last segment
            local parent_path_only = nil
            local last_slash = original_path:match(".*()/")
            if last_slash then
              parent_path_only = original_path:sub(1, last_slash - 1)
            end
            if parent_path_only and #parent_path_only > 0 then
              search_path = parent_path_only .. "/" .. current_name
            else
              search_path = current_name
            end
          else
            search_path = current_name
          end
        end
      end

      if search_path and #tostring(search_path) > 0 then
        re_fetched_collection = CollectionUtils.find_collection_by_path(catalog, search_path)
      end
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
    WriteLock.release_write_lock('Edit Collection') -- Ensure lock is released on timeout
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

function CollectionCommands.handle_collection_delete_command(args)
  Logger.info('handle_collection_delete_command called with args: ' .. tostring(args))
  
  local target_id, target_path = nil, nil
  
  if args then
    if type(args) == 'table' then
      target_id = args.id
      target_path = args.path or args.collection_path  -- Accept legacy name
    elseif type(args) == 'string' then
      target_id = Utils.extract_json_value(args, "id")
      target_path = Utils.extract_json_value(args, "path") or Utils.extract_json_value(args, "collection_path")
    end
  end
  
  -- Precedence: id > path
  local target_identifier = nil
  if target_id and target_id ~= '' then
    target_identifier = target_id
    Logger.info('Deleting collection by id: ' .. tostring(target_id))
  elseif target_path and target_path ~= '' then
    target_identifier = target_path
    Logger.info('Deleting collection by path: ' .. tostring(target_path))
  else
    return false, nil, 'Collection id or path is required for delete'
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
    if not WriteLock.acquire_write_lock('Remove Collection') then
      Logger.error('Failed to acquire write lock for collection removal')
      error_msg = 'Failed to acquire write lock for collection removal'
      task_success = false
      task_completed = true
      return
    end
    
    Logger.debug('Starting collection removal - id: ' .. tostring(target_id) .. ', path: ' .. tostring(target_path))
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
      local target_collection = nil
      if target_id and target_id ~= '' then
        target_collection = CollectionUtils.find_collection_by_id(catalog, target_id)
      else
        target_collection = CollectionUtils.find_collection_by_path(catalog, target_path)
      end
      
      if target_collection then
        target_collection:delete()
        removed = true
        Logger.debug('Collection removed successfully: ' .. tostring(target_identifier))
      else
        Logger.debug('Collection not found for removal: ' .. tostring(target_identifier))
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


function CollectionCommands.handle_collection_remove_command(payload_raw)
  Logger.info('handle_collection_remove_command payload_raw: ' .. tostring(payload_raw))
  local args = nil
  if payload_raw and type(payload_raw) == 'string' and #payload_raw > 0 then
    local id = Utils.extract_json_value(payload_raw, "id")
    local path = Utils.extract_json_value(payload_raw, "path") or Utils.extract_json_value(payload_raw, "collection_path")
    args = { id = id, path = path }
    Logger.info('Parsed remove args - id: ' .. tostring(id) .. ', path: ' .. tostring(path))
  end
  return CollectionCommands.handle_collection_delete_command(args)
end

return CollectionCommands
