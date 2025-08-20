# Freqtrade MCP Tools Documentation

## Overview

The Freqtrade MCP Server provides a comprehensive set of 13 tools for algorithmic trading strategy development, backtesting, optimization, and analysis. This document details each available tool, its parameters, and expected return values.

---

## Table of Contents

1. [Data Management Tools](#data-management-tools)
   - [download_candles](#1-download_candles)
   - [read_candles](#2-read_candles)
2. [Strategy Creation Tools](#strategy-creation-tools)
   - [create_strategy](#3-create_strategy)
   - [create_strategy_wireframe](#4-create_strategy_wireframe)
3. [Testing & Optimization Tools](#testing--optimization-tools)
   - [backtest_strategy](#5-backtest_strategy)
   - [hyperopt_strategy](#6-hyperopt_strategy)
4. [Results Analysis Tools](#results-analysis-tools)
   - [list_results](#7-list_results)
   - [get_result](#8-get_result)
   - [search_results](#9-search_results)
   - [extract_backtest_data](#10-extract_backtest_data)
   - [extract_hyperopt_data](#11-extract_hyperopt_data)
5. [Configuration Tools](#configuration-tools)
   - [create_userdir](#12-create_userdir)
   - [create_config](#13-create_config)

---

## Data Management Tools

### 1. download_candles

**Description:** Download historical candle data and return cache filenames (format: symbol-tf-timerange.json).

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pairs` | array[string] | Yes | - | List of trading pairs (e.g., ["BTC/USDT:USDT"]) or "top15" for top market cap coins |
| `timeframes` | array[string] | Yes | - | List of timeframes (5m, 15m, 30m, 1h, 4h, 1d) or "all" |
| `date_range` | string | Yes | - | Natural language date range (e.g., "last year", "september", "last 3 months") |
| `exchange` | string | No | "binance" | Exchange name |
| `trading_mode` | string | No | auto | Trading mode: "spot" or "futures" (auto-detected from pairs if not specified) |

#### Return Value

```json
{
  "command": "download_candles",
  "success": true,
  "exchange": "binance",
  "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "timeframes": ["1h", "4h"],
  "date_range": "2024-01-01 to 2025-01-01",
  "timerange": "20240101-20250101",
  "total_downloads": 4,
  "successful": 4,
  "failed": 0,
  "results": [
    {
      "timeframe": "1h",
      "pairs_count": 2,
      "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
      "successful_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
      "failed_pairs": [],
      "success": true,
      "cache_files": [
        {
          "pair": "BTC/USDT:USDT",
          "filename": "BTC_USDT_USDT-1h-20240101-20250101.json",
          "full_path": "/path/to/data/BTC_USDT_USDT-1h-20240101-20250101.json",
          "candle_count": 8760
        },
        {
          "pair": "ETH/USDT:USDT",
          "filename": "ETH_USDT_USDT-1h-20240101-20250101.json",
          "full_path": "/path/to/data/ETH_USDT_USDT-1h-20240101-20250101.json",
          "candle_count": 8760
        }
      ],
      "candle_count": 17520
    }
  ]
}
```

### 2. read_candles

**Description:** Read candle data from cache files created by download_candles.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cache_files` | array[string] | Yes | - | List of cache filenames to read (format: symbol-tf-timerange.json) |

#### Return Value

```json
{
  "command": "read_candles",
  "success": true,
  "files_requested": 2,
  "files_read": 2,
  "files_failed": 0,
  "total_candles": 17520,
  "candle_data": {
    "BTC/USDT:USDT": {
      "1h": {
        "symbol": "BTC/USDT:USDT",
        "timeframe": "1h",
        "timerange": "20240101-20250101",
        "data": {
          "open": {"0": 50000, "1": 50100, ...},
          "high": {"0": 50500, "1": 50600, ...},
          "low": {"0": 49500, "1": 49600, ...},
          "close": {"0": 50100, "1": 50200, ...},
          "volume": {"0": 1000, "1": 1100, ...},
          "timestamp": {"0": 1704067200, "1": 1704070800, ...}
        },
        "candle_count": 8760,
        "cache_file": "BTC_USDT_USDT-1h-20240101-20250101.json"
      }
    },
    "ETH/USDT:USDT": {
      "1h": {
        "symbol": "ETH/USDT:USDT",
        "timeframe": "1h",
        "timerange": "20240101-20250101",
        "data": {
          "open": {"0": 3000, "1": 3010, ...},
          "high": {"0": 3050, "1": 3060, ...},
          "low": {"0": 2950, "1": 2960, ...},
          "close": {"0": 3010, "1": 3020, ...},
          "volume": {"0": 500, "1": 550, ...},
          "timestamp": {"0": 1704067200, "1": 1704070800, ...}
        },
        "candle_count": 8760,
        "cache_file": "ETH_USDT_USDT-1h-20240101-20250101.json"
      }
    }
  },
  "successful_reads": [
    {
      "file": "BTC_USDT_USDT-1h-20240101-20250101.json",
      "symbol": "BTC/USDT:USDT",
      "timeframe": "1h",
      "candle_count": 8760
    },
    {
      "file": "ETH_USDT_USDT-1h-20240101-20250101.json",
      "symbol": "ETH/USDT:USDT",
      "timeframe": "1h",
      "candle_count": 8760
    }
  ],
  "failed_reads": []
}
```

---

## Strategy Creation Tools

### 3. create_strategy

**Description:** Create a new Freqtrade trading strategy from predefined templates.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | string | Yes | - | Name of the strategy class and file |
| `strategy_path` | string | No | user_data/strategies | Custom path for strategy file |
| `template` | string | No | "basic" | Template: "basic", "trend", "mean_reversion", "scalping", "advanced" |
| `timeframe` | string | No | "5m" | Primary timeframe for the strategy |
| `indicators` | array[string] | No | [] | List of technical indicators to include |
| `can_short` | boolean | No | false | Whether the strategy can short sell |
| `minimal_roi` | object | No | default | ROI table configuration |
| `stoploss` | number | No | -0.10 | Stop loss percentage (negative value) |
| `trailing_stop` | boolean | No | false | Enable trailing stop |
| `description` | string | No | "" | Strategy description |

#### Return Value

```json
{
  "command": "create_strategy",
  "success": true,
  "strategy_name": "MyTrendStrategy",
  "file_path": "/path/to/user_data/strategies/MyTrendStrategy.py",
  "template_used": "trend",
  "features": {
    "timeframe": "1h",
    "indicators": ["RSI", "MACD", "BB"],
    "can_short": false,
    "trailing_stop": true
  },
  "message": "Strategy 'MyTrendStrategy' created successfully",
  "code_preview": "# First 500 characters of generated code..."
}
```

### 4. create_strategy_wireframe

**Description:** Create a minimal strategy wireframe for maximum LLM flexibility when generating custom strategies.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | string | Yes | - | Name of the strategy class and file |
| `strategy_path` | string | No | user_data/strategies | Custom path for strategy file |
| `style` | string | No | "minimal" | Wireframe style: "minimal", "guided", "structured" |
| `include_comments` | boolean | No | true | Include TODO comments and guidance |
| `include_examples` | boolean | No | false | Include example code snippets |
| `description` | string | No | "" | Strategy description to include in docstring |

#### Return Value

```json
{
  "command": "create_strategy_wireframe",
  "success": true,
  "strategy_name": "CustomStrategy",
  "file_path": "/path/to/user_data/strategies/CustomStrategy.py",
  "style": "minimal",
  "features": {
    "include_comments": true,
    "include_examples": false,
    "methods": ["populate_indicators", "populate_entry_trend", "populate_exit_trend"]
  },
  "message": "Strategy wireframe 'CustomStrategy' created successfully"
}
```

---

## Testing & Optimization Tools

### 5. backtest_strategy

**Description:** Run backtest for a strategy with specified parameters.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | string | Yes | - | Name of the strategy to backtest |
| `pairs` | array[string] | Yes | - | Trading pairs to test |
| `timerange` | string | Yes | - | Natural language date range for backtesting |
| `stake_amount` | number | No | 100 | Amount to stake per trade |
| `enable_protections` | boolean | No | false | Enable trading protections |
| `export_trades` | boolean | No | true | Export detailed trade data |
| `export_signals` | boolean | No | true | Export entry/exit signals |

#### Return Value

```json
{
  "command": "backtest_strategy",
  "success": true,
  "strategy": "MyTrendStrategy",
  "result_id": "backtest_20250118_143025_MyTrendStrategy",
  "result_file": "/path/to/user_data/backtest_results/backtest-result-2025-01-18_14-30-25.zip",
  "performance": {
    "total_profit_pct": 15.42,
    "total_profit_abs": 1542.0,
    "total_trades": 156,
    "winning_trades": 98,
    "losing_trades": 58,
    "win_rate": 0.628,
    "sharpe_ratio": 1.25,
    "max_drawdown_pct": 8.3,
    "avg_profit_pct": 0.099,
    "avg_duration": "4:15:00"
  },
  "pairs_summary": {
    "BTC/USDT:USDT": {
      "profit_pct": 8.5,
      "trades": 78,
      "win_rate": 0.641
    },
    "ETH/USDT:USDT": {
      "profit_pct": 6.92,
      "trades": 78,
      "win_rate": 0.615
    }
  },
  "timerange_used": "20240101-20250101",
  "duration_seconds": 45.2
}
```

### 6. hyperopt_strategy

**Description:** Run hyperparameter optimization for a strategy.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `strategy_name` | string | Yes | - | Name of the strategy to optimize |
| `pairs` | array[string] | Yes | - | Trading pairs for optimization |
| `timerange` | string | Yes | - | Natural language date range |
| `epochs` | integer | No | 100 | Number of optimization epochs |
| `spaces` | string | No | "all" | Spaces to optimize: "all", "buy", "sell", "roi", "stoploss" |
| `loss_function` | string | No | "ShortTradeDurHyperOptLoss" | Loss function to use |

#### Return Value

```json
{
  "command": "hyperopt_strategy",
  "success": true,
  "strategy": "MyTrendStrategy",
  "result_id": "hyperopt_20250118_143525_MyTrendStrategy",
  "result_file": "/path/to/user_data/hyperopt_results/hyperopt-2025-01-18_14-35-25.fthypt",
  "best_result": {
    "loss": -15.42,
    "profit_pct": 18.65,
    "total_trades": 142,
    "win_rate": 0.683,
    "sharpe_ratio": 1.42,
    "max_drawdown_pct": 6.8
  },
  "best_params": {
    "buy": {
      "buy_rsi": 28,
      "buy_rsi_enabled": true,
      "buy_macd_enabled": true
    },
    "sell": {
      "sell_rsi": 72,
      "sell_rsi_enabled": true
    },
    "roi": {
      "0": 0.15,
      "10": 0.08,
      "30": 0.03,
      "60": 0
    },
    "stoploss": -0.085,
    "trailing": {
      "trailing_stop": true,
      "trailing_stop_positive": 0.01,
      "trailing_stop_positive_offset": 0.02
    }
  },
  "optimization_stats": {
    "total_epochs": 100,
    "best_epoch": 73,
    "duration_minutes": 12.5,
    "avg_time_per_epoch": 7.5
  }
}
```

---

## Results Analysis Tools

### 7. list_results

**Description:** List available backtest and hyperopt results.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `result_type` | string | No | "all" | Type of results: "backtest", "hyperopt", "all" |
| `strategy` | string | No | - | Filter by strategy name |
| `limit` | integer | No | 20 | Maximum number of results to return |

#### Return Value

```json
{
  "command": "list_results",
  "success": true,
  "results": [
    {
      "id": "backtest_20250118_143025_MyTrendStrategy",
      "type": "backtest",
      "strategy": "MyTrendStrategy",
      "timestamp": "2025-01-18T14:30:25",
      "file_path": "/path/to/backtest-result.zip",
      "summary": {
        "profit_pct": 15.42,
        "trades": 156,
        "win_rate": 0.628
      }
    },
    {
      "id": "hyperopt_20250118_143525_MyTrendStrategy",
      "type": "hyperopt",
      "strategy": "MyTrendStrategy",
      "timestamp": "2025-01-18T14:35:25",
      "file_path": "/path/to/hyperopt-result.fthypt",
      "summary": {
        "best_profit": 18.65,
        "epochs": 100,
        "best_epoch": 73
      }
    }
  ],
  "total_results": 2,
  "filtered_count": 2
}
```

### 8. get_result

**Description:** Retrieve a specific result by ID.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `result_id` | string | Yes | - | ID of the result to retrieve |
| `include_metadata` | boolean | No | true | Include metadata in response |

#### Return Value

```json
{
  "command": "get_result",
  "success": true,
  "result": {
    "id": "backtest_20250118_143025_MyTrendStrategy",
    "type": "backtest",
    "strategy": "MyTrendStrategy",
    "timestamp": "2025-01-18T14:30:25",
    "file_path": "/path/to/backtest-result.zip",
    "file_size": 245678,
    "metadata": {
      "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
      "timerange": "20240101-20250101",
      "stake_amount": 100,
      "configuration": {
        "max_open_trades": 3,
        "stake_currency": "USDT"
      }
    },
    "performance": {
      "total_profit_pct": 15.42,
      "total_trades": 156,
      "win_rate": 0.628,
      "sharpe_ratio": 1.25
    }
  }
}
```

### 9. search_results

**Description:** Search and filter backtest and hyperopt results with advanced criteria.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | No | - | Free text search query |
| `result_type` | string | No | "all" | Type: "all", "backtest", "hyperopt" |
| `strategy_name` | string | No | - | Filter by strategy name |
| `min_profit` | number | No | - | Minimum profit percentage |
| `max_drawdown` | number | No | - | Maximum drawdown percentage |
| `min_trades` | integer | No | - | Minimum number of trades |
| `min_winrate` | number | No | - | Minimum win rate (0-1) |
| `date_from` | string | No | - | Start date filter (YYYY-MM-DD) |
| `date_to` | string | No | - | End date filter (YYYY-MM-DD) |
| `sort_by` | string | No | "date" | Sort by: "date", "profit", "winrate", "trades", "drawdown" |
| `sort_order` | string | No | "desc" | Sort order: "asc", "desc" |
| `limit` | integer | No | 20 | Maximum results to return |
| `include_summary` | boolean | No | true | Include performance summaries |
| `rebuild_index` | boolean | No | false | Force rebuild of search index |

#### Return Value

```json
{
  "command": "search_results",
  "success": true,
  "query": "profit > 10",
  "matches": [
    {
      "id": "backtest_20250118_143025_MyTrendStrategy",
      "type": "backtest",
      "strategy": "MyTrendStrategy",
      "timestamp": "2025-01-18T14:30:25",
      "relevance_score": 0.95,
      "summary": {
        "profit_pct": 15.42,
        "trades": 156,
        "win_rate": 0.628,
        "sharpe_ratio": 1.25,
        "max_drawdown_pct": 8.3
      },
      "matched_criteria": ["min_profit"]
    }
  ],
  "total_matches": 1,
  "search_stats": {
    "total_searched": 45,
    "execution_time_ms": 125,
    "index_used": true
  }
}
```

### 10. extract_backtest_data

**Description:** Extract and analyze data from backtest result .zip files.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `result_path` | string | Yes | - | Path to the backtest result .zip file |
| `include_trades` | boolean | No | true | Include individual trade data |
| `include_performance` | boolean | No | true | Include performance metrics |
| `include_strategy_code` | boolean | No | false | Include strategy source code |
| `include_config` | boolean | No | false | Include configuration used |
| `include_market_data` | boolean | No | false | Include market change data |
| `output_format` | string | No | "summary" | Level of detail: "summary", "detailed", "raw" |

#### Return Value

```json
{
  "command": "extract_backtest_data",
  "success": true,
  "file_path": "/path/to/backtest-result.zip",
  "data": {
    "strategy": "MyTrendStrategy",
    "timerange": "20240101-20250101",
    "performance_metrics": {
      "total_profit_pct": 15.42,
      "total_profit_abs": 1542.0,
      "total_trades": 156,
      "winning_trades": 98,
      "losing_trades": 58,
      "win_rate": 0.628,
      "sharpe_ratio": 1.25,
      "sortino_ratio": 1.48,
      "calmar_ratio": 1.86,
      "max_drawdown_pct": 8.3,
      "avg_profit_pct": 0.099,
      "avg_duration": "4:15:00"
    },
    "trades": [
      {
        "pair": "BTC/USDT:USDT",
        "profit_pct": 2.5,
        "profit_abs": 25.0,
        "open_date": "2024-01-15 10:30:00",
        "close_date": "2024-01-15 14:45:00",
        "duration": "4:15:00",
        "entry_tag": "rsi_cross",
        "exit_reason": "roi"
      }
    ],
    "pair_results": {
      "BTC/USDT:USDT": {
        "profit_pct": 8.5,
        "trades": 78,
        "win_rate": 0.641
      }
    },
    "daily_stats": {
      "avg_daily_profit": 0.042,
      "best_day": "2024-06-15",
      "worst_day": "2024-03-22"
    }
  }
}
```

### 11. extract_hyperopt_data

**Description:** Extract and analyze data from hyperopt result .fthypt files.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `hyperopt_path` | string | Yes | - | Path to the hyperopt result .fthypt file |
| `include_trials` | boolean | No | true | Include individual trial data |
| `include_best_params` | boolean | No | true | Include best parameter combinations |
| `include_parameter_ranges` | boolean | No | true | Include parameter space analysis |
| `include_convergence` | boolean | No | true | Include optimization convergence analysis |
| `max_trials` | integer | No | - | Maximum number of trials to include |
| `output_format` | string | No | "summary" | Level of detail: "summary", "detailed", "raw" |

#### Return Value

```json
{
  "command": "extract_hyperopt_data",
  "success": true,
  "file_path": "/path/to/hyperopt-result.fthypt",
  "data": {
    "strategy": "MyTrendStrategy",
    "total_epochs": 100,
    "best_epoch": 73,
    "best_result": {
      "loss": -15.42,
      "profit_pct": 18.65,
      "total_trades": 142,
      "win_rate": 0.683,
      "sharpe_ratio": 1.42
    },
    "best_params": {
      "buy": {
        "buy_rsi": 28,
        "buy_rsi_enabled": true
      },
      "sell": {
        "sell_rsi": 72
      },
      "roi": {
        "0": 0.15,
        "10": 0.08,
        "30": 0.03
      },
      "stoploss": -0.085
    },
    "parameter_ranges": {
      "buy_rsi": {
        "min": 20,
        "max": 40,
        "optimal": 28,
        "sensitivity": "high"
      }
    },
    "convergence_analysis": {
      "convergence_epoch": 65,
      "improvement_rate": 0.002,
      "stability_reached": true
    },
    "trials": [
      {
        "epoch": 1,
        "loss": -5.2,
        "profit_pct": 5.2,
        "trades": 125
      }
    ]
  }
}
```

---

## Configuration Tools

### 12. create_userdir

**Description:** Create a new Freqtrade user directory structure with sample files.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `userdir` | string | Yes | - | Path where to create the user directory |
| `reset` | boolean | No | false | Reset user directory if it already exists |

#### Return Value

```json
{
  "command": "create_userdir",
  "success": true,
  "userdir": "/path/to/user_data",
  "created_directories": [
    "/path/to/user_data/strategies",
    "/path/to/user_data/data",
    "/path/to/user_data/backtest_results",
    "/path/to/user_data/hyperopt_results",
    "/path/to/user_data/notebooks",
    "/path/to/user_data/plot"
  ],
  "created_files": [
    "/path/to/user_data/config.json",
    "/path/to/user_data/strategies/sample_strategy.py",
    "/path/to/user_data/notebooks/strategy_analysis.ipynb"
  ],
  "message": "User directory created successfully at /path/to/user_data"
}
```

### 13. create_config

**Description:** Create a new Freqtrade configuration file from template.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `config_path` | string | Yes | - | Path where to save the configuration file |
| `template` | string | No | "default" | Template: "default", "conservative", "aggressive", "advanced" |
| `exchange` | string | No | - | Exchange name (e.g., 'binance', 'kraken') |
| `stake_currency` | string | No | - | Stake currency (e.g., 'USDT', 'BTC') |
| `stake_amount` | number | No | - | Amount to stake per trade |
| `max_open_trades` | integer | No | - | Maximum number of concurrent trades |
| `dry_run` | boolean | No | - | Enable dry run mode (paper trading) |
| `trading_mode` | string | No | - | Trading mode: "spot", "futures", "margin" |
| `pairs` | array[string] | No | - | List of trading pairs |

#### Return Value

```json
{
  "command": "create_config",
  "success": true,
  "config_path": "/path/to/config.json",
  "template_used": "default",
  "configuration": {
    "exchange": {
      "name": "binance",
      "key": "",
      "secret": ""
    },
    "stake_currency": "USDT",
    "stake_amount": 100,
    "max_open_trades": 3,
    "dry_run": true,
    "trading_mode": "spot",
    "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
    "timeframe": "5m",
    "features": {
      "position_adjustment_enable": false,
      "use_exit_signal": true,
      "exit_profit_only": false,
      "ignore_roi_if_entry_signal": false
    }
  },
  "message": "Configuration file created successfully at /path/to/config.json"
}
```

---

## Common Response Fields

All tools return these standard fields:

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | The name of the executed command |
| `success` | boolean | Whether the operation succeeded |
| `error` | string | Error message if success is false |
| `error_type` | string | Type of error (when applicable) |
| `duration_seconds` | number | Execution time (for long operations) |

## Error Handling

When a tool fails, it returns an error response:

```json
{
  "command": "tool_name",
  "success": false,
  "error": "Detailed error message",
  "error_type": "ValidationError",
  "details": {
    "parameter": "invalid_param",
    "provided_value": "bad_value",
    "expected": "valid_value_format"
  }
}
```

## Natural Language Date Parsing

Many tools accept natural language date ranges. Examples:
- "last year"
- "last 3 months"
- "january to march"
- "2024"
- "september 2024"
- "last 30 days"
- "yesterday"
- "this week"

These are automatically converted to Freqtrade's timerange format (YYYYMMDD-YYYYMMDD).

## Best Practices

1. **Always check `success` field**: Before processing results, verify the operation succeeded.

2. **Use appropriate timeframes**: Different strategies work better with different timeframes. Common choices:
   - Scalping: 1m, 5m
   - Day trading: 15m, 30m, 1h
   - Swing trading: 4h, 1d

3. **Progressive optimization**: Start with fewer epochs (50-100) for hyperopt to get quick results, then increase for fine-tuning.

4. **Data validation**: Ensure you have sufficient historical data before backtesting (typically 1+ years).

5. **Result management**: Use meaningful IDs and regularly clean up old results to manage disk space.

6. **Error recovery**: Most tools are idempotent - safe to retry on failure.

---

## Examples

### Example 1: Complete Strategy Development Workflow

```python
# 1. Download historical data
await download_candles(
    pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"],
    timeframes=["1h"],
    date_range="last year"
)

# 2. Create a strategy
await create_strategy(
    strategy_name="MyTrendFollower",
    template="trend",
    timeframe="1h",
    indicators=["RSI", "MACD", "BB"]
)

# 3. Backtest the strategy
result = await backtest_strategy(
    strategy_name="MyTrendFollower",
    pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"],
    timerange="last 6 months"
)

# 4. If profitable, optimize parameters
if result["performance"]["total_profit_pct"] > 0:
    await hyperopt_strategy(
        strategy_name="MyTrendFollower",
        pairs=["BTC/USDT:USDT", "ETH/USDT:USDT"],
        timerange="last 6 months",
        epochs=200
    )
```

### Example 2: Analyzing Historical Results

```python
# Search for profitable strategies
results = await search_results(
    min_profit=10,
    min_winrate=0.6,
    sort_by="profit",
    limit=5
)

# Extract detailed data from the best result
best_result = results["matches"][0]
data = await extract_backtest_data(
    result_path=best_result["file_path"],
    include_trades=True,
    include_performance=True,
    output_format="detailed"
)
```

---

## Version Information

- **MCP Server Version**: 1.0.0
- **Freqtrade Compatibility**: 2024.1+
- **Last Updated**: January 2025

## Support

For issues or questions:
- Check Freqtrade documentation: https://www.freqtrade.io/
- MCP Server issues: Report in the project repository
- Strategy development help: Freqtrade Discord community