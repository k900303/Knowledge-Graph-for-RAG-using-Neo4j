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
        """Check if the question is asking about parameters"""
        question_lower = question.lower()
        parameter_indicators = [
            'revenue', 'margin', 'profit', 'ebitda', 'ebit', 'net income', 
            'parameter', 'earnings', 'sales', 'cost', 'expense', 'ratio',
            'growth', 'yoy', 'qoq', 'percentage', 'metric', 'financial',
            'production', 'volume', 'capacity', 'quantity', 'units', 'output',
            'receivable', 'payable', 'accounts', 'asset', 'liability', 'equity'
        ]
        return any(indicator in question_lower for indicator in parameter_indicators)
    
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
    
    def _generate_fallback_query(self, question: str) -> str:
        """Generate a smart fallback Cypher query when LLM fails"""
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
                self.log_manager.add_info_log('Using Tool Calling approach')
            
            # Initial message to LLM (LangChain format)
            # Include instruction to generate Cypher query after using tools
            from langchain_core.messages import HumanMessage
            
            system_message = """You are a Cypher query expert. Use the available tools to search for companies and parameters, then generate a valid Cypher query.

Process:
1. Use search_company to find the exact company name
2. Use search_parameters to find exact parameter names
3. Use generate_parameter_query or generate_company_details_query to generate the final Cypher query
4. Your final response should contain ONLY a valid Cypher query, no explanations

Generate Cypher queries that:
- Match the exact company and parameter names from tool results
- Include proper relationship patterns ([:HAS_PARAMETER], [:IN_COUNTRY], etc.)
- Return relevant fields (company_name, parameter_name, period, value, currency, etc.)
- Handle period filtering (latest, specific quarters, FY periods)

Example final response format:
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS 'Exact Company Name' AND p.parameter_name CONTAINS 'Exact Parameter Name'
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency
"""
            
            messages = [
                HumanMessage(content=system_message),
                HumanMessage(content=f"Question: {question}")
            ]
            
            # Max iterations for tool calling
            max_iterations = 5
            iteration = 0
            
            while iteration < max_iterations:
                # Call LLM with current messages
                response = self.llm_with_tools.invoke(messages)
                
                # Check if LLM wants to use tools
                # LangChain returns tool_calls in response.tool_calls
                tool_calls = getattr(response, 'tool_calls', None) or []
                if tool_calls:
                    if self.log_manager:
                        self.log_manager.add_info_log(f'LLM requested {len(tool_calls)} tool calls')
                    
                    # Add LLM response to conversation (response is already AIMessage with tool_calls)
                    messages.append(response)
                    
                    # Execute all requested tools
                    tool_messages = []
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
                        
                        try:
                            import time
                            start_time = time.time()
                            
                            if self.log_manager:
                                self.log_manager.add_info_log(f'Executing tool: {tool_name} with args: {tool_args}')
                            
                            # Execute tool via registry
                            tool_result = self.tool_registry.execute_tool(tool_name, **tool_args)
                            
                            # Calculate duration
                            duration_ms = int((time.time() - start_time) * 1000)
                            
                            # Log tool call details
                            if self.log_manager and hasattr(self.log_manager, 'add_tool_call_log'):
                                # Format response for display (truncate if too long)
                                response_str = json.dumps(tool_result, indent=2)
                                if len(response_str) > 500:
                                    response_str = response_str[:500] + "\n... (truncated)"
                                self.log_manager.add_tool_call_log(
                                    tool_name=tool_name,
                                    arguments=tool_args,
                                    response=tool_result,
                                    duration_ms=duration_ms
                                )
                            
                            # Format result for LLM (LangChain format)
                            from langchain_core.messages import ToolMessage
                            
                            tool_message = ToolMessage(
                                content=json.dumps(tool_result, indent=2),
                                tool_call_id=tool_call_id
                            )
                            tool_messages.append(tool_message)
                            
                        except Exception as e:
                            if self.log_manager:
                                self.log_manager.add_error_log(f'Error executing tool {tool_name}: {str(e)}', e)
                            
                            from langchain_core.messages import ToolMessage
                            tool_message = ToolMessage(
                                content=json.dumps({"error": str(e)}),
                                tool_call_id=tool_call_id
                            )
                            tool_messages.append(tool_message)
                    
                    # Add tool results to conversation
                    messages.extend(tool_messages)
                    iteration += 1
                    continue
                
                # No more tool calls - extract final answer
                final_content = response.content if hasattr(response, 'content') else str(response)
                cypher_query = self._extract_cypher_query(final_content)
                
                if self._is_valid_cypher(cypher_query):
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Tool Calling generated valid Cypher query')
                        self.log_manager.add_info_log(f'Generated Cypher Query:\n{cypher_query}')
                    return cypher_query
                else:
                    # If extraction failed, try to get it from messages
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Extracted query invalid, trying alternative extraction')
                    break
            
            # If we get here, tool calling didn't produce valid query
            if self.log_manager:
                self.log_manager.add_error_log('Tool calling did not produce valid query. Please check logs.')
            # Return a simple fallback query
            return "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Tool calling generation failed: {str(e)}', e)
            # Return a simple fallback query
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
                self.log_manager.add_info_log(f'🔍 Cypher Query: {cypher_query}')
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
            if self.log_manager:
                self.log_manager.add_error_log(f'Cypher execution failed: {str(e)}', e)
            raise
    
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
    
    def synthesize_answer(self, question: str, structured_results: list, chunks_text: str) -> str:
        """
        Combine structured data and chunks with LLM to generate final answer (Step 4 of proper GraphRAG flow)
        
        Args:
            question: Original question
            structured_results: Results from Cypher query
            chunks_text: Retrieved text chunks
        
        Returns:
            Final synthesized answer
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 4: Synthesizing final answer with LLM')
            
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
                    
                    structured_data = f"Found {len(companies_info)} company record(s):\n\n"
                    for company in companies_info:
                        structured_data += f"Company: {company['company_name']}\n"
                        structured_data += f"  Company ID: {company['cid']}\n"
                        structured_data += f"  Country: {company['country']} ({company['country_code']})\n"
                        structured_data += f"  Sector: {company['sector']}\n"
                        structured_data += f"  Industry: {company['industry']}\n"
                        if company['market_cap'] != 'N/A' and company['market_cap']:
                            formatted_cap = f"{company['market_cap']:,.0f}" if isinstance(company['market_cap'], (int, float)) else str(company['market_cap'])
                            structured_data += f"  Market Cap: {formatted_cap}\n"
                        if company['description'] and company['description'] != 'N/A':
                            desc = str(company['description'])[:200] + "..." if len(str(company['description'])) > 200 else str(company['description'])
                            structured_data += f"  Description: {desc}\n"
                        structured_data += "\n"
                
                elif is_parameter_query:
                    # Handle parameter query results (original logic)
                    # Group results by parameter and deduplicate by period-value-currency combination
                    params_found = {}
                    periods_found = set()
                    seen_combinations = {}  # Track seen period+value+currency combinations to deduplicate
                    
                    for result in structured_results:
                        if isinstance(result, dict):
                            param_name = result.get('p.parameter_name', result.get('parameter_name', 'Unknown'))
                            period = result.get('pr.period', result.get('period', 'Unknown'))
                            value = result.get('pr.value', result.get('value', 'N/A'))
                            currency = result.get('pr.currency', result.get('currency', 'N/A'))
                            yoy_growth = result.get('pr.yoy_growth', result.get('yoy_growth', 'N/A'))
                            
                            # Create unique key that includes parameter name to keep similar parameters separate
                            # Use exact value (not rounded) to preserve distinct values even if close
                            # This ensures "Accounts receivable" and "Accounts receivable, Average" are shown separately
                            if isinstance(value, (int, float)):
                                value_key = str(value)  # Keep exact value for uniqueness
                            else:
                                value_key = str(value)
                            
                            # Include parameter name in unique key so similar parameters are kept distinct
                            unique_key = f"{param_name}|{period}|{value_key}|{currency}"
                            
                            # Only add if we haven't seen this exact combination before
                            # Different parameter names with same period+value will be shown separately
                            if unique_key not in seen_combinations:
                                seen_combinations[unique_key] = True
                                periods_found.add(period)
                                
                                if param_name not in params_found:
                                    params_found[param_name] = []
                                
                                params_found[param_name].append({
                                    'period': period,
                                    'value': value,
                                    'currency': currency,
                                    'yoy_growth': yoy_growth
                                })
                    
                    # Calculate total deduplicated records
                    total_deduped_records = sum(len(records) for records in params_found.values())
                    
                    # Format as readable data
                    structured_data = f"Found {total_deduped_records} unique data records (after deduplication):\n\n"
                    company_name = structured_results[0].get('c.company_name', structured_results[0].get('company_name', 'Unknown'))
                    structured_data += f"Company: {company_name}\n"
                    structured_data += f"Periods in data: {', '.join(sorted(periods_found))}\n\n"
                    
                    # Check if we have multiple similar parameter names (e.g., "Accounts receivable" and "Accounts receivable, Average")
                    has_similar_params = len(params_found) > 1
                    similar_param_base = None
                    if has_similar_params:
                        # Check if parameters share a common base name
                        param_names = list(params_found.keys())
                        first_base = param_names[0].split(',')[0].strip()
                        if all(p.split(',')[0].strip() == first_base for p in param_names):
                            similar_param_base = first_base
                            has_similar_params = True
                    
                    # Group records by parameter for better table structure
                    for param_name, records in params_found.items():
                        structured_data += f"\nParameter: {param_name} ({len(records)} unique records)\n"
                        # Sort records by period for chronological order
                        sorted_records = sorted(records[:20], key=lambda x: x['period'])  # Limit to 20 per parameter, sorted
                        for record in sorted_records:
                            # Format value with proper decimal places
                            value = record['value']
                            if isinstance(value, (int, float)):
                                if abs(value) >= 1000000:
                                    formatted_value = f"{value:,.2f}"
                                else:
                                    formatted_value = f"{value:.2f}"
                            else:
                                formatted_value = str(value)
                            
                            structured_data += f"  - Period: {record['period']}, Value: {formatted_value}, Currency: {record['currency']}"
                            if record['yoy_growth'] != 'N/A' and record['yoy_growth'] is not None:
                                growth_value = record['yoy_growth']
                                if isinstance(growth_value, (int, float)):
                                    structured_data += f", YoY Growth: {growth_value:.2f}%"
                                else:
                                    structured_data += f", YoY Growth: {growth_value}%"
                            structured_data += "\n"
                    
                    structured_data += f"\nTotal: {len(structured_results)} records found across {len(params_found)} parameters.\n"
                else:
                    # Generic query - format all fields
                    if self.log_manager:
                        self.log_manager.add_info_log('Unknown query type - formatting all fields')
                    structured_data = f"Found {len(structured_results)} record(s):\n\n"
                    for i, result in enumerate(structured_results[:10], 1):
                        structured_data += f"Record {i}:\n"
                        for key, value in result.items():
                            structured_data += f"  {key}: {value}\n"
                        structured_data += "\n"
            else:
                structured_data = "No structured data records found."
            
            # Create synthesis prompt
            # Check if we actually have results
            has_results = len(structured_results) > 0 and structured_data.strip() != ""
            
            # Enhanced prompt based on whether we have results
            if len(structured_results) > 0:
                results_indicator = f"⚠️ CRITICAL: {len(structured_results)} DATA RECORDS FOUND - YOU MUST PRESENT THIS DATA"
            else:
                results_indicator = "No data records found in database."
            
            # Create synthesis prompt based on query type
            if is_company_details_query:
                synthesis_prompt = f"""
