"""Natural language date parsing utilities using dateparser."""

from datetime import datetime, timedelta
from typing import Tuple
import calendar
import re

import dateparser


def _handle_relative_period(date_string: str) -> Tuple[datetime, datetime]:
    """Handle relative period patterns like 'last N days/months/years'.
    
    Args:
        date_string: Pattern like "last 365 days", "past 30 days", etc.
        
    Returns:
        Tuple of (start_date, end_date) or None if pattern doesn't match
    """
    # Patterns to match: "last/past N days/weeks/months/years"
    pattern = r'\b(?:last|past)\s+(\d+)\s+(days?|weeks?|months?|years?)\b'
    match = re.search(pattern, date_string.lower())
    
    if not match:
        return None
    
    number = int(match.group(1))
    unit = match.group(2).rstrip('s')  # Remove plural 's'
    
    end_date = datetime.now()
    
    if unit == 'day':
        start_date = end_date - timedelta(days=number)
    elif unit == 'week':
        start_date = end_date - timedelta(weeks=number)
    elif unit == 'month':
        # Approximate months as 30 days each
        start_date = end_date - timedelta(days=number * 30)
    elif unit == 'year':
        # Approximate years as 365 days each
        start_date = end_date - timedelta(days=number * 365)
    else:
        return None
    
    return start_date, end_date


def _handle_freqtrade_timerange(date_string: str) -> Tuple[datetime, datetime]:
    """Handle Freqtrade timerange format YYYYMMDD-YYYYMMDD.
    
    Args:
        date_string: Pattern like "20240101-20250101"
        
    Returns:
        Tuple of (start_date, end_date) or None if pattern doesn't match
    """
    import re
    # Pattern to match YYYYMMDD-YYYYMMDD
    pattern = r'^(\d{8})-(\d{8})$'
    match = re.match(pattern, date_string)
    
    if not match:
        return None
    
    start_str = match.group(1)
    end_str = match.group(2)
    
    try:
        # Parse YYYYMMDD format
        start_date = datetime.strptime(start_str, '%Y%m%d')
        end_date = datetime.strptime(end_str, '%Y%m%d')
        
        # Set end date to end of day
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return start_date, end_date
    except ValueError:
        return None


def parse_natural_date(date_string: str) -> Tuple[datetime, datetime]:
    """Parse natural language date string to start and end datetime objects using dateparser.
    
    Args:
        date_string: Natural language date like "last year", "september", "last 3 months", "last 365 days", or "YYYYMMDD-YYYYMMDD"
        
    Returns:
        Tuple of (start_date, end_date)
    """
    date_string = date_string.strip()
    
    # First, check if it's already in Freqtrade timerange format
    freqtrade_result = _handle_freqtrade_timerange(date_string)
    if freqtrade_result:
        return freqtrade_result
    
    # Then, try to handle relative period patterns that dateparser might miss
    relative_result = _handle_relative_period(date_string)
    if relative_result:
        return relative_result
    
    # Configure dateparser settings
    settings = {
        'PREFER_DAY_OF_MONTH': 'first',
        'PREFER_DATES_FROM': 'past',
        'RETURN_AS_TIMEZONE_AWARE': False,
    }
    
    # Handle range patterns (e.g., "march to june", "january 2024 to march 2024")
    range_separators = [" to ", " - ", " through ", " until "]
    for separator in range_separators:
        if separator in date_string.lower():
            parts = date_string.lower().split(separator)
            if len(parts) == 2:
                start_str, end_str = parts[0].strip(), parts[1].strip()
                
                start_parsed = dateparser.parse(start_str, settings=settings)
                end_parsed = dateparser.parse(end_str, settings=settings)
                
                if start_parsed and end_parsed:
                    # If parsing a month range, adjust to full month boundaries
                    start_date = _adjust_to_month_start(start_parsed, start_str)
                    end_date = _adjust_to_month_end(end_parsed, end_str)
                    return start_date, end_date
    
    # Check for quarter patterns first (before dateparser)
    date_lower = date_string.lower()
    if any(q in date_lower for q in ["q1", "q2", "q3", "q4", "quarter"]):
        # For quarters, use current year if not specified
        year = datetime.now().year
        if any(str(y) in date_string for y in range(2020, 2030)):
            import re
            year_match = re.search(r'\b(20\d{2})\b', date_string)
            if year_match:
                year = int(year_match.group(1))
        start_date, end_date = _handle_quarter_with_year(date_string, year)
        return start_date, end_date
    
    # Parse single date/period
    parsed = dateparser.parse(date_string, settings=settings)
    
    if not parsed:
        raise ValueError(f"Could not parse date string: {date_string}")
    
    # Determine if this is a period vs specific date
    
    # Check for relative periods that should span a range
    if any(keyword in date_lower for keyword in [
        "last", "past", "previous", "ago", "since"
    ]):
        # For relative periods, end is now, start is the parsed date
        end_date = datetime.now()
        start_date = parsed
        return start_date, end_date
    
    # Check for month names (should span full month)
    month_names = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    if any(month in date_lower for month in month_names):
        start_date = _adjust_to_month_start(parsed, date_string)
        end_date = _adjust_to_month_end(parsed, date_string)
        return start_date, end_date
    
    # Check for year (should span full year)
    if date_string.strip().isdigit() and len(date_string.strip()) == 4:
        year = int(date_string.strip())
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        return start_date, end_date
    
    
    # Default: treat as single day
    start_date = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_date, end_date


def _adjust_to_month_start(dt: datetime, original_string: str) -> datetime:
    """Adjust datetime to start of month."""
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _adjust_to_month_end(dt: datetime, original_string: str) -> datetime:
    """Adjust datetime to end of month."""
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)


def _handle_quarter_with_year(original_string: str, year: int) -> Tuple[datetime, datetime]:
    """Handle quarter parsing with specific year."""
    date_lower = original_string.lower()
    
    # Extract quarter number
    quarter = 1  # default
    if "q1" in date_lower or "quarter 1" in date_lower:
        quarter = 1
    elif "q2" in date_lower or "quarter 2" in date_lower:
        quarter = 2
    elif "q3" in date_lower or "quarter 3" in date_lower:
        quarter = 3
    elif "q4" in date_lower or "quarter 4" in date_lower:
        quarter = 4
    
    # Quarter date ranges
    quarter_ranges = {
        1: (1, 3),   # Jan-Mar
        2: (4, 6),   # Apr-Jun
        3: (7, 9),   # Jul-Sep
        4: (10, 12)  # Oct-Dec
    }
    
    start_month, end_month = quarter_ranges[quarter]
    
    start_date = datetime(year, start_month, 1)
    last_day = calendar.monthrange(year, end_month)[1]
    end_date = datetime(year, end_month, last_day, 23, 59, 59)
    
    return start_date, end_date


def format_timerange(start_date: datetime, end_date: datetime) -> str:
    """Format datetime objects to Freqtrade timerange format (YYYYMMDD-YYYYMMDD)."""
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    return f"{start_str}-{end_str}"


def parse_and_format_date(date_string: str) -> str:
    """Parse natural language date and return Freqtrade timerange format."""
    start_date, end_date = parse_natural_date(date_string)
    return format_timerange(start_date, end_date)