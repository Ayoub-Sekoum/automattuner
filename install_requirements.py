import subprocess
import sys
import platform
import importlib.util # Preferred way to check for module existence

# --- run_command function remains the same as before ---
def run_command(command, check=True, shell=False, capture_output=False, text=True):
    """Helper function to run a command and print output/errors."""
    cmd_str = ' '.join(command) if isinstance(command, list) else command
    print(f"\nExecuting command: {cmd_str}")
    try:
        cmd_arg = cmd_str if shell else command
        result = subprocess.run(
            cmd_arg,
            check=check,
            shell=shell,
            capture_output=capture_output,
            text=text,
            encoding=sys.stdout.encoding or 'utf-8',
            errors='replace'
        )
        if capture_output:
            if result.stdout:
                print("Output:\n", result.stdout)
            if result.stderr:
                print("Errors:\n", result.stderr, file=sys.stderr)
        if not check and result.returncode != 0:
             print(f"Command returned non-zero exit status: {result.returncode}", file=sys.stderr)
        if not check:
             if result.returncode == 0:
                 print(f"Command executed successfully (Return Code: 0).")
        else:
            print(f"Command executed successfully.")
        return result
    except subprocess.CalledProcessError as e:
        print(f"\nError executing command: {cmd_str}", file=sys.stderr)
        print(f"Return code: {e.returncode}", file=sys.stderr)
        if e.stdout: print(f"stdout: {e.stdout}", file=sys.stderr)
        if e.stderr: print(f"stderr: {e.stderr}", file=sys.stderr)
        if check: raise
        return None
    except FileNotFoundError:
        exe_name = command[0] if isinstance(command, list) else cmd_str.split()[0]
        print(f"\nError: Command '{exe_name}' not found.", file=sys.stderr)
        print("Please ensure the required executable is installed and in your system's PATH.", file=sys.stderr)
        if check: raise
        return None
    except Exception as e:
        print(f"\nAn unexpected error occurred while running command: {e}", file=sys.stderr)
        if check: raise
        return None

# --- install_python_packages function remains the same ---
def install_python_packages():
    """Installs required Python packages using pip."""
    print("-" * 50)
    print("STEP 1: Installing Python Packages")
    print("-" * 50)
    packages_to_install = ['colorama', 'alive-progress']
    installed_all = True
    print("Checking for required Python packages...")
    for package in packages_to_install:
        spec = importlib.util.find_spec(package)
        if spec is None:
            print(f"- Package '{package}' is not installed. Installing...")
            try:
                run_command([sys.executable, '-m', 'pip', 'install', package])
                spec = importlib.util.find_spec(package) # Recheck after install
                if spec:
                     print(f"  Successfully installed '{package}'.")
                else:
                     print(f"  Installation command ran, but package '{package}' still not found. Check pip output.", file=sys.stderr)
                     installed_all = False
            except Exception as e:
                print(f"  Failed to install '{package}': {e}", file=sys.stderr)
                installed_all = False
        else:
            print(f"- Package '{package}' is already installed.")
    if installed_all:
        print("\nAll required Python packages seem to be installed.")
    else:
        print("\nSome Python packages may have failed to install. Please check the errors above.", file=sys.stderr)
    print("-" * 50)
    return installed_all

