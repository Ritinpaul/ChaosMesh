---
title: ChaosMesh Arena
emoji: ⚡
colorFrom: indigo
colorTo: slate
sdk: docker
app_port: 8000
pinned: false
---

# ChaosMesh Arena - Hugging Face Space

This directory provides the configuration to run ChaosMesh Arena on Hugging Face Spaces using the Docker SDK.

The `README.md` metadata header tells HF Spaces to build the container using the root `Dockerfile` and expose port `8000`.

## Deployment Instructions (Task 3.10)

1. Create a new Space on [Hugging Face](https://huggingface.co/new-space).
2. Choose **Docker** as the Space SDK.
3. Choose **Blank** Docker template.
4. Clone your Space repository locally.
5. Copy the entire contents of the `chaosmesh-arena` directory into the Space repository.
6. Copy this `README.md` to overwrite the default `README.md` in the Space repository root.
7. Commit and push:
   ```bash
   git add .
   git commit -m "Deploy ChaosMesh Arena"
   git push
   ```

## Secrets configuration

To use OpenRouter fallback, go to your Space **Settings** -> **Variables and secrets** and add a secret:
- `OPENROUTER_API_KEY`: `sk-or-...`
- `CHAOSMESH_API_KEY`: Your custom auth key.

The Dockerfile is already configured to mount volumes for ChromaDB and SQLite internally, but note that HF Spaces are ephemeral by default. If you need persistent memory across restarts, consider mounting a Persistent Storage volume via the Space settings to `/app/data`.
