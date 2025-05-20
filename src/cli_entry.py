# Explicit imports to help PyInstaller bundle all dependencies
import typer  # noqa: F401
import rich  # noqa: F401
import httpx  # noqa: F401
import beautifulsoup4  # noqa: F401
import lxml  # noqa: F401
import tenacity  # noqa: F401
import pytz  # noqa: F401
import pydantic  # noqa: F401
import dateparser  # noqa: F401
import aiofiles  # noqa: F401

from runninglog.cli.typer_main import app

if __name__ == "__main__":
    app()
