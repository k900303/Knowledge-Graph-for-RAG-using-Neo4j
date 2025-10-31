"""
Tests for Tool Calling implementation in PEERS GraphRAG
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG
from PEERS_RAG_tools import ToolRegistry, ParameterSearchTool, CompanySearchTool


class MockLogManager:
    """Mock log manager for testing"""
    def __init__(self):
        self.logs = []
    
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
    
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))


class TestToolCalling(unittest.TestCase):
    """Test cases for Tool Calling functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        
        # Create instance with tool calling enabled
        self.graph_rag_tools = PEERSGraphRAG(
            log_manager=self.log_manager,
            use_tool_calling=True
        )
        
        # Create instance without tool calling (backward compatibility)
        self.graph_rag_classic = PEERSGraphRAG(
            log_manager=self.log_manager,
            use_tool_calling=False
        )
    
    def test_tool_calling_initialization(self):
        """Test that tool calling initializes correctly"""
        self.assertTrue(self.graph_rag_tools.use_tool_calling)
        self.assertIsNotNone(self.graph_rag_tools.tool_registry)
        self.assertIsNotNone(self.graph_rag_tools.llm_with_tools)
    
    def test_backward_compatibility(self):
        """Test that classic mode still works"""
        self.assertFalse(self.graph_rag_classic.use_tool_calling)
        self.assertIsNone(self.graph_rag_classic.tool_registry)
    
    def test_complexity_assessment_simple(self):
        """Test complexity assessment for simple queries"""
        simple_queries = [
            "Show me revenue for Kajaria",
            "What is the market cap of Apollo Tyres?",
            "List companies in Technology sector"
        ]
        
        for query in simple_queries:
            complexity = self.graph_rag_tools._assess_complexity(query)
            self.assertEqual(complexity, "simple", f"Query should be simple: {query}")
    
    def test_complexity_assessment_complex(self):
        """Test complexity assessment for complex queries"""
        complex_queries = [
            "Compare revenue of Kajaria vs Asian Paints",
            "Show me revenue trends across multiple quarters",
            "Calculate the average margin for all companies"
        ]
        
        for query in complex_queries:
            complexity = self.graph_rag_tools._assess_complexity(query)
            self.assertEqual(complexity, "complex", f"Query should be complex: {query}")
    
    def test_tool_registry_creation(self):
        """Test that tool registry is created with all tools"""
        registry = self.graph_rag_tools.tool_registry
        
        self.assertIsNotNone(registry)
        self.assertIn("search_parameters", registry.tools)
        self.assertIn("search_company", registry.tools)
        self.assertIn("generate_parameter_query", registry.tools)
    
    def test_tool_definitions(self):
        """Test that all tools have proper definitions"""
        registry = self.graph_rag_tools.tool_registry
        tool_definitions = registry.get_all_tool_definitions()
        
        self.assertGreater(len(tool_definitions), 0)
        
        # Check each tool has required fields
        for tool_def in tool_definitions:
            self.assertIn("type", tool_def)
            self.assertIn("function", tool_def)
            self.assertIn("name", tool_def["function"])
            self.assertIn("description", tool_def["function"])
    
    def test_enable_disable_tool_calling(self):
        """Test runtime enabling/disabling of tool calling"""
        # Start disabled
        rag = PEERSGraphRAG(log_manager=self.log_manager, use_tool_calling=False)
        self.assertFalse(rag.use_tool_calling)
        
        # Enable at runtime
        rag.enable_tool_calling()
        self.assertTrue(rag.use_tool_calling)
        self.assertIsNotNone(rag.tool_registry)
        
        # Disable at runtime
        rag.disable_tool_calling()
        self.assertFalse(rag.use_tool_calling)
    
    def test_parameter_search_tool(self):
        """Test parameter search tool directly"""
        tool = ParameterSearchTool(log_manager=self.log_manager)
        result = tool.execute(search_term="revenue", limit=3)
        
        self.assertIn("matches", result)
        self.assertIsInstance(result["matches"], list)
    
    def test_company_search_tool(self):
        """Test company search tool directly"""
        tool = CompanySearchTool(log_manager=self.log_manager)
        result = tool.execute(company_name="Kajaria", limit=3)
        
        self.assertIn("companies", result)
        self.assertIsInstance(result["companies"], list)


class TestToolCallingIntegration(unittest.TestCase):
    """Integration tests for tool calling with actual queries"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        self.graph_rag = PEERSGraphRAG(
            log_manager=self.log_manager,
            use_tool_calling=True
        )
    
    @unittest.skip("Requires actual Neo4j connection and API keys")
    def test_parameter_query_with_tools(self):
        """Test parameter query generation with tool calling"""
        question = "Show me revenue for Kajaria"
        cypher = self.graph_rag.generate_cypher_only(question)
        
        self.assertIsInstance(cypher, str)
        self.assertIn("MATCH", cypher.upper())
        self.assertIn("HAS_PARAMETER", cypher.upper())
    
    @unittest.skip("Requires actual Neo4j connection and API keys")
    def test_company_details_with_tools(self):
        """Test company details query generation with tool calling"""
        question = "Show details of Apollo Tyres"
        cypher = self.graph_rag.generate_cypher_only(question)
        
        self.assertIsInstance(cypher, str)
        self.assertIn("MATCH", cypher.upper())


if __name__ == '__main__':
    unittest.main()

