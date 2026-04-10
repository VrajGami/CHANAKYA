"""
FILE: src/rag_memory.py
DESCRIPTION: RAG Core leveraging ChromaDB for storing and retrieving trading memories.
"""
import chromadb
import uuid
from typing import List, Dict, Any

class RAGMemory:
    def __init__(self, persist_dir: str = "data/chroma"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="trading_memories",
            metadata={"hnsw:space": "cosine"}
        )

    def store_trade_memory(self, ticker: str, action: str, pnl: float, rationale: str, market_regime: str):
        """
        Stores the outcome and contextual rationale of a trade into the vector DB.
        """
        document = f"Trade: {action} {ticker}. Regime: {market_regime}. Rationale: {rationale}."
        metadata = {
            "ticker": ticker,
            "action": action,
            "pnl": pnl,
            "market_regime": market_regime,
            "success": pnl > 0
        }
        
        self.collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def retrieve_similar_scenarios(self, current_regime: str, current_metrics: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves historical trades with similar setups to inform the current Trader.
        """
        if self.collection.count() == 0:
            return []

        query_text = f"Regime: {current_regime}. Context: {current_metrics}"
        
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        if not results['documents'] or not results['documents'][0]:
            return []
            
        memories = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            memories.append({
                "document": doc,
                "pnl": meta.get("pnl", 0.0),
                "success": meta.get("success", False)
            })
            
        return memories

    def get_memory_count(self) -> int:
        """Returns the total number of ingested memories in the vector database."""
        return self.collection.count()
