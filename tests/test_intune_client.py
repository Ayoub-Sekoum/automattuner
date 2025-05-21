import unittest
from unittest.mock import patch, MagicMock, mock_open, call # Added call
import urllib.request
import urllib.error
import json
import logging

# Ensure the path includes the root directory to find intune_client
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intune_client import get_access_token, get_intune_apps, determine_platform

# Suppress all logging output from the application during tests
# This can be done globally or per test method if needed
# logging.disable(logging.CRITICAL)

# It's often better to let the default logger configuration happen,
# and then specifically patch the logger instance used in the module under test.
# This avoids issues if other parts of unittest or libraries use logging.

class TestIntuneClient(unittest.TestCase):
    """Test suite for intune_client.py"""

    def setUp(self):
        # It's good practice to explicitly stop any patches started in setUp if using start/stop
        # For decorator-based patching, this is handled automatically.
        pass

    # Tests for get_access_token
    @patch('intune_client.logger') # Patch the logger instance in the intune_client module
    @patch('urllib.request.urlopen')
    def test_get_access_token_success(self, mock_urlopen, mock_logger):
        """Test successful retrieval of an access token."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "access_token": "fake_token_123",
            "expires_in": 3600
        }).encode('utf-8')
        # If using 'with' statement context manager for urlopen
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = None
        mock_urlopen.return_value = mock_cm


        token = get_access_token("dummy_tenant", "dummy_client_id", "dummy_client_secret")
        self.assertEqual(token, "fake_token_123")
        mock_urlopen.assert_called_once()
        args, kwargs = mock_urlopen.call_args
        request_sent = args[0]
        self.assertTrue(request_sent.full_url.startswith("https://login.microsoftonline.com/dummy_tenant/oauth2/v2.0/token"))
        self.assertEqual(request_sent.method, "POST")
        mock_logger.info.assert_any_call("Successfully retrieved access token. (intune_client)")


    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_access_token_http_error(self, mock_urlopen, mock_logger):
        """Test HTTPError during access token retrieval."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error":"unauthorized_client", "error_description":"The client is not authorized"}'
        
        http_error = urllib.error.HTTPError(
            "http://example.com", 401, "Unauthorized", {}, mock_response 
        )
        # If using 'with' statement context manager for urlopen that raises error
        mock_cm = MagicMock()
        mock_cm.__enter__.side_effect = http_error # Error happens when trying to open
        mock_urlopen.return_value = mock_cm


        token = get_access_token("tenant1", "client1", "secret1")
        self.assertIsNone(token)
        
        # Check if logger.error was called. We expect specific parts of the message.
        # The exact message format is: f"MSAL Authentication HTTPError {e.code} ({e.reason}). Response Body: {error_body} (intune_client)"
        # We need to find the call that matches this pattern.
        error_call_args = None
        for c in mock_logger.error.call_args_list:
            if "MSAL Authentication HTTPError 401" in c[0][0]:
                error_call_args = c
                break
        self.assertIsNotNone(error_call_args, "Logger error for HTTP 401 not found.")
        self.assertIn("MSAL Authentication HTTPError 401 (Unauthorized). Response Body: {\"error\":\"unauthorized_client\", \"error_description\":\"The client is not authorized\"} (intune_client)", error_call_args[0][0])
        self.assertTrue(error_call_args[1].get('exc_info'))


    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_access_token_url_error(self, mock_urlopen, mock_logger):
        """Test URLError during access token retrieval."""
        mock_urlopen.side_effect = urllib.error.URLError("Network down")
        token = get_access_token("tenant2", "client2", "secret2")
        self.assertIsNone(token)
        mock_logger.error.assert_called_once_with(
            "MSAL Authentication Network Error: Network down (intune_client)",
            exc_info=True
        )

    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_access_token_general_exception(self, mock_urlopen, mock_logger):
        """Test general Exception during access token retrieval."""
        mock_urlopen.side_effect = Exception("Something broke")
        token = get_access_token("tenant3", "client3", "secret3")
        self.assertIsNone(token)
        mock_logger.error.assert_called_once_with(
            "MSAL Authentication Exception: Something broke (intune_client)",
            exc_info=True
        )
    
    @patch('intune_client.logger')
    def test_get_access_token_missing_credentials(self, mock_logger):
        """Test get_access_token with missing credentials."""
        token = get_access_token(None, "client_id", "secret")
        self.assertIsNone(token)
        mock_logger.error.assert_called_with("Tenant ID, Client ID, or Client Secret is missing. Cannot get token. (intune_client)")

        token = get_access_token("tenant_id", None, "secret")
        self.assertIsNone(token)
        mock_logger.error.assert_called_with("Tenant ID, Client ID, or Client Secret is missing. Cannot get token. (intune_client)")

        token = get_access_token("tenant_id", "client_id", None)
        self.assertIsNone(token)
        mock_logger.error.assert_called_with("Tenant ID, Client ID, or Client Secret is missing. Cannot get token. (intune_client)")


    # Tests for get_intune_apps
    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_intune_apps_success_single_page(self, mock_urlopen, mock_logger):
        """Test successful retrieval of apps (single page)."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "value": [{"id": "app1", "displayName": "App One"}]
        }).encode('utf-8')
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm


        apps = get_intune_apps("dummy_token")
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['displayName'], "App One")
        mock_urlopen.assert_called_once()
        request_sent = mock_urlopen.call_args[0][0]
        self.assertTrue(request_sent.full_url.startswith("https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps"))
        self.assertNotIn("$filter", request_sent.full_url)
        mock_logger.info.assert_any_call("Finished fetching apps. Total found: 1. (intune_client)")


    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_intune_apps_success_multiple_pages(self, mock_urlopen, mock_logger):
        """Test successful retrieval of apps (multiple pages)."""
        mock_response_page1_content = json.dumps({
            "value": [{"id": "app1", "displayName": "App Alpha"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps?$skipToken=123"
        }).encode('utf-8')
        mock_response_page1 = MagicMock()
        mock_response_page1.status = 200
        mock_response_page1.read.return_value = mock_response_page1_content
        mock_cm1 = MagicMock()
        mock_cm1.__enter__.return_value = mock_response_page1

        mock_response_page2_content = json.dumps({
            "value": [{"id": "app2", "displayName": "App Beta"}]
        }).encode('utf-8')
        mock_response_page2 = MagicMock()
        mock_response_page2.status = 200
        mock_response_page2.read.return_value = mock_response_page2_content
        mock_cm2 = MagicMock()
        mock_cm2.__enter__.return_value = mock_response_page2
        
        mock_urlopen.side_effect = [mock_cm1, mock_cm2]

        apps = get_intune_apps("dummy_token_multi")
        self.assertEqual(len(apps), 2)
        self.assertEqual(apps[0]['displayName'], "App Alpha")
        self.assertEqual(apps[1]['displayName'], "App Beta")
        self.assertEqual(mock_urlopen.call_count, 2)
        
        request_page1 = mock_urlopen.call_args_list[0][0][0]
        self.assertTrue(request_page1.full_url.startswith("https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps"))
        request_page2 = mock_urlopen.call_args_list[1][0][0]
        self.assertEqual(request_page2.full_url, "https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps?$skipToken=123")
        mock_logger.info.assert_any_call("Finished fetching apps. Total found: 2. (intune_client)")

    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_intune_apps_with_filter(self, mock_urlopen, mock_logger):
        """Test app retrieval with a package_id_filter."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "value": [{"id": "appFilter", "displayName": "Filtered App"}]
        }).encode('utf-8')
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        apps = get_intune_apps("dummy_token_filter", package_id_filter="FilterApp")
        self.assertIsNotNone(apps)
        mock_urlopen.assert_called_once()
        request_sent = mock_urlopen.call_args[0][0]
        self.assertIn("$filter=contains(tolower(displayName)%2C+%27filterapp%27)", request_sent.full_url)
        self.assertIn("$count=true", request_sent.full_url)
        mock_logger.info.assert_any_call("Finished fetching apps. Total found: 1. (intune_client)")


    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_intune_apps_http_error(self, mock_urlopen, mock_logger):
        """Test HTTPError during app retrieval."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"error":"server_issue"}'
        http_error = urllib.error.HTTPError(
            "http://example.com", 500, "Server Error", {}, mock_response
        )
        mock_cm = MagicMock()
        mock_cm.__enter__.side_effect = http_error
        mock_urlopen.return_value = mock_cm
        
        apps = get_intune_apps("dummy_token_http_error")
        self.assertIsNone(apps)
        
        error_call_args = None
        for c in mock_logger.error.call_args_list:
            if "HTTPError 500" in c[0][0]: # Check for the specific error code
                error_call_args = c
                break
        self.assertIsNotNone(error_call_args, "Logger error for HTTP 500 not found.")
        self.assertIn("HTTPError 500 (Server Error) fetching apps from Intune.", error_call_args[0][0])
        self.assertIn("Response: {\"error\":\"server_issue\"}", error_call_args[0][0])
        self.assertTrue(error_call_args[1].get('exc_info'))

    @patch('intune_client.logger')
    @patch('urllib.request.urlopen')
    def test_get_intune_apps_non_200_status(self, mock_urlopen, mock_logger):
        """Test non-200 status that isn't an HTTPError exception initially."""
        mock_response = MagicMock()
        mock_response.status = 403 # Example: Forbidden
        mock_response.read.return_value = b'{"error":"forbidden_access"}'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        apps = get_intune_apps("dummy_token_403")
        self.assertIsNone(apps) # Should return None as it's an error
        mock_logger.error.assert_any_call(
            "Error fetching apps from Intune. HTTP Status: 403, URI: https://graph.microsoft.com/v1.0/deviceAppManagement/mobileApps?$top=999, Body: {\"error\":\"forbidden_access\"} (intune_client)"
        )


    # Tests for determine_platform
    def test_determine_platform(self):
        """Test platform determination from odata.type strings."""
        test_cases = {
            "#microsoft.graph.win32LobApp": "Windows",
            "#microsoft.graph.windowsUniversalAppX": "Windows UWP",
            "#microsoft.graph.microsoftStoreForBusinessApp": "Win Store",
            "#microsoft.graph.managedAndroidLobApp": "Android LOB",
            "#microsoft.graph.androidStoreApp": "Android Store",
            "#microsoft.graph.iosLobApp": "iOS LOB",
            "#microsoft.graph.iosVppApp": "iOS VPP",
            "#microsoft.graph.macOSLobApp": "macOS LOB",
            "#microsoft.graph.macOSDmgApp": "macOS DMG",
            "#microsoft.graph.microsoftEdgeApp": "Edge",
            "#microsoft.graph.webApp": "Web App",
            "some.other.UnknownType": "Unknowntype", 
            "": "Unknown Type",
            None: "Unknown Type", 
            "#microsoft.graph.officeMobileApp": "Officemobile" 
        }
        for odata_type, expected_platform in test_cases.items():
            with self.subTest(odata_type=odata_type):
                # Ensure the logger isn't called for this simple function unless an error state is possible
                with patch('intune_client.logger') as mock_determine_logger:
                    platform = determine_platform(odata_type)
                    self.assertEqual(platform, expected_platform)
                    mock_determine_logger.assert_not_called()


if __name__ == '__main__':
    unittest.main()
