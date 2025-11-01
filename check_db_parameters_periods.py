"""
Check what parameters and periods exist in the database for Kajaria
This helps verify that queries fetch and display available data
"""

from neo4j_env import graph

print("="*80)
print("CHECKING DATABASE: Parameters and Periods for Kajaria")
print("="*80)

# 1. Check all companies with Kajaria in name
print("\n1. Companies matching 'Kajaria':")
print("-" * 80)
company_query = "MATCH (c:Company) WHERE c.company_name CONTAINS 'Kajaria' RETURN c.company_name, c.cid ORDER BY c.company_name"
companies = graph.query(company_query)
for r in companies:
    print(f"  - {r['c.company_name']} (CID: {r['c.cid']})")

# 2. Check all parameters for Kajaria
print("\n2. All Parameters available for Kajaria:")
print("-" * 80)
params_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)
WHERE c.company_name CONTAINS 'Kajaria'
RETURN DISTINCT p.parameter_name
ORDER BY p.parameter_name
"""
params = graph.query(params_query)
print(f"Total parameters: {len(params)}")
for i, r in enumerate(params[:30], 1):  # Show first 30
    print(f"  {i}. {r['p.parameter_name']}")

# 3. Check specific parameters (EBITDA margin, Net margin, Net profit)
print("\n3. Specific Parameters Check:")
print("-" * 80)
specific_params = ['EBITDA margin', 'Net margin', 'Net profit', 'Net operating profit']
for param_name in specific_params:
    check_query = f"""
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)
    WHERE c.company_name CONTAINS 'Kajaria' 
    AND p.parameter_name CONTAINS '{param_name}'
    RETURN DISTINCT p.parameter_name
    """
    results = graph.query(check_query)
    if results:
        print(f"  ✅ '{param_name}': Found {len(results)} variants")
        for r in results:
            print(f"      - {r['p.parameter_name']}")
    else:
        print(f"  ❌ '{param_name}': NOT FOUND")

# 4. Check periods available for Kajaria
print("\n4. Periods Available for Kajaria:")
print("-" * 80)
periods_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria'
RETURN DISTINCT pr.period
ORDER BY pr.period DESC
LIMIT 20
"""
periods = graph.query(periods_query)
print(f"Total periods: {len(periods)}")
for r in periods:
    print(f"  - {r['pr.period']}")

# 5. Check data for specific query: EBITDA margin and Net margin in 4QFY-2025
print("\n5. Testing Query: EBITDA margin and Net margin in 4QFY-2025:")
print("-" * 80)
test_query = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
AND pr.period CONTAINS '4QFY-2025'
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
ORDER BY p.parameter_name, pr.period
"""
results = graph.query(test_query)
print(f"Results for 4QFY-2025: {len(results)}")
if results:
    print("\n  Sample results:")
    for i, r in enumerate(results[:5], 1):
        print(f"  {i}. {r['p.parameter_name']} - {r['pr.period']} - Value: {r['pr.value']}")
else:
    print("  ⚠️  No data for 4QFY-2025")
    
    # Check what periods have this data
    print("\n  Checking available periods for these parameters:")
    period_check = """
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name CONTAINS 'Kajaria' 
    AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
    RETURN DISTINCT pr.period
    ORDER BY pr.period DESC
    LIMIT 10
    """
    available = graph.query(period_check)
    if available:
        print("  Available periods:")
        for r in available:
            print(f"    - {r['pr.period']}")

# 6. Check data for 4QFY-2024 (to compare)
print("\n6. Testing Query: EBITDA margin and Net margin in 4QFY-2024:")
print("-" * 80)
test_query_2024 = """
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Kajaria' 
AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net margin')
AND pr.period CONTAINS '4QFY-2024'
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
ORDER BY p.parameter_name, pr.period
"""
results_2024 = graph.query(test_query_2024)
print(f"Results for 4QFY-2024: {len(results_2024)}")
if results_2024:
    print("\n  Sample results:")
    for i, r in enumerate(results_2024[:5], 1):
        print(f"  {i}. {r['p.parameter_name']} - {r['pr.period']} - Value: {r['pr.value']}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total parameters for Kajaria: {len(params)}")
print(f"Total periods for Kajaria: {len(periods)}")
print(f"4QFY-2025 results: {len(results)}")
print(f"4QFY-2024 results: {len(results_2024)}")





