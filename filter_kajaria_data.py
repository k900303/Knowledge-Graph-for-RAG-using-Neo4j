"""
Data Filtering Utility for PEERS RAG System
Filters parameter and results CSV files for Kajaria company (cid=18315) only
"""

import csv
import os
from typing import List, Dict

def filter_parameter_csv(input_file: str, output_file: str, target_cid: str = "18315", 
                        allowed_types: List[str] = ["opssd", "sd"]) -> int:
    """
    Filter parameter CSV file for specific company and parameter types
    Only keeps essential columns: param_id, parameter_name, parameter_type, cid, unit, isprimary
    
    Args:
        input_file: Path to input parameter CSV file
        output_file: Path to output filtered CSV file
        target_cid: Company ID to filter for
        allowed_types: List of parameter types to include
    
    Returns:
        Number of filtered rows written
    """
    print(f"\nFiltering parameters for cid={target_cid}, types={allowed_types}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    # Define essential columns to keep
    essential_columns = ['param_id', 'parameter_name', 'parameter_type', 'cid', 'unit', 'isprimary']
    
    filtered_count = 0
    total_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        # Read header and find column indices
        header = next(reader)
        
        # Find indices for essential columns
        column_indices = {}
        for col in essential_columns:
            if col in header:
                column_indices[col] = header.index(col)
            else:
                raise ValueError(f"Essential column '{col}' not found in parameter CSV")
        
        # Write new header with only essential columns
        writer.writerow(essential_columns)
        
        print(f"Essential columns found: {list(column_indices.keys())}")
        print(f"Column indices: {column_indices}")
        
        # Filter rows
        for row in reader:
            total_count += 1
            
            if len(row) > max(column_indices.values()):
                cid = row[column_indices['cid']].strip()
                param_type = row[column_indices['parameter_type']].strip()
                
                # Check if row matches our criteria
                if cid == target_cid and param_type in allowed_types:
                    # Write only essential columns
                    filtered_row = [row[column_indices[col]] for col in essential_columns]
                    writer.writerow(filtered_row)
                    filtered_count += 1
        
        print(f"Total rows processed: {total_count}")
        print(f"Filtered rows written: {filtered_count}")
        print(f"Filter efficiency: {filtered_count/total_count*100:.2f}%")
        print(f"Columns reduced from {len(header)} to {len(essential_columns)}")
    
    return filtered_count

def filter_results_csv(input_file: str, output_file: str, target_cid: str = "18315") -> int:
    """
    Filter results CSV file for specific company
    Only keeps essential columns: id, cid, pid, period, actual_period, value, currency, unit, data_type, yoy_growth, seq_growth
    
    Args:
        input_file: Path to input results CSV file
        output_file: Path to output filtered CSV file
        target_cid: Company ID to filter for
    
    Returns:
        Number of filtered rows written
    """
    print(f"\nFiltering results for cid={target_cid}")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    # Define essential columns to keep (mapped to actual CSV column names)
    essential_columns = ['id', 'cid', 'pid', 'p', 'ap', 'v', 'ciso', 'u', 'dt', 'yoypc', 'seqpc']
    
    filtered_count = 0
    total_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        # Read header and find column indices
        header = next(reader)
        
        # Find indices for essential columns
        column_indices = {}
        for col in essential_columns:
            if col in header:
                column_indices[col] = header.index(col)
            else:
                raise ValueError(f"Essential column '{col}' not found in results CSV")
        
        # Write new header with only essential columns
        writer.writerow(essential_columns)
        
        print(f"Essential columns found: {list(column_indices.keys())}")
        print(f"Column indices: {column_indices}")
        
        # Filter rows
        for row in reader:
            total_count += 1
            
            if len(row) > max(column_indices.values()):
                cid = row[column_indices['cid']].strip()
                
                # Check if row matches our criteria
                if cid == target_cid:
                    # Write only essential columns
                    filtered_row = [row[column_indices[col]] for col in essential_columns]
                    writer.writerow(filtered_row)
                    filtered_count += 1
        
        print(f"Total rows processed: {total_count}")
        print(f"Filtered rows written: {filtered_count}")
        print(f"Filter efficiency: {filtered_count/total_count*100:.2f}%")
        print(f"Columns reduced from {len(header)} to {len(essential_columns)}")
    
    return filtered_count

def main():
    """Main function to filter Kajaria data"""
    print("="*80)
    print("PEERS Data Filtering Utility - Kajaria Company (cid=18315)")
    print("="*80)
    
    # File paths
    data_dir = "data/PEERS_PROD_RAW_CSV_DATA"
    param_input = os.path.join(data_dir, "parameter_library_sync.csv")
    results_input = os.path.join(data_dir, "results_big_dont_use.csv")
    
    param_output = os.path.join(data_dir, "parameters_kajaria_cid_18315.csv")
    results_output = os.path.join(data_dir, "results_kajaria_cid_18315.csv")
    
    # Check if input files exist
    if not os.path.exists(param_input):
        print(f"ERROR: Parameter file not found: {param_input}")
        return
    
    if not os.path.exists(results_input):
        print(f"ERROR: Results file not found: {results_input}")
        return
    
    try:
        # Filter parameter file
        param_count = filter_parameter_csv(
            param_input, 
            param_output, 
            target_cid="18315",
            allowed_types=["opssd", "sd"]
        )
        
        # Filter results file
        results_count = filter_results_csv(
            results_input,
            results_output,
            target_cid="18315"
        )
        
        print("\n" + "="*80)
        print("FILTERING COMPLETED SUCCESSFULLY!")
        print("="*80)
        print(f"Parameters filtered: {param_count} rows")
        print(f"Results filtered: {results_count} rows")
        print(f"\nOutput files created:")
        print(f"  - {param_output}")
        print(f"  - {results_output}")
        print("="*80)
        
    except Exception as e:
        print(f"ERROR during filtering: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