# --- install_dotnet_windows function remains the same (with .NET 9) ---
def install_dotnet_windows():
    """Installs .NET 9 SDK and Svrooij.Winget-Intune.Cli tool on Windows."""
    print("-" * 50)
    print("STEP 2: Installing .NET Components (Windows Only)")
    print("-" * 50)
    installed_all = True
    dotnet_sdk_id = 'Microsoft.DotNet.SDK.9' # Keep .NET 9
    try:
        print(f"Attempting to install/update {dotnet_sdk_id} using winget...")
        print("Winget might require confirmation or run interactively.")
        run_command(['winget', 'install', '--id', dotnet_sdk_id, '--source', 'winget', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity'], check=False)
        print("\nEnsuring nuget.org source is added to .NET...")
        run_command(['dotnet', 'nuget', 'add', 'source', 'https://api.nuget.org/v3/index.json', '--name', 'nuget.org'], check=False)
        print("\nInstalling/updating .NET tool 'Svrooij.Winget-Intune.Cli'...")
        run_command(['dotnet', 'tool', 'install', '--global', 'Svrooij.Winget-Intune.Cli'])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"\nAn error occurred during .NET component installation: {e}", file=sys.stderr)
        print("Please ensure Winget and/or the .NET SDK are accessible.", file=sys.stderr)
        installed_all = False
    except Exception as e:
        print(f"\nAn unexpected error occurred during .NET setup: {e}", file=sys.stderr)
        installed_all = False
    if installed_all:
        print("\n.NET component installation steps attempted. Check logs for winget status.")
    else:
        print("\nSome .NET component installation steps failed.", file=sys.stderr)
    print("-" * 50)
    return installed_all

# --- Updated install_powershell_modules_windows function ---
def install_powershell_modules_windows():
    """Installs/Updates the WinTuner PowerShell module on Windows."""
    print("-" * 50)
    print("STEP 3: Installing PowerShell Modules (Windows Only)")
    print("-" * 50)
    overall_ps_success = True
    module_name = "WinTuner"
    powershell_exe = "powershell.exe" # Use the built-in Windows PowerShell first

    # Check if PowerShell exists
    try:
        run_command([powershell_exe, "-Command", "Write-Host 'PowerShell check'"], capture_output=True, check=True)
        print(f"'{powershell_exe}' executable found.")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print(f"Error: '{powershell_exe}' not found or failed. Trying 'pwsh' (PowerShell Core)...", file=sys.stderr)
        powershell_exe = "pwsh" # Fallback to PowerShell Core if installed
        try:
            run_command([powershell_exe, "-Command", "Write-Host 'PowerShell Core check'"], capture_output=True, check=True)
            print(f"'{powershell_exe}' executable found.")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print(f"Error: Neither 'powershell.exe' nor 'pwsh' found or working.", file=sys.stderr)
            print("Cannot install/update PowerShell modules.", file=sys.stderr)
            print("-" * 50)
            return False # Cannot proceed

    # Commands to execute in sequence
    ps_commands_to_try = [
        {
            "desc": "Update PowerShellGet Module",
            # Using -Force ensures it tries to install even if present.
            # -AllowClobber handles potential command conflicts during update.
            # -SkipPublisherCheck can sometimes bypass prompts on older systems.
            # Run this first to get newer features like -AcceptLicense potentially.
            # Added basic error handling within PS command itself.
            "cmd": "try { Install-Module -Name PowerShellGet -Force -SkipPublisherCheck -AllowClobber -Confirm:$false } catch { Write-Warning ('Failed to update PowerShellGet: {0}' -f $_.Exception.Message) }",
            "check": False # Don't fail the whole script if PSGet update fails, but log warning
        },
        {
            "desc": f"Install {module_name} Module",
            # Added -AcceptLicense, assuming PowerShellGet update succeeded or it was already new enough.
            # If PSGet update failed AND original version was too old, this *might* still fail or prompt.
            "cmd": f"if (-not (Get-Module -ListAvailable -Name {module_name})) {{ Install-Module -Name {module_name} -Scope CurrentUser -Force -Confirm:$false -AllowClobber -AcceptLicense }} else {{ Write-Host 'Module {module_name} already installed, skipping initial install.' }}",
            "check": True # Fail if install command itself errors
        },
        {
            "desc": f"Update {module_name} Module",
            # Added -AcceptLicense here too for newer PowerShellGet versions
            "cmd": f"Update-Module -Name {module_name} -Confirm:$false -AcceptLicense",
            "check": True # Fail if update command itself errors (e.g., module not found after install attempt)
        }
    ]

    # Execute the PowerShell commands
    for item in ps_commands_to_try:
        print(f"\nAttempting: {item['desc']}")
        print(f"PowerShell Command: {item['cmd']}")
        try:
            full_command = [powershell_exe, '-ExecutionPolicy', 'Bypass', '-NoProfile', '-Command', item['cmd']]
            run_command(full_command, check=item['check']) # Use check=True/False as defined
            print(f"PowerShell command for '{item['desc']}' executed successfully.")
        except (subprocess.CalledProcessError) as e:
            # Error is already printed by run_command's exception handler
            print(f"\nError occurred during '{item['desc']}'.", file=sys.stderr)
            print("Check PowerShell Gallery accessibility (Get-PSRepository) and permissions.", file=sys.stderr)
            if item['check']: # If this step was mandatory
                 overall_ps_success = False
                 break # Stop processing further PS commands for this module
            else:
                 print("Continuing with next step as this one was not critical...")
        except Exception as e:
             # Catch other potential errors like FileNotFoundError handled by run_command
             print(f"\nAn unexpected error occurred during '{item['desc']}': {e}", file=sys.stderr)
             overall_ps_success = False
             break

    if overall_ps_success:
        print(f"\nPowerShell module '{module_name}' installation/update steps completed successfully.")
    else:
        print(f"\nPowerShell module '{module_name}' installation/update failed or encountered issues. Please check errors.", file=sys.stderr)
    print("-" * 50)
    return overall_ps_success

# --- install_all_dependencies function remains the same ---
def install_all_dependencies():
    """Installs all required dependencies (Python, .NET, PowerShell)."""
    print("Starting dependency installation process...")
    overall_success = True

    success_py = install_python_packages()
    if not success_py: overall_success = False

    success_dotnet = True
    success_ps = True
    if platform.system() == 'Windows':
        print("\nDetected Windows OS. Proceeding with Windows-specific installations.")
        success_dotnet = install_dotnet_windows()
        # If dotnet setup failed critically (e.g., command not found), mark overall as failed
        # Note: Winget step uses check=False, so success_dotnet might be True even if winget had issues.
        # This logic assumes run_command correctly returns None or raises on critical failures.
        if success_dotnet is None or (isinstance(success_dotnet, bool) and not success_dotnet):
             overall_success = False

        success_ps = install_powershell_modules_windows()
        if not success_ps:
            overall_success = False
    else:
        print("\nNon-Windows OS detected.")
        print("Skipping Windows-specific installations (.NET SDK via winget, PowerShell Modules).")
        print("Please ensure .NET 9 SDK is installed using the appropriate method for your OS.")
        print("Link: https://dotnet.microsoft.com/en-us/download")
        print("Then, manually run: dotnet tool install --global Svrooij.Winget-Intune.Cli")
        print("The 'WinTuner' PowerShell module is Windows-specific and will be skipped.")
        success_dotnet = True # Skipped, not failed
        success_ps = True     # Skipped, not failed

    print("\n--- Installation Summary ---")
    print(f"Python Packages Installation:  {'Success' if success_py else 'Failed/Incomplete'}")
    if platform.system() == 'Windows':
        dotnet_summary = 'Attempted (Check Logs)' if success_dotnet else 'Failed' # Simplified summary
        print(f".NET Components Installation:  {dotnet_summary}")
        print(f"PowerShell Modules Installation: {'Success' if success_ps else 'Failed/Incomplete'}")
    else:
        print(".NET Components Installation:  Skipped (Manual install required)")
        print("PowerShell Modules Installation: Skipped (Windows-specific)")

    if overall_success:
        print("\nDependency installation process completed.")
        if platform.system() == 'Windows':
             print("Please review winget and PowerShell logs above for specific status details.")
    else:
        print("\nSome required dependencies failed to install or configure properly. Please review the logs above.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    install_all_dependencies()
