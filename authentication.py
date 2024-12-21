import msal, webbrowser, urllib.parse, socket, threading, configparser
from http.server import HTTPServer, BaseHTTPRequestHandler

__all__ = ['retrieve_token']

class _AuthorizationCodeHandler(BaseHTTPRequestHandler):
    '''This class handles the authorization code from the redirect URI. It is a simple 
    HTTP request handler that listens for a GET request on the redirect URI. It then 
    extracts the authorization code from the request and stores it in the server's auth_code.'''

    def do_GET(self):
        query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        
        # Black Magic!!! wooooo~ 
        # On a serious note, this allows the server to access the auth_code variable
        self.server.auth_code = query_components.get('code', [None])[0]
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"""
            <html>
                <body style="text-align: center; padding: 20px;">
                    <h3>Authentication successful!</h3>
                    <p>You can close this window now.</p>
                </body>
            </html>
        """)
        threading.Thread(target=self.server.shutdown).start()

    def log_message(self, format, *args):
        # Suppress logging; only interested in the authorization code
        return


def _get_auth_code(app: msal.PublicClientApplication, config:configparser.ConfigParser):
    '''This function retrieves the authorization code from a user login.
       First it gets a free port from the allowed range, then it starts 
       an HTTP server that listens for a GET request on the redirect URI.  
       It then extracts and returns the authorization code from the request.
    '''
    
    # Test and reserve a free port from the allowed range
    port = None
    
    start_port = config['Ports']['start']
    end_port = config['Ports']['end']
    
    if start_port:
        if not isinstance(start_port, int):
            try:
                start_port = int(start_port)
            except ValueError:
                raise ValueError("start_port must be an integer")
    if end_port:
        if not isinstance(end_port, int):
            try:
                end_port = int(end_port)
            except ValueError:
                raise ValueError("end_port must be an integer")
    
    if end_port is None:
        allowed_ports = [start_port]
    else:
        allowed_ports = range(start_port, end_port)

    for _port in allowed_ports:
        try:            
            # Keep the socket open for the duration of the request; 
            # This is to ensure that the server can receive the authorization code

            # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _socket.bind(('localhost', _port))
            port = _port
            break
        except socket.error:
            # Port is already in use; try the next one
            continue
    
    if port is None:
        raise RuntimeError("No free ports available in the allowed range")
      
    # Launch a quick and dirty HTTP server. This will be used to receive the
    # authorization URL from the redirect URI. Otherwise we would need to have
    # the user manually copy and paste the URL into the browser... EWWW!
    redirect_uri_base = config['Redirect URI']['base']
    redirect_uri = f"{redirect_uri_base}:{port}"
    
    host = redirect_uri_base.split('//')[1]
    _socket.close()
    server = HTTPServer((host, port), _AuthorizationCodeHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # # Add claims to force MFA
    # claims = {
    #     "access_token": {
    #         "amr": {
    #             "values": ["mfa"]
    #         }
    #     }
    # }
    
    auth_url = app.get_authorization_request_url(
        scopes=[scope for scope in config['Scopes'].values()],
        redirect_uri=redirect_uri,
        prompt='login'#,  # Force fresh login
        # claims=claims,   # Request MFA
    )
    
    webbrowser.get().open(auth_url, new=1, autoraise=True)
    server.serve_forever()
    return server.auth_code, redirect_uri




# retrieve_token() currently creates a new app instance every time it is called
# therefore the app is not cached and the user is forced to login every time
# TODO: Change this into a class that can be instantiated once and reused

def retrieve_token():
    """This is the main function this script is used for. It retrieves a token from
    Microsoft Graph API using the authorization code after user authentication."""

    # Read the configuration file
    # Azure.cnf contains all information regarding authentication
    # It is used so that this can be configured without changing the code
    config = configparser.ConfigParser()
    config.read('azure.cnf')

    tenant_id = config['Tenant']['id'] 
    client_id = config['Client']['id']

    authority = f'https://login.microsoftonline.com/{tenant_id}'
    scopes = [ scope for scope in config['Scopes'].values() ]

    # Initialize Microsoft Authentication Library (MSAL)
    # This is the client application that will be used to acquire the token
    app = msal.PublicClientApplication(
        client_id,
        authority=authority
    )

    result = None
    token = None

    try:
        accounts = app.get_accounts()

        if accounts:
            # Retrieve token from cache if available
            # Will only work if not expired... should check that down the line
            # The app will most likely need to be kept alive for accounts to be cached
            # Maybe a class should be created to keep the app alive? or 
            # TODO: Check if token is expired and refresh it if necessary
            # TODO: Specify the account to use from the cache
            
            # print(f"Found cached account: {accounts[0]['username']}")
            result = app.acquire_token_silent(scopes, account=accounts[0])
        
        else:
            # ~The Sauce~
            
            # Prompt User login for authentication and retrieve the authorization code
            auth_code , redirect_uri = _get_auth_code(app, config)
            
            if not auth_code:
                raise ValueError("No authorization code received")
            
            # Retrieve token using the authorization code
            result = app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=scopes,
                redirect_uri=redirect_uri
            )

    except Exception as e:
        print(f"An error occurred: {e}")
        
    if result and "access_token" in result:
        token = result['access_token']
        return token
    
    return None