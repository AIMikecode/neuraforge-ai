import hmac
import hashlib
import time
from fastapi import APIRouter

# ... Tus otras configuraciones siguen igual ...

BITSO_API_KEY = os.environ.get("BITSO_KEY", "TU_BITSO_API_KEY")
BITSO_API_SECRET = os.environ.get("BITSO_SECRET", "TU_BITSO_SECRET")

def firmar_peticion_bitso(metodo: str, request_path: str, payload_str: str = "") -> dict:
    """Genera los headers necesarios para interactuar de forma segura con la API v3 de Bitso."""
    nonce = str(int(time.time() * 1000))
    message = nonce + metodo + request_path + payload_str
    
    signature = hmac.new(
        BITSO_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    auth_header = f"Bitso {BITSO_API_KEY}:{nonce}:{signature}"
    return {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }

@app.post("/payments/bitso/wallet", tags=["Pasarela de Pagos"])
def obtener_wallet_deposito(moneda: str = "btc"):
    """
    Consulta a Bitso mediante credenciales seguras para obtener la dirección 
    de depósito (QR/Wallet) para fondear el proyecto.
    """
    if BITSO_API_KEY == "TU_BITSO_API_KEY":
        # Modo de pruebas / Fallback si no hay llaves aún configuradas
        return {
            "status": "sandbox",
            "moneda": moneda.upper(),
            "instrucciones": "Envía tus fondos a la wallet principal del Tesoro Orion",
            "wallet_mock": "3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5" 
        }

    request_path = f"/api/v3/funding_destination/?fund_currency={moneda.lower()}"
    url = f"https://api.bitso.com{request_path}"
    
    try:
        headers = firmar_peticion_bitso("GET", request_path)
        response = requests.get(url, headers=headers)
        return {
            "status": "success",
            "data": response.json()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en el puente Crypto: {str(e)}")
    
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

@app.get("/api/check-updates/{license_key}")
async def check_updates(license_key: str):
    """Verifica actualizaciones para un bot"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Obtener última actualización
    cursor.execute('''
        SELECT * FROM updates 
        ORDER BY pushed_at DESC LIMIT 1
    ''')
    latest_update = cursor.fetchone()
    
    # Verificar si este bot ya tiene la actualización
    cursor.execute('''
        SELECT last_update FROM bots WHERE license_key = ?
    ''', (license_key,))
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

# --- SISTEMA DE ACTUALIZACIONES (LA COLMENA) ---
@app.post("/admin/push-update")
async def push_update(
    password: str = Form(...),
    version: str = Form(...),
    update_type: str = Form(...),
    description: str = Form(...),
    file_url: str = Form(None)
):
    """Empuja actualización a todos los bots (solo admin)"""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO updates (version, update_type, description, file_path)
        VALUES (?, ?, ?, ?)
    ''', (version, update_type, description, file_url))
    
    conn.commit()
    conn.close()
    
    # Notificar a todos los bots (en producción sería via webhook)
    return {
        'success': True,
        'message': f'Actualización {version} publicada a toda la colmena',
        'affected_bots': 'Todos los bots activos'
    }

if __name__ == "__main__":
    # Iniciar todos los bots al arrancar
    async def startup_bots():
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
    
    # Ejecutar en segundo plano
    asyncio.create_task(startup_bots())
    
    # Iniciar servidor web
    uvicorn.run(app, host="0.0.0.0", port=8000)
