"""
Configuration management for URS Generator.
Uses pydantic-settings for environment variable handling.
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = "URS Generator"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_key: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    groq_api_key: Optional[str] = None
    
    # LLM Settings
    llm_mode: str = "real"  # "mock" or "real"
    llm_provider: str = "groq"  # "openai", "azure", or "groq"
    llm_model: str = "llama-3.3-70b-versatile"  # Groq's best free model
    llm_temperature: float = 0.1  # Low temp for deterministic outputs
    llm_max_tokens: int = 4096
    
    # Storage
    database_url: str = "sqlite+aiosqlite:///./urs_generator.db"
    upload_dir: str = "./uploads"
    
    # Chunking
    chunk_size: int = 1000  # tokens
    chunk_overlap: int = 100  # tokens
    
    # Data Classification
    default_classification: str = "INTERNAL"
    
    # Audit
    audit_log_path: str = "./audit_logs"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

