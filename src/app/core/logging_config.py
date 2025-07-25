import logging
import logging.config
from pathlib import Path

import yaml

def setup_logging(default_path: str):
    path = Path(default_path)
    if path.exists():
        with path.open() as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=logging.INFO)
