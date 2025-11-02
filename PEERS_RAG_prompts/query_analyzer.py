"""
Query Analyzer

Analyzes user queries to determine which prompt extensions are needed.
This enables dynamic prompt composition - only load what's necessary.
"""

import re
from typing import Dict, List, Set


class QueryAnalyzer:
    """Analyzes queries to detect what capabilities are needed"""
    
    # Keywords that indicate different query types
    PARAMETER_KEYWORDS = [
        'revenue', 'profit', 'margin', 'ebita', 'ebitda', 'operating',
        'net income', 'cost', 'expense', 'parameter', 'metric', 'financial',
        'earnings', 'sales', 'turnover'
    ]
    
    PERIOD_KEYWORDS = [
        'quarter', 'q1', 'q2', 'q3', 'q4', 'fy', 'fiscal', 'year',
        'latest', 'recent', 'period', 'month', 'annual', 'quarterly'
    ]
    
    COMPARISON_KEYWORDS = [
        'compare', 'comparison', 'versus', 'vs', 'between', 'and',
        'against', 'difference', 'versus', 'versus', 'contrast'
    ]
    
    TREND_KEYWORDS = [
        'trend', 'growth', 'over time', 'across', 'progression',
        'change', 'increase', 'decrease', 'yoy', 'year over year'
    ]
    
    def __init__(self, log_manager=None):
        """Initialize query analyzer"""
        self.log_manager = log_manager
    
    def analyze(self, query: str) -> Dict[str, bool]:
        """
        Analyze query and detect what extensions are needed
        
        Args:
            query: User's query string
            
        Returns:
            Dictionary with boolean flags for each extension need
        """
        query_lower = query.lower()
        
        # Detect parameter mentions
        needs_parameters = any(
            keyword in query_lower 
            for keyword in self.PARAMETER_KEYWORDS
        )
        
        # Detect period mentions
        needs_periods = any(
            keyword in query_lower 
            for keyword in self.PERIOD_KEYWORDS
        )
        
        # Detect comparison (multiple companies)
        # Look for comparison keywords AND multiple company names
        has_comparison_keywords = any(
            keyword in query_lower 
            for keyword in self.COMPARISON_KEYWORDS
        )
        
        # Detect multiple companies (simple heuristic: look for "and" or "," with company context)
        companies = self._extract_company_mentions(query)
        needs_comparison = has_comparison_keywords or len(companies) > 1
        
        # Detect multiple periods
        periods = self._extract_periods(query)
        needs_multi_period = len(periods) > 1 or any(
            keyword in query_lower 
            for keyword in ['multiple', 'all quarters', 'last 4', 'across']
        )
        
        # Detect trend analysis
        needs_trend = any(
            keyword in query_lower 
            for keyword in self.TREND_KEYWORDS
        ) or needs_multi_period
        
        result = {
            'needs_parameters': needs_parameters,
            'needs_periods': needs_periods,
            'needs_comparison': needs_comparison,
            'needs_multi_period': needs_multi_period,
            'needs_trend': needs_trend,
        }
        
        # Log analysis for debugging
        if self.log_manager:
            active_extensions = [k.replace('needs_', '') for k, v in result.items() if v]
            self.log_manager.add_info_log(
                f'Query Analysis: Detected needs -> {", ".join(active_extensions) if active_extensions else "base only"}'
            )
        
        return result
    
    def _extract_company_mentions(self, query: str) -> List[str]:
        """
        Extract potential company names from query
        Simple heuristic-based extraction
        """
        # Look for patterns like "Company A and Company B" or "Company A, Company B"
        # This is a simple implementation - can be enhanced with NLP
        companies = []
        
        # Look for "and" or "," with capitalized words (potential company names)
        # Split on common separators
        parts = re.split(r'\s+(and|&|,|versus|vs)\s+', query, flags=re.IGNORECASE)
        
        for part in parts:
            # Extract capitalized phrases (potential company names)
            # This is a heuristic - real implementation might use NER
            capitalized_phrases = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', part)
            companies.extend(capitalized_phrases)
        
        return companies
    
    def _extract_periods(self, query: str) -> List[str]:
        """
        Extract period mentions from query
        Returns list of detected period strings
        """
        periods = []
        
        # Look for quarter patterns
        quarter_patterns = [
            r'\b(q[1-4]|quarter\s+[1-4])\s*(?:of\s+)?(?:fy|fiscal\s+year)?\s*(\d{4})',
            r'\b(fy|fiscal\s+year)\s*(\d{4})\s*(?:q[1-4]|quarter\s+[1-4])',
            r'\b([1-4]qfy|q[1-4]fy)\s*-?\s*(\d{4})',
        ]
        
        for pattern in quarter_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            periods.extend([' '.join(m).strip() for m in matches])
        
        # Look for fiscal year mentions
        fy_matches = re.findall(r'\b(fy|fiscal\s+year)\s*-?\s*(\d{4})', query, re.IGNORECASE)
        periods.extend([' '.join(m).strip() for m in fy_matches])
        
        # Look for "latest", "recent", "last N quarters"
        if re.search(r'\b(latest|recent|last)\b', query, re.IGNORECASE):
            periods.append('latest')
        
        return periods
    
    def get_required_extensions(self, query: str) -> List[str]:
        """
        Get list of extension keys needed for this query
        
        Returns:
            List of extension keys to load
        """
        analysis = self.analyze(query)
        
        extensions = []
        
        if analysis['needs_parameters']:
            extensions.append('parameter_query')
        
        if analysis['needs_periods']:
            extensions.append('period_handling')
        
        if analysis['needs_comparison']:
            extensions.append('comparison_query')
        
        if analysis['needs_multi_period'] or analysis['needs_trend']:
            extensions.append('multi_period')
        
        return extensions

