"""Test the user's specific query: EBITDA margin and Net margin of Kajaria in 4QFY-2025"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG
from neo4j_env import graph


class MockLogManager:
    def __init__(self):
        self.logs = []
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
        print(f"[INFO] {message}")
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))
        print(f"[ERROR] {message}")


def test_query():
    print("="*80)
    print("Testing: EBITDA margin and Net margin of Kajaria in 4QFY-2025")
    print("="*80)
    
    graph_rag = PEERSGraphRAG(log_manager=MockLogManager())
    question = "EBITDA margin and Net margin of Kajaria in 4QFY-2025"
    
    print(f"\n📝 Question: {question}\n")
    
    # Test decomposition
    print("-" * 80)
    print("STEP 1: Query Decomposition")
    print("-" * 80)
    decomposition = graph_rag._decompose_parameter_query(question)
    print(f"\nDecomposition:")
    print(f"  Company: {decomposition['company']}")
    print(f"  Parameters: {decomposition['parameters']}")
    print(f"  Period: {decomposition['period']}")
    print(f"  Multi-parameter: {decomposition['is_multi_parameter']}")
    
    # Verify fixes
    checks_passed = 0
    total_checks = 3
    
    # Check 1: Period should be 4QFY-2025
    if decomposition['period'] == '4QFY-2025':
        print("  ✅ Period detection: CORRECT (4QFY-2025)")
        checks_passed += 1
    else:
        print(f"  ❌ Period detection: WRONG (got {decomposition['period']}, expected 4QFY-2025)")
    
    # Check 2: Should have both parameters
    if 'EBITDA margin' in decomposition['parameters']:
        print("  ✅ EBITDA margin detection: CORRECT")
    else:
        print("  ❌ EBITDA margin detection: MISSING")
    
    if 'Net margin' in decomposition['parameters']:
        print("  ✅ Net margin detection: CORRECT")
        checks_passed += 1
    else:
        print(f"  ❌ Net margin detection: MISSING (got: {decomposition['parameters']})")
    
    # Check 3: Should be multi-parameter
    if decomposition['is_multi_parameter']:
        print("  ✅ Multi-parameter flag: CORRECT")
        checks_passed += 1
    else:
        print("  ❌ Multi-parameter flag: WRONG")
    
    # Generate query
    print("\n" + "-" * 80)
    print("STEP 2: Generating Cypher Query")
    print("-" * 80)
    query = graph_rag._generate_decomposed_query(decomposition)
    print(f"\nGenerated Query:\n{query}\n")
    
    # Check query has both parameters
    if 'EBITDA margin' in query and 'Net margin' in query:
        print("  ✅ Query includes both parameters")
    else:
        print("  ❌ Query missing one or both parameters")
    
    # Check period in query
    if '4QFY-2025' in query:
        print("  ✅ Query includes correct period (4QFY-2025)")
    else:
        print(f"  ⚠️  Query period: {query[query.find('4QFY'):query.find('4QFY')+10] if '4QFY' in query else 'NOT FOUND'}")
    
    # Execute query
    print("\n" + "-" * 80)
    print("STEP 3: Executing Query")
    print("-" * 80)
    try:
        results = graph.query(query)
        print(f"\n✅ Query executed successfully!")
        print(f"📊 Number of results: {len(results)}")
        
        if results:
            print("\n📋 Sample Results (first 3):")
            for i, result in enumerate(results[:3], 1):
                print(f"\nResult {i}:")
                for key, value in result.items():
                    print(f"  {key}: {value}")
            
            # Check what parameters we got
            param_names = [r.get('p.parameter_name', '') for r in results]
            unique_params = list(set(param_names))
            print(f"\n📈 Parameters found: {unique_params}")
            
        else:
            print("\n⚠️  No results (might be because 4QFY-2025 doesn't exist, but query structure is correct)")
            
    except Exception as e:
        print(f"\n❌ Error executing query: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print(f"Tests Passed: {checks_passed}/{total_checks}")
    print("="*80)


if __name__ == '__main__':
    test_query()




