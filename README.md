## VMS Remote Execution System

A Python-based system for executing commands, Python scripts, and managing virtual environments on a remote VMS (Virtual Machine Server) via SSH using Paramiko.

### Overview

This system provides a Jupyter magic command (`%%vms`) that allows you to execute shell commands and Python code on a remote server directly from your notebook, with support for virtual environments and persistent script files.

### Components

**1. Connection Configuration**

The system loads SSH connection details from a `connection_config.txt` file with the following format:

```
hostname=your.server.com
port=22
username=your_username
password=your_password
```

**2. Main Functions**

**`load_connection_config(config_file='connection_config.txt')`**

Loads SSH connection parameters from a configuration file.

- **Parameters**: `config_file` - Path to configuration file (default: 'connection_config.txt')
- **Returns**: Dictionary with connection parameters (hostname, port, username, password)
- **Note**: Automatically converts port to integer

**`setup_venv(venv_name='ml_env', packages=None, force_reinstall=False)`**

Creates and configures a Python virtual environment on the remote server with specified packages.

- **Parameters**:
  - `venv_name` - Name of virtual environment (default: 'ml_env')
  - `packages` - List of packages to install (default: ['numpy', 'pandas', 'matplotlib', 'scikit-learn', 'fastai', 'tinygrad'])
  - `force_reinstall` - If True, removes existing venv before creating new one (default: False)

- **Process**:
  1. Optionally removes existing environment
  2. Creates new virtual environment if needed
  3. Upgrades pip
  4. Installs specified packages
  5. Verifies installation

### Magic Command: `%%vms`

A unified cell magic for executing commands on the remote server.

**Mode 1: Shell Commands**
```python
%%vms
ls -la
pwd
echo "Hello from VMS"
```

**Mode 2: Python Execution (Auto-detect venv)**
```python
%%vms python
import numpy as np
print(np.array([1, 2, 3]))
```
Automatically uses `ml_env` virtual environment if available, otherwise uses system Python.

**Mode 3: Python with Specific Virtual Environment**
```python
%%vms python:my_custom_env
import pandas as pd
print(pd.__version__)
```

**Mode 4: Persistent Python Script (Auto venv)**
```python
%%vms python persistent script.py
def hello():
    print("This gets appended to script.py")
hello()
```
Appends code to file and executes it. Each cell adds to the same file.

**Mode 5: Persistent Python with Specific Virtual Environment**
```python
%%vms python:ml_env persistent my_analysis.py
import matplotlib.pyplot as plt
plt.plot([1, 2, 3])
plt.savefig('output.png')
```

### Usage Examples

**Setting up a virtual environment:**
```python
# Basic setup with default packages
setup_venv()

# Custom environment with specific packages
setup_venv('data_science', ['numpy', 'scipy', 'jupyter'])

# Force reinstall
setup_venv('ml_env', force_reinstall=True)
```

**Running shell commands:**
```python
%%vms
df -h
free -m
nvidia-smi
```

**Quick Python calculations:**
```python
%%vms python
result = sum(range(1000000))
print(f"Sum: {result}")
```

**Building a persistent script incrementally:**
```python
%%vms python persistent analysis.py
import pandas as pd
data = pd.read_csv('data.csv')
```

```python
%%vms python persistent analysis.py
# This appends to the same file
result = data.describe()
print(result)
```

### Features

- **Automatic venv detection**: Uses `ml_env` by default if available
- **Multiple execution modes**: Shell, Python (ephemeral), and persistent scripts
- **Error handling**: Displays both stdout and stderr
- **Connection testing**: Verifies SSH connection on startup
- **Streaming output**: Real-time feedback during package installation
- **Flexible configuration**: File-based connection settings

### Security Notes

- Connection credentials are stored in plain text in `connection_config.txt`
- Ensure this file has appropriate permissions (`chmod 600`)
- Consider using SSH keys instead of passwords for production use
- The system uses `AutoAddPolicy` for host keys - verify host fingerprints manually for security-critical applications

### Error Handling

The system provides clear feedback for common issues:
- Missing configuration file
- Connection failures
- Command execution errors (displayed as STDERR output)

### Requirements

- `paramiko` - SSH client library
- `IPython` - For magic command registration
- Remote server with SSH access
- Python 3 on remote server (for Python execution modes)
