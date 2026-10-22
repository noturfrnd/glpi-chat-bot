import os


def validation_bypassed() -> bool:
    """Permite ignorar verificações extras somente em ambiente de desenvolvimento."""
    return (
        os.getenv("APP_ENV", "production").strip().lower() == "development"
        and os.getenv("DEV_BYPASS_API_VALIDATION", "").strip().lower() in {"1", "true", "yes"}
    )
