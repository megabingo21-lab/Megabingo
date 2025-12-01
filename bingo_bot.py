import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import random
import os
import asyncio
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float
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
LOBBY_DURATION = 15 

# Conversation States
DEPOSIT_RECEIPT, WITHDRAW_AMOUNT, WITHDRAW_ACCOUNT, ADMIN_MSG_USER_TEXT, ADMIN_MSG_ALL_TEXT = range(5)

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
    
    # 1. Map BINGO letters to columns and collect numbers
    nums = [int(x) for x in layout.split(",")]
    drawn_list = [int(x) for x in drawn.split(",")] if drawn else []
    
    columns = {'B': [], 'I': [], 'N': [], 'G': [], 'O': []}
    
    # Iterate through the card layout based on the 5x5 grid position
    for i in range(5): # Row index (0-4)
        for j, col_letter in enumerate(['B', 'I', 'N', 'G', 'O']): # Column index (0-4)
            num = nums[j * 5 + i] # This accesses the number based on the column-major storage format
            
            # Use 'X' for marked, 'F' for Free Space (0), or the number itself
            status = 'X' if num in drawn_list else ('F' if num == 0 else str(num))
            
            columns[col_letter].append(f"{status}")

    # Create a compact, descriptive layout for the image generator
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

            # RIGGED LOGIC (Same as V7.1)
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
            
            # Announce Number with Image (Same as V7.1)
            col_letter = get_bingo_column_letter(candidate)
            message_text = AMHARIC["draw_announcement"].format(col=col_letter, num=candidate)
            
            prompt = f"Modern high-tech casino bingo drawing machine, holographic display showing the number {col_letter}-{candidate}, neon red and blue glow, cinematic background of slot machines. Title: BINGO DRAW."
            
            try:
                await app.bot.send_photo(
                    chat_id=game.chat_id, 
                    photo="http://googleusercontent.com/image_generation_content/7", 
                    caption=message_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending draw announcement image: {e}")
                await app.bot.send_message(game.chat_id, message_text, parse_mode="Markdown")
            
            # Check Winners (Same as V7.1)
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

        for i in range(LOBBY_DURATION, 0, -1): 
            try: await app.bot.send_message(game.chat_id, f"⏳ ጨዋታ በ {i} ሰከንድ ውስጥ ይጀምራል...")
            except: pass
            await asyncio.sleep(1)
            db.refresh(game); 
        if game.state != "LOBBY": db.close(); return

        if game.state == "LOBBY":
            real_count = db.query(GamePlayer).filter(GamePlayer.is_comp == False).count()
            if real_count <= 20: 
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

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u: 
        u = User(telegram_id=user.id, username=user.username, balance=WELCOME_BONUS)
        db.add(u)
        db.commit()

    is_quick_play = update.message.text.startswith("/quick")
    card_choice = 0

    if not is_quick_play:
        if not context.args: await update.message.reply_text("⛔ እባክዎ ከ 1-200 የካርድ ቁጥር ይምረጡ: `/play 55`", parse_mode="Markdown"); db.close(); return
        try: card_choice = int(context.args[0]); 
        except: await update.message.reply_text(AMHARIC["err_invalid_card"], parse_mode="Markdown"); db.close(); return
        if not (1 <= card_choice <= 200): await update.message.reply_text(AMHARIC["err_invalid_card"], parse_mode="Markdown"); db.close(); return
        card_taken = db.query(GamePlayer).filter_by(card_id=card_choice).first()
        if card_taken: await update.message.reply_text(AMHARIC["err_card_taken"], parse_mode="Markdown"); db.close(); return
    else:
        taken_card_ids = {p.card_id for p in db.query(GamePlayer).filter(GamePlayer.card_id <= 200).all()}
        available_ids = [i for i in range(1, 201) if i not in taken_card_ids]
        if not available_ids: card_choice = random.randint(1, 200) 
        else: card_choice = random.choice(available_ids)

    if u.balance < GAME_COST: await update.message.reply_text(AMHARIC["err_bal"].format(bal=u.balance), parse_mode="Markdown"); db.close(); return
    game = db.query(ActiveGame).first(); 
    if not game: game = ActiveGame(); db.add(game); db.commit()
    if game.state == "RUNNING": await update.message.reply_text(AMHARIC["err_active"], parse_mode="Markdown"); db.close(); return
    if db.query(GamePlayer).filter_by(user_id=u.id).first(): await update.message.reply_text(AMHARIC["err_already_joined"], parse_mode="Markdown"); db.close(); return

    u.balance -= GAME_COST; game.pool += GAME_COST
    player_card_layout = generate_card()
    db.add(GamePlayer(user_id=u.id, card_id=card_choice, card_layout=player_card_layout, name=u.username, is_comp=False))
    db.commit()

    if game.state == "IDLE": asyncio.create_task(start_game_task(context.application, update.effective_chat.id))
    
    message_text = AMHARIC["game_joined"].format(card_id=card_choice, bal=u.balance, wait=LOBBY_DURATION)
    drawn_numbers_str = game.drawn_numbers or ''
    # Use the ENHANCED prompt function here
    card_image_prompt = get_card_image_prompt(player_card_layout, drawn_numbers_str, f"YOUR CARD {card_choice}")

    await update.message.reply_photo(
        photo="http://googleusercontent.com/image_generation_content/8", 
        caption=message_text,
        parse_mode="Markdown"
    )
    db.close()

async def mycard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; db = SessionLocal()
    game = db.query(ActiveGame).first()
    player = db.query(GamePlayer).filter_by(user_id=user.id).first()

    if not game or not player: await update.message.reply_text(AMHARIC["err_no_game"], parse_mode="Markdown"); db.close(); return

    drawn_numbers_str = game.drawn_numbers or ''
    
    message_text = f"--- **የእርስዎ ካርድ / Your Card (ID: {player.card_id})** ---\n"
    if game.state == "RUNNING":
        message_text += f"ጨዋታ: **በሂደት ላይ** | የወጡ ቁጥሮች: **{len(drawn_numbers_str.split(',')) if drawn_numbers_str else 0}**"
    else:
        message_text += f"ጨዋታ: **በመጠባበቅ ላይ**"
    
    # Use the ENHANCED prompt function here
    card_image_prompt = get_card_image_prompt(player.card_layout, drawn_numbers_str, f"YOUR CARD {player.card_id}")
    
    await update.message.reply_photo(
        photo="http://googleusercontent.com/image_generation_content/9", 
        caption=message_text,
        parse_mode="Markdown"
    )
    db.close()

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
# (Omitted for brevity, unchanged)

# --- 8. WITHDRAW CONVERSATION ---
# (Omitted for brevity, unchanged)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["admin_msg_cancel"], parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

# --- 9. ADMIN COMMANDS ---
# (Omitted for brevity, unchanged)

# --- 10. ADMIN MESSAGING ---
# (Omitted for brevity, unchanged)

# --- MAIN ---
def main():
    if not BOT_TOKEN: logger.error("TELEGRAM_BOT_TOKEN environment variable not set."); return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # 1. Main Game/Info Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("quickplay", play_command))
    app.add_handler(CommandHandler("mycard", mycard_command))
    app.add_handler(CommandHandler("card", mycard_command)) # ADDED ALIAS
    app.add_handler(CommandHandler("board", board_command))
    
    # 2. Deposit Conversation
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
    
    # 3. Withdraw Conversation
    withdraw_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(withdraw_conv_handler)
    
    # 4. Admin Approvals
    app.add_handler(CommandHandler("admin_approve_deposit", admin_approve_deposit))
    app.add_handler(CommandHandler("admin_confirm_withdrawal", admin_confirm_withdrawal))
    
    # 5. Admin Messaging - Single User
    msg_user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin_msg_user", admin_msg_user_start)],
        states={
            ADMIN_MSG_USER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_msg_user_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(msg_user_conv_handler)
    
    # 6. Admin Messaging - All Users
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
    
    logger.info("MegaBingo V7.2 LIVE (Visual Card Update)...")
    app.run_polling()

if __name__ == "__main__":
    main()
