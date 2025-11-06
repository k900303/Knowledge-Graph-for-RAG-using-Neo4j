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
OPTIONAL MATCH (p)-[:HAS_UNIT]->(pu:ParameterUnit)
OPTIONAL MATCH (pr)-[:HAS_UNIT]->(ru:ResultUnit)
RETURN c.company_name, p.parameter_name, pu.unit_id as parameter_unit_id, pu.value_name as parameter_unit_name, pu.short_name as parameter_unit, pr.period, pr.value, pr.currency, ru.unit_id as result_unit_id, ru.value_name as result_unit_name, ru.short_name as result_unit
ORDER BY pr.period ASC

TREND ANALYSIS:
- When user asks for "trend" or "growth", return multiple periods
- Calculate differences between periods when explicitly requested
- Format results to show progression over time clearly

VALIDATION:
- Verify all periods exist in database
- Handle missing periods (some quarters might not have data)
- Inform user if any requested period is not available"""

