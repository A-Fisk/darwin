# Darwin Configurable Endpoint Support

Darwin now supports configurable LLM endpoints, allowing you to easily switch between different LLM providers, local models, or custom endpoints without code changes.

## Configuration Methods

Darwin supports three configuration methods with the following priority order:

1. **CLI flags** (highest priority)
2. **Environment variables**
3. **Configuration files** (lowest priority)

## CLI Flags

Use command-line flags to override settings for a single run:

```bash
# Use a custom endpoint
darwin "research topic" --base-url https://api.openrouter.ai/api/v1 --api-key sk-or-...

# Use a local Ollama server
darwin "research topic" --base-url http://localhost:11434 --model llama3.2:latest --timeout 60

# Use different Claude model
darwin "research topic" --model claude-opus-4-6 --timeout 45
```

### Available CLI Options

- `--api-key KEY`: API key for LLM service (overrides `ANTHROPIC_API_KEY`)
- `--auth-token TOKEN`: Auth token for LLM service (overrides `ANTHROPIC_AUTH_TOKEN`)
- `--base-url URL`: Base URL for LLM API endpoint (overrides `ANTHROPIC_BASE_URL`)
- `--timeout SECONDS`: Request timeout in seconds (overrides `DARWIN_TIMEOUT`)
- `--max-retries N`: Maximum number of API retries (overrides `DARWIN_MAX_RETRIES`)
- `--model MODEL`: LLM model to use (overrides `DARWIN_MODEL`, default: claude-sonnet-4-6)

## Environment Variables

Set environment variables for persistent configuration:

```bash
# Anthropic API (existing support)
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_AUTH_TOKEN="your-auth-token"  # alternative
export ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Darwin-specific settings (new)
export DARWIN_MODEL="claude-opus-4-6"
export DARWIN_TIMEOUT="30.0"
export DARWIN_MAX_RETRIES="3"
```

## Configuration Files

Create a TOML configuration file for project-specific settings:

### File Locations (checked in order)

1. `./darwin.toml` (current directory)
2. `~/.config/darwin/darwin.toml` (user config directory)

### Example Configuration

```toml
[llm]
# API configuration
api_key = "your-api-key"
# auth_token = "your-auth-token"  # alternative to api_key

# Endpoint configuration
base_url = "https://api.anthropic.com"

# Model and request settings
model = "claude-sonnet-4-6"
timeout = 30.0
max_retries = 2
```

## Common Use Cases

### 1. OpenRouter (Third-party API)

**CLI:**
```bash
darwin "research topic" \\
  --api-key "sk-or-..." \\
  --base-url "https://openrouter.ai/api/v1" \\
  --model "anthropic/claude-sonnet-4-6"
```

**Config file:**
```toml
[llm]
api_key = "sk-or-..."
base_url = "https://openrouter.ai/api/v1"
model = "anthropic/claude-sonnet-4-6"
timeout = 45.0
```

### 2. Local Ollama Server

**CLI:**
```bash
darwin "research topic" \\
  --base-url "http://localhost:11434" \\
  --model "llama3.2:latest" \\
  --timeout 60
```

**Config file:**
```toml
[llm]
base_url = "http://localhost:11434"
model = "llama3.2:latest"
timeout = 60.0
max_retries = 1
```

### 3. Corporate Proxy

**Environment variables:**
```bash
export ANTHROPIC_API_KEY="corp-key"
export ANTHROPIC_BASE_URL="https://ai-gateway.corp.com/anthropic"
export DARWIN_TIMEOUT="45.0"
export DARWIN_MAX_RETRIES="5"
```

**Config file:**
```toml
[llm]
api_key = "corp-key"
base_url = "https://ai-gateway.corp.com/anthropic"
timeout = 45.0
max_retries = 5
```

### 4. Different Claude Models

```toml
[llm]
# For higher quality (slower, more expensive)
model = "claude-opus-4-6"

# For faster responses (lower quality)
# model = "claude-haiku-4-6"

# Default (balanced)
# model = "claude-sonnet-4-6"
```

## Supported Parameters

| Parameter | CLI Flag | Environment Variable | Config Key | Description |
|-----------|----------|---------------------|------------|-------------|
| API Key | `--api-key` | `ANTHROPIC_API_KEY` | `api_key` | Authentication key |
| Auth Token | `--auth-token` | `ANTHROPIC_AUTH_TOKEN` | `auth_token` | Alternative auth |
| Base URL | `--base-url` | `ANTHROPIC_BASE_URL` | `base_url` | API endpoint URL |
| Model | `--model` | `DARWIN_MODEL` | `model` | Model identifier |
| Timeout | `--timeout` | `DARWIN_TIMEOUT` | `timeout` | Request timeout (seconds) |
| Max Retries | `--max-retries` | `DARWIN_MAX_RETRIES` | `max_retries` | Retry attempts |

## Testing Configuration

Test your configuration without running a full research session:

```bash
# Test with Python
python -c "from darwin.config import get_llm_config; print(get_llm_config())"

# Test client creation
python -c "from darwin.agents._common import get_anthropic_client; print(get_anthropic_client())"
```

## Migration from Previous Versions

If you were previously using Darwin with environment variables, your existing setup will continue to work unchanged. The new configuration system is fully backward compatible.

## Troubleshooting

### Configuration Not Loading

1. Check file location: `./darwin.toml` or `~/.config/darwin/darwin.toml`
2. Validate TOML syntax: `python -c "import tomllib; tomllib.load(open('darwin.toml', 'rb'))"`
3. Check environment variables: `env | grep -E "(ANTHROPIC|DARWIN)_"`

### Authentication Issues

1. Verify API key/token is correct
2. Check base URL matches your provider
3. Ensure your account has sufficient credits/quota

### Connection Issues

1. Test connectivity: `curl -I <base-url>`
2. Check firewall/proxy settings
3. Verify timeout settings are appropriate for your network

### Model Issues

1. Confirm model is available at your endpoint
2. Check model name format matches provider requirements
3. Verify your API key has access to the requested model