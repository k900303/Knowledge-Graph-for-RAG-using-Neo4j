"""
Tool Infrastructure for PEERS GraphRAG
Provides reusable tools for both Tool Calling and future ReAct implementations
"""

from typing import List, Dict, Optional, Any
from abc import ABC, abstractmethod
from neo4j_env import graph
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
import json


class BaseToolHandler(ABC):
    """Abstract base class for all tool handlers"""
    
    def __init__(self, log_manager=None):
        self.log_manager = log_manager
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    @abstractmethod
    def get_tool_definition(self) -> Dict:
        """Return tool definition in OpenAI function calling format"""
        pass


class ParameterSearchTool(BaseToolHandler):
    """Tool for semantic search of parameters in database"""
    
    def __init__(self, log_manager=None, embedding_cache=None):
        super().__init__(log_manager)
        self.embedding_model = OpenAIEmbeddings()
        self.embedding_cache = embedding_cache or {}
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_parameters",
                "description": "Search for parameter names in the database using semantic similarity. Use this when user mentions metrics like 'revenue', 'margin', 'profit', 'ebitda', etc. Returns exact parameter names from database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "The term to search for (e.g., 'revenue', 'margin', 'profit', 'ebitda')"
                        },
                        "company_id": {
                            "type": "string",
                            "description": "Optional: Filter parameters for a specific company by company ID",
                            "default": None
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 5
                        }
                    },
                    "required": ["search_term"]
                }
            }
        }
    
    def execute(self, search_term: str, company_id: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Execute parameter search with semantic similarity"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_parameters called with term="{search_term}", company_id={company_id}, limit={limit}')
            
            # Query all parameters from database (no limit for comprehensive search)
            if company_id:
                query = f"""
                MATCH (c:Company {{cid: '{company_id}'}})-[:HAS_PARAMETER]->(p:Parameter)
                RETURN DISTINCT p.parameter_name
                LIMIT 200
                """
            else:
                query = "MATCH (p:Parameter) RETURN DISTINCT p.parameter_name LIMIT 200"
            
            params_result = graph.query(query)
            all_params = [row['p.parameter_name'] for row in params_result]
            
            if not all_params:
                return {
                    "matches": [],
                    "message": "No parameters found in database"
                }
            
            # Semantic search using embeddings
            matches = self._semantic_search(search_term, all_params, limit)
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Found {len(matches)} parameter matches for "{search_term}"')
            
            result = {
                "matches": matches,
                "search_term": search_term,
                "total_found": len(matches)
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_parameters",
                    arguments={"search_term": search_term, "company_id": company_id, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_parameters tool: {str(e)}', e)
            return {
                "matches": [],
                "error": str(e),
                "message": "Error searching parameters"
            }
    
    def _semantic_search(self, search_term: str, all_params: List[str], limit: int = 5) -> List[Dict]:
        """Perform semantic similarity search"""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
        except ImportError:
            # Fallback to basic string matching if sklearn not available
            return self._fallback_string_search(search_term, all_params, limit)
        
        try:
            # Embed search term
            search_embedding = self.embedding_model.embed_query(search_term)
            
            # Get or create embeddings for parameters
            param_embeddings = []
            for param in all_params:
                cache_key = f"param_{param}"
                if cache_key in self.embedding_cache:
                    param_embeddings.append(self.embedding_cache[cache_key])
                else:
                    param_embedding = self.embedding_model.embed_query(f"parameter: {param}")
                    self.embedding_cache[cache_key] = param_embedding
                    param_embeddings.append(param_embedding)
            
            # Calculate similarities
            similarities = cosine_similarity(
                [search_embedding],
                param_embeddings
            )[0]
            
            # Get top matches above threshold
            threshold = 0.6
            top_indices = similarities.argsort()[-limit:][::-1]
            
            matches = []
            for idx in top_indices:
                if similarities[idx] >= threshold:
                    matches.append({
                        "parameter_name": all_params[idx],
                        "similarity": float(similarities[idx]),
                        "match_method": "semantic"
                    })
            
            return matches
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_info_log(f'Semantic search failed, using fallback: {str(e)}')
            return self._fallback_string_search(search_term, all_params, limit)
    
    def _fallback_string_search(self, search_term: str, all_params: List[str], limit: int) -> List[Dict]:
        """Fallback to substring matching if embeddings fail"""
        search_lower = search_term.lower()
        matches = []
        
        for param in all_params:
            param_lower = param.lower()
            if search_lower in param_lower or param_lower in search_lower:
                # Calculate simple similarity
                similarity = len(search_term) / max(len(search_term), len(param.split()[0]))
                matches.append({
                    "parameter_name": param,
                    "similarity": similarity,
                    "match_method": "substring"
                })
        
        # Sort by similarity and return top matches
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        return matches[:limit]


class CompanySearchTool(BaseToolHandler):
    """Tool for fuzzy company name search"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_company",
                "description": "Search for company names in the database with fuzzy matching. Handles typos, partial names, and variations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {
                            "type": "string",
                            "description": "Company name or partial name to search for"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 5
                        }
                    },
                    "required": ["company_name"]
                }
            }
        }
    
    def execute(self, company_name: str, limit: int = 5) -> Dict[str, Any]:
        """Execute company search with fuzzy matching"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_company called with name="{company_name}", limit={limit}')
            
            # Escape single quotes to prevent Cypher injection
            escaped_name = company_name.replace("'", "\\'")
            
            # Use case-insensitive matching - CONTAINS is case-sensitive, so use toLower()
            query = f"""
            MATCH (c:Company)
            WHERE toLower(c.company_name) CONTAINS toLower('{escaped_name}')
               OR toLower(c.company_name) STARTS WITH toLower('{escaped_name}')
               OR toLower(c.company_name) ENDS WITH toLower('{escaped_name}')
            RETURN c.company_name, c.cid
            ORDER BY 
                CASE 
                    WHEN toLower(c.company_name) = toLower('{escaped_name}') THEN 0
                    WHEN toLower(c.company_name) STARTS WITH toLower('{escaped_name}') THEN 1
                    WHEN toLower(c.company_name) CONTAINS toLower('{escaped_name}') THEN 2
                    ELSE 3 
                END,
                c.company_name
            LIMIT {limit}
            """
            
            results = graph.query(query)
            
            companies = [
                {
                    "company_name": row['c.company_name'],
                    "cid": row['c.cid']
                }
                for row in results
            ]
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Found {len(companies)} company matches for "{company_name}"')
            
            result = {
                "companies": companies,
                "search_term": company_name,
                "total_found": len(companies)
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_company",
                    arguments={"company_name": company_name, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_company tool: {str(e)}', e)
            return {
                "companies": [],
                "error": str(e),
                "message": "Error searching companies"
            }


class SectorSearchTool(BaseToolHandler):
    """Tool for searching sectors in the database"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_sectors",
                "description": "Search for sectors in the database by name. Use this when user mentions a sector like 'Technology', 'Financials', 'Healthcare', etc. Returns exact sector names from database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Sector name or partial name to search for (e.g., 'Technology', 'Financials', 'Healthcare')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 20
                        }
                    },
                    "required": ["search_term"]
                }
            }
        }
    
    def execute(self, search_term: str, limit: int = 20) -> Dict[str, Any]:
        """Execute sector search with fuzzy matching"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_sectors called with term="{search_term}", limit={limit}')
            
            # Escape single quotes to prevent Cypher injection
            escaped_term = search_term.replace("'", "\\'")
            
            # Use case-insensitive matching
            query = f"""
            MATCH (s:Sector)
            WHERE toLower(s.name) CONTAINS toLower('{escaped_term}')
               OR toLower(s.name) STARTS WITH toLower('{escaped_term}')
            RETURN DISTINCT s.name, s.sector_id
            ORDER BY 
                CASE 
                    WHEN toLower(s.name) = toLower('{escaped_term}') THEN 0
                    WHEN toLower(s.name) STARTS WITH toLower('{escaped_term}') THEN 1
                    ELSE 2 
                END,
                s.name
            LIMIT {limit}
            """
            
            results = graph.query(query)
            
            sectors = [
                {
                    "name": row['s.name'],
                    "sector_id": str(row['s.sector_id']) if row.get('s.sector_id') else None
                }
                for row in results
            ]
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Found {len(sectors)} sector matches for "{search_term}"')
            
            result = {
                "sectors": sectors,
                "search_term": search_term,
                "total_found": len(sectors)
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_sectors",
                    arguments={"search_term": search_term, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_sectors tool: {str(e)}', e)
            return {
                "sectors": [],
                "error": str(e),
                "message": "Error searching sectors",
                "search_term": search_term
            }


class IndustrySearchTool(BaseToolHandler):
    """Tool for searching industries in the database"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_industries",
                "description": "Search for industries in the database by name. Use this when user mentions an industry like 'Software', 'Banks', 'Pharmaceuticals', etc. Returns exact industry names from database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Industry name or partial name to search for (e.g., 'Software', 'Banks', 'Pharmaceuticals')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 30
                        }
                    },
                    "required": ["search_term"]
                }
            }
        }
    
    def execute(self, search_term: str, limit: int = 30) -> Dict[str, Any]:
        """Execute industry search with fuzzy matching"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_industries called with term="{search_term}", limit={limit}')
            
            # Escape single quotes to prevent Cypher injection
            escaped_term = search_term.replace("'", "\\'")
            
            # Use case-insensitive matching
            query = f"""
            MATCH (i:Industry)
            WHERE toLower(i.name) CONTAINS toLower('{escaped_term}')
               OR toLower(i.name) STARTS WITH toLower('{escaped_term}')
            RETURN DISTINCT i.name, i.industry_id
            ORDER BY 
                CASE 
                    WHEN toLower(i.name) = toLower('{escaped_term}') THEN 0
                    WHEN toLower(i.name) STARTS WITH toLower('{escaped_term}') THEN 1
                    ELSE 2 
                END,
                i.name
            LIMIT {limit}
            """
            
            results = graph.query(query)
            
            industries = [
                {
                    "name": row['i.name'],
                    "industry_id": str(row['i.industry_id']) if row.get('i.industry_id') else None
                }
                for row in results
            ]
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Found {len(industries)} industry matches for "{search_term}"')
            
            result = {
                "industries": industries,
                "search_term": search_term,
                "total_found": len(industries)
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_industries",
                    arguments={"search_term": search_term, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_industries tool: {str(e)}', e)
            return {
                "industries": [],
                "error": str(e),
                "message": "Error searching industries",
                "search_term": search_term
            }


class GeographySearchTool(BaseToolHandler):
    """Tool for searching countries and regions in the database"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "search_geography",
                "description": "Search for countries or regions in the database. Supports country names, country codes, and region names. Use this when user mentions geography like 'India', 'US', 'Asia', etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "Country name, country code, or region name to search for (e.g., 'India', 'US', 'IN', 'Asia')"
                        },
                        "search_type": {
                            "type": "string",
                            "description": "Type of search: 'country', 'region', or 'both' (default: 'both')",
                            "enum": ["country", "region", "both"],
                            "default": "both"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 20
                        }
                    },
                    "required": ["search_term"]
                }
            }
        }
    
    def execute(self, search_term: str, search_type: str = "both", limit: int = 20) -> Dict[str, Any]:
        """Execute geography search (countries and/or regions)"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: search_geography called with term="{search_term}", type={search_type}, limit={limit}')
            
            # Escape single quotes
            escaped_term = search_term.replace("'", "\\'")
            
            results_list = []
            
            # Search countries if requested
            if search_type in ["country", "both"]:
                country_query = f"""
                MATCH (c:Country)
                WHERE toLower(c.name) CONTAINS toLower('{escaped_term}')
                   OR toLower(c.name) STARTS WITH toLower('{escaped_term}')
                   OR toLower(c.code) = toUpper('{escaped_term}')
                   OR toLower(c.code) CONTAINS toLower('{escaped_term}')
                RETURN DISTINCT c.name, c.code
                ORDER BY 
                    CASE 
                        WHEN toLower(c.code) = toUpper('{escaped_term}') THEN 0
                        WHEN toLower(c.name) = toLower('{escaped_term}') THEN 1
                        WHEN toLower(c.name) STARTS WITH toLower('{escaped_term}') THEN 2
                        WHEN toLower(c.code) CONTAINS toLower('{escaped_term}') THEN 3
                        ELSE 4 
                    END,
                    c.name
                LIMIT {limit}
                """
                
                country_results = graph.query(country_query)
                for row in country_results:
                    results_list.append({
                        "name": row['c.name'],
                        "code": row['c.code'],
                        "type": "country"
                    })
            
            # Search regions if requested
            if search_type in ["region", "both"]:
                region_query = f"""
                MATCH (r:Region)
                WHERE toLower(r.name) CONTAINS toLower('{escaped_term}')
                   OR toLower(r.name) STARTS WITH toLower('{escaped_term}')
                RETURN DISTINCT r.name
                ORDER BY 
                    CASE 
                        WHEN toLower(r.name) = toLower('{escaped_term}') THEN 0
                        WHEN toLower(r.name) STARTS WITH toLower('{escaped_term}') THEN 1
                        ELSE 2 
                    END,
                    r.name
                LIMIT {limit}
                """
                
                region_results = graph.query(region_query)
                for row in region_results:
                    results_list.append({
                        "name": row['r.name'],
                        "code": None,
                        "type": "region"
                    })
            
            # Sort combined results by relevance (countries first if exact code match, then by name)
            results_list.sort(key=lambda x: (
                0 if x.get('code') and x.get('code').upper() == search_term.upper() else 1,
                x['name'].lower()
            ))
            
            # Limit total results
            results_list = results_list[:limit]
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Found {len(results_list)} geography matches for "{search_term}"')
            
            result = {
                "results": results_list,
                "search_term": search_term,
                "search_type": search_type,
                "total_found": len(results_list)
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="search_geography",
                    arguments={"search_term": search_term, "search_type": search_type, "limit": limit},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in search_geography tool: {str(e)}', e)
            return {
                "results": [],
                "error": str(e),
                "message": "Error searching geography",
                "search_term": search_term,
                "search_type": search_type
            }


class CypherGeneratorTool(BaseToolHandler):
    """Tool for generating Cypher queries"""
    
    def get_tool_definition(self) -> Dict:
        """Return tool definitions for different query types"""
        # This tool actually has multiple functions - we'll return them all
        return {
            "parameter_query": {
                "type": "function",
                "function": {
                    "name": "generate_parameter_query",
                    "description": "Generate Cypher query for company parameter data (revenue, margin, profit, etc.). Use this when user asks about financial metrics or parameters for a company.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company_name": {
                                "type": "string",
                                "description": "Exact company name from database (use search_company first)"
                            },
                            "parameter_names": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of exact parameter names from database (use search_parameters first)"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period: 'latest', 'FY-2024', 'Q1FY-2024', etc. Use 'latest' for most recent data.",
                                "default": "latest"
                            },
                            "periods": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Multiple periods to query (e.g., ['1QFY-2024', '2QFY-2024'])",
                                "default": []
                            }
                        },
                        "required": ["company_name", "parameter_names"]
                    }
                }
            },
            "company_details_query": {
                "type": "function",
                "function": {
                    "name": "generate_company_details_query",
                    "description": "Generate Cypher query for company details including country, sector, industry, market cap, and relationships.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company_name": {
                                "type": "string",
                                "description": "Company name from database (use search_company first)"
                            },
                            "include_relationships": {
                                "type": "boolean",
                                "description": "Include all relationship data (country, sector, industry)",
                                "default": True
                            }
                        },
                        "required": ["company_name"]
                    }
                }
            },
            "filter_query": {
                "type": "function",
                "function": {
                    "name": "generate_filter_query",
                    "description": "Generate Cypher query for filtering companies by sector, industry, country, region, exchange, or market cap.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sectors": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by sectors"
                            },
                            "industries": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by industries"
                            },
                            "countries": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by country codes (e.g., ['US', 'IN'])"
                            },
                            "regions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by regions"
                            },
                            "exchanges": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by exchange codes"
                            },
                            "min_market_cap": {
                                "type": "number",
                                "description": "Minimum market capitalization"
                            },
                            "max_market_cap": {
                                "type": "number",
                                "description": "Maximum market capitalization"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 50
                            }
                        }
                    }
                }
            }
        }
    
    def execute_parameter_query(self, company_name: str, parameter_names: List[str], 
                                period: str = "latest", periods: List[str] = None) -> Dict[str, Any]:
        """Generate Cypher query for parameter data"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: generate_parameter_query called - company="{company_name}", parameters={parameter_names}, period={period}')
            
            periods = periods or []
            
            # Build parameter filter conditions
            param_conditions = []
            for param in parameter_names:
                param_conditions.append(f"p.parameter_name CONTAINS '{param}'")
            
            param_filter = "(" + " OR ".join(param_conditions) + ")" if param_conditions else "1=1"
            
            # Build period filter and ordering
            if period == "latest":
                # ✅ FIXED: Get latest period for EACH parameter (not just one record total)
                # First, find the latest period overall, then filter by that period
                cypher = f"""
                MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                WHERE c.company_name CONTAINS '{company_name}'
                  AND {param_filter}
                WITH max(pr.period) as latest_period
                MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                WHERE c.company_name CONTAINS '{company_name}'
                  AND {param_filter}
                  AND pr.period = latest_period
                RETURN DISTINCT c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
                ORDER BY p.parameter_name, pr.period DESC
                """.strip()
            elif periods:
                period_list = "', '".join(periods)
                period_filter = f"AND pr.period IN ['{period_list}']"
                order_clause = "ORDER BY pr.period, p.parameter_name"
                cypher = f"""
                MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                WHERE c.company_name CONTAINS '{company_name}'
                  AND {param_filter}
                  {period_filter}
                RETURN DISTINCT c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
                {order_clause}
                """.strip()
            else:
                # ✅ FIXED: Use EXACT match for specific periods (not CONTAINS)
                # CONTAINS would incorrectly match periods like "1QFY-2025-extra" if they existed
                # For specific periods, we want exact matches only
                period_filter = f"AND pr.period = '{period}'"
                order_clause = "ORDER BY pr.period, p.parameter_name"
                cypher = f"""
                MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
                WHERE c.company_name CONTAINS '{company_name}'
                  AND {param_filter}
                  {period_filter}
                RETURN DISTINCT c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
                {order_clause}
                """.strip()
            
            result = {
                "cypher_query": cypher,
                "query_type": "parameter",
                "company_name": company_name,
                "parameter_names": parameter_names,
                "period": period
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="generate_parameter_query",
                    arguments={"company_name": company_name, "parameter_names": parameter_names, "period": period, "periods": periods},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error generating parameter query: {str(e)}', e)
            return {
                "cypher_query": "",
                "error": str(e)
            }
    
    def execute_company_details_query(self, company_name: str, include_relationships: bool = True) -> Dict[str, Any]:
        """Generate Cypher query for company details"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: generate_company_details_query called - company="{company_name}"')
            
            # Escape single quotes to prevent Cypher injection
            escaped_name = company_name.replace("'", "\\'")
            
            # Use both exact match and case-insensitive contains for better matching
            # If company_name looks like an exact name (from search_company), try exact match first
            # Otherwise, use case-insensitive contains
            if include_relationships:
                cypher = f"""
                MATCH (c:Company)-[:IN_COUNTRY]->(country:Country),
                      (c)-[:IN_SECTOR]->(s:Sector),
                      (c)-[:IN_INDUSTRY]->(i:Industry)
                WHERE c.company_name = '{escaped_name}' 
                   OR toLower(c.company_name) = toLower('{escaped_name}')
                   OR toLower(c.company_name) CONTAINS toLower('{escaped_name}')
                RETURN c.company_name, c.cid, country.name as country, country.code as country_code,
                       s.name as sector, i.name as industry, c.market_cap, c.description
                ORDER BY 
                    CASE 
                        WHEN c.company_name = '{escaped_name}' THEN 0
                        WHEN toLower(c.company_name) = toLower('{escaped_name}') THEN 1
                        ELSE 2 
                    END
                LIMIT 10
                """.strip()
            else:
                cypher = f"""
                MATCH (c:Company)
                WHERE c.company_name = '{escaped_name}' 
                   OR toLower(c.company_name) = toLower('{escaped_name}')
                   OR toLower(c.company_name) CONTAINS toLower('{escaped_name}')
                RETURN c.company_name, c.cid, c.market_cap, c.description
                ORDER BY 
                    CASE 
                        WHEN c.company_name = '{escaped_name}' THEN 0
                        WHEN toLower(c.company_name) = toLower('{escaped_name}') THEN 1
                        ELSE 2 
                    END
                LIMIT 10
                """.strip()
            
            result = {
                "cypher_query": cypher,
                "query_type": "company_details",
                "company_name": company_name
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="generate_company_details_query",
                    arguments={"company_name": company_name, "include_relationships": include_relationships},
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error generating company details query: {str(e)}', e)
            return {
                "cypher_query": "",
                "error": str(e)
            }
    
    def execute_filter_query(self, **filters) -> Dict[str, Any]:
        """Generate Cypher query for filtering companies"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: generate_filter_query called with filters: {filters}')
            
            conditions = []
            
            if filters.get("sectors"):
                sectors_list = "', '".join(filters["sectors"])
                conditions.append(f"s.name IN ['{sectors_list}']")
            
            if filters.get("industries"):
                industries_list = "', '".join(filters["industries"])
                conditions.append(f"i.name IN ['{industries_list}']")
            
            if filters.get("countries"):
                countries_list = "', '".join(filters["countries"])
                conditions.append(f"country.code IN ['{countries_list}']")
            
            if filters.get("regions"):
                regions_list = "', '".join(filters["regions"])
                conditions.append(f"r.name IN ['{regions_list}']")
            
            if filters.get("exchanges"):
                exchanges_list = "', '".join(filters["exchanges"])
                conditions.append(f"e.code IN ['{exchanges_list}']")
            
            if filters.get("min_market_cap") is not None:
                conditions.append(f"c.market_cap >= {filters['min_market_cap']}")
            
            if filters.get("max_market_cap") is not None:
                conditions.append(f"c.market_cap <= {filters['max_market_cap']}")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            limit = filters.get("limit", 50)
            
            # Build query based on filters used
            if filters.get("sectors") or filters.get("industries") or filters.get("countries"):
                cypher = f"""
                MATCH (c:Company)-[:IN_COUNTRY]->(country:Country),
                      (c)-[:IN_SECTOR]->(s:Sector),
                      (c)-[:IN_INDUSTRY]->(i:Industry)
                WHERE {where_clause}
                RETURN c.company_name, c.cid, s.name as sector, country.name as country, c.market_cap
                LIMIT {limit}
                """.strip()
            elif filters.get("regions"):
                cypher = f"""
                MATCH (c:Company)-[:IN_REGION]->(r:Region),
                      (c)-[:IN_COUNTRY]->(country:Country)
                WHERE {where_clause}
                RETURN c.company_name, c.cid, r.name as region, country.name as country, c.market_cap
                LIMIT {limit}
                """.strip()
            elif filters.get("exchanges"):
                cypher = f"""
                MATCH (c:Company)-[:LISTED_ON]->(e:Exchange)
                WHERE {where_clause}
                RETURN c.company_name, c.cid, e.code as exchange, c.market_cap
                LIMIT {limit}
                """.strip()
            else:
                cypher = f"""
                MATCH (c:Company)
                WHERE {where_clause}
                RETURN c.company_name, c.cid, c.market_cap
                LIMIT {limit}
                """.strip()
            
            result = {
                "cypher_query": cypher,
                "query_type": "filter",
                "filters": filters
            }
            
            # Log tool call result
            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                self.log_manager.add_tool_call_log(
                    tool_name="generate_filter_query",
                    arguments=filters,
                    response=result,
                    duration_ms=None
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error generating filter query: {str(e)}', e)
            return {
                "cypher_query": "",
                "error": str(e)
            }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Default execute - should not be called directly"""
        raise NotImplementedError("Use specific execute methods for each query type")


class QueryIntentExtractionTool(BaseToolHandler):
    """
    Comprehensive LLM-powered tool for extracting ALL query components at once:
    - Intent (what user wants)
    - Company name(s)
    - Parameter names
    - Period/fiscal year
    
    This replaces ALL hardcoded pattern matching with a single, scalable LLM call.
    """
    
    def __init__(self, log_manager=None):
        super().__init__(log_manager)
        # Use a lightweight model for extraction (faster and cheaper)
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "extract_query_intent",
                "description": "Extract complete query intent from a natural language question using AI. Extracts: intent type, company name(s), parameter names, and period. Handles all query formats intelligently without hardcoded patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_query": {
                            "type": "string",
                            "description": "The full user query/question to analyze"
                        }
                    },
                    "required": ["user_query"]
                }
            }
        }
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """Use LLM to intelligently extract all query components"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: extract_query_intent called for query: "{user_query}"')
            
            # Use LLM to extract all components with structured JSON output
            extraction_prompt = f"""You are a financial query analysis assistant. Extract all components from the user's query.

