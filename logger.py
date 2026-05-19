import logging
import os
import sys
from datetime import datetime

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "server.log")

# Setup formatter
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# File handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

logger = logging.getLogger("lexai")
logger.setLevel(logging.INFO)
# Remove any existing handlers to prevent duplicate logging
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_api_call(endpoint: str, method: str, client_ip: str, user_email: str = "guest", status_code: int = 200, duration_ms: float = 0.0):
    logger.info(f"API_CALL | Endpoint: {endpoint} | Method: {method} | IP: {client_ip} | User: {user_email} | Status: {status_code} | Duration: {duration_ms:.2f}ms")

def log_security_event(event_type: str, details: str, client_ip: str, user_email: str = "unknown"):
    logger.warning(f"SECURITY_WARNING | Type: {event_type} | User: {user_email} | IP: {client_ip} | Details: {details}")

def log_pdf_generation(doc_type: str, jurisdiction: str, user_email: str = "guest", success: bool = True, error: str = ""):
    if success:
        logger.info(f"PDF_GEN_SUCCESS | DocType: {doc_type} | Jurisdiction: {jurisdiction} | User: {user_email}")
    else:
        logger.error(f"PDF_GEN_FAILED | DocType: {doc_type} | Jurisdiction: {jurisdiction} | User: {user_email} | Error: {error}")

def log_error(context: str, error: Exception, exc_info: bool = True):
    logger.error(f"ERROR | Context: {context} | Error: {str(error)}", exc_info=exc_info)
