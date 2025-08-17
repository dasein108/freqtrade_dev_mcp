"""Search results command implementation."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import re

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
    from .extract_backtest_data import ExtractBacktestDataCommand
    from .extract_hyperopt_data import ExtractHyperoptDataCommand
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE
    from commands.extract_backtest_data import ExtractBacktestDataCommand
    from commands.extract_hyperopt_data import ExtractHyperoptDataCommand

logger = logging.getLogger(__name__)


class SearchResultsCommand(BaseCommand):
    """Command to search and filter backtest and hyperopt results."""

    def __init__(self, config, server):
        super().__init__(config, server)
        self.db_path = Path(config.freqtrade_path) / "mcp_results.db"
        self.backtest_extractor = ExtractBacktestDataCommand(config, server)
        self.hyperopt_extractor = ExtractHyperoptDataCommand(config, server)

    async def execute(
        self,
        query: Optional[str] = None,
        result_type: str = "all",  # all, backtest, hyperopt
        strategy_name: Optional[str] = None,
        min_profit: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        min_trades: Optional[int] = None,
        min_winrate: Optional[float] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "date",  # date, profit, winrate, trades, drawdown
        sort_order: str = "desc",  # asc, desc
        limit: int = 20,
        include_summary: bool = True,
        rebuild_index: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute search results command.
        
        Args:
            query: Free text search query
            result_type: Type of results to search (all, backtest, hyperopt)
            strategy_name: Filter by strategy name
            min_profit: Minimum profit percentage
            max_drawdown: Maximum drawdown percentage
            min_trades: Minimum number of trades
            min_winrate: Minimum win rate (0-1)
            date_from: Start date filter (YYYY-MM-DD)
            date_to: End date filter (YYYY-MM-DD)
            sort_by: Sort criteria
            sort_order: Sort direction
            limit: Maximum results to return
            include_summary: Include performance summaries
            rebuild_index: Force rebuild of search index
            
        Returns:
            Command execution result with search results
        """
        try:
            await self.mcp_log("info", f"Searching results with query: {query}")
            
            # Initialize or rebuild search index
            if rebuild_index or not self.db_path.exists():
                await self._build_search_index()
            
            # Execute search
            search_results = await self._search_database(
                query=query,
                result_type=result_type,
                strategy_name=strategy_name,
                min_profit=min_profit,
                max_drawdown=max_drawdown,
                min_trades=min_trades,
                min_winrate=min_winrate,
                date_from=date_from,
                date_to=date_to,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit
            )
            
            # Enhance results with summaries if requested
            if include_summary:
                search_results = await self._enhance_results_with_summaries(search_results)
            
            await self.mcp_log("info", f"Found {len(search_results)} matching results")
            
            return {
                "command": "search_results",
                "success": True,
                "search_criteria": {
                    "query": query,
                    "result_type": result_type,
                    "strategy_name": strategy_name,
                    "filters": {
                        "min_profit": min_profit,
                        "max_drawdown": max_drawdown,
                        "min_trades": min_trades,
                        "min_winrate": min_winrate,
                        "date_from": date_from,
                        "date_to": date_to
                    },
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                    "limit": limit
                },
                "total_results": len(search_results),
                "results": search_results
            }
            
        except Exception as e:
            await self.mcp_log("error", f"Search results command failed: {e}")
            return {
                "command": "search_results",
                "success": False,
                "error": str(e)
            }

    async def _build_search_index(self):
        """Build searchable index from all result files."""
        await self.mcp_log("info", "Building search index...")
        
        # Create database and tables
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                file_path TEXT,
                result_type TEXT,
                strategy_name TEXT,
                date_created TEXT,
                total_trades INTEGER,
                profit_total REAL,
                profit_total_abs REAL,
                winrate REAL,
                max_drawdown REAL,
                sharpe REAL,
                backtest_start TEXT,
                backtest_end TEXT,
                timeframe TEXT,
                stake_currency TEXT,
                metadata TEXT,
                indexed_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_terms (
                result_id TEXT,
                term TEXT,
                FOREIGN KEY (result_id) REFERENCES results (id)
            )
        ''')
        
        # Create indexes for faster searching
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_name ON results (strategy_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_result_type ON results (result_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_profit ON results (profit_total)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_winrate ON results (winrate)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawdown ON results (max_drawdown)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_terms ON search_terms (term)')
        
        conn.commit()
        
        # Find all result files
        backtest_files = list(Path(self.config.freqtrade_path).glob("**/backtest-result-*.zip"))
        hyperopt_files = list(Path(self.config.freqtrade_path).glob("**/strategy_*.fthypt"))
        
        await self.mcp_log("info", f"Found {len(backtest_files)} backtest files and {len(hyperopt_files)} hyperopt files")
        
        # Index backtest files
        for file_path in backtest_files:
            try:
                await self._index_backtest_file(cursor, file_path)
            except Exception as e:
                await self.mcp_log("warning", f"Failed to index {file_path}: {e}")
        
        # Index hyperopt files
        for file_path in hyperopt_files:
            try:
                await self._index_hyperopt_file(cursor, file_path)
            except Exception as e:
                await self.mcp_log("warning", f"Failed to index {file_path}: {e}")
        
        conn.commit()
        conn.close()
        
        await self.mcp_log("info", "Search index built successfully")

    async def _index_backtest_file(self, cursor: sqlite3.Cursor, file_path: Path):
        """Index a single backtest file."""
        
        # Extract basic data
        extract_result = await self.backtest_extractor.execute(
            result_path=str(file_path),
            include_trades=False,
            include_performance=True,
            output_format="summary"
        )
        
        if not extract_result.get("success"):
            return
        
        data = extract_result.get("data", {})
        summary = extract_result.get("extraction_summary", {})
        
        # Insert into results table
        result_id = file_path.stem
        cursor.execute('''
            INSERT OR REPLACE INTO results (
                id, file_path, result_type, strategy_name, date_created,
                total_trades, profit_total, profit_total_abs, winrate, max_drawdown, sharpe,
                backtest_start, backtest_end, timeframe, stake_currency, metadata, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result_id,
            str(file_path),
            "backtest",
            data.get("strategy_name", "unknown"),
            file_path.stat().st_mtime,
            summary.get("total_trades", 0),
            data.get("performance_metrics", {}).get("profit_total", 0),
            data.get("performance_metrics", {}).get("profit_total_abs", 0),
            data.get("performance_metrics", {}).get("winrate", 0),
            data.get("performance_metrics", {}).get("max_drawdown", 0),
            data.get("performance_metrics", {}).get("sharpe", 0),
            data.get("result_metadata", {}).get("backtest_start"),
            data.get("result_metadata", {}).get("backtest_end"),
            data.get("result_metadata", {}).get("timeframe"),
            data.get("result_metadata", {}).get("stake_currency"),
            json.dumps(data.get("result_metadata", {})),
            datetime.now().isoformat()
        ))
        
        # Index search terms
        search_terms = set()
        search_terms.add(data.get("strategy_name", "").lower())
        search_terms.add(data.get("result_metadata", {}).get("timeframe", "").lower())
        search_terms.add(data.get("result_metadata", {}).get("stake_currency", "").lower())
        search_terms.add("backtest")
        
        # Add performance category terms
        performance = data.get("performance_summary", {})
        if performance.get("performance_rating"):
            search_terms.add(performance["performance_rating"].lower())
        
        winrate = performance.get("winrate_pct", 0)
        if winrate > 80:
            search_terms.add("high_winrate")
        elif winrate > 60:
            search_terms.add("good_winrate")
        elif winrate < 40:
            search_terms.add("low_winrate")
        
        profit = performance.get("profit_total_pct", 0)
        if profit > 50:
            search_terms.add("high_profit")
        elif profit > 10:
            search_terms.add("profitable")
        elif profit < -10:
            search_terms.add("unprofitable")
        
        # Insert search terms
        for term in search_terms:
            if term:  # Skip empty terms
                cursor.execute('INSERT INTO search_terms (result_id, term) VALUES (?, ?)', (result_id, term))

    async def _index_hyperopt_file(self, cursor: sqlite3.Cursor, file_path: Path):
        """Index a single hyperopt file."""
        
        # Extract basic data
        extract_result = await self.hyperopt_extractor.execute(
            hyperopt_path=str(file_path),
            include_trials=False,
            output_format="summary"
        )
        
        if not extract_result.get("success"):
            return
        
        data = extract_result.get("data", {})
        summary = extract_result.get("extraction_summary", {})
        
        # Extract strategy name from filename
        strategy_name = "unknown"
        filename = file_path.stem
        if "strategy_" in filename:
            parts = filename.split("_")
            if len(parts) >= 2:
                strategy_name = parts[1]
        
        # Insert into results table
        result_id = file_path.stem
        cursor.execute('''
            INSERT OR REPLACE INTO results (
                id, file_path, result_type, strategy_name, date_created,
                total_trades, profit_total, profit_total_abs, winrate, max_drawdown, sharpe,
                backtest_start, backtest_end, timeframe, stake_currency, metadata, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result_id,
            str(file_path),
            "hyperopt",
            strategy_name,
            file_path.stat().st_mtime,
            data.get("total_trials", 0),
            None,  # No profit for hyperopt
            None,  # No profit for hyperopt
            None,  # No winrate for hyperopt
            None,  # No drawdown for hyperopt
            None,  # No sharpe for hyperopt
            None,  # No backtest dates for hyperopt
            None,
            None,
            None,
            json.dumps({"best_loss": data.get("best_loss"), "optimization_summary": data.get("optimization_summary", {})}),
            datetime.now().isoformat()
        ))
        
        # Index search terms
        search_terms = set()
        search_terms.add(strategy_name.lower())
        search_terms.add("hyperopt")
        search_terms.add("optimization")
        
        # Add optimization quality terms
        opt_summary = data.get("optimization_summary", {})
        success_rate = opt_summary.get("success_rate", 0)
        if success_rate > 0.8:
            search_terms.add("high_success")
        elif success_rate < 0.5:
            search_terms.add("low_success")
        
        # Insert search terms
        for term in search_terms:
            if term:  # Skip empty terms
                cursor.execute('INSERT INTO search_terms (result_id, term) VALUES (?, ?)', (result_id, term))

    async def _search_database(
        self,
        query: Optional[str],
        result_type: str,
        strategy_name: Optional[str],
        min_profit: Optional[float],
        max_drawdown: Optional[float],
        min_trades: Optional[int],
        min_winrate: Optional[float],
        date_from: Optional[str],
        date_to: Optional[str],
        sort_by: str,
        sort_order: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Search the database with filters."""
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()
        
        # Build SQL query
        sql_parts = ["SELECT DISTINCT r.* FROM results r"]
        where_conditions = []
        params = []
        
        # Join with search_terms if text query provided
        if query:
            sql_parts.append("JOIN search_terms st ON r.id = st.result_id")
            query_terms = query.lower().split()
            term_conditions = []
            for term in query_terms:
                term_conditions.append("st.term LIKE ?")
                params.append(f"%{term}%")
            if term_conditions:
                where_conditions.append(f"({' OR '.join(term_conditions)})")
        
        # Add filters
        if result_type != "all":
            where_conditions.append("r.result_type = ?")
            params.append(result_type)
        
        if strategy_name:
            where_conditions.append("r.strategy_name LIKE ?")
            params.append(f"%{strategy_name}%")
        
        if min_profit is not None:
            where_conditions.append("r.profit_total >= ?")
            params.append(min_profit / 100.0)  # Convert percentage to decimal
        
        if max_drawdown is not None:
            where_conditions.append("r.max_drawdown <= ?")
            params.append(max_drawdown / 100.0)  # Convert percentage to decimal
        
        if min_trades is not None:
            where_conditions.append("r.total_trades >= ?")
            params.append(min_trades)
        
        if min_winrate is not None:
            where_conditions.append("r.winrate >= ?")
            params.append(min_winrate)
        
        if date_from:
            where_conditions.append("r.backtest_start >= ?")
            params.append(date_from)
        
        if date_to:
            where_conditions.append("r.backtest_end <= ?")
            params.append(date_to)
        
        # Add WHERE clause
        if where_conditions:
            sql_parts.append("WHERE " + " AND ".join(where_conditions))
        
        # Add ORDER BY
        sort_column_map = {
            "date": "r.date_created",
            "profit": "r.profit_total",
            "winrate": "r.winrate",
            "trades": "r.total_trades",
            "drawdown": "r.max_drawdown"
        }
        
        sort_column = sort_column_map.get(sort_by, "r.date_created")
        sql_parts.append(f"ORDER BY {sort_column} {sort_order.upper()}")
        
        # Add LIMIT
        sql_parts.append("LIMIT ?")
        params.append(limit)
        
        # Execute query
        sql = " ".join(sql_parts)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        results = []
        for row in rows:
            result = dict(row)
            # Parse metadata JSON
            if result['metadata']:
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except json.JSONDecodeError:
                    result['metadata'] = {}
            
            results.append(result)
        
        conn.close()
        return results

    async def _enhance_results_with_summaries(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add performance summaries to search results."""
        
        enhanced_results = []
        
        for result in results:
            enhanced_result = result.copy()
            
            try:
                if result['result_type'] == 'backtest':
                    # Extract summary data for backtest
                    extract_result = await self.backtest_extractor.execute(
                        result_path=result['file_path'],
                        include_trades=False,
                        include_performance=True,
                        output_format="summary"
                    )
                    
                    if extract_result.get("success"):
                        data = extract_result.get("data", {})
                        enhanced_result['performance_summary'] = data.get("performance_summary", {})
                        enhanced_result['performance_metrics'] = data.get("performance_metrics", {})
                
                elif result['result_type'] == 'hyperopt':
                    # Extract summary data for hyperopt
                    extract_result = await self.hyperopt_extractor.execute(
                        hyperopt_path=result['file_path'],
                        include_trials=False,
                        output_format="summary"
                    )
                    
                    if extract_result.get("success"):
                        data = extract_result.get("data", {})
                        enhanced_result['optimization_summary'] = data.get("optimization_summary", {})
                        enhanced_result['best_parameters'] = data.get("best_parameters", {})
                        enhanced_result['best_loss'] = data.get("best_loss")
                
            except Exception as e:
                await self.mcp_log("warning", f"Failed to enhance result {result['id']}: {e}")
                # Continue with basic result if enhancement fails
            
            enhanced_results.append(enhanced_result)
        
        return enhanced_results