Based ONLY on the structured data provided below, answer the user's question about company details.

Question: {question}

{results_indicator}

Structured Data:
{structured_data if structured_data.strip() else "No structured data records found."}

CRITICAL RULES - FOLLOW EXACTLY:
1. If you see "Found X company record(s)" above, DATA EXISTS - present it immediately
2. NEVER say "No data found", "no information", "no specific data" if structured data shows company records
3. Format the answer as a clear, readable company information summary
4. Use the EXACT company name from the data - do not modify or abbreviate it
5. Present company details in this format:

## Company Details: [Company Name]

**Basic Information:**
- Company ID: [cid]
- Country: [country] ([country_code])
- Sector: [sector]
- Industry: [industry]
- Market Cap: [market_cap] (if available)

**Description:**
[description if available]

6. If multiple companies match, create separate sections for each
7. Use the EXACT values from structured data - do not make up information
8. If market cap is available, format it with commas (e.g., 1,234,567,890)
9. If description is too long, summarize it but keep key information

Example format:
## Company Details: Kajaria Ceramics

**Basic Information:**
- Company ID: 18315
- Country: India (IN)
- Sector: Materials
- Industry: Building Products
- Market Cap: 45,678,900,000

**Description:**
Kajaria Ceramics is a leading manufacturer of ceramic tiles...

