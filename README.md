**Persistent SSH Connection with Keepalive**

The connection uses paramiko's SSH client with a background keepalive mechanism to prevent timeouts. A daemon thread runs every 60 seconds sending `transport.send_ignore()` packets to maintain the TCP connection. The thread monitors `transport.is_active()` and sets `self.connected = False` if the connection drops, preventing operations on a dead socket.

**Tmux Session Management**

On connection, the system checks for an existing tmux session using `tmux has-session -t {session_name}` and inspects the exit code. If the session doesn't exist (exit_code != 0), it creates a detached session with `tmux new-session -d -s {session_name}`. This provides a persistent shell environment that survives SSH disconnections.

To execute commands in the tmux session, you'd use: `tmux send-keys -t {session_name} "command" C-m` which sends the command and a carriage return. The current implementation uses direct `exec_command()` for simplicity, but could be extended to use tmux for truly persistent execution contexts.

**SFTP File Operations**

The SFTP subsystem is opened via `ssh_client.open_sftp()` which returns a persistent SFTP client. File operations use `sftp_client.open(path, mode)` which returns a file-like object supporting read/write. The `write_file` method handles both string and bytes, encoding strings to UTF-8. The `put()` and `get()` methods transfer entire files efficiently using the SFTP protocol's optimized transfer mechanisms.

**Virtual Environment Activation**

Commands run in venvs use shell command chaining: `source {venv}/bin/activate && command`. The `source` activates the venv in the current shell context, modifying `$PATH` and `$VIRTUAL_ENV`. The `&&` ensures the second command only runs if activation succeeds. Each `exec_command()` spawns a new shell, so activation must happen in the same command string.

**Cell Magic Implementation**

The `@register_cell_magic` decorator registers `%%vms` with IPython. When invoked, the `line` parameter contains arguments after `%%vms`, and `cell` contains the code block. The magic parses the line to determine if it's `venv_name filename` (two parts) for Python execution, or treats the cell as shell commands otherwise. The `get_ipython()` function provides access to the IPython instance for runtime registration.

**Exit Code Handling**

The `execute()` method uses `stdout.channel.recv_exit_status()` which blocks until the remote command completes and returns its exit code. This is more reliable than checking `stderr` since commands can write to stderr without failing. Exit codes follow Unix conventions: 0 for success, non-zero for failure.
