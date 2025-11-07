"""Recreate ResultUnit nodes with the updated CSV file"""
from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion

print("\n" + "="*80)
print("Recreating ResultUnit Nodes with Updated Definitions")
print("="*80)

ingestion = PEERSNeo4jIngestion()

# Delete existing ResultUnit nodes
print("\n1. Deleting existing ResultUnit nodes...")
query = "MATCH (ru:ResultUnit) DETACH DELETE ru"
ingestion.graph.query(query)
print("   [OK] Deleted existing ResultUnit nodes")

# Recreate with updated CSV
print("\n2. Creating ResultUnit nodes from updated CSV...")
ingestion.create_unit_nodes()

# Recreate relationships
print("\n3. Recreating PeriodResult-HAS_UNIT relationships...")
query = """
MATCH (pr:PeriodResult)
WHERE pr.unit_id IS NOT NULL AND pr.unit_id <> '' AND pr.unit_id <> 'None'
WITH pr
MATCH (ru:ResultUnit {unit_id: pr.unit_id})
MERGE (pr)-[:HAS_UNIT]->(ru)
RETURN count(*) as relationships_created
"""
result = ingestion.graph.query(query)
count = result[0]['relationships_created'] if result else 0
print(f"   [OK] Created {count} PeriodResult-HAS_UNIT relationships")

# Verify
print("\n4. Verification:")
query = """
MATCH (pr:PeriodResult)-[:HAS_UNIT]->(ru:ResultUnit)
WHERE pr.period = '1QFY-2025'
RETURN pr.period, ru.unit_id, ru.value_name, ru.short_name, ru.key, count(*) as count
"""
results = ingestion.graph.query(query)
for r in results:
    print(f"   Period {r['pr.period']}: unit_id={r['ru.unit_id']}, " +
          f"{r['ru.value_name']} ({r['ru.short_name']}), key={r['ru.key']}, count={r['count']}")

print("\n" + "="*80)
print("Complete!")
print("="*80)



