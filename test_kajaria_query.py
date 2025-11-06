"""Test the Kajaria query with all unit fields"""
from neo4j_env import graph
import json

print("\n" + "="*80)
print("Testing Kajaria Query - EBITDA margin for 1QFY-2025")
print("="*80)

query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name = 'Kajaria Ceramics' 
  AND p.parameter_name CONTAINS 'EBITDA margin'
  AND pr.period = '1QFY-2025'
OPTIONAL MATCH (p)-[:HAS_UNIT]->(pu:ParameterUnit)
OPTIONAL MATCH (pr)-[:HAS_UNIT]->(ru:ResultUnit)
RETURN c.company_name, p.parameter_name,
       COALESCE(pu.unit_id, p.unit_id, '') as parameter_unit_id,
       COALESCE(pu.value_name, '') as parameter_unit_name,
       COALESCE(pu.short_name, p.unit, '') as parameter_unit,
       COALESCE(pu.key, '') as parameter_shortcode,
       pr.period, pr.value, pr.currency,
       COALESCE(ru.unit_id, pr.unit_id, '') as result_unit_id,
       COALESCE(ru.value_name, '') as result_unit_name,
       COALESCE(ru.short_name, pr.unit, '') as result_unit,
       COALESCE(ru.key, '') as result_shortcode,
       pr.yoy_growth
ORDER BY p.parameter_name
"""

results = graph.query(query)

if results:
    for i, r in enumerate(results, 1):
        print(f"\nRecord {i}:")
        print(json.dumps({
            "c.company_name": r.get('c.company_name'),
            "p.parameter_name": r.get('p.parameter_name'),
            "parameter_unit_id": r.get('parameter_unit_id'),
            "parameter_unit_name": r.get('parameter_unit_name'),
            "parameter_unit": r.get('parameter_unit'),
            "parameter_shortcode": r.get('parameter_shortcode'),
            "pr.currency": r.get('pr.currency'),
            "pr.period": r.get('pr.period'),
            "pr.value": r.get('pr.value'),
            "pr.yoy_growth": r.get('pr.yoy_growth'),
            "result_unit_id": r.get('result_unit_id'),
            "result_unit_name": r.get('result_unit_name'),
            "result_unit": r.get('result_unit'),
            "result_shortcode": r.get('result_shortcode')
        }, indent=2))
else:
    print("\n⚠️  No results found!")

print("\n" + "="*80)


