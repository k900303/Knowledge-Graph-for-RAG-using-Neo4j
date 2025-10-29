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
import textwrap
import traceback
import inspect
import io
import sys
import re


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
    
    def __init__(self, log_manager=None):
        self.log_manager = log_manager
        self.cypher_history = []  # Store generated Cypher queries
        self.schema_cache = None  # Cache for schema data
        self.cache_timestamp = None
        
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
                'periods': []
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
            
            # Get parameters
            parameters_query = "MATCH (p:Parameter) RETURN DISTINCT p.parameter_name ORDER BY p.parameter_name LIMIT 30"
            parameters_result = graph.query(parameters_query)
            schema_context['parameters'] = [row['p.parameter_name'] for row in parameters_result]
            
            # Get periods
            periods_query = "MATCH (pr:PeriodResult) RETURN DISTINCT pr.period ORDER BY pr.period LIMIT 15"
            periods_result = graph.query(periods_query)
            schema_context['periods'] = [row['pr.period'] for row in periods_result]
            
            self.schema_cache = schema_context
            self.cache_timestamp = time.time()
            
            if self.log_manager:
                self.log_manager.add_info_log(f'Schema context loaded: {len(schema_context["sectors"])} sectors, {len(schema_context["industries"])} industries, {len(schema_context["parameters"])} parameters')
            
            return schema_context
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Failed to fetch schema context: {str(e)}', e)
            return None
    
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
            
            # Check for "latest" or "recent" keywords and handle them specially
            question_lower = question.lower()
            if 'latest' in question_lower or 'recent' in question_lower:
                # For latest/recent queries, use ORDER BY period DESC LIMIT 1
                # This removes the period filter from WHERE clause and adds ordering
                if self.log_manager:
                    self.log_manager.add_info_log('Detected "latest" or "recent" query - will fetch most recent data')
            
            # Check for common parameter name mappings
            if 'total revenue' in question_lower and 'kajaria' in question_lower:
                # Direct query for the most common case
                cypher_query = """
MATCH (c:Company {company_name: 'Kajaria Ceramics'})-[:HAS_PARAMETER]->(p:Parameter {parameter_name: 'Total revenue, Primary'})-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) 
WHERE pr.period CONTAINS 'FY-2024' 
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth 
ORDER BY pr.period
""".strip()
                
                if self.log_manager:
                    self.log_manager.add_info_log(f'Step 2: Using direct query for Total Revenue: {cypher_query}')
                
                return cypher_query
            
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
PARAMETERS: {', '.join(schema_context['parameters'][:15])}
PERIODS: {', '.join(schema_context['periods'][:10])}
"""
            else:
                available_values = "Schema context unavailable - use fuzzy matching with CONTAINS"
            
            # Use simple LLM call with basic string formatting
            llm = ChatOpenAI(temperature=0)
            schema = str(graph.get_schema)
            
            # Create prompt using .format() to avoid f-string evaluation issues
            # Use double braces {{}} to escape literal braces in Cypher examples
            formatted_prompt = """
You are a Cypher query expert. Generate ONLY Cypher queries, no explanations.

Schema: {schema}

Available Values: {available_values}

CRITICAL RULES:
1. Return ONLY the Cypher query - no explanations, apologies, or additional text
2. ALWAYS use EXTREMELY LENIENT fuzzy matching for ALL searches to handle typos, misspellings, and variations
3. Use LIMIT 100 for general queries (sector, country, region, exchange), but DO NOT use LIMIT for industry-specific queries to get complete results
4. Use multiple fuzzy matching techniques: CONTAINS, STARTS WITH, ENDS WITH, and partial word matching
5. For company searches, use: WHERE c.company_name CONTAINS 'term' OR c.company_name STARTS WITH 'term' OR c.company_name ENDS WITH 'term'
6. Handle common misspellings: "appolo" → "apollo", "hospitol" → "hospital", "tyre" → "tire", etc.
7. Use case-insensitive matching and ignore special characters
8. ALWAYS return comprehensive company details: company_name, cid, country, sector, industry, market_cap
9. MANDATORY: Always include c.cid in RETURN clause for any company-related query
10. When users ask for "details", "information", or specific company names, include ALL mapped relationships
11. IMPORTANT: For software industry queries, use ONLY "Software" matching, NOT "tech" (to avoid matching Biotechnology)
12. If exact match fails, try partial word matching (e.g., "app" matches "Apollo")
13. FOR "latest" or "recent" queries: Use ORDER BY pr.period DESC LIMIT 1 (not WHERE pr.period = 'latest'). Remove period filters from WHERE clause.
14. FOR period-based queries with "latest/recent": Return the most recent period available by sorting DESC and limiting to 1 result.

Examples:
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

Question: EBITA margin of kajaria latest
Cypher: MATCH (c:Company {{company_name: 'Kajaria Ceramics'}})-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'margin' RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency ORDER BY pr.period DESC LIMIT 1

Question: EBITDA margin % of kajaria recent
Cypher: MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE c.company_name CONTAINS 'Kajaria' AND (p.parameter_name CONTAINS 'EBITDA margin' OR p.parameter_name CONTAINS 'margin') RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth ORDER BY pr.period DESC LIMIT 1

Question: {{question}}
Cypher:""".format(schema=schema, available_values=available_values, question=question)
            response = llm.invoke(formatted_prompt)
            
            # Extract just the Cypher query
            cypher_query = response.content.strip()
            
            # Clean up the response
            if cypher_query.startswith("Cypher:"):
                cypher_query = cypher_query.replace("Cypher:", "").strip()
            
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
            if self.log_manager:
                self.log_manager.add_info_log(f'Step 2: Executing Cypher query against Neo4j')
                self.log_manager.add_info_log(f'🔍 Cypher Query: {cypher_query}')
            else:
                # Fallback: print to console if no log_manager
                print(f'\n[GraphRAG] Executing Cypher Query:')
                print(f'🔍 {cypher_query}\n')
            
            # Execute the query
            results = graph.query(cypher_query)
            
            if self.log_manager:
                self.log_manager.add_info_log(f'✅ Query executed successfully, returned {len(results)} results')
                if results:
                    # Log sample of results structure
                    sample_keys = list(results[0].keys()) if results else []
                    self.log_manager.add_info_log(f'📊 Result columns: {", ".join(sample_keys)}')
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
            
            # Format structured results
            # Show all results for industry queries, limit others to 20
            structured_data = ""
            for i, result in enumerate(structured_results):
                if isinstance(result, dict):
                    structured_data += f"Result {i+1}: {result}\n"
            
            # Create synthesis prompt
            synthesis_prompt = f"""
Based ONLY on the structured data and text chunks provided below, answer the user's question. Do NOT provide external information or suggestions.

Question: {question}

Structured Data ({len(structured_results)} companies found):
{structured_data}

Relevant Text Chunks:
{chunks_text}

CRITICAL INSTRUCTIONS:
1. Answer ONLY based on the data provided above
2. If no relevant data is found, simply state "No data found for this is PEERS DATABASE"
3. Do NOT suggest external sources, websites, or general knowledge
4. Do NOT provide company names or information not present in the data
5. If data exists, provide specific details from the structured data and chunks
6. For industry queries, list ALL companies found in the data (do not truncate)
7. For other queries, be concise and factual
8. IMPORTANT: If the question asks for companies in an industry, list EVERY company from the structured data, not just a few examples
9. The structured data shows {len(structured_results)} companies - list ALL of them

Answer:"""
            
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


# Update the original GraphRAG import to use PEERS version
GraphRAG = PEERSGraphRAG

