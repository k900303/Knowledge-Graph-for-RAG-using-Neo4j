# PEERS RAG Modular Prompt System

## 📁 Directory Structure

```
PEERS_RAG_prompts/
├── __init__.py                 # Package initialization
├── base_prompt.py              # Core prompt (stable, rarely changes)
├── prompt_builder.py           # Composes prompts dynamically
├── query_analyzer.py           # Analyzes queries to detect needs
├── README.md                   # This file
└── extensions/
    ├── __init__.py             # Extension registry
    ├── parameter_query.py      # Parameter handling extension
    ├── period_handling.py      # Period normalization extension
    ├── comparison_query.py     # Multi-company comparison extension
    └── multi_period.py         # Multi-period/trend extension
```

## 🎯 How It Works

### **1. Query Analysis**
When a user query comes in, `QueryAnalyzer` detects what capabilities are needed:
- Parameters mentioned? → Load `parameter_query` extension
- Periods mentioned? → Load `period_handling` extension
- Multiple companies? → Load `comparison_query` extension
- Multiple periods? → Load `multi_period` extension

### **2. Dynamic Prompt Composition**
`ModularPromptBuilder` composes the prompt by:
1. Starting with `base_prompt.py` (always included)
2. Adding only the extensions that are needed
3. Returning a focused, efficient prompt

### **3. Usage in GraphRAG**
`PEERS_RAG_graphRAG.py` uses this system automatically:
```python
from PEERS_RAG_prompts import ModularPromptBuilder, QueryAnalyzer

# Analyze query
query_analyzer = QueryAnalyzer(log_manager=self.log_manager)
query_analysis = query_analyzer.analyze(question)

# Build focused prompt
prompt_builder = ModularPromptBuilder(log_manager=self.log_manager)
system_message = prompt_builder.build_for_query_type(query_analysis)
```

## ✅ Benefits

1. **Token Efficiency**: Only loads what's needed (~40-60% reduction)
2. **No Interference**: New extensions don't affect existing ones
3. **Easy Extension**: Add new use cases by creating new extension files
4. **Debuggable**: Clear logging shows which extensions are loaded
5. **Maintainable**: Small, focused modules vs monolithic prompt
6. **Future-Proof**: Scales indefinitely without prompt bloat

## 🔧 Adding New Extensions

### Step 1: Create Extension File
Create a new file in `extensions/`:
```python
# extensions/trend_analysis.py
TREND_ANALYSIS_EXTENSION = """
TREND ANALYSIS RULES:
- Calculate growth rates when requested
- Show progression over time
...
"""
```

### Step 2: Register Extension
Add to `extensions/__init__.py`:
```python
from PEERS_RAG_prompts.extensions.trend_analysis import TREND_ANALYSIS_EXTENSION

EXTENSION_REGISTRY = {
    ...
    'trend_analysis': TREND_ANALYSIS_EXTENSION,
}
```

### Step 3: Update Query Analyzer
Add detection logic in `query_analyzer.py`:
```python
TREND_KEYWORDS = ['trend', 'growth', 'over time', ...]

# In analyze() method:
needs_trend = any(keyword in query_lower for keyword in self.TREND_KEYWORDS)
```

### Step 4: Update Prompt Builder
The builder will automatically use it if detected by analyzer.

## 🐛 Debugging

### Check Which Extensions Are Loaded
Look for log messages:
```
[INFO] Query Analysis: Detected needs -> parameter_query, period_handling, comparison
[INFO] Prompt Builder: Loaded extensions -> parameter_query, period_handling, comparison
[INFO] Modular Prompt: ~1250 tokens (composed dynamically)
```

### Force Load Specific Extensions
For testing, you can manually build prompts:
```python
builder = ModularPromptBuilder()
prompt = builder.build(['parameter_query', 'period_handling'])
```

### View All Available Extensions
```python
builder = ModularPromptBuilder()
print(builder.get_available_extensions())
# ['parameter_query', 'period_handling', 'comparison_query', 'multi_period']
```

## 📊 File Responsibilities

| File | Responsibility | When to Edit |
|------|---------------|--------------|
| `base_prompt.py` | Core principles | Rarely - only for fundamental changes |
| `query_analyzer.py` | Detect query needs | When adding new query patterns |
| `prompt_builder.py` | Compose prompts | When adding new composition logic |
| `extensions/*.py` | Domain-specific rules | Frequently - add new use cases here |

## 🚀 Example: Adding a New Use Case

**Scenario**: Add support for aggregation queries (e.g., "Show me total revenue across all companies")

1. **Create extension**: `extensions/aggregation_query.py`
2. **Register it**: Add to `extensions/__init__.py`
3. **Detect it**: Update `query_analyzer.py` to detect aggregation keywords
4. **Done!** The system will automatically use it when needed

No changes needed to:
- `base_prompt.py`
- `prompt_builder.py`
- `PEERS_RAG_graphRAG.py` (already uses the system)

## 📝 Best Practices

1. **Keep extensions focused**: Each extension should handle one domain
2. **Don't modify base_prompt.py**: It's the stable foundation
3. **Log everything**: Use log_manager for debugging
4. **Test individually**: Test each extension in isolation
5. **Version extensions**: Consider versioning if making breaking changes

## 🔍 Monitoring

Check prompt sizes in logs:
- Base prompt: ~400 tokens
- Each extension: ~200-300 tokens
- Total composed: Only includes what's needed

Example:
- Query needs: `parameter_query` + `period_handling`
- Prompt size: ~400 (base) + ~200 (param) + ~200 (period) = ~800 tokens ✅
- Old monolithic: ~2000 tokens ❌

