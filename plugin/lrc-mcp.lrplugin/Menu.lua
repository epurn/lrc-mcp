local LrDialogs = import 'LrDialogs'
local Logger = require 'Logger'
local TestCommands = require 'TestCommands'

Logger.info('Menu: Run Tests invoked')

-- Call test command directly instead of via HTTP
local success, result, error_msg = pcall(function()
  return TestCommands.handle_run_tests_command()
end)

if not success then
  Logger.error('Test command failed with error: ' .. tostring(result))
  LrDialogs.message('Test Suite Error', 'Test command failed: ' .. tostring(result))
  return
end

if success then
  Logger.info('Test command started successfully')
  LrDialogs.message('Test Suite Started', 'Test suite has been started. Check the plugin logs for results.')
else
  local errorMsg = 'Failed to start test suite: ' .. tostring(error_msg)
  Logger.error('Menu run tests failed: ' .. errorMsg)
  LrDialogs.message('Test Suite Error', errorMsg)
end
