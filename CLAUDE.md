# CLAUDE.md - Freqtrade MCP Project Development Guide

## Project Overview

**Freqtrade MCP** is a Model Context Protocol (MCP) server that provides trading strategy development capabilities through Claude Code integration. The project includes an autonomous **LangGraph Strategy Development Agent** that creates, optimizes, and validates profitable trading strategies using multiple LLM providers.

## Core Components

### 1. **MCP Server** (`src/`)
- **Purpose**: Exposes Freqtrade operations through MCP protocol
- **Transport**: stdio-based communication
- **Tools**: Strategy backtesting, hyperopt, data extraction, candle downloading
- **Language**: Python with asyncio

### 2. **Strategy Agent** (`strategy_agent/`)
- **Purpose**: Autonomous strategy development using LangGraph
- **Architecture**: Multi-node workflow with state management
- **LLM Support**: Multiple providers (OpenAI, DeepSeek, Anthropic, etc.)
- **Communication**: stdio MCP for Freqtrade operations

### 3. **Documentation & Examples** (`examples/`, `*.md`)
- **Purpose**: Usage guides, API documentation, development examples
- **Formats**: Markdown documentation, Python scripts, configuration examples

## Development Principles

### Software Engineering Standards

#### **SOLID Principles** (Mandatory)
- **Single Responsibility**: Each class/module has one clear purpose
- **Open/Closed**: Extensible without modifying existing code
- **Liskov Substitution**: Subclasses must be substitutable for base classes
- **Interface Segregation**: Clean, minimal interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

#### **DRY (Don't Repeat Yourself)**
- No duplicate code patterns
- Shared utilities and base classes
- Common configuration management
- Reusable response models

#### **KISS (Keep It Simple, Stupid)**
- Clear, readable code
- Minimal complexity
- Environment variable configuration
- Straightforward error messages

### Code Quality Standards

#### **Type Safety**
```python
# ✅ Good
async def process_data(symbols: List[str], timeframe: str) -> Dict[str, Any]:
    pass

# ❌ Bad
async def process_data(symbols, timeframe):
    pass
```

#### **Error Handling**
```python
# ✅ Good
try:
    result = await risky_operation()
    return result
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

# ❌ Bad
result = await risky_operation()  # No error handling
```

#### **Logging Standards**
```python
# ✅ Good
import logging
logger = logging.getLogger(__name__)

logger.info("Starting operation with %d symbols", len(symbols))
logger.error("Failed to process %s: %s", symbol, error)

# ❌ Bad
print("Starting operation")  # Use logging, not print
logger.info(f"Processing {symbol}")  # Use % formatting for efficiency
```

#### **Documentation**
```python
# ✅ Good
async def fetch_candles(
    symbols: List[str],
    timeframe: str,
    days: int = 365
) -> Dict[str, Any]:
    """
    Fetch historical candle data for trading pairs.
    
    Args:
        symbols: List of trading pair symbols (e.g., ["BTC/USDT:USDT"])
        timeframe: Candle timeframe (e.g., "1h", "4h", "1d")
        days: Number of days to fetch (default: 365)
        
    Returns:
        Dictionary containing OHLCV data and metadata
        
    Raises:
        ValueError: If symbols list is empty
        ConnectionError: If data source is unavailable
    """
    pass

# ❌ Bad
async def fetch_candles(symbols, timeframe, days=365):
    # Fetch data
    pass
```

## Project Structure Rules

### Directory Organization
```
freqtrade_mcp/
├── src/                    # MCP server implementation
│   ├── commands/           # Tool implementations
│   ├── utils/             # Shared utilities
│   ├── config.py          # Configuration management
│   └── server.py          # Main MCP server
├── strategy_agent/        # LangGraph strategy agent
│   ├── nodes/             # Workflow node implementations
│   ├── prompts/           # LLM prompt templates
│   ├── llm_client.py      # Multi-provider LLM factory
│   ├── state.py           # State management
│   └── agent.py           # Main agent orchestration
├── tests/                 # Test suite
├── examples/              # Usage examples and scripts
├── docs/                  # Additional documentation
└── *.md                   # Project documentation
```

