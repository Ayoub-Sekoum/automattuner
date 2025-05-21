import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import sys
from pathlib import Path

# Ensure the path includes the root directory to find the modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Report import load_config # Assuming Report.py and its load_config
# Import the logger from Report to mock it specifically
from Report import logger as report_logger 

class TestReportConfig(unittest.TestCase):
    """Test suite for load_config in Report.py"""

    def common_path_mocks(self, mock_path_class):
        """Helper to set up common Path object mocks."""
        mock_path_instance = MagicMock(spec=Path)
        mock_path_instance.exists.return_value = False # Default to not existing
        mock_path_instance.is_file.return_value = False # Default
        mock_path_instance.parent = Path('.') # Mock parent attribute
        mock_path_instance.__truediv__.return_value = mock_path_instance 

        mock_path_class.return_value = mock_path_instance
        
        mock_resolve = MagicMock()
        mock_resolve.parent = Path('/fake/script/dir') 
        mock_path_instance.resolve.return_value = mock_resolve
        
        return mock_path_instance

    @patch('Report.Path', autospec=True) 
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_report_tenant_id',
        'INTUNE_CLIENT_ID': 'env_report_client_id',
        'INTUNE_CLIENT_SECRET': 'env_report_client_secret'
    })
    @patch.object(report_logger, 'error') 
    @patch.object(report_logger, 'info')
    def test_load_config_all_from_env(self, mock_log_info, mock_log_error, mock_path_class):
        """Test loading all sensitive config from environment variables for Report.py."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = False # config.json does not exist

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_report_tenant_id')
        self.assertEqual(config['intune_client_id'], 'env_report_client_id')
        self.assertEqual(config['intune_client_secret'], 'env_report_client_secret')
        mock_log_error.assert_not_called()
        mock_log_info.assert_any_call("Configuration loaded successfully for Report.py.")


    @patch('Report.Path', autospec=True)
    @patch.dict(os.environ, {}, clear=True) 
    @patch.object(report_logger, 'error')
    @patch.object(report_logger, 'info')
    def test_load_config_all_from_json(self, mock_log_info, mock_log_error, mock_path_class):
        """Test loading all config from config.json for Report.py when env vars are not set."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True 

        mock_json_content = {
            "intune_tenant_id": "json_report_tenant_id",
            "intune_client_id": "json_report_client_id",
            "intune_client_secret": "json_report_client_secret",
            # Report.py's load_config doesn't use these, but they might be in a shared config
            "wintuner_download_dir": "/some/path", 
            "temp_package_dir": "/other/path"
        }
        
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        mock_path_instance.open = m_open

        config = load_config("config.json")

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'json_report_tenant_id')
        self.assertEqual(config['intune_client_id'], 'json_report_client_id')
        self.assertEqual(config['intune_client_secret'], 'json_report_client_secret')
        mock_log_error.assert_not_called()
        mock_log_info.assert_any_call("Configuration loaded successfully for Report.py.")

    @patch('Report.Path', autospec=True)
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_r_tenant_override',
        'INTUNE_CLIENT_ID': 'env_r_client_override',
        'INTUNE_CLIENT_SECRET': 'env_r_secret_override'
    })
    @patch.object(report_logger, 'error')
    @patch.object(report_logger, 'info')
    def test_load_config_mixed_env_overrides_json(self, mock_log_info, mock_log_error, mock_path_class):
        """Test env vars override config.json for sensitive data in Report.py."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True

        mock_json_content = {
            "intune_tenant_id": "json_tenant_not_used",
            "intune_client_id": "json_client_not_used",
            "intune_client_secret": "json_secret_not_used"
        }
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        mock_path_instance.open = m_open

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_r_tenant_override')
        self.assertEqual(config['intune_client_id'], 'env_r_client_override')
        self.assertEqual(config['intune_client_secret'], 'env_r_secret_override')
        mock_log_error.assert_not_called()
        mock_log_info.assert_any_call("Configuration loaded successfully for Report.py.")


    @patch('Report.Path', autospec=True)
    @patch.dict(os.environ, {'INTUNE_TENANT_ID': 'env_tenant', 'INTUNE_CLIENT_ID': 'env_client'}, clear=True)
    @patch('Report.error_msg') 
    @patch.object(report_logger, 'error') 
    def test_load_config_missing_critical_secret(self, mock_log_file_error, mock_error_msg_console, mock_path_class):
        """Test missing critical sensitive value (client_secret) for Report.py."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True 
        
        mock_json_content = {"intune_tenant_id": "json_tenant", "intune_client_id": "json_client"}
        m_open = mock_open(read_data=json.dumps(mock_json_content))
        mock_path_instance.open = m_open

        config = load_config()

        self.assertIsNone(config)
        mock_error_msg_console.assert_called()
        # Check the logged message for the specific missing key
        logged_error_message = ""
        for call_arg in mock_log_file_error.call_args_list:
            if "Missing critical sensitive configuration(s)" in call_arg[0][0]:
                logged_error_message = call_arg[0][0]
                break
        self.assertIn("INTUNE_CLIENT_SECRET or intune_client_secret in config.json", logged_error_message)


    @patch('Report.Path', autospec=True)
    @patch.dict(os.environ, {
        'INTUNE_TENANT_ID': 'env_r_tenant_no_json',
        'INTUNE_CLIENT_ID': 'env_r_client_no_json',
        'INTUNE_CLIENT_SECRET': 'env_r_secret_no_json'
    })
    @patch.object(report_logger, 'error') 
    @patch.object(report_logger, 'info') 
    def test_load_config_json_not_found_env_provides_sensitive(self, mock_log_info, mock_log_error, mock_path_class):
        """Test config.json not found, but env vars provide sensitive data for Report.py."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = False # config.json does not exist

        config = load_config()

        self.assertIsNotNone(config)
        self.assertEqual(config['intune_tenant_id'], 'env_r_tenant_no_json')
        self.assertEqual(config['intune_client_id'], 'env_r_client_no_json')
        self.assertEqual(config['intune_client_secret'], 'env_r_secret_no_json')
        
        # Report.py's load_config does not add default paths like publish_installer.py does
        self.assertNotIn('wintuner_download_dir', config) 
        self.assertNotIn('temp_package_dir', config)
        
        mock_log_error.assert_not_called() 
        mock_log_info.assert_any_call("Configuration loaded successfully for Report.py.")


    @patch('Report.Path', autospec=True)
    @patch.dict(os.environ, {}, clear=True)
    @patch('Report.error_msg')
    @patch.object(report_logger, 'error')
    def test_load_config_invalid_json(self, mock_log_file_error, mock_error_msg_console, mock_path_class):
        """Test invalid JSON content in config.json for Report.py."""
        mock_path_instance = self.common_path_mocks(mock_path_class)
        mock_path_instance.exists.return_value = True
        
        m_open = mock_open(read_data="this is not valid json")
        mock_path_instance.open = m_open

        config = load_config()

        self.assertIsNone(config)
        mock_error_msg_console.assert_called()
        console_error_arg = mock_error_msg_console.call_args[0][1]
        self.assertIn("Error decoding JSON", str(console_error_arg))
        
        file_error_arg = ""
        for call_arg in mock_log_file_error.call_args_list:
            if "Error decoding JSON" in call_arg[0][0]:
                file_error_arg = call_arg[0][0]
                break
        self.assertIn("Error decoding JSON", file_error_arg)

if __name__ == '__main__':
    unittest.main()
