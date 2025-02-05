"""Entry point for agents."""

# from logging.config import fileConfig

from dotenv import load_dotenv

from agents.aopic import run

if __name__ == "__main__":  # pragma: no cover
    # log_file_path = path.join(path.dirname(path.abspath(__file__)), "logging.conf")
    # fileConfig(log_file_path, disable_existing_loggers=False)
    load_dotenv()
    run()