### File Naming Conventions
- **Python modules**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Configuration files**: `lowercase.json`, `lowercase.yaml`

### Import Organization
```python
# ✅ Good import order
# 1. Standard library
import asyncio
import logging
from typing import Dict, List, Optional

# 2. Third-party packages
import pandas as pd
from pydantic import BaseModel

# 3. Local imports
from .state import StrategyDevelopmentState
from ..config import config
```

## MCP Server Development Rules

### Tool Implementation Standards

#### **Command Pattern**
```python
# ✅ Good - Follow base command pattern
class NewToolCommand(BaseCommand):
    """Tool for performing specific operation."""
    
    def __init__(self, config: Config, session: Optional[Any] = None):
        super().__init__(config, session)
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool operation."""
        try:
            # Validate inputs
            await self._validate_inputs(kwargs)
            
            # Perform operation
            result = await self._perform_operation(kwargs)
            
            # Return structured response
            return {
                "success": True,
                "data": result,
                "metadata": {"tool": "new_tool", "timestamp": datetime.now().isoformat()}
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _validate_inputs(self, kwargs: Dict[str, Any]) -> None:
        """Validate input parameters."""
        pass
    
    async def _perform_operation(self, kwargs: Dict[str, Any]) -> Any:
        """Perform the actual operation."""
        pass
```

#### **Response Format Standardization**
```python
# ✅ Standard success response
{
    "success": True,
    "data": {...},
    "metadata": {
        "tool": "tool_name",
        "timestamp": "2025-01-01T00:00:00",
        "execution_time_ms": 150
    }
}

# ✅ Standard error response
{
    "success": False,
    "error": "Clear error message",
    "error_type": "ValidationError",
    "metadata": {
        "tool": "tool_name",
        "timestamp": "2025-01-01T00:00:00"
    }
}
```

### MCP Protocol Compliance

#### **Tool Registration**
```python
# ✅ Proper tool registration
@self.server.tool()
async def tool_name(argument1: str, argument2: int = 100) -> str:
    """
    Brief tool description.
    
    Args:
        argument1: Description of required argument
        argument2: Description of optional argument (default: 100)
    """
    command = ToolCommand(self.config, self.session)
    result = await command.execute(argument1=argument1, argument2=argument2)
    return json.dumps(result)
```

#### **Error Handling**
```python
# ✅ MCP-safe error handling
try:
    result = await operation()
    await self.send_log_message(LoggingLevel.INFO, f"Operation completed: {result}")
    return json.dumps({"success": True, "result": result})
except Exception as e:
    await self.send_log_message(LoggingLevel.ERROR, f"Operation failed: {e}")
    return json.dumps({"success": False, "error": str(e)})
```

## Strategy Agent Development Rules

### LangGraph Node Standards

#### **Node Function Signature**
```python
# ✅ Standard node signature
async def node_function(
    state: StrategyDevelopmentState,
    additional_param: Optional[Any] = None
) -> StrategyDevelopmentState:
    """
    Node description.
    
    Args:
        state: Current workflow state
        additional_param: Optional additional parameter
        
    Returns:
        Updated workflow state
    """
    logger.info(f"Starting {node_function.__name__}")
    state["current_step"] = "node_name"
    
    try:
        # Node implementation
        result = await perform_operation(state)
        
        # Update state
        state["result_key"] = result
        
        logger.info(f"Completed {node_function.__name__}")
        return state
        
    except Exception as e:
        logger.error(f"Node {node_function.__name__} failed: {e}")
        state["errors"].append(f"{node_function.__name__}: {str(e)}")
        return state
```

#### **State Management**
```python
# ✅ Proper state updates
state["current_step"] = "operation_name"
state["timestamp"] = datetime.now().isoformat()

# Always append to lists, don't replace
state["errors"].append(new_error)
state["warnings"].append(new_warning)

# Use structured data
state["results"] = {
    "success": True,
    "data": result_data,
    "metadata": metadata
}
```

### LLM Integration Rules

