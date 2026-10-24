# Automatic Solution Generator (ASG)

A Python-based tool that automates solution generation by interacting with the OpenCode API to create, manage, and monitor AI agent sessions for solving development tasks.

## Overview

The Automatic Solution Generator provides an automated workflow to:
- Connect to OpenCode API instances
- Manage AI agent sessions
- Execute prompts and commands programmatically
- Monitor session progress and retrieve results
- Generate solutions iteratively for project requirements

## Prerequisites

- **Python** >= 3.14
- **OpenCode server** running and accessible via API

## Installation

1. **Clone or navigate to the project directory:**

   ```bash
   cd automatic-solution-generator
   ```

2. **Create and activate a virtual environment:**

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   uv sync
   ```

   Or install directly with pip:

   ```bash
   pip install pyyaml requests curlify waiting
   ```

## Configuration

The ASG requires a YAML configuration file to run. Create a configuration file with the following parameters:

```yaml
# config.yaml example
project_path: "/path/to/project/directory"
project_requirements: "/path/to/requirements.txt"
opencode_base_url: "http://localhost:8000"
opencode_user: "your_username"
opencode_password: "your_password"
model: "provider/model-name"
```

### Configuration Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_path` | string | Absolute path where generated solutions will be created |
| `project_requirements` | string | Path to a file containing project requirements or prompts |
| `opencode_base_url` | string | Base URL of the OpenCode API server |
| `opencode_user` | string | Username for OpenCode API authentication |
| `opencode_password` | string | Password for OpenCode API authentication |
| `model` | string | Model specification in format `providerID/modelID` (e.g., `opencode/big-pickle`) |

## Usage

### Running the Main Generator

Execute the main script with a configuration file:

```bash
python main.py --config config.yaml
```

Or using the short form:

```bash
python main.py -c config.yaml
```

### Using the Opencode Example Script

A standalone example script is provided for testing the API directly:

```bash
python scripts/opencode-example.py
```

You can customize it using environment variables:

```bash
export OPENCODE_BASE_URL="http://localhost:8000"
export OPENCODE_USERNAME="user"
export OPENCODE_PASSWORD="password"
export OPENCODE_AGENT="build"
export OPENCODE_MODEL="opencode/big-pickle"
export OPENCODE_MESSAGE="Create a Python script that prints Hello World"
python scripts/opencode-example.py
```

## Project Structure

```
automatic-solution-generator/
├── main.py                 # Main entry point
├── src/
│   └── asg.py             # AutomaticSolutionGenerator class
├── utils/
│   ├── config_utils.py    # Configuration file handling
│   ├── log_utils.py       # Logging utilities
│   └── opencode_api.py    # OpenCode API client
├── scripts/
│   └── opencode-example.py # Example API usage script
├── tests/
│   └── test_opencode_api.py # Unit tests
├── logs/                   # Log files directory (auto-created)
├── build/                  # Build output directory
└── pyproject.toml         # Project dependencies and metadata
```

## Module Reference

### `OpencodeAPI` Class

The main API client with the following methods:

| Method | Description |
|--------|-------------|
| `get_health()` | Check if OpenCode server is running |
| `get_info()` | Retrieve server information |
| `get_config()` | Get current OpenCode configuration |
| `get_openapi()` | Fetch OpenAPI specification |
| `get_agents()` | List available agents |
| `get_session(agent, model, directory)` | Create a new session |
| `send_prompt(session, message, files)` | Send a prompt to a session |
| `get_session_messages(session)` | Retrieve session messages |
| `wait_session_messages(session, timeout)` | Wait for session completion |
| `execute_command(session, command_name, text, ...)` | Execute commands in a session |

### `AutomaticSolutionGenerator` Class

Main orchestrator class that:
- Validates OpenCode connection
- Loads project requirements
- Manages sprint cycles
- Coordinates agent interactions

### `LogUtils` Class

Provides logging functionality:
- Console and file logging
- Timestamp-based log file naming
- JSON dictionary export capability

## Logging

Logs are automatically saved to the `logs/` directory with the following format:

- Daily log files: `logs/YYYYMMDD-asg.log`
- JSON exports: `logs/YYYYMMDDHHMMSS-{resource}.json`

## Requirements File Format

The `project_requirements` file should contain:
- Clear description of the desired solution
- Any specific constraints or guidelines
- Example inputs and expected outputs

Example:
```
Create a Python script called hello_world.py that:
1. Prints "Hello, World!" to the console
2. Uses proper Python conventions
3. Is placed in the build directory
```

## Troubleshooting

### Connection Issues

- Verify OpenCode server is running: `curl http://localhost:8000/api/info`
- Check authentication credentials
- Ensure the base URL is correct

### Permission Errors

- Verify file write permissions in `project_path`
- Check virtual environment activation

### Model Errors

- Confirm the model ID exists in your OpenCode instance
- Verify provider format: `providerID/modelID`

## License

This project is licensed under the terms specified in the LICENSE file.

## Development

To run tests:

```bash
python -m pytest tests/
```

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
