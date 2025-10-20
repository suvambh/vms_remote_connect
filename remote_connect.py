import paramiko
import threading
import time
from IPython.core.magic import register_cell_magic
from IPython import get_ipython


class VMSConnection:
    def __init__(self, hostname, username, password=None, key_filename=None, 
                 port=22, tmux_session='vms_session', venv_name='venv'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.tmux_session = tmux_session
        self.venv_name = venv_name
        
        self.ssh_client = None
        self.sftp_client = None
        self.keepalive_thread = None
        self.connected = False
        
    def connect(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': self.hostname,
                'port': self.port,
                'username': self.username,
            }
            
            if self.password:
                connect_kwargs['password'] = self.password
            if self.key_filename:
                connect_kwargs['key_filename'] = self.key_filename
                
            self.ssh_client.connect(**connect_kwargs)
            self.sftp_client = self.ssh_client.open_sftp()
            self._setup_tmux_session()
            
            self.connected = True
            self.keepalive_thread = threading.Thread(target=self._keepalive, daemon=True)
            self.keepalive_thread.start()
            
            print(f"✓ Connected to {self.hostname} (tmux session: {self.tmux_session})")
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            raise
            
    def _setup_tmux_session(self):
        check_cmd = f"tmux has-session -t {self.tmux_session} 2>/dev/null"
        stdin, stdout, stderr = self.ssh_client.exec_command(check_cmd)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            create_cmd = f"tmux new-session -d -s {self.tmux_session}"
            self.ssh_client.exec_command(create_cmd)
            print(f"Creating default tmux session: {self.tmux_session}")
            
        
    def execute(self, command):
        if not self.connected: raise RuntimeError("Not connected. Call connect() first.")
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        exit_code = stdout.channel.recv_exit_status()
        return output, error, exit_code


    def execute_streaming(self, command):
        if not self.connected: raise RuntimeError("Not connected. Call connect() first.")
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        channel = stdout.channel
        while not channel.exit_status_ready():
            if channel.recv_ready():
                data = channel.recv(1024).decode('utf-8')
                print(data, end='', flush=True)
            time.sleep(0.1)
        while channel.recv_ready():
            data = channel.recv(1024).decode('utf-8')
            print(data, end='', flush=True)
        exit_code = channel.recv_exit_status()
        return exit_code

    def run_python_file(self, filename, venv_name=None):
        if venv_name is None: venv_name = self.venv_name
        run_cmd = f"source {venv_name}/bin/activate && python {filename}"
        print(f"Running {filename} in {venv_name}")
        self.execute_streaming(run_cmd)


    def execute_and_print(self, commands):
        for cmd in commands.strip().split('\n'):
            cmd = cmd.strip()
            if not cmd or cmd.startswith('#'):
                continue
                
            print(f"$ {cmd}")
            output, error, exit_code = self.execute(cmd)
            
            if output:
                print(output)
            if error:
                print(f"Error: {error}")
                
    def create_venv(self, venv_name=None):
        if venv_name is None:
            venv_name = self.venv_name
            
        print(f"Creating virtual environment: {venv_name}")
        self.execute_and_print(f"python3 -m venv {venv_name}")
        print(f"✓ Virtual environment '{venv_name}' created")
        
    def install_packages(self, packages, venv_name=None):
        if venv_name is None:
            venv_name = self.venv_name
            
        if isinstance(packages, str):
            packages = [packages]
            
        pip_cmd = f"source {venv_name}/bin/activate && pip install {' '.join(packages)}"
        print(f"Installing packages: {', '.join(packages)}")
        self.execute_and_print(pip_cmd)
        print(f"✓ Packages installed")
        
        
    def write_and_run(self, filename, code, venv_name=None):
        self.write_file(filename, code)
        self.run_python_file(filename, venv_name)
                
    def write_file(self, remote_path, content):
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
            
        with self.sftp_client.open(remote_path, 'w') as f:
            if isinstance(content, str):
                content = content.encode('utf-8')
            f.write(content)
            
        print(f"✓ Wrote to {remote_path}")
        
    def read_file(self, remote_path):
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
            
        with self.sftp_client.open(remote_path, 'r') as f:
            content = f.read().decode('utf-8')
            
        return content
        
    def upload_file(self, local_path, remote_path):
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
            
        self.sftp_client.put(local_path, remote_path)
        print(f"✓ Uploaded {local_path} → {remote_path}")
        
    def download_file(self, remote_path, local_path):
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
            
        self.sftp_client.get(remote_path, local_path)
        print(f"✓ Downloaded {remote_path} → {local_path}")
        
    def _keepalive(self):
        while self.connected:
            try:
                transport = self.ssh_client.get_transport()
                if transport and transport.is_active():
                    transport.send_ignore()
                else:
                    print("⚠ Connection lost")
                    self.connected = False
                    break
            except Exception as e:
                print(f"⚠ Keepalive error: {e}")
                self.connected = False
                break
                
            time.sleep(60)
            
    def disconnect(self):
        self.connected = False
        
        if self.sftp_client:
            self.sftp_client.close()
            
        if self.ssh_client:
            self.ssh_client.close()
            
        print(f"✓ Disconnected from {self.hostname}")


vms_conn = None


def save_config(input_str, config_file='connection_config.txt'):
    parts = input_str.strip().split()
    hostname, port = parts[0].split(':') if ':' in parts[0] else (parts[0], '22')
    username = parts[1]
    password = parts[2] if len(parts) > 2 else ''
    
    with open(config_file, 'w') as f:
        f.write(f"hostname={hostname}\n")
        f.write(f"port={port}\n")
        f.write(f"username={username}\n")
        if password: f.write(f"password={password}\n")
        f.write(f"tmux_session=vms_session\n")
        f.write(f"venv_name=venv\n")
    
    print(f"✓ Config saved to {config_file}")


def load_config(config_file='connection_config.txt'):
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config


def setup_vms_connection(config_file='connection_config.txt'):
    global vms_conn
    
    config = load_config(config_file)
    
    vms_conn = VMSConnection(
        hostname=config.get('hostname'),
        username=config.get('username'),
        password=config.get('password'),
        key_filename=config.get('key_filename'),
        port=int(config.get('port', 22)),
        tmux_session=config.get('tmux_session', 'vms_session'),
        venv_name=config.get('venv_name', 'venv')
    )
    
    vms_conn.connect()
    
    @register_cell_magic
    def vms(line, cell):
        if vms_conn is None or not vms_conn.connected:
            print("✗ Not connected. Run setup_vms_connection() first.")
            return
        
        line = line.strip()
        
        if line:
            parts = line.split()
            if len(parts) == 2:
                venv_name, filename = parts[0], parts[1]
                vms_conn.write_and_run(filename, cell, venv_name)
            else:
                vms_conn.execute_and_print(cell)
        else:
            vms_conn.execute_and_print(cell)
