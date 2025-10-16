# Contributing to WireGuard SPA

Thank you for your interest in contributing to WireGuard SPA! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a new branch for your feature or bug fix
4. Make your changes
5. Test your changes
6. Submit a pull request

## Development Setup

### Backend (Azure Functions)

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure local settings
cp local.settings.json.template local.settings.json
# Edit local.settings.json with your values

# Run locally
func start
```

### Frontend (Vue.js SPA)

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Infrastructure (Bicep)

```bash
# Validate Bicep template
az bicep build --file infra/main.bicep

# Preview deployment changes
az deployment group what-if \
  --resource-group wireguard-spa-rg \
  --template-file infra/main.bicep \
  --parameters projectName=wgspa
```

## Code Style

### Python
- Follow PEP 8 style guide
- Use meaningful variable names
- Add docstrings to functions and classes
- Keep functions focused and small

### JavaScript/Vue
- Use ES6+ features
- Follow Vue.js style guide
- Use meaningful component and variable names
- Keep components small and focused

### Bicep
- Use descriptive resource names
- Add comments for complex logic
- Use parameters for configurable values
- Include output values for important resources

## Testing

### Python Testing
```bash
cd backend
python -m pytest tests/
```

### Frontend Testing
```bash
cd frontend
npm test
```

### Infrastructure Testing
```bash
# Validate Bicep syntax
az bicep build --file infra/main.bicep

# Dry-run deployment
az deployment group create \
  --resource-group test-rg \
  --template-file infra/main.bicep \
  --parameters projectName=test \
  --what-if
```

## Pull Request Process

1. **Update Documentation**: If you change functionality, update the README.md and relevant documentation
2. **Update Tests**: Add or update tests for your changes
3. **Follow Code Style**: Ensure your code follows the project's style guidelines
4. **Write Clear Commit Messages**: Use descriptive commit messages
5. **Keep PRs Focused**: Each PR should address a single concern
6. **Update Changelog**: Add your changes to CHANGELOG.md (if it exists)

### PR Title Format
- `feat: Add new feature`
- `fix: Fix bug in component`
- `docs: Update documentation`
- `chore: Update dependencies`
- `refactor: Refactor code`
- `test: Add tests`

## Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and PRs in commit body

Example:
```
feat: Add session timeout notification

- Add countdown timer to UI
- Show notification 5 minutes before timeout
- Allow user to extend session

Closes #123
```

## Reporting Bugs

When reporting bugs, please include:
- **Description**: Clear description of the bug
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, browser, Azure region, etc.
- **Screenshots**: If applicable
- **Logs**: Relevant error logs or stack traces

## Suggesting Features

When suggesting features, please include:
- **Use Case**: Describe the problem you're trying to solve
- **Proposed Solution**: Your suggested approach
- **Alternatives**: Other solutions you've considered
- **Additional Context**: Any other relevant information

## Code Review Process

All PRs will be reviewed by maintainers. Reviews will check for:
- Code quality and style
- Test coverage
- Documentation updates
- Breaking changes
- Security considerations

Please be patient during the review process and be open to feedback.

## Community Guidelines

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Help others learn
- Give credit where credit is due

## Security

If you discover a security vulnerability, please email the maintainers directly instead of opening a public issue. Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## License

By contributing to WireGuard SPA, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:
- Check existing issues and discussions
- Review the README and documentation
- Open a new issue with the "question" label

Thank you for contributing to WireGuard SPA! 🎉
