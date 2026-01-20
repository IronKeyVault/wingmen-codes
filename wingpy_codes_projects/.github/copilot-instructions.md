# Copilot Instructions for `wingpy_codes_projects`

This document provides guidance for AI coding agents working on the `wingpy_codes_projects` repository. It outlines the architecture, workflows, and conventions specific to this project to ensure productive contributions.

## Project Overview

The `wingpy_codes_projects` repository is designed to interact with Cisco Firepower Management Center (FMC) APIs. It includes utilities for managing dynamic objects in the FMC system. The project is written in Python and relies on the `wingpy` library for interfacing with the FMC.

### Key Components

1. **`FMC_dynObj.py`**
   - Fetches dynamic objects from the FMC.
   - Demonstrates the use of the `wingpy` library for API interactions.
   - Example usage:
     ```python
     fmc = CiscoFMC(base_url=FMC_URL, username=USERNAME, password=PASSWORD, verify=False)
     dynamic_objects = fmc.get_all("/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects")
     ```

2. **`PUT_in_dynobjects.py`**
   - Manages dynamic objects by adding IP addresses to them.
   - Implements custom HTTP requests using `requests` for authentication and object manipulation.
   - Example workflow:
     - Authenticate and retrieve a token.
     - Fetch the domain UUID.
     - Add an IP address to a dynamic object.

3. **`pyproject.toml`**
   - Defines the project metadata and dependencies.
   - Dependency: `wingpy`.

## Developer Workflows

### Authentication
- Use the `get_auth_token` function in `PUT_in_dynobjects.py` to generate an authentication token.
- Example:
  ```python
  token = get_auth_token()
  ```

### Fetching Domain UUID
- Use the `get_domain_uuid` function to retrieve the domain UUID required for API calls.
- Example:
  ```python
  domain_uuid = get_domain_uuid(token)
  ```

### Adding IP to Dynamic Object
- Use the `add_ip_to_dynamic_object` function to add an IP address to a dynamic object.
- Ensure the IP address is validated using `validate_ip`.
- Example:
  ```python
  add_ip_to_dynamic_object(object_id, new_ip, token, domain_uuid)
  ```

## Project-Specific Conventions

1. **Logging**
   - Use the `logging` module for consistent logging.
   - Example:
     ```python
     logging.info("✅ Token hentet.")
     ```

2. **Error Handling**
   - Raise exceptions for HTTP errors and handle them in the `main` function.
   - Example:
     ```python
     if response.status_code != 200:
         raise Exception(f"Fejl ved GET: {response.status_code} - {response.text}")
     ```

3. **Validation**
   - Validate IP addresses before adding them to dynamic objects.
   - Example:
     ```python
     if not validate_ip(new_ip):
         print("❌ Ugyldig IP-adresse. Prøv igen.")
         exit(1)
     ```

## External Dependencies

- **`wingpy`**: A Python library for interacting with Cisco FMC APIs.
- **`requests`**: Used for HTTP requests in `PUT_in_dynobjects.py`.
- **`urllib3`**: Used to suppress SSL warnings.

## Integration Points

- **Cisco FMC API**: The project communicates with the FMC API for managing dynamic objects.
- **Dynamic Objects**: The primary focus is on fetching and updating dynamic objects in the FMC.

## Examples

### Fetching Dynamic Objects
```python
fmc = CiscoFMC(base_url=FMC_URL, username=USERNAME, password=PASSWORD, verify=False)
dynamic_objects = fmc.get_all("/api/fmc_config/v1/domain/{domainUUID}/object/dynamicobjects")
```

### Adding an IP Address
```python
object_id = "example-id"
new_ip = "192.168.1.1"
if validate_ip(new_ip):
    token = get_auth_token()
    domain_uuid = get_domain_uuid(token)
    add_ip_to_dynamic_object(object_id, new_ip, token, domain_uuid)
```

---

For any questions or clarifications, please refer to the code comments or contact the repository maintainers.