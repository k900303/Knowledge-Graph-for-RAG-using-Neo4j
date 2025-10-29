# India-Only Filter Applied

## Current Configuration

The PEERS RAG system is **currently configured to process only Indian companies** for testing purposes.

### What's Filtered

- **Country Code**: 'IN' (India)
- **Companies**: Only companies with `country_code = 'IN'`
- **Purpose**: Testing and validation before processing all ~7,591 companies

### Expected Results

When you run the pipeline, you should see:
- Approximately **500-800 Indian companies** (instead of 7,591)
- Much faster ingestion and processing
- Easier validation and testing

## How It Works

### In `PEERS_RAG_neo4j_ingestion.py`:
```python
# Line 20-27: Added filter_country parameter
def create_company_graph(self, parser: CSVParser, batch_size: int = 100, filter_country: str = None):
    """
    filter_country: Filter companies by country code (e.g., 'IN' for India)
    """
    
    # Line 40-42: Filter companies
    if filter_country:
        companies = [c for c in companies if c.country_code == filter_country]
```

### In `PEERS_RAG_pipeline.py`:
```python
# Line 47-48: Apply filter
self.ingestion.create_company_graph(self.parser, batch_size=100, filter_country='IN')
```

### In `PEERS_RAG_csv_chunking.py`:
```python
# Line 56-61: Filter companies for chunking too
filtered_companies = [c for c in companies if c.country_code == 'IN']
temp_parser.companies = filtered_companies
self.chunking.create_company_chunks(temp_parser, batch_size=100)
```

## To Run Pipeline

```bash
python PEERS_RAG_pipeline.py
```

Expected output will show:
```
[FILTER] Only processing companies from: IN
[FILTERED] 500-800 companies from IN
```

## To Disable Filter (Process All Companies)

### Option 1: Modify pipeline.py
Change line 48:
```python
# Change from:
self.ingestion.create_company_graph(self.parser, batch_size=100, filter_country='IN')

# To:
self.ingestion.create_company_graph(self.parser, batch_size=100)  # No filter
```

Also change line 56:
```python
# Remove the filter
filtered_companies = companies  # Use all companies
temp_parser.companies = filtered_companies
```

### Option 2: Set filter_country to None
```python
self.ingestion.create_company_graph(self.parser, batch_size=100, filter_country=None)
```

## Other Country Codes

You can test with other countries by changing 'IN' to other country codes such as:
- `'US'` - United States
- `'CN'` - China  
- `'GB'` - United Kingdom
- `'DE'` - Germany
- etc.

Example:
```python
self.ingestion.create_company_graph(self.parser, batch_size=100, filter_country='US')
```

## Benefits of Testing with India

1. **Faster processing** - ~500-800 companies vs 7,591
2. **Easier validation** - Smaller dataset to verify
3. **Lower Neo4j memory usage**
4. **Quicker embedding generation**
5. **Faster to iterate and test queries**

## Production Deployment

When ready for production:
1. Remove the `filter_country='IN'` parameter
2. Process all companies
3. Run full pipeline
4. Enable all features

---

**Note**: This filter is temporary for testing. Remove it when deploying to production.

