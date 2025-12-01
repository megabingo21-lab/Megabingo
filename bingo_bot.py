import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import random
import os
import asyncio
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# Set up logging for easier debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
ADMIN_CHAT_ID = 7932072571  # Must be your Telegram User ID

# Financial & Game Constants
TELEBIRR_ACCOUNT = '0997077778' 
WELCOME_BONUS = 40.0 
REFERRAL_BONUS = 10.0
MIN_DEPOSIT = 50.0
MIN_WITHDRAWAL = 100.0
GAME_COST = 20.0
COMMISSION_RATE = 0.20
CALL_DELAY = 2.5
LOBBY_DURATION = 15 # Countdown in seconds

# Conversation States
DEPOSIT_RECEIPT, WITHDRAW_AMOUNT, WITHDRAW_ACCOUNT, ADMIN_MSG_USER_TEXT, ADMIN_MSG_ALL_TEXT, CARD_SELECTION_MANUAL = range(6)

# --- RENDER KEEPALIVE SERVER ---
PORT = int(os.environ.get("PORT", 8080))

class RenderKeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MegaBingo Casino V7 is Live on Render!")

def run_server():
    server_address = ('0.0.0.0', PORT)
    httpd = HTTPServer(server_address, RenderKeepAlive)
    logger.info(f"Web Server running on port {PORT}")
    httpd.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# --- 2. LOCALIZATION (AMHARIC) ---
