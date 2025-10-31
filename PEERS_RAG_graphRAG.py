"""
GraphRAG Module for PEERS RAG System
Generates Cypher queries for company knowledge graph
"""

from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_core.callbacks import BaseCallbackHandler
from neo4j_env import graph
from PEERS_RAG_tools import ToolRegistry
from PEERS_RAG_react import ReActEngine, BaseReasoningEngine
import textwrap
import traceback
import inspect
import io
import sys
import re
import json


retrieval_qa_chat_prompt = """
Task: Generate Cypher statement to query a graph database about companies and their relationships.

Instructions:
Use only the provided relationship types and properties in the schema. Do not use any other relationship types or properties that are not provided.

Remember the relationships are like this Schema:
{schema}

Graph Structure:
- Companies are connected to Countries via [:IN_COUNTRY]
- Companies are connected to Regions via [:IN_REGION]
- Companies are connected to Sectors via [:IN_SECTOR]
- Companies are connected to Industries via [:IN_INDUSTRY]
- Companies are connected to Exchanges via [:LISTED_ON]
- Companies have detailed chunks connected via [:HAS_Chunk_INFO]

Note: Do not include any explanations or apologies in your responses.
Do not include any text except the generated Cypher statement.

Example 1: Which companies are in the Technology sector?
MATCH (c:Company)-[:IN_SECTOR]->(s:Sector {name: 'Technology'})
RETURN c.company_name, c.cid, c.market_cap, c.base_currency

Example 2: Show me companies listed on NASDAQ with market cap over 1 billion USD
MATCH (c:Company)-[:LISTED_ON]->(e:Exchange)
WHERE e.code CONTAINS 'NASDAQ' AND c.market_cap > 1000000000 AND c.base_currency = 'USD'
RETURN c.company_name, c.cid, c.market_cap, c.exchange_symbol

Example 3: Find companies in the United States in the Healthcare sector
MATCH (c:Company)-[:IN_COUNTRY]->(country:Country {code: 'US'})
MATCH (c)-[:IN_SECTOR]->(s:Sector {name: 'Health Care'})
RETURN c.company_name, c.cid, s.name, country.name

Example 4: Show me companies in Asia with positive one week change
MATCH (c:Company)-[:IN_REGION]->(r:Region {name: 'Asia'})
WHERE c.one_week_change > 0
RETURN c.company_name, c.cid, c.one_week_change, c.this_month_change
ORDER BY c.one_week_change DESC

Example 5: List all pharmaceutical companies with their industry details
MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry)
WHERE i.name CONTAINS 'Pharmaceutical'
RETURN c.company_name, c.cid, i.name, i.id, c.market_cap

The question is:
{question}
"""


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
    
    def __init__(self, log_manager=None, use_tool_calling=False):
        self.log_manager = log_manager
        self.cypher_history = []  # Store generated Cypher queries
        self.schema_cache = None  # Cache for schema data
        self.cache_timestamp = None
        
        # Tool Calling support
        self.use_tool_calling = use_tool_calling
        self.tool_registry = None
        self.llm_with_tools = None
        
        # ReAct support (future)
        self.react_engine = None
        
        if self.use_tool_calling:
            self._initialize_tool_calling()
        
        # Create a comprehensive prompt for Cypher generation
        cypher_prompt = PromptTemplate(
            input_variables=["schema", "question", "available_values"],
            template="""
You are a Cypher query expert for a company knowledge graph. You MUST generate ONLY Cypher queries.

Schema: {schema}

AVAILABLE VALUES IN DATABASE:
{available_values}

CRITICAL RULES:
1. NEVER return natural language responses like "I don't know" or "I cannot answer"
2. ALWAYS generate a valid Cypher query, even if it might return empty results
3. For parameter queries, use EXACT parameter names from available values (e.g., 'Total revenue, Primary' not 'Total Revenue')
4. For company queries, use EXACT company names (e.g., 'Kajaria Ceramics' not just 'Kajaria')
5. Return ONLY the Cypher query - no explanations, apologies, or additional text
6. Use the available values above to guide your query construction
7. Keep queries simple and direct - avoid unnecessary joins
8. IMPORTANT: When user asks about "Total Revenue", use parameter_name = 'Total revenue, Primary' (exact match)
9. IMPORTANT: When user asks about "Kajaria", use company_name = 'Kajaria Ceramics' (exact match)

GRAPH STRUCTURE:
- Companies are connected to Countries via [:IN_COUNTRY]
- Companies are connected to Regions via [:IN_REGION] 
- Companies are connected to Sectors via [:IN_SECTOR]
- Companies are connected to Industries via [:IN_INDUSTRY]
- Companies are connected to Exchanges via [:LISTED_ON]
- Companies are connected to Parameters via [:HAS_PARAMETER]
- Parameters are connected to PeriodResults via [:HAS_VALUE_IN_PERIOD]
- Companies are connected to PeriodResults via [:HAS_RESULT_IN_PERIOD]

FOR PARAMETER QUERIES: Use simple patterns like:
MATCH (c:Company {company_name: 'Company Name'})-[:HAS_PARAMETER]->(p:Parameter {parameter_name: 'Exact Parameter Name'})-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)

COMPREHENSIVE EXAMPLES:

Example 1: Which companies are in the Technology sector?
MATCH (c:Company)-[:IN_SECTOR]->(s:Sector {name: 'Technology'}) RETURN c.company_name, c.cid, c.market_cap LIMIT 10

Example 2: Show me companies listed on NASDAQ
MATCH (c:Company)-[:LISTED_ON]->(e:Exchange) WHERE e.code CONTAINS 'NASDAQ' RETURN c.company_name, c.cid, c.exchange_symbol LIMIT 10

Example 3: Find pharmaceutical companies
MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Pharmaceutical' RETURN c.company_name, c.cid, i.name

Example 4: Which US companies are in Healthcare?
MATCH (c:Company)-[:IN_COUNTRY]->(country:Country {code: 'US'}) MATCH (c)-[:IN_SECTOR]->(s:Sector {name: 'Health Care'}) RETURN c.company_name, c.cid, s.name LIMIT 10

Example 5: Show me companies in Asia with positive change
MATCH (c:Company)-[:IN_REGION]->(r:Region {name: 'Asia'}) WHERE c.one_week_change > 0 RETURN c.company_name, c.cid, c.one_week_change ORDER BY c.one_week_change DESC LIMIT 10

Example 6: Find large companies with market cap over 1 billion
MATCH (c:Company) WHERE c.market_cap > 1000000000 RETURN c.company_name, c.cid, c.market_cap ORDER BY c.market_cap DESC LIMIT 10

Example 7: Companies in automotive industry
MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Automotive' RETURN c.company_name, c.cid, i.name

Example 8: European companies in financial sector
MATCH (c:Company)-[:IN_REGION]->(r:Region {name: 'Europe'}) MATCH (c)-[:IN_SECTOR]->(s:Sector {name: 'Financials'}) RETURN c.company_name, c.cid, r.name, s.name LIMIT 10

Example 9: Companies with specific ticker pattern
MATCH (c:Company) WHERE c.va_ticker CONTAINS 'AAPL' RETURN c.company_name, c.cid, c.va_ticker LIMIT 10

Example 10: Top performing companies this month
MATCH (c:Company) WHERE c.this_month_change > 0 RETURN c.company_name, c.cid, c.this_month_change ORDER BY c.this_month_change DESC LIMIT 10

Example 11: Companies in specific country by name
MATCH (c:Company)-[:IN_COUNTRY]->(country:Country) WHERE country.name CONTAINS 'United States' RETURN c.company_name, c.cid, country.name LIMIT 10

Example 12: Multiple sector companies
MATCH (c:Company)-[:IN_SECTOR]->(s:Sector) WHERE s.name IN ['Technology', 'Health Care'] RETURN c.company_name, c.cid, s.name LIMIT 10

Example 13: Companies with missing data (use OPTIONAL MATCH)
MATCH (c:Company) OPTIONAL MATCH (c)-[:IN_SECTOR]->(s:Sector) WHERE s.name IS NULL RETURN c.company_name, c.cid LIMIT 10

Example 14: Fuzzy industry matching
MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Tech' OR i.name CONTAINS 'Software' RETURN c.company_name, c.cid, i.name

Example 15: Companies with specific currency
MATCH (c:Company) WHERE c.base_currency = 'USD' RETURN c.company_name, c.cid, c.market_cap LIMIT 10

Example 16: Show Total Revenue for Kajaria across FY-2024 quarters
MATCH (c:Company {company_name: 'Kajaria Ceramics'})-[:HAS_PARAMETER]->(p:Parameter {parameter_name: 'Total revenue, Primary'})-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE pr.period CONTAINS 'FY-2024' RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period

Example 17: Find parameters with positive growth in latest quarter
MATCH (c:Company {company_name: 'Kajaria Ceramics'})-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE pr.period CONTAINS '3QFY-2024' AND pr.yoy_growth > 0 RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.yoy_growth ORDER BY pr.yoy_growth DESC LIMIT 10

Example 18: Multi-period parameter comparison
MATCH (c:Company {company_name: 'Kajaria Ceramics'})-[:HAS_PARAMETER]->(p:Parameter {parameter_name: 'Total revenue, Primary'})-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE pr.period IN ['1QFY-2024', '2QFY-2024', '3QFY-2024', '4QFY-2024'] RETURN c.company_name, p.parameter_name, pr.period, pr.value ORDER BY pr.period

Question: {question}

Cypher Query:"""
        )
        
        self.cypher_chain = GraphCypherQAChain.from_llm(
            ChatOpenAI(temperature=0),
            graph=graph,
            verbose=True,
            cypher_prompt=cypher_prompt,
            allow_dangerous_requests=True,
        )
    
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
            
            # Route to appropriate generation method
            if self.use_tool_calling:
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
            
            # Fallback to existing monolithic prompt approach
            return self._generate_with_monolithic_prompt(question)
            
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
                    self.log_manager.add_info_log('Tool calling not initialized, falling back to monolithic prompt')
                return self._generate_with_monolithic_prompt(question)
            
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
                            if self.log_manager:
                                self.log_manager.add_info_log(f'Executing tool: {tool_name} with args: {tool_args}')
                            
                            # Execute tool via registry
                            tool_result = self.tool_registry.execute_tool(tool_name, **tool_args)
                            
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
                self.log_manager.add_info_log(f'Tool calling did not produce valid query, falling back to monolithic prompt')
            return self._generate_with_monolithic_prompt(question)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Tool calling generation failed: {str(e)}', e)
            # Fallback to monolithic prompt
            return self._generate_with_monolithic_prompt(question)
    
    def _generate_with_monolithic_prompt(self, question: str) -> str:
        """
        Generate Cypher query using existing monolithic prompt approach
        
        This is the original implementation for backward compatibility
        
        Args:
            question: Natural language question
        
        Returns:
            Generated Cypher query string
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log('Using monolithic prompt approach (backward compatibility)')
            
            # Analyze question for parameter queries
            question_lower = question.lower()
            
            # Detect if this is a parameter query (mentions parameter names and company names)
            # Common parameter indicators: revenue, margin, profit, ebitda, net income, etc.
            parameter_indicators = [
                'revenue', 'margin', 'profit', 'ebitda', 'ebit', 'net income', 'expense', 
                'cost', 'earnings', 'sales', 'gross', 'operating', 'parameter', 'metric',
                'ratio', 'growth', 'yoy', 'qoq', 'percentage', 'percentage', 'ratio',
                'receivable', 'payable', 'accounts', 'production', 'volume', 'capacity',
                'quantity', 'units', 'output', 'asset', 'liability', 'equity'
            ]
            
            is_parameter_query = any(indicator in question_lower for indicator in parameter_indicators)
            
            # Detect period keywords
            has_latest_recent = 'latest' in question_lower or 'recent' in question_lower or 'current' in question_lower
            has_specific_period = any(keyword in question_lower for keyword in ['q1', 'q2', 'q3', 'q4', 'fy-', 'quarter', 'annual', 'year'])
            
            if is_parameter_query:
                if self.log_manager:
                    self.log_manager.add_info_log(f'Detected parameter query - will use parameter-specific query pattern')
                    if has_latest_recent:
                        self.log_manager.add_info_log('Detected "latest/recent/current" - will fetch most recent period data')
                    if has_specific_period:
                        self.log_manager.add_info_log('Detected specific period - will filter by period')
            
            # Get dynamic schema context
            schema_context = self.get_dynamic_schema_context()
            available_values = ""
            
            if schema_context:
                available_values = f"""
