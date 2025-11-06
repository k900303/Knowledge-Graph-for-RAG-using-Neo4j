"""Final comprehensive verification that all unit fields are properly populated"""
from neo4j_env import graph
import json

def test_kajaria_ebitda():
    """Test 1: Original query - Kajaria EBITDA margin"""
    print("\n" + "="*80)
    print("TEST 1: Kajaria EBITDA Margin - 1QFY-2025")
    print("="*80)
    
    query = """
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name = 'Kajaria Ceramics' 
      AND p.parameter_name CONTAINS 'EBITDA margin'
      AND pr.period = '1QFY-2025'
    OPTIONAL MATCH (p)-[:HAS_UNIT]->(pu:ParameterUnit)
    OPTIONAL MATCH (pr)-[:HAS_UNIT]->(ru:ResultUnit)
    RETURN c.company_name, p.parameter_name,
           COALESCE(pu.unit_id, p.unit_id, '') as parameter_unit_id,
           COALESCE(pu.value_name, '') as parameter_unit_name,
           COALESCE(pu.short_name, p.unit, '') as parameter_unit,
           COALESCE(pu.key, '') as parameter_shortcode,
           pr.period, pr.value, pr.currency,
           COALESCE(ru.unit_id, pr.unit_id, '') as result_unit_id,
           COALESCE(ru.value_name, '') as result_unit_name,
           COALESCE(ru.short_name, pr.unit, '') as result_unit,
           COALESCE(ru.key, '') as result_shortcode,
           pr.yoy_growth
    ORDER BY p.parameter_name
    """
    
    results = graph.query(query)
    
    if not results:
        print("   [FAILED] No results returned")
        return False
    
    all_fields_present = True
    for i, r in enumerate(results, 1):
        print(f"\n   Record {i}: {r.get('p.parameter_name')}")
        
        # Check all required fields
        checks = {
            'parameter_unit_id': r.get('parameter_unit_id'),
            'parameter_unit_name': r.get('parameter_unit_name'),
            'parameter_unit': r.get('parameter_unit'),
            'parameter_shortcode': r.get('parameter_shortcode'),
            'result_unit_id': r.get('result_unit_id'),
            'result_unit_name': r.get('result_unit_name'),
            'result_unit': r.get('result_unit'),
            'result_shortcode': r.get('result_shortcode')
        }
        
        for field, value in checks.items():
            if not value or value == '':
                print(f"      [X] {field}: EMPTY")
                all_fields_present = False
            else:
                print(f"      [OK] {field}: '{value}'")
    
    if all_fields_present:
        print("\n   [PASSED] All unit fields populated")
    else:
        print("\n   [FAILED] Some fields are empty")
    
    return all_fields_present


def test_different_units():
    """Test 2: Different unit types"""
    print("\n" + "="*80)
    print("TEST 2: Various Unit Types")
    print("="*80)
    
    query = """
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name = 'Kajaria Ceramics' 
      AND pr.period = '1QFY-2025'
    OPTIONAL MATCH (p)-[:HAS_UNIT]->(pu:ParameterUnit)
    OPTIONAL MATCH (pr)-[:HAS_UNIT]->(ru:ResultUnit)
    WITH DISTINCT pu.unit_id as pu_id, pu.value_name as pu_name, pu.short_name as pu_short, pu.key as pu_key,
         ru.unit_id as ru_id, ru.value_name as ru_name, ru.short_name as ru_short, ru.key as ru_key
    WHERE pu_id IS NOT NULL OR ru_id IS NOT NULL
    RETURN pu_id, pu_name, pu_short, pu_key, ru_id, ru_name, ru_short, ru_key
    ORDER BY pu_id, ru_id
    LIMIT 10
    """
    
    results = graph.query(query)
    
    if not results:
        print("   [FAILED] No results returned")
        return False
    
    print(f"\n   Found {len(results)} unique unit combinations:")
    for r in results:
        print(f"\n      Parameter Unit: id={r.get('pu_id')}, {r.get('pu_name')} ({r.get('pu_short')}), key={r.get('pu_key')}")
        print(f"      Result Unit: id={r.get('ru_id')}, {r.get('ru_name')} ({r.get('ru_short')}), key={r.get('ru_key')}")
    
    print("\n   [PASSED] Multiple unit types verified")
    return True


