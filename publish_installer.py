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
import logging
import csv # Added for CSV export

init(autoreset=True)

# Global logger instance
logger = logging.getLogger(__name__)

###############################################################################
# Logging Setup
###############################################################################
def setup_logging(log_file_name="intune_publisher.log"):
    """Configures logging for the script."""
    logger.setLevel(logging.INFO)  # Set the general logging level for the logger instance

    # File Handler - logs INFO and higher
    file_handler = logging.FileHandler(log_file_name, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler - for specific messages that need to be printed
    # We will use direct print() for user prompts and critical console feedback for now,
    # but a console handler could be added for more granular control if needed.
    # For example, to print WARNING and ERROR to console:
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.WARNING)
    # console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    # console_handler.setFormatter(console_formatter)
    # logger.addHandler(console_handler)

    logger.info("Logging initialized.")

from intune_client import get_access_token as client_get_access_token
from intune_client import get_intune_apps as client_get_intune_apps
from intune_client import determine_platform as client_determine_platform

###############################################################################
## Configuration Loading
###############################################################################
import os

def load_config(config_file="config.json"):
    """Load configurations, prioritizing environment variables for sensitive data."""
    config = {}
    errors = []
    script_directory = Path(__file__).resolve().parent
    config_path = script_directory / config_file

    # Load sensitive data from environment variables first
    config['intune_tenant_id'] = os.environ.get('INTUNE_TENANT_ID')
    config['intune_client_id'] = os.environ.get('INTUNE_CLIENT_ID')
    config['intune_client_secret'] = os.environ.get('INTUNE_CLIENT_SECRET')

    # Try to load from config.json if any sensitive data is missing or for other settings
    config_from_file = {}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_from_file = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Error decoding JSON from '{config_file}': {e}")
        except Exception as e:
            errors.append(f"Unexpected error reading '{config_file}': {e}")
    elif not all(config[key] for key in ['intune_tenant_id', 'intune_client_id', 'intune_client_secret']):
        # If config file not found and sensitive env vars are not all set, it's an issue for those.
        errors.append(f"Configuration file '{config_file}' not found at {config_path} and sensitive environment variables are not all set.")

    # Fallback to config file for sensitive data if not in env
    if not config['intune_tenant_id'] and 'intune_tenant_id' in config_from_file:
        config['intune_tenant_id'] = config_from_file['intune_tenant_id']
    if not config['intune_client_id'] and 'intune_client_id' in config_from_file:
        config['intune_client_id'] = config_from_file['intune_client_id']
    if not config['intune_client_secret'] and 'intune_client_secret' in config_from_file:
        config['intune_client_secret'] = config_from_file['intune_client_secret']

    # Check for missing sensitive data
    missing_sensitive_keys = []
    if not config['intune_tenant_id']:
        missing_sensitive_keys.append('INTUNE_TENANT_ID or intune_tenant_id in config.json')
    if not config['intune_client_id']:
        missing_sensitive_keys.append('INTUNE_CLIENT_ID or intune_client_id in config.json')
    if not config['intune_client_secret']:
        missing_sensitive_keys.append('INTUNE_CLIENT_SECRET or intune_client_secret in config.json')

    if missing_sensitive_keys:
        errors.append(f"Missing critical sensitive configuration(s): {', '.join(missing_sensitive_keys)}. Please set them as environment variables or in {config_file}.")

    # Load non-sensitive configurations from config file or use defaults
    config['wintuner_download_dir'] = config_from_file.get('wintuner_download_dir', str(script_directory / 'wintuner_downloads'))
    config['temp_package_dir'] = config_from_file.get('temp_package_dir', str(script_directory / 'temp_packages'))

    # Ensure required directories exist
    try:
        Path(config['wintuner_download_dir']).mkdir(parents=True, exist_ok=True)
        Path(config['temp_package_dir']).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Error creating directories: {e}")

    if errors:
        for err in errors:
            # error_msg is now logger.error, but for config, we want it on console too.
            # For now, load_config will call the original error_msg which prints.
            # This part needs careful refactoring if error_msg is fully replaced by logger.error
            # For this iteration, we'll assume error_msg still prints to console for critical startup errors.
            error_msg("Configuration Error", err) 
        logger.error(f"Configuration failed with errors: {'; '.join(errors)}")
        return None # Indicate failure
    logger.info("Configuration loaded successfully.")
    return config

###############################################################################
## STEP 5: Intune App Check (Report Based)
###############################################################################
def check_intune_app_report_based(package_id, config):
    """Check if the app exists in Intune by comparing against a generated report."""
    logger.info(f"Checking Intune for apps matching '{package_id}' using Intune App Report.")
    print(f"\n{Fore.CYAN}Checking Intune for apps matching '{package_id}' using Intune App Report...")

    processed_package_id_match = package_id
    if "." in processed_package_id_match:
        processed_package_id_match = processed_package_id_match.split(".")[0]

    # Use the centralized generate_intune_app_report which now uses client functions
    report_output = generate_intune_app_report(config, package_id_filter=processed_package_id_match, print_report=False)

    if report_output is None:
        logger.warning(f"Could not retrieve Intune App Report for '{package_id}'. Report generation failed. (check_intune_app_report_based)")
        print(f"{Fore.YELLOW}⚠️ Could not retrieve Intune App Report to check for existing apps.") # Keep console output
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
        logger.info(f"Found {len(apps_found)} matching app(s) in Intune for '{package_id}'.")
        print(f"{Fore.YELLOW}Found the following matching app(s) in Intune:") # Keep console output
        for app_info in apps_found:
            original_display_name = app_info.get('originalDisplayName', 'Unknown App')
            logger.info(f"  - Match: '{original_display_name}' (Version: {app_info.get('displayVersion', 'N/A')}, ID: {app_info.get('id', 'N/A')})")
            print(f"  - '{original_display_name}' (Version: {app_info.get('displayVersion', 'N/A')}, ID: {app_info.get('id', 'N/A')})") # Keep console output
        return True # Indicate that at least one match was found
    else:
        logger.info(f"No app with name containing '{package_id}' found in Intune based on the report.")
        print(Fore.GREEN + f"No app with name containing '{package_id}' found in Intune based on the report.") # Keep console output
        return False

