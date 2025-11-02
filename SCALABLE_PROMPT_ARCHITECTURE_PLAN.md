# Scalable & Future-Proof Prompt Architecture Plan

## 🔴 Current Problem Analysis

### Issue: Prompt Bloat & Interference

**Current Approach:**
- Single monolithic system prompt in `_generate_with_tools()`
- All instructions in one large prompt string
- Adding new use cases = extending the prompt
- Risk: New instructions may conflict with existing ones
- Risk: Token cost increases linearly with prompt size
- Risk: LLM may "forget" earlier instructions in long prompts

**Example Current Prompt Structure:**
```python
system_message = """You are a Cypher query expert. Use the available tools...
Process:
1. Use search_company...
2. Use search_parameters...
3. Generate Cypher query...
CRITICAL RULES:
- Rule 1...
- Rule 2...
... (grows indefinitely)
"""
```

## ✅ Proposed Solution: Modular Prompt Architecture

### Architecture Pattern: **Layered Prompt Composition**

```
┌─────────────────────────────────────────┐
│  Base Prompt (Core Principles)         │ ← Stable, rarely changes
├─────────────────────────────────────────┤
│  Domain-Specific Extensions             │ ← Modular, pluggable
│  ├─ Parameter Query Extensions         │
│  ├─ Period Handling Extensions         │
│  ├─ Comparison Query Extensions        │
│  └─ Future: Trend Analysis, etc.      │
├─────────────────────────────────────────┤
│  Dynamic Context (Runtime)              │ ← Built from query context
│  ├─ Detected Query Type                │
│  ├─ Required Tools                     │
│  └─ Validation Rules                   │
└─────────────────────────────────────────┘
```

---

## 🏗️ Implementation Strategy

### **Option 1: Template-Based Prompt Composition (Recommended)**

**Structure:**
```python
class PromptBuilder:
    """Modular prompt builder that composes prompts dynamically"""
    
    # Base prompt - core principles (stable)
    BASE_PROMPT = """You are a Cypher query expert for financial data.
    
Core Principles:
1. Always verify data exists before querying
2. Use exact names from database (never fabricate)
3. Validate before generating queries
    
Tool Usage Order:
1. verify_parameter_exists (ALWAYS FIRST for parameters)
2. search_company (for company names)
3. search_periods / normalize_period (for periods)
4. generate_parameter_query or generate_comparison_query
"""
    
    # Domain-specific extensions (pluggable modules)
    EXTENSIONS = {
        "parameter_query": """
Parameter Query Rules:
- Verify parameter exists before using
- Use exact parameter name from verification
- Support single or multiple parameters
""",
        
        "period_handling": """
Period Handling Rules:
- Normalize all period strings to database format
- Handle "latest" by querying most recent period
- Support multiple period formats: Q1FY2025, FY2025Q1, etc.
""",
        
        "comparison_query": """
Comparison Query Rules:
- Support 2+ companies
- Support 1+ parameters
- Support 1+ periods
- Return side-by-side comparison format
""",
        
        "multi_period_trend": """
Multi-Period Trend Rules:
- Order periods chronologically
- Calculate growth rates when requested
- Format as time-series data
"""
    }
    
    def build_prompt(self, query_type: str, extensions: List[str]) -> str:
        """
        Compose prompt dynamically based on query type
        
        Args:
            query_type: Detected query type
            extensions: List of extension keys to include
        """
        prompt = self.BASE_PROMPT
        
        # Add only relevant extensions
        for ext_key in extensions:
            if ext_key in self.EXTENSIONS:
                prompt += "\n\n" + self.EXTENSIONS[ext_key]
        
        return prompt
```

**Benefits:**
- ✅ Only loads relevant instructions (smaller prompts)
- ✅ Easy to add new extensions without touching base
- ✅ No interference between modules
- ✅ Can version/extend individual modules independently

---

### **Option 2: Configuration-Driven Prompts (Advanced)**

