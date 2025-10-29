import requests
import json

# Replace with your actual API key if required by the API
# The endpoint you provided requires an API key based on the FastAPI code structure
API_KEY = "f87f754c7ccdfb93f5b115ec0d5f4090"  # <-- !! CHANGE THIS !!
API_URL = "https://cronapi.cronbid.com/campaigns/get_campaigns/"

def check_null_targeting():
    """
    Calls the get_campaigns API and checks if the 'targeting' key 
    in any campaign object is explicitly null (or not present).
    """
    
    # Headers must include the authorization check
    headers = {
        "x-api-key": API_KEY,
        "Accept": "application/json"
    }

    print(f"Testing API endpoint: {API_URL}")
    print("-" * 40)

    try:
        response = requests.get(API_URL, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        data = response.json()
        campaigns = data.get('campaigns', [])
        
        if not campaigns:
            print("✅ API returned successfully, but the 'campaigns' list is empty. Cannot verify targeting data.")
            return

        null_targeting_found = False
        
        for campaign in campaigns:
            campaign_id = campaign.get("campaign_id", "N/A")
            
            # 1. Check if the 'targeting' key is missing or explicitly None
            if 'targeting' not in campaign or campaign['targeting'] is None:
                print(f"❌ ERROR: Campaign {campaign_id} is missing the 'targeting' key or its value is null (None).")
                null_targeting_found = True
                continue
                
            targeting_data_str = campaign['targeting']
            
            # 2. Check if the JSON string itself is "null" (which sometimes happens)
            if targeting_data_str.lower().strip() == 'null':
                 print(f"❌ ERROR: Campaign {campaign_id} has 'targeting' set to the string 'null'.")
                 null_targeting_found = True
                 continue

            # 3. Check the content after your script's processing
            # Your script ensures it's a JSON array string. Let's check its decoded content.
            try:
                # Decode the JSON string content of the 'targeting' key
                decoded_targeting = json.loads(targeting_data_str)
                
                # Check if the list itself is empty (it should not be due to your DEFAULT_TARGETING fix)
                if not decoded_targeting:
                    print(f"❌ ERROR: Campaign {campaign_id} has an empty 'targeting' array: {targeting_data_str}")
                    null_targeting_found = True
                    continue
                    
            except json.JSONDecodeError:
                print(f"❌ ERROR: Campaign {campaign_id} has invalid JSON content in 'targeting': {targeting_data_str}")
                null_targeting_found = True
                continue


        if not null_targeting_found:
            print("✅ SUCCESS: No campaign was found where the 'targeting' key was null (None) or invalid.")
            
    except requests.exceptions.RequestException as e:
        print(f"🔥 An error occurred while calling the API: {e}")
    except Exception as e:
        print(f"🔥 An unexpected error occurred: {e}")

if __name__ == "__main__":
    check_null_targeting()