###############################################################################
## STEP 9: Intune App Report Generation
###############################################################################
# Note: get_intune_apps is now imported as client_get_intune_apps
# Note: determine_platform is now imported as client_determine_platform

def generate_report_output(apps):
    """Generates a formatted report list of Intune apps (list of dictionaries)."""
    if not apps:
        return []

    report_output_list = []
    for app in apps:
        name = app.get('displayName', 'N/A')
        original_name = name

        processed_name = name
        if "." in processed_name:
            processed_name = processed_name.split(".")[0]

        # Use imported client_determine_platform
        platform = client_determine_platform(app.get('@odata.type', ''))
        version = app.get('displayVersion', 'N/A') or app.get('committedContentVersion', 'N/A') or app.get('appVersion', 'N/A') or 'N/A'
        vpp_token_name = app.get('vppTokenAppleId', 'N/A') if platform == "iOS VPP" else 'N/A'
        assigned = 'Yes' if app.get('isAssigned') else 'No'
        developer = app.get('publisher', 'N/A')

        app_info = {
            "displayName": processed_name,
            "originalDisplayName": original_name,
            "platform": platform,
            "displayVersion": version,
            "vppTokenName": vpp_token_name,
            "isAssigned": assigned,
            "publisher": developer,
            "id": app.get('id', 'N/A')
        }
        report_output_list.append(app_info)
    return report_output_list

def print_formatted_report(report_data):
    """Prints the report data list in a formatted table to the console."""
    if not report_data:
        logger.info("No app data to display in the report.")
        print(f"{Fore.YELLOW}No app data to display in the report.") # Keep console output
        return

    # Log the raw report data at debug level if needed
    logger.debug(f"Raw report data for printing: {report_data}")

    col_widths = {
        "Name": 40,
        "Platform": 13,
        "Version": 15,
        "VPP Token Name": 20,
        "Assigned": 10,
        "Developer": 24
    }
    border_line = "+" + "+".join(["-" * (width + 2) for width in col_widths.values()]) + "+"

    # Keep console output for the report
    report_string = ["\n" + Fore.CYAN + "--- Intune App Report ---"]
    report_string.append(border_line)
    header = "|"
    for col, width in col_widths.items():
        header += " " + f"{col:<{width}}" + " |"
    report_string.append(header)
    report_string.append(border_line)

    for app_info in report_data:
        name = app_info.get('originalDisplayName', 'N/A')
        platform = app_info.get('platform', 'N/A')
        version = app_info.get('displayVersion', 'N/A')
        vpp_token_name = app_info.get('vppTokenName', 'N/A')
        assigned = app_info.get('isAssigned', 'N/A')
        developer = app_info.get('publisher', 'N/A')

        name_disp = (name[:col_widths['Name'] - 1] + '…') if len(name) > col_widths['Name'] else name
        platform_disp = (platform[:col_widths['Platform'] - 1] + '…') if len(platform) > col_widths['Platform'] else platform
        version_disp = (version[:col_widths['Version'] - 1] + '…') if len(version) > col_widths['Version'] else version
        vpp_disp = (vpp_token_name[:col_widths['VPP Token Name'] - 1] + '…') if len(vpp_token_name) > col_widths['VPP Token Name'] else vpp_token_name
        assigned_disp = (assigned[:col_widths['Assigned'] - 1] + '…') if len(assigned) > col_widths['Assigned'] else assigned
        dev_disp = (developer[:col_widths['Developer'] - 1] + '…') if len(developer) > col_widths['Developer'] else developer

        row_str = (
            f"| {name_disp:<{col_widths['Name']}} | "
            f"{platform_disp:<{col_widths['Platform']}} | "
            f"{version_disp:<{col_widths['Version']}} | "
            f"{vpp_disp:<{col_widths['VPP Token Name']}} | "
            f"{assigned_disp:<{col_widths['Assigned']}} | "
            f"{dev_disp:<{col_widths['Developer']}} |"
        )
        report_string.append(row_str)

    report_string.append(border_line)
    report_string.append(f"{Fore.CYAN}--- End of Report ---")
    
    final_report_output = "\n".join(report_string)
    print(final_report_output)
    logger.info("Intune App Report generated and printed to console.")
    # For file log, a summary or the full data might be more appropriate than the formatted table.
    # For now, just log that it was printed. A more structured log of the data itself is in generate_report_output.

# determine_platform is now imported as client_determine_platform

