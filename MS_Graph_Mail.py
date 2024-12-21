import authentication, requests
from urllib import parse, request

token = authentication.retrieve_token()
if token:                
    # Microsoft Graph API endpoint for messages
    graph_url = "https://graph.microsoft.com/v1.0/me/messages"
    
    # Parameters to get top 10 messages, ordered by receivedDateTime
    params = {
        "$top": 10,
        "$orderby": "receivedDateTime desc",
        "$select": "subject,receivedDateTime,from"  # Only get these fields
    }
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Make the request
    response = requests.get(graph_url, headers=headers, params=params)
    
    if response.status_code == 200:
        messages = response.json()['value']
        print("\nLast 10 emails:")
        print("-" * 50)
        for msg in messages:
            try:
                print(f"From: {msg['from']['emailAddress']['address']}")
                print(f"Subject: {msg['subject']}")
                print(f"Received: {msg['receivedDateTime']}")
                print("-" * 50)
            except KeyError as e:
                print(f"Error accessing email: {e}")
                print(msg)
                print("-" * 50)
    else:
        print(f"Error accessing emails: {response.status_code}")
        print(response.text)
else:
    print("Failed to acquire token")


def _get_folder_id(folder_name):
    pass

def _get_subfolder(folder_id):
    pass

def _get_inbox_subfolders(folder_id):
    pass

if __name__ == "__main__":
    pass