"""
Remote VMS Connection Module
=============================

Provides tools for connecting to and executing commands on a remote VMS server
via SSH using paramiko. Includes IPython magic commands for interactive use.

Usage:
    from remote_connect import setup_venv
    
    # In IPython/Jupyter:
    %%vms
    ls -la
    
    %%vms python
    print("Hello from remote!")
"""

import paramiko
from IPython.core.magic import register_cell_magic


def load_connection_config(config_file='connection_config.txt'):
    """
    Load SSH connection configuration from a text file.
    
    Args:
        config_file (str): Path to configuration file. Default: 'connection_config.txt'
        
    Returns:
        dict: Configuration dictionary with keys: hostname, port, username, password
        
    Expected file format:
        hostname=example.com
        port=22
        username=myuser
        password=mypass
    """
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                # Convert port to integer
                if key == 'port':
                    value = int(value)
                config[key] = value
    return config


def initialize_connection():
    """
    Initialize and test the SSH connection using configuration from file.
    
    Returns:
        tuple: (hostname, port, username, password) or (None, None, None, None) on failure
    """
    try:
        secrets = load_connection_config('connection_config.txt')
        hostname = secrets['hostname']
        port = secrets['port']
        username = secrets['username']
        password = secrets['password']
        
        # Test connection
        print(f"Connecting to {hostname}:{port} as {username}...")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=hostname, port=port, username=username, password=password, timeout=10)
        print("✓ Connection successful!\n")
        client.close()
        
        return hostname, port, username, password
    except FileNotFoundError:
        print("⚠ Warning: connection_config.txt not found. Please create it first.")
        return None, None, None, None
    except Exception as e:
        print(f"✗ Connection failed: {e}\n")
        return None, None, None, None


# Initialize connection credentials
hostname, port, username, password = initialize_connection()


@register_cell_magic
def vms(line, cell):
    """
    Unified VMS cell magic command for executing shell and Python commands remotely.
    
    This IPython magic command allows you to execute shell commands or Python code
    on a remote VMS server. It supports virtual environments and persistent scripts.
    
    Usage:
        %%vms
        # Execute shell commands
        ls -la
        
        %%vms python
        # Execute Python (uses venv if available)
        print("Hello!")
        
        %%vms python:ml_env
        # Execute Python with specific venv
        import numpy as np
        
        %%vms python persistent script.py
        # Append to file and execute
        
        %%vms python:ml_env persistent script.py
        # Append to file and execute in venv
    
    Args:
        line (str): Command line arguments (mode specification)
        cell (str): Cell content to execute
    """
    if not hostname:
        print("✗ Error: No connection configured. Please run initialize_connection() first.")
        return
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostname, port=port, username=username, password=password, timeout=10)
    
    line = line.strip()
    
    # Mode 1: Shell commands (default)
    if not line or not line.startswith('python'):
        stdin, stdout, stderr = client.exec_command(cell)
        output = stdout.read().decode()
        errors = stderr.read().decode()
        
        client.close()
        
        if errors:
            print("STDERR:", errors)
        if output:
            print(output)
        return
    
    # Parse Python modes
    venv_name = None
    persistent = False
    filename = 'persistent.py'
    
    # Check if specific venv is specified (python:venv_name)
    if ':' in line:
        prefix, rest = line.split(':', 1)
        rest_parts = rest.strip().split()
        venv_name = rest_parts[0]
        
        # Check for persistent mode
        if len(rest_parts) > 1 and rest_parts[1] == 'persistent':
            persistent = True
            if len(rest_parts) > 2:
                filename = rest_parts[2]
    else:
        # No specific venv, check for persistent mode
        parts = line.split()
        if len(parts) > 1 and parts[1] == 'persistent':
            persistent = True
            if len(parts) > 2:
                filename = parts[2]
    
    # Determine which Python to use
    if venv_name:
        # Use specified venv
        python_cmd = f'{venv_name}/bin/python3'
    else:
        # Auto-detect default venv
        default_venv = 'ml_env'
        stdin, stdout, stderr = client.exec_command(f'test -f {default_venv}/bin/python3 && echo "yes" || echo "no"')
        venv_exists = stdout.read().decode().strip() == "yes"
        python_cmd = f'{default_venv}/bin/python3' if venv_exists else 'python3'
    
    # Mode 2 & 3: Python execution (non-persistent)
    if not persistent:
        command = f'{python_cmd} << EOF\n{cell}\nEOF'
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        errors = stderr.read().decode()
        
        client.close()
        
        if errors:
            print("STDERR:", errors)
        if output:
            print(output)
        return
    
    # Mode 4 & 5: Persistent Python execution
    command = f'cat >> {filename} << EOF\n{cell}\nEOF\n{python_cmd} {filename}'
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    errors = stderr.read().decode()
    
    client.close()
    
    if errors:
        print("STDERR:", errors)
    if output:
        print(output)


