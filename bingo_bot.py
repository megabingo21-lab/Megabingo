import telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import random
import os
import logging
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# --- 1. CONFIGURATION & SECRETS ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GAME_NUMBERS = list(range(1, 76)) # Standard Bingo numbers 1-75

# --- CRUCIAL: ADMIN SETUP ---
# ADMIN ID IS SET TO YOUR PROVIDED VALUE
ADMIN_CHAT_ID = 7932072571 

# Financial Constants
MIN_DEPOSIT = 50.0
MIN_WITHDRAWAL = 100.0
GAME_COST = 20.0
COMMISSION_RATE = 0.20 # 20%
CALL_DELAY = 2.30 # seconds

# --- 2. LOCALIZATION (Amharic Constants) ---
AMHARIC = {
    "welcome": "እንኳን ወደ ሜጋ ቢንጎ በደህና መጡ! 🎉\nለጨዋታ ዝግጁ ነኝ። /getcard ተጠቅመው ካርድ ይምረጡ።",
    "new_game_started": "አዲስ ጨዋታ ተጀምሯል! 🥳\nጠቅላላ ተጫዋቾች: {count}\nየመጀመሪያውን ቁጥር ለመጥራት /draw ይጠቀሙ።",
    "not_active": "ጨዋታው አልተጀመረም። ለመጀመር /newgame ይጠቀሙ።",
    "draw_announcement": "ቁጥሩ... **{column}-{number}**! 🔔\n{drawn} ቁጥሮች ወጥተዋል። {remaining} ቀርተዋል።",
    "all_drawn": "ሁሉም 75 ቁጥሮች ወጥተዋል! ጨዋታው አልቋል!",
    "no_card": "ካርድ የለዎትም። ለመጫወት /getcard በመጠቀም ካርድ ይምረጡ።",
    "card_exists": "አስቀድሞ ካርድ ወስደዋል። በአንድ ጨዋታ አንድ ካርድ ብቻ ነው የሚፈቀደው።",
    "card_success": "ካርድ ቁጥር **{card_id}** ተሰጥተዎታል። መልካም ዕድል! ✨",
    "deposit_info": f"ማስገባት (Deposit):\nአነስተኛ ማስገቢያ፡ {MIN_DEPOSIT:.2f} ብር\nገንዘብዎን ወደዚህ የቴሌብር ቁጥር ይላኩ: **0997077778**\nከተላከ በኋላ፣ የመላኪያ **ደረሰኝ (receipt) ምስል** ወደዚህ ቦት ይላኩልኝ።",
    "withdraw_info": f"ማውጣት (Withdraw):\nየእርስዎ ሂሳብ: {{0:.2f}} ብር\nአነስተኛ ማውጫ: {MIN_WITHDRAWAL:.2f} ብር\nለማውጣት፡ /withdraw [amount] [telebirr_account]",
    "deposit_received": "ደረሰኝዎን ተቀብለናል! አስተዳዳሪው ወዲያውኑ ሂሳብዎን ያረጋግጣል። በትዕግስት ይጠብቁ።",
    "deposit_forward_admin": "--- 🚨 አዲስ ማስገቢያ ጥያቄ 🚨 ---\nተጠቃሚ ID: `{user_id}`\nቴሌግራም መታወቂያ: @{username}\n(እባክዎ ከታች ያለውን ደረሰኝ ያረጋግጡና ሂሳቡን ይጨምሩ።)",
    "not_enough_balance": f"በቂ ሂሳብ የለዎትም። ለመጫወት {GAME_COST:.2f} ብር ያስፈልጋል።",
    "not_enough_withdraw": f"ለማውጣት {MIN_WITHDRAWAL:.2f} ብር ወይም ከዚያ በላይ ሊኖርዎት ይገባል።",
    "withdrawal_request": "ማውጣት ጥያቄ ተልኳል! አስተዳዳሪው ወዲያውኑ ይፈትሻል።",
    "withdrawal_forward_admin": "--- 🚨 አዲስ ማውጫ ጥያቄ 🚨 ---\nተጠቃሚ ID: `{user_id}`\nቴሌግራም መታወቂያ: @{username}\nየተጠየቀው መጠን: **{amount:.2f} ብር**\nየቴሌብር ቁጥር: **{telebirr}**\n(እባክዎ ያረጋግጡና ገንዘብ ይላኩ።)",
    "bingo_correct": "ቢንጎ! 🎉 እንኳን ደስ አለዎት! አሸንፈዋል! አሁን ውጤትዎን በመጠበቅ ላይ ነን።",
    "bingo_false": "ልክ አይደለም። (Invalid Bingo). ካርድዎን እንደገና ያረጋግጡ።",
    "winner_announcement": "👑 አሸናፊ: **{name}**\nጠቅላላ ሽልማት: **{prize:.2f} ብር**",
    "countdown": "ጨዋታው በ {time} ይጀምራል...",
    "referral_success": "ሪፈራልዎ ተመዝግቧል። ጓደኛዎ ለመጀመሪያ ጊዜ ሲያስገባ 10 ብር በሂሳብዎ ላይ ይታከላል።",
    "referral_info": "ጓደኞቻችሁን ስትጋብዙ 10 ብር ያግኙ! የእርስዎ ሪፈራል ኮድ: {ref_code}\nጓደኛዎ ለመጀመሪያ ጊዜ ሲያስገባ ብቻ።",
    "agent_info": "ይህ ትዕዛዝ ለተመዘገቡ ወኪሎች ብቻ ነው።",
    "total_players": "ጠቅላላ ተጫዋቾች: {count}",
    "game_active_error": "ጨዋታ አስቀድሞ እየተካሄደ ነው! /draw ይጠብቁ።",
}