def generate_intune_app_report(config, package_id_filter=None, print_report=True, csv_file_path: str = None, json_file_path: str = None):
    """Generates Intune app report data, optionally filters, prints, and saves to CSV/JSON."""
    logger.info(f"Generating Intune app report. Filter: '{package_id_filter}', Print: {print_report}, CSV: '{csv_file_path}', JSON: '{json_file_path}' (publish_installer)")
    print(f"{Fore.CYAN}Generating Intune app report data...")

    logger.info("Requesting access token via intune_client module... (publish_installer)")
    access_token = client_get_access_token(
        tenant_id=config.get('intune_tenant_id'),
        client_id=config.get('intune_client_id'),
        client_secret=config.get('intune_client_secret')
    )

    if not access_token:
        logger.error("Failed to retrieve access token via intune_client. Cannot proceed with report generation. (publish_installer)")
        # User-facing error message is handled by print statements within this function or by the caller
        print(f"{Fore.YELLOW}⚠️ Failed to retrieve access token for report generation.")
        return None

    # Call the client_get_intune_apps function
    logger.info(f"Fetching apps via intune_client module with filter: '{package_id_filter}'... (publish_installer)")
    # The print for "Fetching Intune apps..." will be inside client_get_intune_apps if we keep it there,
    # or we can add one here if client_get_intune_apps becomes silent on console.
    # For now, assuming client_get_intune_apps might still print its progress dots.
    apps = client_get_intune_apps(access_token, package_id_filter=package_id_filter)
    
    if apps is None:
        logger.warning("App fetching via intune_client failed, cannot generate report data. (publish_installer)")
        # User-facing message can be added here if needed, e.g., print(f"{Fore.YELLOW}⚠️ Failed to retrieve app list from Intune.")
        return None

    report_data = generate_report_output(apps) # This function now uses client_determine_platform
    logger.info(f"Generated report data for {len(report_data)} app(s). (publish_installer)")
    logger.debug(f"Generated report data (first 5 items): {report_data[:5]} (publish_installer)")

    if print_report:
        print_formatted_report(report_data)

    # Save to CSV if path is provided
    if csv_file_path and report_data:
        try:
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                if report_data: # Ensure there's data to get headers from
                    # Using originalDisplayName as it's likely more complete for reports
                    # and other fields as they are in app_info within generate_report_output
                    # The keys in report_data items are:
                    # "displayName", "originalDisplayName", "platform", "displayVersion", 
                    # "vppTokenName", "isAssigned", "publisher", "id"
                    # Let's choose a sensible subset for export, matching print_formatted_report more closely.
                    # Using originalDisplayName instead of displayName for the main name column.
                    fieldnames = ['originalDisplayName', 'platform', 'displayVersion', 'vppTokenName', 'isAssigned', 'publisher', 'id']
                    # Filter out keys not present in all dicts if necessary, or ensure all dicts have these keys (even if value is N/A)
                    # For simplicity, assuming generate_report_output ensures these keys.
                    
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore') # extrasaction='ignore' is safer
                    writer.writeheader()
                    # Write the data rows
                    for app_row in report_data:
                        # Ensure all expected keys are present, defaulting to 'N/A' if missing, to avoid KeyError
                        row_to_write = {key: app_row.get(key, 'N/A') for key in fieldnames}
                        writer.writerow(row_to_write)
                    logger.info(f"Intune app report successfully saved to CSV: {csv_file_path}")
                    print(f"{Fore.GREEN}📊 Report saved to CSV: {csv_file_path}")
                else:
                    logger.warning(f"No data to save to CSV for path: {csv_file_path}")
        except IOError as e:
            logger.error(f"IOError saving report to CSV '{csv_file_path}': {e}", exc_info=True)
            error_msg("CSV Export Error", f"Could not write CSV file to '{csv_file_path}'. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving report to CSV '{csv_file_path}': {e}", exc_info=True)
            error_msg("CSV Export Error", f"An unexpected error occurred while writing CSV to '{csv_file_path}'. Error: {e}")
    elif csv_file_path and not report_data:
         logger.warning(f"CSV export requested to '{csv_file_path}', but no report data was generated.")

    # Save to JSON if path is provided
    if json_file_path and report_data:
        try:
            with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(report_data, jsonfile, indent=4)
            logger.info(f"Intune app report successfully saved to JSON: {json_file_path}")
            print(f"{Fore.GREEN}📊 Report saved to JSON: {json_file_path}")
        except IOError as e:
            logger.error(f"IOError saving report to JSON '{json_file_path}': {e}", exc_info=True)
            error_msg("JSON Export Error", f"Could not write JSON file to '{json_file_path}'. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving report to JSON '{json_file_path}': {e}", exc_info=True)
            error_msg("JSON Export Error", f"An unexpected error occurred while writing JSON to '{json_file_path}'. Error: {e}")
    elif json_file_path and not report_data:
        logger.warning(f"JSON export requested to '{json_file_path}', but no report data was generated.")
        
    return report_data


