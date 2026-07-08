import os
import json
import asyncio
import google.generativeai as genai

class FinancialNLP:
    _initialized = False
    _model = None  # Cacheamos la instancia del modelo

    @classmethod
    def _setup_api(cls):
        if not cls._initialized:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            # Inicializamos el modelo una sola vez
            cls._model = genai.GenerativeModel(
                'gemini-2.5-flash', 
                generation_config={"response_mime_type": "application/json"}
            )
            cls._initialized = True

    @staticmethod
    async def parse_instruction(text):
        FinancialNLP._setup_api()
        
        prompt = f"""
        Eres un analizador financiero estricto. Transforma el siguiente texto natural en un objeto JSON exacto.
        
        Texto del usuario: "{text}"
        
        Reglas estrictas:
        - "tipo": Solo puede ser "Ingreso", "Gasto", o "Transferencia".
        - "categoria": Clasifica lógicamente (ej. "Trabajo", "Transporte", "Comida", "Ocio"). Si el tipo es "Transferencia", el valor debe ser "Transferencia".
        - "monto": Extrae el número entero exacto. Considera la jerga chilena (ej. "luca" o "lucas" = 1000).
        - "cuenta_origen": De dónde sale el dinero. Usa nombres formales (ej. "Mercado Pago", "Banco Estado", "Banco de Chile", "Efectivo"). Si no se menciona y es un Gasto, asume "Efectivo".
        - "cuenta_destino": A dónde llega el dinero. Solo aplica si el tipo es "Transferencia", de lo contrario déjalo vacío ("").
        - "descripcion": El mismo texto original del usuario, truncado a máximo 100 caracteres.
        
        Salida esperada (solo JSON válido):
        {{
            "tipo": "Gasto",
            "categoria": "Transporte",
            "monto": 5000,
            "cuenta_origen": "Efectivo",
            "cuenta_destino": "",
            "descripcion": "gaste 5 lucas en la micro"
        }}
        """
        
        # Consumimos la instancia persistente de la clase
        response = await asyncio.to_thread(FinancialNLP._model.generate_content, prompt)
        
        try:
            data = json.loads(response.text)
            return {
                'tipo': data.get('tipo', 'Gasto'),
                'categoria': data.get('categoria', 'Varios'),
                'monto': int(data.get('monto', 0)),
                'cuenta_origen': data.get('cuenta_origen', 'Efectivo'),
                'cuenta_destino': data.get('cuenta_destino', ''),
                'descripcion': data.get('descripcion', text[:100])
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"Fallo en la decodificación del LLM: {str(e)}\nRespuesta cruda: {response.text}")