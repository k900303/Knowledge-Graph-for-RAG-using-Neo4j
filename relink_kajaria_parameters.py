"""
Re-link Parameters to Kajaria Company node
This ensures Parameter nodes exist and are linked via HAS_PARAMETER relationship
"""

from neo4j_env import graph

def relink_kajaria_parameters(cid: str = "18315"):
    """Re-link Parameter nodes to Kajaria via PeriodResult relationships"""
    print("\n" + "="*80)
    print(f"RE-LINKING PARAMETERS FOR KAJARIA (cid={cid})")
    print("="*80)
    
    try:
        # Step 1: Find all unique parameters from PeriodResults
        print("\n[1/3] Finding unique parameters from PeriodResults...")
        query1 = """
        MATCH (c:Company {cid: $cid})-[:HAS_RESULT_IN_PERIOD]->(pr:PeriodResult)
        WITH DISTINCT pr.pid as pid
        WHERE pid IS NOT NULL AND pid <> ''
        RETURN pid
        ORDER BY pid
        """
        result1 = graph.query(query1, {"cid": cid})
        unique_pids = [row['pid'] for row in result1]
        print(f"  [OK] Found {len(unique_pids):,} unique parameter IDs")
        
        # Step 2: Create Parameter nodes if they don't exist
        print("\n[2/3] Creating/ensuring Parameter nodes exist...")
        created_params = 0
        for pid in unique_pids[:10]:  # Show first 10
            query2 = """
            MERGE (p:Parameter {param_id: $pid})
            ON CREATE SET p.param_id = $pid
            RETURN p.param_id
            """
            try:
                graph.query(query2, {"pid": pid})
                created_params += 1
            except:
                pass
        
        print(f"  [OK] Processed parameter nodes")
        
        # Step 3: Create HAS_PARAMETER relationships
        print("\n[3/3] Creating Company-Parameter relationships...")
        query3 = """
        MATCH (c:Company {cid: $cid})
        MATCH (pr:PeriodResult {cid: $cid})
        WHERE pr.pid IS NOT NULL AND pr.pid <> ''
        WITH DISTINCT c, pr.pid as pid
        MATCH (p:Parameter {param_id: pid})
        MERGE (c)-[:HAS_PARAMETER]->(p)
        RETURN count(DISTINCT p) as param_count
        """
        result3 = graph.query(query3, {"cid": cid})
        param_count = result3[0]['param_count'] if result3 else 0
        print(f"  [OK] Linked {param_count:,} Parameters to Kajaria")
        
        print(f"\n{'='*80}")
        print("RE-LINKING COMPLETED!")
        print(f"{'='*80}")
        print(f"Unique Parameter IDs found: {len(unique_pids):,}")
        print(f"Parameters linked to Kajaria: {param_count:,}")
        print(f"{'='*80}")
        
        return param_count
        
    except Exception as e:
        print(f"\n[ERROR] Error during re-linking: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    relink_kajaria_parameters("18315")

