.PHONY: test all build clean install-dev # lint format autoflake check-format

# lint:
# 	flake8 .

# format:
# 	black .
# 	isort .

# autoflake:
# 	autoflake --remove-all-unused-imports --remove-unused-variables -i -r .

test:
	pytest

# check-format:
# 	black --check .
# 	isort --check-only .

build:
	python -m PyInstaller runninglog.spec

build-mac: build
	cd dist && zip -r runninglog-macos.zip runninglog

build-win: build
	cd dist && zip -r runninglog-windows.zip runninglog.exe

clean:
	rm -rf build/ dist/ *.egg-info/ __pycache__/ **/__pycache__/

install-dev:
	pip install -e ".[dev]"
	pip install pyinstaller

all: test # autoflake format lint check-format
