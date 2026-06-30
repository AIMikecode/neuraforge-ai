# main.py - Sistema de gestión de bots con licencias
import sqlite3
import asyncio
import logging
import hashlib
import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, Form, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import uvicorn
import qrcode
from io import BytesIO
import json

# --- CONFIGURACIÓN AVANZADA ---
TOKEN_TELEGRAM = "TU_TOKEN_AQUÍ"
ADMIN_PASSWORD = "neuraforge_admin_2026"
DB_NAME = "neuraforge_hive.db"
SECRET_KEY = "tu_clave_secreta_2026"  # Para ofuscación

app = FastAPI(title="NeuraForge Hive - Bot Factory")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeuraForgeHive")

# --- BASE DE DATOS COMPLETA ---
def init_complete_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de licencias/bots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            bot_token TEXT,
            owner_name TEXT,
            owner_email TEXT,
            bot_type TEXT DEFAULT 'SAT_ASSISTANT',
            status TEXT DEFAULT 'active',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_count INTEGER DEFAULT 0,
            serial_hash TEXT,
            payment_status TEXT DEFAULT 'free',
            ads_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Tabla de agentes (modo escucha)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_license TEXT,
            agent_name TEXT,
            telegram_id TEXT,
            listen_keywords TEXT,  # JSON de palabras clave
            response_template TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (bot_license) REFERENCES bots (license_key)
        )
    ''')
    
    # Tabla de donaciones/pagos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            amount REAL,
            currency TEXT DEFAULT 'MXN',
            payment_method TEXT,
            transaction_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_key) REFERENCES bots (license_key)
        )
    ''')
    
    # Tabla de actualizaciones (colmena)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT,
            update_type TEXT,
            description TEXT,
            file_path TEXT,
            requires_restart INTEGER DEFAULT 0,
            pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_complete_db()

