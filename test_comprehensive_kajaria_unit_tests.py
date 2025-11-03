"""
Comprehensive Unit Tests for Kajaria Queries
Tests all use cases with actual result validation
"""

import sys
from typing import Dict, List, Any, Optional
from PEERS_RAG_graphRAG import PEERSGraphRAG
from PEERS_RAG_flask_app import LogManager
from neo4j_env import graph

class TestResult:
    """Test result container"""
    def __init__(self, test_name: str, passed: bool, message: str, 
                 expected: Any = None, actual: Any = None, details: str = ""):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.expected = expected
        self.actual = actual
        self.details = details

class ComprehensiveKajariaTester:
    """Comprehensive test suite for Kajaria queries"""
    
    def __init__(self):
        self.log_manager = LogManager()
        self.graph_rag = PEERSGraphRAG(log_manager=self.log_manager)
        self.test_results: List[TestResult] = []
        self.company_name = "Kajaria"
        self.company_cid = "18315"
    
    def run_all_tests(self):
        """Run all test cases"""
        print("=" * 100)
        print("COMPREHENSIVE UNIT TESTS: KAJARIA QUERIES")
        print("=" * 100)
        print()
        
        # Test Suite 1: Company Details
        self.test_company_details()
        
        # Test Suite 2: Single Parameter - Latest Period
        self.test_single_parameter_latest()
        
        # Test Suite 3: Single Parameter - Specific Quarters
        self.test_single_parameter_quarters()
        
        # Test Suite 4: Single Parameter - Full Year
        self.test_single_parameter_full_year()
        
        # Test Suite 5: Single Parameter - Half Year
        self.test_single_parameter_half_year()
        
        # Test Suite 6: Multiple Parameters - Latest Period
        self.test_multiple_parameters_latest()
        
        # Test Suite 7: Multiple Parameters - Multiple Quarters
        self.test_multiple_parameters_quarters()
        
        # Test Suite 8: Multiple Parameters - Full Year
        self.test_multiple_parameters_full_year()
        
        # Test Suite 9: Period Variations
        self.test_period_variations()
        
        # Test Suite 10: Parameter Name Variations
        self.test_parameter_name_variations()
        
        # Print summary
        self.print_summary()
    
    def test_company_details(self):
        """Test 1: Company Details Query"""
        print("=" * 100)
        print("TEST SUITE 1: COMPANY DETAILS")
        print("=" * 100)
        
        query = f"What are the company details for {self.company_name}?"
        test_name = "Company Details Query"
        
        try:
            # Generate and execute
            cypher = self.graph_rag.generate_cypher_query(query)
            if not cypher or "MATCH" not in cypher:
                self._add_failure(test_name, "No valid Cypher query generated", query)
                return
            
            results = self.graph_rag.execute_cypher_query(cypher)
            
            # Validate results
            if not results or len(results) == 0:
                self._add_failure(test_name, "No results returned", query)
                return
            
            first_result = results[0]
            if not isinstance(first_result, dict):
                self._add_failure(test_name, "Result is not a dictionary", query)
                return
            
            # Check for required fields
            company_name = first_result.get('c.company_name', first_result.get('company_name', ''))
            cid = first_result.get('c.cid', first_result.get('cid', ''))
            
            expected_name_contains = "Kajaria"
            expected_cid = self.company_cid
            
            name_correct = expected_name_contains.lower() in company_name.lower() if company_name else False
            cid_correct = str(cid) == expected_cid if cid else False
            
            if name_correct and cid_correct:
                self._add_success(test_name, f"Company: {company_name}, CID: {cid}", query)
            else:
                self._add_failure(test_name, 
                    f"Expected name containing '{expected_name_contains}' and CID '{expected_cid}', "
                    f"got name '{company_name}' and CID '{cid}'", query)
        
        except Exception as e:
            self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_single_parameter_latest(self):
        """Test 2: Single Parameter - Latest Period"""
        print("\n" + "=" * 100)
        print("TEST SUITE 2: SINGLE PARAMETER - LATEST PERIOD")
        print("=" * 100)
        
        parameters = ["EBITDA margin", "Revenue", "Profit"]
        
        for param in parameters:
            query = f"What is the {param.lower()} of {self.company_name} for latest period?"
            test_name = f"Latest Period - {param}"
            
            try:
                cypher = self.graph_rag.generate_cypher_query(query)
                if not cypher or "MATCH" not in cypher:
                    self._add_failure(test_name, "No valid Cypher query generated", query)
                    continue
                
                results = self.graph_rag.execute_cypher_query(cypher)
                
                if not results:
                    self._add_failure(test_name, "No results returned", query)
                    continue
                
                # Check if results are for Kajaria
                company_names = set()
                periods = set()
                params_found = set()
                
                for result in results:
                    if isinstance(result, dict):
                        comp_name = result.get('c.company_name', result.get('company_name', ''))
                        period = result.get('pr.period', result.get('period', ''))
                        param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                        
                        if comp_name:
                            company_names.add(comp_name)
                        if period:
                            periods.add(period)
                        if param_name:
                            params_found.add(param_name)
                
                # Validate
                company_correct = any("kajaria" in name.lower() for name in company_names)
                param_correct = any(param.lower() in p.lower() for p in params_found)
                has_period = len(periods) > 0
                has_value = len(results) > 0
                
                if company_correct and param_correct and has_period and has_value:
                    latest_period = sorted(periods, reverse=True)[0]
                    self._add_success(test_name, 
                        f"Found {len(results)} records, Latest period: {latest_period}", query)
                else:
                    self._add_failure(test_name,
                        f"Company correct: {company_correct}, Param correct: {param_correct}, "
                        f"Has period: {has_period}, Has value: {has_value}", query)
            
            except Exception as e:
                self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_single_parameter_quarters(self):
        """Test 3: Single Parameter - Specific Quarters"""
        print("\n" + "=" * 100)
        print("TEST SUITE 3: SINGLE PARAMETER - SPECIFIC QUARTERS")
        print("=" * 100)
        
        quarters = ["Q1FY2025", "Q2FY2025", "Q3FY2025", "Q4FY2025"]
        parameter = "EBITDA margin"
        
        for quarter in quarters:
            # Test multiple query formats
            query_formats = [
                f"What is the {parameter.lower()} of {self.company_name} for {quarter}?",
                f"{parameter} of {self.company_name} {quarter}",
                f"Show {parameter.lower()} {self.company_name} {quarter}"
            ]
            
            for query in query_formats:
                test_name = f"Quarter Query - {quarter} ({query_formats.index(query) + 1})"
                
                try:
                    cypher = self.graph_rag.generate_cypher_query(query)
                    if not cypher or "MATCH" not in cypher:
                        self._add_failure(test_name, "No valid Cypher query generated", query)
                        continue
                    
                    # Check if period is correctly extracted and used
                    # Expected normalized format: 1QFY-2025, 2QFY-2025, etc.
                    expected_period = self._normalize_quarter(quarter)
                    
                    # Check if query contains the correct period
                    period_in_query = expected_period in cypher or quarter.upper() in cypher.upper()
                    
                    results = self.graph_rag.execute_cypher_query(cypher)
                    
                    if not results:
                        # Check if period exists in database first
                        period_exists = self._check_period_exists(expected_period)
                        if not period_exists:
                            self._add_skip(test_name, f"Period {expected_period} does not exist in database", query)
                        else:
                            self._add_failure(test_name, "No results returned but period exists", query)
                        continue
                    
                    # Validate results
                    periods_in_results = set()
                    company_correct = False
                    param_correct = False
                    
                    for result in results:
                        if isinstance(result, dict):
                            comp_name = result.get('c.company_name', result.get('company_name', ''))
                            period = result.get('pr.period', result.get('period', ''))
                            param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                            
                            if period:
                                periods_in_results.add(period)
                            if comp_name and "kajaria" in comp_name.lower():
                                company_correct = True
                            if param_name and parameter.lower() in param_name.lower():
                                param_correct = True
                    
                    # Check if correct period is in results
                    period_correct = expected_period in periods_in_results or any(
                        expected_period.split('-')[0] in p for p in periods_in_results
                    )
                    
                    if company_correct and param_correct and period_correct:
                        actual_period = periods_in_results.pop() if periods_in_results else "N/A"
                        self._add_success(test_name,
                            f"Found results for period: {actual_period}", query)
                    else:
                        self._add_failure(test_name,
                            f"Company: {company_correct}, Param: {param_correct}, "
                            f"Period: {period_correct} (Expected: {expected_period}, Got: {periods_in_results})", query)
                
                except Exception as e:
                    self._add_failure(test_name, f"Exception: {str(e)}", query)
                    import traceback
                    self._add_failure(test_name, f"Traceback: {traceback.format_exc()}", query)
    
    def test_single_parameter_full_year(self):
        """Test 4: Single Parameter - Full Year"""
        print("\n" + "=" * 100)
        print("TEST SUITE 4: SINGLE PARAMETER - FULL YEAR")
        print("=" * 100)
        
        years = ["FY2024", "FY2025", "FY2023"]
        parameter = "EBITDA margin"
        
        for year in years:
            query = f"What is the {parameter.lower()} of {self.company_name} for {year}?"
            test_name = f"Full Year - {year}"
            
            try:
                cypher = self.graph_rag.generate_cypher_query(query)
                if not cypher or "MATCH" not in cypher:
                    self._add_failure(test_name, "No valid Cypher query generated", query)
                    continue
                
                # Expected format: FY-2024, FY-2025, etc.
                expected_period = f"FY-{year[-4:]}"
                
                results = self.graph_rag.execute_cypher_query(cypher)
                
                if not results:
                    period_exists = self._check_period_exists(expected_period)
                    if not period_exists:
                        self._add_skip(test_name, f"Period {expected_period} does not exist", query)
                    else:
                        self._add_failure(test_name, "No results but period exists", query)
                    continue
                
                # Validate
                periods_in_results = set()
                for result in results:
                    if isinstance(result, dict):
                        period = result.get('pr.period', result.get('period', ''))
                        if period:
                            periods_in_results.add(period)
                
                period_correct = expected_period in periods_in_results
                
                if period_correct and len(results) > 0:
                    self._add_success(test_name, f"Found {len(results)} records for {expected_period}", query)
                else:
                    self._add_failure(test_name,
                        f"Expected period {expected_period}, got {periods_in_results}", query)
            
            except Exception as e:
                self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_single_parameter_half_year(self):
        """Test 5: Single Parameter - Half Year"""
        print("\n" + "=" * 100)
        print("TEST SUITE 5: SINGLE PARAMETER - HALF YEAR")
        print("=" * 100)
        
        half_years = ["1HFY2025", "2HFY2025"]
        parameter = "EBITDA margin"
        
        for half_year in half_years:
            query = f"What is the {parameter.lower()} of {self.company_name} for {half_year}?"
            test_name = f"Half Year - {half_year}"
            
            try:
                cypher = self.graph_rag.generate_cypher_query(query)
                if not cypher or "MATCH" not in cypher:
                    self._add_failure(test_name, "No valid Cypher query generated", query)
                    continue
                
                # Expected format: 1HFY-2025, 2HFY-2025
                expected_period = f"{half_year[0]}HFY-{half_year[-4:]}"
                
                results = self.graph_rag.execute_cypher_query(cypher)
                
                if not results:
                    period_exists = self._check_period_exists(expected_period)
                    if not period_exists:
                        self._add_skip(test_name, f"Period {expected_period} may not exist", query)
                    else:
                        self._add_failure(test_name, "No results but period exists", query)
                    continue
                
                periods_in_results = set()
                for result in results:
                    if isinstance(result, dict):
                        period = result.get('pr.period', result.get('period', ''))
                        if period:
                            periods_in_results.add(period)
                
                if len(results) > 0:
                    self._add_success(test_name, f"Found {len(results)} records", query)
                else:
                    self._add_failure(test_name, "No results returned", query)
            
            except Exception as e:
                self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_multiple_parameters_latest(self):
        """Test 6: Multiple Parameters - Latest Period"""
        print("\n" + "=" * 100)
        print("TEST SUITE 6: MULTIPLE PARAMETERS - LATEST PERIOD")
        print("=" * 100)
        
        query = f"Show me revenue and EBITDA margin of {self.company_name} for latest period"
        test_name = "Multiple Parameters - Latest"
        
        try:
            cypher = self.graph_rag.generate_cypher_query(query)
            if not cypher or "MATCH" not in cypher:
                self._add_failure(test_name, "No valid Cypher query generated", query)
                return
            
            results = self.graph_rag.execute_cypher_query(cypher)
            
            if not results:
                self._add_failure(test_name, "No results returned", query)
                return
            
            # Check for both parameters
            params_found = set()
            for result in results:
                if isinstance(result, dict):
                    param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                    if param_name:
                        params_found.add(param_name.lower())
            
            has_revenue = any("revenue" in p for p in params_found)
            has_ebitda_margin = any("ebitda" in p and "margin" in p for p in params_found)
            
            if has_revenue and has_ebitda_margin:
                self._add_success(test_name, f"Found both parameters, {len(results)} total records", query)
            else:
                self._add_failure(test_name,
                    f"Revenue: {has_revenue}, EBITDA margin: {has_ebitda_margin}", query)
        
        except Exception as e:
            self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_multiple_parameters_quarters(self):
        """Test 7: Multiple Parameters - Multiple Quarters"""
        print("\n" + "=" * 100)
        print("TEST SUITE 7: MULTIPLE PARAMETERS - MULTIPLE QUARTERS")
        print("=" * 100)
        
        query = f"Show me revenue and EBITDA margin of {self.company_name} for Q1, Q2, Q3 of FY2025"
        test_name = "Multiple Parameters - Multiple Quarters"
        
        try:
            cypher = self.graph_rag.generate_cypher_query(query)
            if not cypher or "MATCH" not in cypher:
                self._add_failure(test_name, "No valid Cypher query generated", query)
                return
            
            results = self.graph_rag.execute_cypher_query(cypher)
            
            if not results:
                self._add_failure(test_name, "No results returned", query)
                return
            
            # Check for multiple periods
            periods_found = set()
            params_found = set()
            
            for result in results:
                if isinstance(result, dict):
                    period = result.get('pr.period', result.get('period', ''))
                    param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                    if period:
                        periods_found.add(period)
                    if param_name:
                        params_found.add(param_name.lower())
            
            # Should have multiple periods (Q1, Q2, Q3)
            has_multiple_periods = len(periods_found) >= 2
            has_both_params = any("revenue" in p for p in params_found) and any("ebitda" in p and "margin" in p for p in params_found)
            
            if has_multiple_periods and has_both_params:
                self._add_success(test_name,
                    f"Found {len(periods_found)} periods, {len(results)} records", query)
            else:
                self._add_failure(test_name,
                    f"Multiple periods: {has_multiple_periods} ({len(periods_found)} found), "
                    f"Both params: {has_both_params}", query)
        
        except Exception as e:
            self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_multiple_parameters_full_year(self):
        """Test 8: Multiple Parameters - Full Year"""
        print("\n" + "=" * 100)
        print("TEST SUITE 8: MULTIPLE PARAMETERS - FULL YEAR")
        print("=" * 100)
        
        query = f"Show revenue and EBITDA margin of {self.company_name} for FY2024"
        test_name = "Multiple Parameters - Full Year"
        
        try:
            cypher = self.graph_rag.generate_cypher_query(query)
            if not cypher or "MATCH" not in cypher:
                self._add_failure(test_name, "No valid Cypher query generated", query)
                return
            
            results = self.graph_rag.execute_cypher_query(cypher)
            
            if not results:
                self._add_failure(test_name, "No results returned", query)
                return
            
            periods_found = set()
            params_found = set()
            
            for result in results:
                if isinstance(result, dict):
                    period = result.get('pr.period', result.get('period', ''))
                    param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                    if period:
                        periods_found.add(period)
                    if param_name:
                        params_found.add(param_name.lower())
            
            has_fy2024 = any("FY-2024" in p for p in periods_found)
            has_both_params = any("revenue" in p for p in params_found) and any("ebitda" in p and "margin" in p for p in params_found)
            
            if has_fy2024 and has_both_params:
                self._add_success(test_name, f"Found {len(results)} records for FY2024", query)
            else:
                self._add_failure(test_name,
                    f"FY2024: {has_fy2024}, Both params: {has_both_params}", query)
        
        except Exception as e:
            self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_period_variations(self):
        """Test 9: Period Format Variations"""
        print("\n" + "=" * 100)
        print("TEST SUITE 9: PERIOD FORMAT VARIATIONS")
        print("=" * 100)
        
        period_variations = [
            ("Q1FY2025", "1QFY-2025"),
            ("FY2025Q1", "1QFY-2025"),
            ("1QFY2025", "1QFY-2025"),
            ("1QFY-2025", "1QFY-2025"),
            ("quarter 1 of 2025", "1QFY-2025"),
        ]
        
        parameter = "EBITDA margin"
        
        for input_format, expected_period in period_variations:
            query = f"{parameter} of {self.company_name} {input_format}"
            test_name = f"Period Format - '{input_format}'"
            
            try:
                cypher = self.graph_rag.generate_cypher_query(query)
                if not cypher:
                    self._add_failure(test_name, "No Cypher generated", query)
                    continue
                
                # Check if query uses correct period format
                period_used_correctly = expected_period in cypher or input_format.upper() in cypher.upper()
                
                results = self.graph_rag.execute_cypher_query(cypher)
                
                if period_used_correctly or (results and len(results) > 0):
                    self._add_success(test_name, f"Query generated and executed", query)
                else:
                    self._add_failure(test_name, "Period format not correctly used", query)
            
            except Exception as e:
                self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    def test_parameter_name_variations(self):
        """Test 10: Parameter Name Variations"""
        print("\n" + "=" * 100)
        print("TEST SUITE 10: PARAMETER NAME VARIATIONS")
        print("=" * 100)
        
        variations = [
            "EBITDA margin",
            "ebitda margin",
            "EBITDA Margin",
            "EBITDA MARGIN",
            "ebitda",
            "revenue",
            "Revenue",
            "profit",
        ]
        
        for param_variation in variations:
            query = f"{param_variation} of {self.company_name} latest"
            test_name = f"Parameter Name Variation - '{param_variation}'"
            
            try:
                cypher = self.graph_rag.generate_cypher_query(query)
                if not cypher or "MATCH" not in cypher:
                    self._add_failure(test_name, "No valid Cypher query", query)
                    continue
                
                results = self.graph_rag.execute_cypher_query(cypher)
                
                if results and len(results) > 0:
                    # Check if correct parameter was found
                    params_found = set()
                    for result in results:
                        if isinstance(result, dict):
                            param_name = result.get('p.parameter_name', result.get('parameter_name', ''))
                            if param_name:
                                params_found.add(param_name.lower())
                    
                    param_matched = any(param_variation.lower() in p for p in params_found)
                    
                    if param_matched:
                        self._add_success(test_name, f"Parameter matched correctly", query)
                    else:
                        self._add_failure(test_name,
                            f"Expected '{param_variation}', got: {params_found}", query)
                else:
                    self._add_failure(test_name, "No results returned", query)
            
            except Exception as e:
                self._add_failure(test_name, f"Exception: {str(e)}", query)
    
    # Helper methods
    
    def _normalize_quarter(self, quarter_str: str) -> str:
        """Normalize quarter string to database format"""
        quarter_str = quarter_str.upper().replace(" ", "")
        
        # Extract quarter and year
        if "Q1" in quarter_str:
            q = "1"
        elif "Q2" in quarter_str:
            q = "2"
        elif "Q3" in quarter_str:
            q = "3"
        elif "Q4" in quarter_str:
            q = "4"
        else:
            return quarter_str
        
        # Extract year (4 digits)
        import re
        year_match = re.search(r'(\d{4})', quarter_str)
        year = year_match.group(1) if year_match else "2025"
        
        return f"{q}QFY-{year}"
    
    def _check_period_exists(self, period: str) -> bool:
        """Check if period exists in database for Kajaria"""
        try:
            query = f"""
            MATCH (c:Company {{cid: "{self.company_cid}"}})-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
            WHERE pr.period = '{period}'
            RETURN count(pr) as count
            LIMIT 1
            """
            results = graph.query(query)
            if results and len(results) > 0:
                count = results[0].get('count', 0)
                return count > 0
            return False
        except:
            return False
    
    def _add_success(self, test_name: str, message: str, query: str):
        """Add successful test result"""
        result = TestResult(test_name, True, message, None, None, f"Query: {query}")
        self.test_results.append(result)
        print(f"[PASS] {test_name}: {message}")
    
    def _add_failure(self, test_name: str, message: str, query: str):
        """Add failed test result"""
        result = TestResult(test_name, False, message, None, None, f"Query: {query}")
        self.test_results.append(result)
        print(f"[FAIL] {test_name}: {message}")
    
    def _add_skip(self, test_name: str, message: str, query: str):
        """Add skipped test result"""
        result = TestResult(test_name, None, message, None, None, f"Query: {query}")
        self.test_results.append(result)
        print(f"[SKIP] {test_name}: {message}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 100)
        print("TEST SUMMARY")
        print("=" * 100)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.passed is True)
        failed = sum(1 for r in self.test_results if r.passed is False)
        skipped = sum(1 for r in self.test_results if r.passed is None)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({passed*100//total if total > 0 else 0}%)")
        print(f"Failed: {failed} ({failed*100//total if total > 0 else 0}%)")
        print(f"Skipped: {skipped} ({skipped*100//total if total > 0 else 0}%)")
        
        if failed > 0:
            print("\n" + "=" * 100)
            print("FAILED TESTS:")
            print("=" * 100)
            for result in self.test_results:
                if result.passed is False:
                    print(f"\n[FAIL] {result.test_name}")
                    print(f"  Message: {result.message}")
                    print(f"  Details: {result.details}")
        
        print("\n" + "=" * 100)
        
        # Return exit code
        return 0 if failed == 0 else 1


if __name__ == "__main__":
    tester = ComprehensiveKajariaTester()
    exit_code = tester.run_all_tests()
    sys.exit(exit_code)

