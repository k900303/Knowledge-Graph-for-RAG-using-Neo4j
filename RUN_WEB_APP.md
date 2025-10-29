# How to Run the PEERS RAG Web Application

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_web.txt
```

Or install Streamlit separately:
```bash
pip install streamlit
```

### 2. Ensure Pipeline is Complete

Make sure you've run the data ingestion pipeline first:
```bash
python PEERS_RAG_pipeline.py
```

### 3. Run the Web App

```bash
streamlit run PEERS_RAG_web_app.py
```

The app will automatically open in your browser at:
```
http://localhost:8501
```

## 📱 Using the Web Application

### Features

1. **Dual RAG Modes**
   - **GraphRAG**: For structured queries using Cypher
   - **VectorRAG**: For semantic search and similarity

2. **Interactive Interface**
   - Sidebar with configuration and example queries
   - Main query input area
   - Real-time results display
   - Query history

3. **Quick Stats**
   - Company counts
   - Network statistics
   - Data overview

### How to Query

1. **Select RAG Mode** from the sidebar (GraphRAG or VectorRAG)

2. **Click "Initialize RAG Systems"** (first time only)

3. **Enter your query** in the main input box

4. **Click "Submit Query"** or press Enter

5. **View results** displayed below

### Example Queries

#### GraphRAG Examples (Structured Queries)
- "Which companies are in the Technology sector?"
- "Show me companies listed on NASDAQ"
- "Find pharmaceutical companies in Asia"
- "List companies with positive one week change"
- "Which US companies are in Healthcare?"

#### VectorRAG Examples (Semantic Search)
- "Tell me about large Fortune 500 companies"
- "Find technology companies"
- "Show me healthcare companies"
- "What are top performing financial companies?"
- "Find companies in emerging markets"

## 🖼️ Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PEERS RAG System                         │
├──────────────┬──────────────────────────────────────────────┤
│              │                                               │
│   Sidebar    │         Main Content Area                     │
│              │                                               │
│ Configuration│  Query Input                                 │
│ Examples     │  Submit Button                               │
│ Stats        │  Results Display                             │
│              │  Query History                                │
│              │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

## 🔧 Troubleshooting

### Error: "Please initialize RAG systems first"
- Click the "Initialize RAG Systems" button in the sidebar
- Wait for the success message

### Error: "Neo4j connection failed"
- Make sure Neo4j is running: `neo4j status`
- Check your `.env` file has correct credentials

### No results returned
- Verify the pipeline completed successfully
- Check that company data exists in Neo4j
- Try different query phrases

### Streamlit not found
```bash
pip install streamlit
```

### Port already in use
```bash
streamlit run PEERS_RAG_web_app.py --server.port 8502
```

## 📊 Using Neo4j Browser Alongside

You can also monitor the graph in Neo4j Browser:
1. Open: http://localhost:7474
2. Run queries to explore the data
3. Keep both tabs open for comparison

## 🎨 Customization

Edit `PEERS_RAG_web_app.py` to:
- Change colors and styling
- Add more example queries
- Modify the layout
- Add more features

## 🚀 Next Steps

1. **Explore the data** using different query types
2. **Compare GraphRAG vs VectorRAG** results
3. **Build custom queries** for your use case
4. **Extend the app** with additional features

## 📝 Tips

- Use **GraphRAG** for specific, structured questions
- Use **VectorRAG** for exploratory, semantic searches
- Click example queries to auto-fill the input
- Check the query history to review past searches
- Use the sidebar stats to understand the data scale

