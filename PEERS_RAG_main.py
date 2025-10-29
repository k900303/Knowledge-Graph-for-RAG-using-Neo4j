"""
Main Entry Point for PEERS RAG System
Demonstrates both GraphRAG and VectorRAG with company data
"""

from PEERS_RAG_graphRAG import PEERSGraphRAG
from PEERS_RAG_vectorRAG import PEERSVectorRAG


def query_peers_rag(use_graph: bool, question: str) -> str:
    """
    Query the PEERS RAG system using either GraphRAG or VectorRAG
    
    Args:
        use_graph: True for GraphRAG (Cypher queries), False for VectorRAG (semantic search)
        question: Natural language question
    
    Returns:
        Formatted answer
    """
    if use_graph:
        # GraphRAG - Uses Cypher queries
        print(f"\n[GraphRAG] Question: {question}\n")
        query_generator = PEERSGraphRAG()
        answer = query_generator.generate_cypher_query(question)
        return answer
    else:
        # VectorRAG - Uses semantic search
        print(f"\n[VectorRAG] Question: {question}\n")
        retrieval_qa = PEERSVectorRAG()
        answer = retrieval_qa.query(question)
        return answer


def main():
    """Example queries for the PEERS RAG system"""
    
    print("\n" + "="*100)
    print("  PEERS RAG SYSTEM - QUERY EXAMPLES")
    print("="*100)
    
    # Example queries
    queries = [
        ("Which technology companies are in the United States?", True),  # GraphRAG
        ("Show me companies with market cap over 10 billion", True),      # GraphRAG
        ("Find pharmaceutical companies in Asia", True),                  # GraphRAG
        ("What are the top performing companies this month?", True),      # GraphRAG
        ("Tell me about NASDAQ listed healthcare companies", False),      # VectorRAG
        ("Which companies are in financial services?", False),            # VectorRAG
    ]
    
    for question, use_graph in queries:
        try:
            answer = query_peers_rag(use_graph, question)
            print(f"\nAnswer:\n{answer}\n")
            print("-"*100)
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            print("-"*100)


if __name__ == '__main__':
    main()