SECTORS: {', '.join(schema_context['sectors'][:10])}
INDUSTRIES: {', '.join(schema_context['industries'][:15])}
COUNTRIES: {', '.join(schema_context['countries'][:10])}
REGIONS: {', '.join(schema_context['regions'][:5])}
EXCHANGES: {', '.join(schema_context['exchanges'][:10])}
COMPANIES: {', '.join(schema_context['companies'][:20])}
PARAMETERS: {', '.join(schema_context['parameters'][:25])}
PERIODS: {', '.join(schema_context['periods'][:15])}
"""
            else:
                available_values = "Schema context unavailable - use fuzzy matching with CONTAINS"
            
            # Use simple LLM call with basic string formatting
            llm = ChatOpenAI(temperature=0)
            schema = str(graph.get_schema)
            
            # Create prompt using .format() to avoid f-string evaluation issues
            # Use double braces {{}} to escape literal braces in Cypher examples
            formatted_prompt = """
You are a Cypher query expert. You MUST generate ONLY Cypher queries. DO NOT return any natural language text, explanations, or apologies.

Schema: {schema}

Available Values: {available_values}

ABSOLUTE REQUIREMENTS - VIOLATION WILL CAUSE ERRORS:
1. Your response MUST start with "MATCH", "RETURN", "WITH", "OPTIONAL", "UNWIND", or "CALL"
2. DO NOT include phrases like "I'm sorry", "I cannot", "Here is", "The query is", etc.
3. DO NOT include any explanatory text before or after the Cypher query
4. If you cannot generate a query, return a simple MATCH query that queries all companies: "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
5. ALWAYS generate a valid Cypher query - never refuse to generate one

