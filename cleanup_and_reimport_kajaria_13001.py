"""
Cleanup and Re-import Script for Kajaria (cid=18315)
- Deletes all existing Kajaria data from Neo4j
- Filters results CSV to only include parameter_source_id = 13001
- Re-imports clean data
"""

import csv
import os
from neo4j_env import graph
from csv_parser import parse_results_csv, ResultsParser
from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion
import csv_parser

def extract_parameter_source_id(id_field: str) -> str:
    """
    Extract parameter_source_id from ID field
    Format: {cid}_{pid}_{parameter_source_id}_{period}
    Example: "18315_38_13001_FY-2040_validation" -> "13001"
    """
    if not id_field or '_' not in id_field:
        return ""
    
    parts = id_field.split('_')
    if len(parts) >= 3:
        return parts[2]  # Third part is parameter_source_id
    return ""

def filter_results_for_13001(input_file: str, output_file: str, target_cid: str = "18315") -> tuple:
    """
    Filter results CSV to only include rows where parameter_source_id = 13001
    Also filters for specific company (cid)
    
    Args:
        input_file: Path to input results CSV
        output_file: Path to output filtered CSV
        target_cid: Company ID to filter for (default: 18315 for Kajaria)
    
    Returns:
        Tuple of (total_rows, filtered_rows_13001, filtered_rows_other_ids)
    """
    print("\n" + "="*80)
    print(f"Filtering results for cid={target_cid} with parameter_source_id=13001 ONLY")
    print("="*80)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    essential_columns = ['id', 'cid', 'pid', 'p', 'ap', 'v', 'ciso', 'u', 'dt', 'yoypc', 'seqpc']
    
    total_rows = 0
    filtered_13001 = 0
    filtered_other_ids = 0
    filtered_other_cid = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        # Read header
        header = next(reader)
        
        # Find column indices
        column_indices = {}
        for col in essential_columns:
            if col in header:
                column_indices[col] = header.index(col)
            else:
                raise ValueError(f"Essential column '{col}' not found in results CSV")
        
        # Write header
        writer.writerow(essential_columns)
        
        id_idx = column_indices['id']
        cid_idx = column_indices['cid']
        
        # Filter rows
        for row in reader:
            total_rows += 1
            
            if len(row) > max(column_indices.values()):
                cid = row[cid_idx].strip()
                id_field = row[id_idx].strip()
                
                # Extract parameter_source_id from ID field
                param_source_id = extract_parameter_source_id(id_field)
                
                # Check company ID first
                if cid != target_cid:
                    filtered_other_cid += 1
                    continue
                
                # Check parameter_source_id - ONLY 13001
                if param_source_id == "13001":
                    filtered_row = [row[column_indices[col]] for col in essential_columns]
                    writer.writerow(filtered_row)
                    filtered_13001 += 1
                else:
                    filtered_other_ids += 1
                    if total_rows <= 100:  # Log first 100 for debugging
                        print(f"  [SKIPPED] Row {total_rows}: ID={id_field}, param_source_id={param_source_id}")
        
        print(f"\n{'='*80}")
        print(f"FILTERING SUMMARY:")
        print(f"{'='*80}")
        print(f"Total rows processed: {total_rows:,}")
        print(f"[OK] Filtered (13001): {filtered_13001:,} rows")
        print(f"[SKIP] Skipped (other param_source_id): {filtered_other_ids:,} rows")
        print(f"[SKIP] Skipped (other cid): {filtered_other_cid:,} rows")
        print(f"\nFilter efficiency: {filtered_13001/total_rows*100:.2f}%")
        print(f"{'='*80}")
    
    return (total_rows, filtered_13001, filtered_other_ids)

def delete_kajaria_data_from_neo4j(cid: str = "18315"):
    """
    Delete all Kajaria-related data from Neo4j:
    - PeriodResult nodes for this company
    - Relationships: HAS_VALUE_IN_PERIOD, HAS_RESULT_IN_PERIOD
    - Parameter nodes that are only used by this company (optional - be careful!)
    
    Args:
        cid: Company ID (default: 18315 for Kajaria)
    """
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
        
        # Step 2: Delete Parameter-PeriodResult relationships (cleanup orphaned relationships)
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
        
        # Optional: Delete Parameter nodes that are now orphaned (only if they have no PeriodResults)
        # BE CAREFUL: This deletes parameters that might be used by other companies!
        # Commenting out for safety - uncomment only if you're sure
        # print("\n[4/4] Deleting orphaned Parameter nodes (optional, be careful!)...")
        # delete_query4 = """
        # MATCH (p:Parameter)
        # WHERE NOT (p)-[:HAS_VALUE_IN_PERIOD]->()
        # DELETE p
        # RETURN count(p) as deleted_count
        # """
        # result4 = graph.query(delete_query4)
        # deleted_params = result4[0]['deleted_count'] if result4 else 0
        # print(f"  ✓ Deleted {deleted_params:,} orphaned Parameter nodes")
        
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

def verify_filtered_data(filtered_file: str) -> dict:
    """
    Verify the filtered data contains only 13001 parameter_source_id
    """
    print("\n" + "="*80)
    print("VERIFYING FILTERED DATA")
    print("="*80)
    
    param_source_ids = {}
    total_rows = 0
    
    with open(filtered_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            id_field = row.get('id', '').strip()
            param_source_id = extract_parameter_source_id(id_field)
            param_source_ids[param_source_id] = param_source_ids.get(param_source_id, 0) + 1
    
    print(f"\nTotal rows in filtered file: {total_rows:,}")
    print(f"\nParameter Source ID Distribution:")
    for pid, count in sorted(param_source_ids.items()):
        marker = "[OK]" if pid == "13001" else "[SKIP]"
        print(f"  {marker} {pid}: {count:,} rows")
    
    # Check if only 13001 exists
    has_only_13001 = len(param_source_ids) == 1 and "13001" in param_source_ids
    if has_only_13001:
        print(f"\n[SUCCESS] VERIFICATION PASSED: Only parameter_source_id=13001 found!")
    else:
        print(f"\n[WARNING] VERIFICATION FAILED: Found other parameter_source_ids!")
        print(f"   Expected: Only '13001'")
        print(f"   Found: {list(param_source_ids.keys())}")
    
    print("="*80)
    
    return {
        "total_rows": total_rows,
        "parameter_source_ids": param_source_ids,
        "is_valid": has_only_13001
    }

def main():
    """Main execution function"""
    print("\n" + "="*80)
    print("KAJARIA DATA CLEANUP AND RE-IMPORT (parameter_source_id=13001 ONLY)")
    print("="*80)
    
    # File paths
    data_dir = "data/PEERS_PROD_RAW_CSV_DATA"
    results_input = os.path.join(data_dir, "results_kajaria_cid_18315.csv")
    results_output = os.path.join(data_dir, "results_kajaria_cid_18315_filtered_13001_only.csv")
    
    target_cid = "18315"  # Kajaria
    
    # Check if input file exists
    if not os.path.exists(results_input):
        print(f"[ERROR] Results file not found: {results_input}")
        return
    
    try:
        # Step 1: Filter CSV to only include parameter_source_id = 13001
        print("\n" + "="*80)
        print("STEP 1: FILTERING RESULTS CSV (13001 ONLY)")
        print("="*80)
        total, filtered_13001, filtered_other = filter_results_for_13001(
            results_input,
            results_output,
            target_cid
        )
        
        if filtered_13001 == 0:
            print("\n[ERROR] No rows found with parameter_source_id=13001!")
            print("   Please check your data file.")
            return
        
        # Step 2: Verify filtered data
        print("\n" + "="*80)
        print("STEP 2: VERIFYING FILTERED DATA")
        print("="*80)
        verification = verify_filtered_data(results_output)
        
        if not verification["is_valid"]:
            print("\n[WARNING] Filtered data contains other parameter_source_ids!")
            response = input("\nContinue anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted by user.")
                return
        
        # Step 3: Delete existing Kajaria data from Neo4j
        print("\n" + "="*80)
        print("STEP 3: DELETING EXISTING KAJARIA DATA FROM NEO4J")
        print("="*80)
        print("\n[WARNING] This will delete ALL existing PeriodResult data for Kajaria!")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted by user.")
            return
        
        cleanup_stats = delete_kajaria_data_from_neo4j(target_cid)
        
        # Step 4: Re-import filtered data
        print("\n" + "="*80)
        print("STEP 4: RE-IMPORTING FILTERED DATA (13001 ONLY)")
        print("="*80)
        print("\nTo re-import the data, run:")
        print(f"  python -c \"from csv_parser import parse_results_csv; from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion; parser = parse_results_csv('{results_output}', target_cid='{target_cid}'); ingestion = PEERSNeo4jIngestion(); ingestion.create_period_results(parser)\"")
        print("\nOr use the pipeline:")
        print(f"  from PEERS_RAG_pipeline import PEERSPipeline")
        print(f"  pipeline = PEERSPipeline(results_file_path='{results_output}')")
        print(f"  pipeline.run_full_pipeline()")
        
        print("\n" + "="*80)
        print("CLEANUP AND FILTERING COMPLETED!")
        print("="*80)
        print(f"\nSummary:")
        print(f"  - Filtered file created: {results_output}")
        print(f"  - Rows with 13001: {filtered_13001:,}")
        print(f"  - Rows excluded (other IDs): {filtered_other:,}")
        print(f"  - Cleaned up from Neo4j: {cleanup_stats['period_results']:,} PeriodResults")
        print(f"\nNext step: Re-import the filtered data using the commands above")
        print("="*80)
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