User Query: "{user_query}"

Extract the following components:
1. **intent**: The type of query ("parameter_query" | "company_details" | "compare" | "filter" | "unknown")
2. **company_name**: Company name(s) mentioned (null if none)
3. **parameters**: List of financial parameters mentioned (e.g., ["EBITDA margin", "Revenue"])
4. **period**: Fiscal period mentioned (e.g., "1QFY-2026", "FY-2025", "latest", null)
5. **query_type**: Additional classification ("parameter_with_period" | "parameter_latest" | "company_info" | etc.)

Instructions:
- Remove financial terms from company names (revenue, margin, profit, etc.)
- Remove time periods from company names (Q1, Q2, FY2024, etc.)
- Normalize periods to format: "1QFY-2026", "2QFY-2026", "3QFY-2026", "4QFY-2026", or "FY-2026"
- For latest queries, use period: "latest"
- Extract parameter names exactly as they appear in financial contexts
- Preserve original capitalization for company names

Examples:
- Query: "ebitda margin of kajaria q1fy2026"
  → {{"intent": "parameter_query", "company_name": "kajaria", "parameters": ["EBITDA margin"], "period": "1QFY-2026", "query_type": "parameter_with_period"}}

- Query: "show me Apple's revenue"
  → {{"intent": "parameter_query", "company_name": "Apple", "parameters": ["Revenue"], "period": "latest", "query_type": "parameter_latest"}}

