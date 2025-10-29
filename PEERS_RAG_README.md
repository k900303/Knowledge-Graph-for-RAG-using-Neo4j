# PEERS RAG System

A comprehensive RAG (Retrieval-Augmented Generation) system for company and financial data using Neo4j knowledge graph and vector embeddings.

## Overview

This system converts CSV company master data into a Neo4j knowledge graph and provides two query interfaces:
1. **GraphRAG**: Uses Cypher queries to explore relationships between companies, sectors, industries, countries, etc.
2. **VectorRAG**: Uses semantic search to find similar companies based on descriptions.

## Architecture

```
CSV Data → Parse → Neo4j Graph → Text Chunks → Vector Embeddings → RAG Queries
```

## Knowledge Graph Structure

```
Company [:IN_COUNTRY] → Country
Company [:IN_REGION] → Region  
Company [:IN_SECTOR] → Sector
Company [:IN_INDUSTRY] → Industry
Company [:LISTED_ON] → Exchange
Company [:HAS_Chunk_INFO] → Company_Chunk (for vector search)
```

## Files

### Core Modules
- `csv_parser.py` - Parses company_master CSV file
- `PEERS_RAG_neo4j_ingestion.py` - Creates graph nodes and relationships
- `PEERS_RAG_csv_chunking.py` - Generates searchable text chunks
- `PEERS_RAG_embeddings.py` - Generates OpenAI embeddings
- `PEERS_RAG_pipeline.py` - Orchestrates the complete pipeline

### RAG Modules
- `PEERS_RAG_graphRAG.py` - GraphRAG implementation with Cypher queries
- `PEERS_RAG_vectorRAG.py` - VectorRAG implementation with semantic search
- `PEERS_RAG_main.py` - Main entry point with example queries

## Usage

### 1. Run Complete Pipeline

```python
from PEERS_RAG_pipeline import PEERSPipeline

csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
pipeline = PEERSPipeline(csv_path)

# Run full pipeline
pipeline.run_full_pipeline(clear_existing=True)
```

### 2. Query with GraphRAG

```python
from PEERS_RAG_graphRAG import PEERSGraphRAG

rag = PEERSGraphRAG()
answer = rag.generate_cypher_query("Which technology companies are in the US?")
print(answer)
```

### 3. Query with VectorRAG

```python
from PEERS_RAG_vectorRAG import PEERSVectorRAG

rag = PEERSVectorRAG()
answer = rag.query("Find large healthcare companies")
print(answer)
```

### 4. Run Main Examples

```bash
python PEERS_RAG_main.py
```

## Example Queries

### GraphRAG Queries
- "Which companies are in the Technology sector?"
- "Show me companies listed on NASDAQ"
- "Find pharmaceutical companies in Asia"
- "List companies with positive one week change"
- "Which US companies are in Healthcare?"

### VectorRAG Queries
- "Tell me about large Fortune 500 companies"
- "Find companies similar to Apple"
- "Show me technology startups"
- "What are the top financial services companies?"

## Configuration

Update `neo4j_env.py` with your Neo4j and OpenAI credentials:

```python
NEO4J_URI = 'bolt://localhost:7687'
NEO4J_USERNAME = 'neo4j'
NEO4J_PASSWORD = 'password'
NEO4J_DATABASE = 'neo4j'
OPENAI_API_KEY = 'your-api-key'
OPENAI_BASE_URL = 'https://api.openai.com/v1'
```

## Data Flow

1. **CSV Parsing**: Read company_master_csv.txt and extract entities
2. **Graph Creation**: Create nodes (Company, Country, Region, Sector, Industry, Exchange) and relationships
3. **Chunking**: Generate descriptive text for each company
4. **Embeddings**: Create vector embeddings using OpenAI API
5. **Indexing**: Create vector index in Neo4j for fast similarity search
6. **Querying**: Execute either GraphRAG or VectorRAG queries

## Neo4j Indexes

The system creates the following indexes:
- Vector index: `CompanyOpenAI_embedding` for semantic search
- Node labels: `Company`, `Country`, `Region`, `Sector`, `Industry`, `Exchange`, `Company_Chunk`

## Performance

- Batch processing for efficient ingestion
- Configurable batch sizes (default: 100 for nodes, 50 for embeddings)
- Progress tracking for large datasets
- Error handling for robust processing

## Next Steps

To extend the system:
1. Add parameter library support (parameter_library_sync.csv)
2. Implement additional relationship types
3. Add temporal queries (historical data)
4. Include financial metrics and ratios

