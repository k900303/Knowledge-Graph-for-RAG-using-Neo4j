# How to Run the PEERS RAG Pipeline

## Prerequisites

1. **Neo4j Running**: Make sure Neo4j is running and accessible
   ```bash
   # Check if Neo4j is running
   neo4j status
   ```

2. **Environment Variables**: Update your `.env` file with correct credentials:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_DATABASE=neo4j
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

3. **Dependencies Installed**: Ensure all Python packages are installed
   ```bash
   pip install neo4j langchain-openai langchain-community langchain-classic python-dotenv
   ```

## Running the Pipeline

### Option 1: Run the Complete Pipeline (Recommended)

From your terminal in the project root directory:

```bash
python PEERS_RAG_pipeline.py
```

This will:
1. Parse the CSV file
2. Create Neo4j graph (nodes and relationships)
3. Generate text chunks
4. Create vector embeddings
5. Show statistics

### Option 2: Test with a Small Subset First

Create a test script to verify everything works:

```bash
# Create test file
python -c "
from PEERS_RAG_pipeline import PEERSPipeline
import os

# Get first 100 lines from CSV
os.system('head -n 101 data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt > test_company_master.csv')

pipeline = PEERSPipeline('test_company_master.csv')
pipeline.run_full_pipeline(clear_existing=True)
"
```

### Option 3: Run Individual Steps

Edit `PEERS_RAG_pipeline.py` and uncomment specific steps:

```python
if __name__ == '__main__':
    csv_path = 'data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt'
    pipeline = PEERSPipeline(csv_path)
    
    # Run only what you need
    pipeline.run_ingestion_only()      # Step 1: Create graph
    # pipeline.run_chunking_only()       # Step 2: Create chunks
    # pipeline.run_embeddings_only()    # Step 3: Generate embeddings
```

### Option 4: Use Python Interactive Mode

```bash
python
```

Then run:

```python
from PEERS_RAG_pipeline import PEERSPipeline

# Create pipeline
pipeline = PEERSPipeline('data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt')

# Run full pipeline
pipeline.run_full_pipeline(clear_existing=True)
```

## Expected Output

You should see output like:

```
================================================================================
  PEERS RAG SYSTEM - COMPLETE PIPELINE
================================================================================

[1/4] Parsing CSV file...
Parsing CSV file: data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt
Parsed 18123 companies
Found 95 countries, 8 regions
Found 25 sectors, 185 industries
✅ CSV parsed successfully

[2/4] Creating Neo4j knowledge graph...
Creating reference nodes...
  ✅ Created 95 Country nodes
  ✅ Created 8 Region nodes
  ✅ Created 25 Sector nodes
  ✅ Created 185 Industry nodes
  ✅ Created 45 Exchange nodes
Creating 18123 company nodes in batches of 100
  Progress: 100/18123 companies processed
  ...
✅ Company graph creation completed!

[3/4] Creating text chunks for vector search...
Creating Company Text Chunks for Vector Embeddings
  Progress: 100/18123 companies processed
✅ Text chunks created successfully

[4/4] Generating vector embeddings...
Found 45231 chunks to embed
  Progress: 50/45231 chunks processed
✅ Embeddings generated successfully

================================================================================
  PIPELINE COMPLETE
================================================================================
```

## Testing Queries

After the pipeline completes, test queries:

```bash
python PEERS_RAG_main.py
```

Or in Python:

```python
from PEERS_RAG_main import query_peers_rag

# Test GraphRAG
result = query_peers_rag(True, "Which technology companies are in the US?")
print(result)

# Test VectorRAG
result = query_peers_rag(False, "Find large healthcare companies")
print(result)
```

## Troubleshooting

### Issue: Neo4j Connection Error
```bash
# Check Neo4j is running
neo4j status

# Start Neo4j if needed
neo4j start
```

### Issue: OpenAI API Error
```bash
# Verify API key is set
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

### Issue: Memory Issues with Large Dataset
Edit `PEERS_RAG_pipeline.py` and reduce batch sizes:

```python
pipeline.run_full_pipeline(clear_existing=True)  # Uses default batches

# Or manually set smaller batches
pipeline.ingestion.create_company_graph(pipeline.parser, batch_size=50)
pipeline.chunking.create_company_chunks(pipeline.parser, batch_size=50)
pipeline.embedding_gen.generate_embeddings_for_all_chunks(batch_size=25)
```

### Issue: CSV File Not Found
```bash
# Verify file exists
ls -lh data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt

# Check file size
wc -l data/PEERS_PROD_RAW_CSV_DATA/company_master_csv.txt
```

## Estimated Runtime

- **Parsing**: ~30 seconds
- **Graph Creation**: ~5-10 minutes (for ~18K companies)
- **Chunking**: ~2-3 minutes
- **Embeddings**: ~30-60 minutes (depends on API rate limits)

**Total**: ~40-75 minutes for full pipeline

## Monitoring Progress

Watch Neo4j browser during ingestion:
```
http://localhost:7474
```

Run this query to see progress:
```cypher
MATCH (n)
RETURN labels(n) as Label, count(n) as Count
ORDER BY Count DESC
```

