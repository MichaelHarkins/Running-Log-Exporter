# Contributing to RunningLog Exporter CLI

Thank you for your interest in contributing! This project welcomes bug reports, feature requests, and code contributions.

## How to Contribute

1. **Fork the repository** and create your branch from `main`.
2. **Write clear, descriptive commit messages**.
3. **Add or update tests** for any new features or bug fixes.
4. **Run all tests and linter/formatter** before submitting a pull request.
5. **Open a pull request** with a clear description of your changes.

## Code Style

- Use [Black](https://black.readthedocs.io/en/stable/) for code formatting.
- Use [flake8](https://flake8.pycqa.org/en/latest/) for linting.
- Follow PEP8 and PEP257 for code and docstring style.
- Organize imports using [isort](https://pycqa.github.io/isort/).

## Reporting Issues

- Use the GitHub Issues tab to report bugs or request features.
- Include as much detail as possible: steps to reproduce, expected behavior, actual behavior, and environment info.

## Directory Structure

- All athlete-specific data (output, debug, state, journal) is stored under a subdirectory named after the athlete.
- Use the `--output-dir` option to specify a custom output directory for TCX files.
- State, debug, and journal files always remain under the athlete-specific directory.

## Pull Request Checklist

- [ ] All tests pass.
- [ ] Code is formatted with Black.
- [ ] Linting passes with flake8.
- [ ] Documentation and README are updated as needed.
- [ ] No sensitive data or secrets are included.

## Community

- Be respectful and constructive in all interactions.
- Review and respond to issues and pull requests in a timely manner.

Thank you for helping make RunningLog Exporter CLI better!
