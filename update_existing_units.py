"""
Update Existing Units in Neo4j
Updates Parameter and PeriodResult nodes to use display names instead of IDs
"""

from neo4j_env import graph, get_graph
from unit_mapper import UnitMapper
import sys


def update_parameter_units(mapper: UnitMapper, dry_run: bool = False):
    """
    Update all Parameter nodes to use unit display names instead of IDs
    
    Args:
        mapper: UnitMapper instance
        dry_run: If True, only show what would be updated without making changes
    """
    print("\n" + "="*80)
    print("Updating Parameter Unit Values")
    print("="*80)
    
    # First, get all parameters with their current unit values
    cypher_query = """
    MATCH (p:Parameter)
    WHERE p.unit IS NOT NULL
    RETURN p.param_id, p.parameter_name, p.unit as current_unit
    LIMIT 1000
    """
    
    result = graph.query(cypher_query)
    total_params = len(result)
    print(f"Found {total_params} parameters to check (showing first 1000)")
    
    if total_params == 0:
        print("[INFO] No parameters found to update")
        return
    
    # Count updates needed
    updates_needed = 0
    updates_skipped = 0
    sample_updates = []
    
    for row in result:
        param_id = row.get('param_id')
        param_name = row.get('parameter_name', 'Unknown')
        current_unit = row.get('current_unit')
        
        # Check if current unit is already a display name (not numeric)
        # If it's numeric (ID), map it; if it's already a name, skip
        try:
            # Try to convert to int - if it succeeds, it's an ID
            int(current_unit)
            is_id = True
        except (ValueError, TypeError):
            # Not numeric, might already be a display name
            is_id = False
        
        if is_id:
            # Map ID to display name
            display_name = mapper.get_param_unit_display(current_unit)
            
            if display_name != current_unit:
                updates_needed += 1
                if len(sample_updates) < 10:
                    sample_updates.append({
                        'param_id': param_id,
                        'param_name': param_name,
                        'old': current_unit,
                        'new': display_name
                    })
            else:
                updates_skipped += 1
        else:
            updates_skipped += 1
    
    print(f"\n[ANALYSIS]")
    print(f"  Parameters needing update: {updates_needed}")
    print(f"  Parameters already correct or skipped: {updates_skipped}")
    
    if sample_updates:
        print(f"\n[Sample Updates (first 10)]:")
        for sample in sample_updates:
            print(f"  {sample['param_id']}: '{sample['old']}' -> '{sample['new']}'")
    
    if dry_run:
        print("\n[DRY RUN] No changes made. Remove --dry-run flag to apply updates.")
        return
    
    if updates_needed == 0:
        print("\n[INFO] No updates needed - all units are already display names")
        return
    
    # Perform batch update
    print(f"\n[UPDATING] Applying updates to {updates_needed} parameters...")
    
    # Update in batches using Cypher
    cypher_update = """
    MATCH (p:Parameter)
    WHERE p.unit IS NOT NULL
    WITH p, p.unit as current_unit
    WHERE current_unit =~ '^[0-9]+$'  // Only update if unit is numeric (ID)
    SET p.unit = CASE
        WHEN current_unit = '1' THEN 'Amount'
        WHEN current_unit = '2' THEN '%'
        WHEN current_unit = '3' THEN 'Days'
        WHEN current_unit = '4' THEN 'Years'
        WHEN current_unit = '6' THEN '#'
        WHEN current_unit = '7' THEN 'Person-Months'
        WHEN current_unit = '8' THEN 'sq ft'
        WHEN current_unit = '9' THEN 'x'
        WHEN current_unit = '12' THEN 'Months'
        WHEN current_unit = '13' THEN 'Weeks'
        WHEN current_unit = '14' THEN 'MB'
        WHEN current_unit = '15' THEN 'Petabytes'
        WHEN current_unit = '16' THEN 'lbs'
        WHEN current_unit = '19' THEN 'Minutes'
        WHEN current_unit = '20' THEN 'bbl'
        WHEN current_unit = '21' THEN 'bpd'
        WHEN current_unit = '22' THEN 'mmbtu'
        WHEN current_unit = '24' THEN 'mcf'
        WHEN current_unit = '27' THEN 'Miles'
        WHEN current_unit = '28' THEN 'hl'
        WHEN current_unit = '29' THEN 'MW'
        WHEN current_unit = '30' THEN 'mcfe'
        WHEN current_unit = '31' THEN 'boe'
        WHEN current_unit = '32' THEN 'Acres'
        WHEN current_unit = '33' THEN 'Gallons'
        WHEN current_unit = '34' THEN 'btu'
        WHEN current_unit = '35' THEN 'cf'
        WHEN current_unit = '36' THEN 'cfe'
        WHEN current_unit = '37' THEN 'GWh'
        WHEN current_unit = '38' THEN 'Tons'
        WHEN current_unit = '40' THEN 'km'
        WHEN current_unit = '41' THEN 'barrel miles'
        WHEN current_unit = '42' THEN 'cubic metres'
        WHEN current_unit = '43' THEN 'litres'
        WHEN current_unit = '44' THEN 'MWh'
        WHEN current_unit = '45' THEN 'Inches'
        WHEN current_unit = '46' THEN 'MVA'
        WHEN current_unit = '47' THEN 'Gbps'
        WHEN current_unit = '48' THEN 'KWh'
        WHEN current_unit = '49' THEN 'Dekatherms'
        WHEN current_unit = '50' THEN 'cubic yards'
        WHEN current_unit = '51' THEN 'hrs'
        WHEN current_unit = '52' THEN 'dwt'
        WHEN current_unit = '53' THEN 'short green tons'
        WHEN current_unit = '54' THEN 'board feet'
        WHEN current_unit = '55' THEN 'grams'
        WHEN current_unit = '56' THEN 'kgs'
        WHEN current_unit = '57' THEN 'ozt'
        WHEN current_unit = '58' THEN 'feet'
        WHEN current_unit = '59' THEN 'sq mt'
        WHEN current_unit = '60' THEN 'Metres'
        WHEN current_unit = '61' THEN 'Carat'
        WHEN current_unit = '62' THEN 'Ntk'
        WHEN current_unit = '63' THEN 'Sq KM'
        WHEN current_unit = '64' THEN 'GEO'
        WHEN current_unit = '65' THEN 'kcal'
        WHEN current_unit = '66' THEN 'J'
        WHEN current_unit = '67' THEN 'bu'
        WHEN current_unit = '68' THEN 'cwt'
        WHEN current_unit = '69' THEN 'oz'
        WHEN current_unit = '70' THEN 'gcal'
        WHEN current_unit = '71' THEN 'short ton'
        WHEN current_unit = '72' THEN 'long ton'
        WHEN current_unit = '73' THEN 'wmt'
        WHEN current_unit = '74' THEN 'dmt'
        WHEN current_unit = '75' THEN 'hhp'
        WHEN current_unit = '76' THEN 'mbf'
        WHEN current_unit = '77' THEN 'msf'
        WHEN current_unit = '78' THEN 'mlf'
        WHEN current_unit = '79' THEN 'ccf'
        WHEN current_unit = '80' THEN 'GJ'
        WHEN current_unit = '81' THEN 'TJ'
        WHEN current_unit = '82' THEN 'PJ'
        WHEN current_unit = '83' THEN 'TEU'
        WHEN current_unit = '84' THEN 'W'
        WHEN current_unit = '85' THEN 'thm'
        WHEN current_unit = '86' THEN 'bps'
        WHEN current_unit = '87' THEN 'TH/s'
        WHEN current_unit = '88' THEN 'EH/s'
        WHEN current_unit = '89' THEN 'ha'
        ELSE current_unit
    END
    RETURN count(p) as updated_count
    """
    
    # Actually, let's do it more programmatically using the mapper
    # Get all unique unit values that are numeric
    get_numeric_units = """
    MATCH (p:Parameter)
    WHERE p.unit IS NOT NULL AND p.unit =~ '^[0-9]+$'
    RETURN DISTINCT p.unit as unit_id
    """
    
    numeric_units = graph.query(get_numeric_units)
    print(f"Found {len(numeric_units)} unique numeric unit IDs to map")
    
    # Update each unique unit ID
    updated_total = 0
    for row in numeric_units:
        unit_id = row.get('unit_id')
        display_name = mapper.get_param_unit_display(unit_id)
        
        if display_name != unit_id:
            update_query = """
            MATCH (p:Parameter)
            WHERE p.unit = $unit_id
            SET p.unit = $display_name
            RETURN count(p) as count
            """
            
            result = graph.query(update_query, {
                "unit_id": unit_id,
                "display_name": display_name
            })
            
            count = result[0]['count'] if result else 0
            updated_total += count
            print(f"  Updated {count} parameters: unit '{unit_id}' -> '{display_name}'")
    
    print(f"\n[OK] Updated {updated_total} parameter nodes")
    print("="*80)