CRITICAL RULES:
6. ALWAYS use EXTREMELY LENIENT fuzzy matching for ALL searches to handle typos, misspellings, and variations
7. Use LIMIT 100 for general queries (sector, country, region, exchange), but DO NOT use LIMIT for industry-specific queries to get complete results
8. Use multiple fuzzy matching techniques: CONTAINS, STARTS WITH, ENDS WITH, and partial word matching
9. For company searches, use: WHERE c.company_name CONTAINS 'term' OR c.company_name STARTS WITH 'term' OR c.company_name ENDS WITH 'term'
10. Handle common misspellings: "appolo" → "apollo", "hospitol" → "hospital", "tyre" → "tire", etc.
11. Use case-insensitive matching and ignore special characters
12. ALWAYS return comprehensive company details: company_name, cid, country, sector, industry, market_cap
13. MANDATORY: Always include c.cid in RETURN clause for any company-related query
14. When users ask for "details", "information", or specific company names, include ALL mapped relationships
15. IMPORTANT: For software industry queries, use ONLY "Software" matching, NOT "tech" (to avoid matching Biotechnology)
16. If exact match fails, try partial word matching (e.g., "app" matches "Apollo")
17. FOR "latest" or "recent" queries: Use ORDER BY pr.period DESC LIMIT 1 (not WHERE pr.period = 'latest'). Remove period filters from WHERE clause.
18. FOR period-based queries with "latest/recent": Return the most recent period available by sorting DESC and limiting to 1 result.
19. FOR PARAMETER QUERIES: Always use fuzzy matching with CONTAINS for both company_name and parameter_name. Match using available parameter names from the database.
20. FOR MULTIPLE PARAMETERS: Use UNION or multiple MATCH patterns to get different parameters for the same company.
21. FOR MULTIPLE PERIODS: When querying multiple periods, filter with WHERE pr.period IN ['period1', 'period2'] or use CONTAINS for fiscal year patterns.
22. ALWAYS return: company_name, parameter_name, period, value, currency, yoy_growth for parameter queries.

