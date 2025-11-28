import telegram
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import random
import os
import logging
import asyncio
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float, select
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

# --- 1. CONFIGURATION ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
# YOUR ADMIN ID
ADMIN_CHAT_ID = 7932072571

# Financial & Game Constants
MIN_DEPOSIT = 50.0
MIN_WITHDRAWAL = 100.0
GAME_COST = 20.0
COMMISSION_RATE = 0.20
CALL_DELAY = 2.30  # Seconds between auto-calls
LOBBY_TIME = 10    # Seconds for countdown

# --- 2. LOCALIZATION (AMHARIC) ---
AMHARIC = {
    "welcome": "👋 **እንኳን ወደ ሜጋ ቢንጎ በደህና መጡ!**\n\nጨዋታ ለመጀመር ወይም ለመቀላቀል `/play` የሚለውን ትእዛዝ ይጠቀሙ።\n\nሂሳብ ለመሙላት: `/deposit`\nደንብ: `/rules`",
    "rules": "📜 **የጨዋታ ህጎች**:\n1. ለመጫወት 20 ብር ያስፈልጋል።\n2. ከ 1-200 የቢንጎ ካርድ ይምረጡ።\n3. ጨዋታው በራስ-ሰር ቁጥሮችን ይጠራል።\n4. አሸናፊው 80% ጠቅላላውን ገንዘብ ይወስዳል።\n5. ማንኛውም ችግር ካለ አድሚኑን ያናግሩ።",
    "balance": "💰 **የእርስዎ ሂሳብ:** {amount:.2f} ብር",
    "deposit_info": "💳 **ገንዘብ ለማስገባት:**\n\nወደ ቴሌብር ቁጥር **0997077778** ይላኩ።\nደረሰኙን (Receipt) ፎቶ አንስተው ወደዚህ ቦት ይላኩ።\nአድሚኑ ሲያረጋግጥ ሂሳብዎ ይሞላል።",
    "withdraw_info": "💸 **ገንዘብ ለማውጣት:**\n`/withdraw [amount] [telebirr_account]`\n\nምሳሌ: `/withdraw 100 0911223344`\n(ቢያንስ 100 ብር)",
    "choose_card": "ማጫወቻ ካርድ ቁጥር አልመረጡም!\nእባክዎ ከ **1 እስከ 200** ቁጥር ይምረጡ።\n\nአጠቃቀም: `/play [ቁጥር]`\nምሳሌ: `/play 55`",
    "card_assigned": "✅ **ካርድ ቁጥር {id} ተመርጧል!**\nጨዋታው እስኪጀምር ይጠብቁ...\n\nየእርስዎ ካርድ:\n{board}",
    "lobby_wait": "⏳ **ጨዋታው በ {seconds} ሰከንድ ውስጥ ይጀምራል...**\nተጨማሪ ተጫዋቾችን በመጠበቅ ላይ።",
    "game_running_err": "⚠️ ጨዋታው እየተካሄደ ነው! እስኪያልቅ ይጠብቁ።",
    "balance_err": "⚠️ በቂ ሂሳብ የለዎትም። ለመጫወት 20 ብር ያስፈልጋል። /deposit ይጠቀሙ።",
    "draw_msg": "🔔 **ቁጥር: {col}-{num}**\n\n{board}",
    "winner": "🎉 **ቢንጎ!! አሸናፊ: {name}** 🎉\n\nሽልማት: **{prize:.2f} ብር**\nጨዋታው ተጠናቀቀ። አዲስ ለመጀመር /play ይበሉ።",
    "receipt_received": "✅ ደረሰኝ ተቀብለናል! አድሚኑ እስኪያረጋግጥ በትግስት ይጠብቁ።",
    "admin_alert_dep": "🚨 **አዲስ ማስገቢያ (Deposit)**\nUser: {uid} (@{user})\nReceipt Below ⬇️",
    "admin_alert_wit": "🚨 **አዲስ ማውጣት (Withdraw)**\nUser: {uid}\nAmount: {amt}\nTelebirr: {acc}",
    "success_credit": "✅ Admin: Credited {amt} to {uid}.",
    "success_debit": "✅ Admin: Debited {amt} from {uid}."
}

# --- 3. DATABASE ---
BASE = declarative_base()
ENGINE = create_engine('sqlite:///megabingo_v3.db') # New DB file for V3
SessionLocal = sessionmaker(bind=ENGINE)

class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    balance = Column(Float, default=0.0)
    referral_code = Column(String)
    referred_by = Column(Integer, nullable=True)

