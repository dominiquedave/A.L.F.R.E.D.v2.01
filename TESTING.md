# A.L.F.R.E.D. Testing Guide

This document describes the comprehensive testing setup for A.L.F.R.E.D. v2.01, including unit tests, integration tests, coverage reporting, and pre-commit hooks.

## Overview

The testing framework provides:
- **Unit Tests**: Comprehensive tests for individual modules with >80% coverage
- **Integration Tests**: End-to-end functionality testing
- **Coverage Reporting**: Detailed coverage analysis with HTML reports
- **Pre-commit Hooks**: Automated code quality checks on commit
- **Continuous Testing**: Automated test runner with multiple options

## Test Structure

```
tests/
├── __init__.py                     # Test package initialization
├── conftest.py                     # Shared pytest configuration
├── unit/                           # Unit tests for individual modules
│   ├── shared/                     # Tests for shared models
│   │   ├── __init__.py
│   │   └── test_models.py         # Comprehensive model testing
│   ├── agent/                      # Tests for agent functionality
│   │   ├── __init__.py
│   │   └── test_agent.py          # Agent core functionality tests
│   └── coordinator/                # Tests for coordinator modules
│       ├── __init__.py
│       ├── test_coordinator.py     # Core coordinator logic
│       ├── test_coordinator_core.py # Focused core tests
│       ├── test_voice_interface.py # Voice interface testing
│       └── test_web_interface.py   # Web interface testing
└── integration/                    # Integration tests
    ├── __init__.py
    └── test_models_integration.py  # Cross-module integration tests
```

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests with coverage
python run_tests.py

# Run specific test suites
python run_tests.py --unit           # Unit tests only
python run_tests.py --integration    # Integration tests only
python run_tests.py --coverage       # Check coverage requirements
```

### Test Runner Options

The `run_tests.py` script provides comprehensive testing options:

```bash
# Basic testing
python run_tests.py                 # Run tests with coverage
python run_tests.py --no-coverage   # Run tests without coverage

# Code quality
python run_tests.py --format        # Format code with Black and isort
python run_tests.py --lint          # Run linting with flake8
python run_tests.py --all           # Run everything (tests, format, lint)

# Setup and maintenance
python run_tests.py --install-deps  # Install test dependencies
python run_tests.py --install-hooks # Install pre-commit hooks
```

### Direct pytest Usage

```bash
# Run with coverage
pytest --cov=shared --cov=agent --cov=coordinator --cov-report=html

# Run specific test files
pytest tests/unit/shared/test_models.py -v

# Run with specific markers
pytest -m "not slow" -v  # Skip slow tests
```

## Coverage Targets

The project maintains **80%+ code coverage** across core modules:

- **shared/models.py**: 100% coverage ✅
- **agent/core/agent.py**: 79%+ coverage ✅
- **coordinator/core/coordinator.py**: Target 80%+ coverage

Coverage reports are generated in multiple formats:
- **Terminal**: Real-time coverage summary
- **HTML**: Detailed coverage report in `htmlcov/index.html`
- **XML**: Machine-readable coverage for CI/CD

## Test Categories

### Unit Tests

**Shared Models (`tests/unit/shared/test_models.py`)**
- Pydantic model validation and serialization
- Enum value verification
- Error handling and edge cases
- JSON roundtrip testing

**Agent Core (`tests/unit/agent/test_agent.py`)**
- Agent initialization and configuration
- Command validation and security
- HTTP API endpoint testing
- System capability detection
- Health monitoring
- Broadcast discovery protocol

**Coordinator (`tests/unit/coordinator/test_coordinator.py`)**
- Agent registration and management
- Command parsing with OpenAI integration
- Agent selection algorithms
- Health check scheduling
- Network discovery protocols

**Voice Interface (`tests/unit/coordinator/test_voice_interface.py`)**
- Speech recognition integration
- Amazon Polly TTS integration
- Batman-themed UI components
- Voice command processing
- Error handling and fallbacks

**Web Interface (`tests/unit/coordinator/test_web_interface.py`)**
- FastAPI endpoint testing
- WebSocket communication
- Real-time dashboard updates
- Agent status reporting

### Integration Tests

**Model Integration (`tests/integration/test_models_integration.py`)**
- Cross-module data flow
- Real-world usage scenarios
- Complex message handling
- End-to-end serialization

## Pre-commit Hooks

Automated code quality checks run on every commit:

```bash
# Install hooks (one-time setup)
python run_tests.py --install-hooks

# Manual hook execution
pre-commit run --all-files
```

Hook configuration includes:
- **Black**: Code formatting (line length: 100)
- **isort**: Import statement organization
- **flake8**: Code linting and style checking
- **pytest**: Automated test execution on commit
- **Coverage**: 80% coverage requirement on push

## Configuration Files

### pytest.ini
- Test discovery patterns
- Coverage configuration
- Test markers and options
- Asyncio mode settings

### pyproject.toml
- Black formatting configuration
- isort import sorting rules
- Coverage reporting settings
- Project metadata

### .pre-commit-config.yaml
- Hook definitions and versions
- Execution stages (commit/push)
- Custom local hooks for testing

## Best Practices

### Writing Tests

1. **Use descriptive test names** that explain the scenario
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Mock external dependencies** (APIs, file system, network)
4. **Test both success and failure cases**
5. **Use pytest fixtures** for common test data
6. **Test edge cases and error conditions**

### Mock Usage

```python
# Mock external dependencies
@patch('module.external_api_call')
def test_function_with_api(mock_api):
    mock_api.return_value = {"status": "success"}
    result = function_under_test()
    assert result.success is True
```

### Async Testing

```python
# Test async functions
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

## Continuous Integration

The test suite is designed for CI/CD integration:

1. **Fast unit tests** run on every commit
2. **Coverage reports** generated in XML format
3. **Exit codes** indicate test success/failure
4. **Parallel execution** support for faster testing
5. **Detailed logging** for debugging failures

## Troubleshooting

### Common Issues

**ImportError: Module not found**
- Ensure project root is in PYTHONPATH
- Check conftest.py configuration
- Verify virtual environment activation

**Coverage below 80%**
- Add tests for missing code paths
- Use `--cov-report=html` to identify gaps
- Focus on core business logic first

**Pre-commit hook failures**
- Run `python run_tests.py --format` to fix formatting
- Address linting issues with `python run_tests.py --lint`
- Ensure all tests pass before committing

**Mock/patching issues**
- Patch at the import location, not definition location
- Use `spec` parameter for better mock validation
- Consider using `pytest-mock` for simpler syntax

### Debug Mode

Enable verbose testing output:

```bash
pytest -v -s --tb=long  # Verbose output with full tracebacks
pytest --pdb           # Drop into debugger on failure
pytest -k test_name    # Run specific test by name pattern
```

## Contributing

When adding new features:

1. **Write tests first** (TDD approach)
2. **Maintain >80% coverage** for new code
3. **Update integration tests** for cross-module changes
4. **Run full test suite** before submitting PRs
5. **Document complex test scenarios** in docstrings

The testing framework ensures A.L.F.R.E.D. maintains high code quality and reliability across all components.
