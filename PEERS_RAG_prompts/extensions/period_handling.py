"""
Period Handling Extension

Handles period normalization and filtering (quarters, fiscal years, latest periods, etc.)
"""

PERIOD_HANDLING_EXTENSION = """
PERIOD HANDLING RULES:
- Normalize all period strings to database format before querying
- Handle "latest" / "most recent" by querying the most recent period available
- Support multiple period formats: Q1FY2025, FY2025Q1, 1QFY2025, 1QFY-2025, quarter 1 of 2025
- Use normalize_period tool to convert user's period format to database format
- For "latest", first search for available periods, then select the most recent one
- Always include period filtering in WHERE clause when specific periods are mentioned

PERIOD FORMAT CONVERSION:
- "Q1FY2025" or "FY2025Q1" or "1QFY2025" → normalize to database format (e.g., "1QFY-2025")
- "FY2025" or "full year 2025" → use appropriate full year format
- "last 4 quarters" → query last 4 quarters chronologically
- "quarter 1" or "Q1" → interpret as most recent Q1 if year not specified

QUERY EXAMPLES:
- Latest period: ORDER BY pr.period DESC LIMIT 1
- Specific period: WHERE pr.period = '1QFY-2025'
- Multiple periods: WHERE pr.period IN ['1QFY-2025', '2QFY-2025', '3QFY-2025']
- Full year: WHERE pr.period STARTS WITH 'FY-2025'

VALIDATION:
- Always verify period exists in database before using (use search_periods if needed)
- Handle missing periods gracefully - inform user if period not found"""

