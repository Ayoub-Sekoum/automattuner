# Automation of App Upload with WinTuner 🚀

![Intune Application Publisher](https://github.com/Ayoub-Sekoum/automattuner/blob/main/foto.jpg)

[![Watch the video](https://img.youtube.com/vi/JpIa12gXjiw/0.jpg)](https://youtu.be/JpIa12gXjiw)

## Overview

This project provides Python scripts to automate the process of packaging applications from the Winget repository and publishing them to Microsoft Intune. It leverages the `WinTuner` tool to streamline application management, making it easier to deploy and update software across your organization.

The primary scripts are:
- `publish_installer.py`: An interactive script for packaging and publishing applications, with options for batch processing via manual input or CSV file.
- `Report.py`: A script to generate a report of all applications currently in your Intune environment.

## Features ✨

- 📦 **Automatic Packaging:** Creates Intune-compatible `.intunewin` packages directly from Winget.
- ☁️ **Direct Intune Publishing:** Uploads and configures applications in your Intune environment.
- 🔄 **Dependency Management:** (Where supported by Winget manifests) Handles application dependencies.
- 批量 **Batch Processing:** Process multiple applications using manual input or a CSV file for detailed specifications.
- 📊 **Interactive CLI:** User-friendly interface guides you through the packaging and publishing process.
- 🔍 **Duplicate Detection:** Option to check for existing versions in Intune to help prevent conflicts.
- 📄 **Detailed Reporting:**
    - `publish_installer.py` can generate a report of all Intune applications, with options to save as CSV or JSON.
    - `Report.py` generates a comprehensive console report of all Intune applications, also with CSV/JSON export options.
- 🔐 **Secure Authentication:** Uses Azure AD application registration for secure API access to Intune.
- 📝 **Logging:** Detailed logging for troubleshooting and monitoring operations for both scripts.
- 🧪 **Unit Tests:** Includes unit tests for the core Intune client API interaction logic.

## Prerequisites 📋

### 1. System Requirements
- Windows Operating System (as WinTuner and Winget are Windows-based)
- PowerShell 7+ (Recommended: `winget install Microsoft.Powershell`)
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) (Verify if a newer version is specified in `install_requirements.py` if available)
- [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (Windows Package Manager, built into modern Windows versions)

### 2. Python Environment
- Python 3.8+
- Required Python packages (install via `pip install -r requirements.txt` if a `requirements.txt` file is provided, or install individually):
    - `colorama`
    - `alive-progress`
    - (Verify `install_requirements.py` for any other specific package versions if needed)

### 3. Software Dependencies
The script relies on the WinTuner CLI. Install it globally using:
```powershell
# Install .NET 8 SDK first if not already present
winget install Microsoft.DotNet.SDK.8

# Then install WinTuner CLI
dotnet tool install --global SvRooij.Winget-Intune.Cli
```
Ensure WinTuner is accessible in your system's PATH.

### 4. Azure AD Configuration
An Azure AD application registration is required for the scripts to interact with Microsoft Intune via the Graph API.

- **Register an Application**: Create a new application registration in the Azure Portal for your tenant.
- **API Permissions**: Assign the following **Application permissions** to your registered app:
    - `DeviceManagementApps.ReadWrite.All` (Allows managing Intune applications)
    - `Group.Read.All` (Often needed for assignments, can be restricted if not using group assignments via script)
    - `User.Read.All` (May be needed for some scenarios, evaluate if necessary for your use case)
    *(Review these permissions. `Application.ReadWrite.All` is very broad. `DeviceManagementServiceConfig.ReadWrite.All` might also be listed in some older guides but might not be strictly necessary for app management only. Always apply the principle of least privilege.)*
- **Important**: An administrator must grant **admin consent** for these permissions in the Azure Portal.
- **Client Secret**: Create a client secret for your application. **Record this secret value immediately and store it securely**; you won't be able to see it again after leaving the page.

**Credentials to Note:**
- Tenant ID (Your Azure AD Directory/Tenant ID)
- Client ID (The Application (Client) ID of your registered app)
- Client Secret (The value of the client secret you created)

## Initial Setup & Configuration ⚙️

### 1. Sensitive Credentials: Environment Variables (Highly Recommended)
For sensitive information like your Tenant ID, Client ID, and Client Secret, using environment variables is the most secure method.
Set the following environment variables in your system where you will run the scripts:

- `INTUNE_TENANT_ID`: Your Azure AD Tenant ID.
- `INTUNE_CLIENT_ID`: The Application (Client) ID of your Azure AD registered application.
- `INTUNE_CLIENT_SECRET`: The Client Secret value for your Azure AD registered application.

**These environment variables take precedence over any values specified in `config.json`.**

### 2. Configuration File: `config.json`
This file is used for non-sensitive configurations and as an **optional fallback** for credentials if environment variables are not set.

Create a file named `config.json` in the root directory of the project.

**Example `config.json`:**
```json
{
  "intune_tenant_id": "YOUR_TENANT_ID_IF_NOT_SET_AS_ENV_VAR",
  "intune_client_id": "YOUR_CLIENT_ID_IF_NOT_SET_AS_ENV_VAR",
  "intune_client_secret": "YOUR_CLIENT_SECRET_IF_NOT_SET_AS_ENV_VAR",
  "wintuner_download_dir": "wintuner_downloads",
  "temp_package_dir": "temp_packages"
}
```

**Explanation:**
- **`intune_tenant_id`, `intune_client_id`, `intune_client_secret`**:
    - These are **optional** in `config.json` if you have set the corresponding environment variables.
    - If environment variables are **not** set, the script will use values from this file.
    - **Critical:** If these values are missing from both environment variables and `config.json`, the scripts will fail.
- **`wintuner_download_dir`**:
    - Specifies the directory where WinTuner will download installers and create `.intunewin` packages.
    - Defaults to `wintuner_downloads` in the script's directory if not specified.
    - Ensure this directory exists or the script has permissions to create it.
- **`temp_package_dir`**:
    - Specifies a temporary directory for package processing (used by `publish_installer.py`).
    - Defaults to `temp_packages` in the script's directory if not specified.

**Security Note:** If you use `config.json` for sensitive fallback credentials, **DO NOT commit this file to version control (e.g., Git)**. It's best practice to rely on environment variables for all sensitive data.

### 3. `.gitignore`
Ensure `config.json` and log files are listed in your `.gitignore` file:
```
# Configuration files (if containing secrets)
config.json

# Log files
*.log
intune_publisher.log
intune_report.log

# Python virtual environment
env/
venv/
*.venv/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
```

## Usage 🚀

### `publish_installer.py` - Packaging and Publishing
This script is designed for interactive use to package Winget applications and publish them to Intune.

**Batch Processing Input Methods:**
The script will first ask you to choose your input method for the batch:
1.  **[M] Manual Entry:**
    *   You'll be prompted to enter a comma-separated list of Package IDs (e.g., `Mozilla.Firefox,Zoom.Zoom`).
    *   Then, you'll define common settings (Version, Architecture, Installer Context, Intune Check preference) that will apply to **all** applications in that manually entered list.
2.  **[C] CSV File Input:**
    *   Provide a path to a CSV file detailing the applications. This allows for per-app settings within the batch.
    *   **CSV Format:**
        *   Must include a header row.
        *   **Required Column:** `PackageID` (Winget package identifier).
        *   **Optional Columns:** `Version`, `Architecture`, `InstallerContext`.
        *   If optional columns are blank for a row, the script uses the common settings (prompted next) as fallbacks for that specific app.
        *   Example:
            ```csv
            PackageID,Version,Architecture,InstallerContext
            Mozilla.Firefox,,x64,system
            Zoom.Zoom,latest,x64,user
            Microsoft.VisualStudioCode,1.80.0,,
            ```
    *   **Common Settings as Fallbacks (for CSV):** Even with CSV input, you'll be prompted for common settings (Version, etc.). These are used for any app in the CSV where the corresponding optional field is blank.

**Interactive Prompts per App:**
Regardless of input method, for each application, the script may prompt for:
- **Packaging:** If not already packaged locally.
- **Intune Check:** Optionally checks if the app exists in Intune (this can be set for the whole batch).
- **Publishing:** Confirms before publishing to Intune.

### `Report.py` - Generating Intune Application Report
This script connects to Intune and generates a report of all applications.
- It will output the report to the console.
- It will also prompt if you wish to save the report to a file (CSV or JSON format).

---

## Running Tests 🧪
Unit tests are provided for the `intune_client.py` module to ensure the core API interaction logic is working correctly.

To run the tests:
1.  Navigate to the root directory of the project in your terminal.
2.  Execute the following command:
    ```bash
    python -m unittest discover tests
    ```
    Alternatively, you can run a specific test file:
    ```bash
    python -m unittest tests.test_intune_client
    ```
This will discover and run all tests within the `tests` directory. Ensure you have any necessary testing libraries installed (though these tests primarily use the built-in `unittest` and `unittest.mock`).

---

## Logging 📝

Both scripts feature detailed logging to aid in monitoring and troubleshooting.
- **Log Files:**
    - `publish_installer.py` logs to `intune_publisher.log`.
    - `Report.py` logs to `intune_report.log`.
    - Files are created in the script's execution directory.
- **Content:** Logs include timestamps, severity levels, source file details, and messages.
- **Usage:** Check these logs for detailed error information and operational history if you encounter issues.

---

## Best Practices & Recommendations

### Security
- ⭐ **Environment Variables for Credentials:** This is the most secure way to handle `INTUNE_TENANT_ID`, `INTUNE_CLIENT_ID`, and `INTUNE_CLIENT_SECRET`. Avoid hardcoding them.
- **`config.json` Security:** If using `config.json` for fallback credentials, ensure its file permissions are restricted. Do not commit it to version control if it contains secrets.
- **Log File Security:** Log files (`intune_publisher.log`, `intune_report.log`) may contain details about your operations and environment. Protect them appropriately (e.g., restrict access, include in `.gitignore`).
- **Azure AD App Permissions:** Adhere to the principle of least privilege. Only grant the necessary API permissions to your Azure AD registered application. Regularly review these permissions.

### Usage
- **Test Thoroughly:** Before running on many applications, test with a single app or a small, non-critical batch to ensure configuration and functionality are correct.
- **CSV for Larger Batches:** For managing numerous applications or when individual settings per app (like version) are crucial, the CSV input method for `publish_installer.py` is recommended.
- **Consult Log Files:** If you encounter errors or unexpected behavior, the first place to check is the relevant log file (`intune_publisher.log` or `intune_report.log`).
- **Keep Dependencies Updated:** Regularly update WinTuner CLI and the .NET SDK to their latest stable versions to benefit from new features and security patches.

### Configuration
- **Download Directory:** Ensure the directory specified by `wintuner_download_dir` (in `config.json` or the default `wintuner_downloads`) exists and that the script has write permissions to it. This is where WinTuner will store downloaded installers and created `.intunewin` packages.
- **Backup `config.json`:** If you customize `config.json` (especially for non-sensitive paths), keep a backup.

---

❤️ info  | [WinTuner Documentation](https://wintuner.app)
