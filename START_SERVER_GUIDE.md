# 🚀 How to Start the Server and Test Tool Calling

## Prerequisites Check

### 1. Verify Dependencies

```bash
# Install/update dependencies
pip install -r requirements_web.txt
```

Required packages:
- Flask
- langchain-openai
- langchain-community
- neo4j
- openai

### 2. Check Environment Variables

Ensure your `.env` file exists and contains:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key
```

### 3. Verify Neo4j is Running

```bash
# On Windows (PowerShell)
neo4j status

# Or check if Neo4j browser is accessible
# Open: http://localhost:7474
```

---

## Starting the Server

### Method 1: Using the Helper Script (Recommended)

```bash
python run_web_app.py
```

### Method 2: Direct Python Execution

```bash
python PEERS_RAG_flask_app.py
```

### Method 3: Flask CLI

```bash
flask --app PEERS_RAG_flask_app run --host=0.0.0.0 --port=5000
```

---

## Expected Output

When the server starts successfully, you should see:

```
============================================================
  PEERS RAG Flask Web Application
============================================================

Starting server...
Access at: http://localhost:5000

Press CTRL+C to stop the server
============================================================

 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

---

## Accessing the Web Application

Open your browser and navigate to:

```
http://localhost:5000
```

You should see:
- **Header**: "📊 PEERS RAG System"
- **Sidebar**: Stats, buttons, mode selection, and **Advanced Options** (Tool Calling checkbox)
- **Main Area**: Query input and results section

---

## Testing the Server

### Step 1: Test Connections

1. Click **"🔍 Test Connections"** button in the sidebar
2. Wait for success message: "✅ All connections working!"

This tests:
- ✅ Neo4j connection
- ✅ OpenAI API connection
- ✅ GraphRAG initialization (both classic and tool calling modes)

### Step 2: Initialize RAG Systems

1. **Option A: Classic Mode (Default)**
   - Leave "Enable Tool Calling" **unchecked**
   - Click **"⚙️ Initialize RAG Systems"**
   - Expected: "✅ RAG systems initialized successfully"

2. **Option B: Tool Calling Mode**
   - **Check** "Enable Tool Calling" checkbox
   - Click **"⚙️ Initialize RAG Systems"**
   - Expected: "✅ RAG systems initialized successfully (Tool Calling: Enabled)"

### Step 3: Test a Query

#### Test Classic Mode (Tool Calling OFF):

1. Uncheck "Enable Tool Calling"
2. Select **GraphRAG** mode
3. Enter query: `"Show me revenue for Kajaria"`
4. Click **"🚀 Submit Query"**
5. Check the **Live System Logs** section:
   - Should see: "Using monolithic prompt approach (backward compatibility)"

#### Test Tool Calling Mode (Tool Calling ON):

1. **Check** "Enable Tool Calling"
2. Select **GraphRAG** mode
3. Enter query: `"Show me revenue and margin for Kajaria"`
4. Click **"🚀 Submit Query"**
5. Check the **Live System Logs** section:
   - Should see: "Initializing Tool Calling infrastructure..."
   - Should see: "Using Tool Calling approach"
   - Should see: "LLM requested X tool calls"
   - Should see: "Executing tool: search_company with args: ..."
   - Should see: "Executing tool: search_parameters with args: ..."
   - Should see: "Tool Calling generated valid Cypher query"

---

## Verifying Tool Calling is Working

### In Live Logs, Look For:

✅ **Tool Calling Enabled:**
```
[INFO] Initializing Tool Calling infrastructure...
[INFO] Tool Calling initialized with 5 tools
[INFO] Using Tool Calling approach
[INFO] LLM requested 2 tool calls
[INFO] Executing tool: search_company with args: {'company_name': 'Kajaria'}
[INFO] Executing tool: search_parameters with args: {'search_term': 'revenue'}
[INFO] Tool Calling generated valid Cypher query
```

❌ **Classic Mode (Tool Calling Disabled):**
```
[INFO] Using monolithic prompt approach (backward compatibility)
[INFO] Detected parameter query - will use parameter-specific query pattern
```

### Example Test Queries

#### Simple Query (Tool Calling Recommended):
```
"Show me revenue for Kajaria Ceramics"
```

#### Multi-Parameter Query (Tool Calling Recommended):
```
"Show me revenue and EBITDA margin for Apollo Tyres"
```

#### Company Details Query:
```
"Show details of Apollo Hospital"
```

#### Filter Query:
```
"Which companies are in the Technology sector?"
```

---

## Troubleshooting

### Server Won't Start

**Error: "Address already in use"**
```bash
# Find and kill process on port 5000
# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Or change port in PEERS_RAG_flask_app.py:
app.run(debug=True, host='0.0.0.0', port=5001)
```

**Error: "Module not found"**
```bash
pip install -r requirements_web.txt
```

### Neo4j Connection Failed

1. Check Neo4j is running: `neo4j status`
2. Verify `.env` file has correct credentials
3. Test connection in Neo4j Browser: `http://localhost:7474`

### OpenAI Connection Failed

1. Verify `OPENAI_API_KEY` in `.env` file
2. Check API key is valid and has credits
3. Test with: `python -c "from langchain_openai import ChatOpenAI; ChatOpenAI().invoke('test')"`

### Tool Calling Not Working

**Check logs for:**
- "Tool Calling initialized with X tools" (should be 5)
- "LLM requested X tool calls" (should be > 0)
- "Executing tool: ..." messages

**If tools aren't being called:**
1. Ensure "Enable Tool Calling" checkbox is checked
2. Re-initialize RAG systems with tool calling enabled
3. Check OpenAI model supports tool calling (gpt-4o, gpt-4, or gpt-3.5-turbo)

### No Results Returned

1. Verify data exists in Neo4j:
   ```cypher
   MATCH (c:Company) RETURN count(c) LIMIT 1
   ```
2. Check query spelling and syntax
3. Try example queries from sidebar

---

## Quick Verification Checklist

- [ ] Server starts without errors
- [ ] Browser loads `http://localhost:5000`
- [ ] "Test Connections" button works
- [ ] RAG systems initialize successfully
- [ ] Classic mode queries work
- [ ] Tool Calling checkbox appears and works
- [ ] Tool Calling mode shows tool execution in logs
- [ ] Queries return results (either mode)

---

## Monitoring

### Live System Logs

The web app shows live logs in real-time:
- Scroll down to see "Live System Logs" section
- Watch tool execution in real-time
- Check for errors or warnings

### Cypher History

Click **"📋 View Cypher History"** to see:
- All generated Cypher queries
- Questions that triggered them
- Raw query results

---

## Next Steps

1. ✅ Test both modes (Classic vs Tool Calling)
2. ✅ Compare query performance and accuracy
3. ✅ Review generated Cypher queries in history
4. ✅ Try different query types (parameter, company details, filters)

---

## Stopping the Server

Press `CTRL+C` in the terminal where the server is running.

---

**Happy Querying! 🚀**