class CardTemplate(BASE):
    """Stores the 200 fixed card layouts."""
    __tablename__ = 'card_templates'
    id = Column(Integer, primary_key=True) # 1-200
    layout = Column(String) # JSON-like string of numbers

class ActiveGame(BASE):
    __tablename__ = 'active_game'
    id = Column(Integer, primary_key=True)
    state = Column(String, default="IDLE") # IDLE, LOBBY, RUNNING
    drawn_numbers = Column(String, default="")
    pool = Column(Float, default=0.0)
    chat_id = Column(Integer) # Chat where game is happening

class GamePlayer(BASE):
    """Links a user to a card in the current game."""
    __tablename__ = 'game_players'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id')) # If negative, it's a computer
    card_template_id = Column(Integer, ForeignKey('card_templates.id'))
    is_computer = Column(Boolean, default=False)
    name = Column(String)

def init_db():
    BASE.metadata.create_all(bind=ENGINE)
    # Pre-generate 200 cards if they don't exist
    session = SessionLocal()
    if session.query(CardTemplate).count() < 200:
        print("Generating 200 Bingo Cards... (This happens once)")
        for i in range(1, 201):
            layout = generate_layout()
            session.add(CardTemplate(id=i, layout=layout))
        session.commit()
    session.close()

def generate_layout():
    """Generates 5x5 grid string."""
    cols = [
        random.sample(range(1, 16), 5),
        random.sample(range(16, 31), 5),
        random.sample(range(31, 46), 4), # Free space logic handled in display
        random.sample(range(46, 61), 5),
        random.sample(range(61, 76), 5)
    ]
    # Insert dummy 0 for free space
    cols[2].insert(2, 0)
    # Convert to comma string
    flat = []
    for r in range(5):
        for c in range(5):
            flat.append(cols[c][r])
    return ",".join(map(str, flat))

# --- 4. GAME ENGINE HELPERS ---

def get_board_display(layout_str, drawn_list, title="YOUR CARD"):
    nums = [int(x) for x in layout_str.split(",")]
    # Amharic mapping
    am = lambda x: "".join([{'0':'፩','1':'፪','2':'፫','3':'፬','4':'፭','5':'፮','6':'፯','7':'፰','8':'፱','9':'0'}.get(d,d) for d in str(x)]) if x!=0 else "F"
    
    drawn_set = set(drawn_list)
    drawn_set.add(0) # Free space always drawn
    
    rows = []
    for r in range(5):
        row_str = ""
        for c in range(5):
            idx = r * 5 + c
            val = nums[idx]
            mark = "✅" if val in drawn_set else ""
            txt = "FREE" if val == 0 else str(val) # Using English numbers for readabilty on grid, Amharic for style if preferred
            # Let's keep numbers English in grid for alignment, Amharic in text
            cell = f"{txt}{mark}"
            row_str += f"{cell:^6}|" 
        rows.append(row_str[:-1])
    
    board = "   B  |  I  |  N  |  G  |  O\n"
    board += "------------------------------\n"
    board += "\n".join(rows)
    return f"```\n{board}\n```"

def check_win(layout_str, drawn_list):
    nums = [int(x) for x in layout_str.split(",")]
    drawn_set = set(drawn_list)
    drawn_set.add(0)
    
    # Rows
    for r in range(5):
        if all(nums[r*5 + c] in drawn_set for c in range(5)): return True
    # Cols
    for c in range(5):
        if all(nums[r*5 + c] in drawn_set for r in range(5)): return True
    # Diagonals
    if all(nums[i*5 + i] in drawn_set for i in range(5)): return True
    if all(nums[i*5 + (4-i)] in drawn_set for i in range(5)): return True
    return False

# --- 5. THE GAME LOOP (AUTO PILOT) ---

