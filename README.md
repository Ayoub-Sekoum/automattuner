# Automation of App Upload with WinTuner 🚀

![Intune Application Publisher](https://github.com/Ayoub-Sekoum/automattuner/blob/main/foto.jpg)

[![Watch the video](https://img.youtube.com/vi/JpIa12gXjiw/0.jpg)](https://youtu.be/JpIa12gXjiw)

## Overview

This script automates the process of packaging and publishing applications from the Winget repository to Microsoft Intune. It leverages the power of WinTuner to streamline application management, making it easy to deploy and update software across your organization.

## Features ✨

- 📦 **Automatic Packaging:** Creates Intune-compatible packages directly from Winget.
- ☁️ **Direct Intune Publishing:** Uploads and configures applications in your Intune environment.
- 🔄 **Dependency Management:** Handles application dependencies automatically (where supported by the Winget manifest).
- 📊 **Interactive CLI:** User-friendly interface guides you through the process.
- 🔍 **Duplicate Detection:** Checks for existing versions in Intune to prevent conflicts.
- 📄 **Detailed Reporting:** Generates comprehensive reports of published applications.
- 🔐 **Secure Authentication:** Uses Azure AD application registration for secure access to Intune.
- 📄 Detailed report generation

## Prerequisites 📋

### 1. System Requirements

- PowerShell 7+ (Highly Recommended - install via `winget install Microsoft.Powershell`)
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (Windows Package Manager)

### 2. Software Dependencies

```powershell
# Install .NET 8 SDK (if not already installed)
winget install Microsoft.DotNet.SDK.8

# Install WinTuner CLI
dotnet tool install --global SvRooij.Winget-Intune.Cli
```

### 3. Azure AD Configuration

- **Register an Application**: Create a new application registration in the Azure Portal.
- **API Permissions**: Assign the following Application permissions:
  - Application.ReadWrite.All
  - DeviceManagementApps.ReadWrite.All
  - DeviceManagementServiceConfig.ReadWrite.All
  - DeviceManagementApps.ReadWrite.All
  - Group.Read.All
  - User.Read.All

**Important**: Grant admin consent for these permissions.

- **Client Secret**: Create a client secret for your application. Record this secret immediately; you won't be able to see it again.

**Note Credentials**: Keep track of the following:

- Tenant ID
- Client ID
- Client Secret

## Initial Setup & Configuration ⚙️

### Create `config.json`

Create a file named `config.json` in the root directory of your project. Do not commit this file to your repository.

```json
{
  "intune_tenant_id": "YOUR_TENANT_ID",
  "intune_client_id": "YOUR_CLIENT_ID",
  "intune_client_secret": "YOUR_CLIENT_SECRET",
  "wintuner_download_dir": "C:\\IntuneApps"
}
```

### V2

```json
{
  "intune_tenant_id": "",
  "intune_client_id": "",
  "intune_client_secret": "",
  "powershell_cert_thumbprint": "",
  "default_logo_path": "logos/default_logo.png",
  "temp_package_dir": "temp_packages",
  "wintuner_download_dir": "\\wintuner_downloads",
  "required_permissions": [
    "DeviceManagementManagedDevices.ReadWrite.All",
    "DeviceManagementServiceConfig.ReadWrite.All",
    "DeviceManagementApps.ReadWrite.All",
    "Group.Read.All",
    "User.Read.All"
  ]
}
```

Replace the placeholders with your actual credentials.

- `wintuner_download_dir`: Specify the directory where WinTuner will create the Intune packages. Ensure this directory exists and the script has write access.

### `.gitignore`

Add `config.json` to your `.gitignore` file to prevent accidental commits:

```
config.json
```

❤️ info  | [WinTuner Documentation](https://wintuner.app) 
