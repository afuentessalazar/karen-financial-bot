import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class SheetsClient:
    _instance = None
    _last_auth = 0

    @classmethod
    def get_ws(cls, name="Transacciones"):
        if not cls._instance or (time.time() - cls._last_auth > 2700):
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            cls._instance = gspread.authorize(creds).open_by_key(os.getenv("GOOGLE_SHEET_ID"))
            cls._last_auth = time.time()
        return cls._instance.worksheet(name)

    @classmethod
    def get_last_id(cls, worksheet):
        # Obtener todos los valores de la columna A, omitiendo el encabezado
        values = worksheet.col_values(1)[1:] 
        ids = [int(v) for v in values if v.isdigit()]
        return max(ids) + 1 if ids else 1