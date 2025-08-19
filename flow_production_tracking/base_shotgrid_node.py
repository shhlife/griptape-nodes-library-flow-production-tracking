import time

import httpx

from griptape_nodes.exe_types.node_types import ControlNode
from griptape_nodes.retained_mode.griptape_nodes import logger


class BaseShotGridNode(ControlNode):
    """Base class for all ShotGrid nodes with authentication handling"""

    # Class-level cache for the access token
    _access_token = None
    _token_expires_at = None

    SERVICE = "Autodesk"
    API_KEY_ENV_VAR = "SHOTGRID_API_KEY"
    SHOTGRID_URL_ENV_VAR = "SHOTGRID_URL"
    USERNAME_ENV_VAR = "SHOTGRID_USERNAME"
    PASSWORD_ENV_VAR = "SHOTGRID_PASSWORD"
    SCRIPT_NAME = "Griptape Nodes"

    def _get_access_token(self) -> str:
        """Get or refresh the access token using client credentials"""
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at and time.time() < self._token_expires_at:
            return self._access_token

        # Get configuration
        config = self._get_shotgrid_config()
        api_key = config["api_key"]
        base_url = config["base_url"]

        # Get a new token using client credentials
        auth_url = f"{base_url}api/v1/auth/access_token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.SCRIPT_NAME,
            "client_secret": api_key,
        }
        auth_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

        try:
            auth_response = httpx.post(auth_url, data=auth_data, headers=auth_headers)
            auth_response.raise_for_status()

            token_data = auth_response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour

            if not access_token:
                raise Exception("Failed to get access token from ShotGrid")

            # Cache the token
            self._access_token = access_token
            self._token_expires_at = time.time() + expires_in - 300  # Expire 5 minutes early

            return access_token

        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise

    def _get_access_token_with_password(self) -> str:
        """Get or refresh the access token using password credentials"""
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at and time.time() < self._token_expires_at:
            return self._access_token

        # Get configuration
        config = self._get_shotgrid_config()
        username = config.get("username")
        password = config.get("password")
        base_url = config["base_url"]

        if not username or not password:
            raise Exception("Username and password required for password authentication")

        # Get a new token using password credentials
        auth_url = f"{base_url}api/v1/auth/access_token"
        auth_data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        auth_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

        try:
            auth_response = httpx.post(auth_url, data=auth_data, headers=auth_headers)
            auth_response.raise_for_status()

            token_data = auth_response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour

            if not access_token:
                raise Exception("Failed to get access token from ShotGrid")

            # Cache the token
            self._access_token = access_token
            self._token_expires_at = time.time() + expires_in - 300  # Expire 5 minutes early

            return access_token

        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise

    def _get_shotgrid_config(self):
        """Get ShotGrid configuration values"""
        api_key = self.get_config_value(service=self.SERVICE, value=self.API_KEY_ENV_VAR)
        base_url = self.get_config_value(service=self.SERVICE, value=self.SHOTGRID_URL_ENV_VAR)
        username = self.get_config_value(service=self.SERVICE, value=self.USERNAME_ENV_VAR)
        password = self.get_config_value(service=self.SERVICE, value=self.PASSWORD_ENV_VAR)

        if not base_url.endswith("/"):
            base_url += "/"

        return {"api_key": api_key, "base_url": base_url, "username": username, "password": password}