- Query: "what is Reliance Industries profit?"
  → {{"intent": "parameter_query", "company_name": "Reliance Industries", "parameters": ["Profit"], "period": "latest", "query_type": "parameter_latest"}}

- Query: "Kajaria Ceramics financial data"
  → {{"intent": "company_details", "company_name": "Kajaria Ceramics", "parameters": [], "period": null, "query_type": "company_info"}}

- Query: "what is the profit margin"
  → {{"intent": "parameter_query", "company_name": null, "parameters": ["Profit margin"], "period": "latest", "query_type": "parameter_latest"}}

- Query: "revenue and profit for TCS in FY2025"
  → {{"intent": "parameter_query", "company_name": "TCS", "parameters": ["Revenue", "Profit"], "period": "FY-2025", "query_type": "parameter_with_period"}}

Return your response as a JSON object with this exact format:
{{"intent": "<intent_type>", "company_name": "<name or null>", "parameters": ["param1", "param2"], "period": "<period or null>", "query_type": "<type>"}}"""

            # Get LLM response
            response = self.llm.invoke(extraction_prompt)
            
            # Extract structured data from LLM response
            extracted_data = {
                "intent": "unknown",
                "company_name": None,
                "parameters": [],
                "period": None,
                "query_type": "unknown"
            }
            
            if hasattr(response, 'content'):
                extracted_text = response.content.strip()
                
                # Try to parse as JSON first (more reliable)
                try:
                    # Extract JSON from response (might have markdown code blocks or extra text)
                    import re
                    json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', extracted_text)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed = json.loads(json_str)
                        
                        # Validate and extract each field
                        extracted_data["intent"] = parsed.get("intent", "unknown")
                        extracted_data["company_name"] = parsed.get("company_name")
                        extracted_data["parameters"] = parsed.get("parameters", [])
                        extracted_data["period"] = parsed.get("period")
                        extracted_data["query_type"] = parsed.get("query_type", "unknown")
                        
                        # Handle null/None values
                        if extracted_data["company_name"] in [None, "null", "None", ""]:
                            extracted_data["company_name"] = None
                        if extracted_data["period"] in [None, "null", "None", ""]:
                            extracted_data["period"] = None
                        if not isinstance(extracted_data["parameters"], list):
                            extracted_data["parameters"] = []
                except Exception as e:
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Failed to parse JSON response, using fallback: {str(e)}')
                    # Could add fallback parsing here if needed
            
            result = {
                **extracted_data,
                "extracted": extracted_data["company_name"] is not None or len(extracted_data["parameters"]) > 0,
                "query": user_query
            }
            
            if self.log_manager:
                self.log_manager.add_info_log(
                    f'LLM extracted query intent: intent={result["intent"]}, '
                    f'company={result["company_name"]}, '
                    f'parameters={result["parameters"]}, '
                    f'period={result["period"]}'
                )
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in extract_query_intent tool: {str(e)}', e)
            return {
                "intent": "unknown",
                "company_name": None,
                "parameters": [],
                "period": None,
                "query_type": "unknown",
                "extracted": False,
                "error": str(e),
                "query": user_query
            }


# Keep the old tool for backward compatibility, but mark as deprecated
class CompanyNameExtractionTool(BaseToolHandler):
    """
    LLM-powered tool for intelligently extracting company names from natural language queries.
    This replaces hardcoded pattern matching with AI-powered understanding.
    """
    
    def __init__(self, log_manager=None):
        super().__init__(log_manager)
        # Use a lightweight model for extraction (faster and cheaper)
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    def get_tool_definition(self) -> Dict:
        """Return tool definition for OpenAI function calling"""
        return {
            "type": "function",
            "function": {
                "name": "extract_company_name",
                "description": "Extract company name(s) from a natural language query using AI. Use this when you need to identify which company the user is asking about. Handles all query formats intelligently without hardcoded patterns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_query": {
                            "type": "string",
                            "description": "The full user query/question from which to extract the company name"
                        }
                    },
                    "required": ["user_query"]
                }
            }
        }
    
    def execute(self, user_query: str) -> Dict[str, Any]:
        """Use LLM to intelligently extract company name from query"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool: extract_company_name called for query: "{user_query}"')
            
            # Use LLM to extract company name with structured JSON output for reliability
            extraction_prompt = f"""You are a company name extraction assistant. Extract the company name from the user's query.

User Query: "{user_query}"

Instructions:
1. Identify the company name in the query (if any)
2. Extract only the company name part, removing:
   - Financial terms (revenue, margin, profit, ebitda, ebit, sales, earnings, etc.)
   - Time periods (Q1, Q2, Q3, Q4, FY2024, FY2025, 2024, 2025, etc.)
   - Question words (what, show, tell, etc.)
   - Common words (of, the, a, an, etc.)
3. Preserve the original capitalization/spelling (e.g., "Kajaria", "Bajaj", "Apple Inc")
4. If no company name is found, set company_name to null

Examples:
- Query: "ebitda margin of kajaria q1fy2026" → {{"company_name": "kajaria", "confidence": "high"}}
- Query: "revenue of Apple Inc" → {{"company_name": "Apple Inc", "confidence": "high"}}
- Query: "show me Reliance Industries" → {{"company_name": "Reliance Industries", "confidence": "high"}}
- Query: "what is the profit margin" → {{"company_name": null, "confidence": "high"}}

Return your response as a JSON object with this exact format:
{{"company_name": "<extracted name or null>", "confidence": "high|medium|low"}}"""

            # Get LLM response
            response = self.llm.invoke(extraction_prompt)
            
            # Extract the company name from LLM response (try JSON first, then fallback)
            company_name = None
            if hasattr(response, 'content'):
                extracted_text = response.content.strip()
                
                # Try to parse as JSON first (more reliable)
                try:
                    # Extract JSON from response (might have markdown code blocks or extra text)
                    import re
                    json_match = re.search(r'\{[^{}]*"company_name"[^{}]*\}', extracted_text)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed = json.loads(json_str)
                        company_name = parsed.get("company_name")
                        # Handle null/None values
                        if company_name in [None, "null", "None", ""]:
                            company_name = None
                except:
                    # Fallback: extract text directly
                    extracted_text = extracted_text.replace("Company:", "").replace("company:", "")
                    extracted_text = extracted_text.replace("null", "").replace("None", "").replace("none", "")
                    extracted_text = extracted_text.strip()
                    
                    # If response looks valid (not empty and not an explanation)
                    if extracted_text and len(extracted_text) > 1 and extracted_text.lower() not in ["no", "none", "not found", "null"]:
                        company_name = extracted_text.strip()
            
            result = {
                "company_name": company_name,
                "extracted": company_name is not None,
                "query": user_query
            }
            
            if self.log_manager:
                if company_name:
                    self.log_manager.add_info_log(f'LLM extracted company name: "{company_name}" from query: "{user_query}"')
                else:
                    self.log_manager.add_info_log(f'LLM found no company name in query: "{user_query}"')
            
            return result
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Error in extract_company_name tool: {str(e)}', e)
            return {
                "company_name": None,
                "extracted": False,
                "error": str(e),
                "query": user_query
            }


