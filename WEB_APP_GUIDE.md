# 🚀 PEERS RAG Web Application - Quick Guide

## Accessing the App

The web application is now running at:

```
http://localhost:8501
```

If it doesn't open automatically, copy the URL above into your browser.

## 🎯 How to Use

### Step 1: Initialize RAG Systems
- Click the **"Initialize RAG Systems"** button in the sidebar
- Wait for the success message

### Step 2: Select RAG Mode
Choose either:
- **GraphRAG**: For structured queries (Cypher-based)
- **VectorRAG**: For semantic search

### Step 3: Enter Your Query
Type your question in the input box, such as:
- "Which technology companies are in the US?"
- "Find large healthcare companies"
- "Show me NASDAQ listed companies"

### Step 4: Submit
Click the **"Submit Query"** button

### Step 5: View Results
Results will appear in the results box below

## 💡 Example Queries

### GraphRAG (Structured Queries)
Try these specific queries:

```
Which companies are in the Technology sector?
Show me companies listed on NASDAQ
Find pharmaceutical companies in Asia
List companies with positive one week change
Which US companies are in Healthcare?
Show me all companies in North America with market cap over 10 billion
```

### VectorRAG (Semantic Search)
Try these exploratory queries:

```
Tell me about large Fortune 500 companies
Find technology companies
Show me healthcare companies
What are top performing financial companies?
Find companies in emerging markets
Tell me about sustainable energy companies
```

## 📊 Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    PEERS RAG System                            │
│                  Query Company Data                             │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│  ⚙️ CONFIG   │            🔍 ENTER YOUR QUERY                   │
│  [●]Graph    │                                                  │
│  [○]Vector   │  Question: [___________________________]         │
│              │                                                   │
│  [Initialize]│  [🚀 Submit Query]                               │
│              │                                                  │
│  💡 EXAMPLES │                                                  │
│  [Example 1 ] │  📊 QUICK STATS                                 │
│  [Example 2 ] │  Companies: ~7,591                               │
│  [Example 3 ] │  Countries: 62                                   │
│  [Example 4 ] │  Sectors: 11                                     │
│  [Example 5 ] │  Industries: 174                                │
│  [Example 6 ] │  Exchanges: 72                                  │
│              │                                                  │
│              │  📋 RESULTS                                      │
│              │  [Your query results appear here]              │
│              │                                                  │
│              │  📜 QUERY HISTORY                                │
│              │  [Recent queries list]                           │
└──────────────┴──────────────────────────────────────────────────┘
```

## 🎨 Features

### ✅ Interactive Querying
- Real-time query processing
- Dual RAG modes (Graph/Vector)
- Instant results

### ✅ Example Queries
- One-click example queries in sidebar
- Pre-configured for common searches
- Easy to modify and use

### ✅ Query History
- View past queries
- Expand to see details
- Clear history option

### ✅ Visual Stats
- Quick stats dashboard
- Real-time data overview
- Network statistics

## 🔧 Troubleshooting

### "Please initialize RAG systems first"
- Click the "Initialize RAG Systems" button in the sidebar
- Wait for success message

### "Error connecting to Neo4j"
- Ensure Neo4j is running: `neo4j status`
- Check `.env` file has correct credentials
- Verify pipeline completed: `python PEERS_RAG_pipeline.py`

### No results returned
- The pipeline might still be running
- Check if data exists in Neo4j
- Try different query phrasing

### Port 8501 already in use
```bash
streamlit run PEERS_RAG_web_app.py --server.port 8502
```

## 📝 Tips for Best Results

1. **Be Specific**: GraphRAG works best with specific queries
   - ✅ "Which technology companies are in the US?"
   - ❌ "Tell me about companies"

2. **Use Keywords**: For VectorRAG, use descriptive keywords
   - ✅ "Find large healthcare companies with strong growth"
   - ❌ "Give me company names"

3. **Try Different Modes**: 
   - Use **GraphRAG** for exact matches and filters
   - Use **VectorRAG** for similarity and exploration

4. **Review Examples**: Click sidebar examples to see what works

## 🚀 Advanced Usage

### Custom Queries
You can create complex queries like:
```
Show me all companies in the Technology sector listed on NASDAQ with 
market cap over 5 billion USD
```

### Combined Searches
Try mixing structured and semantic approaches:
1. Use GraphRAG to find a subset
2. Use VectorRAG to find similar companies

## 📊 What Data Can You Query?

The system contains:
- **7,591 companies** with detailed information
- **Market capitalization** data
- **Performance metrics** (weekly, monthly, quarterly changes)
- **Geographic data** (countries, regions)
- **Industry classification** (sectors, industries)
- **Stock exchange information**
- **Financial data**

## 🎯 Next Steps

1. **Explore** different query types
2. **Compare** GraphRAG vs VectorRAG results
3. **Experiment** with complex queries
4. **Customize** the interface for your needs

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify Neo4j connection
3. Review the pipeline logs
4. Check the documentation files

---

**Happy Querying! 🎉**

