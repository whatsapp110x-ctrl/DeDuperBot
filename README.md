# Enhanced Telegram Duplicate Cleaner Bot

This bot removes duplicate text, files, audio, video, and images in Telegram groups and channels.
**New**: Auto-activates in channels and detects duplicates regardless of forwarding status.
It works on **Replit** and **Render** with no code changes.

## 🆕 New Features
- **Auto-activation for channels**: No `/startbot` needed when added to channels
- **Universal duplicate detection**: Catches duplicates whether forwarded or original
- **Enhanced file detection**: Uses `file_unique_id` for better cross-forward duplicate detection
- **Smart activation**: Channels auto-activate, groups need manual activation
- **Improved statistics**: Shows auto-activated channels count

## Features
- Monitors any group/channel it is in
- **Auto-activates in channels** (manual activation for groups)
- Deletes duplicates instantly (30-day memory)
- **Detects forwards as duplicates** using enhanced hashing
- Limits storage to 10,000 entries per chat
- Responds to commands from any user
- Compatible with both Replit & Render
- Flask keep-alive server for 24/7 uptime
- Automatic cleanup of expired messages
- Memory management to prevent overflow

---

## Setup

### 1. Create a Telegram Bot
1. Open [@BotFather](https://t.me/BotFather).
2. Run `/newbot` → Follow instructions → Save the token.
3. Run `/setprivacy` → Choose your bot → **Disable** privacy mode.
4. Add the bot to your group/channel as **admin** with "Delete messages" permission.

---

### 2. Run on Replit
1. Fork this repo to your GitHub account.
2. Import it into [Replit](https://replit.com/).
3. Go to **Tools → Secrets** and add:
   - Key: `BOT_TOKEN`
   - Value: your token from BotFather.
4. Click **Run**.
5. (Optional) Use [UptimeRobot](https://uptimerobot.com/) to ping the `/` endpoint every 5 minutes for 24/7 uptime.

---

### 3. Deploy on Render
1. Push this repo to GitHub (if not already).
2. Go to [Render](https://render.com/).
3. Create **New Web Service**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
4. Add Environment Variable:
   ```
   BOT_TOKEN=your-bot-token-here
   ```
5. Deploy.

---

### 4. Commands
- `/startbot` — Activates duplicate detection in the chat (anyone can use)
- `/stopbot` — Deactivates duplicate detection and clears stored data (anyone can use)
- `/stats` — Shows real-time bot performance statistics

---

### 5. How It Works

#### Enhanced Duplicate Detection
- **Universal Detection**: Creates SHA256 hashes of message content, ignoring forwarding metadata
- **File Unique IDs**: Uses `file_unique_id` instead of `file_id` to catch forwards as duplicates
- **Auto-Activation**: Channels automatically activate when bot is added as admin
- **Memory Management**: Stores up to 10,000 messages per chat
- **Auto-Expiry**: Removes messages older than 30 days
- **Instant Deletion**: Removes duplicate messages immediately upon detection

#### Channel vs Group Behavior
- **Channels**: Auto-activate duplicate detection when bot is added
- **Groups**: Require manual `/startbot` command for activation
- **Cross-Platform**: Works identically on both chat types once active

---

### 6. Supported Content Types
- Text messages (forwarded or original)
- Photos/Images
- Videos
- Audio files
- Voice messages
- Documents/Files
- Stickers
- Animations/GIFs
- Video notes

**All content types are detected as duplicates regardless of forwarding status.**

---

### 7. Requirements
- Bot must be admin in the chat/channel
- Bot needs "Delete Messages" permission
- Anyone can use the bot commands
- **Channels auto-activate, groups need manual activation**

---

### 8. Technical Details
- **Language**: Python 3.11+
- **Framework**: python-telegram-bot v22.3+
- **Web Server**: Flask (for keep-alive)
- **Storage**: In-memory with smart cleanup (resets on restart)
- **Deployment**: Replit, Render, or any Python hosting service
- **Enhanced**: Auto-activation and universal duplicate detection

---

### 9. Troubleshooting

**Bot not auto-activating in channels:**
- Ensure bot is added as admin with proper permissions
- Check if bot has "Delete Messages" permission
- Verify BOT_TOKEN is correctly set

**Bot not responding to commands:**
- Ensure bot is admin in the chat
- Check if privacy mode is disabled in BotFather
- Verify BOT_TOKEN is correctly set

**Bot not deleting duplicates:**
- Confirm bot has "Delete Messages" permission
- Make sure bot is active (auto for channels, `/startbot` for groups)
- Check bot logs for error messages

**Memory issues:**
- Bot automatically limits to 10,000 entries per chat
- Old messages (30+ days) are automatically cleaned up
- Restart the bot to clear all stored data

---

### 10. API Endpoints

**Health Check:**
- `GET /` - Basic status check
- `GET /health` - Detailed health information
- `GET /stats` - Real-time bot statistics including auto-activated channels

---

### 11. License
This project is open source. Feel free to modify and distribute.

---

## Quick Start
1. Get bot token from @BotFather
2. Set BOT_TOKEN environment variable
3. Run `python main.py`
4. Add bot as admin to your chat/channel
5. **Channels**: Bot auto-activates immediately
6. **Groups**: Send `/startbot` in the chat
7. Done! All duplicates (forwarded or original) will be automatically removed.

## 🚀 Performance Features
- Real-time statistics with `/stats` command
- Web dashboard at `/stats` endpoint
- Auto-activated channels tracking
- Ultra-fast duplicate detection
- Cross-platform compatibility
- 24/7 uptime with Flask keep-alive server
