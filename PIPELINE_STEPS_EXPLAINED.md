# PEERS RAG Pipeline - Step-by-Step Explanation with Examples

## Overview

The pipeline processes company CSV data into a Neo4j knowledge graph with vector embeddings. Here's what happens at each step:

---

## Step 1: Parsing (~10 seconds)

### What It Does
Reads the CSV file and extracts structured data into Python objects.

### Example from CSV
```
Input (from CSV):
"20680,HDFC Bank,India,Asia,HDFCBANK,HDFCBANK,INR,66,Diversified and Regional banks,17,Financials,8,..."
```

### Processing
```python
# Create Company object
Company(
    company_id="20680",
    company_name="HDFC Bank",
    country_code="IN",
    country="India",
    region="Asia",
    sector_id="17",
    sector_name="Financials",
    industry_id="66",
    industry_name="Diversified and Regional banks",
    exchange="NSE",
    exchange_symbol="HDFCBANK",
    market_cap=15091541858910.0,
    base_currency="INR",
    one_week_change=1.79,
    this_month_change=3.31,
    this_quarter_change=3.31
)
```

### Output
- **~500-800 Indian company objects** (filtered from 7,591 total)
- Unique lists: 1 country, 1 region, ~5 sectors, ~50 industries
- Takes ~10 seconds

### Data Structure
```python
# What's created:
companies = [Company1, Company2, ... Company800]  # List of Company objects
countries = {'IN'}  # Set of country codes
sectors = {'17': 'Financials', '15': 'Technology', ...}
industries = {'66': 'Diversified Banks', '175': 'Software', ...}
```

---

## Step 2: Graph Creation (~2-3 minutes)

### What It Does
Creates Neo4j nodes and relationships for all entities.

### Sub-Step 2.1: Create Reference Nodes

#### Countries
```
CREATE (country1:Country {code: 'IN', name: 'IN'})
```

#### Regions
```
CREATE (region1:Region {name: 'Asia'})
```

#### Sectors
```
CREATE (sector1:Sector {id: '17', name: 'Financials'})
CREATE (sector2:Sector {id: '15', name: 'Technology'})
```

#### Industries
```
CREATE (industry1:Industry {id: '66', name: 'Diversified and Regional banks'})
CREATE (industry2:Industry {id: '175', name: 'IT Consulting'})
```

#### Exchanges
```
CREATE (exchange1:Exchange {code: 'NSE'})
```

### Sub-Step 2.2: Create Company Nodes

For each company (e.g., HDFC Bank):

#### Create Company Node
```cypher
MERGE (company:Company {
    cid: '20680',
    company_name: 'HDFC Bank'
})
SET company.market_cap = 15091541858910.0,
    company.base_currency = 'INR',
    company.one_week_change = 1.79,
    company.this_month_change = 3.31,
    company.this_quarter_change = 3.31,
    company.status = 'Active',
    company.exchange_symbol = 'HDFCBANK'
```

#### Create Relationships
```cypher
// Link to Country
MATCH (c:Company {cid: '20680'})
MATCH (country:Country {code: 'IN'})
MERGE (c)-[:IN_COUNTRY]->(country)

// Link to Region
MATCH (c:Company {cid: '20680'})
MATCH (region:Region {name: 'Asia'})
MERGE (c)-[:IN_REGION]->(region)

// Link to Sector
MATCH (c:Company {cid: '20680'})
MATCH (sector:Sector {id: '17'})
MERGE (c)-[:IN_SECTOR]->(sector)

// Link to Industry
MATCH (c:Company {cid: '20680'})
MATCH (industry:Industry {id: '66'})
MERGE (c)-[:IN_INDUSTRY]->(industry)

// Link to Exchange
MATCH (c:Company {cid: '20680'})
MATCH (exchange:Exchange {code: 'NSE'})
MERGE (c)-[:LISTED_ON]->(exchange)
```

