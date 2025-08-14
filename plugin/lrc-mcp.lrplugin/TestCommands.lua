local LrTasks = import 'LrTasks'
local Logger = require 'Logger'
local TestRunner = require 'TestRunner'

local TestCommands = {}

function TestCommands.handle_run_tests_command()
  Logger.info("Test command received - starting test suite")
  
  -- Run tests in async task to avoid blocking UI
  LrTasks.startAsyncTask(function()
    local results, cleanup_success = TestRunner.run_all_tests()
    
    Logger.info("Test suite completed - Total: " .. results.total .. 
                ", Passed: " .. results.passed .. 
                ", Failed: " .. results.failed ..
                ", Cleanup: " .. (cleanup_success and "SUCCESS" or "FAILED"))
  end, 'Run Plugin Tests')
  
  -- Return immediate success response
  return true, { 
    status = "started", 
    message = "Test suite started - check logs for results" 
  }, nil
end

return TestCommands
