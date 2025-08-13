# lrc-mcp Test Suite

This directory contains the test suite for the lrc-mcp project.

## Test Structure

- `unit/` - Unit tests for individual modules (no external dependencies)
- `integration/` - Integration tests that may require services
- `conftest.py` - pytest configuration

## Running Tests

### Unit Tests Only

```bash
pytest tests/unit -v
```

### All Tests

```bash
pytest tests -v
```

### Run with Coverage

```bash
pytest tests --cov=src/lrc_mcp --cov-report=html --cov-report=term
```

## Test Categories

### Unit Tests (`tests/unit`)

Unit tests cover core modules without requiring external dependencies:
- `test_utils.py` - Tests for utility functions
- `test_lrc_bridge.py` - Tests for the Lightroom bridge service
- `test_health.py` - Tests for health check tools
- `test_lightroom.py` - Tests for Lightroom tools
- `test_collections_adapter.py` - Tests for collection management adapters
- `test_lightroom_adapter.py` - Tests for Lightroom launch adapters

### Integration Tests (`tests/integration`)

Integration tests exercise the full system with external dependencies.

## Writing New Tests

1. Place unit tests in `tests/unit/` with descriptive names
2. Use pytest fixtures for test setup/teardown
3. Mock external dependencies using `unittest.mock`
4. Follow the existing test patterns
5. Use descriptive test method names
6. Include both happy path and error path testing

## Test Markers

- `@pytest.mark.unit` - Unit tests (default)
- `@pytest.mark.integration` - Integration tests

## Environment

Tests are designed to run without external dependencies. All I/O is mocked or isolated.
