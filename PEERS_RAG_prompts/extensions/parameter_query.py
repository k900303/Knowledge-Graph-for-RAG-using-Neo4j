"""
Parameter Query Extension

Handles queries involving financial parameters (revenue, profit, EBITA margin, etc.)
"""

PARAMETER_QUERY_EXTENSION = """
PARAMETER QUERY RULES:
- ALWAYS verify parameter exists using verify_parameter_exists tool BEFORE using it
- Use the EXACT parameter name returned by verification (never use user's original text)
- Support single parameter queries: "What is the revenue of Company X?"
- Support multiple parameter queries: "Show me revenue and profit of Company X"
- When multiple parameters are requested, include all in the same Cypher query
- Always link parameters through (Company)-[:HAS_PARAMETER]->(Parameter)-[:HAS_VALUE_IN_PERIOD]->(PeriodResult)
- Return parameter_name along with value, period, and currency for clarity

VALIDATION REQUIREMENTS:
- If parameter verification fails, inform user - DO NOT fabricate parameter names
- If fuzzy match found, use the verified exact name, not the user's approximation

EXAMPLE MULTI-PARAMETER QUERY:
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Company Name' 
  AND (p.parameter_name CONTAINS 'Revenue' OR p.parameter_name CONTAINS 'Profit')
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency
ORDER BY p.parameter_name, pr.period"""

