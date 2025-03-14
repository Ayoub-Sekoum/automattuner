
## **⚠️ BETA SOFTWARE - VERSION 0.0.3.1 ⚠️**
##
## This script is currently in BETA. Use with caution and at your own risk.
## Expect potential issues and instability.
##
## **Created by Sekoum Ayoub**
##
## **Open Source License:**
##
## This script is released under an Open Source license (Specify License Name here, e.g., MIT License, Apache 2.0).
## You are free to use, modify, and distribute it according to the terms of the license.
## See the LICENSE file for full details.
##
## **Disclaimer:**
##
## The author(s) are not responsible for any issues or damages caused by the use of this script.
## Always test in a non-production environment first and ensure you understand the script's functionality
## before using it in a live environment.
## # Intune App Packager and Publisher Script
##
## This Python script automates the process of packaging and publishing applications to Microsoft Intune using `wintuner`. It simplifies the workflow by providing an interactive command-line interface to package applications, check for existing apps in Intune, and publish new packages.
##  **Wintuner:**  `wintuner` must be installed and accessible in your system's PATH. Follow the installation instructions provided in the [Wintuner documentation]([Wintuner documentation link here if available, otherwise provide general instructions on where to get it]).
##
##   **Microsoft Azure Application Registration:** You need to register an application in Azure Active Directory to authenticate with the Microsoft Graph API. This application will require the following:
##     *   **Application (client) ID:**  You will need to copy this value from your Azure app registration.
##     *   **Client Secret:** Generate a client secret for your application registration and keep it secure.
##     *   **Directory (tenant) ID:**  You will need your Azure tenant ID.
##
## 5.  **`config.json` file:**  A `config.json` file is required in the same directory as the script to store configuration settings. See the [Configuration](#configuration-configjson) section for details on how to create this file.
##
## ## Installation
##
## .  **Download the scripts:** Download the `publish_installer.py` and `install_requirements.py` scripts to your desired directory.
##
##
##     ```bash
##     python install_requirements.py
##     ```
##
##     This script will check for and install the required libraries automatically.
##
## ## Configuration (`config.json`)
##
## Create a file named `config.json` in the same directory as `publish_installer.py`.  This file should contain your Intune and `wintuner` configuration settings in JSON format. Here's an example `config.json` structure:
##
## ```json
## {
##   "intune_tenant_id": "YOUR_TENANT_ID",
##   "intune_client_id": "YOUR_CLIENT_ID",
##   "intune_client_secret": "YOUR_CLIENT_SECRET",
##   "wintuner_download_dir": "wintuner_downloads",
##   "temp_package_dir": "temp_packages"
## }
## ```
## **Configuration parameters:**
##     *   **App ID:** Enter the App ID for the application you want to package and publish. For example, `Notepad++.Notepad++`.  **Note:** The script will process the App ID to use only
import json
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
from colorama import Fore, Style, init
from alive_progress import alive_bar

init(autoreset=True)

###############################################################################
## Configuration Loading
###############################################################################
def load_config(config_file="config.json"):
    """Load configurations from a JSON file in the same directory as the script."""
    try:
        script_directory = Path(__file__).resolve().parent
        config_path = script_directory / config_file
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        Path(config['wintuner_download_dir']).mkdir(parents=True, exist_ok=True)
        Path(config.get('temp_package_dir', 'temp_packages')).mkdir(parents=True, exist_ok=True)
        return config
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        error_msg(f"Error loading configuration from {config_path}", str(e))
        return None

