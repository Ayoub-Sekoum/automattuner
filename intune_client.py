import json
import urllib.request
import urllib.parse
import urllib.error
import logging

# Logger for this module
# The actual handler/formatter configuration will be done by the calling script (publish_installer.py or Report.py)
logger = logging.getLogger(__name__)

def get_access_token(tenant_id, client_id, client_secret):
    """Get access token for Microsoft Graph API using client credentials."""
    logger.info(f"Attempting to retrieve Microsoft Graph API access token for tenant: {tenant_id[:7]}... (intune_client)")
    # This log message uses the logger from intune_client.py

    if not all([tenant_id, client_id, client_secret]):
        logger.error("Tenant ID, Client ID, or Client Secret is missing. Cannot get token. (intune_client)")
        # No direct console print here, relies on calling script's error handling for console
        return None

    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        url = f"{authority}/oauth2/v2.0/token"
        logger.debug(f"Token request URL: {url} (intune_client)")
        
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret, 
            'scope': 'https://graph.microsoft.com/.default'
        }
        data = urllib.parse.urlencode(payload).encode('utf-8')
        # logger.debug(f"Token request data (excluding client_secret for safety): grant_type={payload['grant_type']}, client_id={payload['client_id']}, scope={payload['scope']} (intune_client)")

        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method='POST')

        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode('utf-8')
            if response.status == 200:
                result = json.loads(response_body)
                if "access_token" in result:
                    logger.info("Successfully retrieved access token. (intune_client)")
                    return result['access_token']
                else:
                    error_description = result.get("error_description", "No error description provided.")
                    logger.error(f"MSAL Authentication Error (Token not found in response): {error_description}. Response: {response_body} (intune_client)")
                    return None
            else:
                logger.error(f"MSAL Authentication Error. HTTP Status: {response.status}. Response Body: {response_body} (intune_client)")
                return None

    except urllib.error.HTTPError as e:
        error_body = "N/A"
        try:
            error_body = e.read().decode('utf-8', errors='replace')
        except Exception as read_err:
            logger.warning(f"Could not read error body from HTTPError {e.code} response: {read_err} (intune_client)")
        logger.error(f"MSAL Authentication HTTPError {e.code} ({e.reason}). Response Body: {error_body} (intune_client)", exc_info=True)
        return None
    except urllib.error.URLError as e:
        logger.error(f"MSAL Authentication Network Error: {e.reason} (intune_client)", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"MSAL Authentication Exception: {str(e)} (intune_client)", exc_info=True)
        return None

def get_intune_apps(token, package_id_filter=None):
    """
    Retrieves Intune apps using Microsoft Graph API, optionally filters by display name containing package_id_filter.
    (Copied from publish_installer.py and adapted for intune_client.py)
    """
    logger.info(f"Fetching Intune apps. Filter: '{package_id_filter or 'None'}' (intune_client)")
    headers = {
        "Authorization": f"Bearer {token}", # Token itself is not logged for security
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ConsistencyLevel": "eventual" 
    }
    base_uri = "https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps"
    params = {'$top': '999'} 
    if package_id_filter:
        params['$filter'] = f"contains(tolower(displayName), '{package_id_filter.lower()}')"
        params['$count'] = 'true'

    uri = base_uri + "?" + urllib.parse.urlencode(params)
    logger.debug(f"Initial URI for fetching Intune apps: {uri} (intune_client)")

    all_apps = []
    page_num = 1
    while uri:
        logger.debug(f"Fetching page {page_num} from URI: {uri} (intune_client)")
        # The calling script (publish_installer.py / Report.py) will print progress dots if desired
        try:
            req = urllib.request.Request(uri, headers=headers, method='GET')
            with urllib.request.urlopen(req, timeout=45) as response:
                if response.status != 200:
                    error_body = "N/A"
                    try:
                        error_body = response.read().decode('utf-8', errors='replace')
                    except Exception as read_err:
                        logger.warning(f"Could not read error body from HTTP {response.status} response: {read_err} (intune_client)")
                    logger.error(f"Error fetching apps from Intune. HTTP Status: {response.status}, URI: {uri}, Body: {error_body} (intune_client)")
                    # The calling script will handle user-facing error messages
                    return None 
                data = json.loads(response.read().decode('utf-8'))
                apps_on_page = data.get('value', [])
                logger.debug(f"Page {page_num}: Fetched {len(apps_on_page)} app(s). (intune_client)")
                all_apps.extend(apps_on_page)
                uri = data.get('@odata.nextLink')
                if uri:
                    logger.debug(f"Next page URI: {uri} (intune_client)")
                page_num += 1
        except urllib.error.HTTPError as e:
            error_body = "N/A"
            try:
                error_body = e.read().decode('utf-8', errors='replace')
            except Exception as read_err:
                logger.warning(f"Could not read error body from HTTPError {e.code} response: {read_err} (intune_client)")
            logger.error(f"HTTPError {e.code} ({e.reason}) fetching apps from Intune. URI: {repr(uri)}, Response: {error_body} (intune_client)", exc_info=True)
            return None 
        except Exception as e:
            logger.error(f"Unexpected error fetching apps. URI: {repr(uri)} (intune_client)", exc_info=True)
            return None

    logger.info(f"Finished fetching apps. Total found: {len(all_apps)}. (intune_client)")
    return all_apps

def determine_platform(odata_type):
    """
    Determine app platform based on @odata.type.
    (Copied from publish_installer.py)
    """
    # This function does not require logging from intune_client's logger itself,
    # as it's a simple utility. Logging around its usage can be done by the caller.
    odata_type = odata_type.lower() 
    if not odata_type: return "Unknown Type"
    if "win32lobapp" in odata_type: return "Windows"
    if "windowsuniversalappx" in odata_type: return "Windows UWP"
    if "microsoftstoreforbusinessapp" in odata_type: return "Win Store"
    if "managedandroidlobapp" in odata_type: return "Android LOB"
    if "androidstoreapp" in odata_type: return "Android Store"
    if "ioslobapp" in odata_type: return "iOS LOB"
    if "iosvppapp" in odata_type: return "iOS VPP"
    if "macoslobapp" in odata_type: return "macOS LOB"
    if "macosdmgapp" in odata_type: return "macOS DMG"
    if "microsoftedge" in odata_type: return "Edge" 
    if "webapp" in odata_type: return "Web App" 
    
    simple_type = odata_type.split('.')[-1]
    return simple_type.replace('app', '').capitalize() or "Other"
