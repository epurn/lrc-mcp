local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrDialogs = import 'LrDialogs'
local Logger = require 'Logger'
local TestAssertions = require 'TestAssertions'
local CollectionUtils = require 'CollectionUtils'
local CollectionCommands = require 'CollectionCommands'
local WriteLock = require 'WriteLock'

local TestRunner = {}

-- Test cleanup tracking
local created_test_items = {
  collections = {},
  collection_sets = {}
}

function TestRunner.add_cleanup_item(item_type, path)
  table.insert(created_test_items[item_type], path)
  Logger.info("Added cleanup item: " .. item_type .. " - " .. path)
end

function TestRunner.cleanup_test_items()
  Logger.info("Starting test cleanup...")
  
  local catalog = LrApplication.activeCatalog()
  if not catalog then
    Logger.error("Cannot cleanup - no active catalog")
    return false
  end
  
  local success = true
  
  -- Clean up collections (in reverse order to handle nested structures)
  for i = #created_test_items.collections, 1, -1 do
    local path = created_test_items.collections[i]
    Logger.info("Cleaning up collection: " .. path)
    
    local status, err = catalog:withWriteAccessDo('Test Cleanup', function(context)
      local collection = CollectionUtils.find_collection_by_path(catalog, path)
      if collection then
        pcall(function() collection:delete() end)
        Logger.info("Deleted collection: " .. path)
      else
        Logger.info("Collection not found for cleanup: " .. path)
      end
    end, { timeout = 5 })
    
    if status ~= "executed" then
      Logger.error("Failed to cleanup collection " .. path .. ": " .. tostring(err))
      success = false
    end
  end
  
  -- Clean up collection sets (in reverse order)
  for i = #created_test_items.collection_sets, 1, -1 do
    local path = created_test_items.collection_sets[i]
    Logger.info("Cleaning up collection set: " .. path)
    
    local status, err = catalog:withWriteAccessDo('Test Cleanup', function(context)
      local collection_set = CollectionUtils.find_collection_set(catalog, path)
      if collection_set and collection_set ~= catalog then
        pcall(function() collection_set:delete() end)
        Logger.info("Deleted collection set: " .. path)
      else
        Logger.info("Collection set not found for cleanup: " .. path)
      end
    end, { timeout = 5 })
    
    if status ~= "executed" then
      Logger.error("Failed to cleanup collection set " .. path .. ": " .. tostring(err))
      success = false
    end
  end
  
  -- Reset cleanup tracking
  created_test_items.collections = {}
  created_test_items.collection_sets = {}
  
  Logger.info("Test cleanup completed " .. (success and "successfully" or "with errors"))
  return success
end

-- Test suite functions
function TestRunner.test_collection_lifecycle()
  Logger.info("=== Starting Collection Lifecycle Tests ===")
  TestAssertions.reset_results()
  
  local catalog = LrApplication.activeCatalog()
  if not catalog then
    TestAssertions.assert_true(false, "Collection Lifecycle - Catalog Check", "No active catalog available")
    return
  end
  
  TestAssertions.assert_true(true, "Collection Lifecycle - Catalog Check", "Active catalog found")
  
  -- Test 1: Create collection at root level
  local test_collection_name = "Test_Collection_" .. os.time()
  local create_payload = '{"name":"' .. test_collection_name .. '","parent_path":""}'
  
  local ok, result, err = CollectionCommands.handle_create_collection_command(create_payload)
  TestAssertions.assert_true(ok, "Collection Lifecycle - Create Root Collection", 
    ok and ("Created collection: " .. test_collection_name) or ("Failed to create collection: " .. tostring(err)))
  
  if ok and result and result.collection then
    local created_path = result.collection.path
    TestRunner.add_cleanup_item("collections", created_path)
    
    -- Verify collection exists
    local found_collection = CollectionUtils.find_collection_by_path(catalog, created_path)
    TestAssertions.assert_not_nil(found_collection, "Collection Lifecycle - Verify Creation", 
      "Collection should exist after creation")
    
    if found_collection then
      -- Test 2: Remove collection
      local remove_payload = '{"collection_path":"' .. created_path .. '"}'
      local remove_ok, remove_result, remove_err = CollectionCommands.handle_remove_collection_command(remove_payload)
      TestAssertions.assert_true(remove_ok, "Collection Lifecycle - Remove Collection", 
        remove_ok and "Collection removed successfully" or ("Failed to remove collection: " .. tostring(remove_err)))
      
      if remove_ok then
        -- Verify collection is gone
        local gone_collection = CollectionUtils.find_collection_by_path(catalog, created_path)
        TestAssertions.assert_true(gone_collection == nil, "Collection Lifecycle - Verify Removal", 
          "Collection should not exist after removal")
      end
    end
  end
  
  Logger.info("=== Collection Lifecycle Tests Completed ===")
