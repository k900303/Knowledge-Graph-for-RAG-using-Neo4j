"""Check actual parameter names in database"""
from neo4j_env import graph

# Check for profit-related parameters
profit_query = "MATCH (p:Parameter) WHERE p.parameter_name CONTAINS 'profit' OR p.parameter_name CONTAINS 'Profit' RETURN DISTINCT p.parameter_name ORDER BY p.parameter_name LIMIT 20"
results = graph.query(profit_query)

print("Parameters containing 'profit' or 'Profit':")
print("-" * 60)
for r in results:
    print(f"  - {r['p.parameter_name']}")

# Check specifically for Net profit
net_profit_query = "MATCH (p:Parameter) WHERE p.parameter_name CONTAINS 'Net' AND (p.parameter_name CONTAINS 'profit' OR p.parameter_name CONTAINS 'Profit') RETURN DISTINCT p.parameter_name ORDER BY p.parameter_name LIMIT 10"
net_results = graph.query(net_profit_query)

print("\n\nParameters containing 'Net' and 'profit':")
print("-" * 60)
if net_results:
    for r in net_results:
        print(f"  - {r['p.parameter_name']}")
else:
    print("  None found")




