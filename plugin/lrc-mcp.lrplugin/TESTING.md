# Plugin Test Suite Documentation

## Overview
This document describes how to run and use the in-situ test suite for the lrc-mcp Lightroom plugin.

## Running Tests

### Via Menu Item
1. In Lightroom Classic, go to `File` → `Plug-in Extras`
2. Select `MCP: Run Tests` from the menu
3. A dialog will confirm that the test suite has started
4. Check the plugin logs for detailed results

### Via Command Queue
Tests can also be triggered by sending a `run_tests` command to the plugin command queue:
```json
{
  "type": "run_tests",
  "payload": {},
  "idempotency_key": "test-run-12345"
}
```

## Test Coverage

### Collection Lifecycle Tests
- Create collection at root level
- Verify collection exists after creation
- Remove collection
- Verify collection is gone after removal

### Collection Set Lifecycle Tests
- Create collection set at root level
- Verify collection set exists after creation
- Create collection inside the set
- Verify collection exists in set
- Remove collection set (and contained collections)
- Verify collection set is gone after removal

### Error Path Tests
- Attempt to create collection without name (should fail)
- Attempt to create collection set without name (should fail)
- Attempt to remove non-existent collection (should handle gracefully)
- Attempt to create collection with invalid parent path (should fail)

## Test Results
Test results are logged using the plugin's Logger system:
- **Plugin log file**: `logs/lrc_mcp.log` within the plugin directory
- **Documents log file**: `Documents/lrClassicLogs/lrc_mcp.log`
- **Lightroom console**: Visible in Lightroom's console if enabled

Results are also displayed in a dialog box after test execution.

## Cleanup
The test suite automatically cleans up any collections or collection sets created during testing. Cleanup occurs even if tests fail, ensuring no test artifacts remain in your catalog.

## Asynchronous Execution
Tests run in an asynchronous task (`LrTasks.startAsyncTask`) to avoid blocking the UI thread. Catalog mutations are executed within `catalog:withWriteAccessDo` to ensure proper write access handling.

## Logging
All test results and assertions are logged using `logger.info` as required by the project guidelines. Test passes and failures are clearly marked in the logs.
