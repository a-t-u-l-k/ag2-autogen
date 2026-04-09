import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv
import autogen


def _llm_config() -> Dict[str, Any]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        auth_file = Path.home() / ".codex" / "auth.json"
        if auth_file.exists():
            try:
                data = json.loads(auth_file.read_text())
                api_key = data.get("OPENAI_API_KEY", "")
            except Exception:
                api_key = ""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return {
        "config_list": [
            {
                "model": model,
                "api_key": api_key,
                "api_type": "openai",
            }
        ],
        "temperature": 0.2,
        "timeout": 120,
    }


def create_agents():
    llm = _llm_config()

    user_proxy = autogen.UserProxyAgent(
        name="UserProxy",
        human_input_mode="NEVER",
        code_execution_config=False,
    )

    planner = autogen.AssistantAgent(
        name="Planner",
        llm_config=llm,
        system_message=(
            "You are a solution planner. Break problems into steps, assign tasks, "
            "and ensure final output is actionable."
        ),
    )

    researcher = autogen.AssistantAgent(
        name="Researcher",
        llm_config=llm,
        system_message=(
            "You are a researcher. Provide concise facts, trade-offs, and references. "
            "Prefer bullet points."
        ),
    )

    coder = autogen.AssistantAgent(
        name="Coder",
        llm_config=llm,
        system_message=(
            "You are a practical engineer. Convert plans into implementation details "
            "and pseudocode/config snippets."
        ),
    )

    reviewer = autogen.AssistantAgent(
        name="Reviewer",
        llm_config=llm,
        system_message=(
            "You are a reviewer. Validate correctness, risk, security, and performance. "
            "End with 'APPROVED' when satisfied."
        ),
    )

    def get_current_time(_: str = "") -> str:
        return datetime.now().isoformat()

    researcher.register_for_llm(name="get_current_time", description="Get current ISO time")(get_current_time)
    user_proxy.register_for_execution(name="get_current_time")(get_current_time)

    groupchat = autogen.GroupChat(
        agents=[user_proxy, planner, researcher, coder, reviewer],
        messages=[],
        max_round=12,
        speaker_selection_method="round_robin",
    )

    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm)
    return user_proxy, manager


def main():
    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Design an enterprise RAG system with indexing, hybrid retrieval, reranking, citations, and eval metrics."
    )

    user_proxy, manager = create_agents()
    user_proxy.initiate_chat(
        manager,
        message=(
            f"Task: {prompt}\n"
            "Collaboration rules:\n"
            "1) Planner defines phases\n"
            "2) Researcher adds evidence\n"
            "3) Coder proposes implementation\n"
            "4) Reviewer validates and signs off with APPROVED"
        ),
    )


if __name__ == "__main__":
    main()