Answer (provide complete company details from the data):"""
            else:
                synthesis_prompt = f"""
Based ONLY on the structured data provided below, answer the user's question.

Question: {question}

{results_indicator}

Structured Data:
{structured_data if structured_data.strip() else "No structured data records found."}

CRITICAL RULES - FOLLOW EXACTLY:
1. If you see "{len(structured_results)} records found" or "Found X data records" above, DATA EXISTS - present it immediately
2. NEVER say "No data found", "no information", "no specific data", "Unfortunately there is no data" if structured data shows records
3. Format the answer as a structured table using markdown format with pipe delimiters
4. If multiple records exist, group by parameter and show each period's data in a row
5. Round currency values to 2 decimal places for readability
6. Use this EXACT format for parameter queries:

## [Parameter Name] for [Company Name] in [Period/Range]

| Period | Value | Currency | YoY Growth |
|--------|-------|----------|------------|
| [period1] | [value1] | [currency1] | [growth1]% |
| [period2] | [value2] | [currency2] | [growth2]% |

If multiple similar parameter names exist (e.g., "Accounts receivable" and "Accounts receivable, Average"), use this format instead:

| Parameter Name | Period | Value | Currency | YoY Growth |
|---------------|--------|-------|----------|------------|
| Accounts receivable | [period1] | [value1] | [currency1] | [growth1]% |
| Accounts receivable, Average | [period1] | [value2] | [currency2] | [growth2]% |