# --- 3. DATABASE SETUP (SQLAlchemy) ---
BASE = declarative_base()
ENGINE = create_engine('sqlite:///megabingo.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

# Database Models
class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String)
    balance = Column(Float, default=0.0)
    referral_code = Column(String, unique=True, index=True)
    referred_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_agent = Column(Boolean, default=False)
    
class GameCard(BASE):
    __tablename__ = 'game_cards'
    id = Column(Integer, primary_key=True)
    card_arrangement = Column(String) # Stores the 5x5 grid numbers as a JSON/string
    user_id = Column(Integer, ForeignKey('users.id'), unique=True)
    
class ActiveGame(BASE):
    __tablename__ = 'active_game'
    id = Column(Integer, primary_key=True)
    is_active = Column(Boolean, default=False)
    numbers_drawn = Column(String, default="") # Comma-separated drawn numbers
    total_pool = Column(Float, default=0.0)
    player_count = Column(Integer, default=0)
    computer_count = Column(Integer, default=0)

# Create tables if they don't exist
def init_db():
    BASE.metadata.create_all(bind=ENGINE)

# --- 4. CORE BINGO LOGIC ---

def generate_bingo_card_arrangement() -> list[list[int]]:
    """Generates a standard 5x5 Bingo card (B-I-N-G-O) with a Free Space (0)."""
    # B: 1-15, I: 16-30, N: 31-45, G: 46-60, O: 61-75
    card = []
    
    b_column = random.sample(range(1, 16), 5)
    i_column = random.sample(range(16, 31), 5)
    n_column = random.sample(range(31, 46), 4) # Only 4 numbers
    g_column = random.sample(range(46, 61), 5)
    o_column = random.sample(range(61, 76), 5)

    # Combine and insert free space (0) at (2, 2)
    n_column.insert(2, 0) 
    
    # Create the 5x5 grid by zipping the columns
    for i in range(5):
        card.append([b_column[i], i_column[i], n_column[i], g_column[i], o_column[i]])
        
    return card

def is_winning_card(card_numbers_str: str, drawn_numbers: list[int]) -> bool:
    """Checks for a single line win (horizontal, vertical, or diagonal)."""
    
    # Load card from string (assuming comma-separated 25 numbers)
    card_list = [int(n) for n in card_numbers_str.split(',')]
    grid = [card_list[i*5:(i+1)*5] for i in range(5)]
    
    # Add Free Space (0) to drawn numbers if it's the center
    if 0 in card_list:
        drawn_numbers.append(0)

    # Helper function to check if a line is marked
    def check_line(line):
        return all(num in drawn_numbers for num in line)

    # 1. Check Rows (Horizontal)
    for row in grid:
        if check_line(row):
            return True

    # 2. Check Columns (Vertical)
    for col in range(5):
        column = [grid[row][col] for row in range(5)]
        if check_line(column):
            return True

    # 3. Check Diagonals
    diag1 = [grid[i][i] for i in range(5)]
    diag2 = [grid[i][4 - i] for i in range(5)]

    if check_line(diag1) or check_line(diag2):
        return True

    return False

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

