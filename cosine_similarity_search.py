"""
Enhanced Cosine Similarity Search for Neo4j RAG
This module provides detailed cosine similarity search with scores and multiple retrieval options.
"""

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from neo4j import GraphDatabase
from neo4j_env import *
from typing import List, Dict, Tuple
import numpy as np


class CosineSimilaritySearch:
    """
    Enhanced cosine similarity search with Neo4j vector store.
    Provides detailed similarity scores and multiple search options.
    """
    
    def __init__(self):
        """Initialize the vector store and embeddings."""
        self.embeddings = OpenAIEmbeddings()
        
        # Initialize Neo4j Vector Store
        self.vector_store = Neo4jVector.from_existing_graph(
            embedding=self.embeddings,
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            index_name=VECTOR_INDEX_NAME,
            node_label=VECTOR_NODE_LABEL,
            text_node_properties=[VECTOR_SOURCE_PROPERTY],
            embedding_node_property=VECTOR_EMBEDDING_PROPERTY,
        )
        
        # Direct Neo4j driver for custom queries
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    
    def search_with_scores(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Perform similarity search and return results with cosine similarity scores.
        
        Args:
            query: The search query text
            k: Number of top results to return
            
        Returns:
            List of tuples (document_text, similarity_score)
        """
        # Use LangChain's similarity_search_with_score method
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append((doc.page_content, score))
        
        return formatted_results
    
    def search_with_metadata(self, query: str, k: int = 5) -> List[Dict]:
        """
        Perform similarity search and return detailed results with metadata.
        
        Args:
            query: The search query text
            k: Number of top results to return
            
        Returns:
            List of dictionaries containing text, score, and metadata
        """
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        detailed_results = []
        for doc, score in results:
            result_dict = {
                'text': doc.page_content,
                'similarity_score': score,
                'metadata': doc.metadata,
                'source': doc.metadata.get('source', 'Unknown'),
                'chunk_id': doc.metadata.get('chunkId', 'Unknown')
            }
            detailed_results.append(result_dict)
        
        return detailed_results
    
    def search_by_vector(self, embedding_vector: List[float], k: int = 5) -> List[Dict]:
        """
        Search using a pre-computed embedding vector.
        
        Args:
            embedding_vector: The embedding vector to search with
            k: Number of top results to return
            
        Returns:
            List of dictionaries with search results
        """
        results = self.vector_store.similarity_search_by_vector(embedding_vector, k=k)
        
        formatted_results = []
        for doc in results:
            result_dict = {
                'text': doc.page_content,
                'metadata': doc.metadata
            }
            formatted_results.append(result_dict)
        
        return formatted_results
    
    def custom_cypher_similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Perform custom similarity search using direct Cypher query.
        This gives you full control over the vector search in Neo4j.
        
        Args:
            query: The search query text
            k: Number of top results to return
            
        Returns:
            List of dictionaries with detailed results
        """
        # Get query embedding
        query_embedding = self.embeddings.embed_query(query)
        
        # Custom Cypher query for vector similarity search
        cypher_query = f"""
        CALL db.index.vector.queryNodes(
            $index_name, 
            $k, 
            $query_embedding
        )
        YIELD node, score
        RETURN 
            node.text AS text,
            node.source AS source,
            node.chunkId AS chunkId,
            node.formItem AS formItem,
            node.chunkSeqId AS chunkSeqId,
            score
        ORDER BY score DESC
        """
        
        with self.driver.session() as session:
            result = session.run(
                cypher_query,
                index_name=VECTOR_INDEX_NAME,
                k=k,
                query_embedding=query_embedding
            )
            
            results = []
            for record in result:
                results.append({
                    'text': record['text'],
                    'source': record['source'],
                    'chunk_id': record['chunkId'],
                    'form_item': record['formItem'],
                    'chunk_seq_id': record['chunkSeqId'],
                    'similarity_score': record['score']
                })
        
        return results
    
    def compare_queries(self, queries: List[str], k: int = 3) -> Dict[str, List[Dict]]:
        """
        Compare multiple queries and their top results.
        
        Args:
            queries: List of query strings to compare
            k: Number of top results per query
            
        Returns:
            Dictionary mapping each query to its results
        """
        comparison = {}
        
        for query in queries:
            results = self.search_with_metadata(query, k=k)
            comparison[query] = results
        
        return comparison
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get the embedding vector for a given text.
        
        Args:
            text: The text to embed
            
        Returns:
            Embedding vector as a list of floats
        """
        return self.embeddings.embed_query(text)
    
    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (between -1 and 1)
        """
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()


def main():
    """Example usage of the CosineSimilaritySearch class."""
    
    # Initialize the search
    search = CosineSimilaritySearch()
    
    # Example 1: Basic similarity search with scores
    print("=" * 80)
    print("Example 1: Similarity Search with Scores")
    print("=" * 80)
    query = "What happened at the Battle of Waterloo?"
    results = search.search_with_scores(query, k=3)
    
    print(f"\nQuery: {query}\n")
    for i, (text, score) in enumerate(results, 1):
        print(f"Result {i} (Score: {score:.4f}):")
        print(f"{text[:200]}...\n")
    
    # Example 2: Search with detailed metadata
    print("=" * 80)
    print("Example 2: Search with Metadata")
    print("=" * 80)
    query = "Napoleon's career"
    results = search.search_with_metadata(query, k=3)
    
    print(f"\nQuery: {query}\n")
    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  Similarity Score: {result['similarity_score']:.4f}")
        print(f"  Source: {result['source']}")
        print(f"  Chunk ID: {result['chunk_id']}")
        print(f"  Text: {result['text'][:150]}...")
        print()
    
    # Example 3: Custom Cypher similarity search
    print("=" * 80)
    print("Example 3: Custom Cypher Similarity Search")
    print("=" * 80)
    query = "Napoleon's death"
    results = search.custom_cypher_similarity_search(query, k=3)
    
    print(f"\nQuery: {query}\n")
    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  Similarity Score: {result['similarity_score']:.4f}")
        print(f"  Form Item: {result['form_item']}")
        print(f"  Chunk Sequence: {result['chunk_seq_id']}")
        print(f"  Text: {result['text'][:150]}...")
        print()
    
    # Example 4: Compare multiple queries
    print("=" * 80)
    print("Example 4: Compare Multiple Queries")
    print("=" * 80)
    queries = [
        "Napoleon's military campaigns",
        "The French Revolution",
        "European politics in 1815"
    ]
    comparison = search.compare_queries(queries, k=2)
    
    for query, results in comparison.items():
        print(f"\nQuery: {query}")
        print(f"Top result score: {results[0]['similarity_score']:.4f}")
        print(f"Preview: {results[0]['text'][:100]}...")
        print()
    
    # Example 5: Calculate similarity between two texts
    print("=" * 80)
    print("Example 5: Calculate Cosine Similarity Between Texts")
    print("=" * 80)
    text1 = "Napoleon Bonaparte was a French military leader"
    text2 = "Napoleon was a general in the French army"
    text3 = "The Battle of Waterloo was fought in Belgium"
    
    emb1 = search.get_embedding(text1)
    emb2 = search.get_embedding(text2)
    emb3 = search.get_embedding(text3)
    
    sim_1_2 = search.calculate_cosine_similarity(emb1, emb2)
    sim_1_3 = search.calculate_cosine_similarity(emb1, emb3)
    
    print(f"\nText 1: {text1}")
    print(f"Text 2: {text2}")
    print(f"Cosine Similarity: {sim_1_2:.4f}\n")
    
    print(f"Text 1: {text1}")
    print(f"Text 3: {text3}")
    print(f"Cosine Similarity: {sim_1_3:.4f}\n")
    
    # Close the connection
    search.close()


if __name__ == "__main__":
    main()


