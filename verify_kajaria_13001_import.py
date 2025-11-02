"""
Verify that only parameter_source_id=13001 data exists for Kajaria in Neo4j
"""

from neo4j_env import graph

def verify_kajaria_13001_data(cid: str = "18315"):
    """Verify Kajaria data contains only 13001 parameter_source_id"""
    print("\n" + "="*80)
    print(f"VERIFYING KAJARIA (cid={cid}) DATA IN NEO4J")
    print("="*80)
    
    try:
        # Count total PeriodResults for Kajaria
        query1 = """
        MATCH (c:Company {cid: $cid})-[:HAS_RESULT_IN_PERIOD]->(pr:PeriodResult)
        RETURN count(pr) as total_count
        """
        result1 = graph.query(query1, {"cid": cid})
        total_count = result1[0]['total_count'] if result1 else 0
        print(f"\n[1] Total PeriodResult nodes for Kajaria: {total_count:,}")
        
        # Extract parameter_source_id from PeriodResult IDs and count distribution
        query2 = """
        MATCH (c:Company {cid: $cid})-[:HAS_RESULT_IN_PERIOD]->(pr:PeriodResult)
        WITH pr.id as id_str
        WHERE id_str CONTAINS '_'
        WITH split(id_str, '_') as parts
        WHERE size(parts) >= 3
        RETURN parts[2] as param_source_id, count(*) as count
        ORDER BY count DESC
        LIMIT 10
        """
        result2 = graph.query(query2, {"cid": cid})
        
        print(f"\n[2] Parameter Source ID Distribution:")
        param_dist = {}
        for row in result2:
            param_id = row.get('param_source_id', 'unknown')
            count = row.get('count', 0)
            param_dist[param_id] = count
            marker = "[OK]" if param_id == "13001" else "[WARNING]"
            print(f"  {marker} {param_id}: {count:,} rows")
        
        # Check if only 13001 exists
        has_only_13001 = len(param_dist) == 1 and "13001" in param_dist and param_dist["13001"] == total_count
        
        # Count relationships
        query3 = """
        MATCH (c:Company {cid: $cid})-[:HAS_PARAMETER]->(p:Parameter)
        RETURN count(p) as param_count
        """
        result3 = graph.query(query3, {"cid": cid})
        param_count = result3[0]['param_count'] if result3 else 0
        print(f"\n[3] Total Parameters linked to Kajaria: {param_count:,}")
        
        # Sample PeriodResults to show structure
        query4 = """
        MATCH (c:Company {cid: $cid})-[:HAS_RESULT_IN_PERIOD]->(pr:PeriodResult)
        RETURN pr.id as id, pr.period as period, pr.value as value
        ORDER BY pr.period DESC
        LIMIT 5
        """
        result4 = graph.query(query4, {"cid": cid})
        print(f"\n[4] Sample PeriodResults (latest 5):")
        for row in result4:
            pr_id = row.get('id', '')
            period = row.get('period', '')
            value = row.get('value', '')
            param_source_id = pr_id.split('_')[2] if '_' in pr_id and len(pr_id.split('_')) >= 3 else 'unknown'
            marker = "[OK]" if param_source_id == "13001" else "[ERROR]"
            print(f"  {marker} ID: {pr_id[:50]}... | Period: {period} | Value: {value}")
        
        print(f"\n{'='*80}")
        if has_only_13001:
            print("[SUCCESS] VERIFICATION PASSED!")
            print(f"  - Only parameter_source_id=13001 found")
            print(f"  - Total PeriodResults: {total_count:,}")
            print(f"  - Total Parameters: {param_count:,}")
        else:
            print("[WARNING] VERIFICATION FAILED!")
            print(f"  - Expected: Only parameter_source_id=13001")
            print(f"  - Found: {list(param_dist.keys())}")
        print(f"{'='*80}")
        
        return {
            "total_period_results": total_count,
            "total_parameters": param_count,
            "parameter_source_ids": param_dist,
            "is_valid": has_only_13001
        }
        
    except Exception as e:
        print(f"\n[ERROR] Error during verification: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    verify_kajaria_13001_data("18315")

