# Azure test deployment

Repo Brain runs in its own Docker Compose project on the existing Azure Linux VM. Its source is installed at `/opt/repo-brain`, and its app port is bound to `127.0.0.1:8000` on the server. The existing Clipflow containers keep their own ports, networks, and volumes.

## Connect from your computer

Keep an SSH tunnel running:

```sh
ssh -N -L 8000:127.0.0.1:8000 -i /path/to/your/ssh-key clipflow@your-server-ip
```

Open <http://127.0.0.1:8000/bots>. The page is served by Azure through SSH. Enter the owner token in **Settings**, then browse GitHub and choose a repository. Keep **Local · free** selected to chat without an OpenAI key. OpenAI remains an optional model choice.

### Windows reconnection

The owner's computer has a task named `RepoBrain-Azure-Tunnel`. It checks the connection every two minutes and at login. If disconnected, it refreshes the dedicated Azure SSH rule for the computer's current public IPv4 address and starts a hidden SSH tunnel. It preserves strict host-key verification and permits SSH from one `/32` address. A healthy connection is left running.

The task runs `scripts/keep-azure-tunnel.ps1` with a local JSON connection file. That file contains `localPort`, `serverAddress`, `userName`, `identityFile`, `knownHostsFile`, `azureCliPython`, `resourceGroup`, `nsgName`, and `ruleName`. Paths point to the existing SSH key, known-hosts file, and authenticated Azure CLI Python installation. Credentials remain in those tools' existing private files.

To reconnect immediately or inspect a failure:

```powershell
Start-ScheduledTask -TaskName RepoBrain-Azure-Tunnel
Get-ScheduledTaskInfo -TaskName RepoBrain-Azure-Tunnel
```

An expired Azure login needs renewal before the task can update the SSH rule. The browser is unavailable while the computer is offline; the Azure application continues running.

The deployment saves its owner token and GitHub credential in the root-readable `/opt/repo-brain/deploy/server.env`. Keep that file out of source control and shared logs. The SSH network rule permits the deployment computer's IP; if that IP changes, update the rule to the new address with a `/32` prefix.

## Maintenance

This VM's login user needs `sudo` for Docker:

```sh
cd /opt/repo-brain
sudo bash scripts/server.sh status
sudo bash scripts/server.sh logs
sudo bash scripts/server.sh check
```

Containers restart automatically after a server restart. Persistent data is stored in the `repo-brain_app-data` and `repo-brain_app-storage` volumes. Back up these volumes and the private environment file before changing the installation.

The initial source transfer uses an archive of a committed Git revision. For an upgrade, replace source files from a newer reviewed revision while preserving `deploy/server.env` and the volumes, then run `sudo bash scripts/server.sh up`. The archive installation has no Git checkout, so `server.sh update` is intended for installations made with `git clone`.

The production model provider is used here. Server checks verify authentication, storage, connectivity, and an actual Najm PNG without making a paid model request.
