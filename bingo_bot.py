import telegram
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import random
import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. CONFIGURATION ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
ADMIN_CHAT_ID = 7932072571 

# Financial & Game Constants
WELCOME_BONUS = 40.0
REFERRAL_BONUS = 10.0
MIN_DEPOSIT = 50.0
MIN_WITHDRAWAL = 100.0
GAME_COST = 20.0
COMMISSION_RATE = 0.20
CALL_DELAY = 2.5
LOBBY_DURATION = 15 

# States for Withdrawal Conversation
WITHDRAW_AMOUNT, WITHDRAW_ACCOUNT = range(2)

# --- REPLIT KEEPALIVE ---
class ReplitKeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"MegaBingo V5 is Live!")
def run_server():
    HTTPServer(('', 8080), ReplitKeepAlive).serve_forever()
threading.Thread(target=run_server, daemon=True).start()

# --- 2. LOCALIZATION (AMHARIC) ---
AMHARIC = {
    "welcome": "👋 **እንኳን ወደ ሜጋ ቢንጎ በደህና መጡ!**\n\n🎁 ለጀማሪዎች የ **{bonus} ብር** ስጦታ ተሰጥቶዎታል!\n\nለመጫወት: `/play` ወይም `/quickplay`\nሒሳብ: `/balance`\nገንዘብ ለማስገባት: `/deposit`",
    "deposit_instr": "💳 **ገንዘብ ለማስገባት (Deposit)**\n\n1. እባክዎ ወደዚህ የቴሌብር ቁጥር ይላኩ:\n`0997077778` (Click to Copy)\n\n2. የላኩበትን **ደረሰኝ (Receipt)** ፎቶ ወይም **የግብይት ቁጥር** ለቦቱ ይላኩ።\n\n3. አድሚኑ እንደፈቀደ መልእክት ይደርስዎታል።",
    "withdraw_ask_amt": "💸 **ገንዘብ ለማውጣት**\n\nምን ያህል ማውጣት ይፈልጋሉ? (ቢያንስ 100 ብር)\nእባክዎ መጠኑን ብቻ ይፃፉ (ምሳሌ: `200`)",
    "withdraw_ask_acc": "✅ **መጠን: {amt} ብር**\n\nእባክዎ ገንዘቡ እንዲገባሎት የሚፈልጉትን **የቴሌብር ቁጥር** ይላኩ።",
    "withdraw_sent": "✅ **ጥያቄዎ ተልኳል!**\n\nመጠን: `{amt}` ብር\nቁጥር: `{acc}`\n\nአድሚኑ በቅርቡ ይልካል።",
    "withdraw_cancel": "❌ **ተሰርዟል።**",
    "game_joined": "🎟 **ቢንጎ ካርድ #{id}**\nሒሳብዎ: {bal:.2f} ብር\n\nተጫዋቾችን በመጠበቅ ላይ... ({wait}s)",
    "game_start": "🚀 **ጨዋታ ተጀመረ!**\n\n👥 ጠቅላላ ተጫዋቾች: **{count}**\nመልካም እድል!",
    "winner": "🏆 **ቢንጎ! አሸናፊ: {name}**\n\n💰 ሽልማት: **{prize:.2f} ብር**\n\nቀጣይ ጨዋታ ለመጫወት `/quickplay` ይበሉ።",
    "dep_confirmed": "✅ **ገንዘብዎ ገብቷል!**\n\nየተሞላው ሂሳብ: **{amt} ብር**\nጠቅላላ ሂሳብዎ: **{bal:.2f} ብር**\n\nለመጫወት `/quickplay` ይላኩ።",
    "ref_bonus": "🎉 **የሪፈራል ሽልማት!**\n\nጓደኛዎ የመጀመሪያ ገንዘብ በማስገባቱ **{amt} ብር** አግኝተዋል!",
    "err_bal": "⛔ **በቂ ሂሳብ የለዎትም።**\nሂሳብዎ: {bal:.2f} ብር\nለመጫወት `/deposit` ይጠቀሙ።",
    "admin_new_dep": "🚨 **NEW DEPOSIT**\nUser: `{uid}`\nName: @{name}\n\n👇 **Receipt Below** 👇",
    "admin_new_wit": "🚨 **WITHDRAW REQUEST**\nUser: `{uid}`\nName: @{name}\nAmount: `{amt}`\nTelebirr: `{acc}`"
}

# --- 3. DATABASE ---
BASE = declarative_base()
ENGINE = create_engine('sqlite:///megabingo_v5.db')
SessionLocal = sessionmaker(bind=ENGINE)

class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    balance = Column(Float, default=0.0)
    referrer_id = Column(Integer, nullable=True) # Who invited them
    has_deposited = Column(Boolean, default=False) # For referral logic

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
    user_id = Column(Integer) # Negative = Computer
    card_layout = Column(String)
    is_comp = Column(Boolean, default=False)
    name = Column(String)

