<a href="https://livekit.io/">
  <img src="./.github/assets/livekit-mark.png" alt="LiveKit logo" width="100" height="100">
</a>

# Python Voice Agent

<p>
  <a href="https://cloud.livekit.io/projects/p_/sandbox"><strong>Deploy a sandbox app</strong></a>
  •
  <a href="https://docs.livekit.io/agents/overview/">LiveKit Agents Docs</a>
  •
  <a href="https://livekit.io/cloud">LiveKit Cloud</a>
  •
  <a href="https://blog.livekit.io/">Blog</a>
</p>

A basic example of a voice agent using LiveKit and Python.

## Dev Setup

Clone the repository and install dependencies to a virtual environment:

```console
# Linux/macOS
cd lk-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 agent.py download-files
```

Set up the environment by copying `.env.example` to `.env.local` and filling in the required values:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `OPENAI_API_KEY`
- `CARTESIA_API_KEY`
- `DEEPGRAM_API_KEY`

You can also do this automatically using the LiveKit CLI:

```console
lk app env
```

Run the agent:

```console
python3 agent.py dev
```

This agent requires a frontend application to communicate with. You can use one of our example frontends in [livekit-examples](https://github.com/livekit-examples/), create your own following one of our [client quickstarts](https://docs.livekit.io/realtime/quickstarts/), or test instantly against one of our hosted [Sandbox](https://cloud.livekit.io/projects/p_/sandbox) frontends.

# Use chatbot with RAG
# download document for chatbot
python3 downloader.py --name magingam --urls https://magingam.vn/

# Change document name in chatbot_agent.py
CHATBOT_NAME = "magingam"

Run the agent:

```console
python3 chatbot_agent.py dev
```

# run agent in background mode
# install supervisord
# create supervisord config
```console
sudo vi /etc/supervisor/conf.d/lk-agent.conf
```
[program:lk-agent]
directory=/var/www/livekit/lk-agent
command=/var/www/livekit/lk-agent/venv/bin/python chatbot_agent_toyota.py dev
autostart=true
autorestart=false
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/lk-agent.err.log
stdout_logfile=/var/log/lk-agent.out.log
environment=PYTHONUNBUFFERED=1,HOME="/home/ubuntu"


```console
sudo supervisorctl reread
sudo supervisorctl update
```
