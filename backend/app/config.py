"""
Configuration Management
Loads configuration from .env file in project root
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no .env in root, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'firstbreath-dev-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    JSON_AS_ASCII = False

    # LLM configuration (OpenRouter / any OpenAI-compatible endpoint)
    LLM_API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('OPENROUTER_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://openrouter.ai/api/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'stealth/ox-alpha')
    LLM_FALLBACK_MODEL = os.environ.get('LLM_FALLBACK_MODEL', '')

    # Supabase (Postgres) configuration
    SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
    SUPABASE_SECRET_KEY = os.environ.get('SUPABASE_SECRET_KEY', '')
    DATABASE_URL = os.environ.get('DATABASE_URL', '')  # direct Postgres connection string

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # CORS: comma-separated list of allowed frontend origins
    ALLOWED_ORIGINS = [
        o.strip() for o in os.environ.get(
            'ALLOWED_ORIGINS',
            'http://localhost:3000,http://localhost:5173'
        ).split(',') if o.strip()
    ]

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured")
        if not cls.SUPABASE_URL or not cls.SUPABASE_SECRET_KEY:
            errors.append("Supabase configuration incomplete")
        return errors
