"""
Company Verification Tools for PEERS GraphRAG
Provides tools to verify company names and extract exact company details from Neo4j
"""

from typing import List, Dict, Optional, Any
from neo4j_env import graph, get_graph
import json


class CompanyVerificationTool:
    """
    Tool for verifying and getting exact company names from Neo4j database
    """
    
    def __init__(self, log_manager=None):
        self.log_manager = log_manager
    
    def verify_company_name(self, search_term: str, limit: int = 5) -> Dict[str, Any]:
        """
        Verify company name by searching Neo4j for exact matches
        
        Args:
            search_term: Partial or full company name to search for (e.g., "kajaria", "Kajaria Ceramics")
            limit: Maximum number of results to return
            
        Returns:
            Dictionary containing:
            - verified: bool - Whether exact match was found
            - exact_name: str - Exact company name from database (if found)
            - matches: list - All matching company names
            - search_term: str - Original search term
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Verifying company name for search term: "{search_term}"')
            
            # Ensure graph connection is available
            global graph
            if graph is None:
                graph = get_graph()
                if graph is None:
                    error_msg = 'Neo4j not connected, cannot verify company name'
                    if self.log_manager:
                        self.log_manager.add_error_log(error_msg)
                    return {
                        "verified": False,
                        "exact_name": None,
                        "matches": [],
                        "search_term": search_term,
                        "error": error_msg
                    }
            
            # Escape single quotes in search_term to prevent Cypher injection
            escaped_term = search_term.replace("'", "\\'")
            
            # Use case-insensitive matching - CONTAINS is case-sensitive, so use toLower()
            # Try multiple matching strategies for better results
            query = f"""
            MATCH (c:Company)
            WHERE toLower(c.company_name) CONTAINS toLower('{escaped_term}')
               OR toLower(c.company_name) STARTS WITH toLower('{escaped_term}')
               OR toLower(c.company_name) ENDS WITH toLower('{escaped_term}')
            RETURN c.company_name, c.cid
            ORDER BY 
                CASE 
                    WHEN toLower(c.company_name) = toLower('{escaped_term}') THEN 0
                    WHEN toLower(c.company_name) STARTS WITH toLower('{escaped_term}') THEN 1
                    WHEN toLower(c.company_name) CONTAINS toLower('{escaped_term}') THEN 2
                    ELSE 3 
                END,
                c.company_name
            LIMIT {limit}
            """
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Executing query: {query[:200]}...')
            
            results = graph.query(query)
            
            matches = []
            exact_name = None
            
            if results and len(results) > 0:
                for row in results:
                    # Handle different result formats (dict vs object)
                    if isinstance(row, dict):
                        company_name = row.get('c.company_name', None)
                        cid = row.get('c.cid', None)
                    else:
                        # Handle object-style access
                        company_name = getattr(row, 'c.company_name', None) if hasattr(row, 'c.company_name') else None
                        cid = getattr(row, 'c.cid', None) if hasattr(row, 'c.cid') else None
                    
                    if company_name:
                        matches.append({
                            "company_name": company_name,
                            "cid": str(cid) if cid else None
                        })
                
                if matches:
                    # First match is usually the best match (ordered by relevance)
                    exact_name = matches[0]["company_name"]
                    
                    # Check if we have an exact match (case-insensitive, word-for-word)
                    # This means the entire company name matches the search term, not just contains it
                    verified = any(
                        match["company_name"].lower().strip() == search_term.lower().strip() 
                        for match in matches
                    )
                    
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Found {len(matches)} match(es), best match: "{exact_name}"')
                else:
                    verified = False
                    if self.log_manager:
                        self.log_manager.add_info_log('Query returned results but no valid company names found')
            else:
                verified = False
                if self.log_manager:
                    self.log_manager.add_info_log(f'No results found for search term: "{search_term}"')
            
            result = {
                "verified": verified,
                "exact_name": exact_name,
                "matches": matches,
                "search_term": search_term,
                "total_found": len(matches)
            }
            
            if self.log_manager:
                if exact_name:
                    self.log_manager.add_info_log(f'Found exact company name: "{exact_name}" (verified: {verified})')
                else:
                    self.log_manager.add_info_log(f'No company found matching "{search_term}"')
            
            return result
            
        except Exception as e:
            error_msg = f'Error verifying company name: {str(e)}'
            if self.log_manager:
                self.log_manager.add_error_log(error_msg, e)
            return {
                "verified": False,
                "exact_name": None,
                "matches": [],
                "search_term": search_term,
                "error": error_msg
            }
    
    def get_company_details(self, company_name: str, include_relationships: bool = True) -> Dict[str, Any]:
        """
        Get complete company details from Neo4j
        
        Args:
            company_name: Exact company name (should be verified first using verify_company_name)
            include_relationships: Whether to include country, sector, industry relationships
            
        Returns:
            Dictionary containing company details
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Getting company details for: "{company_name}"')
            
            # Ensure graph connection is available
            global graph
            if graph is None:
                graph = get_graph()
                if graph is None:
                    error_msg = 'Neo4j not connected, cannot get company details'
                    if self.log_manager:
                        self.log_manager.add_error_log(error_msg)
                    return {
                        "found": False,
                        "company_name": company_name,
                        "error": error_msg
                    }
            
            if include_relationships:
                query = f"""
                MATCH (c:Company)-[:IN_COUNTRY]->(country:Country),
                      (c)-[:IN_SECTOR]->(s:Sector),
                      (c)-[:IN_INDUSTRY]->(i:Industry)
                WHERE c.company_name = '{company_name}' OR c.company_name CONTAINS '{company_name}'
                RETURN c.company_name, c.cid, c.market_cap, c.base_currency, 
                       c.one_week_change, c.this_month_change, c.this_quarter_change,
                       c.isin, c.va_ticker, c.status, c.description,
                       country.name as country, country.code as country_code,
                       s.name as sector, s.sector_id as sector_id,
                       i.name as industry, i.industry_id as industry_id
                LIMIT 1
                """
            else:
                query = f"""
                MATCH (c:Company)
                WHERE c.company_name = '{company_name}' OR c.company_name CONTAINS '{company_name}'
                RETURN c.company_name, c.cid, c.market_cap, c.base_currency,
                       c.one_week_change, c.this_month_change, c.this_quarter_change,
                       c.isin, c.va_ticker, c.status, c.description
                LIMIT 1
                """
            
            results = graph.query(query)
            
            if results and len(results) > 0:
                company_data = results[0]
                result = {
                    "found": True,
                    "company_name": company_data.get('c.company_name'),
                    "cid": company_data.get('c.cid'),
                    "market_cap": company_data.get('c.market_cap'),
                    "base_currency": company_data.get('c.base_currency'),
                    "one_week_change": company_data.get('c.one_week_change'),
                    "this_month_change": company_data.get('c.this_month_change'),
                    "this_quarter_change": company_data.get('c.this_quarter_change'),
                    "isin": company_data.get('c.isin'),
                    "va_ticker": company_data.get('c.va_ticker'),
                    "status": company_data.get('c.status'),
                    "description": company_data.get('c.description')
                }
                
                if include_relationships:
                    result.update({
                        "country": company_data.get('country'),
                        "country_code": company_data.get('country_code'),
                        "sector": company_data.get('sector'),
                        "sector_id": company_data.get('sector_id'),
                        "industry": company_data.get('industry'),
                        "industry_id": company_data.get('industry_id')
                    })
                
                if self.log_manager:
                    self.log_manager.add_info_log(f'Company details retrieved for: "{company_data.get("c.company_name")}"')
                
                return result
            else:
                if self.log_manager:
                    self.log_manager.add_info_log(f'Company not found: "{company_name}"')
                return {
                    "found": False,
                    "company_name": company_name,
                    "message": "Company not found in database"
                }
                
        except Exception as e:
            error_msg = f'Error getting company details: {str(e)}'
            if self.log_manager:
                self.log_manager.add_error_log(error_msg, e)
            return {
                "found": False,
                "company_name": company_name,
                "error": error_msg
            }
    
    def verify_and_get_company(self, search_term: str, include_details: bool = False) -> Dict[str, Any]:
        """
        Combined method: Verify company name and optionally get details
        
        Args:
            search_term: Partial or full company name to search for
            include_details: Whether to also fetch full company details
            
        Returns:
            Combined result with verification and optionally details
        """
        # First verify the company name
        verification_result = self.verify_company_name(search_term)
        
        result = {
            "verification": verification_result,
            "details": None
        }
        
        # If verified and details requested, get company details
        if verification_result.get("exact_name") and include_details:
            exact_name = verification_result["exact_name"]
            details_result = self.get_company_details(exact_name, include_relationships=True)
            result["details"] = details_result
        
        return result


