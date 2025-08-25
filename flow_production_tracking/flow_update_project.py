import urllib.parse
from typing import Any

import httpx
from base_shotgrid_node import BaseShotGridNode
from image_utils import convert_image_for_shotgrid, get_mime_type, should_convert_image

from griptape_nodes.exe_types.core_types import Parameter, ParameterGroup, ParameterMessage, ParameterMode
from griptape_nodes.retained_mode.griptape_nodes import logger


class FlowUpdateProject(BaseShotGridNode):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # Dynamic message that will be updated with the updated project link - placed at top for prominence
        self.project_message = ParameterMessage(
            name="project_message",
            title="Project Management",
            value="Update a project to see the link to view it in ShotGrid. Click the button to view all projects.",
            button_link="https://griptape-ai.shotgrid.autodesk.com/projects",
            button_text="View All Projects",
            variant="info",
            full_width=True,
        )
        self.add_node_element(self.project_message)

        # Set the initial link to the main projects page
        self._update_project_message_initial()

        with ParameterGroup(name="project_input") as project_input:
            self.add_parameter(
                Parameter(
                    name="project_id",
                    output_type="string",
                    type="string",
                    default_value=None,
                    tooltip="The ID of the project to update.",
                )
            )
            self.add_parameter(
                Parameter(
                    name="project_name",
                    type="string",
                    default_value=None,
                    tooltip="The new name for the project (optional).",
                )
            )
            self.add_parameter(
                Parameter(
                    name="project_code",
                    type="string",
                    default_value=None,
                    tooltip="The new code for the project (optional).",
                )
            )
            self.add_parameter(
                Parameter(
                    name="project_description",
                    type="string",
                    default_value=None,
                    tooltip="The new description for the project (optional).",
                )
            )
            self.add_parameter(
                Parameter(
                    name="thumbnail_image",
                    type="ImageUrlArtifact",
                    default_value=None,
                    tooltip="The new thumbnail image for the project (optional).",
                    ui_options={
                        "clickable_file_browser": True,
                        "expander": True,
                    },
                )
            )
            self.add_parameter(
                Parameter(
                    name="updated_project",
                    output_type="json",
                    type="json",
                    default_value=None,
                    tooltip="The updated project data.",
                    allowed_modes={ParameterMode.OUTPUT},
                    ui_options={"hide_property": True},
                )
            )

    def _download_image_from_url(self, image_url: str) -> bytes:
        """Download image from URL and return as bytes"""
        try:
            with httpx.Client() as client:
                response = client.get(image_url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"{self.name}: Failed to download image from URL: {e}")
            raise

    def _get_upload_url(self, project_id: int, filename: str, access_token: str, base_url: str) -> dict:
        """Get upload URL for project thumbnail"""
        try:
            # URL-encode the filename to handle special characters
            encoded_filename = urllib.parse.quote(filename)
            upload_url = f"{base_url}api/v1/entity/projects/{project_id}/image/_upload?filename={encoded_filename}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            logger.info(f"{self.name}: Requesting upload URL for project {project_id} with filename '{filename}'")

            with httpx.Client() as client:
                response = client.get(upload_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                logger.info(f"{self.name}: Got upload URL response")
                return data

        except Exception as e:
            logger.error(f"{self.name}: Failed to get upload URL: {e}")
            raise

    def _upload_file_to_url(self, upload_url: str, image_bytes: bytes, mime_type: str) -> dict:
        """Upload file to the provided upload URL"""
        try:
            headers = {
                "Content-Type": mime_type,
                "Content-Length": str(len(image_bytes)),
            }

            logger.info(f"{self.name}: Uploading file to ShotGrid")

            with httpx.Client() as client:
                response = client.put(upload_url, headers=headers, content=image_bytes)
                response.raise_for_status()

                # Try to parse JSON response if available
                try:
                    data = response.json()
                    logger.info(f"{self.name}: File uploaded successfully with response data")
                    return data
                except:
                    # If no JSON response, that's okay for S3 uploads
                    logger.info(f"{self.name}: File uploaded successfully (no JSON response)")
                    return {"success": True}

        except Exception as e:
            logger.error(f"{self.name}: Failed to upload file: {e}")
            raise

    def _complete_upload(self, project_id: int, upload_info: dict, access_token: str, base_url: str) -> dict:
        """Complete the upload process and return the file ID"""
        try:
            complete_url = f"{base_url}api/v1/entity/projects/{project_id}/image/_upload"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Try different completion data structures
            # Option 1: Just the upload_info
            # complete_data = upload_info

            # Option 2: Wrap in upload_info key (if that's what the API expects)
            # complete_data = {"upload_info": upload_info}

            # Option 3: Include additional fields that might be required
            complete_data = {"upload_info": upload_info, "upload_data": {}}

            logger.info(f"{self.name}: Completing upload for project {project_id}")

            with httpx.Client() as client:
                response = client.post(complete_url, headers=headers, json=complete_data)

                # Log the response for debugging
                logger.info(f"{self.name}: Completion response status: {response.status_code}")

                response.raise_for_status()

                # Handle empty response (which is normal for successful completion)
                if response.text.strip():
                    try:
                        data = response.json()
                        logger.info(f"{self.name}: Completion response: {data}")
                    except:
                        logger.info(f"{self.name}: Completion response text: {response.text}")
                        data = {"success": True}
                else:
                    logger.info(f"{self.name}: Completion successful (empty response)")
                    data = {"success": True}

                logger.info(f"{self.name}: Upload completed successfully")
                return data

        except Exception as e:
            logger.error(f"{self.name}: Failed to complete upload: {e}")
            raise

    def _get_project_data(self, project_id: int, access_token: str, base_url: str) -> dict:
        """Get project data to check if image field was updated"""
        try:
            project_url = f"{base_url}api/v1/entity/projects/{project_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            logger.info(f"{self.name}: Getting project data for {project_id}")

            with httpx.Client() as client:
                response = client.get(project_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                logger.info(f"{self.name}: Got project data")
                return data

        except Exception as e:
            logger.error(f"{self.name}: Failed to get project data: {e}")
            raise

    def _update_project_thumbnail(self, project_id: int, thumbnail_image, access_token: str, base_url: str) -> str:
        """Update the project thumbnail and return the file ID"""
        try:
            # Step 1: Download the image from the URL
            logger.info(f"{self.name}: Downloading image from URL")
            thumbnail_url = thumbnail_image.value
            image_bytes = self._download_image_from_url(thumbnail_url)

            # Step 2: Determine filename and MIME type
            # Extract filename from URL or generate one
            if hasattr(thumbnail_image, "name") and thumbnail_image.name:
                filename = thumbnail_image.name
            else:
                # Generate filename from URL
                url_path = thumbnail_url.split("/")[-1]
                if "?" in url_path:
                    url_path = url_path.split("?")[0]
                # Ensure we have a valid filename with extension
                if "." in url_path and len(url_path) > 1:
                    filename = url_path
                else:
                    # Default filename if we can't extract one
                    filename = "project_thumbnail.jpg"

            # Clean up filename - remove any problematic characters
            filename = filename.replace(" ", "_").replace("&", "and")

            # Ensure filename has an extension
            if "." not in filename:
                filename += ".jpg"

            # Step 2.5: Convert image if needed (e.g., WebP to PNG)
            if should_convert_image(filename):
                logger.info(f"{self.name}: Converting image format for ShotGrid compatibility")
                image_bytes, filename = convert_image_for_shotgrid(image_bytes, filename)
                logger.info(f"{self.name}: Converted to {filename}")

            # Determine MIME type
            mime_type = get_mime_type(filename)

            logger.info(f"{self.name}: Using filename '{filename}' with MIME type '{mime_type}'")

            # Step 3: Get upload URL
            logger.info(f"{self.name}: Getting upload URL")
            upload_response = self._get_upload_url(project_id, filename, access_token, base_url)

            # Log the full response for debugging
            logger.info(f"{self.name}: Full upload response: {upload_response}")

            upload_url = upload_response.get("links", {}).get("upload")
            upload_info = upload_response.get("data", {})

            if not upload_url:
                logger.error(f"{self.name}: No upload URL found in response")
                logger.error(f"{self.name}: Available keys in response: {list(upload_response.keys())}")
                if "links" in upload_response:
                    logger.error(f"{self.name}: Available links: {list(upload_response['links'].keys())}")
                raise Exception("Failed to get upload URL from ShotGrid")

            # Step 4: Upload the file
            logger.info(f"{self.name}: Uploading file")
            upload_result = self._upload_file_to_url(upload_url, image_bytes, mime_type)

            # Step 5: Complete the upload
            logger.info(f"{self.name}: Completing upload")
            completion_response = self._complete_upload(project_id, upload_info, access_token, base_url)

            # Get the file ID from the completion response
            upload_id = completion_response.get("data", {}).get("id")

            if not upload_id:
                logger.info(f"{self.name}: No file ID in completion response, checking project image field")
                # If no file ID in completion response, the upload might have automatically
                # updated the project's image field. Let's get the current project data.
                try:
                    project_response = self._get_project_data(project_id, access_token, base_url)
                    project_data = project_response.get("data", {})
                    upload_id = project_data.get("attributes", {}).get("image")

                    if upload_id:
                        logger.info(f"{self.name}: Found file ID in project image field: {upload_id}")
                        # Check if it's a pending thumbnail URL
                        if "thumbnail_pending" in upload_id:
                            logger.info(f"{self.name}: Thumbnail is still processing, not updating project")
                            upload_id = "pending_thumbnail"
                    else:
                        logger.warning(f"{self.name}: No file ID found in project image field")
                        # Continue anyway - the upload might have succeeded
                        upload_id = "uploaded_file"  # Placeholder
                except Exception as e:
                    logger.warning(f"{self.name}: Could not get project data: {e}")
                    upload_id = "uploaded_file"  # Placeholder

            return upload_id

        except Exception as e:
            logger.error(f"{self.name}: Failed to update project thumbnail: {e}")
            raise

    def _update_project_message(self, project_id: int, project_name: str) -> None:
        """Update the ParameterMessage with a link to the updated project."""
        try:
            # Construct the URL for the updated project
            base_url = self._get_shotgrid_config()["base_url"]
            project_url = f"{base_url}#!/project/{project_id}"

            # Update the button_link and value of the ParameterMessage
            self.project_message.button_link = project_url
            self.project_message.value = (
                f"Project '{project_name}' updated successfully! Click the button to view it in ShotGrid."
            )
            logger.info(f"{self.name}: ParameterMessage updated with project link: {project_url}")
        except Exception as e:
            logger.error(f"{self.name}: Failed to update ParameterMessage with project link: {e}")

    def _update_project_message_initial(self) -> None:
        """Set the initial value of the ParameterMessage to the main projects page."""
        try:
            base_url = self._get_shotgrid_config()["base_url"]
            self.project_message.value = (
                "Update a project to see the link to view it in ShotGrid. Click the button to view all projects."
            )
            self.project_message.button_link = f"{base_url}#!/projects"
            logger.info(f"{self.name}: ParameterMessage initialized with main projects link.")
        except Exception as e:
            logger.error(f"{self.name}: Failed to initialize ParameterMessage with main projects link: {e}")

    def after_value_set(self, parameter: Parameter, value: Any) -> None:
        """Update the ParameterMessage when project_id changes to show a link to that specific project."""
        if parameter.name == "project_id" and value:
            try:
                # Get access token and base URL
                access_token = self._get_access_token()
                base_url = self._get_shotgrid_config()["base_url"]

                # Make API call to get project data (which includes the proper URL)
                project_url = f"{base_url}api/v1/entity/projects/{value}"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }

                with httpx.Client() as client:
                    response = client.get(project_url, headers=headers)
                    if response.status_code == 200:
                        project_data = response.json()
                        # Get the self link from the project data
                        shotgrid_url = project_data.get("data", {}).get("links", {}).get("self", "")

                        if shotgrid_url:
                            # Construct the full URL by combining base URL with the self link
                            # The self link is relative (e.g., "/api/v1/entity/projects/222")
                            # We need to convert it to a web URL (e.g., "https://griptape-ai.shotgrid.autodesk.com/detail/Project/222")
                            full_url = f"{base_url}detail/Project/{value}"

                            # Update the ParameterMessage to show the specific project
                            message_param = self.get_element_by_name_and_type("project_message", ParameterMessage)
                            message_param.button_text = f"View Project (ID: {value})"
                            message_param.button_link = full_url
                            message_param.value = f"Update project ID {value}. Click the button to view it in ShotGrid."

                            logger.info(f"{self.name}: Updated project message to show project {value}")
                        else:
                            logger.warning(f"{self.name}: No self link found in project data for {value}")
                    else:
                        logger.warning(f"{self.name}: Failed to get project data for {value}: {response.status_code}")

            except Exception as e:
                logger.warning(f"{self.name}: Failed to update project message for project {value}: {e}")

        return super().after_value_set(parameter, value)

    def process(self) -> None:
        try:
            # Get input parameters
            project_id = self.get_parameter_value("project_id")
            project_name = self.get_parameter_value("project_name")
            project_code = self.get_parameter_value("project_code")
            project_description = self.get_parameter_value("project_description")
            thumbnail_image = self.get_parameter_value("thumbnail_image")

            if not project_id:
                logger.error(f"{self.name}: project_id is required")
                return

            # Convert project_id to integer if it's a string
            try:
                project_id = int(project_id)
            except (ValueError, TypeError):
                logger.error(f"{self.name}: project_id must be a valid integer")
                return

            # Get access token and base URL
            access_token = self._get_access_token()
            base_url = self._get_shotgrid_config()["base_url"]

            # Prepare update data for basic project fields
            update_data = {}
            has_basic_updates = False

            if project_name is not None:
                update_data["name"] = project_name
                has_basic_updates = True

            if project_code is not None:
                update_data["code"] = project_code
                has_basic_updates = True

            if project_description is not None:
                update_data["sg_description"] = project_description
                has_basic_updates = True

            # Update basic project fields if any are provided
            if has_basic_updates:
                logger.info(f"{self.name}: Updating basic project fields")
                try:
                    # Try password authentication first for better permissions
                    try:
                        access_token = self._get_access_token_with_password()
                        logger.info(f"{self.name}: Using password authentication")
                    except Exception as e:
                        logger.warning(
                            f"{self.name}: Password authentication failed, falling back to client credentials: {e}"
                        )
                        access_token = self._get_access_token()

                    update_url = f"{base_url}api/v1/entity/projects/{project_id}"
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }

                    logger.info(f"{self.name}: Updating project {project_id} with data: {update_data}")

                    with httpx.Client() as client:
                        response = client.put(update_url, headers=headers, json=update_data)
                        response.raise_for_status()

                        data = response.json()
                        updated_project = data.get("data", {})
                        logger.info(f"{self.name}: Basic project fields updated successfully")
                except Exception as e:
                    logger.error(f"{self.name}: Failed to update basic project fields: {e}")
                    raise

            # Update thumbnail if provided
            if thumbnail_image:
                logger.info(f"{self.name}: Updating project thumbnail")
                try:
                    upload_id = self._update_project_thumbnail(project_id, thumbnail_image, access_token, base_url)
                    logger.info(f"{self.name}: Thumbnail update completed")
                except Exception as e:
                    logger.error(f"{self.name}: Failed to update thumbnail: {e}")
                    raise

            # Get final project data
            try:
                project_response = self._get_project_data(project_id, access_token, base_url)
                final_project_data = project_response.get("data", {})
                logger.info(f"{self.name}: Retrieved final project data")
            except Exception as e:
                logger.warning(f"{self.name}: Could not get final project data: {e}")
                # Use the updated project data from the basic update if available
                final_project_data = updated_project if has_basic_updates else {"id": project_id, "status": "updated"}

            # Output the results
            self.parameter_output_values["updated_project"] = final_project_data

            logger.info(f"{self.name}: Successfully updated project {project_id}")

            # Update the ParameterMessage with a link to the updated project
            self._update_project_message(project_id, project_name)

        except Exception as e:
            logger.error(f"{self.name} encountered an error: {e!s}")
