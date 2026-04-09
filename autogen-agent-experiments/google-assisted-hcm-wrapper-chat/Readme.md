# Install dependencies
pip install fastapi uvicorn websockets autogen httpx

# Run the server
uvicorn app:app --host 0.0.0.0 --port 8000
