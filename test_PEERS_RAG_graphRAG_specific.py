"""
Specific test cases for the user's query: "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
"""

import unittest
from unittest.mock import patch
import sys
import os

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


class TestSpecificQuery(unittest.TestCase):
    """Test the specific query the user asked about"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        self.graph_rag = PEERSGraphRAG(log_manager=self.log_manager)
        
        self.mock_schema_context = {
            'companies': ['Kajaria Ceramics', 'Bajaj Finance Limited'],
            'parameters': ['Total revenue, Primary', 'EBITDA margin', 'Net profit'],
            'periods': ['1QFY-2024', '2QFY-2024', '3QFY-2024', '4QFY-2024'],
            'sectors': [],
            'industries': [],
            'countries': [],
            'regions': [],
            'exchanges': []
        }
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_user_query_decomposition(self, mock_schema):
        """Test decomposition of: 'EBITDA margin and Net profit of Kajaria in Q3FY-2024'"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        
        # Verify all components
        self.assertEqual(decomposition['company'], 'Kajaria Ceramics', 
                        "Should detect Kajaria Ceramics")
        self.assertIn('EBITDA margin', decomposition['parameters'],
                     "Should detect EBITDA margin")
        self.assertIn('Net profit', decomposition['parameters'],
                     "Should detect Net profit")
        self.assertEqual(len(decomposition['parameters']), 2,
                        "Should have exactly 2 parameters")
        self.assertTrue(decomposition['is_multi_parameter'],
                       "Should flag as multi-parameter query")
        self.assertEqual(decomposition['period'], '3QFY-2024',
                        "Should detect Q3FY-2024 period")
        self.assertEqual(decomposition['operation'], 'retrieve',
                        "Should be a retrieve operation")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_user_query_generated_cypher(self, mock_schema):
        """Test Cypher query generated for user's query"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Verify query structure
        query_upper = query.upper()
        self.assertIn('MATCH', query_upper)
        self.assertIn('HAS_PARAMETER', query_upper)
        self.assertIn('HAS_VALUE_IN_PERIOD', query_upper)
        self.assertIn('PERIODRESULT', query_upper)
        self.assertIn('RETURN', query_upper)
        self.assertIn('WHERE', query_upper)
        
        # Verify query content
        self.assertIn('Kajaria', query)
        self.assertIn('3QFY-2024', query)
        self.assertIn('EBITDA margin', query)
        self.assertIn('Net profit', query)
        self.assertIn('OR', query_upper)  # Should have OR for multiple parameters
        
        # Verify query is valid
        self.assertTrue(self.graph_rag._is_valid_cypher(query))
        self.assertTrue(self.graph_rag._query_has_parameters(query))
        
        # Should order by parameter name for multi-parameter queries
        self.assertIn('ORDER BY', query_upper)
        self.assertIn('parameter_name', query.lower())
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_user_query_fallback_generation(self, mock_schema):
        """Test fallback query generation for user's query"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        fallback_query = self.graph_rag._generate_fallback_query(question)
        
        # Should generate correct parameter query
        self.assertTrue(self.graph_rag._is_valid_cypher(fallback_query))
        self.assertTrue(self.graph_rag._query_has_parameters(fallback_query))
        self.assertIn('Kajaria', fallback_query)
        self.assertIn('3QFY-2024', fallback_query)
        self.assertIn('EBITDA margin', fallback_query)
        self.assertIn('Net profit', fallback_query)
    
    def test_query_not_basic_company_query(self):
        """Ensure the query is NOT the basic 'MATCH (c:Company) RETURN...' query"""
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        
        with patch.object(self.graph_rag, 'get_dynamic_schema_context', return_value=self.mock_schema_context):
            decomposition = self.graph_rag._decompose_parameter_query(question)
            query = self.graph_rag._generate_decomposed_query(decomposition)
            
            # Should NOT be the basic company query
            basic_query = "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
            self.assertNotEqual(query, basic_query)
            self.assertNotIn("LIMIT 10", query)  # Should have proper structure, not basic limit
        
            # Should have parameter relationships
            self.assertIn('HAS_PARAMETER', query.upper())


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.log_manager = MockLogManager()
        self.graph_rag = PEERSGraphRAG(log_manager=self.log_manager)
        
        self.mock_schema_context = {
            'companies': ['Kajaria Ceramics'],
            'parameters': ['EBITDA margin', 'Net profit'],
            'periods': ['3QFY-2024'],
            'sectors': [],
            'industries': [],
            'countries': [],
            'regions': [],
            'exchanges': []
        }
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_case_insensitive_company_detection(self, mock_schema):
        """Test that company detection is case insensitive"""
        mock_schema.return_value = self.mock_schema_context
        
        variations = [
            "EBITDA margin of kajaria in Q3FY-2024",
            "EBITDA margin of KAJARIA in Q3FY-2024",
            "EBITDA margin of KaJaRiA in Q3FY-2024",
        ]
        
        for question in variations:
            decomposition = self.graph_rag._decompose_parameter_query(question)
            self.assertEqual(decomposition['company'], 'Kajaria Ceramics',
                           f"Should detect company in: {question}")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_case_insensitive_parameter_detection(self, mock_schema):
        """Test that parameter detection is case insensitive"""
        mock_schema.return_value = self.mock_schema_context
        
        variations = [
            "ebitda margin of Kajaria",
            "EBITDA MARGIN of Kajaria",
            "Ebitda Margin of Kajaria",
            "net profit of Kajaria",
            "NET PROFIT of Kajaria",
        ]
        
        for question in variations:
            decomposition = self.graph_rag._decompose_parameter_query(question.lower())
            self.assertGreater(len(decomposition['parameters']), 0,
                             f"Should detect parameter in: {question}")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_period_variations(self, mock_schema):
        """Test different period formats"""
        mock_schema.return_value = self.mock_schema_context
        
        period_tests = [
            ("Q3FY-2024", "3QFY-2024"),
            ("q3fy-2024", "3QFY-2024"),
            ("3QFY-2024", "3QFY-2024"),
            ("3qfy-2024", "3QFY-2024"),
        ]
        
        for period_input, expected_period in period_tests:
            question = f"EBITDA margin of Kajaria in {period_input}"
            decomposition = self.graph_rag._decompose_parameter_query(question)
            self.assertEqual(decomposition['period'], expected_period,
                           f"Should detect period {expected_period} from {period_input}")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_empty_decomposition_handling(self, mock_schema):
        """Test handling when decomposition has minimal info"""
        mock_schema.return_value = self.mock_schema_context
        
        decomposition = {
            'company': None,
            'parameters': [],
            'period': None,
            'operation': 'retrieve',
            'is_multi_parameter': False
        }
        
        # Should still generate valid query
        query = self.graph_rag._generate_decomposed_query(decomposition)
        self.assertTrue(self.graph_rag._is_valid_cypher(query))
        self.assertIn('MATCH', query.upper())
    
    def test_extract_cypher_with_apology(self):
        """Test extraction when LLM returns apology"""
        apology_response = "I'm sorry, but I cannot assist with that request as it is not specific enough."
        
        result = self.graph_rag._extract_cypher_query(apology_response)
        # Should return the text (which will be caught by validation)
        self.assertEqual(result, apology_response)
        
        # Validation should catch it
        self.assertFalse(self.graph_rag._is_valid_cypher(result))


if __name__ == '__main__':
    unittest.main(verbosity=2)


