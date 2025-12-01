import asyncio, os, logging, enum, time, random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update, InputFile
from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- 1. Configuration and Logging ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
if not BOT_TOKEN: 
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. Database Configuration and Models ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./data.db" 
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# The MovedIn20Warning shown in your logs is harmless, as the function still works.
Base = declarative_base() 

class GameState(enum.Enum):
    IDLE = 'IDLE'; LOBBY = 'LOBBY'; RUNNING = 'RUNNING'; PAUSED = 'PAUSED'

class ActiveGame(Base):
    __tablename__ = "active_game"
    id = Column(Integer, primary_key=True, index=True, default=1)
    state = Column(Enum(GameState), default=GameState.IDLE)
    chat_id = Column(Integer, nullable=True)
    drawn_numbers = Column(String, default="")
    pool_size = Column(Integer, default=75) 
    last_call_message_id = Column(Integer, nullable=True)
    lobby_start_time = Column(Integer, nullable=True)

class PlayerCard(Base):
    __tablename__ = "player_cards"
    user_id = Column(Integer, primary_key=True)
    chat_id = Column(Integer)
    card_data = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

# --- 3. Utility Functions ---

def generate_bingo_card_numbers():
    card = {}
    card['B'] = random.sample(range(1, 16), 5)
    card['I'] = random.sample(range(16, 31), 5)
    card['N'] = random.sample(range(31, 46), 4)
    card['G'] = random.sample(range(46, 61), 5)
    card['O'] = random.sample(range(61, 76), 5)
    data_list = [f"{col}:{','.join(map(str, nums))}" for col, nums in card.items()]
    return card, "|".join(data_list)

def render_bingo_card_image(card_data_string, drawn_numbers_list=None):
    if drawn_numbers_list is None: drawn_numbers_list = []
    card = {}; drawn_nums_set = set()
    for item in card_data_string.split('|'):
        col, nums_str = item.split(':')
        card[col] = [int(n) for n in nums_str.split(',')]
    for drawn in drawn_numbers_list:
        try: drawn_nums_set.add(int(drawn.split('-')[1]))
        except: pass
        
    CARD_SIZE = (500, 550); img = Image.new('RGB', CARD_SIZE, color='white')
    draw = ImageDraw.Draw(img)
    try:
        font_col = ImageFont.truetype("arial.ttf", 40)
        font_num = ImageFont.truetype("arial.ttf", 30)
    except IOError:
        font_col = ImageFont.load_default()
        font_num = ImageFont.load_default()

    COLUMNS = ['B', 'I', 'N', 'G', 'O']; CELL_SIZE = 100; START_Y = 50
    
    for i, col_name in enumerate(COLUMNS):
        x = i * CELL_SIZE
        draw.rectangle([x, 0, x + CELL_SIZE, START_Y], outline='black', fill='#ddd')
        draw.text((x + 50, 5), col_name, fill='black', font=font_col, anchor='mm')
        numbers = card[col_name]
        for j in range(5):
            y = START_Y + j * CELL_SIZE
            draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], outline='black')
            if col_name == 'N' and j == 2:
                num = "FREE"; fill_color = 'red'
            elif j < len(numbers):
                num = str(numbers[j])
                fill_color = 'green' if numbers[j] in drawn_nums_set else 'black'
            else:
                num = ""; fill_color = 'black'
            draw.text((x + 50, y + 50), num, fill=fill_color, font=font_num, anchor='mm')

    bio = BytesIO(); bio.name = 'bingo_card.png'
    img.save(bio, 'PNG'); bio.seek(0)
    return bio

def get_next_bingo_number(drawn_numbers_str):
    all_numbers = list(range(1, 76))
    drawn_list = [int(n.split('-')[1]) for n in drawn_numbers_str.split(',') if n and '-' in n]
    available_numbers = [n for n in all_numbers if n not in drawn_list]
    
    if not available_numbers: return None, True

    next_num = random.choice(available_numbers)
    
    if 1 <= next_num <= 15: col = 'B'
    elif 16 <= next_num <= 30: col = 'I'
    elif 31 <= next_num <= 45: col = 'N'
    elif 46 <= next_num <= 60: col = 'G'
    else: col = 'O'
    
    return f"{col}-{next_num}", False

# --- 4. Game Engine (V7.7 Automatic Worker Logic) ---
DRAW_INTERVAL_SECONDS = 5
LOBBY_CHECK_INTERVAL_SECONDS = 10

async def game_engine(app: Application):
    """The background loop that automatically resumes and runs the game."""
    while True:
        db = SessionLocal(); game = db.query(ActiveGame).first()
        
        if game is None or game.state == GameState.IDLE:
            db.close(); await asyncio.sleep(LOBBY_CHECK_INTERVAL_SECONDS); continue

        elif game.state == GameState.LOBBY:
            player_count = db.query(PlayerCard).filter(PlayerCard.chat_id == game.chat_id).count()
            if game.lobby_start_time and (time.time() - game.lobby_start_time) > 60 and player_count >= 1:
                 game.state = GameState.RUNNING
                 db.commit()
                 await app.bot.send_message(game.chat_id, "🔔 **Lobby time is over! Starting game now!**", parse_mode="Markdown")

            db.close(); await asyncio.sleep(LOBBY_CHECK_INTERVAL_SECONDS)

        elif game.state == GameState.RUNNING:
            try:
                next_number, is_game_over = get_next_bingo_number(game.drawn_numbers)
                
                if is_game_over:
                    game.state = GameState.IDLE
                    db.commit()
                    await app.bot.send_message(game.chat_id, "🚨 **GAME OVER!** All numbers drawn. No winner found.", parse_mode="Markdown")
                    db.close(); await asyncio.sleep(DRAW_INTERVAL_SECONDS); continue
                    
                game.drawn_numbers += f",{next_number}" if game.drawn_numbers else next_number
                drawn_list = game.drawn_numbers.split(',')
                message_text = f"🚨 **Number {len(drawn_list)} Called!**\n\n🎯 New Number: `{next_number}`"
                
                if game.last_call_message_id and game.chat_id:
                     await app.bot.edit_message_text(
                         chat_id=game.chat_id, message_id=game.last_call_message_id, 
                         text=message_text, parse_mode="Markdown"
                     )
                elif game.chat_id:
                    msg = await app.bot.send_message(game.chat_id, message_text, parse_mode="Markdown")
                    game.last_call_message_id = msg.message_id
                    
                db.commit()
            except Exception as e: logger.error(f"Error during RUNNING state: {e}")

            db.close(); await asyncio.sleep(DRAW_INTERVAL_SECONDS)

        elif game.state == GameState.PAUSED:
            db.close(); await asyncio.sleep(DRAW_INTERVAL_SECONDS)

