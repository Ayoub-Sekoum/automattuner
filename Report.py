import json
import os
import urllib.request
import urllib.parse
import urllib.error
from colorama import Fore, init

init(autoreset=True)

def load_config(config_file="config.json"):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        error_msg("Error loading configuration from config.json", e)
        return None

def get_access_token(config):
    try:
        url = f"https://login.microsoftonline.com/{config['intune_tenant_id']}/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'client_id': config['intune_client_id'],
            'client_secret': config['intune_client_secret'],
            'scope': 'https://graph.microsoft.com/.default'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('access_token')
    except urllib.error.HTTPError as e:
        error_msg("Error requesting token", e)
        return None
    except Exception as e:
        error_msg("Unexpected authentication error", e)
        return None

def get_intune_apps(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "ConsistencyLevel": "eventual"
    }
    uri = "https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps"
    all_apps = []
    while uri:
        try:
            req = urllib.request.Request(uri, headers=headers)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                all_apps.extend(data.get('value', []))
                uri = data.get('@odata.nextLink')
        except urllib.error.HTTPError as e:
            error_msg("Error fetching apps from Intune", e)
            break
    return all_apps

def determine_platform(odata_type):
    if "win32LobApp" in odata_type:
        return "Windows"
    elif "iosVppApp" in odata_type:
        return "iOS"
    elif "android" in odata_type:
        return "Android"
    else:
        return "Not specified"

def generate_report(apps):
    if not apps:
        print(f"{Fore.YELLOW}⚠️ No apps found.")
        return

    # Define column widths
    col_widths = {
        "Name": 32,
        "Platform": 12,
        "Version": 10,
        "VPP Token Name": 17,
        "Assigned": 10,
        "Developer": 24
    }
    # Create the border line
    border_line = "+" + "+".join(["-" * (width + 2) for width in col_widths.values()]) + "+"

    # Print header
    print(Fore.CYAN + "App Report:")
    print(border_line)
    header = "|"
    for col, width in col_widths.items():
        header += " " + f"{col:<{width}}" + " |"
    print(header)
    print(border_line)

    # Print each row
    for app in apps:
        name = app.get('displayName', 'N/A')
        platform = determine_platform(app.get('@odata.type', ''))
        version = app.get('displayVersion', 'N/A') or app.get('committedContentVersion', 'N/A') or app.get('appVersion', 'N/A')
        vpp_token_name = app.get('vppTokenName', 'N/A') if platform == "iOS" else 'N/A'
        assigned = 'Yes' if app.get('isAssigned') else 'No'
        developer = app.get('publisher', 'N/A')

        row = (
            f"| {name:<{col_widths['Name']}} | "
            f"{platform:<{col_widths['Platform']}} | "
            f"{version:<{col_widths['Version']}} | "
            f"{vpp_token_name:<{col_widths['VPP Token Name']}} | "
            f"{assigned:<{col_widths['Assigned']}} | "
            f"{developer:<{col_widths['Developer']}} |"
        )
        print(row)
        print(border_line)

def error_msg(step, error):
    print(f"\n{Fore.RED}❌ Error during {step}: {error}")

def main():
    print(f"{Fore.CYAN}Initializing...")
    config = load_config()
    if not config:
        return

    print(f"{Fore.BLUE}Authenticating...")
    token = get_access_token(config)
    if not token:
        return

    print(f"{Fore.CYAN}Retrieving app information from Intune...")
    apps = get_intune_apps(token)
    generate_report(apps)

if __name__ == "__main__":
    main()
