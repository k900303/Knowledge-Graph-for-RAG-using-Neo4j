# Implementation Plan: Parameter & Period-Based RAG Queries

## Executive Summary

This plan outlines the implementation of RAG and tool calling for financial parameter queries with period support. The system will handle queries like:
- "What is the EBITA margin of the latest 2025 quarter?"
- "Compare the EBITA margin of two companies"
- Period variations: "latest", "Q1FY2025", "FY2025Q1", "quarter 2", "full year"

## Current Architecture Analysis

### Existing Relationships
```
Company -[:HAS_PARAMETER]-> Parameter -[:HAS_VALUE_IN_PERIOD]-> PeriodResult
```

**PeriodResult Node Properties:**
- `period`: Period string (e.g., "3QFY-2024", "FY-2024", "1HFY-2024")
- `actual_period`: Actual period value
- `value`: Numeric value
- `currency`: Currency code (e.g., "INR", "USD")
- `yoy_growth`: Year-over-year growth percentage
- `seq_growth`: Sequential growth percentage
- `data_type`: A=Actual, E=Estimated

### Existing Tools
1. ✅ `search_parameters` - Semantic search for parameter names
2. ✅ `search_company` - Search for companies
3. ✅ `generate_parameter_query` - Basic parameter query generation
4. ❌ **Missing**: Period search/validation tool
5. ❌ **Missing**: Period parsing/normalization tool
6. ❌ **Missing**: Parameter existence verification before LLM
7. ❌ **Missing**: Multi-company comparison tool
8. ❌ **Missing**: Smart period interpretation ("latest", "recent quarter")

## Implementation Plan

### Phase 1: Enhanced Parameter & Period Tools

#### 1.1 `search_periods` Tool
**Purpose**: Search and validate periods in database for a given company/parameter

**Functionality**:
- Query available periods for a parameter
- Support fuzzy matching for period strings
- Return periods sorted by recency
- Validate period existence before querying

**Tool Definition**:
```python
{
    "name": "search_periods",
    "description": "Search for available periods in database for a parameter/company. Use this to validate period names like 'Q1FY2025', 'FY2025Q1', 'latest', 'quarter 2', 'full year' before querying.",
    "parameters": {
        "parameter_name": "string",  # Exact parameter name from database
        "company_name": "string",    # Company name
        "period_hint": "string"     # User's period hint (e.g., "latest", "Q1", "2025")
    }
}
```

**Implementation**:
- Query Neo4j: `MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult) WHERE ... RETURN DISTINCT pr.period ORDER BY pr.period DESC`
- Fuzzy match period hints to actual periods
- Handle "latest" → most recent period
- Handle "Q1", "Q2", etc. → match quarter patterns
- Handle "FY2025" → match full year patterns

#### 1.2 `normalize_period` Tool
**Purpose**: Normalize user period input to database format

**Functionality**:
- Parse variations: "Q1FY2025", "FY2025Q1", "1QFY2025", "quarter 1 2025"
- Map to database format: "1QFY-2025"
- Handle "latest" → find most recent period
- Handle relative terms: "quarter 2", "full year 2024"

**Tool Definition**:
```python
{
    "name": "normalize_period",
    "description": "Normalize period strings like 'Q1FY2025', 'FY2025Q1', 'latest', 'quarter 2' to database format (e.g., '1QFY-2025'). Also handles 'latest' by finding most recent period.",
    "parameters": {
        "period_input": "string",      # User's period string
        "company_name": "string",       # Company name (for context)
        "parameter_name": "string"     # Parameter name (for validation)
    }
}
```

**Implementation**:
- Regex patterns for period formats
- Query database for available periods
- Match user input to closest period
- Return normalized period string

#### 1.3 `verify_parameter_exists` Tool (Critical)
**Purpose**: **Verify parameter exists in database BEFORE sending to LLM**

**Functionality**:
- Use fuzzy search to find closest matching parameter
- Verify exact parameter name exists for the company
- Return validation result with confidence score
- Prevent hallucinations by validating before LLM query generation

**Tool Definition**:
```python
{
    "name": "verify_parameter_exists",
    "description": "CRITICAL: Verify if a parameter name exists in database for a company. Use fuzzy matching to find closest match. Returns exact parameter name if found, or None if not found. ALWAYS use this before generating queries.",
    "parameters": {
        "parameter_hint": "string",   # User's parameter hint (e.g., "EBITA margin")
        "company_name": "string"       # Company name
    }
}
```

**Implementation**:
- Step 1: Use `search_parameters` with semantic search
- Step 2: Check if parameter exists for specific company
- Step 3: Return exact parameter name or suggest closest match
- Step 4: Log validation results

### Phase 2: Enhanced Query Generation

#### 2.1 Enhanced `generate_parameter_query` Tool
**Improvements**:
- ✅ Already exists but needs enhancement
- Add period normalization logic
- Add parameter verification (use `verify_parameter_exists` first)
- Better handling of "latest" period
- Support multi-period queries

