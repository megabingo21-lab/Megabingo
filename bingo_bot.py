import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import random
import os
import logging

# --- Configuration ---
# Your bot token should be stored securely as an environment variable in Render.
# We fetch it here, but it MUST be set in the deployment environment (e.g., Render settings).
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_PLACEHOLDER_TOKEN") 
GAME_NUMBERS = list(range(1, 76)) # Standard Bingo numbers 1-75

# Set up logging for better debugging in Render logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Game State (Simplified In-Memory) ---
# NOTE: For a real-world, multi-user game, this must be replaced with a database (like SQLite or Postgres).
# In-memory variables will reset every time the bot service restarts (common in free tiers).
# For now, we use a simple dict to hold the state of one game.
game_state = {
    'is_active': False,
    'numbers_drawn': [],
    'remaining_numbers': []
}


# --- Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    await update.message.reply_text(
        'Welcome to MegaBingo! 🎉\n'
        'Use /newgame to start a fresh round of Bingo.\n'
        'Use /draw to pull the next number.'
    )

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resets and starts a new Bingo game."""
    global game_state
    
    game_state['is_active'] = True
    game_state['numbers_drawn'] = []
    game_state['remaining_numbers'] = list(GAME_NUMBERS)
    
    await update.message.reply_text(
        'A new game of MegaBingo has started! 🥳\n'
        'Total numbers available: 75. Use /draw to call the first number.'
    )

async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Draws a random, unique number and announces it."""
    global game_state
    
    if not game_state['is_active']:
        await update.message.reply_text('The game is not active. Use /newgame to start.')
        return
    
    if not game_state['remaining_numbers']:
        await update.message.reply_text("All 75 numbers have been drawn! Game over!")
        game_state['is_active'] = False
        return

    # Draw a random number from the remaining list
    drawn_number = random.choice(game_state['remaining_numbers'])
    
    # Remove it from the remaining list and add it to the drawn list
    game_state['remaining_numbers'].remove(drawn_number)
    game_state['numbers_drawn'].append(drawn_number)
    
    # Announce the number with a column letter (B:1-15, I:16-30, N:31-45, G:46-60, O:61-75)
    if 1 <= drawn_number <= 15:
        column = 'B'
    elif 16 <= drawn_number <= 30:
        column = 'I'
    elif 31 <= drawn_number <= 45:
        column = 'N'
    elif 46 <= drawn_number <= 60:
        column = 'G'
    else: # 61 <= drawn_number <= 75
        column = 'O'
        
    await update.message.reply_text(
        f'The number is... **{column}-{drawn_number}**! 🔔\n'
        f'{len(game_state["numbers_drawn"])} numbers drawn so far. {len(game_state["remaining_numbers"])} remaining.'
    )
    
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows all numbers drawn so far in the current game."""
    global game_state
    
    if not game_state['numbers_drawn']:
        await update.message.reply_text('No numbers have been drawn yet in this game.')
        return
        
    history_text = ", ".join(map(str, game_state['numbers_drawn']))
    
    # Send a formatted list of drawn numbers
    await update.message.reply_text(
        f'🔢 **Drawn Numbers History:**\n'
        f'{history_text}'
    )

# --- Main Function ---

def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_PLACEHOLDER_TOKEN":
        logging.error("TELEGRAM_BOT_TOKEN environment variable is not set. The bot cannot start.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("newgame", new_game_command))
    application.add_handler(CommandHandler("draw", draw_command))
    application.add_handler(CommandHandler("history", history_command))
    
    # Start the Bot in Polling Mode (easiest for testing/simple deployment)
    # We will need to adapt this to Webhooks for production/Render if necessary, 
    # but Polling is a good start.
    print("Starting bot in Polling mode...")
    application.run_polling(poll_interval=3.0)

if __name__ == '__main__':
    main()
