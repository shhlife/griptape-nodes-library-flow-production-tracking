from typing import Any

from griptape_nodes.exe_types.core_types import NodeMessageResult, Parameter, ParameterGroup, ParameterMessage
from griptape_nodes.exe_types.node_types import ControlNode
from griptape_nodes.traits.button import Button, ButtonDetailsMessagePayload, OnClickMessageResultPayload


class AutodeskFlowConfiguration(ControlNode):
    """Configuration node for Autodesk Flow Production Tracking settings."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # Step 1: ShotGrid URL
        with ParameterGroup(
            name="Step_1_Autodesk_Flow_URL", ui_options={"display_name": "Step 1: Autodesk Flow URL"}
        ) as url_group:
            ParameterMessage(
                name="step1_message",
                title="Set Your Autodesk Flow URL",
                value="Enter your Autodesk Flow Production Tracking instance URL. \nThis is typically in the format: https://your-company.shotgrid.autodesk.com/",
                button_link="",
                button_text="",
                variant="info",
            )

            Parameter(
                name="shotgrid_url",
                type="string",
                default_value=self.get_config_value(service="Autodesk", value="SHOTGRID_URL") or "",
                tooltip="Your ShotGrid instance URL (e.g., https://your-company.shotgrid.autodesk.com/)",
                ui_options={
                    "display_name": "ShotGrid URL",
                    "placeholder": "https://your-company.shotgrid.autodesk.com/",
                },
            )

        self.add_node_element(url_group)

        # Step 2: Script Name
        with ParameterGroup(
            name="Step_2_Script Name", ui_options={"display_name": "Step 2: Script Name"}
        ) as script_group:
            ParameterMessage(
                name="step2_message",
                title="Configure Script Name",
                value="Set the name of your ShotGrid script. \nThis should match the script name you created in ShotGrid Admin > Scripts.",
                button_link="https://help.autodesk.com/view/SGDEV/ENU/?guid=SGD_py_python_api_create_manage_html",
                button_text="View Flow Documentation",
                variant="info",
            )

            Parameter(
                name="script_name",
                type="string",
                default_value=self.get_config_value(service="Autodesk", value="SHOTGRID_SCRIPT_NAME")
                or "Griptape Nodes",
                tooltip="Name of the script (should match the script name in ShotGrid)",
                ui_options={
                    "display_name": "Script Name",
                    "placeholder": "Griptape Nodes",
                },
            )

        self.add_node_element(script_group)

        # Step 3: API Key
        with ParameterGroup(name="Step_3_API_Key") as api_key_group:
            ParameterMessage(
                name="step3_message",
                title="Step 3: Set Your API Key",
                value="Configure your ShotGrid API Key (Script Key) in the settings.\nIf you don't have one, you can create one in ShotGrid Admin > Scripts,\nor ask your administrator for one.",
                button_link="#settings-secrets?filter=SHOTGRID_API_KEY",
                button_text="Open Settings",
                variant="info",
            )
        self.add_node_element(api_key_group)

        with ParameterGroup(name="Step_4_Check_Configuration") as check_config_group:
            # Step 4: Check Configuration
            ParameterMessage(
                name="step4_message",
                title="Step 4: Test Your Configuration",
                value="Click the button below to test your ShotGrid configuration and verify everything is working correctly.",
                button_link="",
                button_text="",
                variant="info",
            )

            # Check configuration button
            Parameter(
                name="configuration_status",
                type="string",
                default_value="",
                tooltip="Test your ShotGrid configuration",
                ui_options={"multiline": True, "is_full_width": True, "placeholder_text": "Configuration status..."},
                traits={
                    Button(
                        label="Check Configuration",
                        icon="check-circle",
                        on_click=self._check_configuration,
                        full_width=True,
                    )
                },
            )
        self.add_node_element(check_config_group)

    def after_value_set(self, parameter: Parameter, value: Any) -> None:
        """Automatically set config values when parameters are changed."""
        if parameter.name == "shotgrid_url":
            self.set_config_value(service="Autodesk", value="SHOTGRID_URL", new_value=value)
        elif parameter.name == "script_name":
            self.set_config_value(service="Autodesk", value="SHOTGRID_SCRIPT_NAME", new_value=value)

        return super().after_value_set(parameter, value)

    def _check_configuration(self, button: Button, button_details: ButtonDetailsMessagePayload) -> NodeMessageResult:
        """Check the ShotGrid configuration when button is clicked."""
        # Get configuration from parameters
        shotgrid_url = self.get_parameter_value("shotgrid_url")
        script_name = self.get_parameter_value("script_name")

        # Get API key from environment variables
        api_key = self.get_config_value(service="Autodesk", value="SHOTGRID_API_KEY")

        # Validate required fields
        if not shotgrid_url or not api_key:
            status_message = "❌ Configuration incomplete!\n\n"
            if not shotgrid_url:
                status_message += "• ShotGrid URL is required\n"
            if not api_key:
                status_message += "• API Key is required (set via SHOTGRID_API_KEY environment variable)\n"

            status_message += "\nTo complete configuration:\n"
            status_message += "• Set SHOTGRID_API_KEY environment variable\n"

            self.set_parameter_value("configuration_status", status_message)
            response = OnClickMessageResultPayload(button_details=button_details)
            return NodeMessageResult(success=False, details="Configuration incomplete", response=response)
        # Clean up URL
        if not shotgrid_url.endswith("/"):
            shotgrid_url += "/"

        # Test the configuration
        try:
            import httpx

            test_url = f"{shotgrid_url}api/v1/auth/access_token"
            test_data = {
                "grant_type": "client_credentials",
                "client_id": script_name,
                "client_secret": api_key,
            }
            test_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

            response = httpx.post(test_url, data=test_data, headers=test_headers, timeout=10)
            response.raise_for_status()

            # Configuration is valid
            status_message = "✅ Autodesk Flow configuration is valid!\n\n"
            status_message += f"📡 URL: {shotgrid_url}\n"
            status_message += f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}\n"
            status_message += f"📝 Script: {script_name}\n"
            status_message += "🔐 Using API key authentication\n"
            status_message += "\n🎉 You can now use other Autodesk Flow nodes!"

            self.set_parameter_value("configuration_status", status_message)
            response = OnClickMessageResultPayload(button_details=button_details)
            return NodeMessageResult(success=True, details="Configuration test successful", response=response)

        except Exception as e:
            status_message = f"❌ Configuration test failed: {e!s}\n\n"
            status_message += "Please check:\n"
            status_message += "• Autodesk Flow URL is correct\n"
            status_message += "• API Key is valid\n"
            status_message += "• Script name matches Autodesk Flow settings\n"
            status_message += "• Network connection is working"

            self.set_parameter_value("configuration_status", status_message)
            response = OnClickMessageResultPayload(button_details=button_details)
            return NodeMessageResult(success=False, details=f"Configuration test failed: {e!s}", response=response)

    def process(self) -> None:
        """Process the ShotGrid configuration."""
        # Configuration is now handled by the button click
        # This method is kept for compatibility but doesn't do anything
