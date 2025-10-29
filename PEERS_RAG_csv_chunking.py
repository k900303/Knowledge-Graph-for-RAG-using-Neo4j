"""
Text Chunking Module for PEERS RAG System
Generates searchable text chunks from company data for vector embeddings
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from csv_parser import Company, CSVParser, Parameter, PeriodResult, ParameterParser, ResultsParser
from typing import List, Dict
from neo4j_env import graph
import warnings

warnings.filterwarnings("ignore")


class PEERSChunking:
    """Handles text chunking for company data"""
    
    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        self.graph = graph
    
    def generate_company_text(self, company: Company) -> str:
        """
        Generate a textual description of a company for embedding
        
        Args:
            company: Company object
        
        Returns:
            Formatted text string describing the company
        """
        # Build a rich description
        text_parts = []
        
        text_parts.append(f"Company: {company.company_name}")
        text_parts.append(f"Company ID: {company.company_id}")
        
        if company.country:
            text_parts.append(f"Country: {company.country} ({company.country_code})")
        
        if company.region:
            text_parts.append(f"Region: {company.region}")
        
        if company.sector_name:
            text_parts.append(f"Sector: {company.sector_name}")
        
        if company.industry_name:
            text_parts.append(f"Industry: {company.industry_name}")
        
        if company.exchange:
            text_parts.append(f"Exchange: {company.exchange}")
            if company.exchange_symbol:
                text_parts.append(f"Exchange Symbol: {company.exchange_symbol}")
        
        if company.market_cap and company.market_cap > 0:
            text_parts.append(f"Market Capitalization: {company.market_cap:,.0f} {company.base_currency}")
        
        # Performance metrics
        if company.one_week_change != 0:
            text_parts.append(f"1-Week Change: {company.one_week_change:.2f}%")
        
        if company.this_month_change != 0:
            text_parts.append(f"1-Month Change: {company.this_month_change:.2f}%")
        
        if company.this_quarter_change != 0:
            text_parts.append(f"Quarter Change: {company.this_quarter_change:.2f}%")
        
        if company.va_ticker:
            text_parts.append(f"Ticker: {company.va_ticker}")
        
        if company.isin:
            text_parts.append(f"ISIN: {company.isin}")
        
        # Combine into a single text
        return "\n".join(text_parts)
    
    def create_company_chunks(self, parser: CSVParser, batch_size: int = 100):
        """
        Create text chunks for all companies and store in Neo4j
        
        Args:
            parser: CSVParser with parsed companies
            batch_size: Number of companies to process per batch
        """
        print("\n" + "="*80)
        print("Creating Company Text Chunks for Vector Embeddings")
        print("="*80)
        
        companies = parser.get_companies()
        total_companies = len(companies)
        
        chunks_created = []
        
        for i, company in enumerate(companies, 1):
            try:
                # Generate company description text
                company_text = self.generate_company_text(company)
                
                # Split into chunks
                chunks = self.text_splitter.split_text(company_text)
                
                # Create chunk nodes in Neo4j
                for chunk_seq, chunk_text in enumerate(chunks):
                    chunk_data = {
                        "cid": company.company_id,
                        "company_name": company.company_name,
                        "chunk_seq_id": chunk_seq,
                        "text": chunk_text,
                        "formItem": "company_description",
                        "chunkId": f"{company.company_id}_company_description_chunk{chunk_seq:04d}"
                    }
                    
                    chunks_created.append(chunk_data)
                
                # Process in batches
                if len(chunks_created) >= batch_size:
                    self._insert_chunks_batch(chunks_created)
                    print(f"  Progress: {i}/{total_companies} companies processed")
                    chunks_created = []
                    
            except Exception as e:
                print(f"  Error processing company {company.company_name}: {e}")
                continue
        
        # Insert remaining chunks
        if chunks_created:
            self._insert_chunks_batch(chunks_created)
        
        print(f"\n[OK] Completed creating chunks for {total_companies} companies")
        print("="*80)
    
    def _insert_chunks_batch(self, chunks: List[Dict]):
        """Insert a batch of chunk nodes into Neo4j"""
        
        cypher = """
        UNWIND $chunks AS chunk
        MATCH (company:Company {cid: chunk.cid})
        CREATE (company_chunk:Company_Chunk {
            chunkId: chunk.chunkId,
            text: chunk.text,
            formItem: chunk.formItem,
            chunkSeqId: chunk.chunkSeqId,
            company_name: chunk.company_name,
            source: chunk.company_name
        })
        CREATE (company)-[:HAS_Chunk_INFO]->(company_chunk)
        RETURN count(company_chunk) as count
        """
        
        result = self.graph.query(cypher, {"chunks": chunks})
        return result
    
    def create_vector_index(self, index_name: str = "CompanyOpenAI"):
        """Create vector index for company chunks"""
        print(f"\nCreating vector index: {index_name}")
        
        cypher = f"""
        CREATE VECTOR INDEX {index_name}_embedding IF NOT EXISTS
        FOR (n:Company_Chunk)
        ON n.textEmbeddingOpenAI
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        
        try:
            self.graph.query(cypher)
            print(f"[OK] Vector index '{index_name}_embedding' created successfully")
        except Exception as e:
            print(f"[WARNING] Index creation: {e}")
    
    def generate_parameter_text(self, parameter: Parameter, company_name: str = "") -> str:
        """
        Generate a textual description of a parameter for embedding - optimized for 6 essential fields only
        
        Args:
            parameter: Parameter object
            company_name: Company name for context
        
        Returns:
            Formatted text string describing the parameter
        """
        text_parts = []
        
        text_parts.append(f"Parameter: {parameter.parameter_name}")
        text_parts.append(f"Parameter ID: {parameter.param_id}")
        
        if company_name:
            text_parts.append(f"Company: {company_name}")
        
        text_parts.append(f"Company ID: {parameter.cid}")
        text_parts.append(f"Parameter Type: {parameter.parameter_type}")
        
        if parameter.unit:
            text_parts.append(f"Unit: {parameter.unit}")
        
        if parameter.isprimary:
            text_parts.append(f"Primary Parameter: Yes")
        
        return "\n".join(text_parts)
    
    def generate_period_result_text(self, result: PeriodResult, parameter_name: str = "", company_name: str = "") -> str:
        """
        Generate a textual description of a period result for embedding - optimized for 11 essential fields only
        
        Args:
            result: PeriodResult object
            parameter_name: Parameter name for context
            company_name: Company name for context
        
        Returns:
            Formatted text string describing the period result
        """
        text_parts = []
        
        if company_name:
            text_parts.append(f"Company: {company_name}")
        
        text_parts.append(f"Company ID: {result.cid}")
        
        if parameter_name:
            text_parts.append(f"Parameter: {parameter_name}")
        
        text_parts.append(f"Parameter ID: {result.pid}")
        text_parts.append(f"Period: {result.period}")
        
        if result.actual_period:
            text_parts.append(f"Actual Period: {result.actual_period}")
        
        text_parts.append(f"Value: {result.value}")
        
        if result.currency:
            text_parts.append(f"Currency: {result.currency}")
        
        if result.data_type:
            text_parts.append(f"Data Type: {result.data_type}")
        
        if result.yoy_growth != 0:
            text_parts.append(f"Year-over-Year Growth: {result.yoy_growth:.2f}%")
        
        if result.seq_growth != 0:
            text_parts.append(f"Sequential Growth: {result.seq_growth:.2f}%")
        
        return "\n".join(text_parts)
    
    def create_parameter_chunks(self, parameter_parser: ParameterParser, company_name: str = "", batch_size: int = 100):
        """
        Create text chunks for all parameters and store in Neo4j
        
        Args:
            parameter_parser: ParameterParser with parsed parameters
            company_name: Company name for context
            batch_size: Number of parameters to process per batch
        """
        print("\n" + "="*80)
        print("Creating Parameter Text Chunks for Vector Embeddings")
        print("="*80)
        
        parameters = parameter_parser.get_parameters()
        total_parameters = len(parameters)
        
        chunks_created = []
        
        for i, parameter in enumerate(parameters, 1):
            try:
                # Generate parameter description text
                parameter_text = self.generate_parameter_text(parameter, company_name)
                
                # Split into chunks
                chunks = self.text_splitter.split_text(parameter_text)
                
                # Create chunk nodes in Neo4j
                for chunk_seq, chunk_text in enumerate(chunks):
                    chunk_data = {
                        "param_id": parameter.param_id,
                        "parameter_name": parameter.parameter_name,
                        "chunk_seq_id": chunk_seq,
                        "text": chunk_text,
                        "formItem": "parameter_description",
                        "chunkId": f"{parameter.param_id}_parameter_description_chunk{chunk_seq:04d}",
                        "company_name": company_name or f"Company_{parameter.cid}"
                    }
                    
                    chunks_created.append(chunk_data)
                
                # Process in batches
                if len(chunks_created) >= batch_size:
                    self._insert_parameter_chunks_batch(chunks_created)
                    print(f"  Progress: {i}/{total_parameters} parameters processed")
                    chunks_created = []
                    
            except Exception as e:
                print(f"  Error processing parameter {parameter.parameter_name}: {e}")
                continue
        
        # Insert remaining chunks
        if chunks_created:
            self._insert_parameter_chunks_batch(chunks_created)
        
        print(f"\n[OK] Completed creating chunks for {total_parameters} parameters")
        print("="*80)
    
    def _insert_parameter_chunks_batch(self, chunks: List[Dict]):
        """Insert a batch of parameter chunk nodes into Neo4j"""
        
        cypher = """
        UNWIND $chunks AS chunk
        MATCH (param:Parameter {param_id: chunk.param_id})
        CREATE (param_chunk:Parameter_Chunk {
            chunkId: chunk.chunkId,
            text: chunk.text,
            formItem: chunk.formItem,
            chunkSeqId: chunk.chunkSeqId,
            parameter_name: chunk.parameter_name,
            company_name: chunk.company_name,
            source: chunk.parameter_name
        })
        CREATE (param)-[:HAS_PARAMETER_INFO]->(param_chunk)
        RETURN count(param_chunk) as count
        """
        
        result = self.graph.query(cypher, {"chunks": chunks})
        return result
    
    def create_period_result_chunks(self, results_parser: ResultsParser, parameter_names: Dict[str, str] = {}, 
                                  company_name: str = "", batch_size: int = 100):
        """
        Create text chunks for all period results and store in Neo4j
        
        Args:
            results_parser: ResultsParser with parsed results
            parameter_names: Dictionary mapping param_id to parameter_name
            company_name: Company name for context
            batch_size: Number of results to process per batch
        """
        print("\n" + "="*80)
        print("Creating Period Result Text Chunks for Vector Embeddings")
        print("="*80)
        
        results = results_parser.get_results()
        total_results = len(results)
        
        chunks_created = []
        
        for i, result in enumerate(results, 1):
            try:
                # Get parameter name
                param_name = parameter_names.get(result.pid, f"Parameter_{result.pid}")
                
                # Generate period result description text
                result_text = self.generate_period_result_text(result, param_name, company_name)
                
                # Split into chunks
                chunks = self.text_splitter.split_text(result_text)
                
                # Create chunk nodes in Neo4j
                for chunk_seq, chunk_text in enumerate(chunks):
                    chunk_data = {
                        "result_id": result.id,
                        "cid": result.cid,
                        "pid": result.pid,
                        "period": result.period,
                        "value": result.value,
                        "chunk_seq_id": chunk_seq,
                        "text": chunk_text,
                        "formItem": "period_result_description",
                        "chunkId": f"{result.id}_period_result_chunk{chunk_seq:04d}",
                        "parameter_name": param_name,
                        "company_name": company_name or f"Company_{result.cid}"
                    }
                    
                    chunks_created.append(chunk_data)
                
                # Process in batches
                if len(chunks_created) >= batch_size:
                    self._insert_period_result_chunks_batch(chunks_created)
                    print(f"  Progress: {i}/{total_results} results processed")
                    chunks_created = []
                    
            except Exception as e:
                print(f"  Error processing result {result.id}: {e}")
                continue
        
        # Insert remaining chunks
        if chunks_created:
            self._insert_period_result_chunks_batch(chunks_created)
        
        print(f"\n[OK] Completed creating chunks for {total_results} period results")
        print("="*80)
    
    def _insert_period_result_chunks_batch(self, chunks: List[Dict]):
        """Insert a batch of period result chunk nodes into Neo4j"""
        
        cypher = """
        UNWIND $chunks AS chunk
        MATCH (pr:PeriodResult {id: chunk.result_id})
        CREATE (pr_chunk:PeriodResult_Chunk {
            chunkId: chunk.chunkId,
            text: chunk.text,
            formItem: chunk.formItem,
            chunkSeqId: chunk.chunkSeqId,
            parameter_name: chunk.parameter_name,
            company_name: chunk.company_name,
            period: chunk.period,
            value: chunk.value,
            source: chunk.parameter_name
        })
        CREATE (pr)-[:HAS_PERIOD_RESULT_INFO]->(pr_chunk)
        RETURN count(pr_chunk) as count
        """
        
        result = self.graph.query(cypher, {"chunks": chunks})
        return result
    
    def create_parameter_vector_index(self, index_name: str = "ParameterOpenAI"):
        """Create vector index for parameter chunks"""
        print(f"\nCreating vector index: {index_name}")
        
        cypher = f"""
        CREATE VECTOR INDEX {index_name}_embedding IF NOT EXISTS
        FOR (n:Parameter_Chunk)
        ON n.textEmbeddingOpenAI
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        
        try:
            self.graph.query(cypher)
            print(f"[OK] Vector index '{index_name}_embedding' created successfully")
        except Exception as e:
            print(f"[WARNING] Index creation: {e}")
    
    def create_period_result_vector_index(self, index_name: str = "PeriodResultOpenAI"):
        """Create vector index for period result chunks"""
        print(f"\nCreating vector index: {index_name}")
        
        cypher = f"""
        CREATE VECTOR INDEX {index_name}_embedding IF NOT EXISTS
        FOR (n:PeriodResult_Chunk)
        ON n.textEmbeddingOpenAI
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        
        try:
            self.graph.query(cypher)
            print(f"[OK] Vector index '{index_name}_embedding' created successfully")
        except Exception as e:
            print(f"[WARNING] Index creation: {e}")


def main():
    """Example usage"""
    from csv_parser import parse_company_csv
    
    # Parse CSV
    csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
    parser = parse_company_csv(csv_path)
    
    # Create chunking instance
    chunking = PEERSChunking(chunk_size=1500, chunk_overlap=150)
    
    # Create chunks
    chunking.create_company_chunks(parser, batch_size=100)
    
    # Create vector index
    chunking.create_vector_index()


if __name__ == '__main__':
    main()

