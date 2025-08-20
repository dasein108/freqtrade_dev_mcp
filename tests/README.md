# Freqtrade MCP Test Suite

This directory contains comprehensive unit and integration tests for the Freqtrade MCP (Model Context Protocol) system.

## Test Structure

```
tests/
├── conftest.py                    # Shared pytest fixtures and configuration
├── unit/                          # Unit tests for individual components
│   ├── test_base_models.py        # Pydantic model validation tests
│   ├── test_base_command.py       # Base command functionality tests
│   ├── test_download_candles.py   # Download candles command tests
│   ├── test_read_candles.py       # Read candles command tests  
│   ├── test_mcp_server.py         # MCP server functionality tests
│   └── test_mcp_client.py         # MCP client functionality tests
├── integration/                   # Integration tests for full workflows
│   └── test_mcp_integration.py    # Server-client communication tests
└── README.md                      # This file
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-asyncio
```

### Run All Tests
```bash
# Run all tests with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov=strategy_agent --cov-report=html

# Run specific test file
pytest tests/unit/test_base_models.py -v

# Run specific test
pytest tests/unit/test_base_models.py::TestMCPBaseResponse::test_valid_response -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

## Test Categories

### Unit Tests

#### **test_base_models.py**
- Tests all Pydantic models for validation and schema consistency
- Validates required fields, default values, and strict field validation
- Tests utility functions for creating standard responses
- Ensures `extra = "forbid"` prevents schema drift

#### **test_base_command.py**
- Tests the base command functionality and abstract interface
- Tests MCP logging integration and error handling
- Tests Freqtrade config generation and command execution
- Tests timeout and exception handling for subprocess operations

#### **test_download_candles.py**
- Tests download command with various parameters and exchanges
- Tests pair processing (single, list, "top15" with fallback)
- Tests timeframe processing ("all", single, list)
- Tests cache filename generation with proper format
- Tests both package-based and CLI-based download methods
- Tests error handling and command execution failure scenarios

#### **test_read_candles.py**
- Tests reading candle data from cache files
- Tests filename parsing for different pair formats (spot/futures)
- Tests handling of multiple cache files
- Tests conversion from freqtrade OHLCV format to structured format
- Tests file not found and JSON parsing error handling
- Tests absolute and relative file path handling

#### **test_mcp_server.py**
- Tests MCP server initialization and tool registration
- Tests download_candles and read_candles tool endpoints
- Tests error handling and JSON serialization consistency
- Tests MCP logging integration

#### **test_mcp_client.py**
- Tests MCP client communication with server
- Tests Pydantic model validation of server responses
- Tests error handling for connection failures and invalid responses
- Tests multiple cache file processing

### Integration Tests

#### **test_mcp_integration.py**
- Tests complete download→read candles workflow
- Tests schema validation consistency between server and client
- Tests error handling consistency across all tools
- Tests multiple file processing integration
- Tests filename parsing for different symbol formats
- Tests JSON serialization consistency for all response types

## Test Data and Fixtures

### Shared Fixtures (conftest.py)

- **`temp_data_dir`**: Temporary directory for test data files
- **`test_config`**: Mock configuration with test-specific settings
- **`mock_mcp_server`**: Mock MCP server instance for testing
- **`sample_ohlcv_data`**: Standard OHLCV data in freqtrade format
- **`sample_cache_files`**: Standard cache filenames for testing
- **`sample_pairs`**: Mix of spot and futures trading pairs

### Test Data Patterns

Tests use consistent data patterns:
- **Cache filenames**: `symbol-timeframe-daterange.json` format
- **OHLCV data**: Standard 6-element arrays `[timestamp, o, h, l, c, v]`
- **Symbol formats**: Both spot (`BTC/USDT`) and futures (`BTC/USDT:USDT`)
- **Timeframes**: Standard freqtrade timeframes (`5m`, `1h`, `4h`, `1d`)

## Test Coverage Requirements

All tests must maintain high coverage standards:
- **Unit tests**: Minimum 85% coverage for individual modules
- **Integration tests**: Must cover all critical user workflows
- **Error handling**: All exception paths must be tested
- **Schema validation**: All Pydantic models must be thoroughly tested

## Mock Strategy

Tests use comprehensive mocking to avoid external dependencies:
- **File operations**: Mocked with temporary directories and mock file content
- **Network calls**: Mocked MCP client/server communication
- **Subprocess execution**: Mocked freqtrade command execution
- **External APIs**: Mocked CoinGecko and exchange API calls

## Assertions and Validation

Tests validate multiple aspects:
- **Response structure**: Correct JSON structure and required fields
- **Data types**: Proper type conversion and validation
- **Business logic**: Correct processing of trading pairs, timeframes, etc.
- **Error handling**: Appropriate error messages and fallback behavior
- **Performance**: Reasonable execution times and resource usage

## Continuous Integration

Tests are designed to run in CI/CD environments:
- No external dependencies or network calls
- Deterministic test data and expected outcomes
- Proper cleanup of temporary resources
- Clear error messages and failure diagnostics

## Adding New Tests

When adding new MCP tools or features:

1. **Create unit tests** for the new component
2. **Add integration tests** for user workflows
3. **Update fixtures** if new test data patterns are needed
4. **Update this README** with new test descriptions
5. **Ensure schema validation** tests for any new Pydantic models

### Test Template

```python
@pytest.mark.asyncio
async def test_new_feature_success(self, fixture_name):
    """Test successful execution of new feature."""
    # Arrange
    input_data = {"param": "value"}
    expected_result = {"success": True}
    
    # Act
    result = await component.execute(**input_data)
    
    # Assert
    assert result["success"] is True
    assert result["param"] == expected_result["param"]
    
    # Validate with Pydantic model if applicable
    validated_result = ResponseModel(**result)
    assert validated_result.success is True
```

## Performance Testing

While not included in the current suite, consider adding:
- **Load testing**: Multiple concurrent MCP calls
- **Memory testing**: Large dataset processing
- **Timeout testing**: Long-running operations

## Security Testing

Security considerations tested:
- **Input validation**: All user inputs are properly validated
- **Path traversal**: File operations are constrained to allowed directories
- **Schema enforcement**: Strict Pydantic models prevent injection attacks