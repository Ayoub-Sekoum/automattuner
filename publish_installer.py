##
## **⚠️ BETA SOFTWARE - VERSION 0.1.8.2 ⚠️** ## Fixes SyntaxError in error handling
##
## This script is currently in BETA. Use with caution and at your own risk.
## Expect potential issues and instability.
##
## **Created by Sekoum Ayoub**
##
## **Open Source License:** MIT License (Example - Replace with your chosen license)
##
## This script is released under the MIT License.
## You are free to use, modify, and distribute it according to the terms of the license.
## See the LICENSE file (if present) or https://opensource.org/licenses/MIT for full details.
##
## **Disclaimer:**
##
## The author(s) are not responsible for any issues or damages caused by the use of this script.
## Always test in a non-production environment first and ensure you understand the script's functionality
## before using it in a live environment.
##
## # Intune App Packager and Publisher Script
##
## (Description and other comments remain the same)
##

import json
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.parse # Import urlencode
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
        # Ensure required directories exist
        Path(config['wintuner_download_dir']).mkdir(parents=True, exist_ok=True)
        Path(config.get('temp_package_dir', 'temp_packages')).mkdir(parents=True, exist_ok=True) # Optional temp dir
        # Basic validation
        required_keys = ['intune_tenant_id', 'intune_client_id', 'intune_client_secret', 'wintuner_download_dir']
        if not all(key in config for key in required_keys):
             missing = [key for key in required_keys if key not in config]
             raise KeyError(f"Missing required keys in config: {', '.join(missing)}")
        return config
    except FileNotFoundError:
        error_msg(f"Configuration file '{config_file}' not found", f"Please create it in the script directory: {script_directory}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        error_msg(f"Error loading configuration from {config_file}", str(e))
        return None
    except Exception as e:
        error_msg("Unexpected error loading configuration", str(e))
        return None

###############################################################################
## STEP 5: Intune App Check (Report Based)
###############################################################################
def check_intune_app_report_based(package_id, config):
    """Check if the app exists in Intune by comparing against a generated report."""
    print(f"\n{Fore.CYAN}Checking Intune for apps matching '{package_id}' using Intune App Report...")

    # Process package_id to get only the part before the first dot (if any) for broader matching
    processed_package_id_match = package_id
    if "." in processed_package_id_match:
        processed_package_id_match = processed_package_id_match.split(".")[0]

    # Generate report filtered by the processed ID part
    report_output = generate_intune_app_report(config, package_id_filter=processed_package_id_match, print_report=False) # Don't print full report here

    if report_output is None: # Handle case where report generation failed (e.g., bad token)
        print(f"{Fore.YELLOW}⚠️ Could not retrieve Intune App Report to check for existing apps.")
        return False  # Indicate check failure

    apps_found = []
    if report_output: # Check if report_output is not empty
        for app_info in report_output: # Iterate through the returned list of dicts
            display_name = app_info.get('displayName', 'N/A')
            # Process display name from report to get only the first part
            processed_display_name_match = display_name
            if "." in processed_display_name_match:
                processed_display_name_match = processed_display_name_match.split(".")[0]

            # Compare processed package_id with processed display_name
            if processed_package_id_match.lower() in processed_display_name_match.lower():
                apps_found.append(app_info) # Add matching app info to the list

    if apps_found:
        print(f"{Fore.YELLOW}Found the following matching app(s) in Intune:")
        for app_info in apps_found:
            original_display_name = app_info.get('originalDisplayName', 'Unknown App')
            print(f"  - '{original_display_name}' (Version: {app_info.get('displayVersion', 'N/A')}, ID: {app_info.get('id', 'N/A')})")
        return True # Indicate that at least one match was found
    else:
        print(Fore.GREEN + f"No app with name containing '{package_id}' found in Intune based on the report.")
        return False

###############################################################################
## STEP 9: Intune App Report Generation (Fixed SyntaxError)
###############################################################################
def get_intune_apps(token, package_id_filter=None):
    """Retrieves Intune apps using Microsoft Graph API, optionally filters by display name containing package_id_filter."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json", # Good practice to include Accept header
        "ConsistencyLevel": "eventual" # Required for certain filters/counts
    }
    # Use urlencode for query parameters
    base_uri = "https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps"
    params = {'$top': '999'} # Fetch maximum allowed per page to reduce requests
    if package_id_filter:
        # Add parameters for filtering and counting
        params['$filter'] = f"contains(tolower(displayName), '{package_id_filter.lower()}')"
        params['$count'] = 'true' # Required header ConsistencyLevel is set

    # Construct the initial URI with properly encoded parameters
    uri = base_uri + "?" + urllib.parse.urlencode(params)

    all_apps = []
    print(f"{Fore.BLUE}Fetching Intune apps... (Filter: {package_id_filter or 'None'})", end='', flush=True)
    while uri:
        print(".", end='', flush=True) # Progress indicator
        try:
            # Ensure the request uses the potentially updated URI with encoded params
            req = urllib.request.Request(uri, headers=headers, method='GET') # Explicitly GET
            with urllib.request.urlopen(req, timeout=45) as response: # Increased timeout slightly
                if response.status != 200:
                     error_body = "N/A"
                     try: # Try to read body
                         error_body = response.read().decode('utf-8', errors='replace')
                     except Exception: pass
                     error_msg("Error fetching apps from Intune", f"HTTP Status: {response.status}, Body: {error_body}")
                     return None # Indicate failure
                data = json.loads(response.read().decode('utf-8'))
                apps = data.get('value', [])
                all_apps.extend(apps)
                # IMPORTANT: Use the full URL provided in @odata.nextLink for pagination
                uri = data.get('@odata.nextLink')
        except urllib.error.HTTPError as e:
            # --- FIX: Corrected Syntax Error ---
            error_body = "N/A"
            try:
                error_body = e.read().decode('utf-8', errors='replace') # Try reading the body
            except Exception:
                pass # Ignore if reading fails
            # --- End of FIX ---
            error_msg(f"Error fetching apps from Intune (HTTP {e.code})", f"Reason: {e.reason} for URL: {repr(uri)}\nResponse: {error_body}")
            print() # Newline after progress dots
            return None # Indicate failure
        except Exception as e:
            error_msg(f"Unexpected error fetching apps for URL: {repr(uri)}", e)
            print() # Newline after progress dots
            return None # Indicate failure

    print(f" {Fore.GREEN}Done. Found {len(all_apps)} apps.") # Report count
    return all_apps

def generate_report_output(apps):
    """Generates a formatted report list of Intune apps (list of dictionaries)."""
    if not apps:
        return [] # Return empty list if no apps

    report_output_list = []
    for app in apps:
        name = app.get('displayName', 'N/A')
        original_name = name # Store original name

        processed_name = name # Keep processed name logic if needed elsewhere
        if "." in processed_name:
            processed_name = processed_name.split(".")[0]

        platform = determine_platform(app.get('@odata.type', ''))
        version = app.get('displayVersion', 'N/A') or app.get('committedContentVersion', 'N/A') or app.get('appVersion', 'N/A') or 'N/A' # Ensure default
        # Field name for VPP token might be vppTokenAppleId or similar, adjust if needed based on Graph API output
        vpp_token_name = app.get('vppTokenAppleId', 'N/A') if platform == "iOS VPP" else 'N/A'
        assigned = 'Yes' if app.get('isAssigned') else 'No'
        developer = app.get('publisher', 'N/A')

        app_info = {
            "displayName": processed_name,
            "originalDisplayName": original_name, # Keep the original full name
            "platform": platform,
            "displayVersion": version,
            "vppTokenName": vpp_token_name, # Include VPP Token Name in data
            "isAssigned": assigned,
            "publisher": developer,
            "id": app.get('id', 'N/A')
        }
        report_output_list.append(app_info)

    return report_output_list

def print_formatted_report(report_data):
    """Prints the report data list in a formatted table to the console."""
    if not report_data:
        print(f"{Fore.YELLOW}No app data to display in the report.")
        return

    col_widths = {
        "Name": 40,
        "Platform": 13, # Slightly wider
        "Version": 15,
        "VPP Token Name": 20, # Restored & Wider
        "Assigned": 10,
        "Developer": 24
    }
    border_line = "+" + "+".join(["-" * (width + 2) for width in col_widths.values()]) + "+"

    print("\n" + Fore.CYAN + "--- Intune App Report ---")
    print(border_line)
    header = "|"
    for col, width in col_widths.items():
        header += " " + f"{col:<{width}}" + " |"
    print(header)
    print(border_line)

    for app_info in report_data:
        name = app_info.get('originalDisplayName', 'N/A') # Use original name for display
        platform = app_info.get('platform', 'N/A')
        version = app_info.get('displayVersion', 'N/A')
        vpp_token_name = app_info.get('vppTokenName', 'N/A') # Get VPP token data
        assigned = app_info.get('isAssigned', 'N/A')
        developer = app_info.get('publisher', 'N/A')

        # Truncate fields safely before formatting
        name_disp = (name[:col_widths['Name'] - 1] + '…') if len(name) > col_widths['Name'] else name
        platform_disp = (platform[:col_widths['Platform'] - 1] + '…') if len(platform) > col_widths['Platform'] else platform
        version_disp = (version[:col_widths['Version'] - 1] + '…') if len(version) > col_widths['Version'] else version
        vpp_disp = (vpp_token_name[:col_widths['VPP Token Name'] - 1] + '…') if len(vpp_token_name) > col_widths['VPP Token Name'] else vpp_token_name
        assigned_disp = (assigned[:col_widths['Assigned'] - 1] + '…') if len(assigned) > col_widths['Assigned'] else assigned
        dev_disp = (developer[:col_widths['Developer'] - 1] + '…') if len(developer) > col_widths['Developer'] else developer

        row = (
            f"| {name_disp:<{col_widths['Name']}} | "
            f"{platform_disp:<{col_widths['Platform']}} | "
            f"{version_disp:<{col_widths['Version']}} | "
            f"{vpp_disp:<{col_widths['VPP Token Name']}} | " # Display VPP token
            f"{assigned_disp:<{col_widths['Assigned']}} | "
            f"{dev_disp:<{col_widths['Developer']}} |"
        )
        print(row)

    print(border_line)
    print(f"{Fore.CYAN}--- End of Report ---")


def determine_platform(odata_type):
    """Determine app platform based on @odata.type."""
    odata_type = odata_type.lower() # Case-insensitive check
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
    if "microsoftedge" in odata_type: return "Edge" # MicrosoftEdgeApp
    if "webapp" in odata_type: return "Web App" # WebApp
    # Extract simple type if complex one not matched
    simple_type = odata_type.split('.')[-1]
    return simple_type.replace('app', '').capitalize() or "Other"

def generate_intune_app_report(config, package_id_filter=None, print_report=True):
    """Generates Intune app report data, optionally filters, optionally prints."""

    print(f"{Fore.CYAN}Generating Intune app report data...")
    token = get_access_token(config)
    if not token:
        print(f"{Fore.YELLOW}⚠️ Failed to retrieve access token for report generation.")
        return None # Indicate failure

    # Fetch apps, potentially filtered (uses the fixed get_intune_apps)
    apps = get_intune_apps(token, package_id_filter=package_id_filter)
    if apps is None: # Check if fetching failed
        return None # Propagate failure

    # Generate the report data (list of dictionaries)
    report_data = generate_report_output(apps)

    if print_report:
        print_formatted_report(report_data) # Uses the fixed print function

    return report_data # Always return the data list


###############################################################################
## STEP 6: Microsoft Graph API Access Token Retrieval (Fixed SyntaxError)
###############################################################################
def get_access_token(config):
    """Get access token for Microsoft Graph API using client credentials via urllib."""
    try:
        tenant_id = config['intune_tenant_id']
        client_id = config['intune_client_id']
        client_secret = config['intune_client_secret'] # Ensure this is handled securely

        authority = f"https://login.microsoftonline.com/{tenant_id}"
        url = f"{authority}/oauth2/v2.0/token"
        data = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default' # Scope for client credentials
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method='POST') # Explicitly POST

        with urllib.request.urlopen(req, timeout=30) as response: # Added timeout
            if response.status == 200:
                result = json.loads(response.read().decode('utf-8'))
                if "access_token" in result:
                    return result['access_token']
                else:
                    error_msg("MSAL Authentication Error (Token not found)", result.get("error_description", "No error description provided."))
                    return None
            else:
                 error_body = "N/A"
                 try: # Try reading body
                     error_body = response.read().decode('utf-8', errors='replace')
                 except Exception: pass
                 error_msg("MSAL Authentication Error", f"HTTP Status {response.status}, Body: {error_body}")
                 return None

    except urllib.error.HTTPError as e:
        # --- FIX: Corrected Syntax Error ---
        error_body = "N/A"
        try:
            error_body = e.read().decode('utf-8', errors='replace') # Try reading the body
        except Exception:
            pass # Ignore if reading fails
        # --- End of FIX ---
        error_msg("MSAL Authentication HTTP Error", f"Code: {e.code}, Reason: {e.reason}\nResponse Body: {error_body}")
        return None
    except urllib.error.URLError as e:
        error_msg("MSAL Authentication Network Error", str(e.reason))
        return None
    except Exception as e:
        error_msg("MSAL Authentication Exception", str(e))
        return None

###############################################################################
## STEP 4: Local Package Check
###############################################################################
def check_local_package(package_id, version, config):
    """Check if a local package directory exists for the specific version or latest."""
    version_folder = version if version else 'latest'
    package_path = Path(config['wintuner_download_dir']) / package_id / version_folder
    return package_path.is_dir()

###############################################################################
## STEP 7: Command Execution with Alive-Progress Bar
###############################################################################
def run_command_with_progress(cmd, description):
    """Execute a command with alive-progress bar and capture output."""
    stdout_lines = []
    stderr_lines = []
    try:
        # Message is now printed ONLY by alive_bar title and the initial print here
        print(f"{Fore.CYAN}🚀 {description}...")
        # Ensure command args are strings
        cmd_str_list = [str(item) for item in cmd]
        process = subprocess.Popen(cmd_str_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', shell=False) # Explicitly shell=False

        with alive_bar(total=None, title=f"{Fore.YELLOW}{description}", theme='smooth', length=30) as bar:
            while process.poll() is None:
                time.sleep(0.1)
                bar()

        stdout, stderr = process.communicate()

        if stdout: stdout_lines = stdout.strip().splitlines()
        if stderr: stderr_lines = stderr.strip().splitlines()

        if process.returncode != 0:
            error_msg(f"Error during {description} (Return Code: {process.returncode})", "\n".join(stderr_lines) or "\n".join(stdout_lines) or "No output.")
            return False, stdout_lines, stderr_lines
        else:
            print(f"{Fore.GREEN}✅ {description} completed successfully.")
            return True, stdout_lines, stderr_lines

    except FileNotFoundError:
        error_msg(f"Error during {description}", f"Command not found: '{cmd[0]}'. Is wintuner installed and in PATH?")
        return False, [], [f"Command not found: {cmd[0]}"]
    except Exception as e:
        error_msg(f"An unexpected error occurred during {description}", str(e))
        return False, [], [str(e)]

###############################################################################
## STEP 8: Error Message Handling
###############################################################################
def error_msg(step, error):
    """Print a formatted error message."""
    print(f"\n{Fore.RED}{Style.BRIGHT}❌ Error during {step}:{Style.RESET_ALL}")
    error_lines = str(error).splitlines()
    for line in error_lines:
        print(f"  {Fore.YELLOW}{line}")

###############################################################################
## STEP 10: Main Application Logic
###############################################################################
def main():
    """Main function to drive the Intune app packaging and publishing process."""
    print(f"{Fore.CYAN}{Style.BRIGHT}🚀 Intune App Packager and Publisher (Multi-App) 🚀{Style.RESET_ALL}")

    config = load_config()
    if not config:
        print(f"{Fore.RED}Exiting due to configuration loading errors.")
        sys.exit(1)

    while True: # Loop for processing batches of apps
        # --- Get Batch Input ---
        print(f"\n{Fore.GREEN}🆔 Enter App IDs (comma-separated, e.g., Mozilla.Firefox,Zoom.Zoom): ", end="")
        app_ids_input = input().strip()
        if not app_ids_input: print(f"{Fore.RED}No App IDs entered."); continue
        app_id_list = [pid.strip() for pid in app_ids_input.split(',') if pid.strip()]
        if not app_id_list: print(f"{Fore.RED}No valid App IDs found in the input."); continue
        print(f"\n{Fore.CYAN}Processing batch of {len(app_id_list)} app(s): {', '.join(app_id_list)}")

        # --- Get Common Settings for the Batch ---
        print(f"\n{Fore.GREEN}📦 Enter Version (leave empty for latest - applies to ALL apps in batch): ", end="")
        version = input().strip() or None # Use None if empty

        architecture_options = {"1": 'x64', "2": 'x86', "3": 'arm64'}
        default_architecture = "1" # x64
        print(f"\n{Fore.CYAN}⚙️ Architecture (applies to ALL apps in batch):")
        for key, value in architecture_options.items(): print(f"  [{key}] {Fore.YELLOW}{value}{' (default)' if key == default_architecture else ''}")
        architecture_choice = input(f"{Fore.GREEN}👉 Choose or ENTER for default: ").strip()
        architecture = architecture_options.get(architecture_choice, architecture_options[default_architecture])

        installer_context_options = {"1": 'user', "2": 'system'}
        default_installer_context = "2" # system
        print(f"\n{Fore.CYAN}⚙️ Installation Context (applies to ALL apps in batch):")
        for key, value in installer_context_options.items(): print(f"  [{key}] {Fore.YELLOW}{value}{' (default)' if key == default_installer_context else ''}")
        installer_context_choice = input(f"{Fore.GREEN}👉 Choose or ENTER for default: ").strip()
        installer_context = installer_context_options.get(installer_context_choice, installer_context_options[default_installer_context])

        # --- Process Each App in the Batch ---
        batch_results = {"success": [], "failed_pkg": [], "failed_pub": [], "skipped": []}
        access_token = None # Store token once obtained for the batch

        for package_id in app_id_list:
            print(f"\n{Fore.MAGENTA}{Style.BRIGHT}--- Processing App: {package_id} ---{Style.RESET_ALL}")

            # 1. Package Creation/Check
            local_package_exists = check_local_package(package_id, version, config)
            package_dir = Path(config['wintuner_download_dir']) / package_id / (version or 'latest')

            if local_package_exists:
                print(f"{Fore.YELLOW}✔️ Local package found: {package_dir}")
            else:
                package_cmd = [ "wintuner", "package", package_id, "--package-folder", config['wintuner_download_dir'], "--architecture", architecture, "--installer-context", installer_context ]
                if version: package_cmd.extend(["--version", version])

                success, _, _ = run_command_with_progress(package_cmd, f"Packaging {package_id}")
                if success:
                    print(f"{Fore.GREEN}✅ Package created: {package_dir}")
                else:
                    print(f"{Fore.RED}❌ Failed to create package for {package_id}. Skipping further steps for this app.")
                    batch_results["failed_pkg"].append(package_id); continue

            # 2. Intune Check (Optional)
            intune_check_choice = input(f"\n{Fore.YELLOW}🔎 Check Intune for '{package_id}'? (y/n, default n): ").strip().lower() or 'n'
            proceed_with_publish = True

            if intune_check_choice == 'y':
                app_exists_in_intune = check_intune_app_report_based(package_id, config)
                if app_exists_in_intune:
                    publish_anyway_choice = input(f"{Fore.YELLOW}❓ App(s) matching '{package_id}' found. Still try publishing? (y/n, default n): ").strip().lower() or 'n'
                    if publish_anyway_choice != 'y':
                        proceed_with_publish = False
                        print(f"{Fore.YELLOW}Skipping publishing for {package_id} as requested.")
                        batch_results["skipped"].append(package_id)
            else:
                 print(f"{Fore.BLUE}Skipping Intune check for {package_id}.")

            # 3. Publish to Intune (Optional)
            if proceed_with_publish:
                publish_choice = input(f"\n{Fore.YELLOW}🚀 Publish '{package_id}' to Intune? (y/n, default n): ").strip().lower() or 'n'
                if publish_choice == 'y':
                    if not access_token:
                        print(f"{Fore.BLUE}Obtaining Intune access token...")
                        access_token = get_access_token(config)
                        if not access_token:
                            print(f"{Fore.RED}❌ Failed to obtain access token. Cannot publish {package_id} or subsequent apps.")
                            batch_results["failed_pub"].append(package_id + " (Token Error)"); break

                    publish_cmd = [ "wintuner", "publish", package_id, "--package-folder", config['wintuner_download_dir'], "--tenant", config['intune_tenant_id'], "--token", access_token ]
                    if version: publish_cmd.extend(["--version", version])

                    success, _, _ = run_command_with_progress(publish_cmd, f"Publishing {package_id}")
                    if success:
                        print(f"{Fore.GREEN}🎉 Successfully published {package_id} to Intune.")
                        batch_results["success"].append(package_id)
                    else:
                        batch_results["failed_pub"].append(package_id)
                else:
                    print(f"{Fore.YELLOW}Skipping publishing for {package_id}.")
                    if package_id not in batch_results["skipped"]: batch_results["skipped"].append(package_id)

        # --- End of Batch Summary ---
        print(f"\n{Fore.CYAN}{Style.BRIGHT}--- Batch Processing Summary ---")
        if batch_results["success"]: print(f"{Fore.GREEN}✅ Published Successfully: {', '.join(batch_results['success'])}")
        if batch_results["failed_pkg"]: print(f"{Fore.RED}❌ Failed Packaging: {', '.join(batch_results['failed_pkg'])}")
        if batch_results["failed_pub"]: print(f"{Fore.RED}❌ Failed Publishing: {', '.join(batch_results['failed_pub'])}")
        if batch_results["skipped"]: print(f"{Fore.YELLOW}🟡 Skipped Publishing (User choice or existing): {', '.join(batch_results['skipped'])}")
        print(f"{Fore.CYAN}-----------------------------")

        # --- Optional Full Report After Batch ---
        report_choice = input(f"\n{Fore.CYAN}📊 Generate a full report of ALL apps in your Intune tenant? (y/n, default n): ").strip().lower() or 'n'
        if report_choice == 'y':
            generate_intune_app_report(config, print_report=True)

        # --- Ask to Process Another Batch ---
        another_batch = input(f"\n{Fore.YELLOW}🔄 Process another batch of apps? (y/n, default n): ").strip().lower() or 'n'
        if another_batch != 'y': break

    print(f"{Fore.CYAN}{Style.BRIGHT}\n✨ All operations finished. ✨{Style.RESET_ALL}")

###############################################################################
## STEP 11: Script Entry Point
###############################################################################
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
         print(f"\n{Fore.RED}{Style.BRIGHT}💥 An unexpected critical error occurred: {e}")
         import traceback; traceback.print_exc() # Uncomment for debugging details
         sys.exit(1)