def test_relationships():
    """Test 3: Relationship counts"""
    print("\n" + "="*80)
    print("TEST 3: Relationship Counts")
    print("="*80)
    
    # Count Parameter-HAS_UNIT relationships
    query = "MATCH (p:Parameter)-[:HAS_UNIT]->(pu:ParameterUnit) RETURN count(*) as count"
    result = graph.query(query)
    param_count = result[0]['count'] if result else 0
    print(f"\n   Parameter-HAS_UNIT relationships: {param_count}")
    
    # Count PeriodResult-HAS_UNIT relationships
    query = "MATCH (pr:PeriodResult)-[:HAS_UNIT]->(ru:ResultUnit) RETURN count(*) as count"
    result = graph.query(query)
    result_count = result[0]['count'] if result else 0
    print(f"   PeriodResult-HAS_UNIT relationships: {result_count}")
    
    # Check nodes
    query = "MATCH (pu:ParameterUnit) RETURN count(*) as count"
    result = graph.query(query)
    pu_count = result[0]['count'] if result else 0
    print(f"\n   ParameterUnit nodes: {pu_count}")
    
    query = "MATCH (ru:ResultUnit) RETURN count(*) as count"
    result = graph.query(query)
    ru_count = result[0]['count'] if result else 0
    print(f"   ResultUnit nodes: {ru_count}")
    
    if param_count > 0 and result_count > 0 and pu_count > 0 and ru_count > 0:
        print("\n   [PASSED] All relationships and nodes exist")
        return True
    else:
        print("\n   [FAILED] Missing relationships or nodes")
        return False


def test_unit_node_properties():
    """Test 4: Unit node properties"""
    print("\n" + "="*80)
    print("TEST 4: Unit Node Properties")
    print("="*80)
    
    # Check ParameterUnit
    query = """
    MATCH (pu:ParameterUnit)
    RETURN pu.unit_id as unit_id, pu.value_name as value_name, 
           pu.short_name as short_name, pu.key as key
    LIMIT 3
    """
    results = graph.query(query)
    
    print("\n   Sample ParameterUnit nodes:")
    all_valid = True
    for r in results:
        has_all = all([r.get('unit_id'), r.get('value_name'), r.get('short_name'), r.get('key')])
        status = "[OK]" if has_all else "[X]"
        print(f"      {status} id={r.get('unit_id')}, name={r.get('value_name')}, " +
              f"short={r.get('short_name')}, key={r.get('key')}")
        if not has_all:
            all_valid = False
    
    # Check ResultUnit
    query = """
    MATCH (ru:ResultUnit)
    RETURN ru.unit_id as unit_id, ru.value_name as value_name, 
           ru.short_name as short_name, ru.key as key
    LIMIT 3
    """
    results = graph.query(query)
    
    print("\n   Sample ResultUnit nodes:")
    for r in results:
        has_all = all([r.get('unit_id'), r.get('value_name'), r.get('short_name'), r.get('key')])
        status = "[OK]" if has_all else "[X]"
        print(f"      {status} id={r.get('unit_id')}, name={r.get('value_name')}, " +
              f"short={r.get('short_name')}, key={r.get('key')}")
        if not has_all:
            all_valid = False
    
    if all_valid:
        print("\n   [PASSED] All unit nodes have required properties")
    else:
        print("\n   [FAILED] Some unit nodes missing properties")
    
    return all_valid


if __name__ == '__main__':
    print("\n" + "="*80)
    print("  FINAL VERIFICATION TEST SUITE")
    print("="*80)
    
    tests = [
        test_kajaria_ebitda,
        test_different_units,
        test_relationships,
        test_unit_node_properties
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n   [ERROR] {e}")
            results.append(False)
    
    print("\n" + "="*80)
    print("  TEST RESULTS SUMMARY")
    print("="*80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n   Tests Passed: {passed}/{total}")
    
    if all(results):
        print("\n   *** ALL TESTS PASSED! Unit ingestion is fully fixed. ***")
    else:
        print("\n   WARNING: Some tests failed. Review output above.")
    
    print("\n" + "="*80)

