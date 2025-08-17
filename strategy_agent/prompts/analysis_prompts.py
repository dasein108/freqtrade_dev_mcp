"""
Prompt templates for result analysis
"""

STRATEGY_ANALYSIS_PROMPT = """
Analyze the performance of this trading strategy:

Strategy: {strategy_name}

Performance Metrics:
{metrics}

Strategy Code Overview:
{strategy_code}

Provide a comprehensive analysis including:

1. Overall Performance Rating:
   - "excellent" if profit > 20% AND Sharpe > 2
   - "good" if profit > 10% AND Sharpe > 1
   - "poor" if profit > 0% but below thresholds
   - "failure" if profit <= 0%

2. Is Profitable: Consider the strategy profitable if:
   - Profit > 5% AND
   - Sharpe ratio > 0.5 AND
   - Win rate > 35% AND
   - Has reasonable number of trades (> 50)

3. Strengths: What aspects of the strategy work well?
   - Good indicator combinations
   - Effective entry/exit timing
   - Risk management effectiveness

4. Weaknesses: What needs improvement?
   - Poor signal quality
   - Timing issues
   - Risk/reward problems
   - Overfit or underfit

5. Improvement Suggestions: Specific actionable improvements
   - Indicator adjustments
   - Logic modifications
   - Parameter tuning recommendations

6. Risk Assessment: Evaluate the risk profile
   - Is drawdown acceptable?
   - Is the strategy robust or fragile?
   - Suitability for live trading

Be specific and actionable in your analysis.
"""

MARKET_ANALYSIS_PROMPT = """
Analyze the market conditions from the provided data:

Symbols: {symbols}
Timeframes: {timeframes}
Data Summary: {data_summary}

Provide insights on:
1. Current market regime (trending, ranging, volatile)
2. Best timeframes for trading
3. Recommended strategy types for these conditions
4. Key levels or patterns observed
"""