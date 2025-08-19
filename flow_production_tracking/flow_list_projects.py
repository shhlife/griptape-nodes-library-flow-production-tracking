from typing import Any

import httpx
from base_shotgrid_node import BaseShotGridNode

from griptape_nodes.exe_types.core_types import Parameter, ParameterMode
from griptape_nodes.retained_mode.griptape_nodes import logger
from griptape_nodes.traits.options import Options

# Default choices - will be populated dynamically
PROJECT_CHOICES_ARGS = [
    {
        "name": "No projects available",
    },
]
PROJECT_CHOICES = [project["name"] for project in PROJECT_CHOICES_ARGS]


class FlowListProjects(BaseShotGridNode):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.add_parameter(
            Parameter(
                name="show_templates",
                type="boolean",
                default_value=False,
                tooltip="Include project templates in the list.",
            )
        )
        self.add_parameter(
            Parameter(
                name="show_only_templates",
                type="boolean",
                default_value=False,
                tooltip="Show only project templates.",
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_project",
                type="string",
                default_value="No projects available",
                tooltip="Select a project from the list.",
                allowed_modes={ParameterMode.INPUT, ParameterMode.PROPERTY},
                ui_options={
                    "display_name": "Select Project",
                    "data": [],
                    "icon_size": "medium",
                },
                traits={Options(choices=PROJECT_CHOICES)},
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_project_id",
                type="str",
                default_value="",
                allowed_modes={ParameterMode.OUTPUT},
                tooltip="ID of the selected project",
            )
        )
        self.add_parameter(
            Parameter(
                name="selected_project_data",
                type="json",
                default_value={},
                allowed_modes={ParameterMode.OUTPUT},
                tooltip="Complete data for the selected project",
                ui_options={"hide_property": True},
            )
        )
        self.add_parameter(
            Parameter(
                name="projects",
                output_type="json",
                type="json",
                default_value=None,
                tooltip="The projects to list.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hide_property": True},
            )
        )

    def _is_template(self, project_data: dict) -> bool:
        """Determine if a project is a template based on various fields"""
        # Check various fields that might indicate template status
        if project_data.get("template") is True:
            return True
        if project_data.get("is_template") is True:
            return True
        if project_data.get("sg_type") == "Template":
            return True
        if project_data.get("sg_status") == "Template":
            return True

        # Check if name or code contains "template" (case insensitive)
        name = project_data.get("name") or ""
        code = project_data.get("code") or ""
        name_lower = name.lower()
        code_lower = code.lower()
        if "template" in name_lower or "template" in code_lower:
            return True

        return False

    def after_value_set(self, parameter: Parameter, value: Any) -> None:
        if parameter.name == "selected_project" and value and value != "No projects available":
            # Find the selected choice and update outputs
            for choice in PROJECT_CHOICES_ARGS:
                if choice["name"] == value:
                    args = choice["args"]
                    self.parameter_output_values["selected_project_id"] = args["project_id"]
                    self.parameter_output_values["selected_project_data"] = args["project_data"]
                    self.publish_update_to_parameter("selected_project_id", args["project_id"])
                    self.publish_update_to_parameter("selected_project_data", args["project_data"])
                    break
        return super().after_value_set(parameter, value)

    def process(self) -> None:
        try:
            # Get access token
            access_token = self._get_access_token()

            # Make request to get projects
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            # Get base URL
            base_url = self._get_shotgrid_config()["base_url"]
            url = f"{base_url}api/v1/entity/projects"

            # Add fields to get thumbnail URLs and template info
            params = {
                "fields": "id,name,code,description,sg_status_list,image,sg_thumbnail,sg_type,sg_status,template,is_template"
            }

            logger.info(f"{self.name}: Getting projects via REST API")

            with httpx.Client() as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()

                data = response.json()
                projects = data.get("data", [])

                # Convert to list of dictionaries for output
                project_list = []
                choices_args = []
                choices_names = []

                for project in projects:
                    project_data = {
                        "id": project.get("id"),
                        "name": project.get("attributes", {}).get("name"),
                        "code": project.get("attributes", {}).get("code"),
                        "description": project.get("attributes", {}).get("description"),
                        "sg_status_list": project.get("attributes", {}).get("sg_status_list"),
                        "image": project.get("attributes", {}).get("image"),
                        "sg_thumbnail": project.get("attributes", {}).get("sg_thumbnail"),
                        "sg_type": project.get("attributes", {}).get("sg_type"),
                        "sg_status": project.get("attributes", {}).get("sg_status"),
                        "template": project.get("attributes", {}).get("template"),
                        "is_template": project.get("attributes", {}).get("is_template"),
                    }

                    # Determine if this is a template
                    is_template = self._is_template(project_data)

                    # Add the computed is_template field to the project data
                    project_data["is_template"] = is_template

                    # Apply filtering based on parameters
                    show_templates = self.get_parameter_value("show_templates")
                    show_only_templates = self.get_parameter_value("show_only_templates")

                    if show_only_templates and not is_template:
                        continue  # Skip non-templates
                    if not show_templates and not show_only_templates and is_template:
                        continue  # Skip templates when not showing them

                    project_list.append(project_data)

                    # Create choice for the dropdown
                    project_id = project_data["id"]
                    project_name = project_data["name"] or f"Project {project_id}"
                    project_code = project_data["code"] or ""

                    # Get thumbnail URL
                    thumbnail_url = project_data.get("sg_thumbnail") or project_data.get("image") or ""

                    # Add template indicator to display name
                    display_name = project_name
                    subtitle = project_code

                    if is_template:
                        display_name = f"📋 {project_name} (Template)"
                        if not subtitle:
                            subtitle = "Template"
                        else:
                            subtitle = f"{subtitle} (Template)"

                    choice = {
                        "name": display_name,
                        "icon": thumbnail_url,
                        "subtitle": subtitle,
                        "args": {
                            "project_id": project_id,
                            "project_data": project_data,
                        },
                    }
                    choices_args.append(choice)
                    choices_names.append(display_name)

                # Update global choices
                global PROJECT_CHOICES_ARGS, PROJECT_CHOICES
                PROJECT_CHOICES_ARGS = choices_args
                PROJECT_CHOICES = choices_names

                # Update the dropdown parameter with new choices
                if PROJECT_CHOICES and len(PROJECT_CHOICES) > 0:
                    # Get the current selected value to preserve it
                    current_selection = self.get_parameter_value("selected_project")

                    # If current selection is still valid, keep it; otherwise use first choice
                    if current_selection and current_selection in PROJECT_CHOICES:
                        selected_value = current_selection
                    else:
                        selected_value = PROJECT_CHOICES[0]

                    self._update_option_choices("selected_project", PROJECT_CHOICES, selected_value)
                    project_param = self.get_parameter_by_name("selected_project")
                    if project_param:
                        project_ui_options = project_param.ui_options
                        project_ui_options["data"] = PROJECT_CHOICES_ARGS
                        project_param.ui_options = project_ui_options
                    self.publish_update_to_parameter("selected_project", selected_value)
                else:
                    self._update_option_choices("selected_project", ["No projects available"], "No projects available")
                    project_param = self.get_parameter_by_name("selected_project")
                    if project_param:
                        project_param.ui_options["data"] = []

                # Output the projects
                self.parameter_output_values["projects"] = project_list
                logger.info(f"{self.name}: Retrieved {len(project_list)} projects via REST API")

        except Exception as e:
            logger.error(f"{self.name} encountered an error: {e!s}")
