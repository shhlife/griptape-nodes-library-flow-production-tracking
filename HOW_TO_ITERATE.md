# How to Iterate: Testing & Learning Process for ShotGrid Features

This document outlines the systematic approach for testing and implementing new ShotGrid features in our Griptape nodes.

## 🔬 **Testing & Learning Process for ShotGrid Task Templates**

### **Step 1: Identify the Problem**

- User reported that task templates weren't being applied when creating assets
- Needed to understand how ShotGrid task templates actually work

### **Step 2: Start with Basic API Exploration**

```bash
# Get access token using password auth (more reliable than API key)
curl -X POST https://griptape-ai.shotgrid.autodesk.com/api/v1/auth/access_token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Accept: application/json' \
  -d "username=jason@griptape.ai&password=Mousy-Snap-Deplored4&grant_type=password"
```

### **Step 3: Explore Available Data**

```bash
# Get task templates to understand the data structure
curl -H "Authorization: Bearer $TOKEN" \
  "https://griptape-ai.shotgrid.autodesk.com/api/v1/entity/task_templates?fields=id,name,code,description,entity_type&entity_type=Asset"
```

**Key Discovery**: Template information is in the `code` field, not the `name` field!

### **Step 4: Create Simple Test Script**

```python
# test_curl.py - Basic task creation test
# This revealed that manual task creation works but isn't the right approach
```

### **Step 5: Research the "Right Way"**

- Looked at ShotGrid documentation and examples
- Discovered that task templates should be **attached** to assets, not manually applied
- Found the correct field: `"task_template": {"type": "TaskTemplate", "id": template_id}`

### **Step 6: Create Comprehensive Test**

```python
# test_asset_with_template.py - Proper template attachment test
# This revealed the magic: ShotGrid automatically creates tasks when template is attached!
```

### **Step 7: Apply Learning to Node**

- Updated the create asset node to use the correct approach
- Removed manual task creation logic
- Added template attachment during asset creation

## 🎯 **Key Learning Principles:**

### **1. Start Simple**

- Begin with basic curl commands to understand the API
- Don't assume you know how something works

### **2. Explore the Data Structure**

- Always check what fields are actually available
- Don't assume field names (e.g., `name` vs `code`)

### **3. Test the "Right Way"**

- Research how the feature is supposed to work
- Don't just make it work - make it work correctly

### **4. Create Isolated Tests**

- Build simple scripts to test specific functionality
- This allows rapid iteration without complex node logic

### **5. Document the Process**

- Keep track of what you learn
- This helps with future debugging and feature development

## 🚀 **Benefits of This Approach:**

1. **Faster Debugging** - Can test API calls directly without node complexity
1. **Better Understanding** - Learn how the system actually works
1. **More Reliable Solutions** - Find the "right way" instead of workarounds
1. **Reusable Knowledge** - Can apply this process to other features
1. **Confidence** - Know exactly what should happen before implementing

## 📝 **Template for Future Testing:**

```bash
# 1. Get authentication working
curl -X POST https://site.shotgrid.autodesk.com/api/v1/auth/access_token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=user&password=pass&grant_type=password"

# 2. Explore the data
curl -H "Authorization: Bearer $TOKEN" \
  "https://site.shotgrid.autodesk.com/api/v1/entity/ENTITY_TYPE?fields=id,name,code"

# 3. Create test script
# test_feature.py - Isolated test of the feature

# 4. Apply learning to node
# Update node with correct approach
```

## 🔧 **Common Testing Patterns:**

### **Authentication Testing**

```python
import httpx

# Get access token
auth_url = "https://site.shotgrid.autodesk.com/api/v1/auth/access_token"
auth_data = {
    "username": "user@example.com",
    "password": "password",
    "grant_type": "password"
}
auth_headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}

auth_response = httpx.post(auth_url, data=auth_data, headers=auth_headers)
auth_response.raise_for_status()
token_data = auth_response.json()
access_token = token_data.get("access_token")
```

### **API Exploration**

```python
# Explore entity data
headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
url = "https://site.shotgrid.autodesk.com/api/v1/entity/ENTITY_TYPE?fields=id,name,code,description"

response = httpx.get(url, headers=headers)
response.raise_for_status()
data = response.json()

for item in data.get('data', []):
    print(f"ID: {item.get('id')}, Name: '{item.get('attributes', {}).get('name', '')}', Code: '{item.get('attributes', {}).get('code', '')}'")
```

### **Feature Testing**

```python
# Test creating something with the feature
create_data = {
    "field1": "value1",
    "field2": "value2",
    "feature_field": {"type": "FeatureType", "id": feature_id}  # The feature we're testing
}

create_url = "https://site.shotgrid.autodesk.com/api/v1/entity/ENTITY_TYPE"
create_headers = {**headers, "Content-Type": "application/json"}

create_response = httpx.post(create_url, headers=create_headers, json=create_data)
create_response.raise_for_status()
result = create_response.json()
print(f"Created with ID: {result.get('data', {}).get('id')}")
```

## 🎯 **Success Criteria:**

- [ ] API calls work with curl/httpx
- [ ] Data structure is understood
- [ ] Feature works in isolation
- [ ] Node implementation follows the "right way"
- [ ] Feature works reliably in the node
- [ ] Process is documented for future reference

## 📚 **Resources:**

- [ShotGrid API Documentation](https://developer.shotgridsoftware.com/rest-api/)
- [ShotGrid Python API](https://github.com/shotgunsoftware/python-api)
- [Griptape Nodes Documentation](https://docs.griptape.ai/)

______________________________________________________________________

*This process ensures we build features that work correctly and reliably!* 🎯