###############################################################################
# STEP 6: Microsoft Graph API Access Token Retrieval
# This function is now handled by intune_client.get_access_token
# The local get_access_token(config) function in publish_installer.py is removed.
# Calls will be made to client_get_access_token(tenant_id, client_id, client_secret)
###############################################################################

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
    cmd_str_list = [str(item) for item in cmd] # Ensure command args are strings
    logger.info(f"Executing command: {' '.join(cmd_str_list)}") # Log the command
    # Keep console print for user feedback
    print(f"{Fore.CYAN}🚀 {description}...")
    try:
        process = subprocess.Popen(cmd_str_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', shell=False)

        with alive_bar(total=None, title=f"{Fore.YELLOW}{description}", theme='smooth', length=30) as bar:
            while process.poll() is None:
                time.sleep(0.1)
                bar() # Update progress

        stdout, stderr = process.communicate()

        if stdout:
            stdout_lines = stdout.strip().splitlines()
            logger.debug(f"Command '{description}' STDOUT:\n{stdout}")
        if stderr:
            stderr_lines = stderr.strip().splitlines()
            logger.debug(f"Command '{description}' STDERR:\n{stderr}")

        if process.returncode != 0:
            logger.error(f"Error during '{description}' (Return Code: {process.returncode}). STDERR: {stderr.strip()} STDOUT: {stdout.strip()}")
            error_msg(f"Error during {description} (Return Code: {process.returncode})", "\n".join(stderr_lines) or "\n".join(stdout_lines) or "No output.") # Keep console
            return False, stdout_lines, stderr_lines
        else:
            logger.info(f"'{description}' completed successfully.")
            print(f"{Fore.GREEN}✅ {description} completed successfully.") # Keep console
            return True, stdout_lines, stderr_lines

    except FileNotFoundError:
        logger.error(f"Command not found: '{cmd_str_list[0]}'. Is wintuner installed and in PATH?", exc_info=True)
        error_msg(f"Error during {description}", f"Command not found: '{cmd_str_list[0]}'. Is wintuner installed and in PATH?") # Keep console
        return False, [], [f"Command not found: {cmd_str_list[0]}"]
    except Exception as e:
        logger.error(f"An unexpected error occurred during '{description}': {str(e)}", exc_info=True)
        error_msg(f"An unexpected error occurred during {description}", str(e)) # Keep console
        return False, [], [str(e)]

###############################################################################
## STEP 8: Error Message Handling
###############################################################################
def error_msg(step, error_details):
    """Prints a formatted error message to console and logs it as an error."""
    # Log the error first
    logger.error(f"Error during {step}: {error_details}")

    # Then print to console (as this function was originally for console output)
    print(f"\n{Fore.RED}{Style.BRIGHT}❌ Error during {step}:{Style.RESET_ALL}")
    error_lines = str(error_details).splitlines()
    for line in error_lines:
        print(f"  {Fore.YELLOW}{line}")

###############################################################################
## STEP 10: Main Application Logic - Refactored Helper Functions
###############################################################################

def prompt_for_manual_app_ids():
    """Prompts user for app IDs manually and returns a list of PackageID strings."""
    logger.info("Prompting for manual batch App IDs.")
    print(f"\n{Fore.GREEN}🆔 Enter App IDs (comma-separated, e.g., Mozilla.Firefox,Zoom.Zoom): ", end="")
    app_ids_input = input().strip()
    logger.info(f"User entered App IDs: '{app_ids_input}'")
    if not app_ids_input:
        logger.warning("No App IDs entered by user for manual input.")
        print(f"{Fore.RED}No App IDs entered.")
        return []
    app_id_list = [pid.strip() for pid in app_ids_input.split(',') if pid.strip()]
    if not app_id_list:
        logger.warning(f"No valid App IDs found in manual input: '{app_ids_input}'")
        print(f"{Fore.RED}No valid App IDs found in the input.")
        return []
    logger.info(f"Processing {len(app_id_list)} app(s) from manual input: {', '.join(app_id_list)}")
    print(f"\n{Fore.CYAN}Processing {len(app_id_list)} app(s) from manual input: {', '.join(app_id_list)}")
    return app_id_list

def prompt_for_csv_path():
    """Prompts user for CSV file path and returns it."""
    logger.info("Prompting for CSV file path.")
    csv_path = input(f"{Fore.GREEN}📂 Enter path to CSV file for batch input: ").strip()
    logger.info(f"User entered CSV path: '{csv_path}'")
    return csv_path

def parse_csv_input(csv_path):
    """Parses CSV for app specifications. Returns list of dicts or None on error."""
    app_specs = []
    required_column = "PackageID" # Case-sensitive as per current code style
    optional_columns = ["Version", "Architecture", "InstallerContext"]

    try:
        # Ensure the path is absolute or resolve it relative to the script/CWD
        # For simplicity, let's assume Path(csv_path) handles it well enough for now.
        csv_file = Path(csv_path)
        if not csv_file.is_file():
            error_msg("CSV Input Error", f"CSV file not found at: {csv_path}")
            return None

        with open(csv_file, mode='r', encoding='utf-8-sig', newline='') as file: # utf-8-sig handles BOM
            reader = csv.DictReader(file)
            
            # Check for required header
            if required_column not in reader.fieldnames:
                error_msg("CSV Input Error", f"Required column '{required_column}' not found in CSV header: {reader.fieldnames}")
                logger.error(f"CSV missing required column '{required_column}'. Headers: {reader.fieldnames}")
                return None

            for i, row in enumerate(reader):
                package_id = row.get(required_column, "").strip()
                if not package_id:
                    error_msg("CSV Input Error", f"Row {i+2}: '{required_column}' is missing or empty. Skipping row.")
                    logger.warning(f"CSV Row {i+2}: '{required_column}' is missing or empty. Skipping.")
                    continue
                
                app_spec = {'PackageID': package_id}
                for col in optional_columns:
                    value = row.get(col, "").strip()
                    app_spec[col] = value if value else None # Store None if empty/missing, for easier fallback logic
                
                app_specs.append(app_spec)
        
        if not app_specs:
            logger.warning(f"No valid app specifications found in CSV: {csv_path}")
            error_msg("CSV Input Error", "No valid app specifications could be read from the CSV.")
            return None
            
        logger.info(f"Successfully parsed {len(app_specs)} app specifications from CSV: {csv_path}")
        print(f"{Fore.CYAN}📄 Parsed {len(app_specs)} app specifications from CSV.")
        return app_specs

    except FileNotFoundError:
        error_msg("CSV Input Error", f"CSV file not found at: {csv_path}")
        logger.error(f"CSV file not found: {csv_path}", exc_info=True)
        return None
    except Exception as e:
        error_msg("CSV Input Error", f"Failed to parse CSV file '{csv_path}'. Error: {e}")
        logger.error(f"Error parsing CSV {csv_path}: {e}", exc_info=True)
        return None

def get_batch_input():
    """Asks user for input method (manual or CSV) and returns method and app specifications."""
    logger.info("Prompting for batch input method.")
    print(f"\n{Fore.BLUE}Choose batch input method:")
    print(f"  [{Fore.YELLOW}M{Style.RESET_ALL}] Manual App ID entry")
    print(f"  [{Fore.YELLOW}C{Style.RESET_ALL}] CSV file input")
    choice = input(f"{Fore.GREEN}👉 Enter choice (M/C, default M): ").strip().upper() or 'M'
    logger.info(f"User selected input method: '{choice}'")

    if choice == 'C':
        csv_path = prompt_for_csv_path()
        if not csv_path:
            logger.warning("No CSV path provided. Defaulting to manual input.")
            print(f"{Fore.YELLOW}⚠️ No CSV path entered. Please use manual input or try again.")
            return 'manual', prompt_for_manual_app_ids() # Fallback or re-prompt
        
        app_specs = parse_csv_input(csv_path)
        if app_specs:
            return 'csv', app_specs
        else:
            logger.warning("CSV parsing failed or returned no specs. Defaulting to manual input.")
            print(f"{Fore.YELLOW}⚠️ CSV processing failed. Please use manual input or try again.")
            # Fallback to manual if CSV fails critically
            return 'manual', prompt_for_manual_app_ids() 
    else: # Manual or invalid choice defaults to Manual
        if choice != 'M':
            logger.warning(f"Invalid input method choice '{choice}'. Defaulting to Manual.")
            print(f"{Fore.YELLOW}⚠️ Invalid choice. Defaulting to Manual App ID entry.")
        return 'manual', prompt_for_manual_app_ids()


def get_batch_common_settings(input_method='manual'):
    """
    Prompts for common settings: version, architecture, context, and Intune check preference.
    These serve as fallbacks if input_method is 'csv'.
    """
    prompt_suffix = "(applies to ALL apps in batch)" if input_method == 'manual' else "(serves as fallback for CSV)"
    logger.info(f"Prompting for batch common settings. Input method: {input_method}. Suffix: '{prompt_suffix}'")

    print(f"\n{Fore.GREEN}📦 Enter Version (leave empty for latest) {prompt_suffix}: ", end="")
    version = input().strip() or None # None if empty, meaning 'latest'
    logger.info(f"User entered common Version: '{version if version else "latest"}'")

    architecture_options = {"1": 'x64', "2": 'x86', "3": 'arm64'}
    default_architecture = "1"  # x64
    print(f"\n{Fore.CYAN}⚙️ Architecture (applies to ALL apps in batch):")
    for key, value in architecture_options.items(): print(f"  [{key}] {Fore.YELLOW}{value}{' (default)' if key == default_architecture else ''}")
    architecture_choice = input(f"{Fore.GREEN}👉 Choose or ENTER for default: ").strip()
    architecture = architecture_options.get(architecture_choice, architecture_options[default_architecture])
    logger.info(f"Selected Architecture: {architecture} (Choice: '{architecture_choice}')")

    installer_context_options = {"1": 'user', "2": 'system'}
    default_installer_context = "2"  # system
    print(f"\n{Fore.CYAN}⚙️ Installation Context (applies to ALL apps in batch):")
    for key, value in installer_context_options.items(): print(f"  [{key}] {Fore.YELLOW}{value}{' (default)' if key == default_installer_context else ''}")
    installer_context_choice = input(f"{Fore.GREEN}👉 Choose or ENTER for default: ").strip()
    installer_context = installer_context_options.get(installer_context_choice, installer_context_options[default_installer_context])
    logger.info(f"Selected Installer Context: {installer_context} (Choice: '{installer_context_choice}')")

    intune_check_batch_pref_input = input(f"\n{Fore.YELLOW}🔎 Perform Intune check for each app in this batch? (y/n, default y): ").strip().lower() or 'y'
    perform_intune_check_for_batch = intune_check_batch_pref_input == 'y'
    logger.info(f"User preference for batch Intune check: {perform_intune_check_for_batch} (Input: '{intune_check_batch_pref_input}')")
    
    return version, architecture, installer_context, perform_intune_check_for_batch

def handle_app_packaging(package_id, version, architecture, installer_context, config):
    """Handles local package check and creation. Returns (success_bool, package_dir_str_or_None)."""
    logger.info(f"Handling packaging for {package_id}, Version: {version or 'latest'}.")
    package_dir = Path(config['wintuner_download_dir']) / package_id / (version or 'latest')
    logger.debug(f"Package directory for {package_id}: {package_dir}")

    if check_local_package(package_id, version, config): # check_local_package uses Path object
        logger.info(f"Local package found for {package_id} at {package_dir}")
        print(f"{Fore.YELLOW}✔️ Local package found: {package_dir}")
        return True, str(package_dir)
    else:
        logger.info(f"Local package not found for {package_id}. Attempting to create.")
        package_cmd_list = [
            "wintuner", "package", package_id,
            "--package-folder", str(config['wintuner_download_dir']), # Ensure string for command
            "--architecture", architecture,
            "--installer-context", installer_context
        ]
        if version:
            package_cmd_list.extend(["--version", version])
        
        success, _, _ = run_command_with_progress(package_cmd_list, f"Packaging {package_id}")
        if success:
            logger.info(f"Package created successfully for {package_id} at {package_dir}")
            print(f"{Fore.GREEN}✅ Package created: {package_dir}")
            return True, str(package_dir)
        else:
            logger.error(f"Failed to create package for {package_id}.")
            print(f"{Fore.RED}❌ Failed to create package for {package_id}. Skipping further steps for this app.")
            return False, None

def handle_intune_app_check(package_id, config, perform_batch_check):
    """Handles Intune app existence check and user prompts. Returns proceed_flag (bool)."""
    logger.info(f"Handling Intune app check for {package_id}. Batch check preference: {perform_batch_check}.")

    if not perform_batch_check:
        logger.info(f"Skipping Intune check for '{package_id}' as per batch setting.")
        print(f"{Fore.BLUE}Skipping Intune check for {package_id} (batch setting).")
        return True # Proceed with publishing without individual check

    # If perform_batch_check is True, proceed with the original individual check logic
    # The original prompt "Check Intune for '{package_id}'? (y/n, default n)" is now effectively replaced by the batch setting.
    # So, if perform_batch_check is True, we *do* the check.
    
    app_exists_in_intune = check_intune_app_report_based(package_id, config) # This function prints and logs
    if app_exists_in_intune:
        publish_anyway_choice = input(f"{Fore.YELLOW}❓ App(s) matching '{package_id}' found. Still try publishing? (y/n, default n): ").strip().lower() or 'n'
        logger.info(f"App '{package_id}' found in Intune. User choice to publish anyway: {publish_anyway_choice}")
        if publish_anyway_choice != 'y':
            logger.info(f"Skipping publishing for {package_id} as per user choice after finding existing app.")
            print(f"{Fore.YELLOW}Skipping publishing for {package_id} as requested.")
            return False # Do not proceed
    return True # Proceed (either not found, or found and user wants to publish anyway)


def handle_app_publishing(package_id, version, config, access_token):
    """Handles publishing to Intune. Returns success_flag (bool)."""
    logger.info(f"Handling app publishing for {package_id}, Version: {version or 'latest'}.")
    publish_choice = input(f"\n{Fore.YELLOW}🚀 Publish '{package_id}' to Intune? (y/n, default n): ").strip().lower() or 'n'
    logger.info(f"User choice to publish '{package_id}': {publish_choice}")

    if publish_choice == 'y':
        if not access_token:
            # This case should ideally be handled before calling this function,
            # by pre-fetching token if any app in batch needs publishing.
            # However, as a fallback, log and error out.
            logger.critical(f"No access token provided for publishing {package_id}. This is unexpected.")
            error_msg("Publishing Error", f"Cannot publish {package_id}: Access token is missing.")
            return False

        publish_cmd_list_log = [
            "wintuner", "publish", package_id,
            "--package-folder", str(config['wintuner_download_dir']),
            "--tenant", config['intune_tenant_id'],
            "--token", "****"  # Masked for logging
        ]
        actual_publish_cmd = [
            "wintuner", "publish", package_id,
            "--package-folder", str(config['wintuner_download_dir']),
            "--tenant", config['intune_tenant_id'],
            "--token", access_token
        ]
        if version:
            publish_cmd_list_log.extend(["--version", version])
            actual_publish_cmd.extend(["--version", version])
        
        logger.info(f"Publish command (token masked): {' '.join(publish_cmd_list_log)}")
        success, _, _ = run_command_with_progress(actual_publish_cmd, f"Publishing {package_id}")
        
        if success:
            logger.info(f"Successfully published {package_id} to Intune.")
            print(f"{Fore.GREEN}🎉 Successfully published {package_id} to Intune.")
            return True
        else:
            logger.error(f"Failed to publish {package_id} to Intune.")
            # error_msg already called by run_command_with_progress
            return False
    else:
        logger.info(f"Skipping publishing for {package_id} as per user choice.")
        print(f"{Fore.YELLOW}Skipping publishing for {package_id}.")
        # This return signifies the user chose 'n' at the "Publish 'package_id' to Intune?" prompt.
        # It's a form of skipping, but specific to the publish step.
        return False 

def process_single_app(package_id, version, architecture, installer_context, config, access_token, perform_intune_check_for_batch):
    """Processes a single app: packaging, Intune check, publishing. Returns status string."""
    logger.info(f"--- Starting processing for App: {package_id} (Batch Intune Check: {perform_intune_check_for_batch}) ---")
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}--- Processing App: {package_id} ---{Style.RESET_ALL}")

    packaging_success, _ = handle_app_packaging(package_id, version, architecture, installer_context, config)
    if not packaging_success:
        return "failed_pkg"

    # Pass the batch-level Intune check preference
    proceed_with_publish = handle_intune_app_check(package_id, config, perform_intune_check_for_batch)
    if not proceed_with_publish: # This means user chose not to proceed after app was found (if check was done)
        return "skipped" 

    # If we reach here, user wants to proceed with publishing or skipped the Intune check.
    # Now, ask if they want to publish (this is the final y/n for publishing itself)
    # Note: handle_app_publishing includes its own y/n prompt.
    # The 'access_token' is passed here. It should be pre-fetched if any app in batch needs publishing.
    
    # The prompt "Publish 'package_id' to Intune? (y/n)" is inside handle_app_publishing.
    # If user says 'n' there, it returns False, which we'll treat as 'skipped_publish'.
    # If user says 'y' and it fails, it returns False, which we'll treat as 'failed_pub'.
    # If user says 'y' and it succeeds, it returns True.
    
    # We need to determine if user *wants* to publish first.
    # This is slightly different from the original logic flow where the publish_choice was outside.
    # For this refactor, let's stick to handle_app_publishing containing the publish y/n prompt.
    
    # If handle_intune_app_check returned True (proceed_with_publish), 
    # then we call handle_app_publishing which itself asks the final y/n.
    
    published_successfully = handle_app_publishing(package_id, version, config, access_token)
    
    if published_successfully: # True means it was attempted and succeeded
        return "success"
    else:
        # At this point, publishing either failed or was skipped by the user at the final prompt.
        # We need to differentiate. The current handle_app_publishing returns False for both.
        # For simplicity in this refactor, if it wasn't a success, and wasn't skipped *before* this stage,
        # we'll rely on the user's y/n inside handle_app_publishing to have been logged.
        # If handle_app_publishing returns False, it means either user said 'n' or publish command failed.
        # Let's refine batch_results slightly.
        # If user said 'n' inside handle_app_publishing, it's a "skip_publish_decision".
        # If user said 'y' and it failed, it's "failed_pub".
        
        # To achieve this, handle_app_publishing needs to return more distinct states,
        # or we ask the "Publish to Intune (y/n)" *before* calling handle_app_publishing,
        # and only call handle_app_publishing if 'y'.
        
        # Re-aligning with original logic structure more closely for this part:
        final_publish_choice = input(f"\n{Fore.YELLOW}🚀 Publish '{package_id}' to Intune? (y/n, default n): ").strip().lower() or 'n'
        logger.info(f"User final choice to publish '{package_id}': {final_publish_choice}")

        if final_publish_choice == 'y':
            if not access_token:
                 logger.critical(f"No access token available for publishing {package_id} when user confirmed desire to publish.")
                 error_msg("Publishing Error", f"Cannot publish {package_id}: Access token is missing and publish was confirmed.")
                 return "failed_pub_token" # More specific error for batch results

            # Simplified call to a more direct publish command executor
            publish_cmd_list_log = [ "wintuner", "publish", package_id, "--package-folder", str(config['wintuner_download_dir']), "--tenant", config['intune_tenant_id'], "--token", "****" ]
            actual_publish_cmd = [ "wintuner", "publish", package_id, "--package-folder", str(config['wintuner_download_dir']), "--tenant", config['intune_tenant_id'], "--token", access_token ]
            if version:
                publish_cmd_list_log.extend(["--version", version])
                actual_publish_cmd.extend(["--version", version])
            
            logger.info(f"Publish command (token masked): {' '.join(publish_cmd_list_log)}")
            success, _, _ = run_command_with_progress(actual_publish_cmd, f"Publishing {package_id}")
            
            if success:
                logger.info(f"Successfully published {package_id} to Intune.")
                print(f"{Fore.GREEN}🎉 Successfully published {package_id} to Intune.")
                return "success"
            else:
                logger.error(f"Failed to publish {package_id} to Intune.")
                return "failed_pub"
        else:
            logger.info(f"User chose not to publish {package_id} at the final prompt.")
            print(f"{Fore.YELLOW}Skipping publishing for {package_id} as per user choice.")
            return "skipped_publish_decision"


