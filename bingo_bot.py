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
WELCOME_BONUS = 20.0 # CHANGED: Reduced from 40.0 to 20.0
REFERRAL_BONUS = 10.0
MIN_DEPOSIT = 50.0 # Minimum Deposit amount added to instruction text
MIN_WITHDRAWAL = 100.0
GAME_COST = 20.0
COMMISSION_RATE = 0.20
CALL_DELAY = 2.5
LOBBY_DURATION = 15 # Countdown in seconds

# Conversation States
DEPOSIT_RECEIPT, WITHDRAW_AMOUNT, WITHDRAW_ACCOUNT, ADMIN_MSG_USER_TEXT, ADMIN_MSG_ALL_TEXT, CARD_SELECTION_MANUAL = range(6)

# Marker constants for Interactive Card
CHECK_MARK = "✅"
CALLED_MARK = "🟢"
NEUTRAL_MARK = "⚪"
BINGO_CLAIM = "🏆 BINGO 🏆"

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
    "deposit_instr": "💳 **ገንዘብ ለማስገባት (Deposit)**\n\n1. እባክዎ ቢያንስ **`{min_dep:.2f}` ብር** ወደዚህ የቴሌብር ቁጥር ይላኩ:\n`{acc}` (Click to Copy)\n\n2. ከላኩ በኋላ ከታች ያለውን **'ገንዘብ ልኬለሁ'** የሚለውን ቁልፍ ይጫኑ።", # MIN_DEPOSIT included
    "deposit_btn": "ገንዘብ ልኬለሁ ✅", # CHANGED: Button text
    "deposit_receipt_prompt": "✅ **አሁን የደረሰኙን ፎቶ ወይም የግብይት ቁጥሩን ይላኩልኝ።**",
    "deposit_receipt_received": "✅ መረጃዎ ተልኳል! አድሚኑ እስኪያረጋግጥ ይጠብቁ።",
    "deposit_cancel": "❌ የገንዘብ ማስገባት ተሰርዟል።",
    "withdraw_ask_amt": "💸 **ገንዘብ ለማውጣት**\n\nምን ያህል ማውጣት ይፈልጋሉ? (ቢያንስ `{min_wit:.2f}` ብር)\nእባክዎ **መጠኑን ብቻ** በቁጥር ይፃፉ (ለምሳሌ: `200`)።",
    "withdraw_ask_acc": "✅ **መጠን: `{amt:.2f}` ብር**\n\nእባክዎ ገንዘቡ እንዲገባሎት የሚፈልጉትን **የቴሌብር ቁጥር** ይላኩ።",
    "withdraw_sent": "✅ **የማውጣት ጥያቄዎ ተልኳል!**\n\nመጠን: `{amt:.2f}` ብር\nቁጥር: `{acc}`\n\nአድሚኑ በቅርቡ ይልካል።",
    "withdraw_cancel": "❌ የማውጣት ጥያቄው ተሰርዟል።",
    "game_joined": "🎟 **ቢንጎ ካርድ #{card_id}**\nሒሳብዎ: `{bal:.2f}` ብር\n\nተጫዋቾችን በመጠበቅ ላይ... ({wait}s)\n\n👇 **ካርድዎን ለማየት እና ቁጥር ለመምረጥ /card ይጫኑ!**", 
    "card_selection_prompt": "👇 **ከ 1 እስከ 200 የካርድ ቁጥር ይምረጡ:**\n\n(ለመሰረዝ /cancel ይጫኑ)",
    "game_start": "🚀 **ጨዋታ ተጀመረ!**\n\n👥 ጠቅላላ ተጫዋቾች: **{count}**\nመልካም እድል!",
    "draw_announcement": "🔔 **ቁጥር: {col}-{num}**", 
    "winner": "🏆 **ቢንጎ! አሸናፊ: {name}**\n\n💰 ሽልማት: **`{prize:.2f}` ብር**\n\nቀጣይ ጨዋታ ለመጫወት `/quickplay` ይበሉ።",
    "err_bal": "⛔ **በቂ ሂሳብ የለዎትም።**\nሂሳብዎ: `{bal:.2f}` ብር\nለመጫወት `/deposit` ይጠቀሙ።",
    "err_active": "⚠️ ጨዋታው እየተካሄደ ነው።",
    "err_invalid_card": "⛔ የካርድ ቁጥር ከ 1-200 ብቻ መሆን አለበት።",
    "err_card_taken": "⛔ ይህ ካርድ ተወስዷል። ሌላ ቁጥር ይምረጡ።",
    "err_already_joined": "✅ አስቀድመው ተመዝግበዋል።",
    "err_no_game": "⛔ በአሁኑ ጊዜ ንቁ ጨዋታ ላይ የለዎትም ወይም ካርድ አልመረጡም።",
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
    card_layout = Column(String) # e.g., "1,20,0,..."
    tapped_cells = Column(String, default="") # e.g., "12,45,..." (numbers the player has marked/tapped)
    is_comp = Column(Boolean, default=False)
    name = Column(String)

