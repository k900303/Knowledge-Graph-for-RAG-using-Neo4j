"""
Delete Kajaria (cid=18315) data from Neo4j
Run this separately after filtering the CSV
"""

from neo4j_env import graph

def delete_kajaria_data(cid: str = "18315"):
    """Delete all Kajaria-related data from Neo4j"""
    print("\n" + "="*80)
    print(f"DELETING KAJARIA (cid={cid}) DATA FROM NEO4J")
    print("="*80)
    
    try:
        # Step 1: Delete PeriodResult nodes and their relationships for this company
        print("\n[1/3] Deleting PeriodResult nodes for Kajaria...")
        delete_query1 = """
        MATCH (c:Company {cid: $cid})
        MATCH (c)-[:HAS_RESULT_IN_PERIOD]->(pr:PeriodResult)
        DETACH DELETE pr
        RETURN count(pr) as deleted_count
        """
        result1 = graph.query(delete_query1, {"cid": cid})
        deleted_pr = result1[0]['deleted_count'] if result1 else 0
        print(f"  [OK] Deleted {deleted_pr:,} PeriodResult nodes")
        
        # Step 2: Delete Parameter-PeriodResult relationships
        print("\n[2/3] Cleaning up Parameter-PeriodResult relationships...")
        delete_query2 = """
        MATCH (p:Parameter)-[r:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult {cid: $cid})
        DELETE r
        RETURN count(r) as deleted_count
        """
        result2 = graph.query(delete_query2, {"cid": cid})
        deleted_rel = result2[0]['deleted_count'] if result2 else 0
        print(f"  [OK] Deleted {deleted_rel:,} Parameter-PeriodResult relationships")
        
        # Step 3: Delete Company-Parameter relationships for this company
        print("\n[3/3] Deleting Company-Parameter relationships for Kajaria...")
        delete_query3 = """
        MATCH (c:Company {cid: $cid})-[r:HAS_PARAMETER]->(p:Parameter)
        DELETE r
        RETURN count(r) as deleted_count
        """
        result3 = graph.query(delete_query3, {"cid": cid})
        deleted_param_rel = result3[0]['deleted_count'] if result3 else 0
        print(f"  [OK] Deleted {deleted_param_rel:,} Company-Parameter relationships")
        
        print(f"\n{'='*80}")
        print("CLEANUP COMPLETED!")
        print(f"{'='*80}")
        print(f"Deleted PeriodResults: {deleted_pr:,}")
        print(f"Deleted Parameter-PeriodResult relationships: {deleted_rel:,}")
        print(f"Deleted Company-Parameter relationships: {deleted_param_rel:,}")
        print(f"{'='*80}")
        
        return {
            "period_results": deleted_pr,
            "parameter_period_relationships": deleted_rel,
            "company_parameter_relationships": deleted_param_rel
        }
        
    except Exception as e:
        print(f"\n[ERROR] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    delete_kajaria_data("18315")

