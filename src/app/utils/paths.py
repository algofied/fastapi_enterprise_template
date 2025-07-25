from pathlib import Path

FILE = Path(__file__).resolve()
APP_ROOT = FILE.parents[1]
PROJECT_ROOT = FILE.parents[2]

def in_project(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)

def in_app(*parts: str) -> Path:
    return APP_ROOT.joinpath(*parts)