end

function TestRunner.test_collection_set_lifecycle()
  Logger.info("=== Starting Collection Set Lifecycle Tests ===")
  TestAssertions.reset_results()
  
  local catalog = LrApplication.activeCatalog()
  if not catalog then
    TestAssertions.assert_true(false, "Collection Set Lifecycle - Catalog Check", "No active catalog available")
    return
  end
  
  TestAssertions.assert_true(true, "Collection Set Lifecycle - Catalog Check", "Active catalog found")
  
  -- Test 1: Create collection set at root level
  local test_set_name = "Test_Set_" .. os.time()
  local create_payload = '{"name":"' .. test_set_name .. '","parent_path":""}'
  
  local ok, result, err = CollectionCommands.handle_create_collection_set_command(create_payload)
  TestAssertions.assert_true(ok, "Collection Set Lifecycle - Create Root Set", 
    ok and ("Created collection set: " .. test_set_name) or ("Failed to create collection set: " .. tostring(err)))
  
  if ok and result and result.collection_set then
    local created_path = result.collection_set.path
    TestRunner.add_cleanup_item("collection_sets", created_path)
    
    -- Verify collection set exists
    local found_set = CollectionUtils.find_collection_set(catalog, created_path)
    TestAssertions.assert_not_nil(found_set, "Collection Set Lifecycle - Verify Creation", 
      "Collection set should exist after creation")
    TestAssertions.assert_true(found_set ~= catalog, "Collection Set Lifecycle - Not Root", 
      "Created set should not be the catalog root")
    
    if found_set then
      -- Test 2: Create collection inside the set
      local test_coll_name = "Test_Coll_In_Set_" .. os.time()
      local coll_payload = '{"name":"' .. test_coll_name .. '","parent_path":"' .. created_path .. '"}'
      
      local coll_ok, coll_result, coll_err = CollectionCommands.handle_create_collection_command(coll_payload)
      TestAssertions.assert_true(coll_ok, "Collection Set Lifecycle - Create Collection In Set", 
        coll_ok and ("Created collection in set: " .. test_coll_name) or ("Failed to create collection: " .. tostring(coll_err)))
      
      if coll_ok and coll_result and coll_result.collection then
        local coll_path = coll_result.collection.path
        TestRunner.add_cleanup_item("collections", coll_path)
        
        -- Verify collection exists in set
        local found_coll = CollectionUtils.find_collection_by_path(catalog, coll_path)
        TestAssertions.assert_not_nil(found_coll, "Collection Set Lifecycle - Verify Collection In Set", 
          "Collection should exist in collection set")
      end
      
      -- Test 3: Remove collection set (should also remove contained collections)
      local remove_payload = '{"collection_path":"' .. created_path .. '"}'
      local remove_ok, remove_result, remove_err = CollectionCommands.handle_remove_collection_command(remove_payload)
      TestAssertions.assert_true(remove_ok, "Collection Set Lifecycle - Remove Set", 
        remove_ok and "Collection set removed successfully" or ("Failed to remove collection set: " .. tostring(remove_err)))
      
      if remove_ok then
        -- Verify collection set is gone
        local gone_set = CollectionUtils.find_collection_set(catalog, created_path)
        TestAssertions.assert_true(gone_set == nil or gone_set == catalog, "Collection Set Lifecycle - Verify Removal", 
          "Collection set should not exist after removal")
      end
    end
  end
  
  Logger.info("=== Collection Set Lifecycle Tests Completed ===")
