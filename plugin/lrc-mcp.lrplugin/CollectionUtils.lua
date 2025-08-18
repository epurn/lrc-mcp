local LrApplication = import 'LrApplication'

local CollectionUtils = {}

-- Collection utilities
function CollectionUtils.parse_json_string(str)
  if not str then return nil end
  -- Remove surrounding quotes and unescape
  local result = str:gsub('^"', ''):gsub('"$', '')
  result = result:gsub('\\"', '"'):gsub('\\\\', '\\')
  return result
end

function CollectionUtils.find_collection_set(catalog, path)
  -- Handle nil, empty string, or missing path - all mean root level (catalog)
  if not path or path == '' then
    return catalog
  end
  
  local parts = {}
  for part in string.gmatch(path, "([^/]+)") do
    table.insert(parts, part)
  end
  
  local current = catalog
  for i, part in ipairs(parts) do
    local found = nil
    for _, coll_set in ipairs(current:getChildCollectionSets()) do
      if coll_set:getName() == part then
        found = coll_set
        break
      end
    end
    if not found then
      return nil  -- Collection set not found
    end
    current = found
  end
  return current
end

function CollectionUtils.get_collection_set_path_for_creation(catalog, path)
  -- Handle nil, empty string, or missing path - all mean root level (catalog)
  if not path or path == '' then
    return catalog, {}
  end
  
  local parts = {}
  for part in string.gmatch(path, "([^/]+)") do
    table.insert(parts, part)
  end
  
  local current = catalog
  local missing_start_index = nil
  
  -- Traverse existing collection sets to find where we need to start creating
  for i, part in ipairs(parts) do
    local found = nil
    for _, coll_set in ipairs(current:getChildCollectionSets()) do
      if coll_set:getName() == part then
        found = coll_set
        break
      end
    end
    if not found then
      missing_start_index = i
      break
    else
      current = found
    end
  end
  
  -- If all collection sets exist, return the final one
  if not missing_start_index then
    return current, {}
  end
  
  -- Return the last found collection set and the remaining parts that need to be created
  local to_create_names = {}
  for i = missing_start_index, #parts do
    table.insert(to_create_names, parts[i])
  end
  
  return current, to_create_names
end

function CollectionUtils.create_missing_collection_sets(catalog, to_create)
  local last_created = nil
  for i, item in ipairs(to_create) do
    local new_set = item.parent:createCollectionSet(item.name)
    last_created = new_set
  end
  return last_created
end

function CollectionUtils.find_collection_by_path(catalog, path)
  -- Handle nil, empty string, or missing path - all mean no collection can be found
  if not path or path == '' then
    return nil
  end
  
  local parts = {}
  for part in string.gmatch(path, "([^/]+)") do
    table.insert(parts, part)
  end
  
  if #parts == 0 then
    return nil
  end
  
  -- Navigate to parent collection (if any)
  local current = catalog
  for i = 1, #parts - 1 do
    local found = nil
    for _, coll_set in ipairs(current:getChildCollectionSets()) do
      if coll_set:getName() == parts[i] then
        found = coll_set
        break
      end
    end
    if not found then
      return nil  -- Parent not found
    end
    current = found
  end
  
  -- Find the target collection
  local target_name = parts[#parts]
  for _, coll in ipairs(current:getChildCollections()) do
    if coll:getName() == target_name then
      return coll
    end
  end
  
  return nil  -- Collection not found
end

function CollectionUtils.get_collection_path(catalog, collection)
  local path_parts = {}
  local parent = collection:getParent()
  while parent and parent ~= catalog do
    table.insert(path_parts, 1, parent:getName())
    parent = parent:getParent()
  end
  table.insert(path_parts, collection:getName())
  return table.concat(path_parts, "/")
end

-- Find a collection set by its localIdentifier (string)
function CollectionUtils.find_collection_set_by_id(catalog, target_id)
  if not target_id or target_id == '' then return nil end
  -- Depth-first search of collection sets
  local function dfs_set(node)
    local child_sets = node:getChildCollectionSets()
    if child_sets then
      for _, coll_set in ipairs(child_sets) do
        if tostring(coll_set.localIdentifier) == tostring(target_id) then
          return coll_set
        end
        local found = dfs_set(coll_set)
        if found then return found end
      end
    end
    return nil
  end
  return dfs_set(catalog)
end

-- Find a collection by its localIdentifier (string) by scanning all sets
function CollectionUtils.find_collection_by_id(catalog, target_id)
  if not target_id or target_id == '' then return nil end
  -- Search collections under the catalog and all nested sets
  local function scan_collections(node)
    local cols = node:getChildCollections()
    if cols then
      for _, coll in ipairs(cols) do
        if tostring(coll.localIdentifier) == tostring(target_id) then
          return coll
        end
      end
    end
    local child_sets = node:getChildCollectionSets()
    if child_sets then
      for _, coll_set in ipairs(child_sets) do
        local found = scan_collections(coll_set)
        if found then return found end
      end
    end
    return nil
  end
  return scan_collections(catalog)
end

return CollectionUtils
