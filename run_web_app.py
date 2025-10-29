"""
Simple script to run the PEERS RAG Flask Web Application
"""

if __name__ == '__main__':
    from PEERS_RAG_flask_app import app
    
    print("\n" + "="*60)
    print("  PEERS RAG Flask Web Application")
    print("="*60)
    print("\nStarting server...")
    print("Access at: http://localhost:5000")
    print("\nPress CTRL+C to stop the server")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