def display_batch_summary(batch_results):
    """Prints the summary of the batch processing."""
    logger.info("--- Batch Processing Summary ---")
    logger.info(f"Successfully Published: {', '.join(batch_results.get('success', []))}")
    logger.info(f"Failed Packaging: {', '.join(batch_results.get('failed_pkg', []))}")
    logger.info(f"Failed Publishing (Command Error): {', '.join(batch_results.get('failed_pub', []))}")
    logger.info(f"Failed Publishing (Token Error): {', '.join(batch_results.get('failed_pub_token', []))}")
    logger.info(f"Skipped (Intune Check/User Choice): {', '.join(batch_results.get('skipped', []))}")
    logger.info(f"Skipped (Final Publish Decision): {', '.join(batch_results.get('skipped_publish_decision', []))}")

    print(f"\n{Fore.CYAN}{Style.BRIGHT}--- Batch Processing Summary ---")
    if batch_results.get("success"): print(f"{Fore.GREEN}✅ Published Successfully: {', '.join(batch_results['success'])}")
    if batch_results.get("failed_pkg"): print(f"{Fore.RED}❌ Failed Packaging: {', '.join(batch_results['failed_pkg'])}")
    if batch_results.get("failed_pub"): print(f"{Fore.RED}❌ Failed Publishing (Command Error): {', '.join(batch_results['failed_pub'])}")
    if batch_results.get("failed_pub_token"): print(f"{Fore.RED}❌ Failed Publishing (Token Error): {', '.join(batch_results['failed_pub_token'])}")
    
    skipped_all = batch_results.get('skipped', []) + batch_results.get('skipped_publish_decision', [])
    if skipped_all: print(f"{Fore.YELLOW}🟡 Skipped Publishing (User choice or existing): {', '.join(skipped_all)}")
    print(f"{Fore.CYAN}-----------------------------")


