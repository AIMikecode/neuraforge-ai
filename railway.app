#!/usr/bin/env python3
"""
NEURAFORGEAИ® - ORCHESTRATOR + BOT UNIFICADO
Versión: 3.2.0 - Listo para Railway
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIGURACIÓN =================
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ej: https://tu-app.up.railway.app
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT = int(os.getenv("PORT", "8000"))

if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN no está definido.")
    sys.exit(1)

# ================= APLICACIÓN FASTAPI =================
app = FastAPI(title="NeuraForge AI - Orchestrator")

# ================= BOT DE TELEGRAM =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BOT INICIALIZADO [OK]")

async def afiliado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔗 AFILIADOS ACTIVOS")

async def productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛍️ CATÁLOGO ACTIVO")

async def urgente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚨 MARKETING ACTIVO")

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ SISTEMA ESTABLE ✅")

async def tesorero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🪙 TESORERO ACTIVO 🪙")

# Construir la aplicación del bot
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("afiliado", afiliado))
bot_app.add_handler(CommandHandler("productos", productos))
bot_app.add_handler(CommandHandler("urgente", urgente))
bot_app.add_handler(CommandHandler("estado", estado))
bot_app.add_handler(CommandHandler("tesorero", tesorero))

# ================= WEBHOOK PARA TELEGRAM =================
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Recibe las actualizaciones de Telegram vía webhook."""
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        return {"status": "error"}, 500

# ================= HEALTH CHECK =================
@app.get("/health")
async def health_check():
    """Endpoint para que Railway verifique que la app está viva."""
    return {"status": "alive", "service": "NeuraForge AI Orchestrator"}

# ================= INICIO =================
if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 Iniciando NeuraForge AI Orchestrator en puerto {PORT}")
    
    # Configurar el webhook en Telegram (solo si WEBHOOK_URL está definido)
    if WEBHOOK_URL:
        full_webhook_url = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
        logger.info(f"✅ Configurando webhook en: {full_webhook_url}")
        try:
            # Intentar configurar el webhook
            import requests
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
                json={"url": full_webhook_url}
            )
            if response.json().get("ok"):
                logger.info("✅ Webhook configurado correctamente")
            else:
                logger.error(f"❌ Error configurando webhook: {response.text}")
        except Exception as e:
            logger.error(f"❌ Error configurando webhook: {e}")
    
    # Iniciar el servidor FastAPI con Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
