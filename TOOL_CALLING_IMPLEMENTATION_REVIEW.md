# Tool Calling Implementation Review

## 🔍 Current Implementation Analysis

### ✅ **What's Working Well**

1. **Tool Registry Pattern** ✓
   - Centralized tool management
   - Clean separation of concerns
   - Easy to add new tools

2. **Tool Binding** ✓
   - Uses `llm.bind_tools(tool_definitions)` correctly
   - Proper LangChain pattern

3. **Iteration Control** ✓
   - Max iterations (5) prevents infinite loops
   - Proper loop management

4. **Duplicate Detection** ✓
   - Prevents same tool from being called twice in same iteration
   - Good performance optimization

5. **Error Handling** ✓
   - Try-catch around tool execution
   - Error messages returned to LLM

---

## ⚠️ **Issues Found & Recommendations**

### **Issue 1: System Message Format**

**Current Code (Line 890-892):**
```python
messages = [
    HumanMessage(content=system_message),  # ❌ System message as HumanMessage
    HumanMessage(content=f"Question: {question}")
]
```

**Problem**: System message should use `SystemMessage`, not `HumanMessage`.

**Impact**: 
- LangChain may not treat it as system-level instructions
- Could affect prompt structure and model behavior

**Fix Required:**
```python
from langchain_core.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage(content=system_message),  # ✅ Correct
    HumanMessage(content=f"Question: {question}")
]
```

---

### **Issue 2: Tool Result Format**

**Current Code (Line 990-993):**
```python
tool_message = ToolMessage(
    content=json.dumps(tool_result, indent=2),  # ❌ Full JSON dump
    tool_call_id=tool_call_id
)
```

**Problem**: 
- `json.dumps()` with `indent=2` creates verbose output
- Increases token count unnecessarily
- May cause parsing issues if too large

**Impact**: 
- Higher token costs
- Slower processing
- Potential truncation issues

**Recommendation:**
```python
# Option 1: Compact JSON (recommended)
content = json.dumps(tool_result, separators=(',', ':'))

# Option 2: String representation if simple
content = str(tool_result) if isinstance(tool_result, (dict, list)) else tool_result
```

---

### **Issue 3: Response Content Extraction**

**Current Code (Line 1013-1014):**
```python
final_content = response.content if hasattr(response, 'content') else str(response)
cypher_query = self._extract_cypher_query(final_content)
```

**Potential Issues:**
- May not handle AIMessage properly if response structure changes
- Fallback to `str(response)` might not extract Cypher correctly

**Recommendation:**
```python
# More robust extraction
if hasattr(response, 'content'):
    final_content = response.content
elif isinstance(response, AIMessage):
    final_content = response.content or ""
else:
    final_content = str(response)

# Also check tool_calls are empty before extracting
if hasattr(response, 'tool_calls') and response.tool_calls:
    # Still has tool calls, shouldn't extract final answer
    continue
```

---

### **Issue 4: Missing Tool Call Validation**

**Current Code (Line 908):**
```python
tool_calls = getattr(response, 'tool_calls', None) or []
```

**Issue**: No validation that tool_calls are valid before execution.

**Recommendation:**
```python
tool_calls = getattr(response, 'tool_calls', None) or []

# Validate tool calls
if tool_calls:
    valid_tool_calls = []
    for tc in tool_calls:
        if hasattr(tc, 'name') and hasattr(tc, 'args'):
            valid_tool_calls.append(tc)
        else:
            if self.log_manager:
                self.log_manager.add_warning_log(f'Invalid tool call structure: {tc}')
    tool_calls = valid_tool_calls
```

---

### **Issue 5: Tool Execution Error Handling**

**Current Code (Line 996-1005):**
```python
except Exception as e:
    tool_message = ToolMessage(
        content=json.dumps({"error": str(e)}),
        tool_call_id=tool_call_id
    )
```

**Issue**: Generic error handling - doesn't distinguish between tool errors and system errors.

**Recommendation:**
```python
except KeyError as e:
    # Missing required argument
    error_msg = {"error": f"Missing required argument: {str(e)}", "type": "validation_error"}
except ValueError as e:
    # Invalid argument value
    error_msg = {"error": f"Invalid argument value: {str(e)}", "type": "validation_error"}
except Exception as e:
    # Unexpected error
    error_msg = {"error": f"Tool execution failed: {str(e)}", "type": "execution_error"}
    if self.log_manager:
        self.log_manager.add_error_log(f'Unexpected error in tool {tool_name}: {str(e)}', e)

tool_message = ToolMessage(
    content=json.dumps(error_msg),
    tool_call_id=tool_call_id
)
```

---

## 🎯 **Best Practices Recommendations**

### **1. Message Handling**

✅ **DO:**
```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

messages = [
    SystemMessage(content=system_message),
    HumanMessage(content=question)
]

# After tool execution
messages.append(AIMessage(...))  # LLM response with tool_calls
messages.extend(tool_messages)   # Tool results
```

### **2. Tool Result Format**

✅ **DO:**
- Keep tool results concise
- Use structured format (JSON without excessive whitespace)
- Truncate very long results

