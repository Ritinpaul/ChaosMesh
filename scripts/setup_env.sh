#!/usr/bin/env bash
# ChaosMesh Arena — Env Setup (Task 3.7)

set -euo pipefail

ENV_FILE="../.env"
EXAMPLE_FILE="../.env.example"

# Run from scripts directory
cd "$(dirname "$0")"

echo "==============================================="
echo "⚡ ChaosMesh Arena: Environment Setup"
echo "==============================================="

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "Error: .env.example not found. Are you missing project files?"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Copying .env.example to .env..."
    cp "$EXAMPLE_FILE" "$ENV_FILE"
else
    echo ".env file already exists."
fi

# Prompt for OpenRouter Key
read -p "Enter your OpenRouter API Key (sk-or-v1-...): " OR_KEY

if [ -n "$OR_KEY" ]; then
    # Replace the stub in .env
    if grep -q "OPENROUTER_API_KEY=" "$ENV_FILE"; then
        # Using sed to replace the line
        sed -i.bak "s/^OPENROUTER_API_KEY=.*/OPENROUTER_API_KEY=${OR_KEY}/g" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
        echo "✅ OpenRouter API Key configured."
    else
        echo "OPENROUTER_API_KEY=${OR_KEY}" >> "$ENV_FILE"
        echo "✅ OpenRouter API Key appended."
    fi
else
    echo "⚠️ No key provided. OpenRouter fallback will be disabled."
fi

echo "Configuration complete. Review your .env file to customize other settings (like OLLAMA models or SERVER port)."