AMHARIC = {
    "welcome": "👋 **እንኳን ወደ ሜጋ ቢንጎ ካሲኖ በደህና መጡ!**\n\n🎁 ለጀማሪዎች የ **`{bonus:.2f}` ብር** ስጦታ ተሰጥቶዎታል።\n\nለመጫወት: `/play` ወይም `/quickplay`\nሒሳብዎ: `/balance`\nገንዘብ ለማስገባት: `/deposit`",
    "balance": "💰 **የእርስዎ ሂሳብ:** `{amount:.2f}` ብር",
    "deposit_instr": "💳 **ገንዘብ ለማስገባት (Deposit)**\n\n1. እባክዎ ወደዚህ የቴሌብር ቁጥር ይላኩ:\n`{acc}` (Click to Copy)\n\n2. ከላኩ በኋላ ከታች ያለውን **'ላክቻለሁ'** የሚለውን ቁልፍ ይጫኑ።",
    "deposit_btn": "ላክቻለሁ ✅",
    "deposit_receipt_prompt": "✅ **አሁን የደረሰኙን ፎቶ ወይም የግብይት ቁጥሩን ይላኩልኝ።**",
    "deposit_receipt_received": "✅ መረጃዎ ተልኳል! አድሚኑ እስኪያረጋግጥ ይጠብቁ።",
    "deposit_cancel": "❌ የገንዘብ ማስገባት ተሰርዟል።",
    "withdraw_ask_amt": "💸 **ገንዘብ ለማውጣት**\n\nምን ያህል ማውጣት ይፈልጋሉ? (ቢያንስ `{min_wit:.2f}` ብር)\nእባክዎ **መጠኑን ብቻ** በቁጥር ይፃፉ (ለምሳሌ: `200`)።",
    "withdraw_ask_acc": "✅ **መጠን: `{amt:.2f}` ብር**\n\nእባክዎ ገንዘቡ እንዲገባሎት የሚፈልጉትን **የቴሌብር ቁጥር** ይላኩ።",
    "withdraw_sent": "✅ **የማውጣት ጥያቄዎ ተልኳል!**\n\nመጠን: `{amt:.2f}` ብር\nቁጥር: `{acc}`\n\nአድሚኑ በቅርቡ ይልካል።",
    "withdraw_cancel": "❌ የማውጣት ጥያቄው ተሰርዟል።",
    "game_joined": "🎟 **ቢንጎ ካርድ #{card_id}**\nሒሳብዎ: `{bal:.2f}` ብር\n\nተጫዋቾችን በመጠበቅ ላይ... ({wait}s)", 
    "card_selection_prompt": "👇 **ከ 1 እስከ 200 የካርድ ቁጥር ይምረጡ:**\n\n(ለመሰረዝ /cancel ይጫኑ)",
    "game_start": "🚀 **ጨዋታ ተጀመረ!**\n\n👥 ጠቅላላ ተጫዋቾች: **{count}**\nመልካም እድል!",
    "draw_announcement": "🔔 **ቁጥር: {col}-{num}**", 
    "winner": "🏆 **ቢንጎ! አሸናፊ: {name}**\n\n💰 ሽልማት: **`{prize:.2f}` ብር**\n\nቀጣይ ጨዋታ ለመጫወት `/quickplay` ይበሉ።",
    "err_bal": "⛔ **በቂ ሂሳብ የለዎትም።**\nሂሳብዎ: `{bal:.2f}` ብር\nለመጫወት `/deposit` ይጠቀሙ።",
    "err_active": "⚠️ ጨዋታው እየተካሄደ ነው።",
    "err_invalid_card": "⛔ የካርድ ቁጥር ከ 1-200 ብቻ መሆን አለበት።",
    "err_card_taken": "⛔ ይህ ካርድ ተወስዷል። ሌላ ቁጥር ይምረጡ።",
    "err_already_joined": "✅ አስቀድመው ተመዝግበዋል።",
    "err_no_game": "⛔ በአሁኑ ጊዜ ንቁ ጨዋታ ላይ የለዎትም።",
    "dep_confirmed_user": "✅ **ገንዘብዎ ገብቷል!**\n\nየተሞላው ሂሳብ: **`{amt:.2f}` ብር**\nጠቅላላ ሂሳብዎ: **`{bal:.2f}` ብር**\n\nለመጫወት `/quickplay` ይላኩ።",
    "wit_confirmed_user": "✅ **ገንዘብዎ ተልኳል!**\n\nየወጣው ሂሳብ: **`{amt:.2f}` ብር**\nጠቅላላ ሂሳብዎ: **`{bal:.2f}` ብር**\n\nመልካም ቀን!",
    "ref_bonus_user": "🎉 **የሪፈራል ሽልማት!**\n\nጓደኛዎ የመጀመሪያ ገንዘብ በማስገባቱ **`{amt:.2f}` ብር** አግኝተዋል!",
    "admin_new_dep_alert": "🚨 **አዲስ ማስገቢያ (Deposit) ጥያቄ**\n\nተጠቃሚ ID: `{uid}`\nየተጠቃሚ ስም: @{uname}\n\n👇 **ደረሰኙን ከታች ይመልከቱ** 👇\n\nለማጽደቅ: `/admin_approve_deposit {uid} {min_dep:.2f}` [amount you manually verified]",
    "admin_new_wit_alert": "🚨 **አዲስ የማውጣት (Withdraw) ጥያቄ**\n\nተጠቃሚ ID: `{uid}`\nየተጠቃሚ ስም: @{uname}\nመጠን: `{amt:.2f}` ብር\nቴሌብር ቁጥር: `{acc}`\n\nገንዘብ ከላኩ በኋላ: `/admin_confirm_withdrawal {uid} {amt:.2f}`",
    "admin_dep_approved_admin": "✅ የ `{uid}` የ `{amt:.2f}` ብር ማስገቢያ ጸድቋል።",
    "admin_wit_confirmed_admin": "✅ የ `{uid}` የ `{amt:.2f}` ብር የማውጣት ጥያቄ ተረጋግጧል።",
    "admin_msg_prompt_user": "መልዕክት የሚልኩለትን **የተጠቃሚ ID** ይላኩ።",
    "admin_msg_prompt_all": "ለሁሉም ተጠቃሚዎች የሚልኩትን **መልዕክት** ይፃፉ።",
    "admin_msg_sent_single": "✅ መልዕክት ለ `{uid}` ተልኳል።",
    "admin_msg_sent_all": "✅ መልዕክት ለሁሉም ተጠቃሚዎች ተልኳል።",
    "admin_msg_cancel": "❌ የመልዕክት መላክ ተሰርዟል።",
}

