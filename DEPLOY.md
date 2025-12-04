# Deployment Guide: From Zero to Running on VPS

This guide assumes you are using a fresh **Ubuntu** (or Debian-based) VPS.

## 1. Connect to your VPS

SSH into your server:
```bash
ssh root@<your_vps_ip>
```

## 2. Install Docker & Docker Compose

Run the following commands to install Docker and the Docker Compose plugin:

```bash
# Update package index
apt-get update

# Install prerequisites
apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources
echo \
  "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker compose version
```

## 3. Upload Project Files

You can upload the files using `scp` (from your local machine) or `git clone` (if you pushed to a repo).

### Option A: Using SCP (Simplest for local code)
Run this **from your local computer** (PowerShell or Terminal):

```bash
# Replace <your_vps_ip> with your server's IP
scp -r C:\Users\Lucas\Desktop\qqbot root@<your_vps_ip>:/opt/qqbot
```
*Note: This copies the entire folder to `/opt/qqbot` on the server.*

### Option B: Using Git (Recommended)
If you have pushed your code to GitHub/GitLab:

```bash
# On the VPS
cd /opt
git clone https://github.com/your-username/qqbot.git
cd qqbot
```

## 4. Configure Environment
1.  **Navigate to the project directory:**
    ```bash
    cd /opt/qqbot
    ```

2.  **Create .env file:**
    ```bash
    cp .env.example .env
    nano .env
    ```
    *Make sure to fill in:*
    *   `GEMINI_API_KEYS`: Your Google Gemini API keys (uses official `google-genai` SDK with intelligent model auto-selection).
    *   `OPENWEATHER_API_KEY`: Your OpenWeatherMap API key (Required for weather).

## 5. Start Services

Run the containers in the background:

```bash
docker compose up -d
```

## 6. Login to QQ (NapCat)

1.  **Open Firewall (If needed):**
    Ensure port `6099` is open in your VPS firewall (or Security Group on AWS/Aliyun/Tencent).
    ```bash
    ufw allow 6099/tcp
    ```

2.  **Access Web UI:**
    Open your browser and go to: `http://<your_vps_ip>:6099/webui`
    *   **Note**: If asked for a **Token**, run this command on your VPS to find it:
        ```bash
        docker compose logs napcat | grep Token
        ```

3.  **Scan QR Code:**
    Use your mobile QQ app to scan the code and log in.

4.  **Configure Network (If needed):**
    *   If the bot doesn't connect automatically (NapCat shows "0 Network Config"), go to **Network Configuration** -> **WebSocket Clients**.
    *   Add a new connection:
        *   **URL**: `ws://qqbot:8080/onebot/v11/ws`
        *   **Enable**: On
    *   Save.

5.  **Verify Connection:**
    Once logged in, the bot should automatically connect. You can verify by checking logs:
    ```bash
    docker compose logs -f bot
    ```
    Try sending a command in your QQ group:
    *   `/在吗` (Should reply "在呢")
    *   `/天气 北京` (Should reply with weather report)

## 7. Security (Important!)

Once you have logged in successfully, **you should close port 6099** to prevent unauthorized access to your QQ account control panel.

```bash
# If using UFW
ufw delete allow 6099/tcp
```

If you need to access it again later (e.g., to re-login), just re-open the port temporarily or use an SSH tunnel:
```bash
# Local SSH Tunnel (Run on your PC)
ssh -L 6099:localhost:6099 root@<your_vps_ip>
# Then access http://localhost:6099/webui locally
```
