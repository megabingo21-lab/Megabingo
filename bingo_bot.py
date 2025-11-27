import telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import random
import os
import logging
import asyncio

# --- Configuration ---
# The bot token must be set securely as a Replit Secret.
# We fetch it here from the environment variable (TELEGRAM_BOT_TOKEN).
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GAME_NUMBERS = list(range(1, 76)) # Standard Bingo numbers 1-75

# Set up logging 
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Game State (Simplified In-Memory) ---
# NOTE: This state is in-memory and will only track one game at a time. 
# It will persist as long as the Replit worker is running.
game_state = {
    'is_active': False,
    'numbers_drawn': [],
    'remaining_numbers': []
}


# --- Helper Function for Bingo Column ---

def get_bingo_column(number: int) -> str:
    """Returns the Bingo column letter for a given number."""
    if 1 <= number <= 15:
        return 'B'
    elif 16 <= number <= 30:
        return 'I'
    elif 31 <= number <= 45:
        return 'N'
    elif 46 <= number <= 60:
        return 'G'
    else: # 61 <= number <= 75
        return 'O'

# --- Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    await update.message.reply_text(
        'Welcome to MegaBingo! 🎉\n'
        'I am ready to call the numbers.\n'
        'Use /newgame to start a fresh round.\n'
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
    
    column = get_bingo_column(drawn_number)
        
    await update.message.reply_text(
        f'The number is... **{column}-{drawn_number}**! 🔔\n'
        f'{len(game_state["numbers_drawn"])} numbers drawn so far. {len(game_state["remaining_numbers"])} remaining.'
    )
    
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows all numbers drawn so far in the current game."""
    global game_state
    
    if not game_state['numbers_drawn']:
        await update.message.reply_text('No numbers have been drawn yet in this game. Start one with /newgame.')
        return
        
    # Format the history into a block of text
    history_text = ", ".join(map(str, game_state['numbers_drawn']))
    
    await update.message.reply_text(
        f'🔢 **Drawn Numbers History:**\n'
        f'{history_text}'
    )

# --- Main Function ---

def main() -> None:
    """Start the bot using Polling Mode (ideal for Replit/Worker environment)."""
    if not BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN environment variable is not set. The bot cannot start.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # Register the command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("newgame", new_game_command))
    application.add_handler(CommandHandler("draw", draw_command))
    application.add_handler(CommandHandler("history", history_command))
    
    # Start the Bot in Polling Mode
    print("Starting MegaBingo Bot in Polling mode...")
    # The application.run_polling() call is blocking and keeps the bot running
    application.run_polling(poll_interval=3.0)

if __name__ == '__main__':
    # Ensure asyncio is used correctly if the environment requires it
    try:
        main()
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