end

function TestRunner.test_error_paths()
  Logger.info("=== Starting Error Path Tests ===")
  TestAssertions.reset_results()
  
  -- Test 1: Create collection without name (should fail)
  local no_name_payload = '{"name":"","parent_path":""}'
  local ok, result, err = CollectionCommands.handle_create_collection_command(no_name_payload)
  TestAssertions.assert_true(not ok, "Error Paths - Create Collection No Name", 
    not ok and "Should fail when collection name is empty" or "Unexpectedly succeeded with empty name")
  TestAssertions.assert_string_contains(tostring(err), "required", "Error Paths - Error Message Check", 
    "Error message should mention that name is required")
  
  -- Test 2: Create collection set without name (should fail)
  local no_set_name_payload = '{"name":"","parent_path":""}'
  local set_ok, set_result, set_err = CollectionCommands.handle_create_collection_set_command(no_set_name_payload)
  TestAssertions.assert_true(not set_ok, "Error Paths - Create Set No Name", 
    not set_ok and "Should fail when collection set name is empty" or "Unexpectedly succeeded with empty name")
  TestAssertions.assert_string_contains(tostring(set_err), "required", "Error Paths - Set Error Message Check", 
    "Error message should mention that name is required")
  
  -- Test 3: Remove non-existent collection (should not fail catastrophically)
  local fake_path = "NonExistent/Collection_" .. os.time()
  local remove_payload = '{"collection_path":"' .. fake_path .. '"}'
  local remove_ok, remove_result, remove_err = CollectionCommands.handle_remove_collection_command(remove_payload)
  TestAssertions.assert_true(remove_ok, "Error Paths - Remove Non-existent", 
    remove_ok and "Should handle non-existent collection gracefully" or ("Failed unexpectedly: " .. tostring(remove_err)))
  
  -- Test 4: Create collection with invalid parent (should fail)
  local invalid_parent_payload = '{"name":"Test_Invalid_Parent_' .. os.time() .. '","parent_path":"NonExistent/Parent"}'
  local invalid_ok, invalid_result, invalid_err = CollectionCommands.handle_create_collection_command(invalid_parent_payload)
  TestAssertions.assert_true(not invalid_ok, "Error Paths - Invalid Parent", 
    not invalid_ok and "Should fail with invalid parent path" or "Unexpectedly succeeded with invalid parent")
  
  Logger.info("=== Error Path Tests Completed ===")
end

function TestRunner.run_all_tests()
  Logger.info("=== Starting Plugin Test Suite ===")
  
  -- Reset cleanup tracking
  created_test_items.collections = {}
  created_test_items.collection_sets = {}
  
  -- Run all test suites
  TestRunner.test_collection_lifecycle()
  TestRunner.test_collection_set_lifecycle()
  TestRunner.test_error_paths()
  
  -- Cleanup
  local cleanup_success = TestRunner.cleanup_test_items()
  
  -- Report results
  local results = TestAssertions.get_results()
  local summary = string.format(
    "=== Test Suite Summary ===\n" ..
    "Total Tests: %d\n" ..
    "Passed: %d\n" ..
    "Failed: %d\n" ..
    "Cleanup: %s",
    results.total, results.passed, results.failed, 
    cleanup_success and "SUCCESS" or "FAILED"
  )
  
  Logger.info(summary)
  
  -- Show dialog with results
  LrDialogs.message("Plugin Test Results", summary)
  
  return results, cleanup_success
end

return TestRunner
