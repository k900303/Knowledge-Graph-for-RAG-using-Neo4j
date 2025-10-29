"""
VectorRAG Module for PEERS RAG System
Performs semantic search on company text chunks
"""

from langchain_classic import hub
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import ChatOpenAI
from neo4j_env import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    PEERS_VECTOR_INDEX_NAME, PEERS_VECTOR_NODE_LABEL,
    PEERS_VECTOR_SOURCE_PROPERTY, PEERS_VECTOR_EMBEDDING_PROPERTY
)
import textwrap
import traceback
import inspect


class PEERSVectorRAG:
    """VectorRAG class for company semantic search"""
    
    def __init__(self, log_manager=None):
        self.log_manager = log_manager
        
        try:
            if self.log_manager:
                self.log_manager.add_info_log('Initializing Neo4jVector store...')
            
            self.vector_store = Neo4jVector.from_existing_graph(
                embedding=OpenAIEmbeddings(),
                url=NEO4J_URI,
                username=NEO4J_USERNAME,
                password=NEO4J_PASSWORD,
                index_name=PEERS_VECTOR_INDEX_NAME,
                node_label=PEERS_VECTOR_NODE_LABEL,
                text_node_properties=[PEERS_VECTOR_SOURCE_PROPERTY],
                embedding_node_property=PEERS_VECTOR_EMBEDDING_PROPERTY,
            )
            
            if self.log_manager:
                self.log_manager.add_info_log('Neo4jVector store initialized successfully')
            
            if self.log_manager:
                self.log_manager.add_info_log('Loading retrieval QA chat prompt...')
            
            self.retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")
            
            if self.log_manager:
                self.log_manager.add_info_log('Creating document combination chain...')
            
            self.combine_docs_chain = create_stuff_documents_chain(
                ChatOpenAI(temperature=0), 
                self.retrieval_qa_chat_prompt
            )
            
            if self.log_manager:
                self.log_manager.add_info_log('Creating retrieval chain...')
            
            self.retrieval_chain = create_retrieval_chain(
                retriever=self.vector_store.as_retriever(),
                combine_docs_chain=self.combine_docs_chain
            )
            
            if self.log_manager:
                self.log_manager.add_info_log('VectorRAG initialization completed successfully')
                
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'VectorRAG initialization failed: {str(e)}', e)
            raise
    
    def query(self, question: str) -> str:
        """
        Query the vector store with a question
        
        Args:
            question: Natural language question
        
        Returns:
            Formatted answer
        """
        try:
            if self.log_manager:
                self.log_manager.add_info_log(f'Starting vector search for: "{question}"')
            
            # Perform similarity search
            if self.log_manager:
                self.log_manager.add_info_log('Performing similarity search in vector store...')
            
            result = self.retrieval_chain.invoke(input={"input": question})
            
            if self.log_manager:
                answer_length = len(result.get('answer', ''))
                self.log_manager.add_info_log(f'Vector search completed, answer length: {answer_length}')
                
                # Log retrieved documents info
                if 'context' in result:
                    context_length = len(result['context'])
                    self.log_manager.add_info_log(f'Retrieved {context_length} document chunks')
            
            return textwrap.fill(result['answer'], 60)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.add_error_log(f'Vector search failed: {str(e)}', e)
            raise


# Update for backward compatibility
VectorRAG = PEERSVectorRAG

