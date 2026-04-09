# AG2 Group Chat Demo

This project demonstrates how to build agents with **AG2/AutoGen**, wire tools, and run a **group chat** workflow with role-based collaboration.

## What this demo shows

- Building specialized agents (`Planner`, `Researcher`, `Coder`, `Reviewer`)
- Registering tool functions agents can call
- Running a moderated group chat with a manager
- Producing a final consolidated answer

## Setup

```bash
cd /Users/<user>/Downloads/projects/ag2-groupchat-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with your model provider details.

## Run

```bash
python main.py "Design a production-ready RAG architecture for support knowledge base"
```

If no prompt is passed, a default prompt is used.
