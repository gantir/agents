"""Entry point for catapult."""

from logging.config import fileConfig
from os import path

from dotenv import load_dotenv

if __name__ == "__main__":  # pragma: no cover
    log_file_path = path.join(path.dirname(path.abspath(__file__)), "logging.conf")
    fileConfig(log_file_path, disable_existing_loggers=False)
    load_dotenv()
