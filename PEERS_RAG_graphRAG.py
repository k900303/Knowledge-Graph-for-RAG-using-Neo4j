"""
GraphRAG Module for PEERS RAG System
Generates Cypher queries for company knowledge graph
"""

from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from neo4j_env import graph, get_graph
from PEERS_RAG_tools import ToolRegistry
from PEERS_RAG_react import ReActEngine, BaseReasoningEngine
from PEERS_RAG_company_verification import CompanyVerificationTool, CompanyNameExtractor, CompanyQueryBuilder
from PEERS_RAG_prompts import ModularPromptBuilder, QueryAnalyzer
from typing import List, Optional
import textwrap
import traceback
import inspect
import io
import sys
import re
import json


# Note: The old monolithic prompt template has been removed - we now use Tool Calling exclusively


class OutputCapture:
    """Capture stdout to extract Cypher queries from verbose output"""
    
    def __init__(self):
        self.captured_output = ""
        self.original_stdout = None
    
    def __enter__(self):
        self.original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.captured_output = sys.stdout.getvalue()
        sys.stdout = self.original_stdout
    
    def extract_cypher(self):
        """Extract Cypher query from captured output"""
        lines = self.captured_output.split('\n')
        for i, line in enumerate(lines):
            if 'Generated Cypher:' in line:
                # The Cypher query is usually on the next line
                if i + 1 < len(lines):
                    cypher_line = lines[i + 1].strip()
                    if cypher_line and not cypher_line.startswith('Full Context:'):
                        # Remove ANSI color codes
                        cypher_line = re.sub(r'\x1b\[[0-9;]*m', '', cypher_line)
                        return cypher_line
        return "Cypher query not captured from output"


