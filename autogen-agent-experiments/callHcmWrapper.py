# debug_api.py - A simple script to test the API connection directly
import requests
import base64
import json
import urllib3

# Disable SSL warnings for testing
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API settings
API_URL = "https://example.com/completions"
USERNAME = "<set-api-username>"
PASSWORD = ""

def test_api_connection():
    print(f"Testing connection to: {API_URL}")
    
    # Prepare credentials
    credentials = f"{USERNAME}:{PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    auth_header = f"Basic {encoded_credentials}"
    
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Test payload
    payload = {
        "prompt": "Hello, how are you?"
    }
    
    try:
        # Make the request with SSL verification disabled for testing
        response = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            verify=False,
            timeout=30
        )
        
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Response JSON: {json.dumps(result, indent=2)}")
                
                if "choices" in result and len(result["choices"]) > 0:
                    print(f"Extracted text: {result['choices'][0]['text']}")
                else:
                    print("Error: Response format doesn't match expected structure")
            except json.JSONDecodeError:
                print(f"Error: Response is not valid JSON: {response.text}")
        else:
            print(f"Error response: {response.text}")
    
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {str(e)}")
    except requests.exceptions.Timeout as e:
        print(f"Timeout error: {str(e)}")
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    test_api_connection()
