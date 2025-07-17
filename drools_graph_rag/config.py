"""
Configuration module for the Drools Graph RAG package.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Neo4jConfig:
    """
    Configuration for Neo4j connection.
    """

    uri: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username: str = os.environ.get("NEO4J_USERNAME", "neo4j")
    password: str = os.environ.get("NEO4J_PASSWORD", "password")
    database: str = os.environ.get("NEO4J_DATABASE", "neo4j")


@dataclass
class EmbeddingConfig:
    """
    Configuration for embedding model.
    """

    model_name: str = os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
    )
    device: str = os.environ.get("EMBEDDING_DEVICE", "cpu")
    batch_size: int = int(os.environ.get("EMBEDDING_BATCH_SIZE", "32"))


@dataclass
class LLMConfig:
    """
    Configuration for language model.
    """

    model_name: str = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
    api_key: Optional[str] = os.environ.get("OPENAI_API_KEY", None)
    temperature: float = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    max_tokens: int = int(os.environ.get("LLM_MAX_TOKENS", "1024"))


@dataclass
class Config:
    """
    Global configuration for the Drools Graph RAG package.
    """

    neo4j: Neo4jConfig = Neo4jConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")

    @classmethod
    def from_dict(cls, config_dict: Dict) -> "Config":
        """
        Create a Config instance from a dictionary.

        Args:
            config_dict: The configuration dictionary.

        Returns:
            A Config instance.
        """
        neo4j_config = Neo4jConfig(
            uri=config_dict.get("neo4j", {}).get("uri", Neo4jConfig.uri),
            username=config_dict.get("neo4j", {}).get("username", Neo4jConfig.username),
            password=config_dict.get("neo4j", {}).get("password", Neo4jConfig.password),
            database=config_dict.get("neo4j", {}).get("database", Neo4jConfig.database),
        )

        embedding_config = EmbeddingConfig(
            model_name=config_dict.get("embedding", {}).get(
                "model_name", EmbeddingConfig.model_name
            ),
            device=config_dict.get("embedding", {}).get(
                "device", EmbeddingConfig.device
            ),
            batch_size=config_dict.get("embedding", {}).get(
                "batch_size", EmbeddingConfig.batch_size
            ),
        )

        llm_config = LLMConfig(
            model_name=config_dict.get("llm", {}).get("model_name", LLMConfig.model_name),
            api_key=config_dict.get("llm", {}).get("api_key", LLMConfig.api_key),
            temperature=config_dict.get("llm", {}).get(
                "temperature", LLMConfig.temperature
            ),
            max_tokens=config_dict.get("llm", {}).get(
                "max_tokens", LLMConfig.max_tokens
            ),
        )

        return cls(
            neo4j=neo4j_config,
            embedding=embedding_config,
            llm=llm_config,
            log_level=config_dict.get("log_level", cls.log_level),
        )


# Create a default configuration instance
config = Config()