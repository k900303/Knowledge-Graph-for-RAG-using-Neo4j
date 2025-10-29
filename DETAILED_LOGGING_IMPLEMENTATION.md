# Detailed Logging Implementation

## Overview
Enhanced the live logging system to capture exact line numbers, file names, function names, and full stack traces when errors occur. This provides precise debugging information to identify exactly where issues happen in the code.

## Key Enhancements

### 1. Enhanced LogManager (`PEERS_RAG_flask_app.py`)

#### New Methods:
- `add_error_log(message, exception=None)`: Captures full traceback and caller info
- `add_info_log(message, file_info=None)`: Captures caller file/line info

#### Features:
- **File Information**: Captures filename, line number, and function name
- **Stack Traces**: Full Python traceback for errors
- **Thread Safety**: Maintains thread-safe logging
- **Automatic Caller Detection**: Uses `inspect` module to get caller info

### 2. Frontend Enhancements (`templates/peers_rag_index.html`)

#### New UI Elements:
- **File Info Display**: Shows `filename:line in function()`
- **Expandable Stack Traces**: Click to show/hide full traceback
- **Enhanced Styling**: Better visual hierarchy for error details

#### Features:
- **Collapsible Tracebacks**: Click "Show/Hide Stack Trace" to expand
- **Syntax Highlighting**: Monospace font for code readability
- **Scrollable Traces**: Long tracebacks are scrollable
- **Visual Indicators**: File icons and color coding

### 3. GraphRAG Detailed Logging (`PEERS_RAG_graphRAG.py`)

#### Log Points:
- Initialization steps
- Schema retrieval
- LangChain chain execution
- Query generation success/failure
- Response length tracking

#### Error Handling:
- Full exception capture with traceback
- Detailed error context
- File/line information for debugging

### 4. VectorRAG Detailed Logging (`PEERS_RAG_vectorRAG.py`)

#### Log Points:
- Neo4jVector store initialization
- Prompt loading
- Chain creation
- Similarity search execution
- Document retrieval stats

#### Error Handling:
- Initialization error tracking
- Search failure details
- Context information logging

## Example Log Output

### Success Log:
```
[14:32:15] [INFO] Starting Cypher query generation for: "Which companies are in Technology?"
📁 PEERS_RAG_graphRAG.py:95 in generate_cypher_query()
[14:32:15] [INFO] Retrieved graph schema with 6 node types
📁 PEERS_RAG_graphRAG.py:101 in generate_cypher_query()
[14:32:16] [INFO] Calling LangChain GraphCypherQAChain...
📁 PEERS_RAG_graphRAG.py:107 in generate_cypher_query()
[14:32:17] [SUCCESS] Query completed in 1.23s
```

### Error Log with Stack Trace:
```
[14:32:15] [ERROR] Failed to generate Cypher query: ConnectionError: Unable to connect to Neo4j
📁 PEERS_RAG_graphRAG.py:118 in generate_cypher_query()
🔍 Show/Hide Stack Trace
Traceback (most recent call last):
  File "PEERS_RAG_graphRAG.py", line 109, in generate_cypher_query
    response = self.cypher_chain.run(question)
  File "/usr/local/lib/python3.9/site-packages/langchain/chains/base.py", line 140, in run
    return self(inputs, return_only_outputs=True)
  File "neo4j_env.py", line 32, in __init__
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
ConnectionError: Unable to connect to Neo4j database
```

## Debugging Workflow

1. **Submit Query**: User enters query and clicks submit
2. **Watch Logs**: Real-time logs show each step
3. **Identify Error**: Red error logs indicate failures
4. **Expand Traceback**: Click to see full stack trace
5. **Locate Issue**: File:line information shows exact location
6. **Fix Code**: Use traceback to identify root cause

## Technical Implementation

### Backend Stack Trace Capture:
```python
def add_error_log(self, message, exception=None):
    if exception:
        tb = traceback.format_exc()
        frame = inspect.currentframe().f_back
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = frame.f_lineno
        function_name = frame.f_code.co_name
```

### Frontend Traceback Display:
```javascript
if (logData.traceback) {
    const tracebackId = `traceback-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    logHTML += `
        <div class="expand-traceback" onclick="toggleTraceback('${tracebackId}')">
            🔍 Show/Hide Stack Trace
        </div>
        <div class="log-traceback" id="${tracebackId}" style="display: none;">
            ${logData.traceback}
        </div>
    `;
}
```

## Benefits

1. **Precise Error Location**: Know exactly which file and line caused the issue
2. **Full Context**: Complete stack trace shows the call chain
3. **Real-time Debugging**: See errors as they happen
4. **Visual Clarity**: Color-coded and organized display
5. **Interactive**: Expand/collapse tracebacks as needed

## Usage

1. Start the Flask app: `python PEERS_RAG_flask_app.py`
2. Open browser to `http://localhost:5000`
3. Submit queries and watch the detailed logs
4. Click "Show/Hide Stack Trace" on error logs
5. Use file:line information to locate issues in code

This implementation provides comprehensive debugging information to quickly identify and fix issues in the RAG system.

