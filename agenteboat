#!/usr/bin/env python3

import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ej: https://tu-app.up.railway.app
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
PORT = int(os.getenv("PORT", "8000"))

if not TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN no está definido en las variables de entorno.")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

# ===== HANDLERS =====
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

# ===== FUNCIÓN PRINCIPAL =====
def main():
    logger.info("🚀 Iniciando bot...")

    # Construir la aplicación
    app = Application.builder().token(TOKEN).build()

    # Registrar handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("afiliado", afiliado))
    app.add_handler(CommandHandler("productos", productos))
    app.add_handler(CommandHandler("urgente", urgente))
    app.add_handler(CommandHandler("estado", estado))
    app.add_handler(CommandHandler("tesorero", tesorero))

    # Modo Webhook (Railway) o Polling
    if WEBHOOK_URL:
        # Asegurar que el path empiece con "/"
        if not WEBHOOK_PATH.startswith("/"):
            webhook_path = "/" + WEBHOOK_PATH
        else:
            webhook_path = WEBHOOK_PATH

        full_webhook_url = WEBHOOK_URL.rstrip("/") + webhook_path
        logger.info(f"✅ Modo WEBHOOK activado en {full_webhook_url}")

        # ⚠️ IMPORTANTE: NO usar 'path=' en run_webhook() en v20+
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_path=path,
        webhook_url=full_webhook,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
        stop_signals=None
    )
    else:
        logger.info("⚠️ WEBHOOK_URL no definido: usando polling")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=2.0,
            timeout=30,
            stop_signals=None,
        )

# ===== PUNTO DE ENTRADA =====
if __name__ == "__main__":
    main()
