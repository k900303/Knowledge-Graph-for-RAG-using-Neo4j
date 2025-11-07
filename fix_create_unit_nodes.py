"""
Script to manually create unit nodes in Neo4j
This should have been done in step 2.5 of the pipeline
"""

from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion

def main():
    print("\n" + "="*80)
    print("Creating Unit Nodes in Neo4j")
    print("="*80)
    
    ingestion = PEERSNeo4jIngestion()
    
    print("\nCreating ParameterUnit and ResultUnit nodes...")
    ingestion.create_unit_nodes()
    
    print("\n" + "="*80)
    print("Unit Nodes Creation Complete!")
    print("="*80)
    
    # Verify
    print("\nVerifying unit nodes...")
    result = ingestion.graph.query("MATCH (pu:ParameterUnit) RETURN count(pu) as count")
    print(f"ParameterUnit nodes: {result[0]['count']}")
    
    result = ingestion.graph.query("MATCH (ru:ResultUnit) RETURN count(ru) as count")
    print(f"ResultUnit nodes: {result[0]['count']}")

if __name__ == '__main__':
    main()



