import os
import logging
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

# ==================== CONFIGURATION ====================
# Get these from environment variables (we'll set them on the server)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ==================== LOGGING ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP (Keeps bot alive) ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ YouTube Downloader Bot is Running!"

@app.route('/health')
def health():
    return {"status": "alive", "bot": "YouTube Downloader"}

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

# ==================== YOUTUBE DOWNLOADER FUNCTIONS ====================

def get_video_info(url):
    """Get video/playlist information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        logger.error(f"Error getting info: {e}")
        return None

def download_video(url, download_type='video', quality='best'):
    """Download video/audio from YouTube"""
    
    # Create downloads directory if not exists
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    if download_type == 'audio':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
    else:
        # Video download
        if quality == 'best':
            format_spec = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == '720':
            format_spec = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]'
        elif quality == '480':
            format_spec = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]'
        elif quality == '360':
            format_spec = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]'
        else:
            format_spec = 'best[ext=mp4]/best'
        
        ydl_opts = {
            'format': format_spec,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Update extension for audio files
            if download_type == 'audio':
                filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            return filename, info
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None, str(e)

# ==================== BOT COMMAND HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when /start is issued"""
    welcome_text = """
🎬 <b>Welcome to YouTube Downloader Bot!</b>

I can download:
✅ Single YouTube videos
✅ Complete playlists
✅ Audio only (MP3)
✅ Videos in different qualities

<b>How to use:</b>
1️⃣ Send me a YouTube video or playlist link
2️⃣ Choose your download option
3️⃣ Wait for download to complete
4️⃣ Receive your file!

<b>Commands:</b>
/start - Show this message
/help - Get help
/about - About this bot

📎 <b>Just paste a YouTube link to get started!</b>
    """
    
    keyboard = [
        [InlineKeyboardButton("🎬 Video", callback_data='info_video'),
         InlineKeyboardButton("🎵 Audio", callback_data='info_audio')],
        [InlineKeyboardButton("📋 Playlist", callback_data='info_playlist')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = """
<b>📖 How to Use This Bot</b>

<b>1. Download a Single Video:</b>
   • Paste any YouTube video link
   • Choose "🎬 Video" for video or "🎵 Audio" for MP3
   • Select quality (Best, 720p, 480p, 360p)
   • Wait for download

<b>2. Download a Playlist:</b>
   • Paste playlist URL
   • Bot will download all videos
   • Files sent one by one

<b>3. Supported Links:</b>
   • youtube.com/watch?v=...
   • youtu.be/...
   • youtube.com/playlist?list=...
   • youtube.com/shorts/...

<b>⚠️ Notes:</b>
   • Large files may take time
   • Maximum file size: 2GB (Telegram limit)
   • Be patient during downloads

<b>Need help?</b> Contact: @yourusername
    """
    await update.message.reply_text(help_text, parse_mode='HTML')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send about message"""
    about_text = """
<b>🤖 About YouTube Downloader Bot</b>

📌 <b>Version:</b> 2.0
📌 <b>Features:</b>
   • Video & Audio downloads
   • Playlist support
   • Multiple quality options
   • Fast & Free

📌 <b>Powered by:</b>
   • python-telegram-bot
   • yt-dlp
   • Flask

📌 <b>Hosted on:</b> Render (Free Tier)

Made with ❤️ for easy YouTube downloads
    """
    await update.message.reply_text(about_text, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    message_text = update.message.text
    
    # Check if it's a YouTube URL
    if 'youtube.com' in message_text or 'youtu.be' in message_text:
        # Store URL in user data
        context.user_data['current_url'] = message_text
        
        # Get video info first
        processing_msg = await update.message.reply_text("🔍 Analyzing link... Please wait.")
        
        info = get_video_info(message_text)
        
        if not info:
            await processing_msg.edit_text("❌ Error: Could not fetch video information. Please check the URL.")
            return
        
        # Check if it's a playlist
        if 'entries' in info:
            # It's a playlist
            playlist_title = info.get('title', 'Unknown Playlist')
            entry_count = len(info['entries'])
            
            context.user_data['is_playlist'] = True
            context.user_data['playlist_info'] = info
            
            keyboard = [
                [InlineKeyboardButton("🎬 Download All Videos", callback_data='playlist_video')],
                [InlineKeyboardButton("🎵 Download All Audio (MP3)", callback_data='playlist_audio')],
                [InlineKeyboardButton("❌ Cancel", callback_data='cancel')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                f"📋 <b>Playlist Found!</b>\n\n"
                f"📝 Title: {playlist_title}\n"
                f"🔢 Videos: {entry_count}\n\n"
                f"Choose download option:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            # Single video
            video_title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
            
            context.user_data['is_playlist'] = False
            
            keyboard = [
                [InlineKeyboardButton("🎬 Video", callback_data='type_video')],
                [InlineKeyboardButton("🎵 Audio (MP3)", callback_data='type_audio')],
                [InlineKeyboardButton("❌ Cancel", callback_data='cancel')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                f"🎬 <b>Video Found!</b>\n\n"
                f"📝 Title: {video_title}\n"
                f"⏱ Duration: {duration_str}\n\n"
                f"Choose download type:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    else:
        await update.message.reply_text(
            "❌ That doesn't look like a YouTube link.\n\n"
            "Please send a valid YouTube URL like:\n"
            "• https://youtube.com/watch?v=...\n"
            "• https://youtu.be/..."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Info buttons (from start menu)
    if data.startswith('info_'):
        if data == 'info_video':
            await query.edit_message_text(
                "🎬 <b>Video Download</b>\n\n"
                "Send any YouTube video link and select 'Video' to download in MP4 format.\n\n"
                "Supported qualities: Best, 720p, 480p, 360p",
                parse_mode='HTML'
            )
        elif data == 'info_audio':
            await query.edit_message_text(
                "🎵 <b>Audio Download</b>\n\n"
                "Send any YouTube video link and select 'Audio (MP3)' to extract audio.\n\n"
                "Format: MP3 (192kbps)",
                parse_mode='HTML'
            )
        elif data == 'info_playlist':
            await query.edit_message_text(
                "📋 <b>Playlist Download</b>\n\n"
                "Send a YouTube playlist link to download all videos.\n\n"
                "⚠️ Note: Large playlists may take significant time.",
                parse_mode='HTML'
            )
        return
    
    # Cancel button
    if data == 'cancel':
        await query.edit_message_text("❌ Download cancelled.")
        context.user_data.clear()
        return
    
    # Type selection (Video/Audio)
    if data == 'type_video':
        keyboard = [
            [InlineKeyboardButton("⭐ Best Quality", callback_data='quality_best')],
            [InlineKeyboardButton("📺 720p", callback_data='quality_720')],
            [InlineKeyboardButton("📺 480p", callback_data='quality_480')],
            [InlineKeyboardButton("📺 360p", callback_data='quality_360')],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_type')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎬 Select video quality:",
            reply_markup=reply_markup
        )
        return
    
    if data == 'type_audio':
        context.user_data['download_type'] = 'audio'
        await start_download(query, context)
        return
    
    # Back button
    if data == 'back_type':
        keyboard = [
            [InlineKeyboardButton("🎬 Video", callback_data='type_video')],
            [InlineKeyboardButton("🎵 Audio (MP3)", callback_data='type_audio')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Choose download type:",
            reply_markup=reply_markup
        )
        return
    
    # Quality selection
    if data.startswith('quality_'):
        quality = data.replace('quality_', '')
        context.user_data['download_type'] = 'video'
        context.user_data['quality'] = quality
        await start_download(query, context)
        return
    
    # Playlist download
    if data.startswith('playlist_'):
        download_type = data.replace('playlist_', '')
        context.user_data['download_type'] = download_type
        context.user_data['is_playlist'] = True
        await start_playlist_download(query, context)
        return

async def start_download(query, context):
    """Start single video download"""
    url = context.user_data.get('current_url')
    download_type = context.user_data.get('download_type', 'video')
    quality = context.user_data.get('quality', 'best')
    
    if not url:
        await query.edit_message_text("❌ Error: URL not found. Please send the link again.")
        return
    
    type_text = "🎵 Audio" if download_type == 'audio' else f"🎬 Video ({quality} quality)"
    await query.edit_message_text(f"⬇️ Downloading {type_text}...\n\nPlease wait, this may take a few minutes.")
    
    # Download in background to not block
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, 
        lambda: download_video(url, download_type, quality)
    )
    
    filename, info = result
    
    if filename and os.path.exists(filename):
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        
        # Check file size (Telegram limit is 2GB for bots)
        if file_size > 2000:
            await query.edit_message_text(
                f"❌ File too large ({file_size:.1f} MB).\n"
                f"Telegram limit is 2000 MB.\n\n"
                f"Try downloading a lower quality version."
            )
            os.remove(filename)
            return
        
        await query.edit_message_text(f"✅ Download complete!\n📤 Uploading to Telegram ({file_size:.1f} MB)...")
        
        # Send the file
        try:
            with open(filename, 'rb') as file:
                if download_type == 'audio':
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=file,
                        title=info.get('title', 'Unknown'),
                        performer=info.get('uploader', 'Unknown'),
                        duration=info.get('duration', 0)
                    )
                else:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=file,
                        caption=f"🎬 {info.get('title', 'Unknown')}",
                        supports_streaming=True
                    )
            
            await query.edit_message_text("✅ Done! Send another link to download more.")
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error uploading file: {str(e)}")
        finally:
            # Clean up
            if os.path.exists(filename):
                os.remove(filename)
    else:
        error_msg = info if isinstance(info, str) else "Unknown error"
        await query.edit_message_text(f"❌ Download failed: {error_msg}")
    
    context.user_data.clear()

async def start_playlist_download(query, context):
    """Start playlist download"""
    info = context.user_data.get('playlist_info')
    download_type = context.user_data.get('download_type', 'video')
    
    if not info or 'entries' not in info:
        await query.edit_message_text("❌ Error: Playlist information not found.")
        return
    
    entries = info['entries']
    total = len(entries)
    type_text = "🎵 Audio" if download_type == 'audio' else "🎬 Video"
    
    await query.edit_message_text(
        f"📋 Starting playlist download\n"
        f"📝 Total videos: {total}\n"
        f"📥 Type: {type_text}\n\n"
        f"⏳ This will take some time. Please wait..."
    )
    
    success_count = 0
    fail_count = 0
    
    for i, entry in enumerate(entries, 1):
        if not entry:
            continue
            
        url = entry.get('url') or f"https://youtube.com/watch?v={entry.get('id')}"
        
        try:
            # Update progress every 5 videos
            if i % 5 == 0 or i == 1:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"⏳ Progress: {i}/{total} videos processed..."
                )
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: download_video(url, download_type, 'best')
            )
            
            filename, video_info = result
            
            if filename and os.path.exists(filename):
                file_size = os.path.getsize(filename) / (1024 * 1024)
                
                if file_size > 2000:
                    fail_count += 1
                    os.remove(filename)
                    continue
                
                with open(filename, 'rb') as file:
                    if download_type == 'audio':
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=file,
                            title=video_info.get('title', 'Unknown'),
                            performer=video_info.get('uploader', 'Unknown')
                        )
                    else:
                        await context.bot.send_video(
                            chat_id=query.message.chat_id,
                            video=file,
                            caption=f"🎬 {video_info.get('title', 'Unknown')} ({i}/{total})"
                        )
                
                success_count += 1
                os.remove(filename)
            else:
                fail_count += 1
                
        except Exception as e:
            logger.error(f"Error downloading playlist item {i}: {e}")
            fail_count += 1
            continue
    
    # Final summary
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"✅ <b>Playlist Download Complete!</b>\n\n"
             f"✓ Successful: {success_count}\n"
             f"✗ Failed: {fail_count}\n"
             f"📊 Total: {total}",
        parse_mode='HTML'
    )
    
    context.user_data.clear()

# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later or check your URL."
        )

# ==================== MAIN FUNCTION ====================

async def run_bot():
    """Run the bot with asyncio"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Keep running
    while True:
        await asyncio.sleep(3600)

def main():
    """Start the bot"""
    # Start Flask in separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run bot with asyncio
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()
