import json
import os
import urllib.request
import urllib.parse
import urllib.error
from colorama import Fore, init, Style
import logging
import sys
import csv # Added for CSV export

init(autoreset=True)

# Global logger instance
logger = logging.getLogger(__name__)

###############################################################################
# Logging Setup
###############################################################################
def setup_logging(log_file_name="intune_report.log"):
    """Configures logging for the Report script."""
    logger.setLevel(logging.INFO)  # General logging level for the logger

    # File Handler - logs INFO and higher
    try:
        file_handler = logging.FileHandler(log_file_name, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback to console if file logging setup fails
        print(f"{Fore.RED}Failed to set up file logging to {log_file_name}: {e}{Style.RESET_ALL}", file=sys.stderr)
        # Basic console logging setup as a fallback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        logger.error(f"File logging setup failed. Using console logging only. Error: {e}", exc_info=True)


    logger.info("Report script logging initialized.")

# Import functions from the new intune_client module
from intune_client import get_access_token as client_get_access_token
from intune_client import get_intune_apps as client_get_intune_apps
from intune_client import determine_platform as client_determine_platform

from pathlib import Path # Added for path operations

def load_config(config_file="config.json"):
    """Load configurations, prioritizing environment variables for sensitive data."""
    config = {}
    errors = []
    # Determine script directory to robustly locate config.json
    # Assuming Report.py is in the same directory as publish_installer.py and config.json
    script_directory = Path(__file__).resolve().parent
    config_path = script_directory / config_file

    # Load sensitive data from environment variables first
    config['intune_tenant_id'] = os.environ.get('INTUNE_TENANT_ID')
    config['intune_client_id'] = os.environ.get('INTUNE_CLIENT_ID')
    config['intune_client_secret'] = os.environ.get('INTUNE_CLIENT_SECRET')

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

    # Non-sensitive configurations (if Report.py needs any, add them here)
    # For now, Report.py primarily needs credentials.
    # Example if it needed wintuner_download_dir:
    # config['wintuner_download_dir'] = config_from_file.get('wintuner_download_dir', str(script_directory / 'wintuner_downloads'))
    # Path(config['wintuner_download_dir']).mkdir(parents=True, exist_ok=True) # Ensure dir exists

    if errors:
        for err in errors:
            error_msg("Configuration Error", err) # This will now log and print
        logger.error(f"Configuration failed with errors for Report.py: {'; '.join(errors)}")
        return None
    logger.info("Configuration loaded successfully for Report.py.")
    return config

# get_access_token, get_intune_apps, and determine_platform are now imported from intune_client
# The local versions of these functions are removed from Report.py

def _prepare_report_data(apps_list):
    """Prepares structured data for reporting from raw Intune app data."""
    if not apps_list:
        logger.info("No raw app data to prepare for report.")
        return []

    logger.info(f"Preparing report data for {len(apps_list)} raw app entries.")
    prepared_data = []
    for app in apps_list:
        # Using originalDisplayName as 'Name' for the report, similar to publish_installer.py's CSV export
        name = app.get('displayName', 'N/A') # 'originalDisplayName' is not consistently available in all app types from Graph API
        platform = client_determine_platform(app.get('@odata.type', ''))
        version = app.get('displayVersion', 'N/A') or app.get('committedContentVersion', 'N/A') or app.get('appVersion', 'N/A') or 'N/A'
        # VPP Token Name: Use 'vppTokenAppleId' for iOS VPP apps, otherwise N/A
        vpp_token_name = app.get('vppTokenAppleId', 'N/A') if platform == "iOS VPP" else 'N/A' # Corrected platform check
        assigned = 'Yes' if app.get('isAssigned') else 'No' # Assuming 'isAssigned' field exists
        developer = app.get('publisher', 'N/A')
        app_id = app.get('id', 'N/A')

        prepared_data.append({
            "Name": name,
            "Platform": platform,
            "Version": version,
            "VPP Token Name": vpp_token_name,
            "Assigned": assigned,
            "Developer": developer,
            "ID": app_id # Added ID field
        })
    logger.info(f"Successfully prepared {len(prepared_data)} items for the report.")
    return prepared_data

def generate_report(apps_raw_data, csv_file_path: str = None, json_file_path: str = None):
    """Generates, prints, and optionally saves the Intune app report."""
    logger.info(f"Generating Intune app report. CSV: '{csv_file_path}', JSON: '{json_file_path}' (Report.py)")
    
    report_data = _prepare_report_data(apps_raw_data)

    if not report_data:
        logger.warning("No apps found to generate or save report. (Report.py)")
        print(f"{Fore.YELLOW}⚠️ No apps found to report.") # Keep console output
        return

    # Console Printing Logic (remains mostly the same, uses report_data)
    col_widths = { "Name": 32, "Platform": 12, "Version": 10, "VPP Token Name": 17, "Assigned": 10, "Developer": 24, "ID": 36 } # Added ID width
    border_line = "+" + "+".join(["-" * (width + 2) for width in col_widths.values()]) + "+"
    
    report_lines = []
    report_lines.append(Fore.CYAN + "Intune Application Report:")
    report_lines.append(border_line)
    header_str = "|" + "".join([f" {col_name:<{width}} |" for col_name, width in col_widths.items()])
    report_lines.append(header_str)
    report_lines.append(border_line)

    for app_detail in report_data:
        row = "|"
        for col_name, width in col_widths.items():
            value = app_detail.get(col_name, 'N/A')
            row += f" {str(value)[:width]:<{width}} |" # Ensure value is string and truncated
        report_lines.append(row)
        report_lines.append(border_line)
    
    print("\n".join(report_lines))
    logger.info("Successfully printed app report to console. (Report.py)")

    # Save to CSV
    if csv_file_path and report_data:
        try:
            # Use the keys from the first item in report_data as fieldnames
            # This ensures we use the same keys as _prepare_report_data provided
            fieldnames = list(report_data[0].keys()) 
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(report_data)
            logger.info(f"Intune app report successfully saved to CSV: {csv_file_path} (Report.py)")
            print(f"{Fore.GREEN}📊 Report saved to CSV: {csv_file_path}")
        except IOError as e:
            logger.error(f"IOError saving report to CSV '{csv_file_path}': {e} (Report.py)", exc_info=True)
            error_msg("CSV Export Error", f"Could not write CSV file to '{csv_file_path}'. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving report to CSV '{csv_file_path}': {e} (Report.py)", exc_info=True)
            error_msg("CSV Export Error", f"An unexpected error occurred while writing CSV to '{csv_file_path}'. Error: {e}")
    elif csv_file_path and not report_data:
         logger.warning(f"CSV export requested to '{csv_file_path}', but no report data was generated. (Report.py)")

    # Save to JSON
    if json_file_path and report_data:
        try:
            with open(json_file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(report_data, jsonfile, indent=4)
            logger.info(f"Intune app report successfully saved to JSON: {json_file_path} (Report.py)")
            print(f"{Fore.GREEN}📊 Report saved to JSON: {json_file_path}")
        except IOError as e:
            logger.error(f"IOError saving report to JSON '{json_file_path}': {e} (Report.py)", exc_info=True)
            error_msg("JSON Export Error", f"Could not write JSON file to '{json_file_path}'. Error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving report to JSON '{json_file_path}': {e} (Report.py)", exc_info=True)
            error_msg("JSON Export Error", f"An unexpected error occurred while writing JSON to '{json_file_path}'. Error: {e}")
    elif json_file_path and not report_data:
        logger.warning(f"JSON export requested to '{json_file_path}', but no report data was generated. (Report.py)")

def error_msg(step, error_details):
    """Prints a formatted error message to console and logs it as an error."""
    logger.error(f"Error during {step}: {error_details}") # Log first
    # Then print to console
    print(f"\n{Fore.RED}{Style.BRIGHT}❌ Error during {step}:{Style.RESET_ALL}") # Added Style.BRIGHT
    error_lines = str(error_details).splitlines()
    for line in error_lines:
        print(f"  {Fore.YELLOW}{line}")

def main():
    setup_logging() # Initialize logging
    logger.info("Starting Intune App Report script.")
    print(f"{Fore.CYAN}{Style.BRIGHT}Initializing Intune App Report script...{Style.RESET_ALL}") # Keep console

    config = load_config()
    if not config:
        logger.critical("Exiting Report script due to configuration loading errors.")
        # error_msg already called by load_config
        sys.exit(1) # Exit if config fails
    
    logger.info("Authenticating...")
    print(f"{Fore.BLUE}Authenticating...{Style.RESET_ALL}")
    
    # Call the imported client_get_access_token
    token = client_get_access_token(
        tenant_id=config.get('intune_tenant_id'),
        client_id=config.get('intune_client_id'),
        client_secret=config.get('intune_client_secret')
    )
    
    if not token:
        logger.critical("Exiting Report script due to authentication failure (token retrieval via intune_client failed).")
        # Error message for console, as client_get_access_token only logs
        error_msg("MSAL Authentication Error", "Failed to obtain access token. Check logs from intune_client for details.")
        sys.exit(1)

    logger.info("Retrieving app information from Intune... (Report.py)")
    print(f"{Fore.CYAN}Retrieving app information from Intune...{Style.RESET_ALL}")
    
    apps_raw = client_get_intune_apps(token, package_id_filter=None) 
    
    if apps_raw is None:
        logger.error("Failed to retrieve apps from Intune via intune_client. Cannot generate report. (Report.py)")
        error_msg("Intune Data Retrieval Error", "Failed to retrieve app list from Intune. Check logs from intune_client for details.")
        sys.exit(1)

    # Ask user if they want to save the report
    save_file_choice = input(f"\n{Fore.CYAN}💾 Save full report to a file? (y/n, default n): ").strip().lower() or 'n'
    logger.info(f"User choice to save full report to file: {save_file_choice}")

    csv_export_path = None
    json_export_path = None

    if save_file_choice == 'y':
        format_choice = input(f"{Fore.GREEN}Enter format (csv/json, default csv): ").strip().lower() or 'csv'
        logger.info(f"User choice for full report format: {format_choice}")

        default_filename = f"intune_full_report.{format_choice}"
        file_path_input = input(f"{Fore.GREEN}Enter file path (leave empty for default: ./{default_filename}): ").strip()
        
        if not file_path_input:
            file_path_input = default_filename
        logger.info(f"User chosen file path for full report: '{file_path_input}' (default was '{default_filename}')")

        if format_choice == 'csv':
            csv_export_path = file_path_input
        elif format_choice == 'json':
            json_export_path = file_path_input
        else:
            logger.warning(f"Invalid format choice '{format_choice}'. Report will only be printed to console.")
            print(f"{Fore.YELLOW}⚠️ Invalid format '{format_choice}'. Report will only be printed to console.")
            
    # Call generate_report with the raw apps data and optional file paths
    generate_report(apps_raw, csv_file_path=csv_export_path, json_file_path=json_export_path)
    
    logger.info("Intune App Report script finished.")

if __name__ == "__main__":
    # Logging is set up in main()
    try:
        main()
    except KeyboardInterrupt:
        if logging.getLogger(__name__).hasHandlers():
             logger.warning("Operation cancelled by user (KeyboardInterrupt) in Report script.")
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        if logging.getLogger(__name__).hasHandlers():
             logger.critical(f"An unexpected critical error occurred in Report script: {e}", exc_info=True)
        else: # Fallback if logging is not even set up
             print(f"Pre-logging critical error in Report script: {e}", file=sys.stderr)
        print(f"\n{Fore.RED}{Style.BRIGHT}💥 An unexpected critical error occurred: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
