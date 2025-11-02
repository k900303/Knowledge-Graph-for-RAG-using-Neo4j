"""
Period Search and Normalization Tools for PEERS RAG System
Handles period format normalization and period search/validation
"""

from typing import List, Dict, Optional, Any
from PEERS_RAG_tools import BaseToolHandler
from neo4j_env import graph
import re


class PeriodNormalizationTool(BaseToolHandler):
    """Tool for normalizing period strings to database format"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "normalize_period",
                "description": "Normalize period strings to database format. Converts various formats like 'Q1FY2025', 'FY2025Q1', '1QFY2025' to standard format '1QFY-2025'. Also handles 'latest', 'most recent', etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period_string": {
                            "type": "string",
                            "description": "Period string in any format (e.g., 'Q1FY2025', 'FY2025Q1', 'quarter 1 of 2025', 'latest', 'most recent')"
                        }
                    },
                    "required": ["period_string"]
                }
            }
        }
    
    def execute(self, period_string: str) -> Dict[str, Any]:
        """Normalize period string to database format"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: normalize_period called with period_string="{period_string}"')
            
            normalized = self._normalize_period(period_string)
            
            result = {
                "original": period_string,
                "normalized": normalized,
                "format": self._detect_format(period_string)
            }
            
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="normalize_period",
                    arguments={"period_string": period_string},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in normalize_period tool: {str(e)}', e)
            return {
                "original": period_string,
                "normalized": period_string,  # Return original if normalization fails
                "error": str(e)
            }
    
    def _normalize_period(self, period_str: str) -> str:
        """Normalize period string to database format"""
        period_str = period_str.strip()
        
        # Handle special keywords
        if period_str.lower() in ['latest', 'most recent', 'recent', 'current']:
            return 'latest'
        
        # Pattern 1: Q1FY2025, Q2FY2025, etc.
        match = re.match(r'Q([1-4])FY-?(\d{4})', period_str, re.IGNORECASE)
        if match:
            quarter, year = match.groups()
            return f"{quarter}QFY-{year}"
        
        # Pattern 2: FY2025Q1, FY-2025Q1, etc.
        match = re.match(r'FY-?(\d{4})Q([1-4])', period_str, re.IGNORECASE)
        if match:
            year, quarter = match.groups()
            return f"{quarter}QFY-{year}"
        
        # Pattern 3: 1QFY2025, 2QFY2025, etc.
        match = re.match(r'(\d)QFY-?(\d{4})', period_str, re.IGNORECASE)
        if match:
            quarter, year = match.groups()
            return f"{quarter}QFY-{year}"
        
        # Pattern 4: FY2025, FY-2025 (full year)
        match = re.match(r'FY-?(\d{4})', period_str, re.IGNORECASE)
        if match:
            year = match.groups()[0]
            return f"FY-{year}"
        
        # Pattern 5: "quarter 1 of 2025", "Q1 2025", "2025 Q1"
        match = re.search(r'(?:quarter|q)\s*([1-4])', period_str, re.IGNORECASE)
        if match:
            quarter = match.group(1)
            year_match = re.search(r'(\d{4})', period_str)
            if year_match:
                year = year_match.group(1)
                return f"{quarter}QFY-{year}"
        
        # Pattern 6: Half year - 1HFY2025, 2HFY2025
        match = re.match(r'([12])HFY-?(\d{4})', period_str, re.IGNORECASE)
        if match:
            half, year = match.groups()
            return f"{half}HFY-{year}"
        
        # If already in correct format (1QFY-2025), return as-is
        if re.match(r'\dQFY-\d{4}', period_str):
            return period_str
        
        # If no pattern matched, return original (might be valid already)
        return period_str
    
    def _detect_format(self, period_str: str) -> str:
        """Detect the format of the period string"""
        period_lower = period_str.lower()
        
        if period_lower in ['latest', 'most recent', 'recent', 'current']:
            return 'keyword'
        elif re.match(r'Q\dFY', period_str, re.IGNORECASE):
            return 'quarter_first'
        elif re.match(r'FY.*Q', period_str, re.IGNORECASE):
            return 'year_first'
        elif re.match(r'FY-?\d{4}', period_str, re.IGNORECASE):
            return 'full_year'
        elif 'quarter' in period_lower or re.match(r'Q\d', period_str, re.IGNORECASE):
            return 'natural_language'
        else:
            return 'unknown'


class PeriodSearchTool(BaseToolHandler):
    """Tool for searching and validating periods in database"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_periods",
                "description": "Search for available periods in database for a specific company or globally. Use this to validate if a period exists or find available periods.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_id": {
                            "type": "string",
                            "description": "Optional: Company ID (cid) to filter periods for specific company",
                            "default": None
                        },
                        "period_pattern": {
                            "type": "string",
                            "description": "Optional: Period pattern to match (e.g., '1QFY-2025', 'FY-2025')",
                            "default": None
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of periods to return",
                            "default": 20
                        }
                    }
                }
            }
        }
    
    def execute(self, company_id: Optional[str] = None, period_pattern: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """Search for available periods"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_periods called with company_id={company_id}, period_pattern={period_pattern}, limit={limit}')
            
            # Build query
            if company_id:
                if period_pattern:
                    query = f"""
                    MATCH (c:Company {{cid: '{company_id}'}})-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                    WHERE pr.period CONTAINS '{period_pattern.replace("'", "\\'")}'
                    RETURN DISTINCT pr.period
                    ORDER BY pr.period DESC
                    LIMIT {limit}
                    """
                else:
                    query = f"""
                    MATCH (c:Company {{cid: '{company_id}'}})-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                    RETURN DISTINCT pr.period
                    ORDER BY pr.period DESC
                    LIMIT {limit}
                    """
            else:
                if period_pattern:
                    query = f"""
                    MATCH (pr:PeriodResult)
                    WHERE pr.period CONTAINS '{period_pattern.replace("'", "\\'")}'
                    RETURN DISTINCT pr.period
                    ORDER BY pr.period DESC
                    LIMIT {limit}
                    """
                else:
                    query = f"""
                    MATCH (pr:PeriodResult)
                    RETURN DISTINCT pr.period
                    ORDER BY pr.period DESC
                    LIMIT {limit}
                    """
            
            results = graph.query(query)
            periods = [row['pr.period'] for row in results]
            
            result = {
                "periods": periods,
                "total_found": len(periods),
                "company_id": company_id,
                "period_pattern": period_pattern
            }
            
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_periods",
                    arguments={"company_id": company_id, "period_pattern": period_pattern, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_periods tool: {str(e)}', e)
            return {
                "periods": [],
                "error": str(e),
                "total_found": 0
            }

