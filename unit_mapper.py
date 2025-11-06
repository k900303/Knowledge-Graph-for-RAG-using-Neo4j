"""
Unit Mapper Module for PEERS RAG System
Maps numeric unit IDs to display names from CSV mapping files
Provides complete unit data structures for Neo4j ingestion
"""

import csv
import os
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class UnitData:
    """Complete unit data structure"""
    unit_id: str
    value_name: str
    short_name: str
    key: str
    unit_type: str  # 'parameter' or 'result'


class UnitMapper:
    """Maps unit IDs to display names for parameters and results
    Provides complete unit data for Neo4j ingestion"""
    
    def __init__(self, 
                 params_csv_path: str = None, 
                 results_csv_path: str = None):
        """
        Initialize UnitMapper with CSV file paths
        
        Args:
            params_csv_path: Path to infinity_unit_scale_params.csv
            results_csv_path: Path to infinity_unit_scale_results.csv
        """
        # Default paths relative to project root
        if params_csv_path is None:
            params_csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/infinity_unit_scale_params.csv'
        if results_csv_path is None:
            results_csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/infinity_unit_scale_results.csv'
        
        self.params_csv_path = params_csv_path
        self.results_csv_path = results_csv_path
        
        # Mapping dictionaries: {id: short_name} - for backward compatibility
        self.param_unit_map: Dict[str, str] = {}
        self.result_unit_map: Dict[str, str] = {}
        
        # Complete unit data: {id: UnitData}
        self.param_units_data: Dict[str, UnitData] = {}
        self.result_units_data: Dict[str, UnitData] = {}
        
        # Load mappings
        self._load_param_mappings()
        self._load_result_mappings()
    
    def _load_param_mappings(self):
        """Load parameter unit mappings from CSV with complete data"""
        try:
            if not os.path.exists(self.params_csv_path):
                print(f"[WARN] Parameter unit mapping file not found: {self.params_csv_path}")
                return
            
            with open(self.params_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Extract all unit properties
                    unit_id = row.get('id', '').strip()
                    value_name = row.get('Value Name', '').strip()
                    short_name = row.get('Short Name', '').strip()
                    key = row.get('Key', '').strip()
                    
                    if unit_id and short_name:
                        # Store mapping for backward compatibility
                        self.param_unit_map[unit_id] = short_name
                        
                        # Store complete unit data
                        self.param_units_data[unit_id] = UnitData(
                            unit_id=unit_id,
                            value_name=value_name,
                            short_name=short_name,
                            key=key,
                            unit_type='parameter'
                        )
            
            print(f"[OK] Loaded {len(self.param_unit_map)} parameter unit mappings with complete data")
            
        except Exception as e:
            print(f"[ERROR] Failed to load parameter unit mappings: {e}")
    
    def _load_result_mappings(self):
        """Load result unit mappings from CSV with complete data"""
        try:
            if not os.path.exists(self.results_csv_path):
                print(f"[WARN] Result unit mapping file not found: {self.results_csv_path}")
                return
            
            with open(self.results_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Extract all unit properties
                    unit_id = row.get('id', '').strip()
                    value_name = row.get('Value Name', '').strip()
                    short_name = row.get('Short Name', '').strip()
                    key = row.get('Key', '').strip()
                    
                    if unit_id and short_name:
                        # Store mapping for backward compatibility
                        self.result_unit_map[unit_id] = short_name
                        
                        # Store complete unit data
                        self.result_units_data[unit_id] = UnitData(
                            unit_id=unit_id,
                            value_name=value_name,
                            short_name=short_name,
                            key=key,
                            unit_type='result'
                        )
            
            print(f"[OK] Loaded {len(self.result_unit_map)} result unit mappings with complete data")
            
        except Exception as e:
            print(f"[ERROR] Failed to load result unit mappings: {e}")
    
    def get_param_unit_display(self, unit_id: str, default: Optional[str] = None) -> str:
        """
        Get display name for parameter unit ID
        
        Args:
            unit_id: Unit ID (as string, e.g., "1", "2")
            default: Default value if mapping not found (None = return original ID)
        
        Returns:
            Display name (e.g., "Amount", "Percent") or default/original if not found
        """
        if not unit_id:
            return default if default is not None else ""
        
        # Convert to string if not already
        unit_id_str = str(unit_id).strip()
        
        # Look up in mapping
        display_name = self.param_unit_map.get(unit_id_str)
        
        if display_name:
            return display_name
        
        # Return default or original ID
        return default if default is not None else unit_id_str
    
    def get_result_unit_display(self, unit_id: int, default: Optional[str] = None) -> str:
        """
        Get display name for result unit ID
        
        Args:
            unit_id: Unit ID (as integer, e.g., 1, 9, 14)
            default: Default value if mapping not found (None = return original ID as string)
        
        Returns:
            Display name (e.g., "Abs", "K", "M") or default/original if not found
        """
        if unit_id is None:
            return default if default is not None else ""
        
        # Convert to string for lookup
        unit_id_str = str(unit_id).strip()
        
        # Look up in mapping
        display_name = self.result_unit_map.get(unit_id_str)
        
        if display_name:
            return display_name
        
        # Return default or original ID
        return default if default is not None else unit_id_str
    
    def get_param_unit_display_safe(self, unit_id: str) -> str:
        """
        Get display name for parameter unit ID, returning original if not found
        
        Args:
            unit_id: Unit ID (as string)
        
        Returns:
            Display name or original unit_id if mapping not found
        """
        return self.get_param_unit_display(unit_id, default=None)
    
    def get_result_unit_display_safe(self, unit_id: int) -> str:
        """
        Get display name for result unit ID, returning original if not found
        
        Args:
            unit_id: Unit ID (as integer)
        
        Returns:
            Display name or original unit_id as string if mapping not found
        """
        return self.get_result_unit_display(unit_id, default=None)
    
    def get_param_unit_data(self, unit_id: str) -> Optional[UnitData]:
        """
        Get complete unit data for parameter unit ID
        
        Args:
            unit_id: Unit ID (as string)
        
        Returns:
            UnitData object or None if not found
        """
        if not unit_id:
            return None
        unit_id_str = str(unit_id).strip()
        return self.param_units_data.get(unit_id_str)
    
    def get_result_unit_data(self, unit_id: int) -> Optional[UnitData]:
        """
        Get complete unit data for result unit ID
        
        Args:
            unit_id: Unit ID (as integer)
        
        Returns:
            UnitData object or None if not found
        """
        if unit_id is None:
            return None
        unit_id_str = str(unit_id).strip()
        return self.result_units_data.get(unit_id_str)
    
    def get_all_param_units(self) -> List[UnitData]:
        """Get all parameter unit data"""
        return list(self.param_units_data.values())
    
    def get_all_result_units(self) -> List[UnitData]:
        """Get all result unit data"""
        return list(self.result_units_data.values())


# Global instance (lazy loaded)
_global_unit_mapper: Optional[UnitMapper] = None


def get_unit_mapper() -> UnitMapper:
    """Get or create global UnitMapper instance"""
    global _global_unit_mapper
    if _global_unit_mapper is None:
        _global_unit_mapper = UnitMapper()
    return _global_unit_mapper


if __name__ == '__main__':
    # Test the unit mapper
    mapper = UnitMapper()
    
    print("\n" + "="*50)
    print("Unit Mapper Test")
    print("="*50)
    
    # Test parameter mappings
    print("\nParameter Unit Mappings:")
    test_param_ids = ["1", "2", "3", "9", "89"]
    for pid in test_param_ids:
        display = mapper.get_param_unit_display(pid)
        print(f"  ID {pid} -> {display}")
    
    # Test result mappings
    print("\nResult Unit Mappings:")
    test_result_ids = [1, 4, 7, 9, 14]
    for rid in test_result_ids:
        display = mapper.get_result_unit_display(rid)
        print(f"  ID {rid} -> {display}")
    
    # Test missing mappings
    print("\nMissing Mappings (should return original):")
    missing_param = mapper.get_param_unit_display("999")
    missing_result = mapper.get_result_unit_display(999)
    print(f"  Param ID 999 -> {missing_param}")
    print(f"  Result ID 999 -> {missing_result}")

