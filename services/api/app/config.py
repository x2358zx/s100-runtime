import os

class Settings:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "s100logs")
    DB_USER: str = os.getenv("DB_USER", "app")
    DB_PASS: str = os.getenv("DB_PASS", "app123")
    TZ: str = os.getenv("TZ", "Asia/Taipei")
    LOG_ROOT_S100_1: str = os.getenv("LOG_ROOT_S100_1", "/data/s100-1")
    LOG_ROOT_S100_2: str = os.getenv("LOG_ROOT_S100_2", "/data/s100-2")
    HIST_DIR_NAME: str = os.getenv("HIST_DIR_NAME", "S100_test_log")
    API_TOKEN: str = os.getenv("API_TOKEN", "")

settings = Settings()
