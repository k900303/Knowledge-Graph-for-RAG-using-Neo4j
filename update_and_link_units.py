"""
Update Parameter and PeriodResult nodes with unit_id and create HAS_UNIT relationships
"""

from neo4j_env import graph
from csv_parser import parse_parameter_csv, parse_results_csv

def update_parameter_unit_ids():
    """Update Parameter nodes with correct unit_id values from CSV"""
    print("\n" + "="*80)
    print("Step 1: Updating Parameter nodes with unit_id")
    print("="*80)
    
    # Parse the parameters CSV again
    parameter_parser = parse_parameter_csv(
        'data/PEERS_PROD_RAW_CSV_DATA/parameters_kajaria_cid_18315.csv',
        target_cid="18315",
        allowed_types=["opssd", "sd"]
    )
    
    parameters = parameter_parser.get_parameters()
    print(f"\nUpdating {len(parameters)} parameters...")
    
    updated_count = 0
    for param in parameters:
        if param.unit_id and param.unit_id != '':
            # Update the parameter node with the correct unit_id
            query = """
            MATCH (p:Parameter {param_id: $param_id})
            SET p.unit_id = $unit_id
            RETURN p.param_id
            """
            try:
                graph.query(query, {"param_id": param.param_id, "unit_id": param.unit_id})
                updated_count += 1
            except Exception as e:
                print(f"  Error updating parameter {param.param_id}: {e}")
    
    print(f"  [OK] Updated {updated_count} Parameter nodes with unit_id")
    return updated_count


def update_period_result_unit_ids():
    """Update PeriodResult nodes with correct unit_id values from CSV"""
    print("\n" + "="*80)
    print("Step 2: Updating PeriodResult nodes with unit_id")
    print("="*80)
    
    # Parse the results CSV again
    results_parser = parse_results_csv(
        'data/PEERS_PROD_RAW_CSV_DATA/results_kajaria_cid_18315.csv',
        target_cid="18315"
    )
    
    results = results_parser.get_results()
    print(f"\nUpdating {len(results)} period results...")
    
    updated_count = 0
    for result in results:
        if result.unit_id and result.unit_id != '':
            # Update the period result node with the correct unit_id
            query = """
            MATCH (pr:PeriodResult {id: $id})
            SET pr.unit_id = $unit_id
            RETURN pr.id
            """
            try:
                graph.query(query, {"id": result.id, "unit_id": result.unit_id})
                updated_count += 1
            except Exception as e:
                print(f"  Error updating result {result.id}: {e}")
    
    print(f"  [OK] Updated {updated_count} PeriodResult nodes with unit_id")
    return updated_count


def create_parameter_unit_relationships():
    """Create Parameter-[:HAS_UNIT]->ParameterUnit relationships"""
    print("\n" + "="*80)
    print("Step 3: Creating Parameter-HAS_UNIT-ParameterUnit Relationships")
    print("="*80)
    
    query = """
    MATCH (p:Parameter)
    WHERE p.unit_id IS NOT NULL AND p.unit_id <> '' AND p.unit_id <> 'None'
    WITH p
    MATCH (pu:ParameterUnit {unit_id: p.unit_id})
    MERGE (p)-[:HAS_UNIT]->(pu)
    RETURN count(*) as relationships_created
    """
    
    result = graph.query(query)
    count = result[0]['relationships_created'] if result else 0
    print(f"  [OK] Created {count} Parameter-HAS_UNIT relationships")
    return count


def create_result_unit_relationships():
    """Create PeriodResult-[:HAS_UNIT]->ResultUnit relationships"""
    print("\n" + "="*80)
    print("Step 4: Creating PeriodResult-HAS_UNIT-ResultUnit Relationships")
    print("="*80)
    
    query = """
    MATCH (pr:PeriodResult)
    WHERE pr.unit_id IS NOT NULL AND pr.unit_id <> '' AND pr.unit_id <> 'None'
    WITH pr
    MATCH (ru:ResultUnit {unit_id: pr.unit_id})
    MERGE (pr)-[:HAS_UNIT]->(ru)
    RETURN count(*) as relationships_created
    """
    
    result = graph.query(query)
    count = result[0]['relationships_created'] if result else 0
    print(f"  [OK] Created {count} PeriodResult-HAS_UNIT relationships")
    return count


def verify_everything():
    """Verify the final state"""
    print("\n" + "="*80)
    print("Step 5: Verification")
    print("="*80)
    
    # Check Parameters
    query = """
    MATCH (p:Parameter)-[:HAS_UNIT]->(pu:ParameterUnit)
    RETURN p.parameter_name as param_name,
           p.unit_id as p_unit_id,
           pu.unit_id as pu_unit_id,
           pu.short_name as short_name,
           pu.value_name as value_name,
           pu.key as key
    LIMIT 5
    """
    results = graph.query(query)
    
    print("\n1. Sample Parameter-HAS_UNIT relationships:")
    if results:
        for r in results:
            print(f"\n   Parameter: {r['param_name']}")
            print(f"      p.unit_id: '{r['p_unit_id']}' -> pu.unit_id: '{r['pu_unit_id']}'")
            print(f"      value_name: '{r['value_name']}', short_name: '{r['short_name']}', key: '{r['key']}'")
    else:
        print("   ⚠️  No relationships found!")
    
    # Check PeriodResults
    query = """
    MATCH (pr:PeriodResult)-[:HAS_UNIT]->(ru:ResultUnit)
    RETURN pr.period as period,
           pr.unit_id as pr_unit_id,
           ru.unit_id as ru_unit_id,
           ru.short_name as short_name,
           ru.value_name as value_name,
           ru.key as key
    LIMIT 5
    """
    results = graph.query(query)
    
    print("\n2. Sample PeriodResult-HAS_UNIT relationships:")
    if results:
        for r in results:
            print(f"\n   Period: {r['period']}")
            print(f"      pr.unit_id: '{r['pr_unit_id']}' -> ru.unit_id: '{r['ru_unit_id']}'")
            print(f"      value_name: '{r['value_name']}', short_name: '{r['short_name']}', key: '{r['key']}'")
    else:
        print("   ⚠️  No relationships found!")
    
    # Test query with all fields
    print("\n3. Testing complete query for Kajaria Ceramics:")
    query = """
    MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
    WHERE c.company_name = 'Kajaria Ceramics' AND pr.period = '1QFY-2025'
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
    LIMIT 3
    """
    results = graph.query(query)
    
    if results:
        for i, r in enumerate(results, 1):
            print(f"\n   Record {i}:")
            print(f"      Parameter: {r['p.parameter_name']}")
            print(f"      parameter_unit_id: '{r['parameter_unit_id']}'")
            print(f"      parameter_unit_name: '{r['parameter_unit_name']}'")
            print(f"      parameter_unit: '{r['parameter_unit']}'")
            print(f"      parameter_shortcode: '{r['parameter_shortcode']}'")
            print(f"      result_unit_id: '{r['result_unit_id']}'")
            print(f"      result_unit_name: '{r['result_unit_name']}'")
            print(f"      result_unit: '{r['result_unit']}'")
            print(f"      result_shortcode: '{r['result_shortcode']}'")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("  FIXING UNIT DATA AND RELATIONSHIPS")
    print("="*80)
    
    update_parameter_unit_ids()
    update_period_result_unit_ids()
    create_parameter_unit_relationships()
    create_result_unit_relationships()
    verify_everything()
    
    print("\n" + "="*80)
    print("  COMPLETE!")
    print("="*80)



