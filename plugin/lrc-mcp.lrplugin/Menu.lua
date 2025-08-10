local LrDialogs = import 'LrDialogs'
local Logger = require 'Logger'

return function()
  Logger.info('Menu: MCP Loaded marker invoked')
  LrDialogs.message('MCP Loaded', 'Plugin manifest parsed and menu registered')
end


