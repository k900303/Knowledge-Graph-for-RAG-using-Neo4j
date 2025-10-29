<!-- 866c04a9-b31f-4664-8765-75e34feb678b 3e51032a-6e53-4172-8219-4e3bb220b574 -->
# Optimize Parameter & Results CSV Column Selection

## Goal

Create leaner, higher-quality CSV files by keeping only essential columns, reducing file size and improving processing speed.

## Column Selection

### Parameters CSV - Keep 6 Fields Only

```
param_id, parameter_name, parameter_type, cid, unit, isprimary
```

**Rationale**: These provide complete identification, type classification, and primary flag for filtering. Remove all formula, sector, display name fields.

### Results CSV - Keep 11 Fields

```
id, cid, pid, period, actual_period, value, currency, unit, data_type, yoy_growth, seq_growth
```

**Rationale**: Core identification + value + growth metrics. Remove modified dates, source details, nominal changes, currency symbols, and other metadata.

## Implementation Steps

### 1. Update filter_kajaria_data.py

Modify the CSV filtering script to:

- Add column selection logic for parameters (6 columns)
- Add column selection logic for results (11 columns)  
- Write new headers and only selected columns to output files
- Keep the existing cid=18315 and parameter_type filtering logic

### 2. Regenerate Filtered CSV Files

Run the updated script to create:

- `parameters_kajaria_cid_18315.csv` - 6 columns only (currently 35)
- `results_kajaria_cid_18315.csv` - 11 columns only (currently ~40)

### 3. Update csv_parser.py Dataclasses

**Parameter dataclass** - reduce to 6 fields:

```python
@dataclass
class Parameter:
    param_id: str
    parameter_name: str
    parameter_type: str
    cid: str
    unit: str
    isprimary: int
```

**PeriodResult dataclass** - reduce to 11 fields:

```python
@dataclass
class PeriodResult:
    id: str
    cid: str
    pid: str
    period: str
    actual_period: str
    value: float
    currency: str
    unit: int
    data_type: str
    yoy_growth: float
    seq_growth: float
```

### 4. Update Parsers to Match New CSV Structure

- Update `ParameterParser.parse()` to read only 6 columns
- Update `ResultsParser.parse()` to read only 11 columns
- Update column index references to match new structure
- Remove all references to removed fields

### 5. Update Neo4j Ingestion

**PEERS_RAG_neo4j_ingestion.py**:

- Update `_create_parameter_batch()` - use only 6 parameter fields
- Update `_create_period_result_batch()` - use only 11 result fields
- Remove any references to deleted fields in Cypher queries

### 6. Update Chunking Methods

**PEERS_RAG_csv_chunking.py**:

- Update `generate_parameter_text()` - use only available fields
- Update `generate_period_result_text()` - use only available fields
- Remove references to deleted fields like dpname, formula values, etc.

## Benefits

1. **Smaller Files**: Parameters CSV reduced from 35 to 6 columns (~83% reduction), Results from ~40 to 11 columns (~72% reduction)
2. **Faster Processing**: Less data to parse, validate, and load into memory
3. **Better Quality**: Only essential, validated fields - no unused metadata
4. **Clearer Code**: Simpler dataclasses, easier to understand and maintain
5. **Lower Memory**: Reduced memory footprint for large datasets

## Files to Modify

1. `filter_kajaria_data.py` - Add column selection logic
2. `csv_parser.py` - Reduce dataclass fields and update parsers
3. `PEERS_RAG_neo4j_ingestion.py` - Update ingestion to use fewer fields
4. `PEERS_RAG_csv_chunking.py` - Update text generation for fewer fields
5. Regenerated CSV files with optimized columns

### To-dos

- [ ] Update filter_kajaria_data.py to select only 6 parameter columns and 11 result columns
- [ ] Run updated filter script to create optimized CSV files with selected columns only
- [ ] Update Parameter and PeriodResult dataclasses in csv_parser.py to match new column structure
- [ ] Update ParameterParser and ResultsParser to read only selected columns from new CSV structure
- [ ] Update PEERS_RAG_neo4j_ingestion.py to use only available fields in Cypher queries
- [ ] Update PEERS_RAG_csv_chunking.py text generation to use only available fields