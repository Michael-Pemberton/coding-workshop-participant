"""Application configuration loaded from environment variables."""
import os


class Settings:
    """
    Centralized settings derived from environment variables.

    Supports both local development (IS_LOCAL=true) and AWS deployments.
    """

    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_name: str = os.getenv("POSTGRES_NAME", "postgres")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_pass: str = os.getenv("POSTGRES_PASS", "postgres123")
    is_local: bool = os.getenv("IS_LOCAL", "false") == "true"
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    app_id: str = os.getenv("APP_ID", "local")

    @property
    def postgres_dsn(self) -> str:
        """Builds a psycopg connection string, adding SSL for non-local environments."""
        ssl = "" if self.is_local else " sslmode=require"
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_name} "
            f"user={self.postgres_user} "
            f"password={self.postgres_pass} "
            f"connect_timeout=15"
            + ssl
        )


settings = Settings()