**Structure:**
```python
# prompts_config.yaml
base_prompt: |
  You are a Cypher query expert...
  
extensions:
  parameter_query:
    enabled: true
    priority: 1
    instructions: |
      Parameter Query Rules:...
  
  period_handling:
    enabled: true
    priority: 2
    instructions: |
      Period Handling Rules:...
  
  comparison_query:
    enabled: true
    priority: 3
    instructions: |
      Comparison Query Rules:...

# Load and compose at runtime
def load_prompt_config(config_path: str):
    config = yaml.load(config_path)
    return compose_prompt(config)
```

**Benefits:**
- ✅ Non-code changes (edit YAML files)
- ✅ A/B testing different prompt versions
- ✅ Environment-specific prompts (dev/staging/prod)
- ✅ Easy rollback

---

### **Option 3: LLM Chain with Specialized Models (Future)**

**Structure:**
```
Query → Router LLM → Specialized LLMs
                 ├─ Parameter Query LLM (focused prompt)
                 ├─ Comparison LLM (focused prompt)
                 └─ Trend Analysis LLM (focused prompt)
```

**Benefits:**
- ✅ Each LLM has focused, small prompt
- ✅ No interference between use cases
- ✅ Can optimize each prompt independently
- ⚠️ More complex architecture

---

## 🎯 Recommended Implementation: Hybrid Approach

### **Phase 1: Modular Prompt Builder (Immediate)**

```python
class ModularPromptBuilder:
    """Build prompts dynamically based on detected query type"""
    
    def __init__(self):
        self.base_prompt = self._load_base_prompt()
        self.extensions = self._load_extensions()
    
    def build_for_query(self, user_query: str) -> str:
        """
        Detect query type and build focused prompt
        """
        # Detect what capabilities are needed
        needs = {
            "parameters": self._needs_parameters(user_query),
            "periods": self._needs_periods(user_query),
            "comparison": self._needs_comparison(user_query),
            "multi_period": self._needs_multi_period(user_query)
        }
        
        # Compose minimal prompt
        prompt = self.base_prompt
        
        if needs["parameters"]:
            prompt += "\n\n" + self.extensions["parameter_query"]
        
        if needs["periods"]:
            prompt += "\n\n" + self.extensions["period_handling"]
        
        if needs["comparison"]:
            prompt += "\n\n" + self.extensions["comparison_query"]
        
        if needs["multi_period"]:
            prompt += "\n\n" + self.extensions["multi_period_trend"]
        
        return prompt
```

**Query Analysis Example:**
```python
Query: "Compare EBITA margin of Kajaria and Asian Paints for Q1, Q2, Q3"

Detected Needs:
✅ parameters (EBITA margin)
✅ periods (Q1, Q2, Q3)
✅ comparison (Kajaria vs Asian Paints)
✅ multi_period (3 periods)

Prompt Includes:
- Base prompt (always)
- Parameter query extension
- Period handling extension
- Comparison query extension
- Multi-period extension

Total Prompt Size: ~800 tokens (vs ~2000 if monolithic)
```

---

### **Phase 2: Prompt Versioning & Testing**

```python
class PromptVersionManager:
    """Manage prompt versions and A/B testing"""
    
    def __init__(self):
        self.versions = {
            "parameter_query_v1": "...",
            "parameter_query_v2": "...",  # Improved version
            "period_handling_v1": "...",
            "period_handling_v2": "..."   # With new patterns
        }
    
    def get_prompt(self, extension_key: str, version: str = "latest") -> str:
        """Get specific version or latest"""
        if version == "latest":
            # Get most recent version
            return self._get_latest_version(extension_key)
        return self.versions.get(f"{extension_key}_{version}")
```

**Benefits:**
- ✅ Test new prompt versions without breaking existing
- ✅ Gradual rollout (e.g., 10% traffic to v2)
- ✅ Easy rollback if issues found
- ✅ Track performance per version