### Visual Graph Structure
```
HDFC Bank (:Company)
├─ IN_COUNTRY → India (:Country)
├─ IN_REGION → Asia (:Region)
├─ IN_SECTOR → Financials (:Sector)
├─ IN_INDUSTRY → Diversified Banks (:Industry)
└─ LISTED_ON → NSE (:Exchange)

Properties:
- market_cap: ₹15,091,541 crore
- one_week_change: +1.79%
- this_month_change: +3.31%
```

### Output
- **~500-800 Company nodes**
- **1 Country node** (India)
- **1 Region node** (Asia)
- **~5-10 Sector nodes**
- **~50-100 Industry nodes**
- **~5 Exchange nodes** (NSE, BSE, etc.)
- **~2,000-4,000 relationships** total
- Takes ~2-3 minutes

---

## Step 3: Text Chunking (~30 seconds)

### What It Does
Generates searchable text descriptions for each company and splits them into chunks.

### Example: HDFC Bank

#### Generated Text
```
Company: HDFC Bank
Company ID: 20680
Country: India (IN)
Region: Asia
Sector: Financials
Industry: Diversified and Regional banks
Exchange: NSE
Exchange Symbol: HDFCBANK
Market Capitalization: 15,091,541,858,910 INR
1-Week Change: 1.79%
1-Month Change: 3.31%
Quarter Change: 3.31%
Ticker: HDFCBANK
ISIN: INE040A01036
```

#### Chunking Process
```python
# Split into chunks (chunk_size=1500, overlap=150)
Chunk 1: "Company: HDFC Bank\nCompany ID: 20680\nCountry: India (IN)..."
Chunk 2: "...Exchange: NSE\nMarket Capitalization: 15,091,541,858,910 INR..."
```

#### Create Chunk Nodes
```cypher
CREATE (chunk1:Company_Chunk {
    chunkId: '20680_company_description_chunk0000',
    text: 'Company: HDFC Bank...',
    formItem: 'company_description',
    chunkSeqId: 0,
    company_name: 'HDFC Bank',
    source: 'HDFC Bank'
})

CREATE (company)-[:HAS_Chunk_INFO]->(chunk1)
```

### Output
- **~1,000-1,600 chunk nodes** (2 chunks per company on average)
- Each company has 1-3 chunks
- Takes ~30 seconds

### Example Chunks in Neo4j
```
HDFC Bank (:Company)
├─ HAS_Chunk_INFO → Chunk 1: "Company: HDFC Bank..."
└─ HAS_Chunk_INFO → Chunk 2: "...Market Cap: 15 trillion..."

Infosys (:Company)  
├─ HAS_Chunk_INFO → Chunk 1: "Company: Infosys..."
└─ HAS_Chunk_INFO → Chunk 2: "...Technology sector..."
```

---

## Step 4: Embeddings (~10-15 minutes)

### What It Does
Generates vector embeddings for each text chunk using OpenAI API.

### Example: HDFC Bank Chunk

#### Input Text
```
"Company: HDFC Bank
Country: India (IN)
Sector: Financials
Market Capitalization: 15,091,541,858,910 INR"
```

#### OpenAI API Call
```python
embeddings = OpenAIEmbeddings()
embedding_vector = embeddings.embed_query(text)
# Returns: [0.123, -0.456, 0.789, ..., 0.234]  # 1536 dimensions
```

#### Store in Neo4j
```cypher
MATCH (chunk:Company_Chunk {chunkId: '20680_company_description_chunk0000'})
SET chunk.textEmbeddingOpenAI = [
    0.123, -0.456, 0.789, ..., 0.234  # 1536 numbers
]
```

### Visual Representation
```
Chunk 1 Text → OpenAI API → [1536 dimensions] → Stored in Neo4j
"Company: HDFC..."        → [0.12, -0.45, ...] → {textEmbeddingOpenAI: [...]}

Similar chunks will have similar vectors!
```