# --- SISTEMA DE LICENCIAS OFUSCADAS ---
class LicenseManager:
    """Genera y valida licencias ofuscadas"""
    
    @staticmethod
    def generate_license(bot_type: str, email: str) -> dict:
        """Genera una licencia única ofuscada"""
        # Parte 1: UUID único
        license_uuid = str(uuid.uuid4())
        
        # Parte 2: Hash ofuscado
        raw_string = f"{bot_type}:{email}:{license_uuid}:{datetime.now().timestamp()}"
        serial_hash = hashlib.sha256((raw_string + SECRET_KEY).encode()).hexdigest()[:16]
        
        # Parte 3: Código legible (ej: NF-SAT-A1B2-C3D4)
        parts = [
            "NF",
            bot_type[:3].upper(),
            serial_hash[:4].upper(),
            serial_hash[4:8].upper()
        ]
        license_key = "-".join(parts)
        
        # QR Code para la licencia
        qr = qrcode.make(f"NEURAFORGE:{license_key}:{serial_hash}")
        qr_bytes = BytesIO()
        qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        
        return {
            'license_key': license_key,
            'serial_hash': serial_hash,
            'qr_code': qr_bytes,
            'activation_url': f"https://botscaza.com/activate/{license_key}"
        }
    
    @staticmethod
    def validate_license(license_key: str, serial_hash: str) -> bool:
        """Valida una licencia"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 1 FROM bots 
            WHERE license_key = ? AND serial_hash = ? AND status = 'active'
        ''', (license_key, serial_hash))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None

# --- MÓDULO DE COBRO CON GOOGLE PAY Y CRYPTO ---
class PaymentGateway:
    """Integra Google Pay y conversión a crypto"""
    
    @staticmethod
    async def create_donation_link(license_key: str, amount: float = 50.0):
        """Crea enlace de donación con Google Pay"""
        # Google Pay integration
        google_pay_data = {
            "apiVersion": 2,
            "apiVersionMinor": 0,
            "merchantInfo": {
                "merchantId": "BCR2DN4T27S72B6T",
                "merchantName": "NeuraForge Hive"
            },
            "allowedPaymentMethods": [{
                "type": "CARD",
                "parameters": {
                    "allowedAuthMethods": ["PAN_ONLY", "CRYPTOGRAM_3DS"],
                    "allowedCardNetworks": ["MASTERCARD", "VISA"]
                }
            }]
        }
        
        # Generar enlace único
        import secrets
        payment_token = secrets.token_hex(16)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO donations (license_key, amount, payment_method, transaction_id, status)
            VALUES (?, ?, 'google_pay', ?, 'pending')
        ''', (license_key, amount, payment_token))
        conn.commit()
        conn.close()
        
        return {
            'payment_url': f"https://botscaza.com/pay/{payment_token}",
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://botscaza.com/pay/{payment_token}",
            'amount': amount,
            'currency': 'MXN'
        }
    
    @staticmethod
    async def convert_to_crypto(amount_mxn: float, target_crypto: str = "BTC"):
        """Convierte MXN a crypto usando API"""
        # Usar API de Bitso o Binance
        conversion_apis = {
            'BTC': 'https://api.bitso.com/v3/ticker/?book=btc_mxn',
            'ETH': 'https://api.bitso.com/v3/ticker/?book=eth_mxn',
            'USDT': 'https://api.bitso.com/v3/ticker/?book=usdt_mxn'
        }
        
        try:
            import requests
            response = requests.get(conversion_apis.get(target_crypto, conversion_apis['BTC']))
            data = response.json()
            
            if data['success']:
                current_price = float(data['payload']['last'])
                crypto_amount = amount_mxn / current_price
                
                return {
                    'mxn_amount': amount_mxn,
                    'crypto_amount': round(crypto_amount, 8),
                    'crypto_type': target_crypto,
                    'exchange_rate': current_price,
                    'address': '1NeuraForgeCryptoAddressXYZ'  # En producción usar dirección única
                }
        except:
            # Fallback a tasa fija
            fallback_rates = {'BTC': 1000000, 'ETH': 60000, 'USDT': 17}
            crypto_amount = amount_mxn / fallback_rates.get(target_crypto, 17)
            
            return {
                'mxn_amount': amount_mxn,
                'crypto_amount': round(crypto_amount, 8),
                'crypto_type': target_crypto,
                'exchange_rate': fallback_rates.get(target_crypto, 17),
                'note': 'Usando tasa de cambio estimada'
            }

# --- BOT CON MODO ESCUCHA Y AGENTES ---
class SmartBot:
    """Bot inteligente con modo escucha y agentes"""
    
    def __init__(self, token: str, license_key: str):
        self.token = token
        self.license_key = license_key
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        
        # Cargar agentes desde DB
        self.agents = self.load_agents()
    
    def load_agents(self):
        """Carga agentes/configuración de escucha"""
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM agents 
            WHERE bot_license = ? AND is_active = 1
        ''', (self.license_key,))
        
        agents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Parse keywords JSON
        for agent in agents:
            if agent['listen_keywords']:
                agent['keywords'] = json.loads(agent['listen_keywords'])
            else:
                agent['keywords'] = []
        
        return agents
    
    def setup_handlers(self):
        """Configura todos los handlers del bot"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("agentes", self.list_agents))
        self.application.add_handler(CommandHandler("donar", self.donate_command))
        
        # Modo escucha para todos los mensajes
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.listen_mode)
        )
    
    async def start_command(self, update: Update, context: CallbackContext):
        """Comando /start personalizado"""
        user = update.effective_user
        
        # Verificar si requiere donación para funcionalidades premium
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT payment_status FROM bots WHERE license_key = ?
        ''', (self.license_key,))
        bot_status = cursor.fetchone()
        conn.close()
        
        welcome_text = f"""
🤖 *Bot activo - Licencia: {self.license_key}*

¡Hola {user.first_name}! Soy tu asistente administrativo.

📋 *Funcionalidades:*
• Asistencia SAT básica
• Recordatorios fiscales
• Calculadora de impuestos
• Agentes inteligentes

💝 *¿Te ayudo mucho?*
Considera donar un café para mantenerme activo.
Usa /donar para apoyar el proyecto.
"""
        
        # Mostrar anuncio si está habilitado
        if bot_status and bot_status[0] == 'free':
            welcome_text += "\n---\n📢 *Publicidad:* ¡Aprende a invertir en crypto gratis!"
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def listen_mode(self, update: Update, context: CallbackContext):
        """Modo escucha - responde a palabras clave"""
        message_text = update.message.text.lower()
        user_id = update.effective_user.id
        
        # Revisar si coincide con palabras clave de agentes
        for agent in self.agents:
            for keyword in agent['keywords']:
                if keyword.lower() in message_text:
                    # Responder con template del agente
                    response = agent['response_template'].replace("{user}", update.effective_user.first_name)
                    await update.message.reply_text(response, parse_mode='Markdown')
                    return
        
        # Respuesta por defecto si no hay coincidencias
        default_responses = [
            "¿Necesitas ayuda con algún trámite específico?",
            "Puedo ayudarte con temas SAT, escribe 'declaración' o 'factura'",
            "¿Quieres configurar un agente personalizado? Contacta al admin."
        ]
        
        import random
        await update.message.reply_text(random.choice(default_responses))
    
    async def donate_command(self, update: Update, context: CallbackContext):
        """Comando /donar - Solicita donación"""
        payment = PaymentGateway()
        donation_info = await payment.create_donation_link(self.license_key, 50.0)
        
        response_text = f"""
☕ *Invítame un café - $50 MXN*

Tu apoyo ayuda a:
• Mantener servidores activos
• Agregar nuevas funcionalidades
• Soporte 24/7

💳 *Para donar:*
1. Escanea este código QR
2. O visita: {donation_info['payment_url']}

¡Gracias por apoyar el proyecto!
"""
        
        # Enviar QR code
        await update.message.reply_photo(
            photo=donation_info['qr_code'],
            caption=response_text,
            parse_mode='Markdown'
        )
    
    async def start_bot(self):
        """Inicia el bot"""
        await self.application.initialize()
#!/usr/bin/env python3
# main.py - Sistema de gestión de bots con licencias (VERSIÓN PRODUCCIÓN)
import sqlite3
import asyncio
import logging
import hashlib
import uuid
import os
import json
import random
import secrets
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import uvicorn
import qrcode
import requests

# ================= CONFIGURACIÓN DESDE VARIABLES DE ENTORNO =================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TU_TOKEN_AQUÍ")  # ¡REEMPLAZA!
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "neuraforge_admin_2026")
SECRET_KEY = os.getenv("SECRET_KEY", "tu_clave_secreta_2026")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
DB_NAME = os.getenv("DATABASE_URL", "neuraforge_hive.db").replace("sqlite:///", "")

# Si la DB es SQLite, se asegura que el directorio exista
if DB_NAME.startswith("./"):
    DB_NAME = DB_NAME[2:]

# ================= CONFIGURACIÓN DE LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeuraForgeHive")

# ================= APLICACIÓN FASTAPI =================
app = FastAPI(title="NeuraForge Hive - Bot Factory")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ================= BASE DE DATOS COMPLETA =================
def init_complete_db():
    """Inicializa todas las tablas de la base de datos"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de licencias/bots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            bot_token TEXT,
            owner_name TEXT,
            owner_email TEXT,
            bot_type TEXT DEFAULT 'SAT_ASSISTANT',
            status TEXT DEFAULT 'active',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_count INTEGER DEFAULT 0,
            serial_hash TEXT,
            payment_status TEXT DEFAULT 'free',
            ads_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Tabla de agentes (modo escucha)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_license TEXT,
            agent_name TEXT,
            telegram_id TEXT,
            listen_keywords TEXT,
            response_template TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (bot_license) REFERENCES bots (license_key)
        )
    ''')
    
    # Tabla de donaciones/pagos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            amount REAL,
            currency TEXT DEFAULT 'MXN',
            payment_method TEXT,
            transaction_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_key) REFERENCES bots (license_key)
        )
    ''')
    
    # Tabla de actualizaciones (colmena)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT,
            update_type TEXT,
            description TEXT,
            file_path TEXT,
            requires_restart INTEGER DEFAULT 0,
            pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_complete_db()

# ================= SISTEMA DE LICENCIAS OFUSCADAS =================
class LicenseManager:
    @staticmethod
    def generate_license(bot_type: str, email: str) -> dict:
        license_uuid = str(uuid.uuid4())
        raw_string = f"{bot_type}:{email}:{license_uuid}:{datetime.now().timestamp()}"
        serial_hash = hashlib.sha256((raw_string + SECRET_KEY).encode()).hexdigest()[:16]
        
        parts = ["NF", bot_type[:3].upper(), serial_hash[:4].upper(), serial_hash[4:8].upper()]
        license_key = "-".join(parts)
        
        qr = qrcode.make(f"NEURAFORGE:{license_key}:{serial_hash}")
        qr_bytes = BytesIO()
        qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        
        return {
            'license_key': license_key,
            'serial_hash': serial_hash,
            'qr_code': qr_bytes,
            'activation_url': f"https://botscaza.com/activate/{license_key}"
        }
    
    @staticmethod
    def validate_license(license_key: str, serial_hash: str) -> bool:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM bots WHERE license_key = ? AND serial_hash = ? AND status = "active"', (license_key, serial_hash))
        result = cursor.fetchone()
        conn.close()
        return result is not None

# ================= MÓDULO DE PAGOS (GOOGLE PAY + CRYPTO) =================
class PaymentGateway:
    @staticmethod
    async def create_donation_link(license_key: str, amount: float = 50.0):
        payment_token = secrets.token_hex(16)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO donations (license_key, amount, payment_method, transaction_id, status) VALUES (?, ?, "google_pay", ?, "pending")', (license_key, amount, payment_token))
        conn.commit()
        conn.close()
        
        return {
            'payment_url': f"https://botscaza.com/pay/{payment_token}",
            'qr_code': f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=https://botscaza.com/pay/{payment_token}",
            'amount': amount,
            'currency': 'MXN'
        }
    
    @staticmethod
    async def convert_to_crypto(amount_mxn: float, target_crypto: str = "BTC"):
        conversion_apis = {
            'BTC': 'https://api.bitso.com/v3/ticker/?book=btc_mxn',
            'ETH': 'https://api.bitso.com/v3/ticker/?book=eth_mxn',
            'USDT': 'https://api.bitso.com/v3/ticker/?book=usdt_mxn'
        }
        
        try:
            response = requests.get(conversion_apis.get(target_crypto, conversion_apis['BTC']))
            data = response.json()
            if data['success']:
                current_price = float(data['payload']['last'])
                crypto_amount = amount_mxn / current_price
                return {
                    'mxn_amount': amount_mxn,
                    'crypto_amount': round(crypto_amount, 8),
                    'crypto_type': target_crypto,
                    'exchange_rate': current_price,
                    'address': '1NeuraForgeCryptoAddressXYZ'
                }
        except Exception as e:
            logger.error(f"Error en conversión crypto: {e}")
        
        fallback_rates = {'BTC': 1000000, 'ETH': 60000, 'USDT': 17}
        crypto_amount = amount_mxn / fallback_rates.get(target_crypto, 17)
        return {
            'mxn_amount': amount_mxn,
            'crypto_amount': round(crypto_amount, 8),
            'crypto_type': target_crypto,
            'exchange_rate': fallback_rates.get(target_crypto, 17),
            'note': 'Usando tasa de cambio estimada'
        }

# ================= BOT INTELIGENTE =================
class SmartBot:
    def __init__(self, token: str, license_key: str):
        self.token = token
        self.license_key = license_key
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
        self.agents = self.load_agents()
    
    def load_agents(self):
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM agents WHERE bot_license = ? AND is_active = 1', (self.license_key,))
        agents = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        for agent in agents:
            agent['keywords'] = json.loads(agent['listen_keywords']) if agent['listen_keywords'] else []
        return agents
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("agentes", self.list_agents))
        self.application.add_handler(CommandHandler("donar", self.donate_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.listen_mode))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT payment_status FROM bots WHERE license_key = ?', (self.license_key,))
        bot_status = cursor.fetchone()
        conn.close()
        
        welcome_text = f"""
🤖 *Bot activo - Licencia: {self.license_key}*

¡Hola {user.first_name}! Soy tu asistente administrativo.

📋 *Funcionalidades:*
• Asistencia SAT básica
• Recordatorios fiscales
• Calculadora de impuestos
• Agentes inteligentes

💝 *¿Te ayudo mucho?*
Considera donar un café para mantenerme activo.
Usa /donar para apoyar el proyecto.
"""
        if bot_status and bot_status[0] == 'free':
            welcome_text += "\n---\n📢 *Publicidad:* ¡Aprende a invertir en crypto gratis!"
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def listen_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text.lower()
        
        for agent in self.agents:
            for keyword in agent['keywords']:
                if keyword.lower() in message_text:
                    response = agent['response_template'].replace("{user}", update.effective_user.first_name)
                    await update.message.reply_text(response, parse_mode='Markdown')
                    return
        
        default_responses = [
            "¿Necesitas ayuda con algún trámite específico?",
            "Puedo ayudarte con temas SAT, escribe 'declaración' o 'factura'",
            "¿Quieres configurar un agente personalizado? Contacta al admin."
        ]
        await update.message.reply_text(random.choice(default_responses))
    
    async def donate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        payment = PaymentGateway()
        donation_info = await payment.create_donation_link(self.license_key, 50.0)
        
        response_text = f"""
☕ *Invítame un café - $50 MXN*

Tu apoyo ayuda a:
• Mantener servidores activos
• Agregar nuevas funcionalidades
• Soporte 24/7

💳 *Para donar:*
1. Escanea este código QR
2. O visita: {donation_info['payment_url']}

¡Gracias por apoyar el proyecto!
"""
        await update.message.reply_photo(photo=donation_info['qr_code'], caption=response_text, parse_mode='Markdown')
    
    async def start_bot(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info(f"Bot con licencia {self.license_key} iniciado")

# ================= WEBHOOK PARA TELEGRAM =================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Recibe las actualizaciones de Telegram vía webhook."""
    try:
        data = await request.json()
        # Nota: Aquí necesitarías instanciar el bot correcto según el token.
        # Por simplicidad, usamos un bot global, pero en un entorno real,
        # deberías mapear el token con la instancia.
        update = Update.de_json(data, global_bot.bot)
        await global_bot.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return {"status": "error"}, 500

# ================= ENDPOINTS DE LA API =================
@app.get("/")
async def home():
    return HTMLResponse("""
    <html>
        <head>
            <title>NeuraForge Hive - Fábrica de Bots</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 text-white p-8">
            <h1 class="text-3xl font-bold text-blue-400">🚀 NeuraForge Hive</h1>
            <p class="text-gray-300 mt-2">Fábrica de bots inteligentes con actualizaciones automáticas</p>
            
            <div class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">🤖 Crear Bot</h2>
                    <p class="mt-2 text-gray-400">Genera tu bot con licencia única</p>
                    <a href="/create" class="mt-4 inline-block bg-blue-600 px-4 py-2 rounded">Crear ahora</a>
                </div>
                
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">🔄 Actualizaciones</h2>
                    <p class="mt-2 text-gray-400">La colmena actualiza todos los bots automáticamente</p>
                </div>
                
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">💝 Donaciones</h2>
                    <p class="mt-2 text-gray-400">Sistema de "invítame un café" integrado</p>
                </div>
            </div>
        </body>
    </html>
    """)

@app.get("/create")
async def create_bot_page(request: Request):
    return templates.TemplateResponse("create_bot.html", {"request": request})

@app.post("/api/create-bot")
async def create_bot(
    bot_type: str = Form(...),
    owner_name: str = Form(...),
    owner_email: str = Form(...),
    bot_token: str = Form(...)
):
    license_mgr = LicenseManager()
    license_info = license_mgr.generate_license(bot_type, owner_email)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bots (license_key, bot_token, owner_name, owner_email, bot_type, serial_hash, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    ''', (license_info['license_key'], bot_token, owner_name, owner_email, bot_type, license_info['serial_hash']))
    conn.commit()
    conn.close()
    
    bot = SmartBot(bot_token, license_info['license_key'])
    asyncio.create_task(bot.start_bot())
    
    return {
        'success': True,
        'license_key': license_info['license_key'],
        'serial_hash': license_info['serial_hash'],
        'qr_code_url': f"/license-qr/{license_info['license_key']}",
        'activation_url': license_info['activation_url'],
        'message': 'Bot creado exitosamente. Se iniciará en 1-2 minutos.'
    }

