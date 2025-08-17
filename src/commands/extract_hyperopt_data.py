"""Extract hyperopt data command implementation."""

import json
import logging
import pickle
import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .base import BaseCommand, FREQTRADE_AVAILABLE
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from commands.base import BaseCommand, FREQTRADE_AVAILABLE

logger = logging.getLogger(__name__)


class ExtractHyperoptDataCommand(BaseCommand):
    """Command to extract and analyze data from hyperopt result .fthypt files."""

    async def execute(
        self,
        hyperopt_path: str,
        include_trials: bool = True,
        include_best_params: bool = True,
        include_parameter_ranges: bool = True,
        include_convergence: bool = True,
        max_trials: Optional[int] = None,
        output_format: str = "summary",  # summary, detailed, raw
        **kwargs
    ) -> Dict[str, Any]:
        """Execute extract hyperopt data command.
        
        Args:
            hyperopt_path: Path to the hyperopt result .fthypt file
            include_trials: Include individual trial data
            include_best_params: Include best parameter combinations
            include_parameter_ranges: Include parameter space analysis
            include_convergence: Include optimization convergence analysis
            max_trials: Maximum number of trials to include (for performance)
            output_format: Level of detail (summary, detailed, raw)
            
        Returns:
            Command execution result with extracted hyperopt data
        """
        try:
            await self.mcp_log("info", f"Extracting hyperopt data from: {hyperopt_path}")
            
            hyperopt_file = Path(hyperopt_path).resolve()
            
            if not hyperopt_file.exists():
                return {
                    "command": "extract_hyperopt_data",
                    "success": False,
                    "error": f"Hyperopt file {hyperopt_file} does not exist",
                    "path": str(hyperopt_file)
                }
            
            if not hyperopt_file.suffix.lower() == '.fthypt':
                return {
                    "command": "extract_hyperopt_data",
                    "success": False,
                    "error": "Hyperopt file must be a .fthypt file",
                    "path": str(hyperopt_file)
                }
            
            # Load hyperopt data
            hyperopt_data = await self._load_hyperopt_file(hyperopt_file)
            
            # Process and analyze the data
            processed_data = await self._process_hyperopt_data(
                hyperopt_data,
                include_trials=include_trials,
                include_best_params=include_best_params,
                include_parameter_ranges=include_parameter_ranges,
                include_convergence=include_convergence,
                max_trials=max_trials,
                output_format=output_format
            )
            
            await self.mcp_log("info", f"Successfully extracted hyperopt data from {hyperopt_file.name}")
            
            return {
                "command": "extract_hyperopt_data",
                "success": True,
                "hyperopt_file": str(hyperopt_file),
                "hyperopt_id": hyperopt_file.stem,
                "extraction_summary": {
                    "total_trials": processed_data.get("total_trials", 0),
                    "strategy_name": processed_data.get("strategy_name", "unknown"),
                    "best_loss": processed_data.get("best_loss", None),
                    "optimization_summary": processed_data.get("optimization_summary", {})
                },
                "data": processed_data
            }
            
        except Exception as e:
            await self.mcp_log("error", f"Extract hyperopt data command failed: {e}")
            return {
                "command": "extract_hyperopt_data",
                "success": False,
                "error": str(e),
                "path": hyperopt_path
            }

    async def _load_hyperopt_file(self, hyperopt_file: Path) -> Dict[str, Any]:
        """Load hyperopt data from .fthypt file."""
        try:
            # First try as JSON Lines format (newer format)
            try:
                trials = []
                with open(hyperopt_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            trials.append(json.loads(line))
                await self.mcp_log("info", f"Loaded hyperopt file as JSON Lines with {len(trials)} trials")
                return {"trials": trials}
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Try as single JSON object
                try:
                    with open(hyperopt_file, 'r') as f:
                        data = json.load(f)
                    await self.mcp_log("info", f"Loaded hyperopt file as JSON with {len(data) if isinstance(data, list) else 'unknown'} trials")
                    return {"trials": data} if isinstance(data, list) else data
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Fallback to pickle format (older format)
                    with open(hyperopt_file, 'rb') as f:
                        data = pickle.load(f)
                    await self.mcp_log("info", f"Loaded hyperopt file as pickle with {len(data) if isinstance(data, list) else 'unknown'} trials")
                    return {"trials": data} if isinstance(data, list) else data
            
        except Exception as e:
            await self.mcp_log("error", f"Failed to load hyperopt file: {e}")
            raise

    async def _process_hyperopt_data(
        self,
        hyperopt_data: Dict[str, Any],
        include_trials: bool,
        include_best_params: bool,
        include_parameter_ranges: bool,
        include_convergence: bool,
        max_trials: Optional[int],
        output_format: str
    ) -> Dict[str, Any]:
        """Process and analyze hyperopt data."""
        
        processed_data = {}
        trials = hyperopt_data.get('trials', [])
        
        if not trials:
            return {"error": "No trials found in hyperopt data"}
        
        # Basic information
        total_trials = len(trials)
        processed_data['total_trials'] = total_trials
        
        # Extract strategy name from file or trials
        strategy_name = "unknown"
        if trials and 'misc' in trials[0] and 'vals' in trials[0]['misc']:
            # Try to extract strategy name from trial data
            pass  # Strategy name extraction logic would go here
        
        processed_data['strategy_name'] = strategy_name
        
        # Limit trials if requested
        if max_trials and len(trials) > max_trials:
            trials = trials[:max_trials]
            await self.mcp_log("info", f"Limited trials to {max_trials} for performance")
        
        # Extract trial results
        trial_results = []
        losses = []
        parameter_values = {}
        
        for i, trial in enumerate(trials):
            try:
                trial_result = {
                    "trial_number": i + 1,
                    "loss": float('inf'),
                    "status": 'unknown',
                    "params": {}
                }
                
                # Handle new JSON format (freqtrade hyperopt results)
                if 'loss' in trial:
                    trial_result['loss'] = trial['loss']
                    trial_result['status'] = 'ok'  # If loss exists, assume successful
                    
                    # Extract parameters from params_dict
                    if 'params_dict' in trial:
                        for param_name, value in trial['params_dict'].items():
                            trial_result['params'][param_name] = value
                            
                            # Track parameter ranges
                            if param_name not in parameter_values:
                                parameter_values[param_name] = []
                            parameter_values[param_name].append(value)
                
                # Handle old hyperopt format (with misc/vals structure)
                elif 'result' in trial:
                    trial_result['loss'] = trial.get('result', {}).get('loss', float('inf'))
                    trial_result['status'] = trial.get('result', {}).get('status', 'unknown')
                    
                    # Extract parameters
                    if 'misc' in trial and 'vals' in trial['misc']:
                        vals = trial['misc']['vals']
                        for param_name, param_values in vals.items():
                            if param_values:  # Not empty
                                value = param_values[0] if isinstance(param_values, list) else param_values
                                trial_result['params'][param_name] = value
                                
                                # Track parameter ranges
                                if param_name not in parameter_values:
                                    parameter_values[param_name] = []
                                parameter_values[param_name].append(value)
                
                trial_results.append(trial_result)
                if trial_result['loss'] != float('inf'):
                    losses.append(trial_result['loss'])
                    
            except Exception as e:
                await self.mcp_log("warning", f"Failed to process trial {i}: {e}")
                continue
        
        processed_data['trial_results'] = trial_results
        
        # Find best trial
        best_trial = None
        best_loss = float('inf')
        for trial in trial_results:
            if trial['loss'] < best_loss:
                best_loss = trial['loss']
                best_trial = trial
        
        if best_trial:
            processed_data['best_loss'] = best_loss
            processed_data['best_trial'] = best_trial
        
        # Best parameters
        if include_best_params and best_trial:
            processed_data['best_parameters'] = best_trial['params']
        
        # Parameter ranges and statistics
        if include_parameter_ranges:
            param_stats = {}
            for param_name, values in parameter_values.items():
                if values:
                    param_stats[param_name] = {
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / len(values),
                        "count": len(values),
                        "unique_values": len(set(values))
                    }
            
            processed_data['parameter_statistics'] = param_stats
            processed_data['parameter_ranges'] = {
                param: {"min": stats["min"], "max": stats["max"]}
                for param, stats in param_stats.items()
            }
        
        # Convergence analysis
        if include_convergence and losses:
            convergence_analysis = self._analyze_convergence(losses)
            processed_data['convergence_analysis'] = convergence_analysis
        
        # Optimization summary
        processed_data['optimization_summary'] = self._create_optimization_summary(
            trial_results, losses, parameter_values
        )
        
        # Parameter sensitivity analysis
        if include_parameter_ranges and len(trial_results) > 10:
            sensitivity_analysis = self._analyze_parameter_sensitivity(trial_results)
            processed_data['parameter_sensitivity'] = sensitivity_analysis
        
        # Format output based on detail level
        if output_format == "summary":
            # Keep only summary data
            keys_to_keep = [
                'total_trials', 'strategy_name', 'best_loss', 'best_parameters',
                'optimization_summary', 'parameter_ranges'
            ]
            processed_data = {k: v for k, v in processed_data.items() if k in keys_to_keep}
            
        elif output_format == "detailed":
            # Remove raw trial data but keep analysis
            if 'trial_results' in processed_data and len(processed_data['trial_results']) > 100:
                # Keep only best 50 and worst 50 trials
                sorted_trials = sorted(processed_data['trial_results'], key=lambda x: x['loss'])
                processed_data['trial_results'] = sorted_trials[:50] + sorted_trials[-50:]
                
        # output_format == "raw" keeps everything
        
        return processed_data

    def _analyze_convergence(self, losses: List[float]) -> Dict[str, Any]:
        """Analyze optimization convergence."""
        if not losses:
            return {"error": "No loss values to analyze"}
        
        # Best loss progression
        best_so_far = []
        current_best = float('inf')
        for loss in losses:
            if loss < current_best:
                current_best = loss
            best_so_far.append(current_best)
        
        # Convergence metrics
        improvement_rate = []
        for i in range(1, len(best_so_far)):
            if best_so_far[i-1] != 0:
                improvement = (best_so_far[i-1] - best_so_far[i]) / abs(best_so_far[i-1])
                improvement_rate.append(improvement)
        
        # Find when optimization likely converged (no improvement for N trials)
        no_improvement_threshold = 50
        last_improvement = 0
        for i in range(1, len(best_so_far)):
            if best_so_far[i] < best_so_far[i-1]:
                last_improvement = i
        
        converged_at = last_improvement + no_improvement_threshold if last_improvement > 0 else None
        
        return {
            "total_trials": len(losses),
            "best_loss_progression": best_so_far[-50:] if len(best_so_far) > 50 else best_so_far,  # Last 50 for visualization
            "final_best_loss": best_so_far[-1] if best_so_far else None,
            "initial_loss": losses[0] if losses else None,
            "improvement_total": (losses[0] - best_so_far[-1]) if losses and best_so_far else 0,
            "improvement_percentage": ((losses[0] - best_so_far[-1]) / abs(losses[0]) * 100) if losses and losses[0] != 0 else 0,
            "likely_converged_at_trial": converged_at,
            "convergence_detected": converged_at is not None and converged_at < len(losses),
            "avg_improvement_rate": sum(improvement_rate) / len(improvement_rate) if improvement_rate else 0
        }

    def _create_optimization_summary(
        self,
        trial_results: List[Dict[str, Any]],
        losses: List[float],
        parameter_values: Dict[str, List[Any]]
    ) -> Dict[str, Any]:
        """Create a summary of the optimization process."""
        
        if not trial_results:
            return {"error": "No trial results to summarize"}
        
        successful_trials = [t for t in trial_results if t['loss'] != float('inf')]
        
        return {
            "total_trials": len(trial_results),
            "successful_trials": len(successful_trials),
            "failed_trials": len(trial_results) - len(successful_trials),
            "success_rate": len(successful_trials) / len(trial_results) if trial_results else 0,
            "best_loss": min(losses) if losses else None,
            "worst_loss": max(losses) if losses else None,
            "median_loss": sorted(losses)[len(losses)//2] if losses else None,
            "loss_std": pd.Series(losses).std() if losses else None,
            "parameters_optimized": len(parameter_values),
            "parameter_names": list(parameter_values.keys()),
            "optimization_efficiency": self._calculate_optimization_efficiency(losses) if losses else 0
        }

    def _calculate_optimization_efficiency(self, losses: List[float]) -> float:
        """Calculate optimization efficiency (how quickly it found good solutions)."""
        if len(losses) < 10:
            return 0.5  # Not enough data
        
        # Find the trial where we achieved 90% of final improvement
        best_loss = min(losses)
        initial_loss = losses[0]
        target_improvement = 0.9 * (initial_loss - best_loss)
        target_loss = initial_loss - target_improvement
        
        trials_to_target = len(losses)  # Default to all trials
        for i, loss in enumerate(losses):
            if loss <= target_loss:
                trials_to_target = i + 1
                break
        
        # Efficiency is inverse of the fraction of trials needed
        efficiency = 1.0 - (trials_to_target / len(losses))
        return max(0.0, min(1.0, efficiency))  # Clamp between 0 and 1

    def _analyze_parameter_sensitivity(self, trial_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze how sensitive the loss is to each parameter."""
        
        if len(trial_results) < 20:
            return {"error": "Not enough trials for sensitivity analysis"}
        
        # Create DataFrame for analysis
        data_rows = []
        for trial in trial_results:
            if trial['loss'] != float('inf'):
                row = {"loss": trial['loss']}
                row.update(trial['params'])
                data_rows.append(row)
        
        if not data_rows:
            return {"error": "No successful trials for analysis"}
        
        df = pd.DataFrame(data_rows)
        
        # Calculate correlation between each parameter and loss
        correlations = {}
        param_columns = [col for col in df.columns if col != 'loss']
        
        for param in param_columns:
            try:
                if df[param].dtype in ['int64', 'float64']:
                    corr = df['loss'].corr(df[param])
                    correlations[param] = {
                        "correlation": corr,
                        "absolute_correlation": abs(corr),
                        "sensitivity": "High" if abs(corr) > 0.5 else "Medium" if abs(corr) > 0.2 else "Low"
                    }
            except Exception:
                # Skip parameters that can't be correlated (non-numeric, etc.)
                continue
        
        # Sort by absolute correlation
        sorted_correlations = dict(sorted(
            correlations.items(), 
            key=lambda x: x[1]['absolute_correlation'], 
            reverse=True
        ))
        
        # Parameter importance ranking
        param_importance = []
        for param, stats in sorted_correlations.items():
            param_importance.append({
                "parameter": param,
                "importance_score": stats['absolute_correlation'],
                "correlation": stats['correlation'],
                "interpretation": "Higher values increase loss" if stats['correlation'] > 0 else "Higher values decrease loss"
            })
        
        return {
            "parameter_correlations": sorted_correlations,
            "parameter_importance_ranking": param_importance,
            "most_important_parameter": param_importance[0]['parameter'] if param_importance else None,
            "least_important_parameter": param_importance[-1]['parameter'] if param_importance else None,
            "high_sensitivity_params": [p for p, s in correlations.items() if s['sensitivity'] == 'High']
        }