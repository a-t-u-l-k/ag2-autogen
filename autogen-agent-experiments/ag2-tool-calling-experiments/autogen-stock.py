from autogen import AssistantAgent, UserProxyAgent

# Define the configuration for the Code Llama model
config_list = [
    {
        "model": "codellama:7b-instruct",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
    }
]

# Create an AssistantAgent with the Code Llama model
assistant = AssistantAgent("assistant", llm_config={"config_list": config_list})

# Create a UserProxyAgent that can execute code
user_proxy = UserProxyAgent("user_proxy", code_execution_config={"work_dir": "coding", "use_docker": False})

# Initiate a chat between the user proxy and the assistant
user_proxy.initiate_chat(assistant, message="Plot a chart of TSLA stock price change YTD and save in a file. Get information using yfinance.")