#### **Provider-Agnostic Code**
```python
# ✅ Good - Use factory pattern
def _get_llm_client():
    """Get configured LLM client."""
    return _create_llm_client(config.get_llm_config)

async def generate_content(prompt: str) -> ResponseModel:
    """Generate content using configured LLM."""
    client = _get_llm_client()
    return await client.create_completion(
        messages=[{"role": "user", "content": prompt}],
        response_model=ResponseModel
    )

# ❌ Bad - Hardcoded provider
from openai import AsyncOpenAI
client = AsyncOpenAI(api_key="hardcoded")
```

#### **Structured Responses**
```python
# ✅ Good - Use Pydantic models
class StrategyAnalysis(BaseModel):
    """Structured analysis response."""
    is_profitable: bool
    performance_rating: str
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]

# Generate with structure
analysis = await client.create_completion(
    messages=messages,
    response_model=StrategyAnalysis
)

# ❌ Bad - Unstructured text
response = await client.create_completion(messages=messages)
text = response.choices[0].message.content  # Unstructured
```

## Testing Requirements

### Test Coverage Standards
- **Minimum Coverage**: 80% for new code
- **Critical Paths**: 95% coverage required
- **Integration Tests**: All MCP tools must have integration tests
- **Unit Tests**: All business logic functions must have unit tests

### Test Organization
```python
# ✅ Good test structure
class TestStrategyGenerator:
    """Test strategy generation functionality."""
    
    @pytest.fixture
    async def mock_llm_client(self):
        """Mock LLM client for testing."""
        pass
    
    async def test_generate_strategy_idea_success(self, mock_llm_client):
        """Test successful strategy idea generation."""
        # Arrange
        state = create_test_state()
        
        # Act
        result = await generate_strategy_idea(state)
        
        # Assert
        assert result["success"]
        assert result["strategy_idea"] is not None
        assert isinstance(result["strategy_idea"], StrategyIdea)
    
    async def test_generate_strategy_idea_failure(self, mock_llm_client):
        """Test strategy idea generation failure handling."""
        # Test error scenarios
        pass
```

### Test Data Management
```python
# ✅ Good - Use fixtures for test data
@pytest.fixture
def sample_candle_data():
    """Sample candle data for testing."""
    return {
        "BTC/USDT:USDT": {
            "1h": {
                "open": [50000, 50100, 50200],
                "close": [50100, 50200, 50300],
                "high": [50150, 50250, 50350],
                "low": [49950, 50050, 50150],
                "volume": [100, 150, 120]
            }
        }
    }
```

## Configuration Management

### Environment Variables
```python
# ✅ Good configuration with defaults and validation
class Config:
    def __init__(self):
        # Required settings
        self.llm_api_key = os.getenv("LLM_API_KEY")
        if not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required")
        
        # Optional settings with defaults
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        
        # Backward compatibility
        self.openai_api_key = self.llm_api_key  # Support old variable
```

### Configuration Validation
```python
# ✅ Validate configuration on startup
def validate_config(self) -> bool:
    """Validate configuration completeness and correctness."""
    errors = []
    
    if not self.llm_api_key:
        errors.append("LLM_API_KEY is required")
    
    if not self.llm_model:
        errors.append("LLM_MODEL is required")
    
    if self.llm_temperature < 0 or self.llm_temperature > 2:
        errors.append("LLM_TEMPERATURE must be between 0 and 2")
    
    if errors:
        raise ConfigurationError(f"Configuration errors: {', '.join(errors)}")
    
    return True
```

## Security Guidelines

### API Key Management
```python
# ✅ Good - Environment variables only
api_key = os.getenv("LLM_API_KEY")

# ✅ Good - Mask in logs
logger.info(f"Using API key: {api_key[:8]}...")

# ❌ Bad - Hardcoded keys
api_key = "sk-hardcoded-key"  # Never do this

# ❌ Bad - Full key in logs
logger.info(f"API key: {api_key}")  # Security risk
```