### Batch Processing
```python
# Process in batches of 50
Batch 1: Chunks 1-50   (3 seconds)
Batch 2: Chunks 51-100 (3 seconds)
...
Total: ~200 batches for 1,600 chunks
```

### Output
- **~1,000-1,600 embedding vectors** (each 1536 dimensions)
- **Vector index created**: `CompanyOpenAI_embedding`
- Takes ~10-15 minutes (due to API rate limits)

### What Embeddings Enable

#### Similarity Search Example
```
Query: "large Indian banks"

Embedding: [0.456, -0.123, ..., 0.789]

Find similar company chunks:
1. HDFC Bank chunk (similarity: 0.95)
2. ICICI Bank chunk (similarity: 0.92)
3. SBI Bank chunk (similarity: 0.89)
```

---

## Final Graph Structure

### Complete Knowledge Graph
```
┌─────────────────────────────────────────────────────────┐
│                   Reference Nodes                       │
├─────────────────────────────────────────────────────────┤
│ Country: India (IN)                                     │
│ Region: Asia                                            │
│ Sectors: Financials, Technology, Healthcare, ...         │
│ Industries: Banks, IT Services, Pharma, ...              │
│ Exchanges: NSE, BSE                                     │
└─────────────────────────────────────────────────────────┘
                         ↑
                         │ Relationships
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  Company Nodes                           │
├─────────────────────────────────────────────────────────┤
│ HDFC Bank               → Chunk 1 → Embedding           │
│   └─ market_cap: 15T    → Chunk 2 → Embedding          │
│   └─ change: +1.79%                                    │
│                                                          │
│ Infosys                 → Chunk 1 → Embedding           │
│   └─ market_cap: 8T     → Chunk 2 → Embedding          │
│   └─ change: +2.5%                                     │
│                                                          │
│ ... 500-800 companies                                   │
└─────────────────────────────────────────────────────────┘
```

---

## Time Breakdown

### Total Time: ~15-20 minutes

| Step | Time | What Happens |
|------|------|--------------|
| Parse CSV | 10s | Extract 500-800 companies |
| Create Graph | 2-3 min | ~800 nodes + 2,000 relationships |
| Create Chunks | 30s | 1,600 text chunks |
| Generate Embeddings | 10-15 min | 1,600 vectors via API |

---

## Real Example: Query Flow

### User Query: "Which Indian banks have market cap over 10 trillion?"

#### GraphRAG (Cypher)
```cypher
MATCH (c:Company)-[:IN_INDUSTRY]->(i:Industry)
WHERE i.name CONTAINS 'bank' 
  AND c.market_cap > 10000000000000
  AND c.country_code = 'IN'
RETURN c.company_name, c.market_cap
ORDER BY c.market_cap DESC
```

**Result:**
```
HDFC Bank - 15,091,541 INR
ICICI Bank - 10,234,567 INR
State Bank of India - 9,876,543 INR
```

#### VectorRAG (Semantic Search)
```
1. Generate embedding for query
2. Find similar chunks in CompanyOpenAI index
3. Return top matching companies:
   - HDFC Bank (0.95 similarity)
   - ICICI Bank (0.92 similarity)
   - SBI (0.89 similarity)
```

---

## Why This Takes Time

1. **Graph Creation**: 500-800 companies × 6 relationships each = ~3,000-4,800 relationship creations
2. **Chunking**: 500-800 companies × ~2 chunks = 1,000-1,600 text chunks
3. **Embeddings**: 1,000-1,600 API calls to OpenAI (rate limited)
4. **Batch Processing**: Split into batches for efficiency and error handling

---

## Production Deployment

To process all 7,591 companies:

1. **Remove filter**: Change `filter_country='IN'` to `None`
2. **Estimate time**: ~75-120 minutes total
3. **Resource needs**: More Neo4j memory, higher OpenAI costs
4. **Output**: ~15,000 chunks, ~50,000 relationships

---

**The pipeline is optimized for Indian companies (testing) and ready to scale to all companies (production).** 🚀