class CompanyNameExtractor:
    """
    Utility class to extract company names from user queries
    """
    
    @staticmethod
    def extract_from_query(question: str) -> Optional[str]:
        """
        Extract company name from user query using pattern matching
        
        Args:
            question: User's natural language query
            
        Returns:
            Extracted company name or None
        """
        import re
        question_lower = question.lower()
        
        # Pattern: "details of [company]", "company details of [company]", etc.
        patterns = [
            r'(?:details?|information|info|about)\s+(?:of|for|about)\s+([a-zA-Z][\w\s]+?)(?:\s+company|\s+details|\s+information|$)',
            r'company\s+details?\s+(?:of|for|about)\s+([a-zA-Z][\w\s]+?)(?:\s+company|$)',
            r'([a-zA-Z][\w\s]+?)\s+company\s+details?',
            r'([a-zA-Z][\w\s]+?)(?:\s+details|\s+information|\s+info)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question_lower, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                # Remove common stop words
                company_name = re.sub(r'\s+(company|details|information|info|the|of|for|about)$', '', company_name, flags=re.IGNORECASE)
                if len(company_name) > 2:
                    return company_name
        
        # If not found, try simple word extraction (look for capitalized words)
        words = question.split()
        is_details_query = any(word in question_lower for word in ['details', 'detail', 'information', 'info', 'about'])
        
        for i, word in enumerate(words):
            if word.isalpha() and len(word) > 3 and word[0].isupper():
                # Check if this looks like a company name
                if i < len(words) - 1:
                    next_word = words[i + 1]
                    if next_word.lower() in ['company', 'details', 'information', 'info', 'of', 'for']:
                        return word
                # Or if it's at the end and the question contains details/info
                elif is_details_query:
                    return word
        
        return None


class CompanyQueryBuilder:
    """
    Utility class to build Cypher queries with verified company names
    """
    
    @staticmethod
    def build_company_details_query(company_name: str, use_exact_match: bool = True) -> str:
        """
        Build Cypher query for company details
        
        Args:
            company_name: Exact company name (should be verified)
            use_exact_match: Whether to use exact match (=) or contains (CONTAINS)
            
        Returns:
            Cypher query string
        """
        if use_exact_match:
            where_clause = f"c.company_name = '{company_name}'"
        else:
            where_clause = f"c.company_name CONTAINS '{company_name}'"
        
        query = f"""MATCH (c:Company)-[:IN_COUNTRY]->(country:Country),
                      (c)-[:IN_SECTOR]->(s:Sector),
                      (c)-[:IN_INDUSTRY]->(i:Industry)
                    WHERE {where_clause}
                    RETURN c.company_name, c.cid, country.name as country, country.code as country_code,
                           s.name as sector, i.name as industry, c.market_cap, c.description
                    LIMIT 10"""
        return query
    
    @staticmethod
    def build_parameter_query(company_name: str, parameter_names: List[str] = None, period: str = None, use_exact_match: bool = True) -> str:
        """
        Build Cypher query for company parameters
        
        Args:
            company_name: Exact company name (should be verified)
            parameter_names: Optional list of parameter names to filter
            period: Optional period to filter (e.g., 'FY-2024', 'latest')
            use_exact_match: Whether to use exact match (=) or contains (CONTAINS)
            
        Returns:
            Cypher query string
        """
        if use_exact_match:
            where_clause = f"c.company_name = '{company_name}'"
        else:
            where_clause = f"c.company_name CONTAINS '{company_name}'"
        
        if parameter_names:
            param_conditions = " OR ".join([f"p.parameter_name CONTAINS '{param}'" for param in parameter_names])
            where_clause += f" AND ({param_conditions})"
        
        if period and period != 'latest':
            where_clause += f" AND pr.period CONTAINS '{period}'"
        
        query = f"""MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                    WHERE {where_clause}
                    RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth"""
        
        if period == 'latest':
            query += " ORDER BY pr.period DESC LIMIT 20"
        else:
            query += " ORDER BY pr.period DESC LIMIT 20"
        
        return query

