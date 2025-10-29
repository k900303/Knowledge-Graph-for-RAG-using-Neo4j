"""
Neo4j Ingestion Module for PEERS RAG System
Creates graph nodes and relationships from parsed CSV data
"""

from neo4j_env import graph
from csv_parser import Company, CSVParser, Parameter, PeriodResult, ParameterParser, ResultsParser
from typing import List
import warnings

warnings.filterwarnings("ignore")


class PEERSNeo4jIngestion:
    """Handles Neo4j graph creation from CSV data"""
    
    def __init__(self):
        self.graph = graph
    
    def create_company_graph(self, parser: CSVParser, batch_size: int = 100, filter_country: str = None):
        """
        Create the complete company knowledge graph
        
        Args:
            parser: CSVParser object with parsed data
            batch_size: Number of nodes to create in each batch
            filter_country: Filter companies by country code (e.g., 'IN' for India)
        """
        print("\n" + "="*80)
        print("Starting PEERS Neo4j Graph Ingestion")
        if filter_country:
            print(f"[FILTER] Only processing companies from: {filter_country}")
        print("="*80)
        
        # Step 1: Create reference nodes (Countries, Regions, Sectors, Industries)
        self._create_reference_nodes(parser)
        
        # Step 2: Filter companies by country if specified
        companies = parser.get_companies()
        if filter_country:
            companies = [c for c in companies if c.country_code == filter_country]
            print(f"\n[FILTERED] {len(companies)} companies from {filter_country}")
        
        total_companies = len(companies)
        
        print(f"\nCreating {total_companies} company nodes in batches of {batch_size}")
        
        for i in range(0, total_companies, batch_size):
            batch = companies[i:i+batch_size]
            self._create_company_batch(batch)
            print(f"  Progress: {min(i+batch_size, total_companies)}/{total_companies} companies processed")
        
        print("\n[OK] Company graph creation completed!")
        print("="*80)
    
    def _create_reference_nodes(self, parser: CSVParser):
        """Create Country, Region, Sector, Industry, and Exchange nodes"""
        print("\nCreating reference nodes...")
        
        # Create Countries
        countries_list = []
        for country_code in parser.get_unique_countries():
            countries_list.append({
                "code": country_code,
                "name": country_code  # Use code as name for now
            })
        
        cypher = """
        UNWIND $countries AS country
        MERGE (c:Country {code: country.code, name: country.name})
        RETURN count(c) as count
        """
        
        result = self.graph.query(cypher, {"countries": countries_list})
        print(f"  [OK] Created {result[0]['count']} Country nodes")
        
        # Create Regions
        cypher = """
        UNWIND $regions AS region
        MERGE (r:Region {name: region})
        RETURN count(r) as count
        """
        
        regions = list(parser.get_unique_regions())
        result = self.graph.query(cypher, {"regions": regions})
        print(f"  [OK] Created {result[0]['count']} Region nodes")
        
        # Create Sectors
        cypher = """
        UNWIND $sectors AS sector
        MERGE (s:Sector {id: sector.id, name: sector.name})
        RETURN count(s) as count
        """
        
        sectors = [{"id": sid, "name": name} for sid, name in parser.get_sectors().items()]
        result = self.graph.query(cypher, {"sectors": sectors})
        print(f"  [OK] Created {result[0]['count']} Sector nodes")
        
        # Create Industries
        cypher = """
        UNWIND $industries AS industry
        MERGE (i:Industry {id: industry.id, name: industry.name})
        RETURN count(i) as count
        """
        
        industries = [{"id": iid, "name": name} for iid, name in parser.get_industries().items()]
        result = self.graph.query(cypher, {"industries": industries})
        print(f"  [OK] Created {result[0]['count']} Industry nodes")
        
        # Create Exchanges
        cypher = """
        UNWIND $exchanges AS exchange
        MERGE (e:Exchange {code: exchange})
        RETURN count(e) as count
        """
        
        exchanges = parser.get_exchanges()
        result = self.graph.query(cypher, {"exchanges": exchanges})
        print(f"  [OK] Created {result[0]['count']} Exchange nodes")
    
    def _create_company_batch(self, companies: List[Company]):
        """Create company nodes and relationships for a batch"""
        
        # Prepare company data
        company_data = []
        for company in companies:
            company_data.append({
                "cid": company.company_id or '',
                "company_name": company.company_name,
                "country_code": company.country_code,
                "region": company.region,
                "sector_id": company.sector_id,
                "industry_id": company.industry_id,
                "exchange": company.exchange,
                "exchange_symbol": company.exchange_symbol,
                "market_cap": company.market_cap,
                "base_currency": company.base_currency,
                "one_week_change": company.one_week_change,
                "this_month_change": company.this_month_change,
                "this_quarter_change": company.this_quarter_change,
                "isin": company.isin,
                "va_ticker": company.va_ticker,
                "status": company.status
            })
        
        # Create Company nodes with relationships - simplified approach
        successful_companies = 0
        for company in companies:
            try:
                # Skip if no company_id or company_name
                if not company.company_id or not company.company_name:
                    continue
                
                # Prepare company data
                cid = str(company.company_id).strip()
                company_name = str(company.company_name).strip()
                
                if not cid or not company_name:
                    continue
                
                # Create company node
                company_data = {
                    "cid": cid,
                    "company_name": company_name,
                    "market_cap": company.market_cap or 0,
                    "base_currency": company.base_currency or '',
                    "one_week_change": company.one_week_change or 0,
                    "this_month_change": company.this_month_change or 0,
                    "this_quarter_change": company.this_quarter_change or 0,
                    "isin": company.isin or '',
                    "va_ticker": company.va_ticker or '',
                    "status": company.status or 'Active'
                }
                
                cypher = """
                MERGE (company:Company {
                    cid: $cid,
                    company_name: $company_name
                })
                SET company.market_cap = $market_cap,
                    company.base_currency = $base_currency,
                    company.one_week_change = $one_week_change,
                    company.this_month_change = $this_month_change,
                    company.this_quarter_change = $this_quarter_change,
                    company.isin = $isin,
                    company.va_ticker = $va_ticker,
                    company.status = $status
                RETURN company.cid
                """
                
                self.graph.query(cypher, company_data)
                
                # Add relationships one by one with safety checks
                if company.country_code and str(company.country_code).strip():
                    country_code = str(company.country_code).strip()
                    self._create_relationship(cid, 'Country', 'IN_COUNTRY', {
                        'code': country_code,
                        'name': country_code  # Use code as name to match the node creation
                    })
                
                if company.region and str(company.region).strip():
                    self._create_relationship(cid, 'Region', 'IN_REGION', {'name': str(company.region).strip()})
                
                if company.sector_id and str(company.sector_id).strip():
                    self._create_relationship(cid, 'Sector', 'IN_SECTOR', {'id': str(company.sector_id).strip()})
                
                if company.industry_id and str(company.industry_id).strip():
                    self._create_relationship(cid, 'Industry', 'IN_INDUSTRY', {'id': str(company.industry_id).strip()})
                
                if company.exchange and str(company.exchange).strip():
                    self._create_relationship(cid, 'Exchange', 'LISTED_ON', {'code': str(company.exchange).strip()})
                
                successful_companies += 1
                
            except Exception as e:
                print(f"  Error processing company {getattr(company, 'company_name', 'Unknown')}: {e}")
                continue
        
        print(f"  Successfully created {successful_companies} companies with relationships")
        return [{"count": successful_companies}]
    
    def _create_relationship(self, company_cid, node_type, rel_type, match_props):
        """Helper method to safely create relationships"""
        try:
            # Build MATCH clause based on properties
            match_clauses = []
            params = {"cid": company_cid}
            
            for key, value in match_props.items():
                match_clauses.append(f"{key}: ${key}")
                params[key] = value
            
            match_str = ", ".join(match_clauses)
            
            cypher = f"""
            MATCH (c:Company {{cid: $cid}})
            MATCH (target:{node_type} {{{match_str}}})
            MERGE (c)-[:{rel_type}]->(target)
            """
            
            self.graph.query(cypher, params)
        except Exception as e:
            # Log the error but continue processing other companies
            print(f"  [WARN] Failed to create relationship: {rel_type} for company {company_cid}: {e}")
            pass
    
    def clear_all_data(self):
        """Clear all company-related data from Neo4j"""
        print("\n[WARNING] Clearing all company graph data...")
        
        cypher = """
        // Delete all relationships and nodes
        MATCH (n)
        DETACH DELETE n
        """
        
        self.graph.query(cypher)
        print("[OK] All data cleared")
    
    def get_graph_stats(self):
        """Get statistics about the graph"""
        cypher = """
        MATCH (n)
        RETURN labels(n) as label, count(n) as count
        ORDER BY count DESC
        """
        
        result = self.graph.query(cypher)
        
        print("\n" + "="*50)
        print("Graph Statistics")
        print("="*50)
        for row in result:
            label_str = "".join(row['label'])
            print(f"  {label_str}: {row['count']}")
        
        # Count relationships
        cypher = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """
        
        result = self.graph.query(cypher)
        print("\nRelationships:")
        for row in result:
            print(f"  {row['rel_type']}: {row['count']}")
        
        print("="*50)

    def create_parameter_nodes(self, parameter_parser: ParameterParser, batch_size: int = 100):
        """
        Create Parameter nodes and Company-Parameter relationships
        
        Args:
            parameter_parser: ParameterParser object with parsed parameters
            batch_size: Number of parameters to process per batch
        """
        print("\n" + "="*80)
        print("Creating Parameter Nodes and Company-Parameter Relationships")
        print("="*80)
        
        parameters = parameter_parser.get_parameters()
        total_parameters = len(parameters)
        
        print(f"Creating {total_parameters} parameter nodes in batches of {batch_size}")
        
        successful_parameters = 0
        
        for i in range(0, total_parameters, batch_size):
            batch = parameters[i:i+batch_size]
            batch_success = self._create_parameter_batch(batch)
            successful_parameters += batch_success
            print(f"  Progress: {min(i+batch_size, total_parameters)}/{total_parameters} parameters processed")
        
        print(f"\n[OK] Successfully created {successful_parameters} parameter nodes with relationships")
        print("="*80)
    
    def _create_parameter_batch(self, parameters: List[Parameter]) -> int:
        """Create parameter nodes and relationships for a batch"""
        successful_count = 0
        
        for parameter in parameters:
            try:
                # Skip if no param_id or parameter_name
                if not parameter.param_id or not parameter.parameter_name:
                    continue
                
                # Create parameter node - optimized for 6 essential fields only
                parameter_data = {
                    "param_id": parameter.param_id,
                    "parameter_name": parameter.parameter_name,
                    "parameter_type": parameter.parameter_type,
                    "cid": parameter.cid,
                    "unit": parameter.unit,
                    "isprimary": parameter.isprimary
                }
                
                cypher = """
                MERGE (param:Parameter {
                    param_id: $param_id,
                    parameter_name: $parameter_name
                })
                SET param.parameter_type = $parameter_type,
                    param.cid = $cid,
                    param.unit = $unit,
                    param.isprimary = $isprimary
                RETURN param.param_id
                """
                
                self.graph.query(cypher, parameter_data)
                
                # Create Company-Parameter relationship
                self._create_parameter_relationship(parameter.cid, parameter.param_id)
                
                successful_count += 1
                
            except Exception as e:
                print(f"  Error processing parameter {getattr(parameter, 'parameter_name', 'Unknown')}: {e}")
                continue
        
        return successful_count
    
    def _create_parameter_relationship(self, company_cid: str, param_id: str):
        """Helper method to create Company-Parameter relationship"""
        try:
            cypher = """
            MATCH (c:Company {cid: $cid})
            MATCH (p:Parameter {param_id: $param_id})
            MERGE (c)-[:HAS_PARAMETER]->(p)
            """
            
            self.graph.query(cypher, {"cid": company_cid, "param_id": param_id})
        except Exception as e:
            print(f"  [WARN] Failed to create HAS_PARAMETER relationship for company {company_cid}, parameter {param_id}: {e}")
            pass
    
    def create_period_results(self, results_parser: ResultsParser, batch_size: int = 100):
        """
        Create PeriodResult nodes and dual relationships
        
        Args:
            results_parser: ResultsParser object with parsed results
            batch_size: Number of results to process per batch
        """
        print("\n" + "="*80)
        print("Creating PeriodResult Nodes and Dual Relationships")
        print("="*80)
        
        results = results_parser.get_results()
        total_results = len(results)
        
        print(f"Creating {total_results} period result nodes in batches of {batch_size}")
        
        successful_results = 0
        
        for i in range(0, total_results, batch_size):
            batch = results[i:i+batch_size]
            batch_success = self._create_period_result_batch(batch)
            successful_results += batch_success
            print(f"  Progress: {min(i+batch_size, total_results)}/{total_results} results processed")
        
        print(f"\n[OK] Successfully created {successful_results} period result nodes with dual relationships")
        print("="*80)
    
    def _create_period_result_batch(self, results: List[PeriodResult]) -> int:
        """Create period result nodes and dual relationships for a batch"""
        successful_count = 0
        
        for result in results:
            try:
                # Skip if no id or essential fields
                if not result.id or not result.cid or not result.pid:
                    continue
                
                # Create period result node - optimized for 11 essential fields only
                result_data = {
                    "id": result.id,
                    "cid": result.cid,
                    "pid": result.pid,
                    "period": result.period,
                    "actual_period": result.actual_period,
                    "value": result.value,
                    "currency": result.currency,
                    "unit": result.unit,
                    "data_type": result.data_type,
                    "yoy_growth": result.yoy_growth,
                    "seq_growth": result.seq_growth
                }
                
                cypher = """
                MERGE (pr:PeriodResult {
                    id: $id,
                    cid: $cid,
                    pid: $pid
                })
                SET pr.period = $period,
                    pr.actual_period = $actual_period,
                    pr.value = $value,
                    pr.currency = $currency,
                    pr.unit = $unit,
                    pr.data_type = $data_type,
                    pr.yoy_growth = $yoy_growth,
                    pr.seq_growth = $seq_growth
                RETURN pr.id
                """
                
                self.graph.query(cypher, result_data)
                
                # Create dual relationships
                self._create_period_result_relationships(result.cid, result.pid, result.id)
                
                successful_count += 1
                
            except Exception as e:
                print(f"  Error processing result {getattr(result, 'id', 'Unknown')}: {e}")
                continue
        
        return successful_count
    
    def _create_period_result_relationships(self, company_cid: str, param_id: str, result_id: str):
        """Helper method to create dual relationships for period results"""
        try:
            # Create Parameter-PeriodResult relationship
            cypher1 = """
            MATCH (p:Parameter {param_id: $param_id})
            MATCH (pr:PeriodResult {id: $result_id})
            MERGE (p)-[:HAS_VALUE_IN_PERIOD]->(pr)
            """
            self.graph.query(cypher1, {"param_id": param_id, "result_id": result_id})
            
            # Create Company-PeriodResult relationship
            cypher2 = """
            MATCH (c:Company {cid: $cid})
            MATCH (pr:PeriodResult {id: $result_id})
            MERGE (c)-[:HAS_RESULT_IN_PERIOD]->(pr)
            """
            self.graph.query(cypher2, {"cid": company_cid, "result_id": result_id})
            
        except Exception as e:
            print(f"  [WARN] Failed to create period result relationships for result {result_id}: {e}")
            pass


def main():
    """Example usage"""
    from csv_parser import parse_company_csv
    
    # Parse CSV
    csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
    parser = parse_company_csv(csv_path)
    
    # Create ingestion instance
    ingestion = PEERSNeo4jIngestion()
    
    # Optionally clear existing data (uncomment if needed)
    # ingestion.clear_all_data()
    
    # Create graph - FILTER FOR INDIAN COMPANIES ONLY
    ingestion.create_company_graph(parser, batch_size=100, filter_country='IN')
    
    # Show statistics
    ingestion.get_graph_stats()


if __name__ == '__main__':
    main()

