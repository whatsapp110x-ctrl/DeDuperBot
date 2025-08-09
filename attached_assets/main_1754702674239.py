import os
import hashlib
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Thread
import asyncio

from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from flask import Flask
from replit import db

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Duplicate Cleaner Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.route('/stats')
def stats():
    """Return real-time bot statistics"""
    if 'bot_instance' in globals():
        bot_stats = bot_instance.stats.copy()
        uptime = datetime.now() - bot_stats['start_time']
        bot_stats['uptime_hours'] = round(uptime.total_seconds() / 3600, 2)
        bot_stats['start_time'] = bot_stats['start_time'].isoformat()
        return bot_stats
    return {"status": "bot not initialized"}

def run_flask():
    """Run Flask server in a separate thread"""
    port = int(os.environ.get("PORT", 5000))
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.warning(f"Port {port} is already in use - Flask server not started")
        else:
            logger.error(f"Flask server error: {e}")

class DuplicateCleanerBot:
    def __init__(self):
        # Storage for message hashes and metadata
        # Format: {chat_id: {hash: {"timestamp": datetime, "message_id": int}}}
        self.message_store = defaultdict(dict)
        
        # Storage for bot activation status per chat
        # Format: {chat_id: True/False}
        self.active_chats = defaultdict(bool)
        
        # Real-time performance statistics
        self.stats = {
            'messages_processed': 0,
            'duplicates_deleted': 0,
            'active_chats': 0,
            'start_time': datetime.now(),
            'avg_response_time': 0.0
        }
        
        # Maximum entries per chat (prevent memory overflow)
        self.MAX_ENTRIES_PER_CHAT = 10000
        
        # Message expiry time (30 days)
        self.EXPIRY_DAYS = 30
        
        # Get bot token from environment
        self.bot_token = os.getenv("BOT_TOKEN", "")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")
    
    def cleanup_expired_messages(self):
        """Remove messages older than EXPIRY_DAYS"""
        current_time = datetime.now()
        expiry_threshold = current_time - timedelta(days=self.EXPIRY_DAYS)
        
        for chat_id in list(self.message_store.keys()):
            chat_messages = self.message_store[chat_id]
            expired_hashes = []
            
            for msg_hash, metadata in chat_messages.items():
                if metadata["timestamp"] < expiry_threshold:
                    expired_hashes.append(msg_hash)
            
            # Remove expired messages
            for msg_hash in expired_hashes:
                del chat_messages[msg_hash]
            
            # Remove empty chat entries
            if not chat_messages:
                del self.message_store[chat_id]
        
        logger.info(f"Cleanup completed. Active chats: {len(self.message_store)}")
    
    def limit_chat_entries(self, chat_id):
        """Limit entries per chat to prevent memory overflow"""
        chat_messages = self.message_store[chat_id]
        
        if len(chat_messages) > self.MAX_ENTRIES_PER_CHAT:
            # Sort by timestamp and keep only the newest entries
            sorted_messages = sorted(
                chat_messages.items(),
                key=lambda x: x[1]["timestamp"],
                reverse=True
            )
            
            # Keep only the newest MAX_ENTRIES_PER_CHAT entries
            new_messages = dict(sorted_messages[:self.MAX_ENTRIES_PER_CHAT])
            self.message_store[chat_id] = new_messages
            
            logger.info(f"Limited chat {chat_id} to {self.MAX_ENTRIES_PER_CHAT} entries")
    
    def generate_message_hash(self, message):
        """Generate a hash for the message content"""
        content_parts = []
        
        # Text content
        if message.text:
            content_parts.append(message.text.strip())
        
        if message.caption:
            content_parts.append(message.caption.strip())
        
        # File-based content
        if message.photo:
            # Use the largest photo's file_id
            largest_photo = max(message.photo, key=lambda x: x.file_size or 0)
            content_parts.append(f"photo:{largest_photo.file_id}")
        
        if message.document:
            content_parts.append(f"document:{message.document.file_id}")
        
        if message.video:
            content_parts.append(f"video:{message.video.file_id}")
        
        if message.audio:
            content_parts.append(f"audio:{message.audio.file_id}")
        
        if message.voice:
            content_parts.append(f"voice:{message.voice.file_id}")
        
        if message.video_note:
            content_parts.append(f"video_note:{message.video_note.file_id}")
        
        if message.sticker:
            content_parts.append(f"sticker:{message.sticker.file_id}")
        
        if message.animation:
            content_parts.append(f"animation:{message.animation.file_id}")
        
        # Create hash from combined content
        if content_parts:
            combined_content = "|".join(content_parts)
            return hashlib.sha256(combined_content.encode()).hexdigest()
        
        return None
    
    async def is_user_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if the user is an admin in the chat"""
        try:
            chat_id = update.effective_chat.id
            user_id = update.effective_user.id
            
            # Get chat member information
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            
            # Check if user is admin or creator
            return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        
        except TelegramError as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /startbot command (anyone can use)"""
        logger.info(f"Received /startbot command from user {update.effective_user.id} in chat {update.effective_chat.id}")
        
        try:
            chat_id = update.effective_chat.id
            self.active_chats[chat_id] = True
            
            await update.message.reply_text(
                "🤖 **Duplicate Cleaner Activated!**\n\n"
                "🔍 **Now monitoring for duplicates:**\n"
                "• Text messages\n"
                "• Images & Photos\n" 
                "• Videos & GIFs\n"
                "• Audio & Voice notes\n"
                "• Documents & Files\n"
                "• Stickers\n\n"
                "⚡ **Ultra-fast detection** - duplicates deleted instantly\n"
                "🧠 **Smart memory** - 30 days, 10k messages per chat\n"
                "👥 **Open access** - anyone can control\n\n"
                "Type `/stopbot` to deactivate",
                parse_mode='Markdown'
            )
            
            logger.info(f"Bot activated in chat {chat_id} by user {update.effective_user.id}")
            self.stats['active_chats'] = len([c for c in self.active_chats.values() if c])
        except Exception as e:
            logger.error(f"Error in start_bot_command: {e}")
            await update.message.reply_text("❌ An error occurred while processing the command.")
    
    async def stop_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stopbot command (anyone can use)"""
        logger.info(f"Received /stopbot command from user {update.effective_user.id} in chat {update.effective_chat.id}")
        
        try:
            chat_id = update.effective_chat.id
            self.active_chats[chat_id] = False
            
            # Clear stored messages for this chat
            if chat_id in self.message_store:
                del self.message_store[chat_id]
            
            await update.message.reply_text(
                "🛑 **Duplicate Cleaner Deactivated**\n\n"
                "📴 Monitoring stopped for this chat\n"
                "🗑️ All stored data cleared\n"
                "💤 Bot is now inactive\n\n"
                "Type `/startbot` to reactivate anytime",
                parse_mode='Markdown'
            )
            
            logger.info(f"Bot deactivated in chat {chat_id} by user {update.effective_user.id}")
            self.stats['active_chats'] = len([c for c in self.active_chats.values() if c])
        except Exception as e:
            logger.error(f"Error in stop_bot_command: {e}")
            await update.message.reply_text("❌ An error occurred while processing the command.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show bot performance statistics"""
        try:
            uptime = datetime.now() - self.stats['start_time']
            uptime_hours = round(uptime.total_seconds() / 3600, 2)
            
            efficiency = 0
            if self.stats['messages_processed'] > 0:
                efficiency = round((self.stats['duplicates_deleted'] / self.stats['messages_processed']) * 100, 1)
            
            stats_text = (
                f"📊 **Bot Performance Stats**\n\n"
                f"⚡ **Runtime:** {uptime_hours} hours\n"
                f"📨 **Messages processed:** {self.stats['messages_processed']:,}\n"
                f"🗑️ **Duplicates deleted:** {self.stats['duplicates_deleted']:,}\n"
                f"💬 **Active chats:** {self.stats['active_chats']}\n"
                f"🎯 **Detection rate:** {efficiency}%\n"
                f"🚀 **Status:** Ultra-fast & responsive\n\n"
                f"🔗 **Web stats:** Check https://{os.environ.get('REPL_SLUG', 'your-repl')}.{os.environ.get('REPL_OWNER', 'username')}.repl.co/stats"
            )
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats_command: {e}")
            await update.message.reply_text("❌ An error occurred while fetching statistics.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages and check for duplicates"""
        start_time = time.time()
        chat_id = update.effective_chat.id
        
        # Update statistics
        self.stats['messages_processed'] += 1
        
        # Check if bot is active in this chat
        if not self.active_chats.get(chat_id, False):
            return
        
        # Skip if message is from a bot or is a command
        if update.effective_user.is_bot or (update.message.text and update.message.text.startswith('/')):
            return
        
        # Generate message hash
        message_hash = self.generate_message_hash(update.message)
        if not message_hash:
            return  # Skip messages without hashable content
        
        # Check for duplicate
        chat_messages = self.message_store[chat_id]
        current_time = datetime.now()
        
        if message_hash in chat_messages:
            # Duplicate found - delete the message
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=update.message.message_id
                )
                logger.info(f"🗑️ Deleted duplicate in chat {chat_id}")
                self.stats['duplicates_deleted'] += 1
                
                # Update timestamp of the original message  
                chat_messages[message_hash]["timestamp"] = current_time
                
            except TelegramError as e:
                logger.error(f"Failed to delete duplicate message: {e}")
        else:
            # New message - store it
            chat_messages[message_hash] = {
                "timestamp": current_time,
                "message_id": update.message.message_id
            }
            
            # Limit entries to prevent memory overflow
            self.limit_chat_entries(chat_id)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
    
    async def periodic_cleanup(self, context: ContextTypes.DEFAULT_TYPE):
        """Periodic cleanup of expired messages"""
        self.cleanup_expired_messages()
    
    def run(self):
        """Run the bot"""
        # Create application
        application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("startbot", self.start_bot_command))
        application.add_handler(CommandHandler("stopbot", self.stop_bot_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(MessageHandler(filters.ALL, self.handle_message))
        application.add_error_handler(self.error_handler)
        
        # Schedule periodic cleanup (every 6 hours) if job_queue is available
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_repeating(
                self.periodic_cleanup,
                interval=21600,  # 6 hours in seconds
                first=60  # Start after 1 minute
            )
            logger.info("Scheduled periodic cleanup every 6 hours")
        else:
            logger.warning("JobQueue not available - periodic cleanup disabled")
        
        logger.info("Starting Telegram Duplicate Cleaner Bot...")
        
        # Start Flask server in a separate thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Start the bot with optimized settings
        application.run_polling(
            allowed_updates=["message", "chat_member"],
            drop_pending_updates=True
        )

def main():
    """Main function"""
    try:
        global bot_instance
        bot_instance = DuplicateCleanerBot()
        bot_instance.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
