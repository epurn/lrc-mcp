local Logger = require 'Logger'

local TestAssertions = {}

-- Test result tracking
local test_results = {
  total = 0,
  passed = 0,
  failed = 0,
  tests = {}
}

function TestAssertions.reset_results()
  test_results = {
    total = 0,
    passed = 0,
    failed = 0,
    tests = {}
  }
end

function TestAssertions.get_results()
  return test_results
end

function TestAssertions.assert_true(condition, test_name, message)
  test_results.total = test_results.total + 1
  if condition then
    test_results.passed = test_results.passed + 1
    table.insert(test_results.tests, {name = test_name, passed = true, message = "PASSED"})
    Logger.info("[TEST PASSED] " .. test_name .. " - " .. (message or "Assertion passed"))
    return true
  else
    test_results.failed = test_results.failed + 1
    table.insert(test_results.tests, {name = test_name, passed = false, message = message or "Assertion failed"})
    Logger.error("[TEST FAILED] " .. test_name .. " - " .. (message or "Assertion failed"))
    return false
  end
end

function TestAssertions.assert_equal(actual, expected, test_name, message)
  local passed = (actual == expected)
  return TestAssertions.assert_true(passed, test_name, message or ("Expected: " .. tostring(expected) .. ", Got: " .. tostring(actual)))
end

function TestAssertions.assert_not_nil(value, test_name, message)
  local passed = (value ~= nil)
  return TestAssertions.assert_true(passed, test_name, message or ("Expected non-nil value, got: " .. tostring(value)))
end

function TestAssertions.assert_string_contains(str, substring, test_name, message)
  if type(str) ~= "string" or type(substring) ~= "string" then
    return TestAssertions.assert_true(false, test_name, message or "Both arguments must be strings")
  end
  local passed = (string.find(str, substring) ~= nil)
  return TestAssertions.assert_true(passed, test_name, message or ("String '" .. str .. "' does not contain '" .. substring .. "'"))
end

return TestAssertions