def format_card_display(card_numbers_str: str, drawn_numbers: list[int]) -> str:
    """Formats the card with Green Checkmarks (✅) for drawn numbers."""
    
    card_list = [int(n) for n in card_numbers_str.split(',')]
    grid = [card_list[i*5:(i+1)*5] for i in range(5)]
    
    # Add Free Space (0) to drawn numbers for display
    if 0 in card_list:
        drawn_numbers.append(0)

    display = "    B  I  N  G  O\n"
    display += "------------------\n"

    # Mapping English digits to Amharic digits for number display
    amharic_digit_map = zip("0123456789", "፩፪፫፬፭፮፯፰፱")

    for row in grid:
        row_display = []
        for num in row:
            # Convert number to Amharic digits string
            amharic_num = "".join(str(num).replace(d, a) for d, a in amharic_digit_map)

            if num in drawn_numbers:
                # Mark with green check (✅) and bold
                if num == 0:
                    row_display.append("**F✅**") # Free Space
                else:
                    row_display.append(f"**{amharic_num}✅**")
            else:
                if num == 0:
                    row_display.append(" F ")
                else:
                    row_display.append(f" {amharic_num} ")
        display += "| " + " | ".join(row_display) + " |\n"
    
    return display

def generate_player_name(is_male: bool) -> str:
    """Generates a random Ethiopian name for stealth players."""
    male_names = ["Kidus", "Abebe", "Yonas", "Elias", "Tewodros", "Tesfaye", "Moges", "Daniel", "Samson", "Dawit", "Araya", "Fikru", "Gebre", "Haile"]
    female_names = ["Hana", "Mahlet", "Tsehay", "Eden", "Lidiya", "Tigist", "Marta", "Zelalem", "Selam", "Fikir"]

    name_pool = male_names if is_male else female_names
    name = random.choice(name_pool)
    
    # Add random suffix/emoji to make it look "real"
    suffix = random.choice(["", "77", "_ET", "🇪🇹", "🦅", "88", "🦁", "251"])
    return f"{name}{suffix}"

# --- 5. ASYNC COMMAND HANDLERS ---

async def get_db_session() -> SessionLocal:
    """Dependency to get a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    
    # Check for referral link in context arguments
    referred_by_id = None
    if context.args and len(context.args) == 1:
        ref_code = context.args[0]
        referred_by = db.query(User).filter(User.referral_code == ref_code).first()
        if referred_by and referred_by.telegram_id != user_id:
            referred_by_id = referred_by.id

    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        # Create new user
        user = User(
            telegram_id=user_id,
            username=update.effective_user.username,
            balance=0.0,
            referral_code=str(user_id), # Simple initial referral code
            referred_by_id=referred_by_id
        )
        db.add(user)
        db.commit()
    
    await update.message.reply_text(AMHARIC["welcome"])

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Starts a new game and handles stealth computer players."""
    db: SessionLocal = next(get_db_session())
    
    # 1. Check if a game is already active
    active_game = db.query(ActiveGame).first()
    if active_game and active_game.is_active:
        await update.message.reply_text(AMHARIC["game_active_error"])
        return

    # 2. Get real players with cards and deduct game cost
    # Only players who have a card assigned are "in the game" and have balance >= GAME_COST
    real_players_with_cards = db.query(User).join(GameCard).filter(User.balance >= GAME_COST, User.telegram_id > 0).all()
    real_player_count = len(real_players_with_cards)
    
    if real_player_count == 0:
         await update.message.reply_text("ቢያንስ አንድ ተጫዋች ካርድ ወስዶ ጨዋታውን ለመጀመር በቂ ሂሳብ ሊኖረው ይገባል።")
         return
         
    # Deduct cost for real players and calculate initial pool
    total_pool = 0.0
    for player in real_players_with_cards:
        player.balance -= GAME_COST
        total_pool += GAME_COST
        
    computer_count = 0
        
    # 3. Implement Stealth Computer Players
    if real_player_count < 20:
        computer_count = random.randint(20, 49) 
        
        for i in range(computer_count):
            name = generate_player_name(is_male=random.random() < 0.9)
            # Use negative IDs for computers
            comp_id = -abs(random.randint(10000000, 99999999)) 
            
            comp_user = db.query(User).filter(User.telegram_id == comp_id).first()
            if not comp_user:
                comp_user = User(telegram_id=comp_id, username=name, balance=0.0)
                db.add(comp_user)
                db.flush() # Ensure ID is generated for FK
            
            # Assign computer a unique card 
            new_card_grid = generate_bingo_card_arrangement()
            new_card_str = ','.join(map(str, [num for row in new_card_grid for num in row]))
            card = GameCard(user_id=comp_user.id, card_arrangement=new_card_str)
            db.add(card)
        
        # Add computer 'winnings' to the pool (20 ETB per computer player)
        total_pool += computer_count * GAME_COST 
        
    # 4. Create or Update Active Game State
    if not active_game:
        active_game = ActiveGame()
    
    active_game.is_active = True
    active_game.numbers_drawn = ""
    active_game.total_pool = total_pool
    active_game.player_count = real_player_count
    active_game.computer_count = computer_count
    
    db.add(active_game)
    db.commit()
    
    total_players = real_player_count + computer_count
    
    # Countdown (10-1)
    for i in range(10, 0, -1):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=AMHARIC["countdown"].format(time=i))
        await asyncio.sleep(1)

    await update.message.reply_text(AMHARIC["new_game_started"].format(count=total_players))
    
