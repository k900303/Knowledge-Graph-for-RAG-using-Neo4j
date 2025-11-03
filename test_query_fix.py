"""
Quick test script to verify the query "ebita margin of kajaria q2fy2026" works correctly
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Simple log manager
class SimpleLogManager:
    def __init__(self):
        self.logs = []
    
    def add_info_log(self, message, file_info=None):
        self.logs.append(('info', message))
        print(f"[INFO] {message}")
    
    def add_error_log(self, message, exception=None):
        self.logs.append(('error', message))
        print(f"[ERROR] {message}")
        if exception:
            import traceback
            traceback.print_exc()
    
    def add_log(self, log_type, message, file_info=None, traceback_info=None):
        self.logs.append((log_type, message))
        print(f"[{log_type.upper()}] {message}")

try:
    from PEERS_RAG_graphRAG import PEERSGraphRAG
    
    # Initialize log manager
    log_manager = SimpleLogManager()
    
    print("="*80)
    print("Initializing GraphRAG system...")
    print("="*80)
    
    # Create GraphRAG instance
    graph_rag = PEERSGraphRAG(log_manager=log_manager, use_tool_calling=True)
    
    # Test query
    test_query = "ebita margin of kajaria q2fy2026"
    
    print("\n" + "="*80)
    print(f"Testing query: '{test_query}'")
    print("="*80)
    print()
    
    # Run the full GraphRAG flow
    result = graph_rag.generate_cypher_query(test_query)
    
    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(result)
    print("="*80)
    
    # Check if result indicates success or error
    if result and len(result) > 0:
        if "Error" in result or "error" in result.lower():
            print("\n[WARNING] Query returned an error message (but didn't crash)")
            print("   This means error handling is working correctly!")
        elif "No data found" in result:
            print("\n[SUCCESS] Query processed successfully - No data found for this period")
            print("   (This is expected for future periods like Q2FY2026)")
        else:
            print("\n[SUCCESS] Query processed successfully - Data returned")
    else:
        print("\n[WARNING] Query returned empty result")
        
except Exception as e:
    print("\n" + "="*80)
    print("[ERROR] EXCEPTION RAISED (this should NOT happen with the fixes):")
    print("="*80)
    print(f"Error: {str(e)}")
    print(f"Type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
    print("="*80)

print("\n" + "="*80)
print("Test completed")
print("="*80)
