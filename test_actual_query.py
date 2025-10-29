"""
Test the actual query execution against Neo4j
For query: "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG
from neo4j_env import graph


class MockLogManager:
    """Mock log manager for testing"""
    def __init__(self):
        self.logs = []
    
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
        print(f"[INFO] {message}")
    
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))
        print(f"[ERROR] {message}")
        if exception:
            import traceback
            traceback.print_exc()


def test_query():
    """Test the actual query generation and execution"""
    print("="*80)
    print("Testing Query: EBITDA margin and Net profit of Kajaria in Q3FY-2024")
    print("="*80)
    
    # Initialize GraphRAG
    log_manager = MockLogManager()
    graph_rag = PEERSGraphRAG(log_manager=log_manager)
    
    question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
    
    print(f"\n📝 Question: {question}\n")
    
    # Step 1: Generate Cypher query
    print("-" * 80)
    print("STEP 1: Generating Cypher Query")
    print("-" * 80)
    try:
        cypher_query = graph_rag.generate_cypher_only(question)
        print(f"\n✅ Generated Cypher Query:\n{cypher_query}\n")
        
        # Check for spacing issues
        if 'ORDER BY' in cypher_query:
            order_pos = cypher_query.upper().find('ORDER BY')
            if order_pos > 0:
                char_before = cypher_query[order_pos - 1]
                if char_before != ' ':
                    print(f"❌ ERROR: Missing space before ORDER BY! Found '{char_before}'")
                    return False
                else:
                    print("✅ Space before ORDER BY is correct")
        
        # Check query structure
        if 'HAS_PARAMETER' not in cypher_query.upper():
            print("❌ ERROR: Query missing HAS_PARAMETER relationship")
            return False
        
        if 'PERIODRESULT' not in cypher_query.upper():
            print("❌ ERROR: Query missing PeriodResult node")
            return False
        
        if 'Kajaria' not in cypher_query:
            print("❌ ERROR: Query missing company name filter")
            return False
        
        print("✅ Query structure validation passed")
        
    except Exception as e:
        print(f"❌ ERROR generating query: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Validate query syntax
    print("\n" + "-" * 80)
    print("STEP 2: Validating Query Syntax")
    print("-" * 80)
    try:
        is_valid = graph_rag._is_valid_cypher(cypher_query)
        if not is_valid:
            print("❌ ERROR: Query failed validation")
            return False
        print("✅ Query syntax is valid")
    except Exception as e:
        print(f"❌ ERROR validating query: {str(e)}")
        return False
    
    # Step 3: Execute query against Neo4j
    print("\n" + "-" * 80)
    print("STEP 3: Executing Query Against Neo4j")
    print("-" * 80)
    try:
        results = graph.query(cypher_query)
        print(f"\n✅ Query executed successfully!")
        print(f"📊 Number of results: {len(results)}")
        
        if results:
            print("\n📋 Sample Results (first 5):")
            print("-" * 80)
            for i, result in enumerate(results[:5], 1):
                print(f"\nResult {i}:")
                for key, value in result.items():
                    print(f"  {key}: {value}")
            
            if len(results) > 5:
                print(f"\n... and {len(results) - 5} more results")
            
            # Check if we got both parameters
            param_names = [r.get('p.parameter_name', r.get('parameter_name', '')) for r in results]
            unique_params = list(set(param_names))
            
            print(f"\n📈 Parameters found: {', '.join(unique_params)}")
            
            if 'EBITDA margin' in str(results) or 'EBITDA Margin' in str(results):
                print("✅ EBITDA margin found in results")
            else:
                print("⚠️  EBITDA margin not found in results (check parameter name in database)")
            
            if 'Net profit' in str(results) or 'Net Profit' in str(results):
                print("✅ Net profit found in results")
            else:
                print("⚠️  Net profit not found in results (check parameter name in database)")
            
            # Check period
            periods = [r.get('pr.period', r.get('period', '')) for r in results if r.get('pr.period') or r.get('period')]
            unique_periods = list(set(periods))
            if unique_periods:
                print(f"📅 Periods found: {', '.join(unique_periods)}")
                if any('3QFY-2024' in str(p) for p in unique_periods):
                    print("✅ Q3FY-2024 period found in results")
            
        else:
            print("\n⚠️  No results returned from query")
            print("\nPossible reasons:")
            print("  1. Company name mismatch (check if 'Kajaria Ceramics' exists in database)")
            print("  2. Parameter names don't match (check exact parameter names)")
            print("  3. Period '3QFY-2024' doesn't exist in database")
            print("  4. No data for this combination")
            
            # Try to help debug
            print("\n🔍 Debugging queries:")
            
            # Check if company exists
            company_check = "MATCH (c:Company) WHERE c.company_name CONTAINS 'Kajaria' RETURN c.company_name LIMIT 5"
            company_results = graph.query(company_check)
            if company_results:
                print(f"  ✅ Company exists: {[r['c.company_name'] for r in company_results]}")
            else:
                print("  ❌ No company found with 'Kajaria' in name")
            
            # Check if parameters exist
            param_check = "MATCH (p:Parameter) WHERE p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net profit' RETURN DISTINCT p.parameter_name LIMIT 10"
            param_results = graph.query(param_check)
            if param_results:
                print(f"  ✅ Parameters exist: {[r['p.parameter_name'] for r in param_results]}")
            else:
                print("  ❌ No matching parameters found")
            
            # Check if period exists
            period_check = "MATCH (pr:PeriodResult) WHERE pr.period CONTAINS '3QFY-2024' RETURN DISTINCT pr.period LIMIT 5"
            period_results = graph.query(period_check)
            if period_results:
                print(f"  ✅ Period exists: {[r['pr.period'] for r in period_results]}")
            else:
                print("  ❌ Period '3QFY-2024' not found")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR executing query: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n🧪 Testing Actual Query Execution\n")
    success = test_query()
    
    print("\n" + "="*80)
    if success:
        print("✅ TEST PASSED - Query executed successfully!")
    else:
        print("❌ TEST FAILED - Query execution had issues")
    print("="*80)

