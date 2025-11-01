"""
Comprehensive test: Validate parameters exist in DB, periods exist, 
and verify data is fetched and displayed correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG
from neo4j_env import graph


class MockLogManager:
    def __init__(self):
        self.logs = []
    def add_info_log(self, message, file_info=None):
        print(f"[INFO] {message}")
        self.logs.append(('info', message))
    def add_error_log(self, message, exception=None):
        print(f"[ERROR] {message}")
        self.logs.append(('error', message))


def validate_parameters_in_db(company, parameters):
    """Check if parameters exist in database for the company"""
    print(f"\n📋 Validating Parameters in Database for {company}:")
    print("-" * 80)
    
    all_exist = True
    for param in parameters:
        query = f"""
        MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)
        WHERE c.company_name CONTAINS '{company.split()[0]}'
        AND p.parameter_name CONTAINS '{param}'
        RETURN DISTINCT p.parameter_name
        LIMIT 5
        """
        results = graph.query(query)
        if results:
            print(f"  ✅ '{param}': Found {len(results)} variant(s)")
            for r in results[:3]:
                print(f"      - {r['p.parameter_name']}")
        else:
            print(f"  ❌ '{param}': NOT FOUND in database")
            all_exist = False
    
    return all_exist


def validate_period_in_db(company, period):
    """Check if period exists in database for the company"""
    print(f"\n📅 Validating Period in Database: {period}")
    print("-" * 80)
    
    query = f"""
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name CONTAINS '{company.split()[0]}'
    AND pr.period CONTAINS '{period}'
    RETURN DISTINCT pr.period
    LIMIT 5
    """
    results = graph.query(query)
    
    if results:
        print(f"  ✅ Period '{period}': EXISTS in database")
        print(f"      Found: {[r['pr.period'] for r in results]}")
        return True
    else:
        print(f"  ❌ Period '{period}': NOT FOUND in database")
        
        # Find closest periods
        closest_query = f"""
        MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
        WHERE c.company_name CONTAINS '{company.split()[0]}'
        RETURN DISTINCT pr.period
        ORDER BY pr.period DESC
        LIMIT 10
        """
        closest = graph.query(closest_query)
        if closest:
            print(f"  💡 Available periods:")
            for r in closest:
                print(f"      - {r['pr.period']}")
        return False


def test_full_flow(question, expected_params, expected_period):
    """Test the complete flow: validation -> query -> results -> synthesis"""
    print("\n" + "="*80)
    print(f"TESTING: {question}")
    print("="*80)
    
    graph_rag = PEERSGraphRAG(log_manager=MockLogManager())
    
    # Step 1: Decompose query
    print("\n1️⃣ QUERY DECOMPOSITION")
    print("-" * 80)
    decomposition = graph_rag._decompose_parameter_query(question)
    print(f"   Company: {decomposition['company']}")
    print(f"   Parameters: {decomposition['parameters']}")
    print(f"   Period: {decomposition['period']}")
    
    # Validate decomposition
    params_match = all(p in decomposition['parameters'] for p in expected_params)
    period_match = decomposition['period'] == expected_period
    
    print(f"\n   ✅ Parameters match: {params_match}")
    print(f"   ✅ Period matches: {period_match}")
    
    # Step 2: Validate parameters exist in DB
    print("\n2️⃣ DATABASE VALIDATION")
    print("-" * 80)
    params_exist = validate_parameters_in_db(decomposition['company'], decomposition['parameters'])
    period_exists = validate_period_in_db(decomposition['company'], decomposition['period'])
    
    # Step 3: Generate and execute query
    print("\n3️⃣ QUERY EXECUTION")
    print("-" * 80)
    try:
        cypher_query = graph_rag._generate_decomposed_query(decomposition)
        print(f"   Generated query: {cypher_query[:100]}...")
        
        results = graph_rag.execute_cypher_query(cypher_query)
        print(f"   ✅ Query executed: {len(results)} results returned")
        
        if results:
            # Check what was actually returned
            params_returned = set()
            periods_returned = set()
            
            for r in results:
                param = r.get('p.parameter_name', '')
                period = r.get('pr.period', '')
                if param:
                    params_returned.add(param)
                if period:
                    periods_returned.add(period)
            
            print(f"\n   📊 Results Analysis:")
            print(f"      Parameters returned: {len(params_returned)}")
            for p in params_returned:
                count = sum(1 for r in results if r.get('p.parameter_name', '').startswith(p.split()[0]))
                print(f"        - {p}: {count} records")
            print(f"      Periods returned: {', '.join(sorted(periods_returned))}")
            
        else:
            print("   ⚠️  No results returned")
        
        # Step 4: Test synthesis
        print("\n4️⃣ ANSWER SYNTHESIS")
        print("-" * 80)
        answer = graph_rag.synthesize_answer(question, results, "")
        
        # Check if answer mentions "no data found"
        has_no_data_msg = any(phrase in answer.lower() for phrase in [
            "no data found", "no information", "not available", 
            "no data for this", "cannot find"
        ])
        
        # Check if answer contains actual values
        has_values = any(char.isdigit() for char in answer[:100])
        
        print(f"   Answer length: {len(answer)} characters")
        print(f"   Contains 'no data' message: {has_no_data_msg}")
        print(f"   Contains numeric values: {has_values}")
        
        if has_no_data_msg and len(results) > 0:
            print("   ⚠️  WARNING: Answer says 'no data' but results exist!")
        elif len(results) > 0 and not has_no_data_msg:
            print("   ✅ Answer correctly presents data")
        
        print(f"\n   Preview: {answer[:300]}...")
        
        return {
            'decomposition_correct': params_match and period_match,
            'params_exist_in_db': params_exist,
            'period_exists_in_db': period_exists,
            'query_executed': len(results) > 0,
            'results_count': len(results),
            'synthesis_presents_data': not has_no_data_msg if len(results) > 0 else True
        }
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    print("\n🧪 COMPREHENSIVE PARAMETER & PERIOD VALIDATION TEST\n")
    
    # Test 1: User's query
    question1 = "EBITDA margin and Net margin of Kajaria in 4QFY-2025"
    result1 = test_full_flow(question1, ['EBITDA margin', 'Net margin'], '4QFY-2025')
    
    # Test 2: Different period
    question2 = "EBITDA margin of Kajaria in 3QFY-2024"
    result2 = test_full_flow(question2, ['EBITDA margin'], '3QFY-2024')
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for i, (q, r) in enumerate([(question1, result1), (question2, result2)], 1):
        if r:
            print(f"\nTest {i}: {q[:50]}...")
            print(f"  ✅ Decomposition: {r['decomposition_correct']}")
            print(f"  ✅ Parameters exist: {r['params_exist_in_db']}")
            print(f"  ✅ Period exists: {r['period_exists_in_db']}")
            print(f"  ✅ Query executed: {r['query_executed']} ({r['results_count']} results)")
            print(f"  ✅ Synthesis works: {r['synthesis_presents_data']}")





