"""
Main Pipeline for PEERS RAG System
Orchestrates CSV → Neo4j → Embeddings → RAG workflow
"""

from csv_parser import parse_company_csv, parse_parameter_csv, parse_results_csv
from PEERS_RAG_neo4j_ingestion import PEERSNeo4jIngestion
from PEERS_RAG_csv_chunking import PEERSChunking
from PEERS_RAG_embeddings import PEERSEmbeddingGenerator
import warnings

warnings.filterwarnings("ignore")


class PEERSPipeline:
    """Main orchestration class for PEERS RAG pipeline"""
    
    def __init__(self, csv_file_path: str, parameter_file_path: str = None, results_file_path: str = None):
        self.csv_file_path = csv_file_path
        self.parameter_file_path = parameter_file_path
        self.results_file_path = results_file_path
        self.parser = None
        self.parameter_parser = None
        self.results_parser = None
        self.ingestion = PEERSNeo4jIngestion()
        self.chunking = PEERSChunking()
        self.embedding_gen = PEERSEmbeddingGenerator()
    
    def run_full_pipeline(self, clear_existing: bool = False):
        """
        Run the complete PEERS RAG pipeline with parameters and results
        
        Args:
            clear_existing: Whether to clear existing data before ingestion
        """
        print("\n" + "="*100)
        print("  PEERS RAG SYSTEM - COMPLETE PIPELINE (WITH PARAMETERS & RESULTS)")
        print("="*100)
        
        # Step 1: Parse CSV files
        print("\n[1/6] Parsing CSV files...")
        self.parser = parse_company_csv(self.csv_file_path)
        print("[OK] Company CSV parsed successfully")
        
        if self.parameter_file_path:
            self.parameter_parser = parse_parameter_csv(self.parameter_file_path, target_cid="18315", allowed_types=["opssd", "sd"])
            print("[OK] Parameter CSV parsed successfully")
        
        if self.results_file_path:
            self.results_parser = parse_results_csv(self.results_file_path, target_cid="18315")
            print("[OK] Results CSV parsed successfully")
        
        # Step 2: Create Neo4j graph
        print("\n[2/6] Creating Neo4j knowledge graph...")
        if clear_existing:
            print("  [WARNING] Clearing existing data...")
            self.ingestion.clear_all_data()
        
        # FILTER FOR INDIAN COMPANIES ONLY (for testing)
        self.ingestion.create_company_graph(self.parser, batch_size=100, filter_country='IN')
        print("[OK] Company graph created successfully")
        
        # Step 3: Create parameter nodes
        if self.parameter_parser:
            print("\n[3/6] Creating parameter nodes...")
            self.ingestion.create_parameter_nodes(self.parameter_parser, batch_size=100)
            print("[OK] Parameter nodes created successfully")
        
        # Step 4: Create period result nodes
        if self.results_parser:
            print("\n[4/6] Creating period result nodes...")
            self.ingestion.create_period_results(self.results_parser, batch_size=100)
            print("[OK] Period result nodes created successfully")
        
        # Step 5: Create text chunks
        print("\n[5/6] Creating text chunks for vector search...")
        # Filter companies for chunking too
        from csv_parser import Company
        companies = self.parser.get_companies()
        filtered_companies = [c for c in companies if c.country_code == 'IN']
        # Create a temporary parser with filtered companies
        import copy
        temp_parser = copy.deepcopy(self.parser)
        temp_parser.companies = filtered_companies
        self.chunking.create_company_chunks(temp_parser, batch_size=100)
        self.chunking.create_vector_index()
        
        # Create parameter chunks
        if self.parameter_parser:
            company_name = "Kajaria Ceramics"  # Hardcoded for cid=18315
            self.chunking.create_parameter_chunks(self.parameter_parser, company_name, batch_size=100)
            self.chunking.create_parameter_vector_index()
        
        # Create period result chunks
        if self.results_parser and self.parameter_parser:
            # Create parameter name mapping
            parameter_names = {p.param_id: p.parameter_name for p in self.parameter_parser.get_parameters()}
            self.chunking.create_period_result_chunks(self.results_parser, parameter_names, company_name, batch_size=100)
            self.chunking.create_period_result_vector_index()
        
        print("[OK] Text chunks created successfully")
        
        # Step 6: Generate embeddings
        print("\n[6/6] Generating vector embeddings...")
        self.embedding_gen.generate_embeddings_for_all_chunks(batch_size=50)
        print("[OK] Embeddings generated successfully")
        
        # Show final statistics
        print("\n" + "="*100)
        print("  PIPELINE COMPLETE")
        print("="*100)
        self.ingestion.get_graph_stats()
        
        # Cleanup
        self.embedding_gen.close()
    
    def run_ingestion_only(self):
        """Run only the graph ingestion step"""
        print("\n[INGESTION ONLY] Creating Neo4j knowledge graph...")
        
        self.parser = parse_company_csv(self.csv_file_path)
        self.ingestion.create_company_graph(self.parser, batch_size=100)
        self.ingestion.get_graph_stats()
    
    def run_chunking_only(self):
        """Run only the chunking step"""
        print("\n[CHUNKING ONLY] Creating text chunks...")
        
        self.parser = parse_company_csv(self.csv_file_path)
        self.chunking.create_company_chunks(self.parser, batch_size=100)
        self.chunking.create_vector_index()
    
    def run_embeddings_only(self):
        """Run only the embedding generation step"""
        print("\n[EMBEDDINGS ONLY] Generating vector embeddings...")
        
        self.embedding_gen.generate_embeddings_for_all_chunks(batch_size=50)
        self.embedding_gen.close()


def main():
    """Example usage with parameter and results data"""
    csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
    parameter_path = 'data/PEERS_PROD_RAW_CSV_DATA/parameters_kajaria_cid_18315.csv'
    results_path = 'data/PEERS_PROD_RAW_CSV_DATA/results_kajaria_cid_18315.csv'
    
    # Create pipeline with parameter and results files
    pipeline = PEERSPipeline(csv_path, parameter_path, results_path)
    
    # Run full pipeline
    pipeline.run_full_pipeline(clear_existing=True)
    
    # Or run steps individually
    # pipeline.run_ingestion_only()
    # pipeline.run_chunking_only()
    # pipeline.run_embeddings_only()


if __name__ == '__main__':
    main()

