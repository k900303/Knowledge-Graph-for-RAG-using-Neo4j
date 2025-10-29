"""
Test to verify Cypher query spacing is correct
Specifically tests the bug where ORDER BY was missing space before it
"""

import unittest
from unittest.mock import patch
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PEERS_RAG_graphRAG import PEERSGraphRAG


class MockLogManager:
    def __init__(self):
        self.logs = []
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))


class TestQuerySpacing(unittest.TestCase):
    """Test that generated Cypher queries have proper spacing"""
    
    def setUp(self):
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
    def test_user_query_has_proper_spacing(self, mock_schema):
        """Test the specific user query has proper spacing before ORDER BY"""
        mock_schema.return_value = self.mock_schema_context
        
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        decomposition = self.graph_rag._decompose_parameter_query(question)
        query = self.graph_rag._generate_decomposed_query(decomposition)
        
        # Check that there's a space before ORDER BY
        self.assertIn('ORDER BY', query.upper())
        
        # Find ORDER BY in the query
        order_by_match = re.search(r'ORDER BY', query, re.IGNORECASE)
        if order_by_match:
            # Get the character before ORDER BY
            pos = order_by_match.start()
            if pos > 0:
                char_before = query[pos - 1]
                self.assertEqual(char_before, ' ', 
                             f"Expected space before ORDER BY, but found '{char_before}'. Query: {query}")
        
        # Check that RETURN and ORDER BY are separated
        return_match = re.search(r'RETURN.*yoy_growth', query, re.IGNORECASE)
        order_by_match = re.search(r'ORDER BY', query, re.IGNORECASE)
        
        if return_match and order_by_match:
            return_end = return_match.end()
            order_by_start = order_by_match.start()
            
            # There should be at least one space between them
            text_between = query[return_end:order_by_start]
            self.assertIn(' ', text_between,
                         f"No space found between RETURN and ORDER BY. Text between: '{text_between}'")
    
    @patch.object(PEERSGraphRAG, 'get_dynamic_schema_context')
    def test_all_generated_queries_have_proper_spacing(self, mock_schema):
        """Test that all query generation methods produce properly spaced queries"""
        mock_schema.return_value = self.mock_schema_context
        
        # Test different scenarios
        test_cases = [
            {
                'question': "EBITDA margin and Net profit of Kajaria in Q3FY-2024",
                'has_order_by': True,
                'has_limit': False
            },
            {
                'question': "Revenue of Kajaria latest",
                'has_order_by': True,
                'has_limit': True
            },
            {
                'question': "Net profit of Kajaria",
                'has_order_by': True,
                'has_limit': False
            }
        ]
        
        for test_case in test_cases:
            question = test_case['question']
            
            # Test decomposition query
            decomposition = self.graph_rag._decompose_parameter_query(question)
            query = self.graph_rag._generate_decomposed_query(decomposition)
            
            # Test fallback query
            fallback_query = self.graph_rag._generate_fallback_query(question)
            
            for query_name, test_query in [('decomposition', query), ('fallback', fallback_query)]:
                # Check spacing around ORDER BY
                if 'ORDER BY' in test_query.upper():
                    order_pos = test_query.upper().find('ORDER BY')
                    if order_pos > 0:
                        char_before = test_query[order_pos - 1]
                        self.assertEqual(char_before, ' ',
                                       f"{query_name} query missing space before ORDER BY: {test_query}")
                
                # Check spacing around LIMIT
                if 'LIMIT' in test_query.upper():
                    limit_pos = test_query.upper().find('LIMIT')
                    if limit_pos > 0:
                        char_before = test_query[limit_pos - 1]
                        self.assertEqual(char_before, ' ',
                                       f"{query_name} query missing space before LIMIT: {test_query}")
                
                # Validate query syntax (should not have syntax errors)
                # Check for common syntax errors
                self.assertNotIn('RETURN', test_query.upper().replace(' RETURN ', ' RETURN '))
                self.assertNotIn('yoy_growthORDER', test_query)
                self.assertNotIn('yoy_growthLIMIT', test_query)
                self.assertNotIn('ORDER BYLIMIT', test_query.upper())
    
    def test_query_matches_expected_format(self):
        """Test that generated query matches expected format for user's specific query"""
        question = "EBITDA margin and Net profit of Kajaria in Q3FY-2024"
        
        with patch.object(self.graph_rag, 'get_dynamic_schema_context', return_value=self.mock_schema_context):
            decomposition = self.graph_rag._decompose_parameter_query(question)
            query = self.graph_rag._generate_decomposed_query(decomposition)
            
            # Expected pattern: ...RETURN ... ORDER BY ...
            pattern = r'RETURN\s+[\w\s,]+\s+ORDER\s+BY'
            self.assertRegex(query, pattern, 
                           f"Query doesn't match expected format: {query}")
            
            # Should not have missing spaces
            problematic_patterns = [
                r'yoy_growthORDER',
                r'yoy_growthLIMIT',
                r'ORDER BYLIMIT',
                r'RETURN.*ORDER',  # Without space between
            ]
            
            for pattern in problematic_patterns:
                self.assertNotRegex(query, pattern,
                                  f"Query has problematic pattern '{pattern}': {query}")


if __name__ == '__main__':
    unittest.main(verbosity=2)

