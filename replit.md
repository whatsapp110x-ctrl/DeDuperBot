# Enhanced Telegram Duplicate Cleaner Bot

## Overview

This is a Telegram bot designed to automatically detect and remove duplicate messages (text, files, audio, video, and images) in Telegram groups and channels. The bot features enhanced duplicate detection that works across forwarded and original messages, auto-activation for channels, and maintains a 30-day memory of messages with intelligent storage management. It's designed for 24/7 operation on cloud platforms like Replit and Render.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Bot Framework
- **Telegram Bot API**: Built using `python-telegram-bot` library with asynchronous message handling
- **Event-Driven Architecture**: Responds to message events, chat member updates, and admin commands in real-time
- **Smart Activation System**: Auto-activates in channels upon joining, requires manual activation for groups via `/startbot` command

### Advanced Duplicate Detection System
- **Multi-Layer Hashing**: Enhanced SHA-256 hashing with content normalization and metadata fingerprinting
- **File Unique ID Detection**: Leverages Telegram's `file_unique_id` for cross-forward duplicate detection of all media types
- **Content Intelligence**: Normalized text processing, file size/duration matching, and metadata-aware detection
- **Universal Content Support**: Specialized handlers for text, photos, videos, audio, voice, documents, stickers, and animations
- **Forwarding Analysis**: Intelligent detection distinguishing forwarded vs original content with separate tracking
- **Performance Optimization**: Smart memory management with 10,000 entries per chat and infinite retention
- **Real-Time Analytics**: Content type breakdown, forwarding statistics, and performance monitoring

### Data Storage
- **In-Memory Storage**: Uses Python dictionaries and collections for fast duplicate detection and statistics
- **Chat-Specific Organization**: Maintains separate storage per chat ID to handle multiple groups/channels
- **Statistical Tracking**: Real-time tracking of duplicates found, messages processed, and auto-activated channels

### Access Control and Permissions
- **Flexible Command Access**: Allows commands from any user (departure from admin-only in previous version)
- **Admin Permission Requirements**: Bot must be added as admin with "Delete messages" permission
- **Privacy Mode Integration**: Designed to work with privacy mode disabled for full message access

### High Availability Infrastructure
- **Flask Keep-Alive Server**: Runs concurrent HTTP server for health checks and statistics endpoints
- **Multi-Threading**: Separates bot operations from web server using threading for non-blocking operation
- **Health and Statistics APIs**: Provides `/health` and `/stats` endpoints for monitoring and real-time statistics
- **Cross-Platform Deployment**: Zero-code-change compatibility between Replit and Render platforms

### Error Handling and Monitoring
- **Comprehensive Logging**: Structured logging system for debugging and operational monitoring
- **Telegram Error Resilience**: Graceful handling of API rate limits, network issues, and permission errors
- **Uptime Statistics**: Tracks bot uptime, performance metrics, and operational status

## External Dependencies

### Core Dependencies
- **python-telegram-bot**: Primary library for Telegram Bot API interactions and webhook handling
- **Flask**: Lightweight web framework for keep-alive server and API endpoints
- **hashlib**: Built-in Python library for SHA-256 hashing of message content
- **datetime/collections**: Standard Python libraries for time management and data structures

### Platform Integration
- **Replit Environment**: Designed for Replit's cloud environment with PORT environment variable support
- **Render Compatibility**: Full compatibility with Render's deployment model
- **UptimeRobot Integration**: Optional external monitoring service for 24/7 uptime maintenance

### Runtime Requirements
- **Python Threading**: Concurrent execution of Flask server and Telegram bot
- **Environment Variables**: BOT_TOKEN configuration through secure environment variables
- **HTTP Health Checks**: External monitoring capability through web endpoints

## Recent Changes

### August 9, 2025 - Enhanced Bot v2.1 - Performance & Intelligence Upgrade
- **Status**: ✅ Complete enhancement package successfully implemented
- **Universal Auto-Activation**: Bot automatically activates in ALL chats (channels and groups) when added as admin
- **Infinite Memory**: Removed 30-day expiration - bot now remembers duplicates forever with smart memory management
- **Advanced Duplicate Detection**: Enhanced hash algorithm with normalized text, file metadata, and cross-forward detection
- **Content Analysis System**: Real-time tracking of all content types (text, photo, video, audio, documents, stickers, animations)
- **Forwarding Intelligence**: Separate tracking of forwarded vs original duplicates with detailed statistics
- **Performance Monitoring**: Response time tracking, memory usage analytics, and chat size optimization
- **Enhanced Error Handling**: Rate limiting detection, permission error handling, auto-deactivation on excessive errors
- **Advanced Statistics**: Comprehensive stats with content breakdown, forwarding analysis, and system performance metrics
- **Web Dashboard Enhancement**: Detailed JSON API with real-time performance, content analysis, and system information
- **Production-Ready Features**: Auto-recovery, graceful error handling, and intelligent resource management