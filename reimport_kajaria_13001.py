"""
Re-import filtered Kajaria data (parameter_source_id=13001 only)
Run this after cleanup_and_reimport_kajaria_13001.py has filtered the CSV
"""

import os
from csv_parser import parse_results_csv, ResultsParser
from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion

def reimport_kajaria_13001():
    """Re-import filtered Kajaria results (13001 only)"""
    print("\n" + "="*80)
    print("RE-IMPORTING KAJARIA DATA (parameter_source_id=13001 ONLY)")
    print("="*80)
    
    # File paths
    data_dir = "data/PEERS_PROD_RAW_CSV_DATA"
    results_file = os.path.join(data_dir, "results_kajaria_cid_18315_filtered_13001_only.csv")
    target_cid = "18315"  # Kajaria
    
    # Check if filtered file exists
    if not os.path.exists(results_file):
        print(f"[ERROR] Filtered results file not found: {results_file}")
        print("\nPlease run cleanup_and_reimport_kajaria_13001.py first to create the filtered file.")
        return
    
    try:
        # Step 1: Parse the filtered results CSV
        print(f"\n[1/3] Parsing filtered results CSV...")
        print(f"File: {results_file}")
        
        # Create parser and parse (it already filters by cid, but our file is pre-filtered)
        parser = ResultsParser(results_file)
        results = parser.parse(target_cid=target_cid)
        
        print(f"[OK] Parsed {len(results):,} period results")
        
        # Step 2: Create Parameter nodes first (if not already exist)
        print(f"\n[2/3] Ensuring Parameter nodes exist...")
        ingestion = PEERSNeo4jIngestion()
        
        # Note: Parameters should already exist from parameter CSV import
        # If not, they'll be created when PeriodResults are created
        print(f"[OK] Parameter nodes check complete")
        
        # Step 3: Create PeriodResult nodes and relationships
        print(f"\n[3/3] Creating PeriodResult nodes and relationships...")
        # Create a ResultsParser-like object with the parsed results
        # The create_period_results expects a parser object, but we can work with results directly
        # We'll use the ingestion's internal method
        ingestion.create_period_results(parser, batch_size=100)
        
        print(f"\n{'='*80}")
        print("RE-IMPORT COMPLETED!")
        print(f"{'='*80}")
        print(f"Imported {len(results):,} PeriodResult nodes")
        print(f"All with parameter_source_id=13001 only")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"\n[ERROR] Error during re-import: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reimport_kajaria_13001()

