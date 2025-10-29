# 🚀 PEERS RAG Simple Web Application - Quick Guide

## Installation

Install Flask if you haven't already:
```bash
pip install flask
```

## Running the App

### Option 1: Using the Helper Script
```bash
python run_web_app.py
```

### Option 2: Direct Flask Command
```bash
python PEERS_RAG_flask_app.py
```

### Option 3: Flask Command Line
```bash
flask --app PEERS_RAG_flask_app run
```

## Access the Application

Once running, open your browser and go to:

```
http://localhost:5000
```

## 🎯 How to Use

### Step 1: Initialize RAG Systems
Click the **"⚙️ Initialize RAG Systems"** button in the sidebar

### Step 2: Select Mode
Choose either:
- **GraphRAG**: For structured queries
- **VectorRAG**: For semantic search

### Step 3: Enter Query
Type your question in the input box

### Step 4: Submit
Click **"🚀 Submit Query"** or press Enter

### Step 5: View Results
Results appear below in the results box

## 💡 Example Queries

Try these example queries by clicking the buttons in the sidebar:

### GraphRAG Examples
- "Which companies are in the Technology sector?"
- "Show me companies listed on NASDAQ"
- "Find pharmaceutical companies"
- "List companies with positive change"
- "Which US companies are in Healthcare?"

### VectorRAG Examples  
- "Find large healthcare companies"
- "Tell me about top technology companies"
- "Show me sustainable energy companies"

## 🎨 Features

✅ **Simple & Clean UI** - No complex frameworks  
✅ **Interactive Querying** - Real-time results  
✅ **Dual RAG Modes** - GraphRAG & VectorRAG  
✅ **Example Queries** - Click to use  
✅ **Query History** - Review past searches  
✅ **Quick Stats** - See data overview  

## 🔧 Troubleshooting

### "Please initialize RAG systems first"
- Click the "⚙️ Initialize RAG Systems" button
- Wait for success message

### "Neo4j connection failed"
- Make sure Neo4j is running
- Check your `.env` file
- Ensure pipeline completed

### No results returned
- Check if data exists in Neo4j
- Try different query phrasing
- Ensure pipeline completed

### Port 5000 already in use
Edit `PEERS_RAG_flask_app.py` and change:
```python
app.run(debug=True, host='0.0.0.0', port=5001)  # Use different port
```

## 📊 What's Running

```
Flask Server: http://localhost:5000
Neo4j Browser: http://localhost:7474
```

## 🛑 Stopping the Server

Press `CTRL+C` in the terminal

## 📝 Next Steps

1. Explore different queries
2. Compare GraphRAG vs VectorRAG
3. Check query history
4. Customize the HTML template if needed

---

**Simple, Fast, Effective!** 🚀