###############################################################################
## STEP 5: Intune App Check (Report Based)
###############################################################################
def check_intune_app_report_based(package_id, config):
    """Check if the app exists in Intune by comparing against a generated report."""
    print(f"{Fore.CYAN}Checking Intune for '{package_id}' using Intune App Report...")

    # Process package_id to get only the part before the first dot (if any)
    processed_package_id = package_id
    if "." in processed_package_id:
        processed_package_id = processed_package_id.split(".")[0]

    report_output = generate_intune_app_report(config, package_id=processed_package_id) # Pass processed_package_id

    if not report_output:
        print(f"{Fore.YELLOW}⚠️ Could not retrieve Intune App Report to check for existing apps.")
        return False  # Indicate check failure, not necessarily app existence

    app_found = False
    for app_info in report_output[1:]:  # Skip header row
        display_name = app_info.get('displayName', 'N/A')
        # Process display name to get only the first part (already done in report generation)
        if "." in display_name:
            display_name = display_name.split(".")[0]

        if processed_package_id.lower() in display_name.lower():  # Compare processed package_id with processed display_name
            original_display_name = app_info.get('originalDisplayName', 'Unknown App') # Use originalDisplayName for message
            print(Fore.YELLOW + f"- App '{original_display_name}' (ID: {app_info.get('id', 'N/A')}, Version: {app_info.get('displayVersion', 'N/A')}) found in Intune.")
            app_found = True
            break # Stop after finding the first match, assuming we are checking for existence

    if app_found:
        return True
    else:
        print(Fore.GREEN + f"No app with name containing '{package_id}' found in Intune based on the report.") # Use original package_id in message
        return False

###############################################################################
## STEP 9: Intune App Report Generation (Integrated and Modified)
###############################################################################
def get_intune_apps(token, package_id_filter=None):
    """Retrieves Intune apps using Microsoft Graph API, optionally filters by package_id."""
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
                apps = data.get('value', [])
                if package_id_filter:
                    apps = [app for app in apps if package_id_filter.lower() in app.get('displayName', '').lower()] # Filter here using processed package_id
                all_apps.extend(apps)
                uri = data.get('@odata.nextLink')
        except urllib.error.HTTPError as e:
            error_msg("Error fetching apps from Intune", e)
            break
        except Exception as e:
            error_msg("Unexpected error fetching apps", e)
            break
    return all_apps

def generate_report_output(apps):
    """Generates a formatted report of Intune apps and returns it as a string list and prints to console."""
    if not apps:
        print(f"{Fore.YELLOW}No apps found for the report.")
        return [], []

    report_output_list = []
    console_report_lines = []

    col_widths = {
        "Name": 32,
        "Platform": 12,
        "Version": 10,
        "VPP Token Name": 17,
        "Assigned": 10,
        "Developer": 24
    }
    border_line = "+" + "+".join(["-" * (width + 2) for width in col_widths.values()]) + "+"

    console_report_lines.append(Fore.CYAN + "App Report:")
    console_report_lines.append(border_line)
    header = "|"
    header_dict = {}
    for col, width in col_widths.items():
        header += " " + f"{col:<{width}}" + " |"
        header_dict[col] = col
    console_report_lines.append(header)
    console_report_lines.append(border_line)
    report_output_list.append(header_dict)

    for app in apps:
        name = app.get('displayName', 'N/A')
        original_name = name # Store original name before processing
        # Process display name to get only the first part
        if "." in name:
            name = name.split(".")[0]

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
        console_report_lines.append(row)
        console_report_lines.append(border_line)

        app_info = {
            "displayName": name, # Store processed name in report output too if needed, otherwise keep original in report_output_list
            "originalDisplayName": original_name, # Keep the original full name
            "platform": platform,
            "displayVersion": version,
            "vppTokenName": vpp_token_name,
            "isAssigned": assigned,
            "publisher": developer,
            "id": app.get('id', 'N/A')
        }
        report_output_list.append(app_info)

    for line in console_report_lines:
        print(line)

    return report_output_list, console_report_lines

def determine_platform(odata_type):
    """Determine app platform based on @odata.type."""
    if "win32LobApp" in odata_type:
        return "Windows"
    elif "iosVppApp" in odata_type:
        return "iOS"
    elif "android" in odata_type:
        return "Android"
    else:
        return "Not specified"

