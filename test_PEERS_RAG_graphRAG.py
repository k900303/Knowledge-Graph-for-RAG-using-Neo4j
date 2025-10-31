"""
Unit tests for PEERS_RAG_graphRAG module
Tests query decomposition, parameter detection, and Cypher query generation
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG


class MockLogManager:
    """Mock log manager for testing"""
    def __init__(self):
        self.logs = []
    
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
    
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))


class TestPEERSGraphRAG(unittest.TestCase):
    """Test cases for PEERSGraphRAG class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        self.graph_rag = PEERSGraphRAG(log_manager=self.log_manager)
        
        # Mock schema context for testing
        self.mock_schema_context = {
            'companies': ['Kajaria Ceramics', 'Bajaj Finance Limited', 'Apollo Tyres'],
            'parameters': ['Total revenue, Primary', 'EBITDA margin', 'Net profit'],
            'periods': ['1QFY-2024', '2QFY-2024', '3QFY-2024', '4QFY-2024'],
            'sectors': [],
            'industries': [],
            'countries': [],
            'regions': [],
            'exchanges': []
        }
    
    def test_is_parameter_question(self):
        """Test parameter question detection"""
        # Test parameter questions
        self.assertTrue(self.graph_rag._is_parameter_question("EBITDA margin of Kajaria"))
        self.assertTrue(self.graph_rag._is_parameter_question("Show me revenue for company"))
        self.assertTrue(self.graph_rag._is_parameter_question("Net profit and margin"))
        self.assertTrue(self.graph_rag._is_parameter_question("Total revenue, Primary"))
        
        # Test non-parameter questions
        self.assertFalse(self.graph_rag._is_parameter_question("Which companies are in Technology?"))
        self.assertFalse(self.graph_rag._is_parameter_question("Show me companies in India"))
        self.assertFalse(self.graph_rag._is_parameter_question("List all pharmaceutical companies"))
    
    def test_query_has_parameters(self):
        """Test if Cypher query includes parameter relationships"""
        # Valid parameter queries
        valid_query1 = "MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) RETURN c.company_name"
        self.assertTrue(self.graph_rag._query_has_parameters(valid_query1))
        
        valid_query2 = "MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter) RETURN p.parameter_name"
        self.assertTrue(self.graph_rag._query_has_parameters(valid_query2))
        
        # Invalid (non-parameter) queries
        invalid_query1 = "MATCH (c:Company) RETURN c.company_name"
        self.assertFalse(self.graph_rag._query_has_parameters(invalid_query1))
        
        invalid_query2 = "MATCH (c:Company)-[:IN_SECTOR]->(s:Sector) RETURN c.company_name"
        self.assertFalse(self.graph_rag._query_has_parameters(invalid_query2))
    
    def test_is_valid_cypher(self):
        """Test Cypher query validation"""
        # Valid queries
        valid_queries = [
            "MATCH (c:Company) RETURN c.company_name",
            "MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter) WHERE c.company_name CONTAINS 'Kajaria' RETURN p.parameter_name",
            "OPTIONAL MATCH (c:Company) RETURN c.company_name LIMIT 10",
            "WITH c AS company MATCH (c:Company) RETURN c.company_name"
        ]
        
        for query in valid_queries:
            self.assertTrue(self.graph_rag._is_valid_cypher(query), f"Query should be valid: {query}")
        
        # Invalid queries
        invalid_queries = [
            "I'm sorry, but I cannot assist with that request",
            "Here is the query: MATCH (c:Company)",
            "Cannot assist",
            "",  # Empty
            "MATCH",  # Too short
            "SELECT * FROM companies"  # SQL instead of Cypher
        ]
        
        for query in invalid_queries:
            self.assertFalse(self.graph_rag._is_valid_cypher(query), f"Query should be invalid: {query}")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_decompose_parameter_query_single_parameter(self, mock_schema):
        """Test query decomposition for single parameter"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin of Kajaria in Q3FY-2024"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        
        self.assertEqual(decomposition['company'], 'Kajaria Ceramics')
        self.assertIn('EBITDA margin', decomposition['parameters'])
        self.assertEqual(decomposition['period'], '3QFY-2024')
        self.assertFalse(decomposition['is_multi_parameter'])
        self.assertEqual(decomposition['operation'], 'retrieve')
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_decompose_parameter_query_multi_parameter(self, mock_schema):
        """Test query decomposition for multiple parameters"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        
        self.assertEqual(decomposition['company'], 'Kajaria Ceramics')
        self.assertIn('EBITDA margin', decomposition['parameters'])
        self.assertIn('Net profit', decomposition['parameters'])
        self.assertEqual(len(decomposition['parameters']), 2)
        self.assertTrue(decomposition['is_multi_parameter'])
        self.assertEqual(decomposition['period'], '3QFY-2024')
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_decompose_parameter_query_period_detection(self, mock_schema):
        """Test period detection in decomposition"""
        mock_schema.return_value = self.mock_schema_context
        
        # Test Q1
        question1 = "Revenue of Kajaria in Q1FY-2024"
        decomp1 = self.graph_rag._decompose_parameter_query(question1)
        self.assertEqual(decomp1['period'], '1QFY-2024')
        
        # Test Q2
        question2 = "Revenue of Kajaria in Q2FY-2024"
        decomp2 = self.graph_rag._decompose_parameter_query(question2)
        self.assertEqual(decomp2['period'], '2QFY-2024')
        
        # Test Q4
        question4 = "Revenue of Kajaria in Q4FY-2024"
        decomp4 = self.graph_rag._decompose_parameter_query(question4)
        self.assertEqual(decomp4['period'], '4QFY-2024')
        
        # Test latest
        question_latest = "Revenue of Kajaria latest"
        decomp_latest = self.graph_rag._decompose_parameter_query(question_latest)
        self.assertEqual(decomp_latest['period'], 'latest')
        
        # Test FY-2024
        question_fy = "Revenue of Kajaria for FY-2024"
        decomp_fy = self.graph_rag._decompose_parameter_query(question_fy)
        self.assertEqual(decomp_fy['period'], 'FY-2024')
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_decompose_parameter_query_total_revenue(self, mock_schema):
        """Test total revenue detection"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "Total revenue of Kajaria"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        
        self.assertIn('Total revenue, Primary', decomposition['parameters'])
        self.assertNotIn('Revenue', decomposition['parameters'])  # Should not add generic Revenue
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_decomposed_query_single_parameter(self, mock_schema):
        """Test query generation from decomposition - single parameter"""
        mock_schema.return_value = self.mock_schema_context
        
        decomposition = {
            'company': 'Kajaria Ceramics',
            'parameters': ['EBITDA margin'],
            'period': '3QFY-2024',
            'operation': 'retrieve',
            'is_multi_parameter': False
        }
        
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Check query structure
        self.assertIn('MATCH', query.upper())
        self.assertIn('HAS_PARAMETER', query.upper())
        self.assertIn('HAS_VALUE_IN_PERIOD', query.upper())
        self.assertIn('PERIODRESULT', query.upper())
        self.assertIn('Kajaria', query)
        self.assertIn('3QFY-2024', query)
        self.assertIn('EBITDA margin', query)
        self.assertIn('RETURN', query.upper())
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_decomposed_query_multi_parameter(self, mock_schema):
        """Test query generation from decomposition - multiple parameters"""
        mock_schema.return_value = self.mock_schema_context
        
        decomposition = {
            'company': 'Kajaria Ceramics',
            'parameters': ['EBITDA margin', 'Net profit'],
            'period': '3QFY-2024',
            'operation': 'retrieve',
            'is_multi_parameter': True
        }
        
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Check query structure
        self.assertIn('HAS_PARAMETER', query.upper())
        self.assertIn('EBITDA margin', query)
        self.assertIn('Net profit', query)
        self.assertIn('OR', query.upper())  # Should have OR for multiple parameters
        self.assertIn('ORDER BY', query.upper())
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_decomposed_query_latest_period(self, mock_schema):
        """Test query generation for latest period"""
        mock_schema.return_value = self.mock_schema_context
        
        decomposition = {
            'company': 'Kajaria Ceramics',
            'parameters': ['EBITDA margin'],
            'period': 'latest',
            'operation': 'retrieve',
            'is_multi_parameter': False
        }
        
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Should order by period DESC for latest
        self.assertIn('ORDER BY', query.upper())
        self.assertIn('DESC', query.upper())
        self.assertNotIn('3QFY-2024', query)  # Should not filter by specific period
        self.assertIn('LIMIT', query.upper())
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_decomposed_query_no_company(self, mock_schema):
        """Test query generation when company is not detected"""
        mock_schema.return_value = self.mock_schema_context
        
        decomposition = {
            'company': None,
            'parameters': ['Revenue'],
            'period': None,
            'operation': 'retrieve',
            'is_multi_parameter': False
        }
        
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Should still generate valid query
        self.assertIn('MATCH', query.upper())
        self.assertIn('HAS_PARAMETER', query.upper())
        self.assertIn('RETURN', query.upper())
    
    def test_extract_cypher_query_clean(self):
        """Test extracting Cypher from clean response"""
        # Clean Cypher query
        clean_response = "MATCH (c:Company) RETURN c.company_name"
        result = self.graph_rag._extract_cypher_query(clean_response)
        self.assertEqual(result, clean_response)
    
    def test_extract_cypher_query_with_prefix(self):
        """Test extracting Cypher query with prefix"""
        # Query with prefix
        response1 = "Cypher: MATCH (c:Company) RETURN c.company_name"
        result1 = self.graph_rag._extract_cypher_query(response1)
        self.assertIn("MATCH", result1)
        self.assertNotIn("Cypher:", result1)
        
        # Query with code block
        response2 = "```cypher\nMATCH (c:Company) RETURN c.company_name\n```"
        result2 = self.graph_rag._extract_cypher_query(response2)
        self.assertIn("MATCH", result2)
    
    def test_extract_cypher_query_with_explanation(self):
        """Test extracting Cypher from response with explanation"""
        response = """Here is the query:
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)
WHERE c.company_name CONTAINS 'Kajaria'
RETURN c.company_name, p.parameter_name"""
        
        result = self.graph_rag._extract_cypher_query(response)
        self.assertIn("MATCH", result)
        self.assertIn("HAS_PARAMETER", result)
        self.assertNotIn("Here is", result)
    
    def test_extract_cypher_from_text_code_block(self):
        """Test extracting Cypher from code block"""
        text = """
        Some explanation here
        ```cypher
        MATCH (c:Company) RETURN c.company_name
        ```
        More text after
        """
        
        result = self.graph_rag._extract_cypher_from_text(text)
        self.assertIn("MATCH", result)
        self.assertIn("Company", result)
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_fallback_query_parameter_query(self, mock_schema):
        """Test fallback query generation for parameter queries"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        fallback_query = self.graph_rag._generate_fallback_query(question)
        
        # Should generate parameter query
        self.assertIn('HAS_PARAMETER', fallback_query.upper())
        self.assertIn('PERIODRESULT', fallback_query.upper())
        self.assertIn('Kajaria', fallback_query)
        self.assertIn('EBITDA margin', fallback_query)
        self.assertIn('Net profit', fallback_query)
        self.assertIn('3QFY-2024', fallback_query)
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_generate_fallback_query_company_only(self, mock_schema):
        """Test fallback query generation for company queries"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "Show me companies in Technology sector"
        fallback_query = self.graph_rag._generate_fallback_query(question)
        
        # Should generate company query (not parameter query)
        self.assertIn('MATCH', fallback_query.upper())
        self.assertIn('COMPANY', fallback_query.upper())
        # Should not have parameter relationships
        self.assertNotIn('HAS_PARAMETER', fallback_query.upper())
    
    def test_decompose_operation_detection(self):
        """Test operation type detection in decomposition"""
        # Comparison operation
        question1 = "Compare revenue of Kajaria in Q1 and Q2"
        with patch.object(self.graph_rag, 'get_dynamic_schema_context', return_value=self.mock_schema_context):
            decomp1 = self.graph_rag._decompose_parameter_query(question1)
            self.assertEqual(decomp1['operation'], 'compare')
        
        # Aggregate operation
        question2 = "Sum of all revenue for Kajaria"
        with patch.object(self.graph_rag, 'get_dynamic_schema_context', return_value=self.mock_schema_context):
            decomp2 = self.graph_rag._decompose_parameter_query(question2)
            self.assertEqual(decomp2['operation'], 'aggregate')
        
        # Retrieve operation (default)
        question3 = "Revenue of Kajaria"
        with patch.object(self.graph_rag, 'get_dynamic_schema_context', return_value=self.mock_schema_context):
            decomp3 = self.graph_rag._decompose_parameter_query(question3)
            self.assertEqual(decomp3['operation'], 'retrieve')


class TestIntegration(unittest.TestCase):
    """Integration tests for end-to-end query processing"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        self.graph_rag = PEERSGraphRAG(log_manager=self.log_manager)
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_full_decomposition_flow(self, mock_schema):
        """Test full flow: question -> decomposition -> query generation"""
        mock_schema.return_value = {
            'companies': ['Kajaria Ceramics'],
            'parameters': ['EBITDA margin', 'Net profit'],
            'periods': ['3QFY-2024'],
            'sectors': [],
            'industries': [],
            'countries': [],
            'regions': [],
            'exchanges': []
        }
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        
        # Step 1: Decomposition
        decomposition = self.graph_rag._decompose_parameter_query(question)
        
        # Verify decomposition
        self.assertEqual(decomposition['company'], 'Kajaria Ceramics')
        self.assertEqual(len(decomposition['parameters']), 2)
        self.assertTrue(decomposition['is_multi_parameter'])
        
        # Step 2: Query generation
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Verify query
        self.assertTrue(self.graph_rag._is_valid_cypher(query))
        self.assertTrue(self.graph_rag._query_has_parameters(query))
        self.assertIn('Kajaria', query)
        self.assertIn('3QFY-2024', query)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)