---

### **Phase 3: Context-Aware Prompt Selection**

```python
def select_prompt_strategy(query: str) -> Dict:
    """
    Analyze query and select minimal prompt components
    
    Returns:
        {
            "base": True,
            "extensions": ["parameter_query", "period_handling", "comparison"],
            "estimated_tokens": 850,
            "complexity": "medium"
        }
    """
    # NLP analysis of query
    entities = extract_entities(query)
    
    needs = {
        "parameter_query": has_parameter_mentions(entities),
        "period_handling": has_period_mentions(entities),
        "comparison": has_multiple_companies(entities),
        "multi_period": has_multiple_periods(entities),
        "trend_analysis": has_trend_keywords(query)
    }
    
    return {
        "extensions": [k for k, v in needs.items() if v],
        "estimated_tokens": estimate_token_count(needs),
        "complexity": assess_complexity(needs)
    }
```

---

## 📊 Token Efficiency Analysis

### **Monolithic Approach (Current Risk)**
```
All instructions always included: ~2000 tokens
+ Context: ~500 tokens
+ Query: ~50 tokens
────────────────────
Total per query: ~2550 tokens

As use cases grow:
+10 use cases = +2000 tokens
Total: ~4550 tokens per query ❌
```

### **Modular Approach (Proposed)**
```
Base prompt: ~400 tokens (stable)
+ Only needed extensions: ~300-800 tokens
+ Context: ~500 tokens  
+ Query: ~50 tokens
────────────────────
Total per query: ~1250-1750 tokens ✅

As use cases grow:
+10 use cases = +0 tokens (only loaded if needed)
Total: Still ~1250-1750 tokens per query ✅
```

**Savings: 40-60% token reduction per query**

---

## 🔧 Implementation Plan

### **Step 1: Refactor Current Prompt (Low Risk)**

**Current:**
```python
system_message = """... (all instructions in one block) ..."""
```

**Refactored:**
```python
class PromptBuilder:
    BASE_PROMPT = "..."
    EXTENSIONS = {...}
    
    def build(self, query_type): ...
```

### **Step 2: Query Type Detection**

```python
def detect_query_type(user_query: str) -> Dict[str, bool]:
    """
    Detect what extensions are needed
    Returns: {"needs_parameters": True, "needs_periods": True, ...}
    """
    return {
        "needs_parameters": bool(re.search(r"(revenue|profit|margin|ebita)", query, re.I)),
        "needs_periods": bool(re.search(r"(quarter|q1|q2|fy|latest)", query, re.I)),
        "needs_comparison": bool(re.search(r"(compare|versus|vs|between)", query, re.I)),
        "needs_multi_period": len(extract_periods(query)) > 1,
        "needs_multi_company": len(extract_companies(query)) > 1
    }
```

### **Step 3: Dynamic Prompt Composition**

```python
def _generate_with_tools(self, question: str) -> str:
    # Detect query type
    query_type = detect_query_type(question)
    
    # Build focused prompt
    prompt_builder = ModularPromptBuilder()
    system_message = prompt_builder.build_for_query_type(query_type)
    
    # Use focused prompt (smaller, faster, cheaper)
    messages = [
        HumanMessage(content=system_message),
        HumanMessage(content=f"Question: {question}")
    ]
    
    # Rest of tool calling logic...
```

---

## 🚀 Future-Proofing Strategies

### **1. Extension Registry Pattern**

```python
class PromptExtensionRegistry:
    """Central registry for all prompt extensions"""
    
    extensions = {}
    
    @classmethod
    def register(cls, name: str, version: str, prompt: str):
        """Register new extension"""
        key = f"{name}_v{version}"
        cls.extensions[key] = prompt
    
    @classmethod
    def get(cls, name: str, version: str = "latest"):
        """Get extension (auto-selects latest version)"""
        if version == "latest":
            versions = [k for k in cls.extensions.keys() if k.startswith(name)]
            latest = sorted(versions)[-1]
            return cls.extensions[latest]
        return cls.extensions.get(f"{name}_v{version}")

# Usage: Easy to add new extensions
PromptExtensionRegistry.register(
    "trend_analysis", 
    "1",
    "Trend Analysis Rules: ..."
)
```