def generate_intune_app_report(config, package_id=None):
    """Generates an Intune app report using Graph API, optionally filtered by package_id, and returns report data."""

    # Process package_id for filtering in get_intune_apps
    processed_package_id_filter = None
    if package_id:
        processed_package_id_filter = package_id
        if "." in processed_package_id_filter:
            processed_package_id_filter = processed_package_id_filter.split(".")[0]

    print(f"{Fore.CYAN}Generating Intune app report...")
    token = get_access_token(config)
    if not token:
        print(f"{Fore.YELLOW}⚠️ Failed to retrieve access token for report generation.")
        return None

    apps = get_intune_apps(token, package_id_filter=processed_package_id_filter) # Use processed filter
    if apps is None:
        return None

    if package_id: # Use original package_id for messages to user
        if not apps:
            print(f"{Fore.YELLOW}No apps found in Intune matching '{package_id}'.")
        else:
             print(f"{Fore.GREEN}✅ Intune app report generated for '{package_id}'. Showing matching apps:")
             generate_report_output(apps) # Directly print report if package_id is given
    else:
        print(f"{Fore.GREEN}✅ Full Intune app report generated.")
        generate_report_output(apps) # Directly print full report

    return generate_report_output(apps)[0] # Return report data even if printed already

###############################################################################
## STEP 6: Microsoft Graph API Access Token Retrieval
###############################################################################
def get_access_token(config):
    """Get access token for Microsoft Graph API using client credentials via urllib."""
    try:
        authority = f"https://login.microsoftonline.com/{config['intune_tenant_id']}"
        url = f"{authority}/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'client_id': config['intune_client_id'],
            'client_secret': config['intune_client_secret'],
            'scope': 'https://graph.microsoft.com/.default'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if "access_token" in result:
                return result['access_token']
            else:
                error_msg("MSAL Authentication Error", result.get("error_description"))
                return None
    except urllib.error.HTTPError as e:
        error_msg("MSAL Authentication Error", str(e))
        return None
    except Exception as e:
        error_msg("MSAL Authentication Exception", str(e))
        return None

###############################################################################
## STEP 4: Local Package Check
###############################################################################
def check_local_package(package_id, version, config):
    """Check if a local package directory exists."""
    package_path = Path(config['wintuner_download_dir']) / package_id / (version or 'latest')
    return package_path.is_dir()

