# Contributing to AI Bug Deduplication

Thank you for your interest in contributing to this project! We welcome contributions from the community.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/ai-bug-deduplication.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `pytest`
6. Commit your changes: `git commit -m "Add your feature"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a Pull Request

## Development Setup

Follow the installation instructions in [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md).

## Code Standards

- Follow PEP 8 style guide for Python code
- Write meaningful commit messages
- Add docstrings to all functions and classes
- Include type hints where appropriate
- Write unit tests for new features
- Update documentation as needed

## Testing

Before submitting a PR, ensure all tests pass:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_duplicate_detector.py
```

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Add tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Request review from maintainers

## Code Review

All submissions require review. We use GitHub pull requests for this purpose.

## Reporting Bugs

Use GitHub Issues to report bugs. Include:

- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

## Feature Requests

We welcome feature requests! Please use GitHub Issues and include:

- Clear description of the feature
- Use case and rationale
- Proposed implementation (if applicable)

## Questions?

Feel free to open an issue for questions or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
