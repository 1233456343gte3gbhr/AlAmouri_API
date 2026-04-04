"""
⚙️ إعدادات التطبيق
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """إعدادات التطبيق الرئيسية"""
    
    # API Configuration
    api_key: str = "AlAmouri_Pro_123456"
    debug: bool = True
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Rate Limiting
    rate_limit_extract: str = "20/minute"
    rate_limit_download: str = "10/minute"
    
    # Cache Configuration
    cache_ttl_tiktok: int = 3600  # 1 hour
    cache_ttl_youtube: int = 86400  # 24 hours
    cache_ttl_facebook: int = 7200  # 2 hours
    cache_ttl_instagram: int = 7200  # 2 hours
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