# --- 3. DATABASE ---
BASE = declarative_base()
ENGINE = create_engine('sqlite:///megabingo_v7.db') 
SessionLocal = sessionmaker(bind=ENGINE)

class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    balance = Column(Float, default=0.0)
    referrer_id = Column(Integer, nullable=True) 
    has_deposited = Column(Boolean, default=False) 

class ActiveGame(BASE):
    __tablename__ = 'active_game'
    id = Column(Integer, primary_key=True)
    state = Column(String, default="IDLE")
    drawn_numbers = Column(String, default="")
    pool = Column(Float, default=0.0)
    chat_id = Column(Integer, default=0)

class GamePlayer(BASE):
    __tablename__ = 'game_players'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    card_id = Column(Integer, default=0) 
    card_layout = Column(String)
    is_comp = Column(Boolean, default=False)
    name = Column(String)

def init_db():
    BASE.metadata.create_all(bind=ENGINE)

# --- 4. GAME LOGIC HELPERS ---
def generate_card():
    cols = [
        random.sample(range(1, 16), 5), random.sample(range(16, 31), 5),
        random.sample(range(31, 46), 4), random.sample(range(46, 61), 5),
        random.sample(range(61, 76), 5)
    ]
    cols[2].insert(2, 0)
    flat = []
    for r in range(5):
        for c in range(5): flat.append(cols[c][r])
    return ",".join(map(str, flat))

def check_win(layout, drawn):
    nums = [int(x) for x in layout.split(",")]
    d_set = set(drawn) | {0} 
    lines = []
    for r in range(5): lines.append([nums[r*5+c] for c in range(5)])
    for c in range(5): lines.append([nums[r*5+c] for r in range(5)])
    lines.append([nums[i*5+i] for i in range(5)])
    lines.append([nums[i*5+(4-i)] for i in range(5)])
    return any(all(x in d_set for x in line) for line in lines)

def gen_comp_name():
    male_names = ["Kidus", "Yonas", "Abel", "Dawit", "Elias", "Natnael", "Bereket", "Robel", "Samson", "Tewodros", "Michael"]
    female_names = ["Hana", "Lidiya", "Marta", "Helen"] 
    is_male = random.random() < 0.95 
    base_name = random.choice(male_names if is_male else female_names)
    emojis_and_numbers = ["77", "_ET", "🇪🇹", "🦁", "🔥", "10", "22", "88", "🌟", "👑"]
    suffix = random.choice(emojis_and_numbers)
    return f"{base_name}{suffix}"

def get_bingo_column_letter(number: int) -> str:
    if 1 <= number <= 15: return 'B'
    elif 16 <= number <= 30: return 'I'
    elif 31 <= number <= 45: return 'N'
    elif 46 <= number <= 60: return 'G'
    else: return 'O'

def get_card_image_prompt(layout: str, drawn: str, title: str) -> str:
    """Generates a detailed image prompt for the bingo board with drawn numbers marked."""
    
    nums = [int(x) for x in layout.split(",")]
    drawn_list = [int(x) for x in drawn.split(",")] if drawn else []
    
    columns = {'B': [], 'I': [], 'N': [], 'G': [], 'O': []}
    
    for i in range(5): # Row index (0-4)
        for j, col_letter in enumerate(['B', 'I', 'N', 'G', 'O']): # Column index (0-4)
            num = nums[j * 5 + i] 
            
            status = 'X' if num in drawn_list else ('F' if num == 0 else str(num))
            
            columns[col_letter].append(f"{status}")

    layout_description = " | ".join([f"{col}:{', '.join(col_nums)}" for col, col_nums in columns.items()])
    
    return (
        f"High-tech, modern casino bingo card, 5x5 grid with BINGO header. Title: '{title}'. "
        f"Show numbers glowing neon. MARKED numbers should be replaced by a glowing 'X' (or 'F' for 0). "
        f"The card layout is (B|I|N|G|O): {layout_description}. Futuristic, cinematic lighting. Emphasize the marked 'X's."
    )

# --- 5. GAME ENGINE ---