@app.get("/license-qr/{license_key}")
async def get_license_qr(license_key: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT serial_hash FROM bots WHERE license_key = ?', (license_key,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="Licencia no encontrada")
    
    qr_data = f"NEURAFORGE:{license_key}:{result[0]}"
    qr = qrcode.make(qr_data)
    img_bytes = BytesIO()
    qr.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return FileResponse(img_bytes, media_type="image/png")

@app.get("/api/check-updates/{license_key}")
async def check_updates(license_key: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM updates ORDER BY pushed_at DESC LIMIT 1')
    latest_update = cursor.fetchone()
    cursor.execute('SELECT last_update FROM bots WHERE license_key = ?', (license_key,))
    bot_info = cursor.fetchone()
    conn.close()
    
    if latest_update and bot_info:
        update_time = datetime.strptime(latest_update['pushed_at'], '%Y-%m-%d %H:%M:%S')
        bot_update_time = datetime.strptime(bot_info['last_update'], '%Y-%m-%d %H:%M:%S')
        
        if update_time > bot_update_time:
            return {
                'update_available': True,
                'version': latest_update['version'],
                'description': latest_update['description'],
                'requires_restart': bool(latest_update['requires_restart']),
                'download_url': f"/download-update/{license_key}/{latest_update['id']}"
            }
    
    return {'update_available': False}

@app.post("/admin/push-update")
async def push_update(
    password: str = Form(...),
    version: str = Form(...),
    update_type: str = Form(...),
    description: str = Form(...),
    file_url: str = Form(None)
):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO updates (version, update_type, description, file_path) VALUES (?, ?, ?, ?)', (version, update_type, description, file_url))
    conn.commit()
    conn.close()
    
    return {
        'success': True,
        'message': f'Actualización {version} publicada a toda la colmena',
        'affected_bots': 'Todos los bots activos'
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ================= VARIABLE GLOBAL PARA EL BOT =================
global_bot = None

# ================= INICIO =================
async def startup_bots():
    """Inicia todos los bots activos al arrancar."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT license_key, bot_token FROM bots WHERE status = 'active'")
    bots = cursor.fetchall()
    conn.close()
    
    for license_key, bot_token in bots:
        try:
            bot = SmartBot(bot_token, license_key)
            asyncio.create_task(bot.start_bot())
            logger.info(f"Bot {license_key} iniciado")
        except Exception as e:
            logger.error(f"Error iniciando bot {license_key}: {e}")

@app.on_event("startup")
async def startup_event():
    """Evento de inicio de FastAPI."""
    global global_bot
    # Crear un bot de ejemplo para el webhook (idealmente deberías tener uno por token)
    first_bot = SmartBot(TELEGRAM_TOKEN, "GLOBAL")
    global_bot = first_bot
    
    # Iniciar todos los bots
    await startup_bots()
    
    # Configurar webhook en Telegram si WEBHOOK_URL está definida
    if WEBHOOK_URL and TELEGRAM_TOKEN != "TU_TOKEN_AQUÍ":
        webhook_url = WEBHOOK_URL.rstrip("/") + "/webhook"
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": webhook_url}
            )
            if response.json().get("ok"):
                logger.info(f"Webhook configurado en {webhook_url}")
            else:
                logger.error(f"Error configurando webhook: {response.text}")
        except Exception as e:
            logger.error(f"Error configurando webhook: {e}")

# ================= EJECUCIÓN LOCAL =================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info(f"Bot con licencia {self.license_key} iniciado")

# --- API ENDPOINTS PARA LA PLATAFORMA ---
@app.get("/")
async def home():
    return HTMLResponse("""
    <html>
        <head>
            <title>NeuraForge Hive - Fábrica de Bots</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-900 text-white p-8">
            <h1 class="text-3xl font-bold text-blue-400">🚀 NeuraForge Hive</h1>
            <p class="text-gray-300 mt-2">Fábrica de bots inteligentes con actualizaciones automáticas</p>
            
            <div class="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">🤖 Crear Bot</h2>
                    <p class="mt-2 text-gray-400">Genera tu bot con licencia única</p>
                    <a href="/create" class="mt-4 inline-block bg-blue-600 px-4 py-2 rounded">Crear ahora</a>
                </div>
                
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">🔄 Actualizaciones</h2>
                    <p class="mt-2 text-gray-400">La colmena actualiza todos los bots automáticamente</p>
                </div>
                
                <div class="bg-gray-800 p-6 rounded-lg">
                    <h2 class="text-xl font-bold">💝 Donaciones</h2>
                    <p class="mt-2 text-gray-400">Sistema de "invítame un café" integrado</p>
                </div>
            </div>
        </body>
    </html>
    """)

@app.get("/create")
async def create_bot_page(request: Request):
    """Página para crear nuevo bot"""
    return templates.TemplateResponse("create_bot.html", {"request": request})

@app.post("/api/create-bot")
async def create_bot(
    bot_type: str = Form(...),
    owner_name: str = Form(...),
    owner_email: str = Form(...),
    bot_token: str = Form(...)
):
    """API para crear nuevo bot con licencia"""
    
    # Generar licencia
    license_mgr = LicenseManager()
    license_info = license_mgr.generate_license(bot_type, owner_email)
    
    # Guardar en base de datos
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO bots (license_key, bot_token, owner_name, owner_email, 
                         bot_type, serial_hash, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    ''', (
        license_info['license_key'],
        bot_token,
        owner_name,
        owner_email,
        bot_type,
        license_info['serial_hash']
    ))
    
    conn.commit()
    conn.close()
    
    # Iniciar bot en segundo plano
    bot = SmartBot(bot_token, license_info['license_key'])
    asyncio.create_task(bot.start_bot())
    
    # Retornar licencia y QR
    return {
        'success': True,
        'license_key': license_info['license_key'],
        'serial_hash': license_info['serial_hash'],
        'qr_code_url': f"/license-qr/{license_info['license_key']}",
        'activation_url': license_info['activation_url'],
        'message': 'Bot creado exitosamente. Se iniciará en 1-2 minutos.'
    }

@app.get("/license-qr/{license_key}")
async def get_license_qr(license_key: str):
    """Genera QR code para la licencia"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT serial_hash FROM bots WHERE license_key = ?', (license_key,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="Licencia no encontrada")
    
    # Generar QR
    qr_data = f"NEURAFORGE:{license_key}:{result[0]}"
    qr = qrcode.make(qr_data)
    
    img_bytes = BytesIO()
    qr.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return FileResponse(img_bytes, media_type="image/png")
niciar servidor web
    uvicorn.run(app, host="0.0.0.0", port=8000)