def init_db():
    BASE.metadata.create_all(bind=ENGINE)

# --- 4. GAME LOGIC HELPERS ---

# ... (generate_card, get_bingo_column_letter, get_card_image_prompt, gen_comp_name are unchanged)

def check_win_tapped(layout: str, tapped: set) -> bool:
    """Checks for a win using the player's explicitly TAPPED numbers."""
    nums = [int(x) for x in layout.split(",")]
    tapped_set = tapped | {0} # Free space (0) counts if a line goes through it
    
    # 1. Check Rows
    lines = []
    for r in range(5): 
        lines.append([nums[r*5+c] for c in range(5)])
        
    # 2. Check Columns
    for c in range(5): 
        lines.append([nums[r*5+c] for r in range(5)])
        
    # 3. Check Diagonals
    lines.append([nums[i*5+i] for i in range(5)])
    lines.append([nums[i*5+(4-i)] for i in range(5)])
    
    # Check if all numbers in any line are in the tapped set
    return any(all(x in tapped_set for x in line) for line in lines)

def get_card_markup(player_card_layout: str, drawn_numbers_str: str, tapped_cells_str: str):
    """Generates a 5x5 InlineKeyboardMarkup grid for the player's card."""
    nums = [int(x) for x in player_card_layout.split(",")]
    drawn_set = set(int(x) for x in drawn_numbers_str.split(",")) if drawn_numbers_str else set()
    tapped_set = set(int(x) for x in tapped_cells_str.split(",")) if tapped_cells_str else set()

    keyboard = []
    
    # 1. Header Row
    header_row = [InlineKeyboardButton(letter, callback_data='ignore') for letter in ['B', 'I', 'N', 'G', 'O']]
    keyboard.append(header_row)

    # 2. Number Grid
    for r in range(5):
        row = []
        for c in range(5):
            num = nums[c * 5 + r] # Bingo cards are typically read column by column: B1, B2, B3, B4, B5, I1, I2...
            
            if num == 0:
                button_text = "⭐"
                callback_data = "ignore"
            elif num in tapped_set:
                # Player has tapped this number, show the final CHECK_MARK
                button_text = f"{CHECK_MARK} {num}"
                callback_data = "ignore"
            elif num in drawn_set:
                # Number called, but not yet tapped by player (show GREEN/CALLED_MARK)
                button_text = f"{CALLED_MARK} {num}"
                callback_data = f"mark_{num}" # Action: Player taps to claim this cell
            else:
                # Number not called (show NEUTRAL_MARK/WHITE)
                button_text = f"{NEUTRAL_MARK} {num}"
                callback_data = "ignore"

            row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.append(row)

    # 3. BINGO claim button
    keyboard.append([InlineKeyboardButton(BINGO_CLAIM, callback_data='claim_bingo')])
    
    return InlineKeyboardMarkup(keyboard)

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

            # RIGGED LOGIC (omitted for brevity, remains the same)
            # ...
            
            candidate = random.choice(remaining)
            drawn.append(candidate)
            game.drawn_numbers = ",".join(map(str, drawn))
            db.commit()
            
            # Announce Number with Image 
            col_letter = get_bingo_column_letter(candidate)
            message_text = AMHARIC["draw_announcement"].format(col=col_letter, num=candidate)
            
            prompt = f"Modern high-tech casino bingo drawing machine, holographic display showing the number {col_letter}-{candidate}, neon red and blue glow, cinematic background of slot machines. Title: BINGO DRAW."
            
            try:
                # Placeholder for image generation (Draw announcement image)
                await app.bot.send_photo(
                    chat_id=game.chat_id, 
                    photo="http://googleusercontent.com/image_generation_content/7", 
                    caption=message_text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending draw announcement image: {e}")
                await app.bot.send_message(game.chat_id, message_text, parse_mode="Markdown")
            
            # Since COMPs don't tap, we assume they auto-tap called numbers to check for a win
            players = db.query(GamePlayer).all()
            winner = None
            
            for p in players:
                if p.is_comp:
                    # Comp player uses traditional auto-win check 
                    if check_win(p.card_layout, drawn): # Using original check_win which doesn't rely on tapping
                        winner = p; break
                else:
                    # For Human players, check if the NEWLY DRAWN number completed a line they already TAPPED
                    tapped_set = set(int(x) for x in p.tapped_cells.split(",")) if p.tapped_cells else set()
                    
                    # If a human has a win AND they have correctly tapped all winning cells (including the latest one if relevant)
                    if check_win_tapped(p.card_layout, tapped_set):
                        # This is a passive check. The actual win claim must come from the BINGO button press.
                        # We only check for a passive win here to prevent the game from continuing indefinitely 
                        # if a human wins but forgets to press BINGO. 
                        pass # NO ACTION - The win only happens on 'claim_bingo'
            
            # The only way to win now is through the claim_bingo callback handler.
            # The engine loop will continue until a claim is validated.
            
            await asyncio.sleep(CALL_DELAY)
            
        db.close()

# ... (start_game_task remains the same)

# --- 6. USER HANDLERS ---

# ... (start, balance_command, quickplay_command, board_command remain the same)

# Helper function to process joining logic for both play and quickplay
async def process_join(update: Update, context: ContextTypes.DEFAULT_TYPE, card_choice: int):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    # Pre-checks (omitted for brevity, assume success)
    game = db.query(ActiveGame).first(); 
    if not game: game = ActiveGame(); db.add(game); db.commit()
    # ...
    
    # Join logic
    u.balance -= GAME_COST; game.pool += GAME_COST
    player_card_layout = generate_card()
    db.add(GamePlayer(user_id=u.id, card_id=card_choice, card_layout=player_card_layout, tapped_cells="", name=u.username, is_comp=False))
    db.commit()

    if game.state == "IDLE": asyncio.create_task(start_game_task(context.application, update.effective_chat.id))
    
    message_text = AMHARIC["game_joined"].format(card_id=card_choice, bal=u.balance, wait=LOBBY_DURATION)
    
    # Send only the text confirmation, the player must use /card for the visual.
    await update.message.reply_text(message_text, parse_mode="Markdown")
    
    # Automatically send the card after joining for immediate feedback
    await mycard_command(update, context, auto_send=True)
    
    db.close()

# ... (play_start, card_selection_handler, quickplay_command remain the same)

async def mycard_command(update: Update, context: ContextTypes.DEFAULT_TYPE, auto_send: bool = False):
    """Allows a player to view their current card with marked numbers and the interactive grid."""
    
    # Use update.message if manual command, or update.effective_message if auto_send
    message_source = update.message if update.message else update.effective_message 
    user = update.effective_user
    
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    game = db.query(ActiveGame).first()
    player = db.query(GamePlayer).filter_by(user_id=u.id if u else 0).first()

    if not game or not player: 
        if not auto_send:
            await message_source.reply_text(AMHARIC["err_no_game"], parse_mode="Markdown")
        db.close(); return

    drawn_numbers_str = game.drawn_numbers or ''
    
    message_text = f"--- **የእርስዎ ካርድ / Your Card (ID: {player.card_id})** ---\n"
    if game.state == "RUNNING":
        message_text += f"👆 **የካርድዎ ምስል**\n\n👇 **ቁጥሮችን ለመምረጥ ከታች ያለውን ሰሌዳ ይጠቀሙ።**"
    elif game.state == "LOBBY":
        message_text += f"👆 **የካርድዎ ምስል**\n\n⏳ ጨዋታው እስኪጀመር ድረስ ይጠብቁ..."
    
    # Send Static Card Image (Placeholder for visual aesthetic)
    card_image_prompt = get_card_image_prompt(player.card_layout, drawn_numbers_str, f"YOUR CARD {player.card_id}")
    await context.bot.send_photo(
        chat_id=message_source.chat_id,
        photo="http://googleusercontent.com/image_generation_content/9", # Placeholder for player's custom card image
        caption=f"Card {player.card_id} Visual",
        parse_mode="Markdown"
    )
    
    # Send Interactive Card Markup only if game is running
    if game.state == "RUNNING":
        markup = get_card_markup(player.card_layout, drawn_numbers_str, player.tapped_cells)
        
        # Send a new message with the interactive grid
        interactive_message = await context.bot.send_message(
            chat_id=message_source.chat_id,
            text=message_text, 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
        # Store the message ID for future editing
        context.user_data['interactive_card_msg_id'] = interactive_message.message_id
    
    db.close()

# --- 7. DEPOSIT CONVERSATION ---
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(AMHARIC["deposit_btn"], callback_data='deposit_sent')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # MIN_DEPOSIT included in the instruction text
    await update.message.reply_text(AMHARIC["deposit_instr"].format(acc=TELEBIRR_ACCOUNT, min_dep=MIN_DEPOSIT), 
                                    reply_markup=reply_markup, parse_mode="Markdown")
    return DEPOSIT_RECEIPT
    
# ... (deposit_callback_handler, deposit_receipt_handler, etc. remain the same)

# --- 8. CARD CALLBACK HANDLER (MARKING & BINGO CLAIM) ---
async def card_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; db = SessionLocal()
    await query.answer()
    
    user = query.from_user
    player = db.query(GamePlayer).filter_by(user_id=user.id).first()
    game = db.query(ActiveGame).first()

    if not player or not game or game.state != "RUNNING":
        await query.edit_message_text("⛔ ጨዋታው አሁን ንቁ አይደለም።", reply_markup=None)
        db.close(); return
        
    data = query.data
    
    if data.startswith('mark_'):
        # 1. Player Taps a CALLED number
        num_to_tap = int(data.split('_')[1])
        drawn_set = set(int(x) for x in game.drawn_numbers.split(","))
        tapped_list = [int(x) for x in player.tapped_cells.split(",")] if player.tapped_cells else []

        if num_to_tap in drawn_set and num_to_tap not in tapped_list:
            tapped_list.append(num_to_tap)
            player.tapped_cells = ",".join(map(str, tapped_list))
            db.commit()
            
            # Update the interactive grid immediately
            new_markup = get_card_markup(player.card_layout, game.drawn_numbers, player.tapped_cells)
            await query.edit_message_reply_markup(reply_markup=new_markup)
        else:
            await query.answer("⛔ ይህ ቁጥር አልወጣም ወይም አስቀድመው መርጠውታል!", show_alert=True)
        
    elif data == 'claim_bingo':
        # 2. Player Taps BINGO
        tapped_set = set(int(x) for x in player.tapped_cells.split(",")) if player.tapped_cells else set()
        
        if check_win_tapped(player.card_layout, tapped_set):
            # BINGO IS VALID! End the game.
            prize = game.pool * (1 - COMMISSION_RATE)
            u = db.query(User).filter_by(id=player.user_id).first()
            u.balance += prize
            
            await query.message.reply_text(AMHARIC["winner"].format(name=player.name, prize=prize), parse_mode="Markdown")
            
            game.state = "IDLE"; game.drawn_numbers = ""; game.pool = 0
            db.query(GamePlayer).delete(); db.commit()
            
            # Disable the interactive grid
            await query.edit_message_reply_markup(reply_markup=None)
            
        else:
            # BINGO IS INVALID!
            await query.answer(f"❌ BINGO! (Not Yet) - You are missing a line. All winning numbers must be marked.", show_alert=True)
            
    db.close()
    
# ... (All other handlers remain the same)

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
    app.add_handler(CommandHandler("card", mycard_command))
    app.add_handler(CommandHandler("mycard", mycard_command))
    
    # 2. Play Conversation (Manual Card Selection)
    # ... (play_conv_handler remains the same)
    
    # 3. Deposit Conversation
    # ... (deposit_conv_handler remains the same)
    
    # 4. Withdraw Conversation
    # ... (withdraw_conv_handler remains the same)
    
    # 5. Admin Approvals
    # ... (admin handlers remain the same)
    
    # 6. Admin Messaging - Single User/All Users
    # ... (admin msg handlers remain the same)
    
    # 7. Card Interaction Handler
    app.add_handler(CallbackQueryHandler(card_callback_handler, pattern=r'mark_|\bclaim_bingo\b'))
    
    # Start the game engine loop
    loop = asyncio.get_event_loop()
    loop.create_task(game_engine(app))
    
    logger.info("MegaBingo V7.6 LIVE (Interactive Marking & UI Refinements)...")
    app.run_polling()

if __name__ == "__main__":
    main()
