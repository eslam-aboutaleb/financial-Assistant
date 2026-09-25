from chromadb.utils import embedding_functions
from app.config import get_settings

class EmbeddingFactory:
    """
    Factory for creating ChromaDB embedding functions.
    This pattern makes it easy to swap between OpenAI, Vertex AI, HuggingFace, etc.
    """
    @classmethod
    def get_embedding_function(cls):
        settings = get_settings()
        # Currently defaults to OpenAI.
        # Future enhancement: route based on an environment variable or setting,
        # e.g., if settings.embedding_provider == "openai": ...
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name=settings.embedding_model,
        )