class PEERSGraphRAG:
    """GraphRAG class for company knowledge graph"""
    
    def __init__(self, log_manager=None, use_tool_calling=True):
        self.log_manager = log_manager
        self.cypher_history = []  # Store generated Cypher queries
        self.schema_cache = None  # Cache for schema data
        self.cache_timestamp = None
        
        # Tool Calling support (now default)
        self.use_tool_calling = use_tool_calling
        self.tool_registry = None
        self.llm_with_tools = None
        
        # ReAct support (future)
        self.react_engine = None
        
        # Always initialize tool calling (it's the default)
        self._initialize_tool_calling()
        
        # Cypher chain is no longer needed (we use tool calling instead)
        self.cypher_chain = None
    
    def _initialize_tool_calling(self):
        """Initialize tool calling infrastructure"""
        try:
            if self.log_manager:
                self.log_manager.add_info_log('Initializing Tool Calling infrastructure...')
            
            # Create tool registry
            self.tool_registry = ToolRegistry(log_manager=self.log_manager)
            
            # Get all tool definitions
            tool_definitions = self.tool_registry.get_all_tool_definitions()
            
            # Create LLM and bind tools
            # Use gpt-4o if available, otherwise fallback to gpt-4 or gpt-3.5-turbo
            try:
                llm = ChatOpenAI(model="gpt-4o", temperature=0)
            except Exception:
                try:
                    llm = ChatOpenAI(model="gpt-4", temperature=0)
                except Exception:
                    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            
            self.llm_with_tools = llm.bind_tools(tool_definitions)
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Tool Calling initialized with {len(tool_definitions)} tools')
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Failed to initialize Tool Calling: {str(e)}', e)
            # Fallback to non-tool calling
            self.use_tool_calling = False
    
    def _assess_complexity(self, question: str) -> str:
        """
        Assess query complexity to decide between Tool Calling and ReAct
        
        Returns:
            "simple" - Use Tool Calling (fast, efficient)
            "complex" - Use ReAct (future implementation)
        """
        question_lower = question.lower()
        
        # Complex query indicators (will use ReAct in future)
        complex_indicators = [
            "compare", "comparison", "vs", "versus", "trend",
            "across", "multiple", "over", "calculate", "sum",
            "aggregate", "average", "ratio", "difference",
            "growth rate", "percentage change", "correlation"
        ]
        
        # Count complexity indicators
        complexity_score = sum(1 for indicator in complex_indicators if indicator in question_lower)
        
        # Multi-entity detection (multiple companies, multiple parameters)
        company_count = len(re.findall(r'\b(company|companies|corporation|corp)\b', question_lower))
        param_count = len(re.findall(r'\b(revenue|margin|profit|ebitda|sales|earnings)\b', question_lower))
        
        # Determine complexity
        if complexity_score >= 2 or company_count > 1 or param_count > 2:
            return "complex"
        else:
            return "simple"
    
    def get_dynamic_schema_context(self):
        """Get actual values from the database to enhance the prompt"""
        import time
        
        # Check if cache is still valid (5 minutes)
        if (self.schema_cache and self.cache_timestamp and 
            time.time() - self.cache_timestamp < 300):
            return self.schema_cache
        
        try:
            if self.log_manager:
                self.log_manager.add_info_log('Fetching dynamic schema context...')
            
            schema_context = {
                'sectors': [],
                'industries': [],
                'countries': [],
                'regions': [],
                'exchanges': [],
                'parameters': [],
                'periods': [],
                'companies': []
            }
            
            # Get sectors
            sectors_query = "MATCH (s:Sector) RETURN DISTINCT s.name ORDER BY s.name LIMIT 20"
            # Ensure graph connection is available
            if graph is None:
                graph = get_graph()
                if graph is None:
                    if self.log_manager:
                        self.log_manager.add_error_log('Neo4j not connected. Please ensure Neo4j is running.')
                    return None
            
            sectors_result = graph.query(sectors_query)
            schema_context['sectors'] = [row['s.name'] for row in sectors_result]
            
            # Get industries
            industries_query = "MATCH (i:Industry) RETURN DISTINCT i.name ORDER BY i.name LIMIT 30"
            industries_result = graph.query(industries_query)
            schema_context['industries'] = [row['i.name'] for row in industries_result]
            
            # Get countries
            countries_query = "MATCH (c:Country) RETURN DISTINCT c.name, c.code ORDER BY c.name LIMIT 20"
            countries_result = graph.query(countries_query)
            schema_context['countries'] = [f"{row['c.name']} ({row['c.code']})" for row in countries_result]
            
            # Get regions
            regions_query = "MATCH (r:Region) RETURN DISTINCT r.name ORDER BY r.name LIMIT 10"
            regions_result = graph.query(regions_query)
            schema_context['regions'] = [row['r.name'] for row in regions_result]
            
            # Get exchanges
            exchanges_query = "MATCH (e:Exchange) RETURN DISTINCT e.code ORDER BY e.code LIMIT 15"
            exchanges_result = graph.query(exchanges_query)
            schema_context['exchanges'] = [row['e.code'] for row in exchanges_result]
            
            # Get parameters (increase limit for better matching)
            parameters_query = "MATCH (p:Parameter) RETURN DISTINCT p.parameter_name ORDER BY p.parameter_name LIMIT 50"
            parameters_result = graph.query(parameters_query)
            schema_context['parameters'] = [row['p.parameter_name'] for row in parameters_result]
            
            # Get periods (ordered DESC to get latest first)
            periods_query = "MATCH (pr:PeriodResult) RETURN DISTINCT pr.period ORDER BY pr.period DESC LIMIT 20"
            periods_result = graph.query(periods_query)
            schema_context['periods'] = [row['pr.period'] for row in periods_result]
            
            # Get companies (for parameter query matching)
            companies_query = "MATCH (c:Company) RETURN DISTINCT c.company_name ORDER BY c.company_name LIMIT 30"
            companies_result = graph.query(companies_query)
            schema_context['companies'] = [row['c.company_name'] for row in companies_result]
            
            self.schema_cache = schema_context
            self.cache_timestamp = time.time()
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Schema context loaded: {len(schema_context["sectors"])} sectors, {len(schema_context["industries"])} industries, {len(schema_context["parameters"])} parameters, {len(schema_context["companies"])} companies, {len(schema_context["periods"])} periods')
            
            return schema_context
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Failed to fetch schema context: {str(e)}', e)
            return None
    
    def _extract_cypher_query(self, text: str) -> str:
        """Extract Cypher query from LLM response, removing any explanatory text"""
        text = text.strip()
        
        # If it starts with Cypher keywords, return as-is
        if text.upper().startswith(('MATCH', 'RETURN', 'WITH', 'OPTIONAL', 'UNWIND', 'CALL')):
            return text
        
        # Remove common prefixes
        prefixes = ['Cypher:', 'Query:', 'Cypher Query:', 'Here is the Cypher query:', 
                   'The Cypher query is:', 'Generated Cypher:', '```cypher', '```']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # Remove code block markers
        text = text.replace('```cypher', '').replace('```', '').strip()
        
        # Find the first line that starts with MATCH, RETURN, etc.
        lines = text.split('\n')
        cypher_lines = []
        in_cypher = False
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.upper().startswith(('MATCH', 'RETURN', 'WITH', 'OPTIONAL', 'UNWIND', 'CALL', 'ORDER', 'LIMIT', 'WHERE', 'AND', 'OR')):
                in_cypher = True
                cypher_lines.append(line_stripped)
            elif in_cypher and line_stripped:
                # Continue collecting if we're in the middle of a query
                if not line_stripped.lower().startswith(('here', 'the query', 'i ', 'sorry', 'cannot')):
                    cypher_lines.append(line_stripped)
                else:
                    break
        
        if cypher_lines:
            return '\n'.join(cypher_lines)
        
        return text
    
    def _is_parameter_question(self, question: str) -> bool:
        """
        Check if the question is asking about parameters (DEPRECATED - use extract_query_intent tool)
        
        This method uses hardcoded pattern matching and is NOT scalable.
        The primary method is LLM-powered extraction via extract_query_intent tool.
        """
        question_lower = question.lower()
        parameter_indicators = [
            'revenue', 'margin', 'profit', 'ebitda', 'ebit', 'net income', 
            'parameter', 'earnings', 'sales', 'cost', 'expense', 'ratio',
            'growth', 'yoy', 'qoq', 'percentage', 'metric', 'financial',
            'production', 'volume', 'capacity', 'quantity', 'units', 'output',
            'receivable', 'payable', 'accounts', 'asset', 'liability', 'equity'
        ]
        return any(indicator in question_lower for indicator in parameter_indicators)
    
    def _extract_parameter_names_from_question(self, question: str) -> List[str]:
        """
        Extract parameter names from question (DEPRECATED - use extract_query_intent tool)
        
        This method uses hardcoded pattern matching and is NOT scalable.
        The primary method is LLM-powered extraction via extract_query_intent tool.
        """
        question_lower = question.lower()
        params = []
        
        # Check for common parameter patterns
        if 'ebitda margin' in question_lower:
            params.append('EBITDA margin')
        elif 'ebitda' in question_lower:
            params.append('EBITDA')
        if 'revenue' in question_lower and 'revenue' not in params:
            params.append('Revenue')
        if 'profit' in question_lower and 'margin' not in question_lower:
            params.append('Profit')
        if 'net margin' in question_lower:
            params.append('Net margin')
        
        return params if params else None
    
    def _extract_period_from_question(self, question: str) -> Optional[str]:
        """
        Extract period from question and normalize it (DEPRECATED - use extract_query_intent tool)
        
        This method uses hardcoded regex patterns and is NOT scalable.
        The primary method is LLM-powered extraction via extract_query_intent tool.
        """
        question_lower = question.lower()
        
        # Try to use period normalization tool if available
        if self.tool_registry and self.tool_registry.period_normalization_tool:
            # Try to extract period string from question
            import re
            # Match patterns like Q1FY2025, FY2025Q1, 1QFY2025, etc.
            period_patterns = [
                r'\b(q[1-4]|quarter\s+[1-4])\s*(?:of\s+)?(?:fy|fiscal\s+year)?\s*(\d{4})',
                r'\b(fy|fiscal\s+year)\s*(\d{4})\s*(?:q[1-4]|quarter\s+[1-4])',
                r'\b([1-4]qfy|q[1-4]fy)\s*-?\s*(\d{4})',
                r'\bfy-?(\d{4})',
            ]
            
            for pattern in period_patterns:
                match = re.search(pattern, question, re.IGNORECASE)
                if match:
                    period_str = match.group(0)
                    try:
                        result = self.tool_registry.execute_tool("normalize_period", period_string=period_str)
                        return result.get('normalized', period_str)
                    except:
                        pass
        
        # Fallback: simple extraction
        import re
        # Q1FY2025, Q1 FY2025, etc.
        q_match = re.search(r'q([1-4])\s*(?:fy|fiscal)?\s*(\d{4})', question_lower)
        if q_match:
            q, year = q_match.groups()
            return f"{q}QFY-{year}"
        
        # FY2025
        fy_match = re.search(r'fy-?(\d{4})', question_lower)
        if fy_match:
            return f"FY-{fy_match.group(1)}"
        
        # Latest
        if 'latest' in question_lower or 'most recent' in question_lower:
            return 'latest'
        
        return None
    
    def _query_has_parameters(self, query: str) -> bool:
        """Check if the Cypher query includes Parameter and PeriodResult nodes"""
        query_upper = query.upper()
        # Must have HAS_PARAMETER relationship and PeriodResult node
        return ':PARAMETER' in query_upper or 'HAS_PARAMETER' in query_upper or 'PERIODRESULT' in query_upper or 'HAS_VALUE_IN_PERIOD' in query_upper
    
    def _decompose_parameter_query(self, question: str) -> dict:
        """
        Decompose a complex parameter query into components for multi-hop reasoning
        Returns a dictionary with extracted components
        """
        question_lower = question.lower()
        
        decomposition = {
            'company': None,
            'parameters': [],
            'period': None,
            'operation': 'retrieve',  # retrieve, compare, aggregate
            'is_multi_parameter': False
        }
        
        # Extract company name
        try:
            if schema_context := self.get_dynamic_schema_context():
                companies = schema_context.get('companies', [])
                for company in companies[:50]:
                    company_words = company.lower().split()
                    for word in company_words:
                        if len(word) > 3 and word in question_lower:
                            decomposition['company'] = company
                            break
                    if decomposition['company']:
                        break
        except Exception:
            pass  # Continue with special case matching
        
        # Special case for known companies (hardcoded for common ones)
        if not decomposition['company']:
            if 'kajaria' in question_lower:
                decomposition['company'] = 'Kajaria Ceramics'
            # Add more special cases as needed
            elif 'bajaj' in question_lower:
                # Could be multiple Bajaj companies, use partial match
                decomposition['company'] = 'Bajaj'  # Will use fuzzy matching
        
        # Extract parameters - check for multiple parameters
        # EBITDA margin detection
        if 'ebitda margin' in question_lower:
            decomposition['parameters'].append('EBITDA margin')
        elif 'ebitda' in question_lower and 'margin' in question_lower:
            decomposition['parameters'].append('EBITDA margin')
        
        # Net margin detection
        if 'net margin' in question_lower:
            decomposition['parameters'].append('Net margin')
        elif 'net' in question_lower and 'margin' in question_lower and 'ebitda' not in question_lower:
            # Check that they're close together
            net_pos = question_lower.find('net')
            margin_pos = question_lower.find('margin')
            if abs(net_pos - margin_pos) < 15:  # Within 15 chars
                decomposition['parameters'].append('Net margin')
        
        # Net profit detection (separate check so both can be detected)
        if 'net profit' in question_lower:
            decomposition['parameters'].append('Net profit')
        elif 'net' in question_lower and 'profit' in question_lower and 'net margin' not in question_lower:
            # Check that they're close together in the sentence
            net_pos = question_lower.find('net')
            profit_pos = question_lower.find('profit')
            if abs(net_pos - profit_pos) < 10:  # Within 10 chars
                decomposition['parameters'].append('Net profit')
        
        # Production volume detection
        if 'production volume' in question_lower or ('production' in question_lower and 'volume' in question_lower):
            decomposition['parameters'].append('Production Units/Volume')
        elif 'production' in question_lower:
            # Check if they're close together
            prod_pos = question_lower.find('production')
            vol_pos = question_lower.find('volume')
            if abs(prod_pos - vol_pos) < 15:  # Within 15 chars
                decomposition['parameters'].append('Production Units/Volume')
        
        # Accounts receivable detection
        if 'accounts receivable' in question_lower:
            decomposition['parameters'].append('Accounts receivable')
        elif 'receivable' in question_lower and 'accounts receivable' not in question_lower:
            decomposition['parameters'].append('Receivables, Net')  # Fallback to common variant
        
        # Total revenue detection
        if 'total revenue' in question_lower:
            decomposition['parameters'].append('Total revenue, Primary')
        elif 'revenue' in question_lower and 'total revenue' not in question_lower and 'production' not in question_lower:
            decomposition['parameters'].append('Revenue')
        
        decomposition['is_multi_parameter'] = len(decomposition['parameters']) > 1
        
        # Extract period - dynamically detect year
        import re
        year_match = re.search(r'(?:fy-|20)(\d{4})', question_lower)
        year = year_match.group(1) if year_match else '2024'  # Default to 2024 if not specified
        
        if 'q3' in question_lower or '3q' in question_lower:
            decomposition['period'] = f'3QFY-{year}'
        elif 'q2' in question_lower or '2q' in question_lower:
            decomposition['period'] = f'2QFY-{year}'
        elif 'q1' in question_lower or '1q' in question_lower:
            decomposition['period'] = f'1QFY-{year}'
        elif 'q4' in question_lower or '4q' in question_lower:
            decomposition['period'] = f'4QFY-{year}'
        elif f'fy-{year}' in question_lower or 'fy-2024' in question_lower or 'fy-2025' in question_lower:
            # Extract year from question
            fy_match = re.search(r'fy-(\d{4})', question_lower)
            if fy_match:
                decomposition['period'] = f'FY-{fy_match.group(1)}'
            else:
                decomposition['period'] = f'FY-{year}'
        elif 'latest' in question_lower or 'recent' in question_lower:
            decomposition['period'] = 'latest'
        
        # Detect operation type
        if any(op in question_lower for op in ['compare', 'comparison', 'vs', 'versus', 'difference']):
            decomposition['operation'] = 'compare'
        elif any(op in question_lower for op in ['sum', 'total', 'aggregate', 'average']):
            decomposition['operation'] = 'aggregate'
        
        return decomposition
    
    def _generate_decomposed_query(self, decomposition: dict) -> str:
        """
        Generate a Cypher query from decomposed components using multi-hop reasoning
        """
        company = decomposition['company']
        parameters = decomposition['parameters']
        period = decomposition['period']
        is_multi = decomposition['is_multi_parameter']
        
        if not company:
            # If no company found, return a generic parameter query
            return "MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth LIMIT 20"
        
        # Build company filter
        company_word = company.split()[0] if company else ''
        where_parts = [f"c.company_name CONTAINS '{company_word}'"]
        
        # Build parameter filter
        if parameters:
            param_conditions = []
            for param in parameters:
                if param == 'EBITDA margin':
                    param_conditions.append("p.parameter_name CONTAINS 'EBITDA margin'")
                elif param == 'Net margin':
                    param_conditions.append("p.parameter_name CONTAINS 'Net margin'")
                elif param == 'Net profit':
                    param_conditions.append("p.parameter_name CONTAINS 'Net profit'")
                elif param == 'Production Units/Volume':
                    param_conditions.append("(p.parameter_name CONTAINS 'Production Units/Volume' OR (p.parameter_name CONTAINS 'Production' AND p.parameter_name CONTAINS 'Volume'))")
                elif param == 'Accounts receivable':
                    # Match all variations including "Accounts receivable, Average", etc.
                    param_conditions.append("p.parameter_name CONTAINS 'Accounts receivable'")
                elif param == 'Receivables, Net':
                    # Match all receivable variations
                    param_conditions.append("(p.parameter_name CONTAINS 'Receivables' OR p.parameter_name CONTAINS 'Receivable' OR (p.parameter_name CONTAINS 'Accounts' AND p.parameter_name CONTAINS 'receivable'))")
                elif param == 'Total revenue, Primary':
                    param_conditions.append("p.parameter_name CONTAINS 'Total revenue'")
                elif param == 'Revenue':
                    param_conditions.append("p.parameter_name CONTAINS 'Revenue'")
            
            if param_conditions:
                param_filter = "(" + " OR ".join(param_conditions) + ")"
                where_parts.append(param_filter)
        else:
            # If no specific parameters detected, use broader matching
            # This handles cases where parameter names might vary
            where_parts.append("(p.parameter_name CONTAINS 'Revenue' OR p.parameter_name CONTAINS 'Profit' OR p.parameter_name CONTAINS 'margin')")
        
        # Build period filter
        if period and period != 'latest':
            where_parts.append(f"pr.period CONTAINS '{period}'")
        
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        # Build ORDER BY
        if period == 'latest' or period is None:
            order_clause = "ORDER BY pr.period DESC"
            limit_clause = "LIMIT 10" if is_multi else "LIMIT 5"
        elif is_multi:
            order_clause = "ORDER BY p.parameter_name, pr.period"
            limit_clause = ""
        else:
            order_clause = "ORDER BY p.parameter_name"
            limit_clause = ""
        
        query = f"MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)"
        query += f" WHERE {where_clause}"
        query += f" RETURN DISTINCT c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth"
        
        # Build final query with proper spacing - don't strip the leading space!
        if order_clause:
            query += f" {order_clause.strip()}"
        if limit_clause:
            query += f" {limit_clause.strip()}"
        
        return query.strip()
    
    def _is_valid_cypher(self, query: str) -> bool:
        """Check if the response looks like a valid Cypher query"""
        if not query or len(query.strip()) < 10:
            return False
        
        query_upper = query.upper().strip()
        
        # Must start with valid Cypher keywords
        valid_starts = ['MATCH', 'RETURN', 'WITH', 'OPTIONAL', 'UNWIND', 'CALL', 'MERGE', 'CREATE']
        if not any(query_upper.startswith(start) for start in valid_starts):
            return False
        
        # Should not contain natural language apology phrases
        apology_phrases = ["i'm sorry", "i cannot", "here is", "the query is", 
                          "i am unable", "cannot assist", "not specific enough"]
        query_lower = query.lower()
        if any(phrase in query_lower for phrase in apology_phrases):
            return False
        
        # Should contain some Cypher keywords
        cypher_keywords = ['MATCH', 'RETURN', 'WHERE', 'WITH', 'ORDER', 'LIMIT']
        if not any(keyword in query_upper for keyword in cypher_keywords):
            return False
        
        return True
    
    def _extract_cypher_from_text(self, text: str) -> str:
        """Try to extract a Cypher query from text that might contain explanations"""
        # Look for code blocks
        import re
        code_block_pattern = r'```(?:cypher)?\s*(.*?)```'
        matches = re.findall(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0].strip()
        
        # Look for lines starting with MATCH or RETURN
        lines = text.split('\n')
        cypher_start = None
        for i, line in enumerate(lines):
            if line.strip().upper().startswith(('MATCH', 'RETURN')):
                cypher_start = i
                break
        
        if cypher_start is not None:
            return '\n'.join(lines[cypher_start:]).strip()
        
        return text.strip()
    
    def _search_exact_company_name(self, search_term: str, limit: int = 5) -> str:
        """
        Search Neo4j for exact company name matching the search term
        Uses CompanyVerificationTool for better separation of concerns
        
        Args:
            search_term: Partial company name from user query (e.g., "kajaria")
            limit: Maximum number of results to check
            
        Returns:
            Exact company name from database (e.g., "Kajaria Ceramics") or None
        """
        try:
            # Use the dedicated verification tool
            verification_tool = CompanyVerificationTool(log_manager=self.log_manager)
            verification_result = verification_tool.verify_company_name(search_term, limit=limit)
            
            if verification_result.get("exact_name"):
                return verification_result["exact_name"]
            
            return None
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_info_log(f'Error searching for company name: {str(e)}')
            return None
    
    def _generate_smart_fallback_query(self, question: str) -> str:
        """
        Generate a smart fallback Cypher query by extracting company name from question
        Uses dedicated tools for better separation: CompanyNameExtractor, CompanyVerificationTool, CompanyQueryBuilder
        This is used when tool calling fails to produce a valid query
        """
        try:
            question_lower = question.lower()
            
            # Check if this is a company details query
            is_details_query = any(word in question_lower for word in ['details', 'detail', 'information', 'info', 'about'])
            is_parameter_query = self._is_parameter_question(question)
            
            # Use comprehensive LLM-powered extraction tool (extracts intent, company, parameters, period)
            # This replaces ALL hardcoded pattern matching with a single, scalable LLM call
            extracted_intent = None
            company_search_term = None
            param_names = None
            period = None
            
            # Try comprehensive LLM extraction first (foolproof approach)
            if self.tool_registry:
                try:
                    intent_result = self.tool_registry.execute_tool("extract_query_intent", user_query=question)
                    if intent_result.get("extracted"):
                        extracted_intent = intent_result.get("intent", "unknown")
                        company_search_term = intent_result.get("company_name")
                        param_names = intent_result.get("parameters", [])
                        period = intent_result.get("period")
                        
                        # Override is_parameter_query and is_details_query with LLM-extracted intent
                        is_parameter_query = extracted_intent == "parameter_query"
                        is_details_query = extracted_intent == "company_details"
                        
                        if self.log_manager:
                            self.log_manager.add_info_log(
                                f'LLM extracted complete intent: intent={extracted_intent}, '
                                f'company={company_search_term}, params={param_names}, period={period}'
                            )
                except Exception as e:
                    if self.log_manager:
                        self.log_manager.add_info_log(f'LLM intent extraction failed, using fallback: {str(e)}')
            
            # Fallback to individual extraction methods only if comprehensive LLM fails
            if not extracted_intent or extracted_intent == "unknown":
                # Fallback to regex-based extraction (for offline scenarios)
                if not company_search_term:
                    company_search_term = CompanyNameExtractor.extract_from_query(question)
                    if company_search_term and self.log_manager:
                        self.log_manager.add_info_log(f'Regex fallback extracted company: "{company_search_term}"')
                
                # Fallback to hardcoded parameter extraction (deprecated)
                if not param_names:
                    param_names = self._extract_parameter_names_from_question(question)
                    if param_names and self.log_manager:
                        self.log_manager.add_info_log(f'Regex fallback extracted parameters: {param_names}')
                
                # Fallback to hardcoded period extraction (deprecated)
                if not period:
                    period = self._extract_period_from_question(question) or 'latest'
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Regex fallback extracted period: {period}')
            
            # If we found a search term, verify it and build query
            if company_search_term:
                if self.log_manager:
                    self.log_manager.add_info_log(f'Extracted company search term: "{company_search_term}"')
                
                # Use verification tool to get exact company name
                verification_tool = CompanyVerificationTool(log_manager=self.log_manager)
                
                # Get the first word for initial search (e.g., "kajaria" from "kajaria company")
                search_word = company_search_term.split()[0].lower()
                
                # Verify and get exact company name
                verification_result = verification_tool.verify_company_name(search_word, limit=5)
                exact_company_name = verification_result.get("exact_name")
                matches = verification_result.get("matches", [])
                
                # Use exact name if found, otherwise try first match, otherwise use search term
                if exact_company_name:
                    company_name_to_use = exact_company_name
                    use_exact_match = True  # Use exact match when we have verified name
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Using verified exact company name: "{company_name_to_use}"')
                elif matches and len(matches) > 0:
                    # Use first match even if not exact
                    company_name_to_use = matches[0].get("company_name", company_search_term)
                    use_exact_match = True  # Use exact match with the found company name
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Using best match from verification: "{company_name_to_use}"')
                else:
                    # Fallback to using the search term directly (with fuzzy matching)
                    company_name_to_use = company_search_term
                    use_exact_match = False  # Use contains matching as fallback
                    if self.log_manager:
                        self.log_manager.add_info_log(f'No verification matches, using search term with fuzzy matching: "{company_name_to_use}"')
                
                # Generate appropriate query using query builder
                if is_details_query and not is_parameter_query:
                    # Company details query
                    return CompanyQueryBuilder.build_company_details_query(
                        company_name_to_use, 
                        use_exact_match=use_exact_match
                    )
                elif is_parameter_query:
                    # Parameter query with company filter
                    # Use LLM-extracted parameters and period (already extracted above)
                    # If not extracted by LLM, fallback to hardcoded methods (handled above)
                    if not param_names:
                        param_names = self._extract_parameter_names_from_question(question)
                    if not period:
                        period = self._extract_period_from_question(question) or 'latest'
                    
                    return CompanyQueryBuilder.build_parameter_query(
                        company_name_to_use,
                        parameter_names=param_names,
                        period=period,
                        use_exact_match=use_exact_match
                    )
                else:
                    # Generic company query
                    if use_exact_match:
                        where_clause = f"c.company_name = '{company_name_to_use}'"
                    else:
                        where_clause = f"c.company_name CONTAINS '{company_name_to_use}'"
                    
                    return f"""MATCH (c:Company)
                    WHERE {where_clause}
                    RETURN c.company_name, c.cid
                    LIMIT 20"""
            
            return None  # Could not extract company name
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_info_log(f'Smart fallback query generation failed: {str(e)}')
            return None
    
    def _generate_fallback_query(self, question: str) -> str:
        """Generate a smart fallback Cypher query when LLM fails (deprecated - use _generate_smart_fallback_query)"""
        question_lower = question.lower()
        original_question = question
        
        # Parameter query fallback
        if any(indicator in question_lower for indicator in ['revenue', 'margin', 'profit', 'ebitda', 'ebit', 'net income', 'parameter', 'earnings', 'sales']):
            # Extract company name
            companies = []
            company_match = None
            if schema_context := self.get_dynamic_schema_context():
                companies = schema_context.get('companies', [])
                
                # Find company in question - check for partial matches
                for company in companies[:30]:  # Check first 30 companies
                    company_lower = company.lower()
                    # Check if any significant word from company name is in question
                    company_words = company_lower.split()
                    for word in company_words:
                        if len(word) > 3 and word in question_lower:
                            company_match = company
                            break
                    if company_match:
                        break
                
                # Also try direct match
                if not company_match:
                    for company in companies[:30]:
                        if any(word in question_lower for word in company.lower().split() if len(word) > 2):
                            company_match = company
                            break
            
            # Extract period info - dynamically detect year
            import re
            year_match = re.search(r'(?:fy-|20)(\d{4})', question_lower)
            year = year_match.group(1) if year_match else '2024'  # Default to 2024 if not specified
            
            period_conditions = []
            if 'q3' in question_lower or '3q' in question_lower:
                period_conditions.append(f"pr.period CONTAINS '3QFY-{year}'")
            elif 'q2' in question_lower or '2q' in question_lower:
                period_conditions.append(f"pr.period CONTAINS '2QFY-{year}'")
            elif 'q1' in question_lower or '1q' in question_lower:
                period_conditions.append(f"pr.period CONTAINS '1QFY-{year}'")
            elif 'q4' in question_lower or '4q' in question_lower:
                period_conditions.append(f"pr.period CONTAINS '4QFY-{year}'")
            elif 'fy-' in question_lower:
                # Extract year from FY pattern
                fy_match = re.search(r'fy-(\d{4})', question_lower)
                if fy_match:
                    period_conditions.append(f"pr.period CONTAINS 'FY-{fy_match.group(1)}'")
                else:
                    period_conditions.append(f"pr.period CONTAINS 'FY-{year}'")
            elif 'latest' in question_lower or 'recent' in question_lower:
                period_conditions.append("")  # No period filter, will order by DESC LIMIT 1
            
            # Build parameter conditions (order matters - more specific first)
            param_conditions = []
            
            # Production volume detection
            if 'production volume' in question_lower or ('production' in question_lower and 'volume' in question_lower):
                param_conditions.append("(p.parameter_name CONTAINS 'Production Units/Volume' OR (p.parameter_name CONTAINS 'Production' AND p.parameter_name CONTAINS 'Volume'))")
            elif 'production' in question_lower:
                param_conditions.append("p.parameter_name CONTAINS 'Production'")
            
            # Accounts receivable detection - match all variations (don't be too specific)
            if 'accounts receivable' in question_lower:
                # Match "Accounts receivable", "Accounts receivable, Average", etc.
                param_conditions.append("p.parameter_name CONTAINS 'Accounts receivable'")
            elif 'receivable' in question_lower and 'accounts receivable' not in question_lower:
                # Match any receivable-related parameter
                param_conditions.append("(p.parameter_name CONTAINS 'Receivables' OR p.parameter_name CONTAINS 'Receivable' OR (p.parameter_name CONTAINS 'Accounts' AND p.parameter_name CONTAINS 'receivable'))")
            
            if 'total revenue' in question_lower:
                param_conditions.append("p.parameter_name CONTAINS 'Total revenue'")
            elif 'revenue' in question_lower and 'production' not in question_lower and 'receivable' not in question_lower:
                param_conditions.append("p.parameter_name CONTAINS 'Revenue'")
            
            if 'ebitda margin' in question_lower or ('ebitda' in question_lower and 'margin' in question_lower):
                param_conditions.append("p.parameter_name CONTAINS 'EBITDA margin'")
            
            if 'net margin' in question_lower or ('net' in question_lower and 'margin' in question_lower and 'ebitda' not in question_lower):
                param_conditions.append("p.parameter_name CONTAINS 'Net margin'")
            elif 'margin' in question_lower and 'ebitda margin' not in question_lower and 'net margin' not in question_lower:
                param_conditions.append("p.parameter_name CONTAINS 'margin'")
            
            if 'net profit' in question_lower or ('net' in question_lower and 'profit' in question_lower):
                param_conditions.append("p.parameter_name CONTAINS 'Net profit'")
            elif 'profit' in question_lower and 'net profit' not in question_lower:
                param_conditions.append("p.parameter_name CONTAINS 'Profit'")
            
            # Build WHERE clause
            where_parts = []
            
            # Company filter
            if company_match:
                # Use first significant word for fuzzy match
                company_word = company_match.split()[0]
                where_parts.append(f"c.company_name CONTAINS '{company_word}'")
            elif 'kajaria' in question_lower:
                where_parts.append("c.company_name CONTAINS 'Kajaria'")
            
            # Period filter
            if period_conditions:
                period_condition = period_conditions[0]
                if period_condition:
                    where_parts.append(period_condition)
            
            # Parameter filter
            if param_conditions:
                param_condition = "(" + " OR ".join(param_conditions) + ")"
                where_parts.append(param_condition)
            
            where_clause = " AND ".join(where_parts) if where_parts else ""
            
            # Build ORDER BY
            order_clause = "ORDER BY pr.period DESC"
            if 'latest' in question_lower or 'recent' in question_lower:
                limit_clause = "LIMIT 10"
            elif period_conditions and period_conditions[0]:  # Specific period, no limit needed
                limit_clause = ""
                order_clause = "ORDER BY p.parameter_name"
            else:
                limit_clause = "LIMIT 20"
            
            # Construct the query
            query = f"MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)"
            if where_clause:
                query += f" WHERE {where_clause}"
            query += f" RETURN DISTINCT c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth"
            
            # Add ORDER BY and LIMIT with proper spacing - don't strip leading space!
            if order_clause:
                query += f" {order_clause.strip()}"
            if limit_clause:
                query += f" {limit_clause.strip()}"
            
            return query.strip()
        
        # Company query fallback
        # Try to extract company name for better query
        companies = []
        if schema_context := self.get_dynamic_schema_context():
            companies = schema_context.get('companies', [])
            for company in companies[:30]:
                if any(word in question_lower for word in company.lower().split() if len(word) > 2):
                    company_word = company.split()[0]
                    return f"MATCH (c:Company) WHERE c.company_name CONTAINS '{company_word}' RETURN c.company_name, c.cid LIMIT 20"
        
        return "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 20"
    
    def generate_cypher_only(self, question: str) -> str:
        """
        Generate ONLY the Cypher query (Step 1 of proper GraphRAG flow)
        
        Args:
            question: Natural language question about companies
        
        Returns:
            Generated Cypher query string
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 1: Generating Cypher query for: "{question}"')
            
            # Always use Tool Calling approach (monolithic approach removed)
            complexity = self._assess_complexity(question)
            
            if complexity == "simple":
                # Use Tool Calling (current implementation)
                return self._generate_with_tools(question)
            else:
                # Use ReAct for complex queries (future implementation)
                if self.log_manager:
                    self.log_manager.add_info_log('Complex query detected - attempting ReAct (fallback to Tool Calling if not available)')
                
                # Initialize ReAct engine if not already done
                if self.react_engine is None and self.tool_registry:
                    try:
                        self.react_engine = ReActEngine(self.tool_registry, self.log_manager)
                    except:
                        pass
                
                # Use ReAct if available, otherwise fallback to Tool Calling
                if self.react_engine:
                    try:
                        return self.react_engine.generate_cypher(question)
                    except NotImplementedError:
                        if self.log_manager:
                            self.log_manager.add_info_log('ReAct not yet implemented, using Tool Calling')
                        return self._generate_with_tools(question)
                else:
                    return self._generate_with_tools(question)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Cypher generation failed: {str(e)}', e)
            raise
    
    def _generate_with_tools(self, question: str) -> str:
        """
        Generate Cypher query using Tool Calling approach
        
        Args:
            question: Natural language question
        
        Returns:
            Generated Cypher query string
        """
        try:
            if not self.llm_with_tools:
                if self.log_manager:
                    self.log_manager.add_error_log('Tool calling not initialized. Please check logs.')
                # Return a simple fallback query
                return "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
            
            if self.log_manager:
                self.log_manager.add_info_log('Using Tool Calling approach with Modular Prompt System')
            
            # MODULAR PROMPT SYSTEM: Analyze query and build focused prompt
            # This ensures we only load relevant instructions, keeping prompts small and efficient
            query_analyzer = QueryAnalyzer(log_manager=self.log_manager)
            query_analysis = query_analyzer.analyze(question)
            
            # Build prompt dynamically based on query needs
            prompt_builder = ModularPromptBuilder(log_manager=self.log_manager)
            system_message = prompt_builder.build_for_query_type(query_analysis)
            
            # Log prompt size for monitoring
            if self.log_manager:
                estimated_tokens = prompt_builder.estimate_token_count(system_message)
                self.log_manager.add_info_log(f'Modular Prompt: ~{estimated_tokens} tokens (composed dynamically)')
            
            # Initial message to LLM (LangChain format)
            # ✅ CORRECT: Use SystemMessage for system instructions, HumanMessage for user query
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=system_message),  # System-level instructions
                HumanMessage(content=f"Question: {question}")  # User query
            ]
            
            # Max iterations for tool calling
            max_iterations = 5
            iteration = 0
            
            while iteration < max_iterations:
                if self.log_manager:
                    self.log_manager.add_info_log(f'Tool Calling Iteration {iteration + 1}/{max_iterations}')
                
                # Call LLM with current messages
                response = self.llm_with_tools.invoke(messages)
                
                # Check if LLM wants to use tools
                # LangChain returns tool_calls in response.tool_calls
                tool_calls = getattr(response, 'tool_calls', None) or []
                if tool_calls:
                    if self.log_manager:
                        self.log_manager.add_info_log(f'[Iteration {iteration + 1}] LLM requested {len(tool_calls)} tool call(s)')
                    
                    # Add LLM response to conversation (response is already AIMessage with tool_calls)
                    messages.append(response)
                    
                    # Execute all requested tools
                    tool_messages = []
                    tools_executed_this_iteration = []  # Track tools executed to detect duplicates
                    for tool_call in tool_calls:
                        # Extract tool name and arguments from LangChain tool_call object
                        if hasattr(tool_call, 'name'):
                            tool_name = tool_call.name
                        else:
                            tool_name = tool_call.get('name', '')
                        
                        # Extract arguments - LangChain tool_call has 'args' attribute
                        if hasattr(tool_call, 'args'):
                            tool_args = tool_call.args if tool_call.args else {}
                        elif isinstance(tool_call, dict):
                            tool_args = tool_call.get('args', tool_call.get('arguments', {}))
                            # If arguments is a string, parse it
                            if isinstance(tool_args, str):
                                try:
                                    tool_args = json.loads(tool_args)
                                except:
                                    tool_args = {}
                        else:
                            tool_args = {}
                        
                        # Get tool call ID for response
                        tool_call_id = getattr(tool_call, 'id', None) or (tool_call.get('id', '') if isinstance(tool_call, dict) else '')
                        
                        # Check for duplicate tool call in same iteration
                        tool_signature = f"{tool_name}_{str(tool_args)}"
                        if tool_signature in tools_executed_this_iteration:
                            if self.log_manager:
                                self.log_manager.add_error_log(f'[Iteration {iteration + 1}] DUPLICATE tool call detected: {tool_name} with same args. Skipping duplicate execution.')
                            # Still log it but skip execution
                            from langchain_core.messages import ToolMessage
                            # Compact error message for duplicate
                            error_content = json.dumps({
                                "error": "Duplicate tool call skipped",
                                "original_result": tools_executed_this_iteration[tool_signature]
                            }, separators=(',', ':'))
                            tool_message = ToolMessage(
                                content=error_content,
                                tool_call_id=tool_call_id
                            )
                            tool_messages.append(tool_message)
                            continue
                        
                        try:
                            import time
                            start_time = time.time()
                            
                            if self.log_manager:
                                self.log_manager.add_info_log(f'[Iteration {iteration + 1}] Executing tool: {tool_name} with args: {tool_args}')
                            
                            # Execute tool via registry
                            tool_result = self.tool_registry.execute_tool(tool_name, **tool_args)
                            
                            # Store in executed tools to prevent duplicates
                            tools_executed_this_iteration[tool_signature] = tool_result
                            
                            # Calculate duration
                            duration_ms = int((time.time() - start_time) * 1000)
                            
                            # Log tool call details with iteration info
                            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                                # Format response for display (truncate if too long)
                                response_str = json.dumps(tool_result, indent=2)
                                if len(response_str) > 500:
                                    response_str = response_str[:500] + "\n... (truncated)"
                                self.log_manager.add_tool_call_log(
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    response=tool_result,
                                    duration_ms=duration_ms,
                                    iteration=iteration + 1
                                )
                            
                            # Format result for LLM (LangChain format)
                            # ✅ OPTIMIZED: Use compact JSON to reduce token usage (~30% reduction)
                            from langchain_core.messages import ToolMessage
                            
                            # Format tool result compactly
                            if isinstance(tool_result, (dict, list)):
                                # Compact JSON (no indentation, minimal whitespace)
                                content = json.dumps(tool_result, separators=(',', ':'))
                                # Truncate if too long (prevent token bloat)
                                if len(content) > 2000:
                                    content = content[:2000] + '..." (truncated)'
                            else:
                                content = str(tool_result)
                            
                            tool_message = ToolMessage(
                                content=content,
                                tool_call_id=tool_call_id
                            )
                            tool_messages.append(tool_message)
                            
                        except Exception as e:
                            # ✅ IMPROVED: Categorize errors for better LLM understanding
                            error_type = type(e).__name__
                            error_msg = str(e)
                            
                            if self.log_manager:
                                self.log_manager.add_error_log(f'Error executing tool {tool_name} ({error_type}): {error_msg}', e)
                            
                            from langchain_core.messages import ToolMessage
                            # Compact error message with type information
                            error_content = json.dumps({
                                "error": error_msg,
                                "type": error_type
                            }, separators=(',', ':'))
                            
                            tool_message = ToolMessage(
                                content=error_content,
                                tool_call_id=tool_call_id
                            )
                            tool_messages.append(tool_message)
                    
                    # Add tool results to conversation
                    messages.extend(tool_messages)
                    iteration += 1
                    continue
                
                # ✅ IMPROVED: No more tool calls - validate and extract final answer
                from langchain_core.messages import AIMessage
                
                # Validate response is AIMessage
                if not isinstance(response, AIMessage):
                    if self.log_manager:
                        self.log_manager.add_info_log(f'[WARNING] Unexpected response type: {type(response)}')
                    break
                
                # Check if response has content (not just tool calls)
                if hasattr(response, 'content') and response.content:
                    final_content = response.content
                    cypher_query = self._extract_cypher_query(final_content)
                    
                    if self._is_valid_cypher(cypher_query):
                        if self.log_manager:
                            self.log_manager.add_info_log(f'Tool Calling generated valid Cypher query')
                            self.log_manager.add_info_log(f'Generated Cypher Query:\n{cypher_query}')
                        return cypher_query
                    else:
                        if self.log_manager:
                            self.log_manager.add_info_log(f'Extracted query invalid, trying alternative extraction')
                        break
                else:
                    # No content and no tool calls - unexpected state
                    if self.log_manager:
                        self.log_manager.add_info_log('[WARNING] Response has no content and no tool calls')
                    break
            
            # If we get here, tool calling didn't produce valid query
            if self.log_manager:
                self.log_manager.add_info_log('Tool calling did not produce valid query, using smart fallback')
            
            # Try to generate a smart fallback query based on the question
            fallback_query = self._generate_smart_fallback_query(question)
            if fallback_query:
                if self.log_manager:
                    self.log_manager.add_info_log(f'Using smart fallback query: {fallback_query}')
                return fallback_query
            
            # Final fallback - generic query
            return "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Tool calling generation failed: {str(e)}', e)
            
            # Try smart fallback even in exception case
            try:
                fallback_query = self._generate_smart_fallback_query(question)
                if fallback_query:
                    return fallback_query
            except:
                pass
            
            # Final fallback - generic query
            return "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
    
    def execute_cypher_query(self, cypher_query: str) -> list:
        """
        Execute Cypher query against Neo4j (Step 2 of proper GraphRAG flow)
        
        Args:
            cypher_query: Cypher query to execute
        
        Returns:
            List of results from Neo4j
        """
        try:
            # Validate the query before executing
            if not self._is_valid_cypher(cypher_query):
                error_msg = f"Invalid Cypher query detected: {cypher_query[:200]}"
                if self.log_manager:
                    self.log_manager.add_error_log(error_msg)
                raise ValueError(error_msg)
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 2: Executing Cypher query against Neo4j')
                self.log_manager.add_info_log(f'Cypher Query: {cypher_query}')
            else:
                # Fallback: print to console if no log_manager
                print(f'\n[GraphRAG] Executing Cypher Query:')
                print(f'🔍 {cypher_query}\n')
            
            # Execute the query
            results = graph.query(cypher_query)
            
            # Post-query validation: Check what was actually returned
            params_in_results = set()
            periods_in_results = set()
            companies_in_results = set()
            
            if results:
                # Extract unique parameters and periods from results
                for result in results:
                    if isinstance(result, dict):
                        param = result.get('p.parameter_name', result.get('parameter_name'))
                        period = result.get('pr.period', result.get('period'))
                        company = result.get('c.company_name', result.get('company_name'))
                        
                        if param:
                            params_in_results.add(str(param))
                        if period:
                            periods_in_results.add(str(period))
                        if company:
                            companies_in_results.add(str(company))
            
            if self.log_manager:
                self.log_manager.add_info_log(f'✅ Query executed successfully, returned {len(results)} results')
                if results:
                    # Log sample of results structure
                    sample_keys = list(results[0].keys()) if results else []
                    self.log_manager.add_info_log(f'📊 Result columns: {", ".join(sample_keys)}')
                    
                    # Log what parameters and periods were found
                    if params_in_results:
                        self.log_manager.add_info_log(f'📈 Parameters found: {", ".join(list(params_in_results)[:5])}')
                    if periods_in_results:
                        self.log_manager.add_info_log(f'📅 Periods found: {", ".join(sorted(list(periods_in_results))[:5])}')
                    
                    # Log a sample result for debugging
                    if len(results) > 0:
                        sample_result = {k: str(v)[:50] if len(str(v)) > 50 else v for k, v in results[0].items()}
                        self.log_manager.add_info_log(f'📋 Sample result: {sample_result}')
                else:
                    self.log_manager.add_info_log('⚠️ No results returned from query')
            else:
                # Fallback: print to console if no log_manager
                print(f'✅ Query executed successfully, returned {len(results)} results')
                if results:
                    sample_keys = list(results[0].keys()) if results else []
                    print(f'📊 Result columns: {", ".join(sample_keys)}')
                else:
                    print('⚠️ No results returned from query')
            
            return results
            
        except Exception as e:
            error_msg = str(e)
            if self.log_manager:
                self.log_manager.add_error_log(f'Cypher execution failed: {error_msg}', e)
            
            # Return empty list instead of raising - let synthesis handle the empty case
            # This prevents cascading failures
            if self.log_manager:
                self.log_manager.add_info_log('Returning empty results due to execution error')
            return []
    
    def retrieve_relevant_chunks(self, question: str, structured_results: list) -> str:
        """
        Retrieve relevant text chunks based on structured results (Step 3 of proper GraphRAG flow)
        
        Args:
            question: Original question
            structured_results: Results from Cypher query
        
        Returns:
            Combined text chunks
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 3: Retrieving relevant text chunks')
            
            # Extract company names from structured results
            company_names = []
            for result in structured_results:
                if isinstance(result, dict):
                    for key, value in result.items():
                        if 'company_name' in key.lower() and value:
                            company_names.append(str(value))
            
            # If we have company names, get their chunks
            chunks_text = ""
            if company_names:
                # Get chunks for the first few companies
                for company_name in company_names[:5]:  # Limit to 5 companies
                    try:
                        chunk_query = f"""
                        MATCH (c:Company {{company_name: '{company_name}'}})-[:HAS_Chunk_INFO]->(chunk)
                        RETURN chunk.text LIMIT 3
                        """
                        chunk_results = graph.query(chunk_query)
                        for chunk_result in chunk_results:
                            if isinstance(chunk_result, dict) and 'chunk.text' in chunk_result:
                                chunks_text += f"\n{chunk_result['chunk.text']}\n"
                    except Exception as e:
                        if self.log_manager:
                            self.log_manager.add_info_log(f'Could not retrieve chunks for {company_name}: {str(e)}')
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Retrieved {len(chunks_text)} characters of chunk text')
            
            return chunks_text
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Chunk retrieval failed: {str(e)}', e)
            return ""
    
    def _format_value(self, value, currency=None, is_percentage=False):
        """Format numeric values professionally"""
        if value is None or value == 'N/A':
            return 'N/A'
        
        if isinstance(value, (int, float)):
            if is_percentage:
                return f"{value:.2f}%"
            
            # Format large numbers with commas
            if abs(value) >= 1000000:
                return f"{value:,.2f}"
            elif abs(value) >= 1000:
                return f"{value:,.2f}"
            else:
                return f"{value:.2f}"
        
        return str(value)
    
    def _format_market_cap(self, value):
        """Format market cap with appropriate units"""
        if value is None or value == 'N/A' or not isinstance(value, (int, float)):
            return 'N/A'
        
        if abs(value) >= 1_000_000_000_000:  # Trillions
            return f"${value/1_000_000_000_000:.2f}T"
        elif abs(value) >= 1_000_000_000:  # Billions
            return f"${value/1_000_000_000:.2f}B"
        elif abs(value) >= 1_000_000:  # Millions
            return f"${value/1_000_000:.2f}M"
        else:
            return f"${value:,.2f}"
    
    def synthesize_answer(self, question: str, structured_results: list, chunks_text: str) -> str:
        """
        Format structured data ONLY - no LLM hallucinations.
        Only shows actual database results. Returns empty string if no data.
        
        Args:
            question: Original question
            structured_results: Results from Cypher query
            chunks_text: Retrieved text chunks (not used - only structured data shown)
        
        Returns:
            Formatted answer with ONLY database data, or empty string if no data
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 4: Formatting results (NO LLM - data only)')
            
            # CRITICAL: If no results, return informative message - no hallucinations
            if not structured_results or len(structured_results) == 0:
                if self.log_manager:
                    self.log_manager.add_info_log('No data found - returning informative empty response (no hallucinations)')
                # Return informative message instead of empty string
                return "No data found in database for this query.\n\n**Query:** " + question + "\n\n*Only actual database results are shown - no fabricated data.*"
            
            # Detect query type based on result structure
            is_company_details_query = False
            is_parameter_query = False
            
            if structured_results and len(structured_results) > 0:
                first_result = structured_results[0]
                if isinstance(first_result, dict):
                    # Check if this is a company details query (has country, sector, industry, etc.)
                    has_company_fields = any(key in first_result for key in ['country', 'sector', 'industry', 'country_code', 's.name', 'i.name'])
                    has_parameter_fields = any(key in first_result for key in ['p.parameter_name', 'parameter_name', 'pr.period', 'pr.value'])
                    
                    is_company_details_query = has_company_fields and not has_parameter_fields
                    is_parameter_query = has_parameter_fields
            
            # Format structured results in a clear, readable format
            structured_data = ""
            if structured_results:
                if is_company_details_query:
                    # Handle company details query results
                    if self.log_manager:
                        self.log_manager.add_info_log('Detected company details query - formatting company information')
                    
                    companies_info = []
                    for result in structured_results:
                        if isinstance(result, dict):
                            company_name = result.get('c.company_name', result.get('company_name', 'Unknown'))
                            cid = result.get('c.cid', result.get('cid', 'N/A'))
                            country = result.get('country', result.get('country.name', 'N/A'))
                            country_code = result.get('country_code', result.get('country.code', result.get('country_code', 'N/A')))
                            sector = result.get('sector', result.get('s.name', 'N/A'))
                            industry = result.get('industry', result.get('i.name', 'N/A'))
                            market_cap = result.get('c.market_cap', result.get('market_cap', 'N/A'))
                            description = result.get('c.description', result.get('description', 'N/A'))
                            
                            company_info = {
                                'company_name': company_name,
                                'cid': cid,
                                'country': country,
                                'country_code': country_code,
                                'sector': sector,
                                'industry': industry,
                                'market_cap': market_cap,
                                'description': description
                            }
                            companies_info.append(company_info)
                    
                    # Professional company details formatting
                    structured_data = f"## Company Information\n\n"
                    
                    for idx, company in enumerate(companies_info, 1):
                        structured_data += f"### {company['company_name']}\n\n"
                        
                        # Create a clean info table
                        info_rows = []
                        if company['cid'] and company['cid'] != 'N/A':
                            info_rows.append(("**Company ID**", str(company['cid'])))
                        if company['country'] and company['country'] != 'N/A':
                            country_display = f"{company['country']}"
                            if company['country_code'] and company['country_code'] != 'N/A':
                                country_display += f" ({company['country_code']})"
                            info_rows.append(("**Country**", country_display))
                        if company['sector'] and company['sector'] != 'N/A':
                            info_rows.append(("**Sector**", company['sector']))
                        if company['industry'] and company['industry'] != 'N/A':
                            info_rows.append(("**Industry**", company['industry']))
                        if company['market_cap'] != 'N/A' and company['market_cap']:
                            formatted_cap = self._format_market_cap(company['market_cap'])
                            info_rows.append(("**Market Cap**", formatted_cap))
                        
                    # Format as markdown table
                    if info_rows:
                        structured_data += "| Property | Value |\n"
                        structured_data += "|----------|-------|\n"
                        for prop, val in info_rows:
                            # Ensure values are properly formatted strings
                            val_str = str(val) if val and val != 'N/A' and val != 'None' else '-'
                            structured_data += f"| {prop} | {val_str} |\n"
                        structured_data += "\n"
                    else:
                        structured_data += "*No additional information available.*\n\n"
                    
                    # Add description if available
                    if company['description'] and company['description'] != 'N/A':
                        desc = str(company['description'])
                        if len(desc) > 300:
                            desc = desc[:300] + "..."
                        structured_data += f"**Description:**\n{desc}\n\n"
                    
                    # Add separator between multiple companies
                    if idx < len(companies_info):
                        structured_data += "---\n\n"
                
                elif is_parameter_query:
                    # Handle parameter query results with proper validation and edge case handling
                    params_found = {}
                    periods_found = set()
                    seen_combinations = {}  # Track seen period+value+currency combinations to deduplicate
                    company_names_found = {}  # Track all companies in results to get the most common one
                    
                    # First pass: Extract all data with proper validation
                    valid_results_count = 0
                    
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Processing {len(structured_results)} result(s) for parameter query formatting')
                        if structured_results:
                            sample_result = structured_results[0]
                            sample_keys = list(sample_result.keys()) if isinstance(sample_result, dict) else []
                            self.log_manager.add_info_log(f'Sample result keys: {sample_keys}')
                    
                    for result in structured_results:
                        if not isinstance(result, dict):
                            continue
                        
                        # Extract company name (try multiple field name variations)
                        company_name = (
                            result.get('c.company_name') or 
                            result.get('company_name') or 
                            None
                        )
                        if company_name and company_name != 'N/A' and company_name != 'Unknown':
                            company_names_found[company_name] = company_names_found.get(company_name, 0) + 1
                        
                        # Extract parameter name (try multiple field name variations)
                        param_name = (
                            result.get('p.parameter_name') or 
                            result.get('parameter_name') or
                            None
                        )
                        if not param_name or param_name == 'N/A' or param_name == 'Unknown':
                            if self.log_manager:
                                self.log_manager.add_info_log(f'Skipping result with missing/invalid parameter name: {result}')
                            continue
                        
                        # Extract period (try multiple field name variations)
                        period = (
                            result.get('pr.period') or 
                            result.get('period') or
                            None
                        )
                        if not period or period == 'N/A' or period == 'Unknown':
                            if self.log_manager:
                                self.log_manager.add_info_log(f'Skipping result with missing/invalid period: {result}')
                            continue
                        
                        # Extract value (try multiple field name variations)
                        value = (
                            result.get('pr.value') or 
                            result.get('value') or
                            None
                        )
                        if value is None or value == 'N/A':
                            if self.log_manager:
                                self.log_manager.add_info_log(f'Skipping result with missing/invalid value: {result}')
                            continue
                        
                        # Extract currency (try multiple field name variations, optional)
                        currency = (
                            result.get('pr.currency') or 
                            result.get('currency') or
                            'N/A'
                        )
                        
                        # Extract YoY growth (try multiple field name variations, optional)
                        yoy_growth = (
                            result.get('pr.yoy_growth') or 
                            result.get('yoy_growth') or
                            None
                        )
                        
                        # Create unique key that includes parameter name to keep similar parameters separate
                        # Use exact value (not rounded) to preserve distinct values even if close
                        if isinstance(value, (int, float)):
                            value_key = str(value)  # Keep exact value for uniqueness
                        else:
                            value_key = str(value)
                        
                        # Include parameter name in unique key so similar parameters are kept distinct
                        unique_key = f"{param_name}|{period}|{value_key}|{currency}"
                        
                        # Only add if we haven't seen this exact combination before
                        if unique_key not in seen_combinations:
                            seen_combinations[unique_key] = True
                            periods_found.add(period)
                            valid_results_count += 1
                            
                            if param_name not in params_found:
                                params_found[param_name] = []
                            
                            params_found[param_name].append({
                                'period': period,
                                'value': value,
                                'currency': currency,
                                'yoy_growth': yoy_growth
                            })
                    
                    # Get the most common company name (most reliable method)
                    if company_names_found:
                        # Sort by frequency and get the most common
                        company_name = max(company_names_found.items(), key=lambda x: x[1])[0]
                        if self.log_manager:
                            self.log_manager.add_info_log(f'Company name determined from {len(company_names_found)} occurrence(s): "{company_name}"')
                            self.log_manager.add_info_log(f'Company name frequencies: {company_names_found}')
                    else:
                        # Fallback: Try to get from first valid result
                        for result in structured_results:
                            if isinstance(result, dict):
                                company_name = (
                                    result.get('c.company_name') or 
                                    result.get('company_name') or 
                                    None
                                )
                                if company_name and company_name != 'N/A' and company_name != 'Unknown':
                                    break
                        
                        # Final fallback
                        if not company_name or company_name == 'N/A' or company_name == 'Unknown':
                            company_name = 'Unknown Company'
                    
                    # Calculate total deduplicated records
                    total_deduped_records = sum(len(records) for records in params_found.values())
                    
                    # Validate we have data to display
                    if not params_found or total_deduped_records == 0:
                        if self.log_manager:
                            self.log_manager.add_info_log(f'No valid parameter data found after processing. Valid results: {valid_results_count}, Params found: {len(params_found)}, Total deduped: {total_deduped_records}')
                        return ""  # Return empty - no hallucinations
                    
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Parameter query formatting: Company="{company_name}", Parameters={list(params_found.keys())}, Total records={total_deduped_records}')
                    
                    # Professional parameter query formatting with enhanced summary
                    structured_data = f"## Financial Data for {company_name}\n\n"
                    
                    # Summary section as a formatted list (will be styled as a card)
                    structured_data += f"**Summary:**\n"
                    structured_data += f"- **Company:** {company_name}\n"
                    structured_data += f"- **Parameters Found:** {len(params_found)}\n"
                    structured_data += f"- **Total Records:** {total_deduped_records} unique record{'s' if total_deduped_records != 1 else ''}\n"
                    if periods_found:
                        periods_sorted = sorted(periods_found)
                        periods_display = periods_sorted[:10]  # Limit to 10 for display
                        if len(periods_sorted) > 10:
                            periods_display_str = ', '.join(periods_display) + f' (and {len(periods_sorted) - 10} more)'
                        else:
                            periods_display_str = ', '.join(periods_display)
                        structured_data += f"- **Periods:** {periods_display_str}\n"
                    structured_data += "\n"
                    
                    # Format each parameter as a professional table
                    for param_name, records in params_found.items():
                        if not records or len(records) == 0:
                            continue  # Skip empty parameter groups
                        
                        structured_data += f"### {param_name}\n\n"
                        
                        # Sort records by period for chronological order (newest first)
                        # Handle edge case: period might not be sortable string, so use safe sorting
                        try:
                            sorted_records = sorted(records[:20], key=lambda x: str(x.get('period', '')), reverse=True)
                        except Exception:
                            sorted_records = records[:20]  # Fallback to unsorted if sorting fails
                        
                        # Validate we have records to display
                        if not sorted_records:
                            structured_data += "*No data available for this parameter.*\n\n"
                            continue
                        
                        # Create markdown table with EXACT 4 columns (CRITICAL for alignment)
                        # Column order MUST match data row order exactly
                        structured_data += "| Period | Value | Currency | YoY Growth |\n"
                        structured_data += "|:------|------:|:--------:|:----------:|\n"  # Center-align for readability
                        
                        for record in sorted_records:
                            # Extract and validate each field with proper fallbacks
                            period_str = str(record.get('period', 'N/A'))
                            if period_str == 'None' or period_str == '':
                                period_str = 'N/A'
                            
                            # Format value with validation (CRITICAL: Must be in correct column order)
                            value = record.get('value')
                            if value is None or value == 'N/A':
                                value_str = 'N/A'
                            else:
                                try:
                                    value_str = self._format_value(value, record.get('currency'))
                                except Exception as e:
                                    if self.log_manager:
                                        self.log_manager.add_info_log(f'Error formatting value {value}: {str(e)}')
                                    value_str = str(value) if value else 'N/A'
                            
                            # Format currency with validation (CRITICAL: Must be in correct column order)
                            currency = record.get('currency')
                            if currency is None or currency == 'N/A' or currency == 'None':
                                currency_str = '-'
                            else:
                                currency_str = str(currency).strip()
                            
                            # Format YoY growth with validation (CRITICAL: Must be in correct column order)
                            yoy_growth = record.get('yoy_growth')
                            if yoy_growth is None or yoy_growth == 'N/A' or yoy_growth == 'None':
                                growth_str = '-'
                            else:
                                try:
                                    # Convert to percentage format
                                    if isinstance(yoy_growth, (int, float)):
                                        growth_str = f"{yoy_growth:.2f}%"
                                    else:
                                        growth_str = str(yoy_growth)
                                    # Ensure it has % sign
                                    if not growth_str.endswith('%'):
                                        growth_str = growth_str + '%'
                                except Exception as e:
                                    if self.log_manager:
                                        self.log_manager.add_info_log(f'Error formatting YoY growth {yoy_growth}: {str(e)}')
                                    growth_str = str(yoy_growth) if yoy_growth else '-'
                            
                            # CRITICAL: Table row MUST match column header order exactly:
                            # | Period | Value | Currency | YoY Growth |
                            structured_data += f"| {period_str} | {value_str} | {currency_str} | {growth_str} |\n"
                            
                            # Log for debugging
                            if self.log_manager and len(sorted_records) <= 3:
                                self.log_manager.add_info_log(
                                    f'Table row: Period={period_str}, Value={value_str}, Currency={currency_str}, Growth={growth_str}'
                                )
                        
                        structured_data += "\n"
                    
                    # Footer note with accurate information
                    skipped_count = len(structured_results) - valid_results_count
                    duplicate_count = valid_results_count - total_deduped_records
                    
                    notes = []
                    if skipped_count > 0:
                        notes.append(f"{skipped_count} invalid record{'s' if skipped_count != 1 else ''} skipped")
                    if duplicate_count > 0:
                        notes.append(f"{duplicate_count} duplicate record{'s' if duplicate_count != 1 else ''} removed")
                    
                    if notes:
                        structured_data += f"*Note: {'; '.join(notes)}.*\n"
                else:
                    # Generic query - format all fields in a professional table
                    if self.log_manager:
                        self.log_manager.add_info_log('Unknown query type - formatting all fields')
                    
                    structured_data = f"## Query Results\n\n"
                    structured_data += f"Found **{len(structured_results)}** record(s)\n\n"
                    
                    if structured_results:
                        # Get all unique keys from all results
                        all_keys = set()
                        for result in structured_results[:10]:
                            if isinstance(result, dict):
                                all_keys.update(result.keys())
                        
                        # Create table header
                        if all_keys:
                            structured_data += "| " + " | ".join(all_keys) + " |\n"
                            structured_data += "|" + "|".join(["---" for _ in all_keys]) + "|\n"
                            
                            # Add rows
                            for result in structured_results[:10]:
                                if isinstance(result, dict):
                                    row_values = [str(result.get(key, '-')) for key in all_keys]
                                    structured_data += "| " + " | ".join(row_values) + " |\n"
                            structured_data += "\n"
            else:
                # No results - return empty string (no hallucinations)
                if self.log_manager:
                    self.log_manager.add_info_log('No structured data to format - returning empty response')
                return ""
            
            # CRITICAL: Return ONLY the formatted structured data - NO LLM CALL
            # This ensures zero hallucinations - only actual database data is shown
            if self.log_manager:
                self.log_manager.add_info_log(f'Returning formatted data ONLY (no LLM synthesis - prevents hallucinations)')
            
            # Validate that structured_data is not empty
            if not structured_data or not structured_data.strip():
                if self.log_manager:
                    self.log_manager.add_info_log('Formatted data is empty - returning empty response')
                return ""
            
            # Return the formatted structured data directly
            return structured_data.strip()
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Answer synthesis failed: {str(e)}', e)
            raise
    
    def generate_cypher_query(self, question: str) -> str:
        """
        Complete GraphRAG flow: Generate Cypher → Execute → Retrieve chunks → Synthesize answer
        
        Args:
            question: Natural language question about companies
        
        Returns:
            Final synthesized answer
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Starting complete GraphRAG flow for: "{question}"')
            
            # Step 1: Generate Cypher query
            if self.log_manager:
                self.log_manager.add_info_log('='*60)
                self.log_manager.add_info_log('STEP 1: Generating Cypher Query')
                self.log_manager.add_info_log('='*60)
            cypher_query = self.generate_cypher_only(question)
            
            # Step 2: Execute against Neo4j
            if self.log_manager:
                self.log_manager.add_info_log('='*60)
                self.log_manager.add_info_log('STEP 2: Executing Cypher Query')
                self.log_manager.add_info_log('='*60)
            structured_results = self.execute_cypher_query(cypher_query)
            
            # Step 3: Retrieve relevant chunks
            if self.log_manager:
                self.log_manager.add_info_log('='*60)
                self.log_manager.add_info_log('STEP 3: Retrieving Relevant Chunks')
                self.log_manager.add_info_log('='*60)
            chunks_text = self.retrieve_relevant_chunks(question, structured_results)
            
            # Step 4: Synthesize final answer
            if self.log_manager:
                self.log_manager.add_info_log('='*60)
                self.log_manager.add_info_log('STEP 4: Synthesizing Final Answer')
                self.log_manager.add_info_log('='*60)
            final_answer = self.synthesize_answer(question, structured_results, chunks_text)
            
            # Store in history
            import time
            history_entry = {
                'timestamp': time.strftime("%H:%M:%S"),
                'question': question,
                'cypher_query': cypher_query,
                'raw_results': structured_results,  # Store the actual records returned
                'result': final_answer
            }
            self.cypher_history.append(history_entry)
            
            # Keep only last 20 entries
            if len(self.cypher_history) > 20:
                self.cypher_history.pop(0)
            
            if self.log_manager:
                self.log_manager.add_info_log(f'GraphRAG flow completed successfully')
            
            # CRITICAL: Do NOT use textwrap.fill() as it breaks markdown table formatting
            # Return the final answer as-is to preserve markdown structure
            return final_answer
            
        except Exception as e:
            error_msg = str(e)
            if self.log_manager:
                self.log_manager.add_error_log(f'GraphRAG flow failed: {error_msg}', e)
            
            # Provide user-friendly error message instead of raising
            # This prevents the Flask app from returning 500 errors
            return f"**Error processing query:**\n\n{error_msg}\n\n**Query:** {question}\n\n*Please check the query format and try again.*"
    
    def get_cypher_history(self):
        """Get the history of generated Cypher queries"""
        return self.cypher_history
    
    def clear_cypher_history(self):
        """Clear the Cypher query history"""
        self.cypher_history = []
    
    def enable_tool_calling(self):
        """Enable tool calling (can be called at runtime)"""
        if not self.use_tool_calling:
            self.use_tool_calling = True
            self._initialize_tool_calling()
            if self.log_manager:
                self.log_manager.add_info_log('Tool calling enabled')
    
    def disable_tool_calling(self):
        """Disable tool calling (not supported - tool calling is now the only method)"""
        if self.log_manager:
            self.log_manager.add_info_log('Warning: Tool calling cannot be disabled - it is the only supported method')


# Update the original GraphRAG import to use PEERS version
GraphRAG = PEERSGraphRAG