def update_result_units(mapper: UnitMapper, dry_run: bool = False):
    """
    Update all PeriodResult nodes to use unit display names instead of IDs
    
    Args:
        mapper: UnitMapper instance
        dry_run: If True, only show what would be updated without making changes
    """
    print("\n" + "="*80)
    print("Updating PeriodResult Unit Values")
    print("="*80)
    
    # PeriodResult stores unit as integer or string in Neo4j
    # First, check what types we have
    cypher_query = """
    MATCH (pr:PeriodResult)
    WHERE pr.unit IS NOT NULL
    RETURN pr.id, pr.unit as current_unit, 
           CASE WHEN pr.unit IS STRING THEN 'string' 
                WHEN pr.unit IS INTEGER THEN 'integer' 
                ELSE 'other' END as unit_type
    LIMIT 1000
    """
    
    result = graph.query(cypher_query)
    total_results = len(result)
    print(f"Found {total_results} period results to check (showing first 1000)")
    
    if total_results == 0:
        print("[INFO] No period results found to update")
        return
    
    # Count updates needed
    updates_needed = 0
    updates_skipped = 0
    sample_updates = []
    integer_units = []
    string_units = []
    
    for row in result:
        result_id = row.get('id')
        current_unit = row.get('current_unit')
        unit_type = row.get('unit_type')
        
        if unit_type == 'integer':
            integer_units.append(current_unit)
            # Map integer ID to display name
            display_name = mapper.get_result_unit_display(current_unit)
            
            if display_name != str(current_unit):
                updates_needed += 1
                if len(sample_updates) < 10:
                    sample_updates.append({
                        'result_id': result_id,
                        'old': current_unit,
                        'new': display_name
                    })
        elif unit_type == 'string':
            string_units.append(current_unit)
            # Check if it's numeric string (needs mapping)
            try:
                int(current_unit)
                is_numeric_string = True
            except (ValueError, TypeError):
                is_numeric_string = False
            
            if is_numeric_string:
                display_name = mapper.get_result_unit_display(int(current_unit))
                if display_name != current_unit:
                    updates_needed += 1
                    if len(sample_updates) < 10:
                        sample_updates.append({
                            'result_id': result_id,
                            'old': current_unit,
                            'new': display_name
                        })
            else:
                updates_skipped += 1
        else:
            updates_skipped += 1
    
    print(f"\n[ANALYSIS]")
    print(f"  Integer units found: {len(set(integer_units))} unique values")
    print(f"  String units found: {len(set(string_units))} unique values")
    print(f"  PeriodResults needing update: {updates_needed}")
    print(f"  PeriodResults already correct or skipped: {updates_skipped}")
    
    if sample_updates:
        print(f"\n[Sample Updates (first 10)]:")
        for sample in sample_updates:
            print(f"  {sample['result_id']}: '{sample['old']}' -> '{sample['new']}'")
    
    if dry_run:
        print("\n[DRY RUN] No changes made. Remove --dry-run flag to apply updates.")
        return
    
    if updates_needed == 0:
        print("\n[INFO] No updates needed - all units are already display names")
        return
    
    # Get all unique unit values (both integer and numeric strings)
    get_unique_units = """
    MATCH (pr:PeriodResult)
    WHERE pr.unit IS NOT NULL
    WITH pr, 
         CASE WHEN pr.unit IS INTEGER THEN toString(pr.unit)
              ELSE pr.unit END as unit_str
    WHERE unit_str =~ '^[0-9]+$'
    RETURN DISTINCT unit_str as unit_id
    """
    
    unique_units = graph.query(get_unique_units)
    print(f"\n[UPDATING] Found {len(unique_units)} unique numeric unit IDs to map")
    
    # Update each unique unit ID
    updated_total = 0
    for row in unique_units:
        unit_id_str = row.get('unit_id')
        try:
            unit_id_int = int(unit_id_str)
            display_name = mapper.get_result_unit_display(unit_id_int)
            
            if display_name != unit_id_str:
                # Update both integer and string versions
                update_query = """
                MATCH (pr:PeriodResult)
                WHERE (pr.unit = $unit_id_int OR pr.unit = $unit_id_str)
                SET pr.unit = $display_name
                RETURN count(pr) as count
                """
                
                result = graph.query(update_query, {
                    "unit_id_int": unit_id_int,
                    "unit_id_str": unit_id_str,
                    "display_name": display_name
                })
                
                count = result[0]['count'] if result else 0
                updated_total += count
                print(f"  Updated {count} period results: unit '{unit_id_str}' -> '{display_name}'")
        except (ValueError, TypeError):
            continue
    
    print(f"\n[OK] Updated {updated_total} period result nodes")
    print("="*80)


def main():
    """Main function to update existing units"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update existing unit IDs to display names in Neo4j')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be updated without making changes')
    parser.add_argument('--params-only', action='store_true',
                       help='Only update Parameter nodes')
    parser.add_argument('--results-only', action='store_true',
                       help='Only update PeriodResult nodes')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("PEERS Unit Mapping Update Script")
    print("="*80)
    
    # Initialize mapper
    mapper = UnitMapper()
    
    # Get graph connection
    global graph
    graph = get_graph()
    
    try:
        # Update parameters
        if not args.results_only:
            update_parameter_units(mapper, dry_run=args.dry_run)
        
        # Update results
        if not args.params_only:
            update_result_units(mapper, dry_run=args.dry_run)
        
        print("\n" + "="*80)
        print("Unit Update Complete!")
        print("="*80)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to update units: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()