**Enhanced Query Pattern**:
```cypher
MATCH (c:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr:PeriodResult)
WHERE c.company_name CONTAINS '{company_name}'
  AND p.parameter_name = '{exact_parameter_name}'  // Use exact name, not fuzzy
  AND pr.period = '{normalized_period}'             // Use normalized period
RETURN c.company_name, p.parameter_name, pr.period, pr.value, pr.currency, pr.yoy_growth
ORDER BY pr.period DESC
```

#### 2.2 New `generate_comparison_query` Tool
**Purpose**: Generate queries for comparing parameters across companies

**Tool Definition**:
```python
{
    "name": "generate_comparison_query",
    "description": "Generate Cypher query to compare a parameter between two or more companies. Use this when user asks 'compare X of company A and company B'.",
    "parameters": {
        "parameter_name": "string",        # Exact parameter name from database
        "company_names": ["string"],       # List of company names to compare
        "period": "string",                # Period (normalized)
        "comparison_type": "string"        # "side_by_side" or "difference"
    }
}
```

**Implementation**:
```cypher
MATCH (c1:Company)-[:HAS_PARAMETER]->(p:Parameter)-[:HAS_VALUE_IN_PERIOD]->(pr1:PeriodResult)
MATCH (c2:Company)-[:HAS_PARAMETER]->(p)-[:HAS_VALUE_IN_PERIOD]->(pr2:PeriodResult)
WHERE c1.company_name CONTAINS '{company1}'
  AND c2.company_name CONTAINS '{company2}'
  AND p.parameter_name = '{exact_parameter_name}'
  AND pr1.period = '{normalized_period}'
  AND pr2.period = '{normalized_period}'
RETURN c1.company_name, pr1.value as value1, pr1.currency,
       c2.company_name, pr2.value as value2, pr2.currency,
       (pr2.value - pr1.value) as difference,
       ((pr2.value - pr1.value) / pr1.value * 100) as percent_diff
```

### Phase 3: RAG Integration & Tool Calling Flow

#### 3.1 Updated Tool Calling System Prompt
**Enhanced System Message**:
```
You are a Cypher query expert for financial data. Use tools in this EXACT order:

1. ALWAYS use verify_parameter_exists FIRST when user mentions a parameter/metric
2. Use search_company to find exact company names
3. Use search_periods to validate and normalize period strings
4. Use normalize_period if period format is unclear
5. Use generate_parameter_query for single company queries
6. Use generate_comparison_query for multi-company comparisons

CRITICAL RULES:
- NEVER use parameter names that haven't been verified
- ALWAYS use exact parameter names from verify_parameter_exists
- Normalize periods before using in queries
- Handle "latest" by finding most recent period
```

#### 3.2 Query Flow Example

**User Query**: "What is the EBITA margin of the latest 2025 quarter for Kajaria Ceramics?"

**Tool Calling Flow**:
1. `verify_parameter_exists("EBITA margin", "Kajaria Ceramics")`
   - Returns: `"EBITA margin"` (exact match) or suggests closest match
   
2. `search_company("Kajaria Ceramics")`
   - Returns: `"Kajaria Ceramics Limited"` (exact company name)

3. `normalize_period("latest 2025 quarter", "Kajaria Ceramics", "EBITA margin")`
   - Queries available periods
   - Returns: `"1QFY-2025"` or `"2QFY-2025"` (most recent 2025 quarter)

4. `generate_parameter_query("Kajaria Ceramics Limited", ["EBITA margin"], "1QFY-2025")`
   - Generates final Cypher query

5. Execute query and return results

**Multi-Company Query**: "Compare the EBITA margin of Kajaria Ceramics and Asian Paints"

**Tool Calling Flow**:
1. `verify_parameter_exists("EBITA margin", "")` (check globally)
2. `search_company("Kajaria Ceramics")` → "Kajaria Ceramics Limited"
3. `search_company("Asian Paints")` → "Asian Paints Limited"
4. `normalize_period("latest", "", "EBITA margin")` → "1QFY-2025"
5. `generate_comparison_query("EBITA margin", ["Kajaria Ceramics Limited", "Asian Paints Limited"], "1QFY-2025")`
6. Execute and format comparison results

### Phase 4: Period Pattern Matching

#### 4.1 Period Format Patterns
```python
PERIOD_PATTERNS = {
    "latest": lambda: "ORDER BY pr.period DESC LIMIT 1",
    "Q1FY2025": r"1QFY-2025|Q1FY-2025|FY2025Q1",
    "Q2FY2025": r"2QFY-2025|Q2FY-2025|FY2025Q2",
    "quarter 1": r"1QFY-\d{4}",
    "quarter 2": r"2QFY-\d{4}",
    "full year": r"FY-\d{4}",
    "half year": r"\d{1}HFY-\d{4}",
}
```

