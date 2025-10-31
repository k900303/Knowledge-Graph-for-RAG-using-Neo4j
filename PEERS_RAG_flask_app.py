"""
PEERS RAG Flask Web Application
Simple web interface to query company data using GraphRAG and VectorRAG
"""

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from PEERS_RAG_graphRAG import PEERSGraphRAG
from PEERS_RAG_vectorRAG import PEERSVectorRAG
import warnings
import time
import json
import threading
import traceback
import inspect
import sys
warnings.filterwarnings("ignore")

app = Flask(__name__)

# Initialize RAG systems (lazy loading)
graph_rag = None
vector_rag = None

# Log manager for streaming logs
class LogManager:
    def __init__(self):
        self.logs = []
        self.listeners = []
        self.lock = threading.Lock()
    
    def add_log(self, log_type, message, file_info=None, traceback_info=None):
        """Add a log entry with optional file and traceback information"""
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            log_entry = {
                'timestamp': timestamp,
                'type': log_type,
                'message': message
            }
            
            # Add file information if provided
            if file_info:
                log_entry['file_info'] = file_info
            
            # Add traceback information if provided
            if traceback_info:
                log_entry['traceback'] = traceback_info
            
            self.logs.append(log_entry)
            # Send to all listeners
            for listener in self.listeners:
                listener(log_entry)
    
    def add_error_log(self, message, exception=None):
        """Add an error log with detailed traceback information"""
        file_info = None
        traceback_info = None
        
        if exception:
            # Get the current frame and traceback
            tb = traceback.format_exc()
            traceback_info = tb
            
            # Get caller information
            frame = inspect.currentframe().f_back
            if frame:
                filename = frame.f_code.co_filename
                lineno = frame.f_lineno
                function_name = frame.f_code.co_name
                
                # Extract just the filename without full path
                import os
                filename = os.path.basename(filename)
                
                file_info = {
                    'file': filename,
                    'line': lineno,
                    'function': function_name
                }
        
        self.add_log('error', message, file_info, traceback_info)
    
    def add_info_log(self, message, file_info=None):
        """Add an info log with optional file information"""
        if not file_info:
            # Get caller information for info logs too
            frame = inspect.currentframe().f_back
            if frame:
                filename = frame.f_code.co_filename
                lineno = frame.f_lineno
                function_name = frame.f_code.co_name
                
                import os
                filename = os.path.basename(filename)
                
                file_info = {
                    'file': filename,
                    'line': lineno,
                    'function': function_name
                }
        
        self.add_log('info', message, file_info)
    
    def add_tool_call_log(self, tool_name, arguments, response, duration_ms=None):
        """Add a tool calling log with tool name, arguments, and response"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'type': 'tool_call',
            'tool_name': tool_name,
            'arguments': arguments,
            'response': response,
            'duration_ms': duration_ms
        }
        self.logs.append(log_entry)
        # Send to all listeners
        for listener in self.listeners:
            listener(log_entry)
    
    def subscribe(self, callback):
        """Subscribe to log updates"""
        self.listeners.append(callback)
    
    def unsubscribe(self, callback):
        """Unsubscribe from log updates"""
        if callback in self.listeners:
            self.listeners.remove(callback)

log_manager = LogManager()


def init_rag(use_tool_calling=True):
    """Initialize RAG systems (tool calling is now default)"""
    global graph_rag, vector_rag
    if graph_rag is None:
        log_manager.add_info_log('Creating GraphRAG instance with Tool Calling (default)...')
        graph_rag = PEERSGraphRAG(log_manager, use_tool_calling=use_tool_calling)
    if vector_rag is None:
        log_manager.add_info_log('Creating VectorRAG instance...')
        vector_rag = PEERSVectorRAG(log_manager)


@app.route('/')
def index():
    """Home page"""
    return render_template('peers_rag_index.html')


@app.route('/api/logs/stream')
def stream_logs():
    """Server-Sent Events endpoint for streaming logs"""
    def generate():
        import queue
        import uuid
        
        client_queue = queue.Queue()
        client_id = str(uuid.uuid4())
        
        def listener(log_entry):
            client_queue.put(log_entry)
        
        log_manager.subscribe(listener)
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connection', 'message': 'Connected to log stream'})}\n\n"
            
            while True:
                try:
                    log_entry = client_queue.get(timeout=1)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except queue.Empty:
                    # Send heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
        finally:
            log_manager.unsubscribe(listener)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/api/init', methods=['POST'])
def api_init():
    """Initialize RAG systems (tool calling is now default)"""
    try:
        log_manager.add_info_log('Starting RAG systems initialization (Tool Calling: enabled by default)...')
        init_rag(use_tool_calling=True)
        
        log_manager.add_log('success', 'RAG systems initialized successfully (Tool Calling: enabled)')
        return jsonify({
            'status': 'success', 
            'message': 'RAG systems initialized successfully (Tool Calling: enabled by default)',
            'tool_calling_enabled': True
        })
    except Exception as e:
        log_manager.add_error_log(f'RAG initialization failed: {str(e)}', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def api_query():
    """Handle query requests with detailed logging"""
    try:
        data = request.json
        query = data.get('query', '')
        mode = data.get('mode', 'GraphRAG')
        
        log_manager.add_info_log(f'Received query: "{query}" in {mode} mode (Tool Calling: enabled by default)')
        
        if not query:
            log_manager.add_error_log('Query is empty')
            return jsonify({'status': 'error', 'message': 'Query is required'}), 400
        
        # Ensure RAG systems are initialized (tool calling is default)
        log_manager.add_info_log('Initializing RAG systems (Tool Calling: enabled by default)...')
        init_rag(use_tool_calling=True)
        
        log_manager.add_log('success', 'RAG systems ready (Tool Calling: enabled)')
        
        # Execute query
        log_manager.add_info_log(f'Executing {mode} query...')
        start_time = time.time()
        
        if mode == 'GraphRAG':
            log_manager.add_info_log('Generating Cypher query from natural language...')
            try:
                result = graph_rag.generate_cypher_query(query)
                
                # Check if GraphRAG returned "I don't know" or similar natural language
                result_str = str(result).strip().lower()
                if any(phrase in result_str for phrase in ["i don't know", "i cannot", "i'm sorry", "i do not understand", "no results found", "empty result"]):
                    log_manager.add_info_log('GraphRAG returned uncertain response, falling back to VectorRAG...')
                    try:
                        fallback_result = vector_rag.query(query)
                        result = f"[GraphRAG: {result}] [Fallback to VectorRAG: {fallback_result}]"
                        log_manager.add_info_log('VectorRAG fallback completed successfully')
                    except Exception as fallback_error:
                        log_manager.add_error_log(f'VectorRAG fallback also failed: {str(fallback_error)}', fallback_error)
                        result = f"[GraphRAG: {result}] [Fallback failed: {str(fallback_error)}]"
                else:
                    log_manager.add_info_log(f'Cypher query generated successfully')
                    
            except Exception as e:
                log_manager.add_error_log(f'GraphRAG failed, attempting VectorRAG fallback: {str(e)}', e)
                try:
                    log_manager.add_info_log('Attempting VectorRAG fallback...')
                    result = vector_rag.query(query)
                    result = f"[GraphRAG Error: {str(e)}] [VectorRAG Fallback: {result}]"
                    log_manager.add_info_log('VectorRAG fallback completed successfully')
                except Exception as fallback_error:
                    log_manager.add_error_log(f'VectorRAG fallback also failed: {str(fallback_error)}', fallback_error)
                    raise Exception(f"Both GraphRAG and VectorRAG failed. GraphRAG error: {str(e)}, VectorRAG error: {str(fallback_error)}")
        else:
            log_manager.add_info_log('Performing semantic search in vector store...')
            try:
                result = vector_rag.query(query)
                log_manager.add_info_log(f'Semantic search completed successfully')
            except Exception as e:
                log_manager.add_error_log(f'Failed to perform semantic search: {str(e)}', e)
                raise
        
        elapsed = time.time() - start_time
        log_manager.add_log('success', f'Query completed in {elapsed:.2f}s')
        log_manager.add_info_log(f'Retrieved {len(result)} characters of results')
        
        return jsonify({
            'status': 'success',
            'query': query,
            'mode': mode,
            'result': result
        })
    
    except Exception as e:
        log_manager.add_error_log(f'Query failed: {str(e)}', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/test-connections', methods=['POST'])
def test_connections():
    """Test all system connections"""
    try:
        log_manager.add_info_log('Starting connection tests...')
        
        # Test Neo4j connection
        try:
            log_manager.add_info_log('Testing Neo4j connection...')
            from neo4j_env import graph
            test_result = graph.query("RETURN 1 as test")
            log_manager.add_info_log('Neo4j connection successful')
        except Exception as e:
            log_manager.add_error_log(f'Neo4j connection failed: {str(e)}', e)
            return jsonify({'status': 'error', 'message': f'Neo4j connection failed: {str(e)}'}), 500
        
        # Test OpenAI connection
        try:
            log_manager.add_info_log('Testing OpenAI connection...')
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(temperature=0)
            test_response = llm.invoke("Hello")
            log_manager.add_info_log('OpenAI connection successful')
        except Exception as e:
            log_manager.add_error_log(f'OpenAI connection failed: {str(e)}', e)
            return jsonify({'status': 'error', 'message': f'OpenAI connection failed: {str(e)}'}), 500
        
        # Test GraphRAG initialization (both modes)
        try:
            log_manager.add_info_log('Testing GraphRAG initialization (classic mode)...')
            graph_rag_test = PEERSGraphRAG(log_manager, use_tool_calling=False)
            log_manager.add_info_log('GraphRAG classic mode initialization successful')
            
            log_manager.add_info_log('Testing GraphRAG initialization (tool calling mode)...')
            graph_rag_test_tools = PEERSGraphRAG(log_manager, use_tool_calling=True)
            log_manager.add_info_log('GraphRAG tool calling mode initialization successful')
        except Exception as e:
            log_manager.add_error_log(f'GraphRAG initialization failed: {str(e)}', e)
            return jsonify({'status': 'error', 'message': f'GraphRAG initialization failed: {str(e)}'}), 500
        
        log_manager.add_log('success', 'All connection tests passed')
        return jsonify({'status': 'success', 'message': 'All connections working'})
        
    except Exception as e:
        log_manager.add_error_log(f'Connection test failed: {str(e)}', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Get statistics"""
    return jsonify({
        'companies': 7591,
        'countries': 62,
        'sectors': 11,
        'industries': 174,
        'exchanges': 72
    })

@app.route('/api/cypher-history', methods=['GET'])
def api_cypher_history():
    """Get Cypher query history"""
    try:
        if graph_rag is None:
            return jsonify({'status': 'error', 'message': 'GraphRAG not initialized'}), 400
        
        history = graph_rag.get_cypher_history()
        return jsonify({
            'status': 'success',
            'history': history
        })
    except Exception as e:
        log_manager.add_error_log(f'Failed to get Cypher history: {str(e)}', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/clear-cypher-history', methods=['POST'])
def api_clear_cypher_history():
    """Clear Cypher query history"""
    try:
        if graph_rag is None:
            return jsonify({'status': 'error', 'message': 'GraphRAG not initialized'}), 400
        
        graph_rag.clear_cypher_history()
        log_manager.add_info_log('Cypher history cleared')
        return jsonify({'status': 'success', 'message': 'Cypher history cleared'})
    except Exception as e:
        log_manager.add_error_log(f'Failed to clear Cypher history: {str(e)}', e)
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    print("Starting PEERS RAG Flask Application...")
    print("Access at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