def setup_venv(venv_name='ml_env', packages=None, force_reinstall=False):
    """
    Set up a Python virtual environment on the remote machine with ML packages.
    
    Creates a virtual environment on the remote server and installs specified packages.
    Useful for setting up isolated Python environments with machine learning libraries.
    
    Args:
        venv_name (str): Name of the virtual environment. Default: 'ml_env'
        packages (list): List of package names to install. 
                        Default: ['numpy', 'pandas', 'matplotlib', 'scikit-learn', 'fastai', 'tinygrad']
        force_reinstall (bool): If True, removes existing venv and creates fresh one. Default: False
    
    Example:
        setup_venv('my_env', ['numpy', 'scipy', 'matplotlib'])
        setup_venv('ml_env', force_reinstall=True)
    """
    if not hostname:
        print("✗ Error: No connection configured. Please run initialize_connection() first.")
        return
    
    if packages is None:
        packages = ['numpy', 'pandas', 'matplotlib']
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostname, port=port, username=username, password=password, timeout=10)
    
    print(f"Setting up virtual environment: {venv_name}")
    print("=" * 60)
    
    # Step 1: Remove existing venv if force_reinstall
    if force_reinstall:
        print("\n1. Removing existing virtual environment...")
        stdin, stdout, stderr = client.exec_command(f'rm -rf {venv_name}')
        stdout.channel.recv_exit_status()
        print("   ✓ Cleaned up old environment")
    
    # Step 2: Check if venv exists
    print("\n2. Checking for existing virtual environment...")
    stdin, stdout, stderr = client.exec_command(f'test -d {venv_name} && echo "exists" || echo "not found"')
    exists = stdout.read().decode().strip()
    
    if exists == "not found":
        print(f"   Creating new virtual environment: {venv_name}")
        stdin, stdout, stderr = client.exec_command(f'python3 -m venv {venv_name}')
        stdout.channel.recv_exit_status()
        print("   ✓ Virtual environment created")
    else:
        print(f"   ✓ Virtual environment already exists: {venv_name}")
    
    # Step 3: Upgrade pip
    print("\n3. Upgrading pip...")
    stdin, stdout, stderr = client.exec_command(
        f'{venv_name}/bin/pip install --upgrade pip'
    )
    stdout.channel.recv_exit_status()
    print("   ✓ Pip upgraded")
    
    # Step 4: Install packages
    print("\n4. Installing packages...")
    packages_str = ' '.join(packages)
    print(f"   Installing: {packages_str}")
    
    stdin, stdout, stderr = client.exec_command(
        f'{venv_name}/bin/pip install {packages_str}'
    )
    
    # Stream output
    while True:
        line = stdout.readline()
        if not line:
            break
        print(f"   {line.rstrip()}")
    
    stdout.channel.recv_exit_status()
    
    # Step 5: Verify installation
    print("\n5. Verifying installation...")
    package_pattern = '|'.join(packages)
    stdin, stdout, stderr = client.exec_command(
        f'{venv_name}/bin/pip list | grep -E "{package_pattern}"'
    )
    installed = stdout.read().decode()
    print(f"\n   Installed packages:\n{installed}")
    
    client.close()
    
    print("\n" + "=" * 60)
    print("✓ Virtual environment setup complete!")
    print(f"\nUsage:")
    print(f"   %%vms python:{venv_name}")
    print(f"   %%vms python:{venv_name} persistent script.py")
    print("=" * 60)


# Print usage information when module is loaded
if hostname:
    print("✓ VMS Magic command ready:")
    print("  - %%vms                                      : Execute shell commands")
    print("  - %%vms python                               : Execute Python (auto venv)")
    print("  - %%vms python:venv_name                     : Execute Python (specific venv)")
    print("  - %%vms python persistent file.py            : Persistent Python (auto venv)")
    print("  - %%vms python:venv_name persistent file.py  : Persistent Python (specific venv)")
    print("  - setup_venv(name, packages, force)          : Setup virtual environment")
