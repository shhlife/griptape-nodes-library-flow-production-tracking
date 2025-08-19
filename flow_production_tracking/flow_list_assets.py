from typing import Any

import httpx
from base_shotgrid_node import BaseShotGridNode

from griptape_nodes.exe_types.core_types import Parameter, ParameterMode
from griptape_nodes.retained_mode.griptape_nodes import logger
from griptape_nodes.traits.options import Options

# Default choices - will be populated dynamically
ASSET_CHOICES = ["No assets available"]
ASSET_CHOICES_ARGS = []


class FlowListAssets(BaseShotGridNode):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_parameter(
            Parameter(
                name="project_id",
                type="string",
                default_value=None,
                tooltip="The ID of the project to list assets for.",
            )
        )
        self.add_parameter(
            Parameter(
                name="asset_type",
                type="string",
                default_value=None,
                tooltip="Filter assets by type (optional).",
                traits={
                    Options(
                        choices=[
                            "All Types",
                            "Character",
                            "Prop",
                            "Environment",
                            "Vehicle",
                            "FX",
                            "Camera",
                            "Light",
                            "Audio",
                        ]
                    )
                },
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_asset",
                type="string",
                default_value="No assets available",
                tooltip="Select an asset from the list.",
                allowed_modes={ParameterMode.INPUT, ParameterMode.PROPERTY},
                ui_options={
                    "display_name": "Select Asset",
                    "data": ASSET_CHOICES_ARGS,
                    "icon_size": "medium",
                },
                traits={Options(choices=ASSET_CHOICES)},
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_asset_id",
                output_type="string",
                type="string",
                default_value=None,
                tooltip="The ID of the selected asset.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hidden": True},
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_asset_data",
                output_type="json",
                type="json",
                default_value=None,
                tooltip="The data of the selected asset.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hidden": True},
            )
        )
        self.add_parameter(
            Parameter(
                name="assets",
                output_type="json",
                type="json",
                default_value=None,
                tooltip="The list of assets.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hide_property": True},
            )
        )

    def after_value_set(self, parameter: Parameter, value: Any) -> None:
        if parameter.name == "selected_asset" and value and value != "No assets available":
            # Find the selected choice and update outputs
            for choice in ASSET_CHOICES_ARGS:
                if choice["name"] == value:
                    args = choice["args"]
                    self.parameter_output_values["selected_asset_id"] = args["asset_id"]
                    self.parameter_output_values["selected_asset_data"] = args["asset_data"]
                    self.publish_update_to_parameter("selected_asset_id", args["asset_id"])
                    self.publish_update_to_parameter("selected_asset_data", args["asset_data"])
                    break
        return super().after_value_set(parameter, value)

    def process(self) -> None:
        try:
            # Get input parameters
            project_id = self.get_parameter_value("project_id")
            asset_type = self.get_parameter_value("asset_type")

            if not project_id:
                logger.error(f"{self.name}: project_id is required")
                return

            # Convert project_id to integer if it's a string
            try:
                project_id = int(project_id)
            except (ValueError, TypeError):
                logger.error(f"{self.name}: project_id must be a valid integer")
                return

            # Get access token
            access_token = self._get_access_token()

            # Make request to get assets
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            # Get base URL
            base_url = self._get_shotgrid_config()["base_url"]
            url = f"{base_url}api/v1/entity/assets"

            # Add fields to get thumbnail URLs - no complex filters, we'll filter in code
            params = {"fields": "id,code,name,sg_asset_type,sg_status_list,image,sg_thumbnail,project"}

            logger.info(f"{self.name}: Getting assets for project {project_id}")

            with httpx.Client() as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()

                data = response.json()
                all_assets = data.get("data", [])

                # Filter assets by project and optionally by asset type
                assets = []
                for asset in all_assets:
                    # Check if asset belongs to the specified project
                    asset_project = asset.get("relationships", {}).get("project", {}).get("data", {})
                    asset_project_id = asset_project.get("id")

                    if asset_project_id != project_id:
                        continue

                    # Check asset type filter if specified
                    if asset_type and asset_type != "All Types":
                        asset_type_value = asset.get("attributes", {}).get("sg_asset_type")
                        if asset_type_value != asset_type:
                            continue

                    assets.append(asset)

                # Convert to list of dictionaries for output
                asset_list = []
                choices_args = []
                choices_names = []

                for asset in assets:
                    asset_data = {
                        "id": asset.get("id"),
                        "code": asset.get("attributes", {}).get("code"),
                        "name": asset.get("attributes", {}).get("name"),
                        "sg_asset_type": asset.get("attributes", {}).get("sg_asset_type"),
                        "sg_status_list": asset.get("attributes", {}).get("sg_status_list"),
                        "image": asset.get("attributes", {}).get("image"),
                        "sg_thumbnail": asset.get("attributes", {}).get("sg_thumbnail"),
                        "project": asset.get("relationships", {}).get("project", {}).get("data", {}).get("id"),
                    }
                    asset_list.append(asset_data)

                    # Create choice for the dropdown
                    asset_id = asset_data["id"]
                    asset_name = asset_data["name"] or f"Asset {asset_id}"
                    asset_code = asset_data["code"] or ""
                    asset_type_name = asset_data["sg_asset_type"] or "Unknown"

                    # Get thumbnail URL
                    thumbnail_url = asset_data.get("sg_thumbnail") or asset_data.get("image") or ""

                    # Debug thumbnail URLs
                    logger.info(
                        f"{self.name}: Asset {asset_id} ({asset_code}) - sg_thumbnail: {asset_data.get('sg_thumbnail')}, image: {asset_data.get('image')}, final_url: {thumbnail_url}"
                    )

                    # Create display name with asset code as main text and type as subtitle
                    display_name = asset_code if asset_code else f"Asset {asset_id}"
                    subtitle = asset_type_name

                    choice = {
                        "name": display_name,
                        "icon": thumbnail_url,
                        "subtitle": subtitle,
                        "args": {
                            "asset_id": asset_id,
                            "asset_data": asset_data,
                        },
                    }
                    choices_args.append(choice)
                    choices_names.append(display_name)

                # Update global choices
                global ASSET_CHOICES_ARGS, ASSET_CHOICES
                ASSET_CHOICES_ARGS = choices_args
                ASSET_CHOICES = choices_names

                # Update the dropdown parameter with new choices
                if ASSET_CHOICES and len(ASSET_CHOICES) > 0:
                    # Get the current selected value to preserve it
                    current_selection = self.get_parameter_value("selected_asset")

                    # If current selection is still valid, keep it; otherwise use first choice
                    if current_selection and current_selection in ASSET_CHOICES:
                        selected_value = current_selection
                    else:
                        selected_value = ASSET_CHOICES[0]

                    self._update_option_choices("selected_asset", ASSET_CHOICES, selected_value)
                    asset_param = self.get_parameter_by_name("selected_asset")
                    if asset_param:
                        asset_ui_options = asset_param.ui_options
                        asset_ui_options["data"] = ASSET_CHOICES_ARGS
                        asset_param.ui_options = asset_ui_options
                    self.publish_update_to_parameter("selected_asset", selected_value)
                else:
                    self._update_option_choices("selected_asset", ["No assets available"], "No assets available")
                    asset_param = self.get_parameter_by_name("selected_asset")
                    if asset_param:
                        asset_param.ui_options["data"] = []

                # Output the assets
                self.parameter_output_values["assets"] = asset_list
                logger.info(f"{self.name}: Retrieved {len(asset_list)} assets for project {project_id}")

        except Exception as e:
            logger.error(f"{self.name} encountered an error: {e!s}")
