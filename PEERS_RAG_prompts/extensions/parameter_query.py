"""
Parameter Query Extension

Handles queries involving financial parameters (revenue, profit, EBITA margin, etc.)
"""

PARAMETER_QUERY_EXTENSION = """
PARAMETER QUERY RULES:
- ALWAYS use search_parameters tool to find exact parameter names BEFORE using them
- Use the EXACT parameter name(s) returned by search_parameters (never use user's original text directly)
- Support single parameter queries: "What is the revenue of Company X?"
- Support multiple parameter queries: "Show me revenue and profit of Company X"
- When multiple parameters are requested:
  1. Call search_parameters for EACH parameter mentioned (e.g., search "revenue", then search "profit")
  2. Collect all verified parameter names into a list
  3. Use ALL verified names in generate_parameter_query with parameter_names array
- Always link parameters through (Company)-[:HAS_PARAMETER]->(Parameter)-[:HAS_VALUE_IN_PERIOD]->(PeriodResult)
- Return parameter_name along with value, period, and currency for clarity
- Use parameter_names array format: ["Exact Parameter Name 1", "Exact Parameter Name 2"]

VALIDATION REQUIREMENTS:
- If search_parameters returns no matches, inform user - DO NOT fabricate parameter names
- Use the parameter_name from search_parameters matches (the exact database name)
- When user says "revenue", search_parameters may return "Revenue", "Revenue per share", etc. - use the best match

EXAMPLE MULTI-PARAMETER QUERY:
1. search_parameters("revenue") → Returns ["Revenue", "Revenue per share"]
2. search_parameters("profit") → Returns ["Profit", "Profit margin"]
3. search_company("Kajaria") → Returns "Kajaria Ceramics Limited"
4. generate_parameter_query(
     company_name="Kajaria Ceramics Limited",
     parameter_names=["Revenue", "Profit"],
     period="latest"
   )
5. Generated Cypher will use: WHERE (p.parameter_name CONTAINS 'Revenue' OR p.parameter_name CONTAINS 'Profit')"""