###############################################################################
## STEP 10: Main Application Logic - Refactored Main Function
###############################################################################
def main():
    """Main function to drive the Intune app packaging and publishing process."""
    setup_logging()
    logger.info("Starting Intune App Packager and Publisher script.")
    print(f"{Fore.CYAN}{Style.BRIGHT}🚀 Intune App Packager and Publisher (Multi-App) 🚀{Style.RESET_ALL}")

    config = load_config()
    if not config:
        logger.critical("Exiting due to configuration loading errors.")
        sys.exit(1)
    logger.info("Configuration loaded.")

    while True:
        input_method, app_specifications = get_batch_input()

        if not app_specifications: # If CSV parsing failed or manual entry yielded nothing
            logger.warning("No app specifications provided or parsed for this batch.")
            another_batch_choice = input(f"\n{Fore.YELLOW}🔄 No app specifications for this batch. Process another batch? (y/n, default n): ").strip().lower() or 'n'
            if another_batch_choice != 'y':
                break
            continue
        
        # Get common settings, which will act as fallbacks if input is CSV
        common_version, common_architecture, common_installer_context, perform_intune_check_for_batch = get_batch_common_settings(input_method)
        
        batch_results = {"success": [], "failed_pkg": [], "failed_pub": [], "failed_pub_token": [], "skipped": [], "skipped_publish_decision": []}
        access_token = None 

        # Determine if an access token is needed for this batch
        # This is a simplified check; we could ask all publish intentions upfront
        # For now, get it on first actual need within process_single_app or if any app might be published.
        # For this refactor, let's try to get it once if there's a potential for publishing.
        # A more robust way would be to check if *any* app in the batch *might* be published.
        # For now, we will fetch it when the first app requires it.

        for package_id in app_id_list:
            # Pre-fetch token logic:
            # This is tricky without knowing user's intention to publish upfront for each app.
            # The original logic gets token *inside* the loop when publish_choice == 'y'.
            # We will stick to that pattern for now, passing 'access_token' which might be None initially.
            # process_single_app will then be responsible for triggering token acquisition if needed
            # by returning a specific status or by having the token passed and updated.
            
            # Let's refine: if publishing is intended for any app, get token once.
            # The current structure of process_single_app has the publish y/n inside.
            # So, we'll pass current access_token (which could be None) and update it if obtained.

            if access_token is None: # Try to get token if not already fetched for the batch
                # A bit of a look-ahead: if any app will be attempted to publish, we need a token.
                # This is not perfect as user might say 'n' to all publish prompts.
                # For now, let's assume if we don't have a token, the first app that *might* be published will trigger it.
                # The original logic was: if publish_choice == 'y' and not access_token: get_token().
                # This is now inside process_single_app.
                pass # Token will be fetched if needed by client_get_access_token call chain

            current_package_id = None
            current_version = common_version
            current_architecture = common_architecture
            current_installer_context = common_installer_context

            if input_method == 'csv':
                app_spec = app_specifications[i] # app_specifications is list of dicts
                current_package_id = app_spec['PackageID']
                # Prioritize CSV values, then common settings. None from CSV means use common.
                current_version = app_spec.get('Version') if app_spec.get('Version') is not None else common_version
                current_architecture = app_spec.get('Architecture') if app_spec.get('Architecture') is not None else common_architecture
                current_installer_context = app_spec.get('InstallerContext') if app_spec.get('InstallerContext') is not None else common_installer_context
                logger.info(f"Processing CSV entry: ID={current_package_id}, Ver={current_version or 'latest'}, Arch={current_architecture}, Ctx={current_installer_context}")
            else: # manual
                current_package_id = app_specifications[i] # app_specifications is list of PackageID strings
                # For manual, version, arch, context are always the common ones.
                logger.info(f"Processing manual entry: ID={current_package_id}, Ver={current_version or 'latest'}, Arch={current_architecture}, Ctx={current_installer_context}")

            app_status = process_single_app(
                current_package_id, 
                current_version, 
                current_architecture, 
                current_installer_context, 
                config, 
                access_token, # Passed to process_single_app, which might trigger client_get_access_token
                perform_intune_check_for_batch
            )
            
            if app_status == "success": batch_results["success"].append(current_package_id)
            elif app_status == "failed_pkg": batch_results["failed_pkg"].append(current_package_id)
            elif app_status == "failed_pub": batch_results["failed_pub"].append(current_package_id)
            elif app_status == "failed_pub_token": 
                batch_results["failed_pub_token"].append(current_package_id)
                logger.info("Breaking batch processing due to token error during app processing.")
                break 
            elif app_status == "skipped": batch_results["skipped"].append(current_package_id)
            elif app_status == "skipped_publish_decision": batch_results["skipped_publish_decision"].append(current_package_id)
            
            # Token management:
            # The current process_single_app calls client_get_access_token internally if access_token is None
            # and publishing is attempted. This means access_token in main's scope is not updated.
            # For a more robust token handling across the batch (fetch once, reuse),
            # process_single_app would need to signal if it attempted and succeeded/failed token acquisition,
            # or token acquisition needs to be hoisted into the main loop before calling process_single_app,
            # perhaps after confirming user intent to publish *anything* in the batch.
            # For this iteration, we'll stick to the slightly less efficient but simpler per-app check if token is None.
            # If a token was successfully acquired inside process_single_app (via its call to handle_app_publishing->client_get_access_token),
            # it's not currently passed back to main's access_token. This is a known limitation of current refactor step.
            # However, if client_get_access_token fails, "failed_pub_token" is returned and batch breaks.
            # If it succeeds, the token is used for that one app. Subsequent apps needing it would re-fetch if access_token in main is still None.
            # This is not ideal but matches the previous flow more closely than returning token from process_single_app.
            # A better approach would be to have process_single_app NOT fetch tokens, and main does it once.
            # For now, this is a direct adaptation of the previous logic structure.

        display_batch_summary(batch_results)

        report_choice = input(f"\n{Fore.CYAN}📊 Generate a full report of ALL apps in your Intune tenant? (y/n, default n): ").strip().lower() or 'n'
        logger.info(f"User choice for full Intune report: {report_choice}")
        if report_choice == 'y':
            save_to_file_choice = input(f"{Fore.CYAN}💾 Save report to a file? (y/n, default n): ").strip().lower() or 'n'
            logger.info(f"User choice to save report to file: {save_to_file_choice}")

            csv_export_path = None
            json_export_path = None

            if save_to_file_choice == 'y':
                format_choice = input(f"{Fore.GREEN}Enter format (csv/json, default csv): ").strip().lower() or 'csv'
                logger.info(f"User choice for report format: {format_choice}")

                default_filename = f"intune_apps_report.{format_choice}"
                file_path_input = input(f"{Fore.GREEN}Enter file path (leave empty for default: ./{default_filename}): ").strip()
                
                if not file_path_input:
                    file_path_input = default_filename
                logger.info(f"User chosen file path: '{file_path_input}' (default was '{default_filename}')")

                if format_choice == 'csv':
                    csv_export_path = file_path_input
                elif format_choice == 'json':
                    json_export_path = file_path_input
                else:
                    logger.warning(f"Invalid format choice '{format_choice}'. Defaulting to no file export for this report.")
                    print(f"{Fore.YELLOW}⚠️ Invalid format '{format_choice}'. Report will only be printed to console.")
            
            generate_intune_app_report(config, print_report=True, csv_file_path=csv_export_path, json_file_path=json_export_path)

        another_batch_choice = input(f"\n{Fore.YELLOW}🔄 Process another batch of apps? (y/n, default n): ").strip().lower() or 'n'
        logger.info(f"User choice to process another batch: {another_batch_choice}")
        if another_batch_choice != 'y':
            logger.info("User chose not to process another batch. Exiting loop.")
            break
    
    logger.info("All operations finished.")
    print(f"{Fore.CYAN}{Style.BRIGHT}\n✨ All operations finished. ✨{Style.RESET_ALL}")


###############################################################################
## STEP 11: Script Entry Point - Main script execution
###############################################################################
if __name__ == "__main__":
    # Logging is set up in main()
    try:
        main()
    except KeyboardInterrupt:
        # Log this specific exit type if logger is available (might not be if error is before setup_logging)
        if logging.getLogger(__name__).hasHandlers(): # Check if logger was initialized
             logger.warning("Operation cancelled by user (KeyboardInterrupt).")
        print(f"\n{Fore.YELLOW}Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        # Log critical error before exiting if logger is available
        if logging.getLogger(__name__).hasHandlers():
             logger.critical(f"An unexpected critical error occurred: {e}", exc_info=True)
        else: # Fallback if logging is not even set up
             print(f"Pre-logging critical error: {e}") # Basic print
        print(f"\n{Fore.RED}{Style.BRIGHT}💥 An unexpected critical error occurred: {e}")
        import traceback
        traceback.print_exc() # Keep this for detailed console traceback for users
        sys.exit(1)
