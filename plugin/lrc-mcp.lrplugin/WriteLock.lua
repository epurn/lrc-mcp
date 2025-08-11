local LrTasks = import 'LrTasks'
local Logger = require 'Logger'

local WriteLock = {}

-- Write operation lock
WriteLock.write_operation_in_progress = false
WriteLock.write_operation_lock = {}

function WriteLock.acquire_write_lock(operation_name)
  local timeout = 10  -- Reduced timeout to 10 seconds
  local elapsed = 0
  local poll_interval = 0.05  -- Reduced poll interval to 50ms
  
  while WriteLock.write_operation_in_progress and elapsed < timeout do
    LrTasks.sleep(poll_interval)
    elapsed = elapsed + poll_interval
  end
  
  if WriteLock.write_operation_in_progress then
    Logger.error('Write lock timeout for operation: ' .. tostring(operation_name))
    return false
  end
  
  WriteLock.write_operation_in_progress = true
  Logger.debug('Acquired write lock for operation: ' .. tostring(operation_name))
  return true
end

function WriteLock.release_write_lock(operation_name)
  WriteLock.write_operation_in_progress = false
  Logger.debug('Released write lock for operation: ' .. tostring(operation_name))
end

return WriteLock