async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Draws a random number with delay, checks for computer win, and announces."""
    db: SessionLocal = next(get_db_session())
    active_game = db.query(ActiveGame).first()
    
    if not active_game or not active_game.is_active:
        await update.message.reply_text(AMHARIC["not_active"])
        return
        
    drawn_list = [int(n) for n in active_game.numbers_drawn.split(',') if n]
    remaining_numbers = [n for n in GAME_NUMBERS if n not in drawn_list]
    
    if not remaining_numbers:
        await update.message.reply_text(AMHARIC["all_drawn"])
        active_game.is_active = False
        db.commit()
        return

    # Draw number
    drawn_number = random.choice(remaining_numbers)
    drawn_list.append(drawn_number)
    
    # Update state
    active_game.numbers_drawn = ','.join(map(str, drawn_list))
    db.commit()
    
    # Announce with sound delay
    column = get_bingo_column(drawn_number)
    
    await update.message.reply_text("🔔") 
    await asyncio.sleep(CALL_DELAY) 
        
    # Amharic number display for the announced number
    amharic_num = "".join(str(drawn_number).replace(d, a) for d, a in zip("0123456789", "፩፪፫፬፭፮፯፰፱"))
        
    await update.message.reply_text(
        AMHARIC["draw_announcement"].format(
            column=column, 
            number=amharic_num, 
            drawn=len(drawn_list), 
            remaining=len(remaining_numbers)
        )
    )

    # --- STEALTH WINNER CHECK (Computers Win First) ---
    if active_game.computer_count > 0:
        # Check if a computer wins after the number is drawn
        computer_cards = db.query(User).filter(User.telegram_id < 0).join(GameCard).all()
        
        for comp_user in computer_cards:
            comp_card = db.query(GameCard).filter(GameCard.user_id == comp_user.id).first()
            if comp_card and is_winning_card(comp_card.card_arrangement, drawn_list):
                # Computer wins! (ALWAYS THEY ARE WINNERS, mind this)
                await handle_winner(context.bot, active_game, comp_user, db)
                return

async def getcard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows a player to get a unique card for the current game."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        await start_command(update, context)
        return

    # Check if card already exists
    if db.query(GameCard).filter(GameCard.user_id == user.id).first():
        await update.message.reply_text(AMHARIC["card_exists"])
        return

    # Check balance
    if user.balance < GAME_COST: 
        await update.message.reply_text(AMHARIC["not_enough_balance"])
        return

    # Card Selection/Generation (For simplicity, we generate a unique card)
    new_card_grid = generate_bingo_card_arrangement()
    new_card_str = ','.join(map(str, [num for row in new_card_grid for num in row]))

    card = GameCard(user_id=user.id, card_arrangement=new_card_str)
    db.add(card)
    db.commit()

    await update.message.reply_text(AMHARIC["card_success"].format(card_id=card.id))

async def mycard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the user's current card with marked numbers."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    
    user = db.query(User).filter(User.telegram_id == user_id).first()
    card = db.query(GameCard).filter(GameCard.user_id == user.id).first() if user else None
    active_game = db.query(ActiveGame).first()

    if not card:
        await update.message.reply_text(AMHARIC["no_card"])
        return
        
    drawn_list = [int(n) for n in active_game.numbers_drawn.split(',') if n] if active_game and active_game.is_active else []

    card_display = format_card_display(card.card_arrangement, drawn_list)
    
    await update.message.reply_text(f"🔢 **የእርስዎ ካርድ / Your Card** 🔢\n{card_display}")


async def bingo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows user to claim bingo and verifies the win."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id

    user = db.query(User).filter(User.telegram_id == user_id).first()
    card = db.query(GameCard).filter(GameCard.user_id == user.id).first() if user else None
    active_game = db.query(ActiveGame).first()

    if not active_game or not active_game.is_active or not card:
        await update.message.reply_text(AMHARIC["not_active"])
        return

    drawn_list = [int(n) for n in active_game.numbers_drawn.split(',') if n]
    
    if not active_game.is_active:
        await update.message.reply_text(AMHARIC["not_active"])
        return

    if is_winning_card(card.card_arrangement, drawn_list):
        # Correct Bingo - Handle Winner Logic
        await handle_winner(context.bot, active_game, user, db)
    else:
        # False Bingo (Amharic only)
        await update.message.reply_text(AMHARIC["bingo_false"])

async def handle_winner(bot: Bot, active_game: ActiveGame, winner: User, db: SessionLocal):
    """Calculates payout, resets game, and announces winner."""
    
    prize_amount = active_game.total_pool * (1 - COMMISSION_RATE)
    
    # Update real user balance only if it's a real player
    if winner.telegram_id > 0:
        winner.balance += prize_amount
        
        # Referral Bonus Check: Added 10 ETB logic is handled in admin_credit_command
        
    # 1. Announce Winner
    winner_name = winner.username if winner.telegram_id > 0 else winner.username 
    
    # Send winner announcement to the chat where the game is played (assuming the last update chat is the game chat)
    await bot.send_message(
        chat_id=bot.get_chat(active_game.id) if active_game.id else winner.telegram_id, 
        text=AMHARIC["winner_announcement"].format(name=winner_name, prize=prize_amount)
    )
    
    # 2. Reset Game State
    active_game.is_active = False
    active_game.numbers_drawn = ""
    active_game.total_pool = 0.0
    active_game.player_count = 0
    active_game.computer_count = 0
    
    # Clear all player cards for the next game (crucial)
    db.query(GameCard).delete()
    
    db.commit()
    
async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gives instructions for Telebirr deposit."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    
    user = db.query(User).filter(User.telegram_id == user_id).first()
    
    await update.message.reply_text(AMHARIC["deposit_info"])
    
async def handle_deposit_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forwards receipt images to the Admin for manual verification."""
    if update.effective_chat.type not in ["private"]:
        return # Only process receipts sent in private chat with the bot

    if not (update.message.photo or update.message.document):
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    
    caption = AMHARIC["deposit_forward_admin"].format(user_id=user_id, username=username)

    await context.bot.forward_message(
        chat_id=ADMIN_CHAT_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )
    
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=caption
    )
    
    await update.message.reply_text(AMHARIC["deposit_received"])

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles withdrawal requests and forwards them to Admin."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        await start_command(update, context)
        return
        
    if len(context.args) < 2:
        return await update.message.reply_text(AMHARIC["withdraw_info"].format(user.balance))

    try:
        amount = float(context.args[0])
        telebirr_account = context.args[1]
    except ValueError:
        return await update.message.reply_text("ትክክለኛ መጠን ያስገቡ። /withdraw [amount] [telebirr_account]")
        
    if user.balance < MIN_WITHDRAWAL or amount > user.balance or amount < MIN_WITHDRAWAL:
        return await update.message.reply_text(AMHARIC["not_enough_withdraw"])

    # Temporarily deduct balance to prevent double spending
    user.balance -= amount
    db.commit()

    # Forward request to Admin
    caption = AMHARIC["withdrawal_forward_admin"].format(
        user_id=user_id, 
        username=user.username or "N/A", 
        amount=amount, 
        telebirr=telebirr_account
    )
    
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=caption)
    
    await update.message.reply_text(AMHARIC["withdrawal_request"])

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user's current balance."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    user = db.query(User).filter(User.telegram_id == user_id).first()
    
    if user:
        await update.message.reply_text(f"የእርስዎ ሂሳብ: **{user.balance:.2f} ብር**")
    else:
        await start_command(update, context)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides referral link and info."""
    db: SessionLocal = next(get_db_session())
    user_id = update.effective_user.id
    user = db.query(User).filter(User.telegram_id == user_id).first()
    
    if user:
        bot_info = await context.bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"
        
        await update.message.reply_text(
            AMHARIC["referral_info"].format(ref_code=referral_link)
        )
    else:
        await start_command(update, context)

async def agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Info for agents."""
    await update.message.reply_text(AMHARIC["agent_info"])


# --- ADMIN HANDLERS ---
async def admin_credit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only command to manually add funds to a user's balance."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
        
    db: SessionLocal = next(get_db_session())
    
    if len(context.args) != 2:
        await update.message.reply_text("Admin: Invalid format. Use /admin_credit [user_id] [amount]")
        return
        
    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Admin: User ID must be integer, amount must be number.")
        return

    user = db.query(User).filter(User
