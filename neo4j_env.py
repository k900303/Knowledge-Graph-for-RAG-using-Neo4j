from dotenv import load_dotenv
import os
from langchain_community.graphs import Neo4jGraph
load_dotenv('.env', override=True)
# Warning control
import warnings
warnings.filterwarnings("ignore")

NEO4J_URI = os.getenv('NEO4J_URI')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
NEO4J_DATABASE = os.getenv('NEO4J_DATABASE')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_ENDPOINT = os.getenv('OPENAI_BASE_URL') + '/embeddings'



# Global constants - Original (Napoleon)
VECTOR_INDEX_NAME = 'NapoleonOpenAI'
VECTOR_NODE_LABEL = 'Napoleon_Chunk'
VECTOR_SOURCE_PROPERTY = 'text'
VECTOR_EMBEDDING_PROPERTY = 'textEmbeddingOpenAI'

# PEERS RAG constants - Company data
PEERS_VECTOR_INDEX_NAME = 'CompanyOpenAI'
PEERS_VECTOR_NODE_LABEL = 'Company_Chunk'
PEERS_VECTOR_SOURCE_PROPERTY = 'text'
PEERS_VECTOR_EMBEDDING_PROPERTY = 'textEmbeddingOpenAI'


# Lazy initialization - will connect when first accessed
# This prevents connection errors at import time if Neo4j is not running
_graph = None

def get_graph():
    """Get or create Neo4j graph connection (lazy initialization)"""
    global _graph
    if _graph is None:
        try:
            _graph = Neo4jGraph(
                url=NEO4J_URI, 
                username=NEO4J_USERNAME, 
                password=NEO4J_PASSWORD, 
                database=NEO4J_DATABASE
            )
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j at import time: {e}")
            print("Neo4j connection will be retried when first accessed.")
            # Return None, connection will be retried later
            return None
    return _graph

# For backward compatibility, create graph but handle errors gracefully
try:
    graph = Neo4jGraph(
        url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD, database=NEO4J_DATABASE
    )
except Exception as e:
    # If connection fails at import time, create a placeholder
    # The actual connection will be established when needed
    print(f"Warning: Neo4j connection failed at import time: {e}")
    print("Please ensure Neo4j is running before using the application.")
    # Create a None placeholder - actual modules should handle this gracefully
    graph = None