# Agents Guide for ami-helper

This document provides guidance for AI agents working with the `ami-helper` project, a Python CLI tool designed to assist with AMI (ATLAS Metadata Interface) data access for particle physics research.

## Project Overview

`ami-helper` is a command-line tool that interfaces with the ATLAS Metadata Interface to help physicists find and work with Monte Carlo simulation datasets. It's specifically designed for the ATLAS experiment at CERN and provides utilities for querying hashtag information across different Monte Carlo production scopes.

## Architecture

### Core Components

- **CLI Interface** (`src/ami_helper/__main__.py`): Built with Typer, provides command-line interface
- **AMI Integration** (`src/ami_helper/ami.py`): Handles communication with the AMI service using pyAMI
- **Data Model** (`src/ami_helper/datamodel.py`): Defines structured data for different MC production scopes
- **Configuration**: Uses `pyproject.toml` for project metadata and build configuration

## Development Guidelines for Agents

### Code Style & Structure

1. **Type Annotations**: The project uses modern Python type hints extensively
2. **Dataclasses**: Immutable dataclasses with `frozen=True` for data structures, define them in datamodel.py
3. **Enums**: CLI uses Typer's enum support for validated arguments
4. **Error Handling**: Uses assertions for AMI response validation

### Testing

- Tests are in `tests/` directory using pytest
- Mock AMI client interactions for unit tests
- Coverage reporting configured via `pyproject.toml`
- Unit tests should be in files called test_xxx.py, where xxx is the name of the file that contains the code being tested.

### AMI Integration Patterns

When working with AMI queries:

1. **Client Setup**:
   ```python
   ami = pyAMI.client.Client("atlas-replica")
   AtlasAPI.init()
   ```

2. **Query Construction**: Build a truncated SQL strings (see examples in ami.py)
3. **Response Handling**: Always validate DOMObject responses with assertions

## Testing Strategy

### Unit Tests

- Mock `pyAMI.client.Client` for all AMI interactions
- Test data model validation
- Verify CLI argument parsing

## Contributing Guidelines

When making changes:

1. Maintain backward compatibility in data structures unless instructed otherwise.
2. Add comprehensive tests for new functionality
3. Update documentation and type hints
4. Validate changes against real AMI service when possible
5. Follow existing code organization patterns

This project serves the particle physics community, so reliability and accuracy of metadata queries is paramount.