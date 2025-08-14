return {
  LrSdkVersion = 14.0,
  LrSdkMinimumVersion = 14.0,
  LrToolkitIdentifier = 'io.github.epurn.lr.lrc_mcp',
  LrPluginName = 'lrc_mcp',
  -- Force Lightroom to run Init.lua on app start/load
  -- Ref: Adobe community thread on LrForceInitPlugin
  -- https://community.adobe.com/t5/lightroom-classic-discussions/how-to-start-plugin-asynctask-on-lightroom-startup/m-p/7560036
  LrForceInitPlugin = true,
  LrInitPlugin = 'Init.lua',
  LrExportMenuItems = {
    {
      title = 'MCP: Loaded',
      file = 'MenuLoaded.lua',
    },
    {
      title = 'MCP: Run Tests',
      file = 'Menu.lua',
    },
  },
  VERSION = { major = 0, minor = 1, revision = 0 },
}
