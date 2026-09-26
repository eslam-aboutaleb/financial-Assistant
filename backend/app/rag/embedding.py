"""
Embedding function factory for the OmniCare RAG subsystem.

This module provides a single factory method for creating embedding functions.
Currently it defaults to LiteLLM's embedding interface, but the factory
pattern makes it trivial to swap providers (e.g. OpenAI, Vertex AI,
HuggingFace) without touching the retriever or ingestion code.

Why a factory instead of direct instantiation?
  - Centralizes the embedding configuration (API key, model name) in one place.
  - Allows runtime selection of the embedding provider via settings.
  - Keeps the client creation code clean and testable.
"""

import litellm

from app.config import get_settings


class LitellmEmbeddingFunction:
    """Callable embedding function backed by LiteLLM.

    Wraps ``litellm.embedding`` so the rest of the RAG pipeline can treat it
    as a drop-in replacement for the previous ChromaDB embedding function.
    """

    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a list of text strings.

        Args:
            input: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        response = litellm.embedding(
            model=self.model_name,
            input=input,
            api_key=self.api_key,
        )
        return [item["embedding"] for item in response.data]

    def embed_query(self, input: str | list[str]) -> list[float]:
        """Embed a single query string.

        Args:
            input: Query string or list containing one string.

        Returns:
            A single embedding vector as a list of floats.
        """
        if isinstance(input, str):
            input = [input]
        result = self(input)
        return result[0]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """Embed a list of document strings.

        Args:
            input: List of document text strings.

        Returns:
            List of embedding vectors.
        """
        return self(input)


class EmbeddingFactory:
    """
    Factory for creating embedding functions.

    The factory reads the embedding configuration from the centralized
    Pydantic settings and returns a ready-to-use embedding function
    instance. This decouples the embedding provider choice from the
    rest of the RAG pipeline.
    """

    @classmethod
    def get_embedding_function(cls):
        """Create and return an embedding function.

        Currently returns a ``LitellmEmbeddingFunction`` configured with
        the API key and model name from the application settings.

        Returns:
            An embedding function instance ready for use with the
            retriever and ingestion pipelines.
        """
        settings = get_settings()
        return LitellmEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model,
        )