###############################################################################
## STEP 7: Command Execution with Alive-Progress Bar
###############################################################################
def run_command_with_progress(cmd, description):
    """Execute a command with alive-progress bar."""
    try:
        print(f"{Fore.CYAN}🚀 {description}...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        with alive_bar(total=None, title=f"{Fore.YELLOW}{description}", theme='smooth') as bar:
            while process.poll() is None:
                time.sleep(0.1)
                bar()

        stdout, stderr = process.communicate()
        if process.returncode != 0:
            error_msg(f"Error during {description}", stderr)
            return False
        print(f"{Fore.GREEN}✅ {description} completed.")
        return True
    except FileNotFoundError as e:
        error_msg(f"Error: Command not found during {description}", str(e))
        return False
    except Exception as e:
        error_msg(f"An unexpected error occurred during {description}", str(e))
        return False

###############################################################################
## STEP 8: Error Message Handling
###############################################################################
def error_msg(step, error):
    """Print a formatted error message."""
    print(f"\n{Fore.RED}❌ Error during {step}:")
    print(Fore.YELLOW + str(error))

###############################################################################
## STEP 10: Main Application Logic
###############################################################################
def main():
    """Main function to drive the Intune app packaging and publishing process."""
    print(f"{Fore.CYAN}{Style.BRIGHT}🚀 Intune App Packager and Publisher 🚀{Style.RESET_ALL}")

    config = load_config()
    if not config:
        return

    while True:
        print(f"\n{Fore.GREEN}🆔 Enter App ID: ", end="")
        package_id = input().strip()
        if not package_id:
            print(f"{Fore.RED}App ID cannot be empty.")
            continue

        print(f"\n{Fore.GREEN}📦 Enter Version (leave empty for latest): ", end="")
        version = input().strip()

        architecture_options = {"1": 'x64', "2": 'x86', "3": 'arm64'}
        default_architecture = "1"
        print(f"\n{Fore.CYAN}⚙️ Architecture Options:")
        for value in architecture_options.values():
            print(f"{Fore.YELLOW}{value}{' (default)' if value == architecture_options[default_architecture] else ''}")
        architecture_choice = input(f"{Fore.GREEN}👉 Choose [{'/'.join(architecture_options.keys())}] or ENTER for default: ").strip()
        architecture = architecture_options.get(architecture_choice, architecture_options.get(default_architecture))

        installer_context_options = {"1": 'user', "2": 'system'}
        default_installer_context = "2"
        print(f"\n{Fore.CYAN}⚙️ Installation Context:")
        for value in installer_context_options.values():
            print(f"{Fore.YELLOW}{value}{' (default)' if value == installer_context_options[default_installer_context] else ''}")
        installer_context_choice = input(f"{Fore.GREEN}👉 Choose [{'/'.join(installer_context_options.keys())}] or ENTER for default: ").strip()
        installer_context = installer_context_options.get(installer_context_choice, installer_context_options.get(default_installer_context))

        local_package_exists = check_local_package(package_id, version, config)
        if local_package_exists:
            print(f"{Fore.YELLOW}📦 Local package found for {package_id} version {version or 'latest'}.")
        else:
            print(f"{Fore.CYAN}📦 Creating package for {package_id} version {version or 'latest'}")
            package_cmd = [
                "wintuner", "package", package_id,
                "--package-folder", config['wintuner_download_dir'],
                "--architecture", architecture,
                "--installer-context", installer_context
            ]
            if version:
                package_cmd.extend(["--version", version])

            if run_command_with_progress(package_cmd, f"Packaging {package_id} version {version or 'latest'}"):
                print(f"{Fore.GREEN}✅ Package created in {Path(config['wintuner_download_dir']) / package_id / (version or 'latest')}")
            else:
                continue

        intune_check = input(f"\n{Fore.YELLOW}Check if '{package_id}' is already published on Intune? (y/n): ").strip().lower()
        app_exists_in_intune = False
        if intune_check == 'y':
            app_exists_in_intune = check_intune_app_report_based(package_id, config)
            if app_exists_in_intune:
                publish_choice = input(f"{Fore.YELLOW}App(s) with name containing '{package_id}' found in Intune. Do you still want to try publishing? (y/n): ").strip().lower()
                if publish_choice != 'y':
                    continue

        publish_app = input(f"\n{Fore.YELLOW}Do you want to publish the packaged app '{package_id}' to Intune? (y/n): ").strip().lower()
        if publish_app == 'y':
            token = get_access_token(config)
            if not token:
                print(f"{Fore.RED}Failed to obtain access token. Cannot publish to Intune.")
                continue

            print(f"{Fore.CYAN}🚀 Publishing {package_id} version {version or 'latest'} to Intune")
            publish_cmd = [
                "wintuner", "publish", package_id,
                "--package-folder", config['wintuner_download_dir'],
                "--tenant", config['intune_tenant_id'],
                "--token", token
            ]
            if version:
                publish_cmd.extend(["--version", version])

            if run_command_with_progress(publish_cmd, f"Publishing {package_id} version {version or 'latest'} to Intune"):
                print(f"{Fore.GREEN}🎉 Successfully published {package_id} to Intune.")
            else:
                print(f"{Fore.RED}⚠️ Failed to publish {package_id} to Intune.")
        else:
            print(f"{Fore.YELLOW}Skipping publishing of {package_id}.")

        report_choice = input(f"\n{Fore.CYAN}Do you want to generate a full report of apps in your Intune tenant? (y/n): ").strip().lower()
        if report_choice == 'y':
            generate_intune_app_report(config)

        another = input(f"\n{Fore.YELLOW}Do you want to package and/or publish another app? (y/n): ").strip().lower()
        if another != 'y':
            break

    print(f"{Fore.CYAN}{Style.BRIGHT}\n✨ Process completed. ✨{Style.RESET_ALL}")

###############################################################################
## STEP 11: Script Entry Point
###############################################################################
if __name__ == "__main__":
    main()