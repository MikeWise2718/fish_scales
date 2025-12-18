# OpenRouter How-To Guide

This guide explains how to use OpenRouter with the fish-scale-agent for automated tubercle detection.

## What is OpenRouter?

OpenRouter is a unified API that provides access to many different LLMs (Large Language Models) through a single interface. Instead of managing separate API keys and integrations for Claude, GPT-4, Gemini, Llama, etc., you can use one OpenRouter API key to access all of them.

**Benefits:**
- Single API key for multiple providers
- Easy model switching without code changes
- Often lower prices than direct API access
- Access to open-source models (Llama, Mistral) alongside commercial ones

## Signing Up for OpenRouter

1. Go to [https://openrouter.ai](https://openrouter.ai)
2. Click "Sign In" in the top right
3. Sign in with Google, GitHub, or email
4. Once logged in, go to [https://openrouter.ai/keys](https://openrouter.ai/keys)
5. Click "Create Key"
6. Give your key a name (e.g., "fish-scale-agent")
7. Copy the key - it starts with `sk-or-v1-...`

**Important:** Store your API key securely. Never commit it to git.

## Setting Up Your API Key

Set the environment variable before running the agent:

**Windows (Command Prompt):**
```cmd
set OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**Windows (PowerShell):**
```powershell
$env:OPENROUTER_API_KEY = "sk-or-v1-your-key-here"
```

**Linux/macOS:**
```bash
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**Permanent setup:** Add the export line to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) or Windows environment variables.

## Which Models Work for This Application?

The fish-scale-agent requires models that support:
1. **Vision** - ability to analyze images (screenshots of the fish scale)
2. **Tool/Function calling** - ability to call tools like `add_tubercle`, `run_extraction`, etc.

### Recommended Models

#### Tier 1: Premium (Best Quality)
| Model | Vision | Tools | Input $/M | Output $/M | Notes |
|-------|--------|-------|-----------|------------|-------|
| `anthropic/claude-sonnet-4` | ✅ | ✅ | $3.00 | $15.00 | **Default** - Best balance |
| `openai/gpt-4o` | ✅ | ✅ | $2.50 | $10.00 | Strong alternative |
| `x-ai/grok-4` | ✅ | ✅ | $3.00 | $15.00 | 2M context window |
| `mistralai/pixtral-large-2411` | ✅ | ✅ | $2.00 | $6.00 | 124B multimodal |

#### Tier 2: Budget (Good Value)
| Model | Vision | Tools | Input $/M | Output $/M | Notes |
|-------|--------|-------|-----------|------------|-------|
| `google/gemini-2.0-flash-001` | ✅ | ✅ | $0.10 | $0.40 | **Recommended** - reliable, fast |
| `x-ai/grok-4-fast` | ✅ | ✅ | $0.20 | $0.50 | Excellent value, 2M context |
| `x-ai/grok-4.1-fast` | ✅ | ✅ | $0.20 | $0.50 | Best tool-calling |
| `qwen/qwen3-vl-32b-instruct` | ✅ | ✅ | $0.02 | $0.00 | Nearly free! |
| `z-ai/glm-4.6v` | ✅ | ✅ | $0.20 | $0.50 | Chinese, vision model |
| `z-ai/glm-4.5` | ✅ | ✅ | $0.11 | $0.28 | Agentic, very cheap |
| `openai/gpt-4o-mini` | ✅ | ✅ | $0.15 | $0.60 | Fast, may be less accurate |
| `mistralai/pixtral-12b` | ✅ | ✅ | $0.125 | $0.125 | Lightweight vision |

#### Tier 3: FREE Models
| Model | Vision | Tools | Notes |
|-------|--------|-------|-------|
| `qwen/qwen2.5-vl-72b-instruct:free` | ✅ | ✅ | Free tier, 72B params |
| `qwen/qwen2.5-vl-32b-instruct:free` | ✅ | ✅ | Free tier, 32B params |
| `mistralai/mistral-small-3.1-24b-instruct:free` | ✅ | ⚠️ | Free tier - tool calling unreliable |

**⚠️ Free Model Warning:** Free tier models often have unreliable tool calling or availability issues (404 errors, rate limits). For reliable results, use `google/gemini-2.0-flash-001` (~$0.01-0.03 per run).

### Models That Won't Work

These models lack vision support (text-only):
- `deepseek/deepseek-chat` - Excellent but no vision
- `deepseek/deepseek-chat-v3.1` - No vision
- Most Llama models (no vision)
- Older GPT models (GPT-3.5)
- Pure text models

### How to Check Model Capabilities

1. Go to [https://openrouter.ai/docs#models](https://openrouter.ai/docs#models)
2. Look for the "Modality" column - must include "vision" or "multimodal"
3. Check "Context" - larger is better for our use case (we send images)
4. Look for tool/function calling support in the model description

## Specifying Which Model to Use

### Command Line

```bash
# Use default model (anthropic/claude-sonnet-4)
uv run fish-scale-agent run image.tif --provider openrouter

# Use a specific model
uv run fish-scale-agent run image.tif --provider openrouter --model openai/gpt-4o

# Use budget model
uv run fish-scale-agent run image.tif --provider openrouter --model openai/gpt-4o-mini
```

### Model Name Format

OpenRouter model names follow the format: `provider/model-name`

Examples:
- `anthropic/claude-sonnet-4`
- `anthropic/claude-3.5-sonnet`
- `openai/gpt-4o`
- `openai/gpt-4o-mini`
- `google/gemini-pro-1.5`
- `google/gemini-flash-1.5`

Find the exact model name on the [OpenRouter models page](https://openrouter.ai/docs#models).

## Expected Costs

### Pricing Overview

OpenRouter charges per token (roughly 4 characters = 1 token). Prices are per million tokens.

#### Premium Models
| Model | Input $/M | Output $/M | Typical Run* |
|-------|-----------|------------|--------------|
| `anthropic/claude-sonnet-4` | $3.00 | $15.00 | $0.30 - $0.50 |
| `openai/gpt-4o` | $2.50 | $10.00 | $0.25 - $0.40 |
| `x-ai/grok-4` | $3.00 | $15.00 | $0.30 - $0.50 |
| `mistralai/pixtral-large-2411` | $2.00 | $6.00 | $0.15 - $0.30 |

#### Budget Models
| Model | Input $/M | Output $/M | Typical Run* |
|-------|-----------|------------|--------------|
| `google/gemini-2.0-flash-001` | $0.10 | $0.40 | $0.01 - $0.03 |
| `x-ai/grok-4-fast` | $0.20 | $0.50 | $0.02 - $0.04 |
| `x-ai/grok-4.1-fast` | $0.20 | $0.50 | $0.02 - $0.04 |
| `z-ai/glm-4.5` | $0.11 | $0.28 | $0.01 - $0.02 |
| `z-ai/glm-4.6v` | $0.20 | $0.50 | $0.02 - $0.04 |
| `qwen/qwen3-vl-32b-instruct` | $0.02 | $0.00 | ~$0.002 |
| `openai/gpt-4o-mini` | $0.15 | $0.60 | $0.02 - $0.05 |
| `mistralai/pixtral-12b` | $0.125 | $0.125 | $0.01 - $0.02 |

#### Free Models (while available)
| Model | Notes |
|-------|-------|
| `x-ai/grok-4.1-fast` | Free on OpenRouter (limited time offer) |
| `qwen/qwen2.5-vl-72b-instruct:free` | Free tier |
| `qwen/qwen2.5-vl-32b-instruct:free` | Free tier |
| `mistralai/mistral-small-3.1-24b-instruct:free` | Free tier |

*Typical run = 20 iterations with ~5 screenshots. Actual costs vary by image complexity.

### Why Images Are Expensive

Each screenshot sent to the model consumes tokens based on image size:
- A 700x500 pixel screenshot ≈ 1,500-2,500 tokens
- Multiple screenshots per run (debug check, after extraction, pattern analysis)
- With 5-10 screenshots per run, images alone can be 10,000-25,000 tokens

### Cost Tracking

The agent reports usage at the end of each run:

```
==================================================
USAGE SUMMARY
  Model: anthropic/claude-sonnet-4
  Iterations: 15
  Input tokens: 125,432
  Output tokens: 8,234
  Total tokens: 133,666
  Cost: $0.4994
==================================================
```

### Budget Tips

1. **Use smaller images** - Crop to just the scale area before running
2. **Use budget models for testing** - `gpt-4o-mini` or `gemini-flash-1.5`
3. **Reduce max iterations** - `--max-iterations 10` if extraction works well
4. **Check OpenRouter credits** - They sometimes offer free credits for new users

## Monitoring Your Usage

1. Go to [https://openrouter.ai/activity](https://openrouter.ai/activity)
2. View usage by day, model, and API key
3. Set up usage alerts at [https://openrouter.ai/settings](https://openrouter.ai/settings)

## Troubleshooting

### "Model not found" Error
- Check the exact model name at [openrouter.ai/docs#models](https://openrouter.ai/docs#models)
- Model names are case-sensitive

### "Insufficient credits" Error
- Add credits at [openrouter.ai/credits](https://openrouter.ai/credits)
- Check your usage at [openrouter.ai/activity](https://openrouter.ai/activity)

### "Rate limit exceeded" Error
- Wait a minute and try again
- Consider using a different model temporarily

### Vision/Tool Errors
- The model may not support vision or tools
- Switch to a recommended model from the table above

## Example Session

```bash
# Set API key
export OPENROUTER_API_KEY=sk-or-v1-abc123...

# Start the UI (required)
uv run fish-scale-ui

# In another terminal, run with Gemini 2.0 Flash (RECOMMENDED - reliable & cheap)
uv run fish-scale-agent run test_images/sample.tif --provider openrouter --model google/gemini-2.0-flash-001 -v

# Or use the default (Claude Sonnet 4 - higher quality, more expensive)
uv run fish-scale-agent run test_images/sample.tif --provider openrouter -v

# Try a free Qwen model (may have availability issues)
uv run fish-scale-agent run test_images/sample.tif --provider openrouter --model qwen/qwen2.5-vl-72b-instruct:free -v

# Try Z.ai's vision model (very cheap)
uv run fish-scale-agent run test_images/sample.tif --provider openrouter --model z-ai/glm-4.6v -v
```

## Provider Notes

### Z.ai (Zhipu)
Z.ai is a Chinese AI company (spinoff from Tsinghua University) known for extremely competitive pricing. Their GLM-4.6V model has vision support and tool calling at very low cost. The company has raised over $1.5B from investors including Alibaba and Tencent.

- `z-ai/glm-4.5` - Agentic model, no vision but excellent for text tasks
- `z-ai/glm-4.5-air` - Lighter version, even cheaper
- `z-ai/glm-4.6v` - **Vision model** - use this for fish-scale-agent

### xAI (Grok)
Grok models offer exceptional value with 2M token context windows and native tool calling. The Grok 4.1 Fast model is currently **free** on OpenRouter.

### Qwen
Alibaba's Qwen models include excellent vision-language models. The free tiers (`qwen2.5-vl-*:free`) are great for testing.

### Mistral
Pixtral models are Mistral's multimodal offerings. Pixtral-12B is lightweight and cheap; Pixtral-Large is more capable.

## Quick Reference: All Model Commands

Copy-paste ready commands for all documented models. Replace `IMAGE.tif` with your image path.

### Premium Models ($0.15 - $0.50 per run)

```bash
# Claude Sonnet 4 (default) - Best quality
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model anthropic/claude-sonnet-4 -v

# OpenAI GPT-4o - Strong alternative
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model openai/gpt-4o -v

# xAI Grok-4 - 2M context window
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model x-ai/grok-4 -v

# Mistral Pixtral Large - 124B multimodal
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model mistralai/pixtral-large-2411 -v
```

### Budget Models ($0.01 - $0.05 per run)

```bash
# Google Gemini 2.0 Flash - RECOMMENDED (reliable & cheap)
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model google/gemini-2.0-flash-001 -v

# xAI Grok-4 Fast - Excellent value
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model x-ai/grok-4-fast -v

# xAI Grok-4.1 Fast - Best tool-calling
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model x-ai/grok-4.1-fast -v

# Z.ai GLM-4.5 - Very cheap
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model z-ai/glm-4.5 -v

# Z.ai GLM-4.6V - Chinese vision model
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model z-ai/glm-4.6v -v

# Qwen3 VL 32B - Nearly free
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model qwen/qwen3-vl-32b-instruct -v

# OpenAI GPT-4o-mini - Fast
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model openai/gpt-4o-mini -v

# Mistral Pixtral 12B - Lightweight
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model mistralai/pixtral-12b -v
```

### Free Models (may have availability issues)

```bash
# Qwen 2.5 VL 72B Free
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model qwen/qwen2.5-vl-72b-instruct:free -v

# Qwen 2.5 VL 32B Free
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model qwen/qwen2.5-vl-32b-instruct:free -v

# Mistral Small Free (tool calling may be unreliable)
uv run fish-scale-agent run IMAGE.tif --provider openrouter --model mistralai/mistral-small-3.1-24b-instruct:free -v
```

## Further Reading

- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Available Models](https://openrouter.ai/docs#models)
- [Pricing Details](https://openrouter.ai/docs#pricing)
- [API Reference](https://openrouter.ai/docs#api-reference)
