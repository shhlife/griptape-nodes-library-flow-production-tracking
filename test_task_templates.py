#!/usr/bin/env python3

import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from .env
api_key = os.getenv("SHOTGRID_API_KEY")
if not api_key:
    print("Error: SHOTGRID_API_KEY not found in .env file")
    exit(1)

print(f"Using API key: {api_key[:10]}...")

# Get access token
auth_url = "https://griptape-ai.shotgrid.autodesk.com/api/v1/auth/access_token"
auth_data = {
    "grant_type": "client_credentials",
    "client_id": "Griptape Nodes",
    "client_secret": api_key,
}
auth_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

print("Getting access token...")
auth_response = httpx.post(auth_url, data=auth_data, headers=auth_headers)
auth_response.raise_for_status()
token_data = auth_response.json()
access_token = token_data.get("access_token")
print(f"Got access token: {access_token[:50]}...")

# Get task templates
headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
url = "https://griptape-ai.shotgrid.autodesk.com/api/v1/entity/task_templates?fields=id,name,code,description,entity_type&entity_type=Asset"

print("\nGetting task templates...")
response = httpx.get(url, headers=headers)
response.raise_for_status()
data = response.json()
print(f"Found {len(data.get('data', []))} task templates:")

for template in data.get('data', []):
    template_id = template.get('id')
    name = template.get('attributes', {}).get('name', '')
    code = template.get('attributes', {}).get('code', '')
    description = template.get('attributes', {}).get('description', '')
    print(f"  ID: {template_id}, Name: '{name}', Code: '{code}', Description: '{description}'")

# Create an asset with a task template
if data.get('data'):
    template = data['data'][0]  # Use the first template
    template_id = template.get('id')
    
    print(f"\nCreating asset with task template {template_id}...")
    
    # First create the asset
    asset_data = {
        "code": "test_asset_curl",
        "sg_asset_type": "Character",
        "project": {"type": "Project", "id": 233},
        "description": "Test asset created via curl with task template"
    }
    
    create_url = "https://griptape-ai.shotgrid.autodesk.com/api/v1/entity/assets"
    create_headers = {**headers, "Content-Type": "application/json"}
    
    create_response = httpx.post(create_url, headers=create_headers, json=asset_data)
    create_response.raise_for_status()
    created_asset = create_response.json()
    asset_id = created_asset.get('data', {}).get('id')
    print(f"Created asset with ID: {asset_id}")
    
    # Now create a task based on the template
    print(f"Creating task based on template {template_id}...")
    
    # Get the template details
    template_url = f"https://griptape-ai.shotgrid.autodesk.com/api/v1/entity/task_templates/{template_id}"
    template_response = httpx.get(template_url, headers=headers)
    template_response.raise_for_status()
    template_details = template_response.json()
    
    step_data = template_details.get('data', {}).get('attributes', {}).get('step')
    print(f"Template step data: {step_data}")
    
    # Create task
    task_data = {
        "content": template_details.get('data', {}).get('attributes', {}).get('name', 'Task from Template'),
        "project": {"type": "Project", "id": 233},
        "entity": {"type": "Asset", "id": asset_id},
    }
    
    if step_data:
        task_data["step"] = step_data
    
    task_url = "https://griptape-ai.shotgrid.autodesk.com/api/v1/entity/tasks"
    task_response = httpx.post(task_url, headers=create_headers, json=task_data)
    
    if task_response.status_code == 201:
        task_result = task_response.json()
        task_id = task_result.get('data', {}).get('id')
        print(f"Successfully created task with ID: {task_id}")
    else:
        print(f"Failed to create task: {task_response.status_code}")
        print(f"Response: {task_response.text}")
else:
    print("No task templates found")
