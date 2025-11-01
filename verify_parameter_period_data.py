"""Verify specific parameter data for specific periods"""
from neo4j_env import graph

print("="*80)
print("VERIFYING: Parameter Data for Specific Periods")
print("="*80)

# Check Net margin specifically for 4QFY-2025
print("\n1. Net margin data for 4QFY-2025:")
print("-" * 80)
net_margin_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND p.parameter_name CONTAINS 'Net margin'
AND pr.period CONTAINS '4QFY-2025'
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
ORDER BY p.parameter_name
"""
net_results = graph.query(net_margin_query)
print(f"Net margin results for 4QFY-2025: {len(net_results)}")
if net_results:
    for r in net_results:
        print(f"  - {r['p.parameter_name']}: {r['pr.value']} ({r['pr.currency']}) - Growth: {r['pr.yoy_growth']}")
else:
    print("  ❌ No Net margin data for 4QFY-2025")

# Check what periods have Net margin data
print("\n2. Periods with Net margin data:")
print("-" * 80)
periods_net = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND p.parameter_name CONTAINS 'Net margin'
RETURN DISTINCT pr.period
ORDER BY pr.period DESC
LIMIT 10
"""
net_periods = graph.query(periods_net)
print(f"Periods with Net margin: {len(net_periods)}")
for r in net_periods:
    print(f"  - {r['pr.period']}")

# Check full query results
print("\n3. Complete Query Results (EBITDA margin AND Net margin for 4QFY-2025):")
print("-" * 80)
full_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
AND pr.period CONTAINS '4QFY-2025'
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
ORDER BY p.parameter_name, pr.period
"""
full_results = graph.query(full_query)
print(f"Total results: {len(full_results)}")

# Group by parameter
ebitda_results = [r for r in full_results if 'EBITDA margin' in r['p.parameter_name']]
net_margin_results = [r for r in full_results if 'Net margin' in r['p.parameter_name'] and 'EBITDA' not in r['p.parameter_name']]

print(f"\n  EBITDA margin results: {len(ebitda_results)}")
print(f"  Net margin results: {len(net_margin_results)}")

if net_margin_results:
    print("\n  Net margin data:")
    for r in net_margin_results:
        print(f"    - {r['p.parameter_name']}: {r['pr.value']} ({r['pr.currency']})")

# Check if we should suggest alternatives when period doesn't exist
print("\n4. Testing Missing Period Scenario:")
print("-" * 80)
# Try a period that doesn't exist
missing_period_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
AND pr.period CONTAINS '4QFY-2030'
RETURN c.company_name, p.parameter_name, pr.period, pr.value
LIMIT 5
"""
missing_results = graph.query(missing_period_query)
print(f"Results for non-existent period (4QFY-2030): {len(missing_results)}")

if len(missing_results) == 0:
    # Get closest available period
    closest_query = """
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name CONTAINS 'Kajaria' 
    AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
    RETURN DISTINCT pr.period
    ORDER BY pr.period DESC
    LIMIT 5
    """
    closest = graph.query(closest_query)
    print("  ✅ Suggested alternative periods:")
    for r in closest:
        print(f"    - {r['pr.period']}")





