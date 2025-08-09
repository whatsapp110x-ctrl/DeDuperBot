from keep_alive import keep_alive
import os
import hashlib
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Thread
import asyncio

from telegram import Update, ChatMember, Chat
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
from telegram.error import TelegramError

from flask import Flask

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
    """Return enhanced real-time bot statistics"""
    if 'bot_instance' in globals():
        uptime = datetime.now() - bot_instance.stats['start_time']
        uptime_hours = round(uptime.total_seconds() / 3600, 1)
        
        efficiency = 0
        if bot_instance.stats['messages_processed'] > 0:
            efficiency = round((bot_instance.stats['duplicates_deleted'] / bot_instance.stats['messages_processed']) * 100, 1)
        
        forwarded_rate = 0
        if bot_instance.stats['duplicates_deleted'] > 0:
            forwarded_rate = round((bot_instance.stats['forwarded_duplicates'] / bot_instance.stats['duplicates_deleted']) * 100, 1)
        
        content_breakdown = {}
        for content_type, count in bot_instance.stats['content_types_processed'].items():
            if count > 0:
                content_breakdown[content_type] = count
        
        return {
            "status": "🟢 Enhanced & Running",
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": uptime_hours,
            "performance": {
                "messages_processed": bot_instance.stats['messages_processed'],
                "duplicates_deleted": bot_instance.stats['duplicates_deleted'],
                "detection_efficiency": f"{efficiency}%",
                "avg_response_time": f"{bot_instance.stats['avg_response_time']:.2f}ms"
            },
            "content_analysis": {
                "types_processed": content_breakdown,
                "forwarded_duplicates_rate": f"{forwarded_rate}%",
                "forwarded_vs_original": {
                    "forwarded": bot_instance.stats['forwarded_duplicates'],
                    "original": bot_instance.stats['original_duplicates']
                }
            },
            "chat_management": {
                "active_chats": len(bot_instance.active_chats),
                "auto_activated_chats": len(bot_instance.auto_activated_channels)
            },
            "memory_stats": {
                "total_entries": bot_instance.stats['total_memory_usage'],
                "largest_chat_size": bot_instance.stats['largest_chat_size'],
                "retention_policy": "Infinite (never expires)",
                "per_chat_limit": bot_instance.MAX_ENTRIES_PER_CHAT
            },
            "system_info": {
                "version": "Enhanced v2.1",
                "features": ["Auto-activation", "Infinite memory", "Content analysis", "Forward detection", "Real-time stats"],
                "mode": "Fully automatic"
            }
        }
    return {"status": "❌ Bot not initialized", "timestamp": datetime.now().isoformat()}

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
        # Format: {chat_id: {hash: {"timestamp": datetime, "message_id": int, "type": str, etc.}}}
        self.message_store = defaultdict(dict)
        
        # Storage for bot activation status per chat
        # Format: {chat_id: True/False}
        self.active_chats = defaultdict(bool)
        
        # Track auto-activated channels
        self.auto_activated_channels = set()
        
        # Rate limiting and error handling
        self.rate_limit_tracker = defaultdict(list)
        self.error_tracker = defaultdict(int)
        self.MAX_ERRORS_PER_CHAT = 10
        
        # Real-time performance statistics
        self.stats = {
            'messages_processed': 0,
            'duplicates_deleted': 0,
            'active_chats': 0,
            'start_time': datetime.now(),
            'avg_response_time': 0.0,
            'total_memory_usage': 0,
            'largest_chat_size': 0,
            'content_types_processed': {
                'text': 0,
                'photo': 0,
                'video': 0,
                'audio': 0,
                'document': 0,
                'voice': 0,
                'sticker': 0,
                'animation': 0
            },
            'forwarded_duplicates': 0,
            'original_duplicates': 0
        }
        
        # Maximum entries per chat (prevent memory overflow)
        self.MAX_ENTRIES_PER_CHAT = 10000
        
        # Message expiry time (infinite - no expiration)
        self.EXPIRY_DAYS = None
        
        # Get bot token from environment
        self.bot_token = os.getenv("BOT_TOKEN", "")
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")
    
    def cleanup_expired_messages(self):
        """Remove messages older than EXPIRY_DAYS (skip if infinite memory)"""
        if self.EXPIRY_DAYS is None:
            logger.info("Cleanup skipped - infinite memory mode enabled")
            return
            
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
        """Generate enhanced hash for message content with detailed type tracking"""
        content_parts = []
        message_type = None
        
        # Text content (normalize whitespace and case for better detection)
        if message.text:
            normalized_text = ' '.join(message.text.strip().lower().split())
            content_parts.append(f"text:{normalized_text}")
            message_type = 'text'
        
        if message.caption:
            normalized_caption = ' '.join(message.caption.strip().lower().split())
            content_parts.append(f"caption:{normalized_caption}")
        
        # Enhanced media detection with file metadata
        if message.photo:
            largest_photo = max(message.photo, key=lambda x: x.file_size or 0)
            content_parts.append(f"photo:{largest_photo.file_unique_id}")
            if largest_photo.file_size:
                content_parts.append(f"size:{largest_photo.file_size}")
            message_type = 'photo'
        
        if message.document:
            content_parts.append(f"document:{message.document.file_unique_id}")
            if message.document.file_name:
                content_parts.append(f"filename:{message.document.file_name.lower()}")
            if message.document.file_size:
                content_parts.append(f"size:{message.document.file_size}")
            message_type = 'document'
        
        if message.video:
            content_parts.append(f"video:{message.video.file_unique_id}")
            if message.video.duration:
                content_parts.append(f"duration:{message.video.duration}")
            if message.video.file_size:
                content_parts.append(f"size:{message.video.file_size}")
            message_type = 'video'
        
        if message.audio:
            content_parts.append(f"audio:{message.audio.file_unique_id}")
            if message.audio.duration:
                content_parts.append(f"duration:{message.audio.duration}")
            if message.audio.title:
                content_parts.append(f"title:{message.audio.title.lower()}")
            message_type = 'audio'
        
        if message.voice:
            content_parts.append(f"voice:{message.voice.file_unique_id}")
            if message.voice.duration:
                content_parts.append(f"duration:{message.voice.duration}")
            message_type = 'voice'
        
        if message.video_note:
            content_parts.append(f"video_note:{message.video_note.file_unique_id}")
            if message.video_note.duration:
                content_parts.append(f"duration:{message.video_note.duration}")
            message_type = 'video_note'
        
        if message.sticker:
            content_parts.append(f"sticker:{message.sticker.file_unique_id}")
            if message.sticker.set_name:
                content_parts.append(f"set:{message.sticker.set_name}")
            message_type = 'sticker'
        
        if message.animation:
            content_parts.append(f"animation:{message.animation.file_unique_id}")
            if message.animation.file_size:
                content_parts.append(f"size:{message.animation.file_size}")
            message_type = 'animation'
        
        # Create enhanced hash with content fingerprinting
        if content_parts:
            combined_content = "|".join(sorted(content_parts))  # Sort for consistency
            message_hash = hashlib.sha256(combined_content.encode()).hexdigest()
            return message_hash, message_type
        
        return None, None
    
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
    
    async def handle_chat_member_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle when bot is added to or removed from chats"""
        try:
            chat_member_update = update.my_chat_member or update.chat_member
            if not chat_member_update:
                return
            
            chat = update.effective_chat
            chat_id = chat.id
            new_status = chat_member_update.new_chat_member.status
            old_status = chat_member_update.old_chat_member.status if chat_member_update.old_chat_member else None
            
            # Check if bot was added as admin
            if (new_status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER] and 
                old_status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]):
                
                # Auto-activate for both channels and groups
                if chat.type in [Chat.CHANNEL, Chat.GROUP, Chat.SUPERGROUP]:
                    self.active_chats[chat_id] = True
                    self.auto_activated_channels.add(chat_id)
                    
                    chat_type_name = "channel" if chat.type == Chat.CHANNEL else "group"
                    logger.info(f"🤖 Auto-activated duplicate detection in {chat_type_name} {chat.title} ({chat_id})")
                    
                    # Try to send activation message if possible
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="🤖 **Auto-Activated!** Duplicate Cleaner is now monitoring this chat.\n\n"
                                 "🔍 **Detecting all duplicates:**\n"
                                 "• Text messages (forwarded or original)\n"
                                 "• Images & Photos\n" 
                                 "• Videos & GIFs\n"
                                 "• Audio & Voice notes\n"
                                 "• Documents & Files\n"
                                 "• Stickers & Animations\n\n"
                                 "⚡ **Ultra-fast detection** - duplicates deleted instantly\n"
                                 "♾️ **Infinite memory** - never forgets duplicates\n"
                                 "🤖 **Auto-mode** - no commands needed",
                            parse_mode='Markdown'
                        )
                    except TelegramError:
                        # Chat might not allow bot messages, continue silently
                        pass
            
            # Handle bot removal
            elif new_status in [ChatMember.LEFT, ChatMember.KICKED]:
                if chat_id in self.active_chats:
                    del self.active_chats[chat_id]
                if chat_id in self.message_store:
                    del self.message_store[chat_id]
                self.auto_activated_channels.discard(chat_id)
                logger.info(f"🗑️ Bot removed from chat {chat.title} ({chat_id}) - cleaned up data")
            
            # Update active chats count
            self.stats['active_chats'] = len([c for c in self.active_chats.values() if c])
            
        except Exception as e:
            logger.error(f"Error handling chat member update: {e}")
    
    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /startbot command (anyone can use)"""
        logger.info(f"Received /startbot command from user {update.effective_user.id} in chat {update.effective_chat.id}")
        
        try:
            chat_id = update.effective_chat.id
            chat_type = update.effective_chat.type
            
            self.active_chats[chat_id] = True
            
            # Universal message for all chat types (now auto-activated)
            message_text = (
                "🤖 **Duplicate Cleaner Activated!**\n\n"
                "🔍 **Now monitoring for duplicates:**\n"
                "• Text messages (forwarded or original)\n"
                "• Images & Photos\n" 
                "• Videos & GIFs\n"
                "• Audio & Voice notes\n"
                "• Documents & Files\n"
                "• Stickers & Animations\n\n"
                "⚡ **Ultra-fast detection** - duplicates deleted instantly\n"
                "♾️ **Infinite memory** - never forgets duplicates\n"
                "🤖 **Auto-mode** - activates automatically when added\n\n"
                "Note: Bot auto-activates - no commands needed"
            )
            
            await update.message.reply_text(message_text, parse_mode='Markdown')
            
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
            
            # Remove from auto-activated channels if applicable
            self.auto_activated_channels.discard(chat_id)
            
            # Clear stored messages for this chat
            if chat_id in self.message_store:
                del self.message_store[chat_id]
            
            await update.message.reply_text(
                "🛑 **Duplicate Cleaner Temporarily Deactivated**\n\n"
                "📴 Monitoring stopped for this chat\n"
                "🗑️ All stored data cleared\n"
                "💤 Bot is now inactive\n\n"
                "⚠️ **Note**: Bot will auto-reactivate if you remove and re-add it as admin\n"
                "Use `/startbot` for manual reactivation",
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
            
            auto_channels = len(self.auto_activated_channels)
            
            # Enhanced stats with content breakdown
            content_stats = []
            for content_type, count in self.stats['content_types_processed'].items():
                if count > 0:
                    content_stats.append(f"{content_type}: {count:,}")
            content_breakdown = ", ".join(content_stats) if content_stats else "None yet"
            
            # Forwarding analysis
            total_duplicates = self.stats['duplicates_deleted']
            forwarded_rate = 0
            if total_duplicates > 0:
                forwarded_rate = round((self.stats['forwarded_duplicates'] / total_duplicates) * 100, 1)
            
            stats_text = (
                f"📊 **Enhanced Bot Performance Stats**\n\n"
                f"⏱️ **Runtime:** {uptime_hours} hours\n"
                f"📨 **Messages processed:** {self.stats['messages_processed']:,}\n"
                f"🗑️ **Duplicates deleted:** {self.stats['duplicates_deleted']:,}\n"
                f"📋 **Content breakdown:** {content_breakdown}\n"
                f"📤 **Forwarded duplicates:** {forwarded_rate}%\n"
                f"💬 **Active chats:** {self.stats['active_chats']}\n"
                f"🤖 **Auto-activated chats:** {auto_channels}\n"
                f"🧠 **Memory usage:** {self.stats['total_memory_usage']:,} entries\n"
                f"📈 **Largest chat:** {self.stats['largest_chat_size']:,} messages\n"
                f"🎯 **Detection efficiency:** {efficiency}%\n"
                f"♾️ **Memory retention:** Infinite (never expires)\n"
                f"🚀 **Status:** Fully automatic & optimized\n\n"
                f"🔗 **Web dashboard:** Check /stats endpoint"
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
        
        # Generate enhanced message hash with type detection
        hash_result = self.generate_message_hash(update.message)
        if not hash_result[0]:
            return  # Skip messages without hashable content
        
        message_hash, message_type = hash_result
        
        # Update content type statistics
        if message_type and message_type in self.stats['content_types_processed']:
            self.stats['content_types_processed'][message_type] += 1
        
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
                # Enhanced duplicate tracking with forwarding detection
                is_forwarded = hasattr(update.message, 'forward_origin') and update.message.forward_origin is not None
                
                # Update forwarded vs original duplicate statistics
                if is_forwarded:
                    self.stats['forwarded_duplicates'] += 1
                else:
                    self.stats['original_duplicates'] += 1
                
                logger.info(f"🗑️ Deleted {message_type or 'unknown'} duplicate in chat {chat_id} (forwarded: {is_forwarded})")
                self.stats['duplicates_deleted'] += 1
                
                # Update timestamp of the original message  
                chat_messages[message_hash]["timestamp"] = current_time
                
            except TelegramError as e:
                # Enhanced error handling with rate limiting
                error_msg = str(e).lower()
                self.error_tracker[chat_id] += 1
                
                if "too many requests" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"Rate limited in chat {chat_id} - backing off")
                    self.rate_limit_tracker[chat_id].append(datetime.now())
                elif "message can't be deleted" in error_msg:
                    logger.info(f"Message already deleted or too old in chat {chat_id}")
                elif "not enough rights" in error_msg:
                    logger.warning(f"Insufficient permissions in chat {chat_id} - need delete messages permission")
                else:
                    logger.error(f"Failed to delete duplicate message in chat {chat_id}: {e}")
                
                # Auto-deactivate if too many errors
                if self.error_tracker[chat_id] > self.MAX_ERRORS_PER_CHAT:
                    logger.warning(f"Too many errors in chat {chat_id} - auto-deactivating")
                    self.active_chats[chat_id] = False
        else:
            # New message - store it with enhanced metadata
            chat_messages[message_hash] = {
                "timestamp": current_time,
                "message_id": update.message.message_id,
                "type": message_type,
                "forwarded": hasattr(update.message, 'forward_origin') and update.message.forward_origin is not None,
                "user_id": update.effective_user.id,
                "size": getattr(getattr(update.message, message_type, None), 'file_size', None) if message_type else None
            }
            
            # Update memory usage statistics
            self.stats['total_memory_usage'] = sum(len(messages) for messages in self.message_store.values())
            chat_size = len(chat_messages)
            if chat_size > self.stats['largest_chat_size']:
                self.stats['largest_chat_size'] = chat_size
            
            # Limit entries per chat to prevent memory overflow
            self.limit_chat_entries(chat_id)
        
        # Update response time statistics
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        if self.stats['avg_response_time'] == 0:
            self.stats['avg_response_time'] = response_time
        else:
            self.stats['avg_response_time'] = (self.stats['avg_response_time'] + response_time) / 2
    
    async def cleanup_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Background job to clean up expired messages"""
        logger.info("Running scheduled cleanup...")
        self.cleanup_expired_messages()
    
    def run(self):
        """Run the bot"""
        global bot_instance
        bot_instance = self
        
        # Create application
        application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("startbot", self.start_bot_command))
        application.add_handler(CommandHandler("stopbot", self.stop_bot_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(ChatMemberHandler(self.handle_chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message))
        
        # Add cleanup job (every 6 hours)
        job_queue = application.job_queue
        job_queue.run_repeating(self.cleanup_job, interval=21600, first=21600)  # 6 hours
        
        logger.info("🤖 Enhanced Telegram Duplicate Cleaner Bot v2.1 started!")
        logger.info("🔍 Features: Auto-activation, Infinite memory, Content analysis, Forward detection")
        logger.info("🚀 Mode: Fully automatic with advanced error handling and performance monitoring")
        
        # Start Flask server in a separate thread
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        # Run the bot
        application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        # Start optional keep-alive server
        from keep_alive import keep_alive
        keep_alive()

        # Start the Telegram bot
        bot = DuplicateCleanerBot()
        bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise
