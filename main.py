import os
import pytz
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from telegram.ext.filters import MessageFilter

from sheets_engine import SheetsClient
from nlp_processor import FinancialNLP

# 1. Configuración de Logging para producción (reemplaza los print)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
CHILE_TZ = pytz.timezone('America/Santiago')

# 2. Filtro de autorización desacoplado
class AuthFilter(MessageFilter):
    def filter(self, message):
        return str(message.from_user.id) == os.getenv("AUTHORIZED_USER_ID")

is_admin = AuthFilter()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text
    msg_ts = update.message.date.astimezone(CHILE_TZ)
    thinking = await update.message.reply_text("⏳ Procesando...")
    
    try:
        data = await FinancialNLP.parse_instruction(raw_text)

        if not data.get("monto"):
            return await thinking.edit_text("⚠️ Error: No se detectó monto.")

        ws_trans = await asyncio.to_thread(SheetsClient.get_ws, "Transacciones")
        nuevo_id = await asyncio.to_thread(SheetsClient.get_last_id, ws_trans)

        row = [
            nuevo_id,                          # A: ID
            msg_ts.strftime("%d/%m/%Y"),       # B: Fecha
            data['tipo'],                      # C: Tipo
            data['monto'],                     # D: Monto
            data['cuenta_origen'],             # E: Cuenta Origen (Afectada)
            data['cuenta_destino'],            # F: Cuenta Destino (Solo Transferencia)
            data['categoria'],                 # G: Categoría
            data['descripcion']                # H: Descripción
        ]

        await asyncio.to_thread(ws_trans.append_row, row, value_input_option='USER_ENTERED')

        destino_str = f" ➔ {data['cuenta_destino']}" if data['cuenta_destino'] else ""
        res_msg = (f"✅ **ID #{nuevo_id} Registrado**\n"
                   f"📊 {data['tipo']} > {data['categoria']}\n"
                   f"💰 ${data['monto']:,}\n"
                   f"🏦 {data['cuenta_origen']}{destino_str}")
        
        await thinking.edit_text(res_msg, parse_mode='Markdown')

    except Exception as e:
        # Logging real del traceback para poder debugear
        logger.error(f"Error en pipeline: {str(e)}", exc_info=True)
        await thinking.edit_text("❌ Error interno en pipeline. Revisa los logs.")

async def get_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws_dash = await asyncio.to_thread(SheetsClient.get_ws, "Dashboard")
        raw_data = await asyncio.to_thread(ws_dash.get, 'B3:C19')
        
        # 3. Mapeo dinámico de datos. Se asume Columna B = índice 0, Columna C = índice 1
        data_dict = {row[0].strip(): (row[1] if len(row) > 1 else "0") for row in raw_data if row}
        
        # CAMBIA ESTOS STRINGS POR LOS NOMBRES EXACTOS DE TUS FILAS EN SHEETS
        resumen = (f"📊 **Patrimonio: {data_dict.get('Patrimonio', 'N/A')}**\n"
                   f"🟢 Disponible: {data_dict.get('Disponible', 'N/A')}\n"
                   f"📉 Cuota Diaria: {data_dict.get('Cuota Diaria', 'N/A')}\n"
                   f"{'—'*10}\n")
        
        # Desglose de cuentas (Ajusta los nombres a los de tu Excel)
        nombres_cuentas = ['Cuenta Corriente', 'Tarjeta de Crédito', 'Caja'] 
        for cuenta in nombres_cuentas:
            if cuenta in data_dict:
                resumen += f"• {cuenta}: {data_dict[cuenta]}\n"
                
        await update.message.reply_text(resumen, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error obteniendo saldo: {str(e)}", exc_info=True)
        await update.message.reply_text("❌ Error al leer el Dashboard.")

async def delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ws = await asyncio.to_thread(SheetsClient.get_ws, "Transacciones")
        rows = await asyncio.to_thread(ws.get_all_values)
        if len(rows) > 1:
            await asyncio.to_thread(ws.delete_rows, len(rows))
            await update.message.reply_text("🗑️ Rollback completado.")
        else:
            await update.message.reply_text("⚠️ No hay transacciones para borrar.")
    except Exception as e:
        logger.error(f"Error en rollback: {str(e)}", exc_info=True)
        await update.message.reply_text("❌ Error al intentar hacer rollback.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    # 4. El filtro is_admin se aplica directamente en la capa de ruteo
    app.add_handler(CommandHandler("saldo", get_balance, filters=is_admin))
    app.add_handler(CommandHandler("borrar", delete_last, filters=is_admin))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & is_admin, handle_text))
    
    logger.info(">>> K.A.R.E.N. Operativa y escuchando...")
    app.run_polling()