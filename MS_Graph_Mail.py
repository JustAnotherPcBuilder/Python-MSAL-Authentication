import authentication, json, configparser, os.path
import urllib.request, urllib.parse, urllib.error
from datetime import datetime

def get_messages(folder_paths = None, params = None):
    """Grabs messages from the Microsoft Graph API. It will take 
    the folder paths is the format this/is/path1;this/is/path2 and
    find the folder ids asscociated with the paths to grab the messages
    from the folders according to the params. If no params are provided,
    it will grab all messages in the folders from today."""
    
    headers = authentication.get_headers()
    
    if not folder_paths:
        folder_paths = 'inbox'
    
    folder_ids = _get_folder_ids(folder_paths, headers=headers)

    head = "https://graph.microsoft.com/v1.0/me/mailFolders"
    tail = "messages"
    
    if not params:
        today = datetime.now().strftime("%Y-%m-%dT00:00:00Z")
        params = { 
            "$select": "from,subject,body",
            "$filter": f"receivedDateTime ge {today}"
        }
    
    messages = []
    
    for folder in folder_ids.keys():
        id = folder_ids.get(folder)
        endpoint = f"{head}/{id}/{tail}"
        
        response = get_request(endpoint, params, headers)
        data = response.get('value')
        messages.extend(
            {   'subject' : message['subject'], 
                'body'    : message['body']['content']   } 
                    for message in data)
        
    return messages
    
def get_request(endpoint, params = None, headers = None):
    """Request function using built-in urllib. This function is 
    written to avoid having to install unnecessary libraries like 
    requests for simple GET requests. The inputs and outputs are
    similar to the requests.get function from the requests library."""
    
    if params:
        if not isinstance(params, dict):
            raise TypeError("Params must be a dictionary")
        query = urllib.parse.urlencode(params)
        url = f'{endpoint}?{query}'    
    else:    
        url = endpoint
    
    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request) as response:
        try:
            if response.status == 200:
                try:
                    data = json.loads(response.read().decode())
                except json.JSONDecodeError as e:
                    print(f"JSON Decode Error: {e.msg}")
                    data = None
            else:
                print(f"Error accessing emails: {response.status_code}")
                print(response.read().decode())
        
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            print(e.read().decode())
            data = None
        
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            print(e.read().decode())
            data = None
    
    return data

def _get_folder_ids(folder_paths, headers = None):
    
    if folder_paths is None:
        return {'inbox' : 'inbox'}
    
    if isinstance(folder_paths, str):
        if folder_paths.strip().lower() == 'inbox':
            return {'inbox' : 'inbox'}
    
    if not headers:
        headers = authentication.get_headers()
    
    config_ids = _load_folder_ids_from_config(headers)
    
    if config_ids:
        print("Loaded Folder ID's from config file")
    
    folder_ids = config_ids

    if not folder_ids:
        print("Loading Folder IDs from Microsoft Graph")
        folder_ids = {'inbox' : 'inbox'}
        main_folders = []
        for path in folder_paths.split(';'):
            if path.lower() == 'inbox':
                main_folders.append('inbox')
                continue
            main_folders.append(os.path.basename(path))
            folders = path.split('/')
            _iterate_folders(folders, folder_ids, None, headers)

        folder_ids = { folder : folder_ids[folder] for folder in main_folders }

        update_config_folder_ids(folder_ids)

    return folder_ids

def _iterate_folders(folders, folder_ids, current_id, headers):
    """Iterate through the folder in the path. Finds the folder id by getting 
    the child folders of the current folder and checking if the next folder in"""
    
    if not folders or not isinstance(folders, list):
        return None
    
    current_folder = folders[0]

    # Don't need to find the folder id if it is already in the folder_ids dictionary
    if current_folder in folder_ids.keys():
        return _iterate_folders(folders[1:], folder_ids, folder_ids.get(current_folder) , headers)

    # Find the folder id if it is not in the folder_ids dictionary
    url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{current_id}/childFolders"
    if not current_id:
        url = f"https://graph.microsoft.com/v1.0/me/mailFolders"
    data = get_request(url, headers = headers)
    if not data:
        print(f"Failed to get child folders of {current_id}")
        return None
    child_folders = data['value']
    
    print(f"Checking {current_folder}'s children")
    for child in child_folders:
        print(f"Found: {child['displayName']}")    
        if child['displayName'].upper() == current_folder.upper():
            folder_ids[current_folder] = child['id']
            break
    if not folder_ids.get(current_folder):
        print(f"Failed to find {current_folder}")
        return None
    
    return _iterate_folders(folders[1:], folder_ids, folder_ids.get(current_folder), headers)

def _load_folder_ids_from_config(headers):
    """Loads the folder ids from the config file if they exist and
    verifies them with the Microsoft Graph API."""

    config = configparser.ConfigParser()
    config.read('azure.cnf')
    
    if not config.has_section('Folder IDs'):
        return None
    
    folder_ids = { option: config.get('Folder IDs', option) for 
                        option in config.options('Folder IDs') }
    folder_ids = _verify_folder_ids(folder_ids, headers)
    return folder_ids

def _verify_folder_ids(folder_ids, headers):
    print('Verifying Folder IDs')
    graph_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
    for folder in folder_ids.keys():
        url = f"{graph_url}/{folder_ids[folder]}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                if response.status != 200:
                    print(f"Error accessing folder {folder}")
                    print("Refreshing Folder IDs")
                    return None
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            print(e.read().decode())
            return None
        except urllib.error.URLError as e:
            print(f"URL Error: {e.reason}")
            print(e.read().decode())
            return None
        
    return folder_ids

def update_config_folder_ids(folder_ids):
    print('Adding Folder IDs to config file')
    config = configparser.ConfigParser()
    config.read('azure.cnf')
    if not config.has_section('Folder IDs'):
        config.add_section('Folder IDs')
    
    for folder in folder_ids.keys():
        config.set('Folder IDs', folder, folder_ids[folder])
    
    with open('azure.cnf', 'w') as f:
        config.write(f)
    

if __name__ == "__main__":
    from pprint import pprint
    folder_paths = 'Inbox/Logger/Device;Inbox/Logger/Test;Inbox/Logger/Normal'
    # messages = get_messages(folder_paths)
    # # pprint(messages)
    authentication.load_token_data()