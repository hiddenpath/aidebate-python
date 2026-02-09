"""Entry point for running aidebate as a module: python -m aidebate"""

import logging
import os

import uvicorn
from dotenv import load_dotenv


def main():
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "3000"))

    uvicorn.run(
        "aidebate.app:app",
        host=host,
        port=port,
        log_level="info",
        timeout_keep_alive=420,
    )


if __name__ == "__main__":
    main()