async def game_engine(app: Application):
    while True:
        await asyncio.sleep(1)
        db = SessionLocal()
        game = db.query(ActiveGame).first()
        
        if not game: game = ActiveGame(); db.add(game); db.commit(); db.close(); continue
            
        if game.state == "RUNNING":
            drawn = [int(x) for x in game.drawn_numbers.split(",")] if game.drawn_numbers else []
            remaining = [x for x in range(1, 76) if x not in drawn]
            
            if not remaining: game.state = "IDLE"; db.commit(); db.close(); continue

            # RIGGED LOGIC 
            candidate = random.choice(remaining)
            humans = db.query(GamePlayer).filter(GamePlayer.is_comp == False).all()
            human_is_about_to_win = any(check_win(p.card_layout, drawn + [candidate]) for p in humans)
            comp_count = db.query(GamePlayer).filter(GamePlayer.is_comp == True).count()
            
            if human_is_about_to_win and comp_count > 0:
                for _ in range(5):
                    new_candidate = random.choice(remaining)
                    if not any(check_win(p.card_layout, drawn + [new_candidate]) for p in humans):
                        candidate = new_candidate
                        break

            drawn.append(candidate)
            game.drawn_numbers = ",".join(map(str, drawn))
            db.commit()
            
            # Announce Number with Image 
            col_letter = get_bingo_column_letter(candidate)
            message_text = AMHARIC["draw_announcement"].format(col=col_letter, num=candidate)
            
            prompt = f"Modern high-tech casino bingo drawing machine, holographic display showing the number {col_letter}-{candidate}, neon red and blue glow, cinematic background of slot machines. Title: BINGO DRAW."
            
            try:
                # Placeholder for image generation
                await app.bot.send_photo(
                    chat_id=game.chat_id, 
                    photo="http://googleusercontent.com/image_generation_content/7", 
                    caption=message_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending draw announcement image: {e}")
                await app.bot.send_message(game.chat_id, message_text, parse_mode="Markdown")
            
            # Check Winners 
            players = db.query(GamePlayer).all()
            winner = None
            for p in players:
                if check_win(p.card_layout, drawn):
                    winner = p; break
            
            if winner:
                prize = game.pool * (1 - COMMISSION_RATE)
                if not winner.is_comp:
                    u = db.query(User).filter_by(id=winner.user_id).first()
                    u.balance += prize
                
                try:
                    await app.bot.send_message(game.chat_id, AMHARIC["winner"].format(name=winner.name, prize=prize), parse_mode="Markdown")
                except: pass
                
                game.state = "IDLE"; game.drawn_numbers = ""; game.pool = 0
                db.query(GamePlayer).delete(); db.commit()
            
            await asyncio.sleep(CALL_DELAY)
            
        db.close()

async def start_game_task(app, chat_id):
    db = SessionLocal()
    game = db.query(ActiveGame).first()
    if game.state == "IDLE":
        game.state = "LOBBY"; game.chat_id = chat_id; db.commit()

        # Lobby Countdown: Send initial message and then edit it
        status_message = await app.bot.send_message(game.chat_id, f"⏳ ጨዋታ በ {LOBBY_DURATION} ሰከንድ ውስጥ ይጀምራል...")
        
        for i in range(LOBBY_DURATION, 0, -1): 
            await asyncio.sleep(1)
            db.refresh(game); 
            if game.state != "LOBBY": db.close(); return # Check if game was canceled
            try: 
                # Edit the message with the remaining time
                await status_message.edit_text(f"⏳ ጨዋታ በ {i-1} ሰከንድ ውስጥ ይጀምራል...")
            except: 
                pass 
        
        # If still in lobby, start the game logic
        if game.state == "LOBBY":
            real_count = db.query(GamePlayer).filter(GamePlayer.is_comp == False).count()
            if real_count <= 20: 
                # Add COMP players to fill the game
                needed_comps = random.randint(20, 49) 
                taken_card_ids = {p.card_id for p in db.query(GamePlayer).all()}
                
                for i in range(needed_comps):
                    comp_card_id = random.randint(300, 999) + i
                    while comp_card_id in taken_card_ids: comp_card_id = random.randint(1000, 2000)
                    taken_card_ids.add(comp_card_id)
                    
                    db.add(GamePlayer(user_id=-random.randint(100000,999999), 
                                      is_comp=True, name=gen_comp_name(), card_layout=generate_card(), card_id=comp_card_id))
                    game.pool += GAME_COST
            
            total_players = db.query(GamePlayer).count()
            game.state = "RUNNING"
            db.commit()
            
            try:
                await app.bot.send_message(game.chat_id, AMHARIC["game_start"].format(count=total_players), parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error sending game start message: {e}")
    db.close()

# --- 6. USER HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; db = SessionLocal(); u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u:
        ref_id = None
        if context.args:
            try:
                ref_candidate = int(context.args[0])
                if ref_candidate != user.id and db.query(User).filter_by(telegram_id=ref_candidate).first():
                    ref_id = ref_candidate
            except: pass
            
        u = User(telegram_id=user.id, username=user.username, balance=WELCOME_BONUS, referrer_id=ref_id)
        db.add(u); db.commit()
    
    await update.message.reply_text(AMHARIC["welcome"].format(bonus=WELCOME_BONUS), parse_mode="Markdown")
    db.close()

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u:
        u = User(telegram_id=user.id, username=user.username, balance=WELCOME_BONUS)
        db.add(u)
        db.commit()
    
    balance_amount = u.balance 
    await update.message.reply_text(AMHARIC["balance"].format(amount=balance_amount), parse_mode="Markdown")
    db.close()

# Helper function to process joining logic for both play and quickplay
async def process_join(update: Update, context: ContextTypes.DEFAULT_TYPE, card_choice: int):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    # Pre-checks
    game = db.query(ActiveGame).first(); 
    if not game: game = ActiveGame(); db.add(game); db.commit()
    
    if u.balance < GAME_COST: 
        await update.message.reply_text(AMHARIC["err_bal"].format(bal=u.balance), parse_mode="Markdown"); db.close(); return
    if game.state == "RUNNING": 
        await update.message.reply_text(AMHARIC["err_active"], parse_mode="Markdown"); db.close(); return
    if db.query(GamePlayer).filter_by(user_id=u.id).first(): 
        await update.message.reply_text(AMHARIC["err_already_joined"], parse_mode="Markdown"); db.close(); return
    if db.query(GamePlayer).filter_by(card_id=card_choice).first():
        await update.message.reply_text(AMHARIC["err_card_taken"], parse_mode="Markdown"); db.close(); return

    # Join logic
    u.balance -= GAME_COST; game.pool += GAME_COST
    player_card_layout = generate_card()
    db.add(GamePlayer(user_id=u.id, card_id=card_choice, card_layout=player_card_layout, name=u.username, is_comp=False))
    db.commit()

    if game.state == "IDLE": asyncio.create_task(start_game_task(context.application, update.effective_chat.id))
    
    message_text = AMHARIC["game_joined"].format(card_id=card_choice, bal=u.balance, wait=LOBBY_DURATION)
    drawn_numbers_str = game.drawn_numbers or ''
    
    # Display the card image immediately
    card_image_prompt = get_card_image_prompt(player_card_layout, drawn_numbers_str, f"YOUR CARD {card_choice}")

    await update.message.reply_photo(
        photo="http://googleusercontent.com/image_generation_content/8", 
        caption=message_text,
        parse_mode="Markdown"
    )
    db.close()

# --- Manual Card Selection Conversation (/play) ---
async def play_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u or u.balance < GAME_COST: 
        await update.message.reply_text(AMHARIC["err_bal"].format(bal=u.balance if u else 0.0), parse_mode="Markdown"); db.close(); return ConversationHandler.END
        
    game = db.query(ActiveGame).first()
    if not game: game = ActiveGame(); db.add(game); db.commit()
    
    if game.state == "RUNNING":
        await update.message.reply_text(AMHARIC["err_active"], parse_mode="Markdown"); db.close(); return ConversationHandler.END
    if db.query(GamePlayer).filter_by(user_id=u.id).first():
        await update.message.reply_text(AMHARIC["err_already_joined"], parse_mode="Markdown"); db.close(); return ConversationHandler.END
    
    await update.message.reply_text(AMHARIC["card_selection_prompt"], parse_mode="Markdown")
    db.close()
    return CARD_SELECTION_MANUAL

async def card_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        card_choice = int(update.message.text)
        if not (1 <= card_choice <= 200):
            await update.message.reply_text(AMHARIC["err_invalid_card"], parse_mode="Markdown")
            return CARD_SELECTION_MANUAL
            
        # Call the common join logic
        await process_join(update, context, card_choice)
        
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("⛔ እባክዎ ትክክለኛ የካርድ ቁጥር በቁጥር ያስገቡ (1-200)።", parse_mode="Markdown")
        return CARD_SELECTION_MANUAL

# --- Automatic Card Selection Handler (/quickplay) ---
async def quickplay_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    
    # Find an available card ID (1-200)
    taken_card_ids = {p.card_id for p in db.query(GamePlayer).filter(GamePlayer.card_id <= 200).all()}
    available_ids = [i for i in range(1, 201) if i not in taken_card_ids]
    
    if not available_ids: 
        # Emergency assignment if all 200 are somehow taken
        card_choice = random.randint(1, 200) 
    else: 
        card_choice = random.choice(available_ids)

    db.close()
    
    # Process the join
    await process_join(update, context, card_choice)
    return

async def board_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal(); game = db.query(ActiveGame).first()
    
    if not game or not game.drawn_numbers: await update.message.reply_text("⛔ ምንም ቁጥሮች ገና አልወጡም።", parse_mode="Markdown"); db.close(); return

    drawn = [int(x) for x in game.drawn_numbers.split(",")]
    drawn.sort()
    
    output = f"--- **የወጡ ቁጥሮች ({len(drawn)} ጠቅላላ)** ---\n"
    output += f"```\n{', '.join(map(str, drawn))}\n```"

    await update.message.reply_text(output, parse_mode="Markdown")
    db.close()

# --- 7. DEPOSIT CONVERSATION ---
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(AMHARIC["deposit_btn"], callback_data='deposit_sent')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(AMHARIC["deposit_instr"].format(acc=TELEBIRR_ACCOUNT), 
                                    reply_markup=reply_markup, parse_mode="Markdown")
    return DEPOSIT_RECEIPT

async def deposit_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'deposit_sent':
        await query.message.reply_text(AMHARIC["deposit_receipt_prompt"], parse_mode="Markdown")
        return DEPOSIT_RECEIPT

async def deposit_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if update.message.photo or (update.message.text and not update.message.text.startswith('/')):
        alert_msg = AMHARIC["admin_new_dep_alert"].format(uid=user.id, uname=user.username or user.first_name, min_dep=MIN_DEPOSIT)
        await context.bot.send_message(ADMIN_CHAT_ID, alert_msg, parse_mode="Markdown")
        
        await context.bot.forward_message(ADMIN_CHAT_ID, update.effective_chat.id, update.message.id)
        
        await update.message.reply_text(AMHARIC["deposit_receipt_received"], parse_mode="Markdown")
        return ConversationHandler.END
    
    if update.message.text and update.message.text.startswith('/'):
        return ConversationHandler.END
    
    await update.message.reply_text("⛔ እባክዎ የደረሰኙን ፎቶ ወይም የግብይት ቁጥሩን ብቻ ይላኩ።")
    return DEPOSIT_RECEIPT

# --- 8. WITHDRAW CONVERSATION ---
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; db = SessionLocal(); u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u or u.balance < MIN_WITHDRAWAL:
        await update.message.reply_text(AMHARIC["err_bal"].format(bal=u.balance if u else 0.0), parse_mode="Markdown"); db.close(); return ConversationHandler.END
        
    context.user_data['user_balance'] = u.balance
    await update.message.reply_text(AMHARIC["withdraw_ask_amt"].format(min_wit=MIN_WITHDRAWAL), parse_mode="Markdown")
    db.close()
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text)
        current_balance = context.user_data.get('user_balance', 0.0)
        
        if amt < MIN_WITHDRAWAL:
            await update.message.reply_text(f"⛔ አነስተኛ ማውጣት `{MIN_WITHDRAWAL:.2f}` ብር ነው። እንደገና ይፃፉ።", parse_mode="Markdown")
            return WITHDRAW_AMOUNT
        
        if amt > current_balance:
            await update.message.reply_text(f"⛔ በቂ ሂሳብ የለዎትም። ከፍተኛው ማውጣት `{current_balance:.2f}` ብር ነው።", parse_mode="Markdown")
            return WITHDRAW_AMOUNT
            
        context.user_data['w_amt'] = amt
        await update.message.reply_text(AMHARIC["withdraw_ask_acc"].format(amt=amt), parse_mode="Markdown")
        return WITHDRAW_ACCOUNT
    except ValueError:
        await update.message.reply_text("⛔ ቁጥር ብቻ ያስገቡ (ምሳሌ: 200)")
        return WITHDRAW_AMOUNT

async def withdraw_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc = update.message.text
    amt = context.user_data['w_amt']
    user = update.effective_user
    
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if u and u.balance >= amt:
        u.balance -= amt
        db.commit()
        
        alert_msg = AMHARIC["admin_new_wit_alert"].format(uid=user.id, uname=user.username or user.first_name, amt=amt, acc=acc)
        await context.bot.send_message(ADMIN_CHAT_ID, alert_msg, parse_mode="Markdown")
        
        await update.message.reply_text(AMHARIC["withdraw_sent"].format(amt=amt, acc=acc), parse_mode="Markdown")
    else:
        await update.message.reply_text("⛔ ገንዘብዎ በሂደት ተቀንሷል። እባክዎ እንደገና ይሞክሩ።", parse_mode="Markdown")
    
    db.close()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["admin_msg_cancel"], parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

# --- 9. ADMIN COMMANDS ---
async def check_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_CHAT_ID

async def admin_approve_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    if len(context.args) < 2:
        await update.message.reply_text("Use: `/admin_approve_deposit [ID] [Amount]` (e.g., /admin_approve_deposit 123456 50.00)")
        return
    
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        db = SessionLocal()
        u = db.query(User).filter_by(telegram_id=uid).first()
        
        if u:
            is_first_deposit = not u.has_deposited
            
            u.balance += amt
            u.has_deposited = True
            
            if is_first_deposit and u.referrer_id:
                ref = db.query(User).filter_by(telegram_id=u.referrer_id).first()
                if ref:
                    ref.balance += REFERRAL_BONUS
                    await context.bot.send_message(ref.telegram_id, AMHARIC["ref_bonus_user"].format(amt=REFERRAL_BONUS), parse_mode="Markdown")
            
            db.commit()
            
            await context.bot.send_message(uid, AMHARIC["dep_confirmed_user"].format(amt=amt, bal=u.balance), parse_mode="Markdown")
            
            await update.message.reply_text(AMHARIC["admin_dep_approved_admin"].format(uid=uid, amt=amt), parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⛔ User ID {uid} not found in DB.")
        db.close()
    except Exception as e:
        logger.error(f"Admin credit error: {e}")
        await update.message.reply_text(f"⛔ Invalid format or error: {e}")

async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    if len(context.args) < 2:
        await update.message.reply_text("Use: `/admin_confirm_withdrawal [ID] [Amount]` (e.g., /admin_confirm_withdrawal 123456 100.00)")
        return
    
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        db = SessionLocal()
        u = db.query(User).filter_by(telegram_id=uid).first()
        
        if u:
            await context.bot.send_message(uid, AMHARIC["wit_confirmed_user"].format(amt=amt, bal=u.balance), parse_mode="Markdown")
            
            await update.message.reply_text(AMHARIC["admin_wit_confirmed_admin"].format(uid=uid, amt=amt), parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⛔ User ID {uid} not found in DB.")
        db.close()
    except Exception as e:
        logger.error(f"Admin withdraw confirm error: {e}")
        await update.message.reply_text(f"⛔ Invalid format or error: {e}")

# --- 10. ADMIN MESSAGING ---
async def admin_msg_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    await update.message.reply_text(AMHARIC["admin_msg_prompt_user"], parse_mode="Markdown")
    return ADMIN_MSG_USER_TEXT

async def admin_msg_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    
    user_input = update.message.text
    if 'target_uid' not in context.user_data:
        try:
            target_uid = int(user_input)
            context.user_data['target_uid'] = target_uid
            await update.message.reply_text("መልዕክትዎን አሁን ይፃፉ:", parse_mode="Markdown")
            return ADMIN_MSG_USER_TEXT
        except ValueError:
            await update.message.reply_text("⛔ ትክክለኛ የተጠቃሚ ID ብቻ ያስገቡ።", parse_mode="Markdown")
            return ADMIN_MSG_USER_TEXT
    else:
        target_uid = context.user_data['target_uid']
        message = user_input
        
        try:
            await context.bot.send_message(target_uid, f"📢 **ከአድሚን የተላከ መልዕክት:**\n\n{message}", parse_mode="Markdown")
            await update.message.reply_text(AMHARIC["admin_msg_sent_single"].format(uid=target_uid), parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"⛔ መልዕክቱን መላክ አልተቻለም (ID {target_uid} ቦቱን አግዶ ሊሆን ይችላል።). Error: {e}")
        
        context.user_data.clear()
        return ConversationHandler.END

async def admin_msg_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    await update.message.reply_text(AMHARIC["admin_msg_prompt_all"], parse_mode="Markdown")
    return ADMIN_MSG_ALL_TEXT

async def admin_msg_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    message = update.message.text
    db = SessionLocal()
    users = db.query(User).all()
    db.close()
    
    sent_count = 0
    
    tasks = []
    for u in users:
        tasks.append(context.bot.send_message(u.telegram_id, f"📢 **አስቸኳይ መልዕክት (Announcement):**\n\n{message}", parse_mode="Markdown"))
        sent_count += 1
        
    await asyncio.gather(*tasks, return_exceptions=True)
    
    await update.message.reply_text(AMHARIC["admin_msg_sent_all"] + f" (Total attempted: {sent_count})", parse_mode="Markdown")
    return ConversationHandler.END

# --- MAIN ---
def main():
    if not BOT_TOKEN: logger.error("TELEGRAM_BOT_TOKEN environment variable not set."); return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # 1. Main Game/Info Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("quickplay", quickplay_command))
    app.add_handler(CommandHandler("board", board_command))
    
    # 2. Play Conversation (Manual Card Selection)
    play_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("play", play_start)],
        states={
            CARD_SELECTION_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, card_selection_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(play_conv_handler)
    
    # 3. Deposit Conversation
    deposit_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("deposit", deposit_start)],
        states={
            DEPOSIT_RECEIPT: [
                CallbackQueryHandler(deposit_callback_handler),
                MessageHandler(filters.PHOTO | filters.TEXT, deposit_receipt_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(deposit_conv_handler)
    
    # 4. Withdraw Conversation
    withdraw_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(withdraw_conv_handler)
    
    # 5. Admin Approvals
    app.add_handler(CommandHandler("admin_approve_deposit", admin_approve_deposit))
    app.add_handler(CommandHandler("admin_confirm_withdrawal", admin_confirm_withdrawal))
    
    # 6. Admin Messaging - Single User
    msg_user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin_msg_user", admin_msg_user_start)],
        states={
            ADMIN_MSG_USER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_user_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(msg_user_conv_handler)
    
    # 7. Admin Messaging - All Users
    msg_all_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin_msg_all", admin_msg_all_start)],
        states={
            ADMIN_MSG_ALL_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_all_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(msg_all_conv_handler)
    
    # Start the game engine loop
    loop = asyncio.get_event_loop()
    loop.create_task(game_engine(app))
    
    logger.info("MegaBingo V7.4 LIVE (Streamlined Play)...")
    app.run_polling()

if __name__ == "__main__":
    main()
