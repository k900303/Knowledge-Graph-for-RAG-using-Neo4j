"""
Embedding Generator for PEERS RAG System
Generates OpenAI embeddings for company chunks and stores in Neo4j
"""

from neo4j import GraphDatabase
from neo4j_env import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, PEERS_VECTOR_EMBEDDING_PROPERTY
from langchain_openai import OpenAIEmbeddings
from typing import List
import warnings

warnings.filterwarnings("ignore")


class PEERSEmbeddingGenerator:
    """Generate and store embeddings for company chunks"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        self.embeddings = OpenAIEmbeddings()
    
    def generate_embeddings_for_all_chunks(self, batch_size: int = 50):
        """
        Generate embeddings for all company chunks
        
        Args:
            batch_size: Number of chunks to process per batch
        """
        print("\n" + "="*80)
        print("Generating Vector Embeddings for Company Chunks")
        print("="*80)
        
        with self.driver.session() as session:
            # Get all chunks without embeddings
            result = session.run("""
                MATCH (chunk:Company_Chunk)
                WHERE chunk.textEmbeddingOpenAI IS NULL OR chunk.textEmbeddingOpenAI = []
                RETURN chunk.chunkId as chunkId, chunk.text as text
                LIMIT 10000
            """)
            
            chunks = [(record["chunkId"], record["text"]) for record in result]
            total_chunks = len(chunks)
            
            print(f"Found {total_chunks} chunks to embed")
            
            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i+batch_size]
                self._process_batch(session, batch)
                
                processed = min(i+batch_size, total_chunks)
                print(f"  Progress: {processed}/{total_chunks} chunks processed")
            
            print(f"\n[OK] Completed generating embeddings for {total_chunks} chunks")
            print("="*80)
    
    def _process_batch(self, session, batch: List[tuple]):
        """Process a batch of chunks"""
        for chunk_id, text in batch:
            try:
                # Generate embedding
                embedding = self.embeddings.embed_query(text)
                
                # Store in Neo4j
                session.run("""
                    MATCH (chunk:Company_Chunk {chunkId: $chunkId})
                    SET chunk.textEmbeddingOpenAI = $embedding
                """, chunkId=chunk_id, embedding=embedding)
                
            except Exception as e:
                print(f"  Error processing chunk {chunk_id}: {e}")
                continue
    
    def close(self):
        """Close the driver connection"""
        self.driver.close()


def main():
    """Example usage"""
    generator = PEERSEmbeddingGenerator()
    
    try:
        generator.generate_embeddings_for_all_chunks(batch_size=50)
    finally:
        generator.close()


if __name__ == '__main__':
    main()

