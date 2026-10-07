# Azure test deployment

Repo Brain runs in its own Docker Compose project on the existing Azure Linux VM. Its source is installed at `/opt/repo-brain`, and its app port is bound to `127.0.0.1:8000` on the server. The existing Clipflow containers keep their own ports, networks, and volumes.

## Connect from your computer

Keep an SSH tunnel running:

```sh
ssh -N -L 8000:127.0.0.1:8000 -i /path/to/your/ssh-key clipflow@your-server-ip
```

Open <http://127.0.0.1:8000/bots>. The page is served by Azure through SSH. Enter the owner token in **Settings**, then browse GitHub and choose a repository. Enter your OpenAI API key in its bot page when you want to send a message.

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
