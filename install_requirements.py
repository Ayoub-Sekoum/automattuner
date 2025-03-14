import subprocess
import sys

def install_packages():
    """Installs required Python packages using pip."""
    packages_to_install = ['colorama', 'alive-progress']

    try:
        print("Checking for required packages...")
        for package in packages_to_install:
            try:
                __import__(package) # Check if package is already installed
                print(f"- Package '{package}' is already installed.")
            except ImportError:
                print(f"- Package '{package}' is not installed. Installing...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"  Successfully installed '{package}'.")
        print("All required packages are installed.")

    except subprocess.CalledProcessError as e:
        print(f"\nError occurred while installing packages: {e}")
        print("Please make sure pip is installed and accessible in your environment.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    install_packages()