PARAMETER QUERY EXAMPLES:
Question: Which companies are in Technology?
Cypher: MATCH (c:Company)-[:IN_SECTOR]->(s:Sector) WHERE s.name CONTAINS 'Technology' OR s.name CONTAINS 'tech' RETURN c.company_name, c.cid, c.market_cap, s.name as sector LIMIT 10

Question: Find pharmaceutical companies
Cypher: MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Pharmaceutical' OR i.name CONTAINS 'pharma' OR i.name CONTAINS 'drug' RETURN c.company_name, c.cid, i.name as industry

Question: Show me automotive industry companies
Cypher: MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Automotive' OR i.name CONTAINS 'Auto' RETURN c.company_name, c.cid, i.name as industry

Question: Find software industry companies
Cypher: MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry) WHERE i.name CONTAINS 'Software' RETURN c.company_name, c.cid, i.name as industry

Question: Find Apollo Tyres company details (handles "appolo", "appollo", "apollo")
Cypher: MATCH (c:Company)-[:IN_COUNTRY]->(country:Country), (c)-[:IN_SECTOR]->(s:Sector), (c)-[:IN_INDUSTRY]->(i:Industry) WHERE (c.company_name CONTAINS 'Apollo' OR c.company_name CONTAINS 'apollo' OR c.company_name CONTAINS 'appolo' OR c.company_name CONTAINS 'appollo') AND (c.company_name CONTAINS 'Tyre' OR c.company_name CONTAINS 'tyre' OR c.company_name CONTAINS 'tire') RETURN c.company_name, c.cid, country.name as country, s.name as sector, i.name as industry, c.market_cap LIMIT 10

