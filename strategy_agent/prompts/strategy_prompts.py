"""
Prompt templates for strategy generation
"""

IDEA_GENERATION_PROMPT = """
You are developing a trading strategy for the following cryptocurrency pairs: {symbols}
Timeframes available: {timeframes}

Market Context:
{market_context}

Generate a unique and potentially profitable trading strategy idea that:
1. Uses 3-5 technical indicators that work well together
2. Has clear entry and exit logic
3. Includes risk management rules
4. Is suitable for the given timeframes
5. Takes advantage of crypto market characteristics (volatility, trends, etc.)

Focus on strategies that have shown success in crypto markets:
- Trend following with momentum confirmation
- Mean reversion with volatility filters
- Breakout strategies with volume confirmation
- Multi-timeframe analysis

Provide a strategy that is different from common strategies, with your own creative twist.
"""

STRATEGY_CODE_PROMPT = """
Create a complete Freqtrade strategy implementation with the following specifications:

IMPORTANT: The Python class name MUST be exactly: {strategy_name}

Description: {idea_description}
Indicators: {indicators}
Entry Logic: {entry_logic}
Exit Logic: {exit_logic}
Risk Management: {risk_management}
Preferred Timeframe: {timeframe}

Requirements:
1. Implement all necessary imports
2. Create a class named EXACTLY "{strategy_name}" inheriting from IStrategy
3. Define all indicators in populate_indicators()
4. Implement buy signals in populate_entry_trend()
5. Implement sell signals in populate_exit_trend()
6. Add hyperopt parameters for key values (use DecimalParameter and IntParameter)
7. Include proper ROI table
8. Set appropriate stoploss
9. Add trailing stop configuration
10. Include informative pairs if using multiple timeframes

The strategy should:
- Be production-ready and follow Freqtrade best practices
- Include parameter spaces for hyperopt optimization
- Have clear, commented code
- Handle edge cases properly
- Use proper dataframe operations

Generate the complete Python code for this strategy.
"""

STRATEGY_REWRITE_PROMPT = """
Improve the following trading strategy based on performance analysis:

IMPORTANT: The Python class name MUST remain exactly: {strategy_name}

Original Strategy Code:
```python
{original_code}
```

Performance Analysis:
- Rating: {performance_rating}
- Weaknesses: {weaknesses}
- Improvement Suggestions: {suggestions}

Current Metrics:
{metrics}

Rewrite the strategy to address the identified weaknesses while keeping the class name as "{strategy_name}". Focus on:

1. If low profit: Adjust entry/exit logic for better trade timing
2. If high drawdown: Improve stoploss and risk management
3. If low trade count: Relax entry conditions slightly
4. If low win rate: Add confirmation indicators or filters
5. If poor Sharpe ratio: Reduce false signals and improve consistency

Specific improvements to make:
- Modify indicator parameters to be more adaptive
- Add filters to reduce false signals
- Improve exit logic for better profit capture
- Adjust hyperopt parameter ranges based on current results
- Add or modify indicators based on the weaknesses

Generate the complete improved strategy code.
"""