IMPORTANT: Always include "Period" as a column. If multiple similar parameter names exist, include "Parameter Name" as the FIRST column. Each row must have data in ALL columns matching the header structure. Ensure data alignment: Period column should ONLY contain periods (like "2QFY-2025"), Value column should ONLY contain numeric values, Currency column should ONLY contain currency codes (like "INR"), and YoY Growth should ONLY contain percentages.

7. If multiple parameters are requested or similar parameter names exist (e.g., "Accounts receivable" and "Accounts receivable, Average"), create separate rows or separate tables showing BOTH parameter names and their distinct values
8. Sort periods chronologically when possible
9. Use actual numbers from the structured data - do not generalize
10. If {len(structured_results)} records are shown above, create tables with ALL that data
11. IMPORTANT: Do NOT combine or deduplicate similar parameter names - if "Accounts receivable" and "Accounts receivable, Average" both exist, show them as separate rows with their respective values
12. Use the EXACT company name from the data - do not use "Unknown" or make up names

Example format:
## Accounts receivable for Kajaria Ceramics for FY-2025

| Period | Value | Currency | YoY Growth |
|--------|-------|----------|------------|
| 1HFY-2025 | 6,461,000,000.00 | INR | 16.12% |
| 2QFY-2025 | 6,461,000,000.00 | INR | 0.00% |
| FY-2025 | 5,701,800,000.00 | INR | -7.95% |

Answer (create markdown table format if data exists, otherwise say data not found):"""
            
            llm = ChatOpenAI(temperature=0)
            response = llm.invoke(synthesis_prompt)
            
            final_answer = response.content.strip()
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Final answer synthesized successfully, length: {len(final_answer)}')
            
            return final_answer
            
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
            
            return textwrap.fill(final_answer, 60)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'GraphRAG flow failed: {str(e)}', e)
            raise
    
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