#### 4.2 Period Normalization Logic
```python
def normalize_period(user_input: str, company_name: str, parameter_name: str) -> str:
    """
    Normalize user period input to database format
    
    Handles:
    - "latest" → most recent period
    - "Q1FY2025", "FY2025Q1", "1QFY2025" → "1QFY-2025"
    - "quarter 1", "Q1" → find matching quarter
    - "full year 2025", "FY2025" → "FY-2025"
    """
    # Query available periods for this company/parameter
    available_periods = query_available_periods(company_name, parameter_name)
    
    # If "latest", return most recent
    if user_input.lower() in ["latest", "recent", "most recent"]:
        return sorted(available_periods, reverse=True)[0]
    
    # Pattern matching for various formats
    # ... implementation
```

### Phase 5: Data Accuracy & Validation

#### 5.1 Pre-Query Validation Checklist
Before generating any Cypher query:
1. ✅ Parameter exists in database (use `verify_parameter_exists`)
2. ✅ Company exists in database (use `search_company`)
3. ✅ Period exists for that parameter/company (use `search_periods`)
4. ✅ All values normalized to database format

#### 5.2 Post-Query Validation
After executing query:
1. Check if results are empty → return empty (no hallucinations)
2. Verify returned data matches requested parameters
3. Log any mismatches for debugging

#### 5.3 Fuzzy Matching Strategy
For parameter names:
1. **Exact Match**: Direct string comparison
2. **Semantic Match**: Embedding-based similarity (existing `search_parameters`)
3. **Fuzzy Match**: Levenshtein distance for typos
4. **Synonym Match**: Common financial term mappings
   - "EBITA margin" ↔ "EBITA Margin" ↔ "EBITDA margin" (if different)
   - "Revenue" ↔ "Sales" ↔ "Turnover"

## Implementation Steps

### Step 1: Create New Tools (Priority: HIGH)
- [ ] Implement `verify_parameter_exists` tool
- [ ] Implement `search_periods` tool  
- [ ] Implement `normalize_period` tool
- [ ] Enhance `generate_parameter_query` with period normalization
- [ ] Implement `generate_comparison_query` tool

### Step 2: Update Tool Registry
- [ ] Register new tools in `ToolRegistry`
- [ ] Update tool definitions
- [ ] Add tool execution methods

### Step 3: Enhance System Prompt
- [ ] Update LLM system message with new tool ordering
- [ ] Add validation rules
- [ ] Add period handling instructions

### Step 4: Testing & Validation
- [ ] Test parameter verification accuracy
- [ ] Test period normalization for various formats
- [ ] Test "latest" period detection
- [ ] Test multi-company comparisons
- [ ] Validate no hallucinations occur

### Step 5: UI/UX Enhancements (Optional)
- [ ] Show parameter suggestions as user types
- [ ] Display available periods for selected parameter
- [ ] Show comparison visualizations

## Example Queries & Expected Behavior

### Query 1: "What is the EBITA margin of the latest 2025 quarter?"
**Expected Flow**:
1. Verify "EBITA margin" exists → Get exact name
2. Find "latest 2025 quarter" → Normalize to "1QFY-2025" (or most recent)
3. Generate query with exact parameter name and normalized period
4. Return only database values (no LLM synthesis)

### Query 2: "Compare the EBITA margin of Kajaria and Asian Paints"
**Expected Flow**:
1. Verify "EBITA margin" exists
2. Find both companies (exact names)
3. Use "latest" period (or normalize if specified)
4. Generate comparison query
5. Return side-by-side comparison with difference

### Query 3: "Show me Q2FY2025 revenue for Reliance"
**Expected Flow**:
1. Verify "revenue" exists → Get exact name (could be "Revenue", "Total Revenue", etc.)
2. Normalize "Q2FY2025" → "2QFY-2025"
3. Find "Reliance" → "Reliance Industries Limited"
4. Generate query
5. Return data

## Files to Modify

1. **`PEERS_RAG_tools.py`**
   - Add new tool classes
   - Enhance existing tools
   - Add period normalization logic

2. **`PEERS_RAG_graphRAG.py`**
   - Update system prompt
   - Add validation checks
   - Enhance query generation flow

3. **`templates/peers_rag_index.html`** (Optional)
   - Add parameter autocomplete
   - Show period suggestions

## Success Criteria

✅ **Accuracy**: 100% data accuracy - only database values shown
✅ **Validation**: All parameters verified before LLM query generation
✅ **Period Handling**: Supports all period formats mentioned by user
✅ **No Hallucinations**: Zero fabricated data in results
✅ **User Experience**: Natural language queries work seamlessly
✅ **Comparison Queries**: Multi-company comparisons work correctly

## Risk Mitigation

1. **Parameter Mismatch**: Use fuzzy + exact matching with confidence scores
2. **Period Ambiguity**: Query available periods and suggest closest match
3. **Missing Data**: Return empty results (no hallucinations)
4. **Performance**: Cache parameter lists and periods
5. **Multi-Format Periods**: Robust normalization with fallback patterns

---

**Next Action**: Review and approve plan, then proceed with Step 1 implementation.