Question: Apollo Hospital details (handles "appllo", "hospitol", "hospital")
Cypher: MATCH (c:Company)-[:IN_COUNTRY]->(country:Country), (c)-[:IN_SECTOR]->(s:Sector), (c)-[:IN_INDUSTRY]->(i:Industry) WHERE (c.company_name CONTAINS 'Apollo' OR c.company_name CONTAINS 'apollo' OR c.company_name CONTAINS 'appolo' OR c.company_name CONTAINS 'appollo' OR c.company_name CONTAINS 'appllo') AND (c.company_name CONTAINS 'Hospital' OR c.company_name CONTAINS 'hospital' OR c.company_name CONTAINS 'hospitol') RETURN c.company_name, c.cid, country.name as country, country.code as country_code, s.name as sector, i.name as industry, c.market_cap, c.description LIMIT 10

Question: Indian tyre companies details
Cypher: MATCH (c:Company)-[:IN_COUNTRY]->(country:Country), (c)-[:IN_SECTOR]->(s:Sector), (c)-[:IN_INDUSTRY]->(i:Industry) WHERE (country.name CONTAINS 'India' OR country.name CONTAINS 'indian') AND (c.company_name CONTAINS 'Tyre' OR c.company_name CONTAINS 'tyre' OR c.company_name CONTAINS 'tire') RETURN c.company_name, c.cid, country.name as country, s.name as sector, i.name as industry, c.market_cap

Question: Company details for [company name] (ultra-lenient matching)
Cypher: MATCH (c:Company)-[:IN_COUNTRY]->(country:Country), (c)-[:IN_SECTOR]->(s:Sector), (c)-[:IN_INDUSTRY]->(i:Industry) WHERE c.company_name CONTAINS '[company_name]' OR c.company_name STARTS WITH '[company_name]' OR c.company_name ENDS WITH '[company_name]' RETURN c.company_name, c.cid, country.name as country, country.code as country_code, s.name as sector, i.name as industry, c.market_cap, c.description LIMIT 10

Question: Total revenue of Kajaria
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND (p.parameter_name CONTAINS 'Total revenue' OR p.parameter_name CONTAINS 'Revenue') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period DESC

Question: Total revenue of Kajaria for FY-2024
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND (p.parameter_name CONTAINS 'Total revenue' OR p.parameter_name CONTAINS 'Revenue') AND pr.period CONTAINS 'FY-2024' RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period

Question: EBITDA margin of Kajaria latest
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'margin') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period DESC LIMIT 1

Question: EBITDA margin and Net profit for Kajaria in Q3FY-2024
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND pr.period CONTAINS '3QFY-2024' AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Net profit' OR p.parameter_name CONTAINS 'Profit') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY p.parameter_name

Question: Accounts receivable of Kajaria in 2QFY-2025
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND p.parameter_name CONTAINS 'Accounts receivable' AND pr.period CONTAINS '2QFY-2025' RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY p.parameter_name

Question: Show me Total revenue and EBITDA margin for Kajaria across all FY-2024 quarters
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND pr.period CONTAINS 'FY-2024' AND (p.parameter_name CONTAINS 'Total revenue' OR p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'Revenue' OR p.parameter_name CONTAINS 'margin') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period, p.parameter_name

