import time
from typing import Any

import httpx
from base_shotgrid_node import BaseShotGridNode
from image_utils import convert_image_for_shotgrid, get_mime_type, should_convert_image

from griptape_nodes.exe_types.core_types import Parameter, ParameterMode
from griptape_nodes.retained_mode.griptape_nodes import logger
from griptape_nodes.traits.options import Options


class FlowCreateAsset(BaseShotGridNode):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_parameter(
            Parameter(
                name="project_id",
                type="string",
                default_value=None,
                tooltip="The ID of the project to create the asset in.",
            )
        )
        self.add_parameter(
            Parameter(
                name="asset_code",
                type="string",
                default_value=None,
                tooltip="The code for the asset to create.",
            )
        )
        self.add_parameter(
            Parameter(
                name="asset_type",
                type="string",
                default_value="Character",
                tooltip="The type of asset to create (e.g., Character, Prop, Environment).",
                traits={
                    Options(choices=["Character", "Prop", "Environment", "Vehicle", "FX", "Camera", "Light", "Audio"])
                },
            )
        )
        self.add_parameter(
            Parameter(
                name="asset_description",
                type="string",
                default_value=None,
                tooltip="The description for the asset to create.",
            )
        )
        self.add_parameter(
            Parameter(
                name="thumbnail_image",
                type="ImageUrlArtifact",
                default_value=None,
                tooltip="The thumbnail image for the asset (optional).",
                ui_options={
                    "clickable_file_browser": True,
                    "expander": True,
                },
            )
        )
        self.add_parameter(
            Parameter(
                name="created_asset",
                output_type="json",
                type="json",
                default_value=None,
                tooltip="The created asset data.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hide_property": True},
            )
        )
        self.add_parameter(
            Parameter(
                name="asset_id",
                output_type="string",
                type="string",
                default_value=None,
                tooltip="The ID of the newly created asset.",
                allowed_modes={ParameterMode.OUTPUT},
                ui_options={"hide_property": True},
            )
        )

    def after_value_set(self, parameter: Parameter, value: Any) -> None:
        if parameter.name == "project_id" and value:
            # When project_id changes, fetch and update asset types
            try:
                # Get access token
                access_token = self._get_access_token()
                base_url = self._get_shotgrid_config()["base_url"]

                # Make request to get asset types for the project
                headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
                url = f"{base_url}api/v1/schema/Asset"
                params = {"project_id": int(value)}

                logger.info(f"{self.name}: Getting asset types for project {value}")

                with httpx.Client() as client:
                    response = client.get(url, headers=headers, params=params)
                    response.raise_for_status()

                    data = response.json()
                    asset_schema = data.get("data", {})

                    # Extract asset types from the schema
                    asset_types = []

                    # Look for asset type fields in the schema
                    if "properties" in asset_schema:
                        properties = asset_schema["properties"]

                        # Check for sg_asset_type field which typically contains asset types
                        if "sg_asset_type" in properties:
                            sg_asset_type_field = properties["sg_asset_type"]
                            if (
                                "properties" in sg_asset_type_field
                                and "properties" in sg_asset_type_field["properties"]
                            ):
                                # This might contain the allowed values
                                allowed_values = sg_asset_type_field.get("properties", {}).get("properties", {})
                                for value_key, value_info in allowed_values.items():
                                    asset_types.append(value_key)

                    # If we didn't find asset types in the schema, provide common defaults
                    if not asset_types:
                        logger.info(f"{self.name}: No specific asset types found, using common defaults")
                        asset_types = ["Character", "Prop", "Environment", "Vehicle", "FX", "Camera", "Light", "Audio"]

                    # Update the asset_type parameter with the new choices
                    if asset_types:
                        self._update_option_choices("asset_type", asset_types, asset_types[0])
                        logger.info(f"{self.name}: Updated asset_type choices: {asset_types}")
                    else:
                        self._update_option_choices(
                            "asset_type", ["No asset types available"], "No asset types available"
                        )

            except Exception as e:
                logger.warning(f"{self.name}: Could not get asset types for project {value}: {e}")
                self._update_option_choices("asset_type", ["No asset types available"], "No asset types available")

        return super().after_value_set(parameter, value)

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

    def _get_upload_url(self, asset_id: int, filename: str, access_token: str, base_url: str) -> dict:
        """Get upload URL for asset thumbnail"""
        try:
            # Try the upload endpoint for assets
            upload_url = f"{base_url}api/v1/entity/assets/{asset_id}/upload"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            logger.info(f"{self.name}: Requesting file upload for asset {asset_id} with filename '{filename}'")
            logger.info(f"{self.name}: Upload URL request: {upload_url}")

            # For this endpoint, we don't need to get an upload URL first
            # We can directly upload the file
            return {"upload_url": upload_url, "method": "POST", "headers": headers}

        except Exception as e:
            logger.error(f"{self.name}: Failed to prepare file upload: {e}")
            raise

    def _upload_file_to_url(self, upload_url: str, image_bytes: bytes, mime_type: str, headers: dict = None) -> dict:
        """Upload file to the provided upload URL"""
        try:
            if headers is None:
                headers = {}

            # Add content type and length headers
            headers.update(
                {
                    "Content-Type": mime_type,
                    "Content-Length": str(len(image_bytes)),
                }
            )

            logger.info(f"{self.name}: Uploading file to ShotGrid")

            with httpx.Client() as client:
                response = client.post(upload_url, headers=headers, content=image_bytes)
                response.raise_for_status()

                # Try to parse JSON response if available
                try:
                    data = response.json()
                    logger.info(f"{self.name}: File uploaded successfully with response data")
                    return data
                except:
                    # If no JSON response, that's okay
                    logger.info(f"{self.name}: File uploaded successfully (no JSON response)")
                    return {"success": True}

        except Exception as e:
            logger.error(f"{self.name}: Failed to upload file: {e}")
            raise

    def _complete_upload(self, asset_id: int, upload_result: dict, access_token: str, base_url: str) -> dict:
        """Complete the upload process and return the file ID"""
        try:
            # For the new file upload endpoint, the upload might be complete already
            # Let's check if we got a file ID in the upload result
            if upload_result and "data" in upload_result:
                logger.info(f"{self.name}: Upload completed with file ID in response")
                return upload_result

            # If no file ID in upload result, try to get asset data to see if image was updated
            logger.info(f"{self.name}: Checking if upload automatically updated asset image field")
            try:
                asset_response = self._get_asset_data(asset_id, access_token, base_url)
                asset_data = asset_response.get("data", {})
                image_url = asset_data.get("attributes", {}).get("image")

                if image_url:
                    logger.info(f"{self.name}: Found image URL in asset data: {image_url}")
                    return {"data": {"id": image_url}}
                logger.info(f"{self.name}: No image URL found in asset data")
                return {"success": True}

            except Exception as e:
                logger.warning(f"{self.name}: Could not get asset data: {e}")
                return {"success": True}

        except Exception as e:
            logger.error(f"{self.name}: Failed to complete upload: {e}")
            raise

    def _get_asset_data(self, asset_id: int, access_token: str, base_url: str) -> dict:
        """Get asset data to check if image field was updated"""
        try:
            asset_url = f"{base_url}api/v1/entity/assets/{asset_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            logger.info(f"{self.name}: Getting asset data for {asset_id}")

            with httpx.Client() as client:
                response = client.get(asset_url, headers=headers)
                response.raise_for_status()

                data = response.json()
                logger.info(f"{self.name}: Got asset data")
                return data

        except Exception as e:
            logger.error(f"{self.name}: Failed to get asset data: {e}")
            raise

    def _update_asset_thumbnail(self, asset_id: int, thumbnail_image, access_token: str, base_url: str) -> str:
        """Update the asset thumbnail and return the file ID"""
        try:
            # Step 1: Download the image from the URL
            logger.info(f"{self.name}: Downloading image from URL")

            # Handle both ImageUrlArtifact and dictionary formats
            if hasattr(thumbnail_image, "value"):
                # It's an ImageUrlArtifact
                thumbnail_url = thumbnail_image.value
            elif isinstance(thumbnail_image, dict) and "value" in thumbnail_image:
                # It's a dictionary with a value field
                thumbnail_url = thumbnail_image["value"]
            elif isinstance(thumbnail_image, str):
                # It's a direct string URL
                thumbnail_url = thumbnail_image
            else:
                logger.error(f"{self.name}: Invalid thumbnail_image format: {type(thumbnail_image)}")
                raise Exception("Invalid thumbnail format")

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
                    filename = "asset_thumbnail.jpg"

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

            # Step 3: Try the correct ShotGrid file upload approach
            logger.info(f"{self.name}: Attempting asset thumbnail upload using correct ShotGrid API")

            # Step 3a: Get upload URL for the image field (use project-style endpoint)
            try:
                upload_url = f"{base_url}api/v1/entity/assets/{asset_id}/image/_upload?filename={filename}"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }

                logger.info(f"{self.name}: Requesting upload URL for asset image: {upload_url}")

                with httpx.Client() as client:
                    response = client.get(upload_url, headers=headers)
                    if response.status_code == 200:
                        upload_data = response.json()
                        logger.info(f"{self.name}: Got upload response: {upload_data}")

                        # Extract upload URL and info
                        upload_link = upload_data.get("links", {}).get("upload")
                        upload_info = upload_data.get("data", {})

                        if upload_link:
                            # Step 3b: Upload file to S3
                            logger.info(f"{self.name}: Uploading file to S3: {upload_link}")
                            upload_headers = {
                                "Content-Type": mime_type,
                                "Content-Length": str(len(image_bytes)),
                            }

                            upload_response = client.put(upload_link, headers=upload_headers, content=image_bytes)
                            if upload_response.status_code == 200:
                                logger.info(f"{self.name}: File uploaded successfully to S3")

                                # Step 3c: Complete upload (use project-style endpoint)
                                complete_url = f"{base_url}api/v1/entity/assets/{asset_id}/image/_upload"
                                complete_headers = {
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json",
                                }

                                # For assets, we need to try the completion request even when upload_id is None
                                # (unlike projects where it updates automatically)
                                complete_data = {"upload_info": upload_info, "upload_data": {}}

                                logger.info(f"{self.name}: Completing upload for asset image")
                                logger.info(f"{self.name}: Completion URL: {complete_url}")
                                logger.info(f"{self.name}: Completion data: {complete_data}")

                                complete_response = client.post(
                                    complete_url, headers=complete_headers, json=complete_data
                                )

                                logger.info(f"{self.name}: Completion response status: {complete_response.status_code}")
                                try:
                                    completion_data = complete_response.json()
                                    logger.info(f"{self.name}: Completion response: {completion_data}")
                                except:
                                    logger.info(f"{self.name}: Completion response text: {complete_response.text}")

                                if complete_response.status_code in [200, 201]:
                                    logger.info(f"{self.name}: Upload completed successfully")
                                    # Check if the asset's image field was updated
                                    result = self._check_asset_image_field(asset_id, access_token, base_url)
                                    logger.info(f"{self.name}: Post-completion check result: {result}")
                                    return result
                                logger.warning(f"{self.name}: Completion failed: {complete_response.status_code}")
                            else:
                                logger.warning(f"{self.name}: File upload failed: {upload_response.status_code}")
                        else:
                            logger.warning(f"{self.name}: No upload link found in response")
                    else:
                        logger.warning(f"{self.name}: Upload URL request failed: {response.status_code}")

            except Exception as e:
                logger.warning(f"{self.name}: Correct ShotGrid upload failed: {e}")

            # Fallback: Try direct field update
            logger.info(f"{self.name}: Trying direct field update as fallback")
            return self._try_direct_field_update(asset_id, thumbnail_url, access_token, base_url)

        except Exception as e:
            logger.error(f"{self.name}: Failed to update asset thumbnail: {e}")
            raise

    def _try_direct_field_update(self, asset_id: int, thumbnail_url: str, access_token: str, base_url: str) -> str:
        """Try updating the asset's image field directly"""
        try:
            update_url = f"{base_url}api/v1/entity/assets/{asset_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            update_data = {"image": thumbnail_url}

            with httpx.Client() as client:
                response = client.put(update_url, headers=headers, json=update_data)

                if response.status_code == 200:
                    logger.info(f"{self.name}: Successfully updated asset image field directly")
                    return self._check_asset_image_field(asset_id, access_token, base_url)
                logger.warning(f"{self.name}: Direct field update failed: {response.status_code}")
                return "update_failed"

        except Exception as e:
            logger.warning(f"{self.name}: Direct field update exception: {e}")
            return "update_exception"

    def _check_asset_image_field(self, asset_id: int, access_token: str, base_url: str) -> str:
        """Check if the asset's image field was updated and return the file ID"""
        try:
            logger.info(f"{self.name}: Checking asset image field for {asset_id}")
            asset_response = self._get_asset_data(asset_id, access_token, base_url)
            asset_data = asset_response.get("data", {})
            image_url = asset_data.get("attributes", {}).get("image")

            if image_url:
                logger.info(f"{self.name}: Found updated image URL: {image_url}")
                return image_url
            logger.warning(f"{self.name}: No image URL found in asset data")
            return "no_image"

        except Exception as e:
            logger.warning(f"{self.name}: Could not check asset image field: {e}")
            return "check_failed"

    def process(self) -> None:
        try:
            # Get input parameters
            project_id = self.get_parameter_value("project_id")
            asset_code = self.get_parameter_value("asset_code")
            asset_type = self.get_parameter_value("asset_type")
            asset_description = self.get_parameter_value("asset_description")
            thumbnail_image = self.get_parameter_value("thumbnail_image")

            if not project_id:
                logger.error(f"{self.name}: project_id is required")
                return

            if not asset_code:
                logger.error(f"{self.name}: asset_code is required")
                return

            if not asset_type:
                logger.error(f"{self.name}: asset_type is required")
                return

            # Get access token
            access_token = self._get_access_token()
            base_url = self._get_shotgrid_config()["base_url"]

            # Prepare asset data
            asset_data = {
                "code": asset_code,
                "sg_asset_type": asset_type,
                "project": {"type": "Project", "id": int(project_id)},
            }

            if asset_description:
                asset_data["description"] = asset_description

            # Try password authentication first for better permissions
            try:
                access_token = self._get_access_token_with_password()
                logger.info(f"{self.name}: Using password authentication")
            except Exception as e:
                logger.warning(f"{self.name}: Password authentication failed, falling back to client credentials: {e}")
                access_token = self._get_access_token()

            # Create the asset
            url = f"{self._get_shotgrid_config()['base_url']}api/v1/entity/assets"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            logger.info(f"{self.name}: Creating asset with data: {asset_data}")

            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=asset_data)

                # Log the response for debugging
                logger.info(f"{self.name}: Create response status: {response.status_code}")
                try:
                    error_data = response.json()
                    logger.info(f"{self.name}: Create response: {error_data}")
                except:
                    logger.info(f"{self.name}: Create response text: {response.text}")

                response.raise_for_status()

                data = response.json()
                created_asset = data.get("data", {})
                asset_id = created_asset.get("id")

                logger.info(f"{self.name}: Asset created successfully with ID: {asset_id}")

            # Upload thumbnail if provided
            if thumbnail_image and asset_id:
                logger.info(f"{self.name}: Uploading thumbnail for newly created asset {asset_id}")

                # Handle both ImageUrlArtifact and dictionary formats
                if hasattr(thumbnail_image, "value"):
                    # It's an ImageUrlArtifact
                    thumbnail_url = thumbnail_image.value
                    logger.info(f"{self.name}: Thumbnail image value: {thumbnail_url}")
                elif isinstance(thumbnail_image, dict) and "value" in thumbnail_image:
                    # It's a dictionary with a value field
                    thumbnail_url = thumbnail_image["value"]
                    logger.info(f"{self.name}: Thumbnail image value from dict: {thumbnail_url}")
                elif isinstance(thumbnail_image, str):
                    # It's a direct string URL
                    thumbnail_url = thumbnail_image
                    logger.info(f"{self.name}: Thumbnail image value from string: {thumbnail_url}")
                else:
                    logger.error(f"{self.name}: Invalid thumbnail_image format: {type(thumbnail_image)}")
                    thumbnail_url = None

                if thumbnail_url:
                    # Create a simple object to pass to _update_asset_thumbnail
                    class ThumbnailWrapper:
                        def __init__(self, url):
                            self.value = url

                    thumbnail_wrapper = ThumbnailWrapper(thumbnail_url)

                    # Add a longer delay to ensure asset is fully created
                    logger.info(f"{self.name}: Waiting 5 seconds for asset to be fully available...")
                    time.sleep(5)

                    # Try thumbnail upload with retries
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            logger.info(
                                f"{self.name}: Attempting thumbnail upload (attempt {attempt + 1}/{max_retries})"
                            )
                            upload_id = self._update_asset_thumbnail(
                                asset_id, thumbnail_wrapper, access_token, base_url
                            )
                            logger.info(f"{self.name}: Thumbnail uploaded successfully with upload_id: {upload_id}")
                            break  # Success, exit retry loop
                        except Exception as e:
                            logger.warning(f"{self.name}: Thumbnail upload attempt {attempt + 1} failed: {e}")
                            if attempt < max_retries - 1:
                                logger.info(f"{self.name}: Waiting 3 seconds before retry...")
                                time.sleep(3)
                            else:
                                logger.error(f"{self.name}: All thumbnail upload attempts failed")
                                logger.error(
                                    f"{self.name}: Thumbnail upload exception details: {type(e).__name__}: {e!s}"
                                )
                                # Don't fail the entire operation if thumbnail upload fails
                                # The asset was still created successfully
            elif thumbnail_image and not asset_id:
                logger.error(f"{self.name}: Cannot upload thumbnail - asset_id is None")
            elif not thumbnail_image:
                logger.info(f"{self.name}: No thumbnail provided, skipping thumbnail upload")

            # Get final asset data
            try:
                asset_response = self._get_asset_data(asset_id, access_token, base_url)
                final_asset_data = asset_response.get("data", {})
                logger.info(f"{self.name}: Retrieved final asset data")
            except Exception as e:
                logger.warning(f"{self.name}: Could not get final asset data: {e}")
                # Use the created asset data if we can't get the final data
                final_asset_data = created_asset

            # Output the results
            self.parameter_output_values["created_asset"] = final_asset_data
            self.parameter_output_values["asset_id"] = asset_id

            logger.info(f"{self.name}: Successfully created asset {asset_id}")

        except Exception as e:
            logger.error(f"{self.name} encountered an error: {e!s}")
