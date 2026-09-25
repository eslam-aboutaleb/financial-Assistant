"""
Embedding function factory for the OmniCare RAG subsystem.

This module provides a single factory method for creating ChromaDB-compatible
embedding functions. Currently it defaults to OpenAI's embedding API, but the
factory pattern makes it trivial to swap providers (e.g. Vertex AI, HuggingFace)
without touching the retriever or ingestion code.

Why a factory instead of direct instantiation?
  - Centralizes the embedding configuration (API key, model name) in one place.
  - Allows runtime selection of the embedding provider via settings.
  - Keeps the Chroma client creation code clean and testable.
"""

from chromadb.utils import embedding_functions

from app.config import get_settings


class EmbeddingFactory:
    """
    Factory for creating ChromaDB embedding functions.

    The factory reads the embedding configuration from the centralized
    Pydantic settings and returns a ready-to-use embedding function
    instance. This decouples the embedding provider choice from the
    rest of the RAG pipeline.
    """

    @classmethod
    def get_embedding_function(cls):
        """Create and return a ChromaDB embedding function.

        Currently returns an ``OpenAIEmbeddingFunction`` configured with
        the API key and model name from the application settings.

        Future enhancement: route to different providers based on an
        environment variable or setting, e.g.::

            if settings.embedding_provider == "openai":
                return embedding_functions.OpenAIEmbeddingFunction(...)
            elif settings.embedding_provider == "huggingface":
                return embedding_functions.HuggingFaceEmbeddingFunction(...)

        Returns:
            A ChromaDB embedding function instance ready for use with
            ``PersistentClient.get_or_create_collection``.
        """
        settings = get_settings()
        # Currently defaults to OpenAI.
        # Future enhancement: route based on an environment variable or setting,
        # e.g., if settings.embedding_provider == "openai": ...
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model,
        )