# Tool Registry - Central registry for all tools
class ToolRegistry:
    """Central registry for tool discovery and management"""
    
    def __init__(self, log_manager=None):
        self.log_manager = log_manager
        self.embedding_cache = {}
        
        # Initialize tools
        self.parameter_search_tool = ParameterSearchTool(log_manager, self.embedding_cache)
        self.company_search_tool = CompanySearchTool(log_manager)
        self.query_intent_extraction_tool = QueryIntentExtractionTool(log_manager)
        self.company_name_extraction_tool = CompanyNameExtractionTool(log_manager)  # Deprecated, kept for compatibility
        self.sector_search_tool = SectorSearchTool(log_manager)
        self.industry_search_tool = IndustrySearchTool(log_manager)
        self.geography_search_tool = GeographySearchTool(log_manager)
        self.cypher_generator_tool = CypherGeneratorTool(log_manager)
        
        # Initialize period tools (new)
        try:
            from PEERS_RAG_tools_period import PeriodNormalizationTool, PeriodSearchTool
            self.period_normalization_tool = PeriodNormalizationTool(log_manager)
            self.period_search_tool = PeriodSearchTool(log_manager)
        except ImportError:
            # If period tools file doesn't exist, create simple inline versions
            self.period_normalization_tool = None
            self.period_search_tool = None
            if log_manager:
                log_manager.add_info_log('Period tools not available - period search/normalization disabled')
        
        # Register all tools
        self.tools = {
            "search_parameters": self.parameter_search_tool,
            "search_company": self.company_search_tool,
            "extract_query_intent": self.query_intent_extraction_tool,  # Primary extraction tool
            "extract_company_name": self.company_name_extraction_tool,  # Deprecated
            "search_sectors": self.sector_search_tool,
            "search_industries": self.industry_search_tool,
            "search_geography": self.geography_search_tool,
            "generate_parameter_query": self.cypher_generator_tool,
            "generate_company_details_query": self.cypher_generator_tool,
            "generate_filter_query": self.cypher_generator_tool
        }
        
        # Register period tools if available
        if self.period_normalization_tool:
            self.tools["normalize_period"] = self.period_normalization_tool
        if self.period_search_tool:
            self.tools["search_periods"] = self.period_search_tool
    
    def get_all_tool_definitions(self) -> List[Dict]:
        """Get all tool definitions in OpenAI format"""
        tools = []
        
        # Add search tools
        tools.append(self.parameter_search_tool.get_tool_definition())
        tools.append(self.company_search_tool.get_tool_definition())
        tools.append(self.query_intent_extraction_tool.get_tool_definition())  # Primary
        tools.append(self.company_name_extraction_tool.get_tool_definition())  # Deprecated, kept for compatibility
        tools.append(self.sector_search_tool.get_tool_definition())
        tools.append(self.industry_search_tool.get_tool_definition())
        tools.append(self.geography_search_tool.get_tool_definition())
        
        # Add period tools if available
        if self.period_normalization_tool:
            tools.append(self.period_normalization_tool.get_tool_definition())
        if self.period_search_tool:
            tools.append(self.period_search_tool.get_tool_definition())
        
        # Add generator tools (they return dict of multiple tools)
        generator_defs = self.cypher_generator_tool.get_tool_definition()
        tools.append(generator_defs["parameter_query"])
        tools.append(generator_defs["company_details_query"])
        tools.append(generator_defs["filter_query"])
        
        return tools
    
    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}
        
        tool = self.tools[tool_name]
        
        # Route to correct execute method
        if tool_name == "generate_parameter_query":
            return tool.execute_parameter_query(**kwargs)
        elif tool_name == "generate_company_details_query":
            return tool.execute_company_details_query(**kwargs)
        elif tool_name == "generate_filter_query":
            return tool.execute_filter_query(**kwargs)
        elif tool_name in ["normalize_period", "search_periods", "search_parameters", "search_company", 
                           "extract_query_intent", "extract_company_name", "search_sectors", "search_industries", "search_geography"]:
            return tool.execute(**kwargs)
        else:
            return tool.execute(**kwargs)
    
    def clear_embedding_cache(self):
        """Clear embedding cache (useful when schema changes)"""
        self.embedding_cache.clear()
        if self.log_manager:
            self.log_manager.add_info_log('Embedding cache cleared')

