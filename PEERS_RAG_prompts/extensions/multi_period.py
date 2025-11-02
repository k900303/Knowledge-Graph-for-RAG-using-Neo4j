"""
Multi-Period Extension

Handles queries involving multiple periods (trends, time-series, etc.)
"""

MULTI_PERIOD_EXTENSION = """
MULTI-PERIOD QUERY RULES:
- Support queries across multiple periods: "Show me revenue for Q1, Q2, Q3, Q4"
- Always order periods chronologically in results (ORDER BY pr.period)
- Normalize all periods to consistent format before querying
- Handle period ranges: "last 4 quarters", "FY2024 and FY2025"
- Support trend analysis queries across multiple periods

PERIOD ORDERING:
- Always return periods in chronological order (earliest to latest)
- Use ORDER BY pr.period ASC for time-series data
- For "last N quarters", determine the N most recent quarters and query those

QUERY STRUCTURE:
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Company Name'
  AND p.parameter_name CONTAINS 'Parameter Name'
  AND pr.period IN ['1QFY-2025', '2QFY-2025', '3QFY-2025', '4QFY-2025']
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency
ORDER BY pr.period ASC

TREND ANALYSIS:
- When user asks for "trend" or "growth", return multiple periods
- Calculate differences between periods when explicitly requested
- Format results to show progression over time clearly

VALIDATION:
- Verify all periods exist in database
- Handle missing periods (some quarters might not have data)
- Inform user if any requested period is not available"""

