import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import sys
from pathlib import Path

# Ensure the path includes the root directory to find the modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from publish_installer import load_config
# Import the logger from publish_installer to mock it specifically
from publish_installer import logger as publish_logger 

class TestPublishInstallerConfig(unittest.TestCase):
    """Test suite for load_config in publish_installer.py"""

    def common_path_mocks(self, mock_path_class):
        """Helper to set up common Path object mocks."""
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = False # Default to not existing
        mock_path_instance.is_file.return_value = False # Default
        mock_path_instance.parent = Path('.') # Mock parent attribute
        mock_path_instance.__truediv__.return_value = mock_path_instance # for / operator

        # When Path() is called, return our mock_path_instance
        mock_path_class.return_value = mock_path_instance
        
        # Mock resolve().parent behavior
        # Path(__file__).resolve().parent
        mock_resolve = MagicMock()
        mock_resolve.parent = Path('/fake/script/dir') # A plausible fake directory
        mock_path_instance.resolve.return_value = mock_resolve
        
        return mock_path_instance


    @patch('publish_installer.Path', autospec=True) # Mock Path class from publish_installer
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_tenant_id',
        'INTUNE_CLIENT_ID': 'env_client_id',
        'INTUNE_CLIENT_SECRET': 'env_client_secret'
    })
    @patch.object(publish_logger, 'error') # Mocking the logger instance directly
    @patch.object(publish_logger, 'info')
    def test_load_config_all_from_env(self, mock_log_info, mock_log_error, mock_path_class):
        """Test loading all sensitive config from environment variables."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = False # config.json does not exist

        # Mock mkdir to avoid actual directory creation
        mock_path_instance.mkdir = MagicMock()

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_tenant_id')
        self.assertEqual(config['intune_client_id'], 'env_client_id')
        self.assertEqual(config['intune_client_secret'], 'env_client_secret')
        # Check for default paths when config.json is not found
        self.assertTrue(config['wintuner_download_dir'].endswith('wintuner_downloads'))
        self.assertTrue(config['temp_package_dir'].endswith('temp_packages'))
        
        mock_path_instance.mkdir.assert_any_call(parents=True, exist_ok=True)
        mock_log_error.assert_not_called()


    @patch('publish_installer.Path', autospec=True)
    @patch.dict(os.environ, {}, clear=True) # Clear environment variables
    @patch.object(publish_logger, 'error')
    @patch.object(publish_logger, 'info')
    def test_load_config_all_from_json(self, mock_log_info, mock_log_error, mock_path_class):
        """Test loading all config from config.json when env vars are not set."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True # config.json exists

        mock_json_content = {
            "intune_tenant_id": "json_tenant_id",
            "intune_client_id": "json_client_id",
            "intune_client_secret": "json_client_secret",
            "wintuner_download_dir": "/path/from/json/wintuner_downloads",
            "temp_package_dir": "/path/from/json/temp_packages"
        }
        
        # Mock open for reading config.json
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        # The Path object's open method needs to be patched
        mock_path_instance.open = m_open

        # Mock mkdir
        mock_path_instance.mkdir = MagicMock()

        config = load_config("config.json") # Pass filename to ensure it's used

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'json_tenant_id')
        self.assertEqual(config['intune_client_id'], 'json_client_id')
        self.assertEqual(config['intune_client_secret'], 'json_client_secret')
        self.assertEqual(config['wintuner_download_dir'], "/path/from/json/wintuner_downloads")
        self.assertEqual(config['temp_package_dir'], "/path/from/json/temp_packages")
        
        mock_path_instance.mkdir.assert_any_call(parents=True, exist_ok=True)
        mock_log_error.assert_not_called()

    @patch('publish_installer.Path', autospec=True)
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_tenant_id_override',
        'INTUNE_CLIENT_ID': 'env_client_id_override',
        'INTUNE_CLIENT_SECRET': 'env_client_secret_override'
    })
    @patch.object(publish_logger, 'error')
    @patch.object(publish_logger, 'info')
    def test_load_config_mixed_env_overrides_json(self, mock_log_info, mock_log_error, mock_path_class):
        """Test environment variables override config.json for sensitive data."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True

        mock_json_content = {
            "intune_tenant_id": "json_tenant_id_not_used",
            "intune_client_id": "json_client_id_not_used",
            "intune_client_secret": "json_client_secret_not_used",
            "wintuner_download_dir": "/path/from/json/wintuner_downloads_mixed",
            "temp_package_dir": "/path/from/json/temp_packages_mixed"
        }
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        mock_path_instance.open = m_open
        mock_path_instance.mkdir = MagicMock()

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_tenant_id_override')
        self.assertEqual(config['intune_client_id'], 'env_client_id_override')
        self.assertEqual(config['intune_client_secret'], 'env_client_secret_override')
        self.assertEqual(config['wintuner_download_dir'], "/path/from/json/wintuner_downloads_mixed")
        self.assertEqual(config['temp_package_dir'], "/path/from/json/temp_packages_mixed")
        mock_log_error.assert_not_called()

    @patch('publish_installer.Path', autospec=True)
    @patch.dict(os.environ, {'INTUNE_TENANT_ID': 'env_tenant', 'INTUNE_CLIENT_ID': 'env_client'}, clear=True) # Missing secret
    @patch('publish_installer.error_msg') # Mock the error_msg function that prints to console
    @patch.object(publish_logger, 'error') # Mock the logger for file logging
    def test_load_config_missing_critical_secret(self, mock_log_file_error, mock_error_msg_console, mock_path_class):
        """Test missing critical sensitive value (client_secret)."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True # config.json exists
        
        # config.json also does not contain the secret
        mock_json_content = {"intune_tenant_id": "json_tenant", "intune_client_id": "json_client"}
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        mock_path_instance.open = m_open
        mock_path_instance.mkdir = MagicMock()

        config = load_config()

        self.assertIsNone(config)
        # Check that error_msg (console) was called for the missing key
        # The actual message check might be tricky if it lists multiple missing keys.
        # For now, just check it was called.
        mock_error_msg_console.assert_called()
        # Check that logger.error (file log) was called for the overall failure
        mock_log_file_error.assert_any_call("Configuration failed with errors: Missing critical sensitive configuration(s): INTUNE_CLIENT_SECRET or intune_client_secret in config.json. Please set them as environment variables or in config.json.")


    @patch('publish_installer.Path', autospec=True)
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_tenant_no_json',
        'INTUNE_CLIENT_ID': 'env_client_no_json',
        'INTUNE_CLIENT_SECRET': 'env_secret_no_json'
    })
    @patch.object(publish_logger, 'error') # To ensure no critical errors are logged
    @patch.object(publish_logger, 'info') # To check for info/warning about missing file
    def test_load_config_json_not_found_env_provides_sensitive(self, mock_log_info, mock_log_error, mock_path_class):
        """Test config.json not found, but env vars provide sensitive data."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = False # config.json does not exist
        mock_path_instance.mkdir = MagicMock()

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_tenant_no_json')
        self.assertEqual(config['intune_client_id'], 'env_client_no_json')
        self.assertEqual(config['intune_client_secret'], 'env_secret_no_json')
        # Paths should take defaults
        self.assertTrue(config['wintuner_download_dir'].endswith('wintuner_downloads'))
        self.assertTrue(config['temp_package_dir'].endswith('temp_packages'))
        
        mock_log_error.assert_not_called() # No critical errors
        # Check if an error/warning about config file not found was logged by error_msg (which calls logger.error)
        # The load_config function calls error_msg if config file not found AND sensitive vars are missing.
        # In this case, sensitive vars ARE present, so it should not call error_msg for file not found as critical.
        # It will log an error about the file not being found if it's needed for fallback though.
        # The current implementation will append to errors list:
        # "Configuration file 'config.json' not found at ... and sensitive environment variables are not all set."
        # This specific message might not appear if all sensitive are set by env.
        # Let's check the specific log for "Configuration loaded successfully."
        mock_log_info.assert_any_call("Configuration loaded successfully.")


    @patch('publish_installer.Path', autospec=True)
    @patch.dict(os.environ, {}, clear=True)
    @patch('publish_installer.error_msg')
    @patch.object(publish_logger, 'error')
    def test_load_config_invalid_json(self, mock_log_file_error, mock_error_msg_console, mock_path_class):
        """Test invalid JSON content in config.json."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True
        
        m_open = mock_open(read_data="this is not valid json")
        mock_path_instance.open = m_open
        mock_path_instance.mkdir = MagicMock()

        config = load_config()

        self.assertIsNone(config)
        mock_error_msg_console.assert_called()
        # Example: check that the error message contains "Error decoding JSON"
        console_error_arg = mock_error_msg_console.call_args[0][1] # Get the second argument of the first call
        self.assertIn("Error decoding JSON", str(console_error_arg))
        
        file_error_arg = mock_log_file_error.call_args[0][0]
        self.assertIn("Error decoding JSON", file_error_arg)


if __name__ == '__main__':
    unittest.main()
