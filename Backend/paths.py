from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

DB_PATH              = str(DATA_DIR / "db" / "Nse_Mainbhavdata.db")
RAW_BHAV_PATH        = str(DATA_DIR / "RawBhvcopy")
JSON_PATH            = str(DATA_DIR / "csvjson")
PIPELINE_LOG_PATH    = str(DATA_DIR / "pipeline_logs")
BHAVPIPELINE_SRC     = str(_BACKEND_DIR / "bhavpipeline" / "src")
BHAVPIPELINE_CONFIG  = str(_BACKEND_DIR / "bhavpipeline" / "config")
