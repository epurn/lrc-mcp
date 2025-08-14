local LrDialogs = import 'LrDialogs'
local LrHttp = import 'LrHttp'
local Logger = require 'Logger'
local Utils = require 'Utils'

-- Menu handler for "MCP Loaded" - original functionality
local function handle_loaded()
  Logger.info('Menu: MCP Loaded marker invoked')
  LrDialogs.message('MCP Loaded', 'Plugin manifest parsed and menu registered')
end

-- Menu handler for running tests
local function handle_run_tests()
  Logger.info('Menu: Run Tests invoked')
  Logger.info('Attempting to send test command to server')
  
  -- Send test command to the server
  local test_url = 'http://127.0.0.1:8765/plugin/commands/enqueue'
  local test_payload = '{"type":"run_tests","payload":{},"idempotency_key":"test-run-' .. tostring(os.time()) .. '"}'
  
  Logger.info('Test URL: ' .. test_url)
  Logger.info('Test Payload: ' .. test_payload)
  
  local success, respBody, respHdrs = pcall(function()
    return LrHttp.post(test_url, test_payload, Utils.build_headers(), 5)
  end)
  
  if not success then
    Logger.error('HTTP request failed with error: ' .. tostring(respBody))
    LrDialogs.message('Test Suite Error', 'HTTP request failed: ' .. tostring(respBody))
    return
  end
  
  local statusCode = nil
  if respHdrs then
    statusCode = tonumber(respHdrs.status) or tonumber(respHdrs.statusCode) or tonumber(respHdrs.code)
  end
  statusCode = statusCode or 0
  
  Logger.info('HTTP Response Status: ' .. tostring(statusCode))
  Logger.info('HTTP Response Body: ' .. tostring(respBody))
  
  if statusCode >= 200 and statusCode < 300 then
    Logger.info('Test command sent successfully')
    LrDialogs.message('Test Suite Started', 'Test suite has been started. Check the plugin logs for results.')
  else
    local errorMsg = 'Failed to start test suite. Status: ' .. tostring(statusCode) .. '\nBody: ' .. tostring(respBody)
    Logger.error('Menu run tests failed: ' .. errorMsg)
    LrDialogs.message('Test Suite Error', errorMsg)
  end
end

-- For backward compatibility, return the run_tests handler as the default
return handle_run_tests
