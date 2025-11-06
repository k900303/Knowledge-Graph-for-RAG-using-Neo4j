"""
Comparison Query Extension

Handles multi-company comparison queries
"""

COMPARISON_QUERY_EXTENSION = """
COMPARISON QUERY RULES:
- Support comparing 2 or more companies in a single query
- Use UNION or multiple MATCH clauses to compare different companies
- Always return company_name in results to distinguish between companies
- Support comparing same parameter across multiple companies
- Support comparing multiple parameters across multiple companies
- Format results to make comparisons easy (side-by-side in results)

COMPARISON PATTERNS:
- Single parameter, multiple companies: "Compare EBITA margin of Company A and Company B"
- Multiple parameters, multiple companies: "Compare revenue and profit of Company A vs Company B"
- Always include all requested companies in WHERE clause or use UNION

QUERY STRUCTURE FOR COMPARISONS:
Option 1 - UNION approach (when comparing same parameter):
MATCH (c1:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr1:PeriodResult)
WHERE c1.company_name CONTAINS 'Company A' AND p.parameter_name CONTAINS 'Parameter Name'
RETURN c1.company_name as company_name, p.parameter_name, pr1.period, pr1.value, pr1.currency
UNION
MATCH (c2:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr2:PeriodResult)
WHERE c2.company_name CONTAINS 'Company B' AND p.parameter_name CONTAINS 'Parameter Name'
RETURN c2.company_name as company_name, p.parameter_name, pr2.period, pr2.value, pr2.currency

Option 2 - Single MATCH with OR (when comparing same parameter):
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE (c.company_name CONTAINS 'Company A' OR c.company_name CONTAINS 'Company B')
  AND p.parameter_name CONTAINS 'Parameter Name'
OPTIONAL MATCH (p)-[:HAS_UNIT]->(pu:ParameterUnit)
OPTIONAL MATCH (pr)-[:HAS_UNIT]->(ru:ResultUnit)
RETURN c.company_name, p.parameter_name, pu.unit_id as parameter_unit_id, pu.value_name as parameter_unit_name, pu.short_name as parameter_unit, pr.period, pr.value, pr.currency, ru.unit_id as result_unit_id, ru.value_name as result_unit_name, ru.short_name as result_unit
ORDER BY c.company_name, pr.period

VALIDATION:
- Verify ALL companies exist before comparison
- Verify ALL parameters exist before comparison
- If any company or parameter not found, inform user clearly"""