# --- 5. Handlers ---

async def start_command(update: Update, context):
    """Handles the /start command."""
    await update.message.reply_text("Welcome to MegaBingo! Use /join to start or join a game, or /card to see your card.")

async def join_game(update: Update, context):
    """Handles the /join command."""
    user_id = update.effective_user.id; chat_id = update.effective_chat.id
    db = SessionLocal(); game = db.query(ActiveGame).first() or ActiveGame()

    if game.state == GameState.IDLE:
        game.state = GameState.LOBBY; game.chat_id = chat_id
        game.drawn_numbers = ""; game.lobby_start_time = int(time.time())
        db.merge(game)

    if game.state == GameState.LOBBY or game.state == GameState.RUNNING:
        player_card = db.query(PlayerCard).filter_by(user_id=user_id, chat_id=chat_id).first()
        if player_card:
            await update.message.reply_text("You are already in the game! Use /card to view your card.")
        else:
            _, card_data_str = generate_bingo_card_numbers()
            player_card = PlayerCard(user_id=user_id, chat_id=chat_id, card_data=card_data_str)
            db.add(player_card)

            card_image_bio = render_bingo_card_image(card_data_str)
            await update.message.reply_photo(
                photo=card_image_bio, caption="🎉 **You joined!** Here is your card.", parse_mode="Markdown"
            )
            
        await update.message.reply_text(f"Game is currently in the **{game.state.value}** state. Use /card to check your card at any time.")
    else:
        await update.message.reply_text("A game is currently paused or in an invalid state. Please wait.")
        
    db.commit(); db.close()

async def view_card(update: Update, context):
    """Handles the /card command."""
    user_id = update.effective_user.id; chat_id = update.effective_chat.id
    db = SessionLocal()
    player_card = db.query(PlayerCard).filter_by(user_id=user_id, chat_id=chat_id).first()
    game = db.query(ActiveGame).first()
    
    if not player_card:
        await update.message.reply_text("You have not joined a game yet. Use /join to get your card!")
        db.close(); return

    drawn_list = game.drawn_numbers.split(',') if game and game.drawn_numbers else []
    
    card_image_bio = render_bingo_card_image(player_card.card_data, drawn_list)
    
    await update.message.reply_photo(
        photo=card_image_bio,
        caption=f"Your Bingo Card (Updated)\n\nNumbers Called: **{len(drawn_list)}**",
        parse_mode="Markdown"
    )
    db.close()

async def all_other_messages(update: Update, context):
    pass

# --- 6. Main Application Entry Point (V7.7 Automatic Recovery) ---

async def resume_running_game(app: Application):
    """V7.7: Checks the DB on startup and automatically resumes the game."""
    db = SessionLocal(); game = db.query(ActiveGame).filter(ActiveGame.state != GameState.IDLE).first()
    
    if game and game.chat_id:
        if game.state == GameState.RUNNING:
            drawn_list = [n for n in game.drawn_numbers.split(',') if n]; drawn_count = len(drawn_list)
            message = (f"✅ **Game Automatically Resumed!** Continuing from **{drawn_count}th** number drawn.")
        elif game.state == GameState.LOBBY:
            message = ("✅ **Lobby Automatically Resumed!** Waiting for more players.")
        else:
            message = "✅ **System Restart:** The bot has restarted. Game state is preserved."

        try:
            await app.bot.send_message(game.chat_id, message, parse_mode="Markdown")
            logger.info(f"Successfully resumed game in chat {game.chat_id} with state {game.state}")
        except Exception as e:
            logger.error(f"Failed to send resume notification to chat {game.chat_id}: {e}")
            
    db.close()

def main() -> None:
    """Starts the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers (Final Corrected Names)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("card", view_card))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, all_other_messages))

    # CRITICAL AUTOMATIC RECOVERY STEP
    try:
        # Step 1: Run the synchronous part of the resume check before polling
        asyncio.run(resume_running_game(app)) 
    except Exception as e:
        logger.error(f"Error during initial game resume process: {e}")

    # Step 2: Fix for AttributeError: 'Application' object has no attribute 'loop'
    async def post_init(application: Application) -> None:
        """Runs after the Application is initialized to start the non-blocking game engine task."""
        logger.info("Starting game_engine background task via post_init.")
        asyncio.create_task(game_engine(application))

    app.post_init = post_init
    
    logger.info("MegaBingo V7.7 FULL AUTO-RECOVERY LIVE... Starting Polling.")
    app.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