async def run_game_loop(app: Application):
    """Background task that manages the game state."""
    while True:
        await asyncio.sleep(1) # Check state every second
        
        db = SessionLocal()
        game = db.query(ActiveGame).first()
        
        if not game:
            game = ActiveGame()
            db.add(game)
            db.commit()
            db.close()
            continue
            
        if game.state == "LOBBY":
            # Countdown logic is handled in the Play command mostly, 
            # but we can finalize it here if time expires.
            # ideally, the command triggers a task.
            pass
            
        elif game.state == "RUNNING":
            # AUTO DRAW LOGIC
            drawn = [int(x) for x in game.drawn_numbers.split(",")] if game.drawn_numbers else []
            remaining = [x for x in range(1, 76) if x not in drawn]
            
            if not remaining:
                game.state = "IDLE"
                db.commit()
                # Notify Game Over
                try:
                    await app.bot.send_message(chat_id=game.chat_id, text="Game Over! No numbers left.")
                except: pass
                db.close()
                continue

            # DRAW
            num = random.choice(remaining)
            drawn.append(num)
            game.drawn_numbers = ",".join(map(str, drawn))
            db.commit()
            
            # Announce
            col = "B" if num<=15 else "I" if num<=30 else "N" if num<=45 else "G" if num<=60 else "O"
            # We can't show everyone's board, just the number.
            msg = AMHARIC["draw_msg"].format(col=col, num=num, board="") 
            try:
                await app.bot.send_message(chat_id=game.chat_id, text=msg)
            except: pass
            
            # CHECK WINNERS (Real & Computer)
            players = db.query(GamePlayer).all()
            winners = []
            
            for p in players:
                tmpl = db.query(CardTemplate).filter_by(id=p.card_template_id).first()
                if check_win(tmpl.layout, drawn):
                    winners.append(p)
            
            if winners:
                # If multiple, pick first (or split). Let's pick first.
                w = winners[0]
                prize = game.pool * (1 - COMMISSION_RATE)
                
                # Pay if real
                if not w.is_computer:
                    u = db.query(User).filter_by(id=w.user_id).first()
                    u.balance += prize
                
                try:
                    await app.bot.send_message(
                        chat_id=game.chat_id, 
                        text=AMHARIC["winner"].format(name=w.name, prize=prize)
                    )
                except: pass
                
                # Reset Game
                game.state = "IDLE"
                game.drawn_numbers = ""
                game.pool = 0
                db.query(GamePlayer).delete()
                db.commit()
            
            db.close()
            # WAIT DELAY
            await asyncio.sleep(CALL_DELAY) 
            continue # Skip the close at bottom, loop again
            
        db.close()

async def start_game_sequence(app: Application, chat_id):
    """Manages Lobby -> Stealth -> Start."""
    db = SessionLocal()
    game = db.query(ActiveGame).first()
    
    # 1. Countdown
    for i in range(LOBBY_TIME, 0, -1):
        try:
            await app.bot.send_message(chat_id=chat_id, text=AMHARIC["lobby_wait"].format(seconds=i))
        except: pass
        await asyncio.sleep(1)
        
    # 2. Stealth Check
    real_count = db.query(GamePlayer).filter_by(is_computer=False).count()
    if real_count > 0 and real_count < 20:
        comp_needed = random.randint(20, 49)
        # Add computers
        for _ in range(comp_needed):
            # Pick random card 1-200
            tid = random.randint(1, 200)
            name_pool = ["Kidus", "Yonas", "Hana", "Tigist", "Abebe", "Marta"]
            name = f"{random.choice(name_pool)}{random.randint(10,99)}"
            # Neg ID for comps
            cp = GamePlayer(user_id=-1, card_template_id=tid, is_computer=True, name=name)
            db.add(cp)
            # Increase pool (Computers 'pay' to make it look real)
            game.pool += GAME_COST
    
    # 3. Start
    game.state = "RUNNING"
    game.chat_id = chat_id
    db.commit()
    
    # Send Start Msg
    tot = db.query(GamePlayer).count()
    try:
        await app.bot.send_message(chat_id=chat_id, text=f"🚀 **ጨዋታው ተጀምሯል!**\nጠቅላላ ተጫዋቾች: {tot}")
    except: pass
    
    db.close()
    # The run_game_loop will pick up the "RUNNING" state automatically.