```python
def format_tool_result(result: Dict) -> str:
    """Format tool result for LLM consumption"""
    if isinstance(result, dict):
        # Remove verbose fields if needed
        compact = {k: v for k, v in result.items() if v}
        # Truncate long strings
        for k, v in compact.items():
            if isinstance(v, str) and len(v) > 500:
                compact[k] = v[:500] + "... (truncated)"
        return json.dumps(compact, separators=(',', ':'))
    return str(result)
```

### **3. Response Validation**

✅ **DO:**
```python
def validate_response(response) -> bool:
    """Validate LLM response before processing"""
    if not hasattr(response, 'content'):
        return False
    
    # If has tool_calls, should be AIMessage
    if hasattr(response, 'tool_calls') and response.tool_calls:
        if not isinstance(response, AIMessage):
            return False
    
    return True
```

### **4. Early Exit Conditions**

✅ **DO:**
```python
# Check if we have final answer before more iterations
if not tool_calls and response.content:
    cypher = self._extract_cypher_query(response.content)
    if self._is_valid_cypher(cypher):
        return cypher
```

---

## 📊 **Comparison: Current vs Improved**

| Aspect | Current | Improved | Benefit |
|--------|---------|----------|----------|
| **System Message** | HumanMessage | SystemMessage | Proper semantic meaning |
| **Tool Results** | Verbose JSON | Compact JSON | ~30% token reduction |
| **Error Handling** | Generic | Specific | Better debugging |
| **Validation** | Basic | Comprehensive | More robust |
| **Response Check** | Simple | Validated | Fewer edge cases |

---

## 🔧 **Priority Fixes**

### **High Priority (Fix Immediately)**
1. ✅ Change `HumanMessage` to `SystemMessage` for system prompt
2. ✅ Optimize tool result formatting (compact JSON)
3. ✅ Add response validation before final extraction

### **Medium Priority (Improve Soon)**
4. ✅ Add tool call validation
5. ✅ Improve error categorization
6. ✅ Add early exit conditions

### **Low Priority (Nice to Have)**
7. ⚪ Add response caching
8. ⚪ Add tool usage analytics
9. ⚪ Add tool call timeouts

---

## ✅ **Correct Implementation Pattern**

```python
def _generate_with_tools(self, question: str) -> str:
    """Generate Cypher query using Tool Calling (IMPROVED VERSION)"""
    
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
    
    # Build modular prompt
    query_analyzer = QueryAnalyzer(log_manager=self.log_manager)
    query_analysis = query_analyzer.analyze(question)
    prompt_builder = ModularPromptBuilder(log_manager=self.log_manager)
    system_message = prompt_builder.build_for_query_type(query_analysis)
    
    # ✅ CORRECT: Use SystemMessage
    messages = [
        SystemMessage(content=system_message),
        HumanMessage(content=f"Question: {question}")
    ]
    
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        # Invoke LLM
        response = self.llm_with_tools.invoke(messages)
        
        # ✅ CORRECT: Validate response
        if not isinstance(response, AIMessage):
            break
        
        # ✅ CORRECT: Check for tool calls
        tool_calls = getattr(response, 'tool_calls', None) or []
        
        if tool_calls:
            # ✅ CORRECT: Add AIMessage to conversation
            messages.append(response)
            
            # Execute tools
            tool_messages = []
            for tool_call in tool_calls:
                # ✅ CORRECT: Extract tool info
                tool_name = getattr(tool_call, 'name', '')
                tool_args = getattr(tool_call, 'args', {})
                tool_call_id = getattr(tool_call, 'id', '')
                
                try:
                    # Execute tool
                    result = self.tool_registry.execute_tool(tool_name, **tool_args)
                    
                    # ✅ CORRECT: Compact format
                    content = self._format_tool_result(result)
                    
                    # ✅ CORRECT: Create ToolMessage
                    tool_message = ToolMessage(
                        content=content,
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
                    
                except Exception as e:
                    # ✅ CORRECT: Specific error handling
                    error_content = json.dumps({
                        "error": str(e),
                        "type": type(e).__name__
                    })
                    tool_message = ToolMessage(
                        content=error_content,
                        tool_call_id=tool_call_id
                    )
                    tool_messages.append(tool_message)
            
            # ✅ CORRECT: Add tool results
            messages.extend(tool_messages)
            iteration += 1
            continue
        
        # ✅ CORRECT: No tool calls - extract final answer
        if response.content:
            cypher = self._extract_cypher_query(response.content)
            if self._is_valid_cypher(cypher):
                return cypher
        
        # If no valid Cypher, break and use fallback
        break
    
    # Fallback query
    return self._generate_smart_fallback_query(question) or \
           "MATCH (c:Company) RETURN c.company_name, c.cid LIMIT 10"
```

---

## 🎯 **Summary**

### **Overall Assessment: 7/10**

**Strengths:**
- ✅ Good architecture (tool registry pattern)
- ✅ Proper iteration control
- ✅ Duplicate detection
- ✅ Basic error handling

**Needs Improvement:**
- ⚠️ System message format (High Priority)
- ⚠️ Tool result formatting (High Priority)
- ⚠️ Response validation (High Priority)
- ⚠️ Error categorization (Medium Priority)

**Recommendation:** Fix the high-priority items first, then gradually improve others.