Question: Revenue, Profit, and EBITDA margin of [any company] latest
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS '[company]' AND (p.parameter_name CONTAINS 'Revenue' OR p.parameter_name CONTAINS 'Profit' OR p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'margin' OR p.parameter_name CONTAINS 'EBITDA') WITH c, p, pr, ROW_NUMBER() OVER (PARTITION BY p.parameter_name ORDER BY pr.period DESC) as rn WHERE rn = 1 RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY p.parameter_name

Question: What are the parameters for Kajaria in 3QFY-2024 and 4QFY-2024
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND (pr.period CONTAINS '3QFY-2024' OR pr.period CONTAINS '4QFY-2024') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period, p.parameter_name

Question: All parameters for [company] latest quarter
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS '[company]' WITH c, pr, MAX(pr.period) as latest_period MATCH (c)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE pr.period = latest_period RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY p.parameter_name

Question: {{question}}
Cypher:""".format(schema=schema, available_values=available_values, question=question)
            response = llm.invoke(formatted_prompt)
            
            # Extract just the Cypher query
            raw_response = response.content.strip()
            
            # Extract Cypher query from response (handle cases where LLM adds explanations)
            cypher_query = self._extract_cypher_query(raw_response)
            
            # Check if the query matches the question intent (especially for parameter queries)
            if self._is_parameter_question(question):
                if not self._query_has_parameters(cypher_query):
                    if self.log_manager:
                        self.log_manager.add_info_log(f'[WARNING] Generated query does not match parameter question intent, using query decomposition')
                    # Use query decomposition for better accuracy
                    decomposition = self._decompose_parameter_query(question)
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Query decomposition: {decomposition}')
                    cypher_query = self._generate_decomposed_query(decomposition)
                elif self._is_valid_cypher(cypher_query):
                    # Even if query has parameters, validate it has the right structure
                    # Use decomposition as a fallback check
                    decomposition = self._decompose_parameter_query(question)
                    # Check if decomposition suggests a different structure is needed
                    if decomposition['company'] and decomposition['parameters']:
                        # Verify the query includes the company and parameters
                        query_lower = cypher_query.lower()
                        company_word = decomposition['company'].split()[0].lower()
                        if company_word not in query_lower:
                            if self.log_manager:
                                self.log_manager.add_info_log(f'[WARNING] Query missing company match, regenerating with decomposition')
                            cypher_query = self._generate_decomposed_query(decomposition)
            
            # Validate that it's actually a Cypher query
            if not self._is_valid_cypher(cypher_query):
                if self.log_manager:
                    self.log_manager.add_info_log(f'[WARNING] LLM returned invalid Cypher query, attempting to fix...')
                    self.log_manager.add_info_log(f'Raw response: {raw_response[:200]}')
                
                # Try to extract Cypher from the response
                cypher_query = self._extract_cypher_from_text(raw_response)
                
                # If still invalid, generate a fallback query
                if not self._is_valid_cypher(cypher_query):
                    if self.log_manager:
                        self.log_manager.add_info_log(f'[WARNING] LLM response was invalid, generating smart fallback query for question: {question[:100]}')
                        self.log_manager.add_info_log(f'Invalid response was: {raw_response[:300]}')
                    cypher_query = self._generate_fallback_query(question)
                    if self.log_manager:
                        self.log_manager.add_info_log(f'Generated fallback query: {cypher_query[:200]}')
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 1 Complete: Generated Cypher query')
                self.log_manager.add_info_log(f'🔍 Generated Cypher Query:\n{cypher_query}')
            
            return cypher_query
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Cypher generation failed: {str(e)}', e)
            raise
    
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
            
            # Format structured results in a clear, readable format
            structured_data = ""
            if structured_results:
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
                structured_data = "No structured data records found."
            
            # Create synthesis prompt
            # Check if we actually have results
            has_results = len(structured_results) > 0 and structured_data.strip() != ""
            
            # Enhanced prompt based on whether we have results
            if len(structured_results) > 0:
                results_indicator = f"⚠️ CRITICAL: {len(structured_results)} DATA RECORDS FOUND - YOU MUST PRESENT THIS DATA"
            else:
                results_indicator = "No data records found in database."
            
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
        """Disable tool calling (fallback to monolithic prompt)"""
        self.use_tool_calling = False
        if self.log_manager:
            self.log_manager.add_info_log('Tool calling disabled - using monolithic prompt')


# Update the original GraphRAG import to use PEERS version
GraphRAG = PEERSGraphRAG

