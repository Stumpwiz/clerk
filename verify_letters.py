import requests
import json
from datetime import date

API_BASE_URL = "http://localhost:8000" # Assuming backend is running locally for test

def test_generate_letter(full_address=True):
    url = f"{API_BASE_URL}/api/letters/generate"
    
    payload = {
        "letter_date": "2026-03-25",
        "recipient": "John and Mary Smith",
        "salutation": "John and Mary",
        "apartment": "123-B",
    }
    
    if full_address:
        payload["street"] = "456 Maple Avenue"
        payload["city_state_zip"] = "Anytown, ST 12345"
        filename_suffix = "full"
    else:
        filename_suffix = "partial"
        
    print(f"Testing letter generation with {filename_suffix} address...")
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"Success! Generated: {result.get('filename')}")
            else:
                print(f"Failed: {result.get('error')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection error: {e}")

def test_generate_letter_with_defaults():
    url = f"{API_BASE_URL}/api/letters/generate"
    
    payload = {
        "letter_date": "2026-03-25",
        "recipient": "Jane Doe",
        "salutation": "Jane",
        "apartment": "456-A",
        # street and city_state_zip omitted
    }
    
    print("Testing letter generation with default address values...")
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"Success! Generated: {result.get('filename')}")
            else:
                print(f"Failed: {result.get('error')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    # Note: This script expects the backend to be running.
    # Since I cannot easily start the backend and keep it running for the script,
    # I will rely on linting and manual code review if I cannot run it.
    # However, I can try to run the backend in background if needed.
    test_generate_letter(full_address=True)
    test_generate_letter(full_address=False)
    test_generate_letter_with_defaults()