def init_db():
    BASE.metadata.create_all(bind=ENGINE)

# --- 4. GAME LOGIC ---

def generate_card():
    cols = [random.sample(range(1, 16), 5), random.sample(range(16, 31), 5), 
            random.sample(range(31, 46), 4), random.sample(range(46, 61), 5), 
            random.sample(range(61, 76), 5)]
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
    male = ["Kidus", "Yonas", "Abel", "Dawit", "Elias", "Natnael", "Bereket", "Robel", "Samson"]
    is_male = random.random() < 0.95
    base = random.choice(male if is_male else ["Hana", "Marta"])
    suffix = random.choice(["", "77", "_ET", "🦁", "🔥", "10", "22"])
    return f"{base}{suffix}"

# --- 5. GAME ENGINE ---

async def game_engine(app: Application):
    """Handles Lobby countdown and Auto-Draw."""
    while True:
        await asyncio.sleep(1)
        db = SessionLocal()
        game = db.query(ActiveGame).first()
        if not game: 
            game = ActiveGame(); db.add(game); db.commit(); db.close(); continue
            
        if game.state == "LOBBY":
            # Just wait for lobby logic in Play handler to trigger start
            # We add a safety timeout here if needed, but Play handler manages countdown
            pass

        elif game.state == "RUNNING":
            drawn = [int(x) for x in game.drawn_numbers.split(",")] if game.drawn_numbers else []
            remaining = [x for x in range(1, 76) if x not in drawn]
            
            if not remaining:
                game.state = "IDLE"; db.commit(); db.close(); continue

            # --- RIGGED LOGIC: Ensure Computer Wins if needed ---
            candidate = random.choice(remaining)
            
            # Simple Rig: If human wins, 50% chance to re-roll to delay them
            humans = db.query(GamePlayer).filter(GamePlayer.is_comp == False).all()
            if any(check_win(p.card_layout, drawn + [candidate]) for p in humans):
                if db.query(GamePlayer).filter(GamePlayer.is_comp == True).count() > 0:
                    candidate = random.choice(remaining) # Re-roll once

            drawn.append(candidate)
            game.drawn_numbers = ",".join(map(str, drawn))
            db.commit()
            
            # Announce Number
            col = "B" if candidate<=15 else "I" if candidate<=30 else "N" if candidate<=45 else "G" if candidate<=60 else "O"
            try:
                await app.bot.send_message(game.chat_id, f"🔔 **{col} - {candidate}**", parse_mode="Markdown")
            except: pass
            
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
    """Counts down and adds computers."""
    await asyncio.sleep(LOBBY_DURATION)
    db = SessionLocal()
    game = db.query(ActiveGame).first()
    
    if game.state == "LOBBY":
        # Add Computers
        real_count = db.query(GamePlayer).filter(GamePlayer.is_comp == False).count()
        if real_count <= 20:
            needed = random.randint(20, 49)
            for _ in range(needed):
                db.add(GamePlayer(user_id=-random.randint(999,99999), is_comp=True, name=gen_comp_name(), card_layout=generate_card()))
                game.pool += GAME_COST # Illusion of big pool
        
        total = db.query(GamePlayer).count()
        game.state = "RUNNING"
        game.chat_id = chat_id
        db.commit()
        await app.bot.send_message(chat_id, AMHARIC["game_start"].format(count=total), parse_mode="Markdown")
    db.close()

# --- 6. USER HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if not u:
        # Check Referral
        ref_id = None
        if context.args:
            try:
                ref_candidate = int(context.args[0])
                if ref_candidate != user.id: ref_id = ref_candidate
            except: pass
            
        u = User(telegram_id=user.id, username=user.username, balance=WELCOME_BONUS, referrer_id=ref_id)
        db.add(u)
        db.commit()
    
    await update.message.reply_text(AMHARIC["welcome"].format(bonus=WELCOME_BONUS), parse_mode="Markdown")
    db.close()

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    # 1. Quickplay vs Play
    is_quick = update.message.text.startswith("/quick")
    card_id = random.randint(1, 200)
    if not is_quick:
        if not context.args:
            await update.message.reply_text("⛔ እባክዎ ቁጥር ይምረጡ: `/play 55` ወይም `/quickplay` ይላኩ።", parse_mode="Markdown")
            db.close(); return
        try: card_id = int(context.args[0])
        except: card_id = random.randint(1, 200)

    # 2. Check Balance & State
    if u.balance < GAME_COST:
        await update.message.reply_text(AMHARIC["err_bal"].format(bal=u.balance), parse_mode="Markdown")
        db.close(); return

    game = db.query(ActiveGame).first()
    if not game: game = ActiveGame(); db.add(game); db.commit()
    
    if game.state == "RUNNING":
        await update.message.reply_text("⚠️ ጨዋታው እየተካሄደ ነው።", parse_mode="Markdown"); db.close(); return
        
    if db.query(GamePlayer).filter_by(user_id=u.id).first():
        await update.message.reply_text("✅ ተመዝግበዋል።", parse_mode="Markdown"); db.close(); return

    # 3. Join
    u.balance -= GAME_COST
    game.pool += GAME_COST
    db.add(GamePlayer(user_id=u.id, card_layout=generate_card(), name=u.username, is_comp=False))
    
    # Trigger Lobby if first player
    if game.state == "IDLE":
        game.state = "LOBBY"
        asyncio.create_task(start_game_task(context.application, update.effective_chat.id))
        
    db.commit()
    await update.message.reply_text(AMHARIC["game_joined"].format(id=card_id, bal=u.balance, wait=LOBBY_DURATION), parse_mode="Markdown")
    db.close()

