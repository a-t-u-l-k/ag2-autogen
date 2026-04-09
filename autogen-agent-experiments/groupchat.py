from autogen import ConversableAgent, GroupChat, GroupChatManager

config_list = [
    {
        "model": "llama3.2",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    }
]

# Create AI agents
teacher = ConversableAgent(name="teacher", system_message="You suggest lesson topics.")
planner = ConversableAgent(name="planner", system_message="You create lesson plans.")
reviewer = ConversableAgent(name="reviewer", system_message="You review lesson plans.")

# Create GroupChat
groupchat = GroupChat(agents=[teacher, planner, reviewer], speaker_selection_method="auto")

# Create the GroupChatManager, it will manage the conversation and uses an LLM to select the next agent
manager = GroupChatManager(name="manager", groupchat=groupchat, llm_config={"config_list": config_list})

# Start the conversation
teacher.initiate_chat(manager, "Create a lesson on photosynthesis.")