### Input Validation
```python
# ✅ Good - Validate all inputs
def validate_symbol(symbol: str) -> str:
    """Validate trading symbol format."""
    if not isinstance(symbol, str):
        raise ValueError("Symbol must be a string")
    
    if not symbol.strip():
        raise ValueError("Symbol cannot be empty")
    
    # Additional validation logic
    return symbol.strip().upper()
```

### File System Access
```python
# ✅ Good - Restricted paths
def get_strategy_path(strategy_name: str) -> Path:
    """Get validated strategy file path."""
    # Validate strategy name
    if not strategy_name.isalnum():
        raise ValueError("Strategy name must be alphanumeric")
    
    # Ensure within allowed directory
    strategies_dir = Path("user_data/strategies")
    strategy_path = strategies_dir / f"{strategy_name}.py"
    
    # Prevent directory traversal
    if not str(strategy_path.resolve()).startswith(str(strategies_dir.resolve())):
        raise ValueError("Invalid strategy path")
    
    return strategy_path
```

## Performance Guidelines

### Async/Await Best Practices
```python
# ✅ Good - Proper async usage
async def process_multiple_items(items: List[str]) -> List[Dict]:
    """Process multiple items concurrently."""
    tasks = [process_single_item(item) for item in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions in results
    processed_results = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Item processing failed: {result}")
        else:
            processed_results.append(result)
    
    return processed_results

# ❌ Bad - Sequential processing
async def process_multiple_items_bad(items: List[str]) -> List[Dict]:
    results = []
    for item in items:
        result = await process_single_item(item)  # Sequential, slow
        results.append(result)
    return results
```

### Memory Management
```python
# ✅ Good - Memory efficient
async def process_large_dataset(data_stream):
    """Process data in chunks to manage memory."""
    chunk_size = 1000
    async for chunk in data_stream.chunks(chunk_size):
        await process_chunk(chunk)
        # Chunk goes out of scope and gets garbage collected

# ❌ Bad - Load everything into memory
async def process_large_dataset_bad(data_stream):
    all_data = await data_stream.read_all()  # Memory intensive
    await process_chunk(all_data)
```

## Git Workflow

### Commit Message Format
```
type(scope): brief description

Detailed explanation of what and why, not how.

- Bullet points for multiple changes
- Reference issues: Fixes #123
- Breaking changes: BREAKING CHANGE: description
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Branch Naming
- **Feature**: `feat/multi-llm-support`
- **Bugfix**: `fix/strategy-validation-error`
- **Documentation**: `docs/api-reference-update`
- **Refactor**: `refactor/state-management`

### Code Review Checklist
- [ ] Follows SOLID principles
- [ ] Has appropriate tests
- [ ] Includes documentation
- [ ] No hardcoded values
- [ ] Proper error handling
- [ ] Type hints present
- [ ] No security vulnerabilities
- [ ] Performance considerations addressed

## Release Process

### Version Numbering
- **Major**: Breaking changes (X.0.0)
- **Minor**: New features, backward compatible (0.X.0)
- **Patch**: Bug fixes, backward compatible (0.0.X)

### Release Checklist
- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in appropriate files
- [ ] Security review completed
- [ ] Performance benchmarks run

## Maintenance Guidelines

### Code Reviews
- **Required**: All code changes must be reviewed
- **Focus Areas**: Security, performance, maintainability
- **Standards**: Must follow this guide
- **Documentation**: Code must be self-documenting

### Technical Debt Management
- **Regular Refactoring**: Schedule time for code improvement
- **Dependency Updates**: Keep dependencies current
- **Performance Monitoring**: Regular performance assessments
- **Documentation Updates**: Keep docs in sync with code

### Monitoring and Logging
- **Structured Logging**: Use consistent log formats
- **Error Tracking**: Comprehensive error monitoring
- **Performance Metrics**: Track execution times
- **Resource Usage**: Monitor memory and CPU usage

---

## Contact and Support

For questions about this development guide or project architecture:

1. **Check Documentation**: Review existing `.md` files
2. **Search Issues**: Look for similar questions in project issues
3. **Create Issue**: Open a new issue with detailed description
4. **Follow Standards**: Always follow the guidelines in this document

**Remember**: This project serves real trading applications. Code quality, security, and reliability are paramount.