# --- 6. COMMAND HANDLERS ---

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    
    # Create User if not exists
    user = db.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        user = User(telegram_id=user_id, username=update.effective_user.username, balance=0.0)
        db.add(user)
        db.commit()
        
    # Parse Card ID
    if not context.args:
        await update.message.reply_text(AMHARIC["choose_card"])
        db.close()
        return
        
    try:
        card_choice = int(context.args[0])
        if not (1 <= card_choice <= 200): raise ValueError
    except:
        await update.message.reply_text("⛔ 1-200 ብቻ።")
        db.close()
        return
        
    # Check Balance
    if user.balance < GAME_COST:
        await update.message.reply_text(AMHARIC["balance_err"])
        db.close()
        return
        
    game = db.query(ActiveGame).first()
    if not game: 
        game = ActiveGame(state="IDLE")
        db.add(game)
        db.commit()
        
    if game.state == "RUNNING":
        await update.message.reply_text(AMHARIC["game_running_err"])
        db.close()
        return

    # Join Logic
    # Check if already joined
    exists = db.query(GamePlayer).filter_by(user_id=user.id).first()
    if exists:
        await update.message.reply_text("✅ ተመዝግበዋል።")
        db.close()
        return

    # Deduct & Add
    user.balance -= GAME_COST
    game.pool += GAME_COST
    
    player = GamePlayer(user_id=user.id, card_template_id=card_choice, is_computer=False, name=user.username)
    db.add(player)
    db.commit()
    
    # Get Card Layout for display
    tmpl = db.query(CardTemplate).filter_by(id=card_choice).first()
    board_view = get_board_display(tmpl.layout, [])
    
    await update.message.reply_text(AMHARIC["card_assigned"].format(id=card_choice, board=board_view), parse_mode="Markdown")
    
    # If IDLE, Switch to LOBBY and start timer
    if game.state == "IDLE":
        game.state = "LOBBY"
        db.commit()
        # Start background task for countdown
        asyncio.create_task(start_game_sequence(context.application, update.effective_chat.id))
        
    db.close()

async def mycard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=user_id).first()
    game = db.query(ActiveGame).first()
    
    if not user or not game: return
    
    player = db.query(GamePlayer).filter_by(user_id=user.id).first()
    if not player:
        await update.message.reply_text("⛔ በጨዋታው ውስጥ የለዎትም።")
        db.close()
        return
        
    tmpl = db.query(CardTemplate).filter_by(id=player.card_template_id).first()
    drawn = [int(x) for x in game.drawn_numbers.split(",")] if game.drawn_numbers else []
    
    board = get_board_display(tmpl.layout, drawn)
    await update.message.reply_text(board, parse_mode="Markdown")
    db.close()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["welcome"], parse_mode="Markdown")

async def rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["rules"])

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
    bal = user.balance if user else 0.0
    await update.message.reply_text(AMHARIC["balance"].format(amount=bal), parse_mode="Markdown")
    db.close()

async def deposit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["deposit_info"], parse_mode="Markdown")

async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private" and (update.message.photo or update.message.document):
        user = update.effective_user
        await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=user.id, message_id=update.message.id)
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=AMHARIC["admin_alert_dep"].format(uid=user.id, user=user.username))
        await update.message.reply_text(AMHARIC["receipt_received"])

async def withdraw_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(AMHARIC["withdraw_info"], parse_mode="Markdown")
        return
    
    uid = update.effective_user.id
    amt = float(context.args[0])
    acc = context.args[1]
    
    db = SessionLocal()
    user = db.query(User).filter_by(telegram_id=uid).first()
    
    if not user or user.balance < amt or amt < MIN_WITHDRAWAL:
        await update.message.reply_text("⛔ በቂ ሂሳብ የለዎትም ወይም መጠኑ አነስተኛ ነው።")
        db.close()
        return
        
    user.balance -= amt
    db.commit()
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=AMHARIC["admin_alert_wit"].format(uid=uid, amt=amt, acc=acc))
    await update.message.reply_text("✅ ጥያቄዎ ተልኳል።")
    db.close()

# --- ADMIN COMMANDS ---
async def admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        db = SessionLocal()
        user = db.query(User).filter_by(telegram_id=uid).first()
        if user:
            user.balance += amt
            db.commit()
            await update.message.reply_text(AMHARIC["success_credit"].format(amt=amt, uid=uid))
        db.close()
    except: pass

async def admin_debit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        db = SessionLocal()
        user = db.query(User).filter_by(telegram_id=uid).first()
        if user:
            user.balance -= amt
            db.commit()
            await update.message.reply_text(AMHARIC["success_debit"].format(amt=amt, uid=uid))
        db.close()
    except: pass

# --- MAIN ---
def main():
    if not BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN")
        return

    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("rules", rules_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("deposit", deposit_cmd))
    app.add_handler(CommandHandler("withdraw", withdraw_cmd))
    app.add_handler(CommandHandler("mycard", mycard_command))
    
    app.add_handler(CommandHandler("admin_credit", admin_credit))
    app.add_handler(CommandHandler("admin_debit", admin_debit))
    
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, receipt_handler))

    # START GAME LOOP TASK
    loop = asyncio.get_event_loop()
    loop.create_task(run_game_loop(app))

    print("MegaBingo V3 Auto-Pilot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
