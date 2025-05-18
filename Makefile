.PHONY: lint format test autoflake all

lint:
	flake8 .

format:
	black .
	isort .

autoflake:
	autoflake --remove-all-unused-imports --remove-unused-variables -i -r .

test:
	pytest

check-format:
	black --check .
	isort --check-only .

all: autoflake format lint check-format test