# --- WITHDRAWAL CONVERSATION ---

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["withdraw_ask_amt"], parse_mode="Markdown")
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text)
        if amt < MIN_WITHDRAWAL:
            await update.message.reply_text(f"⛔ አነስተኛ ማውጣት {MIN_WITHDRAWAL} ብር ነው። እንደገና ይፃፉ።")
            return WITHDRAW_AMOUNT
        context.user_data['w_amt'] = amt
        await update.message.reply_text(AMHARIC["withdraw_ask_acc"].format(amt=amt), parse_mode="Markdown")
        return WITHDRAW_ACCOUNT
    except:
        await update.message.reply_text("⛔ ቁጥር ብቻ ያስገቡ (ምሳሌ: 200)")
        return WITHDRAW_AMOUNT

async def withdraw_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc = update.message.text
    amt = context.user_data['w_amt']
    user = update.effective_user
    
    db = SessionLocal()
    u = db.query(User).filter_by(telegram_id=user.id).first()
    
    if u.balance < amt:
        await update.message.reply_text("⛔ በቂ ሂሳብ የለዎትም።", parse_mode="Markdown")
    else:
        u.balance -= amt
        db.commit()
        # Alert Admin
        await context.bot.send_message(ADMIN_CHAT_ID, AMHARIC["admin_new_wit"].format(uid=user.id, name=user.username, amt=amt, acc=acc), parse_mode="Markdown")
        await update.message.reply_text(AMHARIC["withdraw_sent"].format(amt=amt, acc=acc), parse_mode="Markdown")
    
    db.close()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["withdraw_cancel"], parse_mode="Markdown")
    return ConversationHandler.END

# --- DEPOSIT & ADMIN ---

async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(AMHARIC["deposit_instr"], parse_mode="Markdown")

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private" and (update.message.photo or update.message.text):
        if update.message.text and update.message.text.startswith("/"): return
        user = update.effective_user
        
        # Forward to Admin with ID
        await context.bot.send_message(ADMIN_CHAT_ID, AMHARIC["admin_new_dep"].format(uid=user.id, name=user.username), parse_mode="Markdown")
        if update.message.photo:
            await context.bot.forward_message(ADMIN_CHAT_ID, update.effective_chat.id, update.message.id)
        else:
            await context.bot.send_message(ADMIN_CHAT_ID, f"📝 Tx Info: {update.message.text}")
            
        await update.message.reply_text("✅ ደረሰኝ ተቀብለናል!", parse_mode="Markdown")

async def admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID: return
    try:
        uid, amt = int(context.args[0]), float(context.args[1])
        db = SessionLocal()
        u = db.query(User).filter_by(telegram_id=uid).first()
        if u:
            u.balance += amt
            # Check Referral Bonus (First Deposit Only)
            if not u.has_deposited:
                u.has_deposited = True
                if u.referrer_id:
                    ref = db.query(User).filter_by(telegram_id=u.referrer_id).first()
                    if ref:
                        ref.balance += REFERRAL_BONUS
                        await context.bot.send_message(ref.telegram_id, AMHARIC["ref_bonus"].format(amt=REFERRAL_BONUS), parse_mode="Markdown")
            
            db.commit()
            # Notify User
            await context.bot.send_message(uid, AMHARIC["dep_confirmed"].format(amt=amt, bal=u.balance), parse_mode="Markdown")
            await update.message.reply_text(f"✅ Credited {amt} to {uid}")
        db.close()
    except: await update.message.reply_text("Use: `/admin_credit [ID] [Amount]`")

# --- MAIN ---
def main():
    if not BOT_TOKEN: print("NO TOKEN"); return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("quickplay", play)) # Same handler, different logic inside
    app.add_handler(CommandHandler("deposit", deposit))
    
    # Withdraw Conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_account)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)
    
    app.add_handler(CommandHandler("admin_credit", admin_credit))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT, handle_receipt))
    
    loop = asyncio.get_event_loop()
    loop.create_task(game_engine(app))
    
    print("MegaBingo V5.0 LIVE...")
    app.run_polling()

if __name__ == "__main__":
    main()