### **2. Prompt Testing Framework**

```python
class PromptTester:
    """Test prompts against query suite"""
    
    def test_extension(self, extension_name: str, test_queries: List[str]):
        """Test if extension handles queries correctly"""
        results = []
        for query in test_queries:
            prompt = build_prompt_with_extension(extension_name)
            result = test_query(query, prompt)
            results.append(result)
        return analyze_results(results)
```

### **3. Prompt Performance Monitoring**

```python
class PromptMonitor:
    """Monitor prompt effectiveness"""
    
    def track_performance(self, prompt_config: str, query: str, result: Dict):
        """Track which prompt configs work best"""
        metrics = {
            "tokens_used": count_tokens(prompt_config),
            "accuracy": result["accuracy"],
            "latency": result["latency"],
            "cost": calculate_cost(result["tokens"])
        }
        self.log_metrics(prompt_config, metrics)
```

---

## ✅ Recommended Implementation Structure

```
PEERS_RAG_prompts/
├── base_prompt.py          # Core principles (stable)
├── extensions/
│   ├── parameter_query.py      # Parameter handling
│   ├── period_handling.py      # Period normalization
│   ├── comparison_query.py     # Multi-company queries
│   ├── multi_period.py         # Multiple periods
│   └── trend_analysis.py        # Future: trends
├── prompt_builder.py       # Composition logic
├── query_analyzer.py       # Detect query type
└── prompt_config.yaml      # Configuration (optional)
```

**Usage:**
```python
from PEERS_RAG_prompts import PromptBuilder, QueryAnalyzer

analyzer = QueryAnalyzer()
builder = PromptBuilder()

query_type = analyzer.analyze(user_query)
prompt = builder.build(query_type)

# Use focused prompt (40-60% smaller)
```

---

## 📈 Scalability Metrics

| Aspect | Monolithic | Modular |
|--------|-----------|---------|
| **Initial Prompt Size** | ~2000 tokens | ~400 tokens (base) |
| **Per-Query Size** | ~2550 tokens | ~1250 tokens |
| **Adding 10 Use Cases** | +2000 tokens | +0 tokens (if not used) |
| **Maintenance** | Edit one large file | Edit small modules |
| **Testing** | Test entire prompt | Test individual modules |
| **Version Control** | Single version | Version per module |
| **Rollback Risk** | High (all or nothing) | Low (module-level) |

---

## 🎯 Action Items

### **Immediate (Phase 1):**
1. ✅ Extract base prompt (core principles)
2. ✅ Create extension modules for existing use cases
3. ✅ Implement query type detection
4. ✅ Refactor `_generate_with_tools` to use modular prompts

### **Short-term (Phase 2):**
5. ✅ Add prompt versioning system
6. ✅ Implement prompt performance monitoring
7. ✅ Create prompt testing framework

### **Long-term (Phase 3):**
8. ✅ Configuration-driven prompts (YAML)
9. ✅ A/B testing infrastructure
10. ✅ Prompt optimization based on metrics

---

## 💡 Key Benefits

1. **Token Efficiency**: 40-60% reduction per query
2. **No Interference**: New extensions don't affect existing
3. **Easy Extension**: Add new use cases by adding modules
4. **Maintainable**: Small, focused modules vs monolithic prompt
5. **Testable**: Test each extension independently
6. **Versionable**: Version and rollback per module
7. **Future-Proof**: Scales indefinitely without prompt bloat

---

**Bottom Line**: This architecture ensures that as you add 10, 20, or 100 new use cases, your prompt size stays constant (only loads what's needed), costs stay low, and existing functionality remains unaffected.

