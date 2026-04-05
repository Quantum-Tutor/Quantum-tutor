import os
import google.genai as genai
from dotenv import load_dotenv
from quantum_tutor_runtime import APP_NAME, DEFAULT_TEXT_MODEL, RUNTIME_VERSION

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: no se encontró GEMINI_API_KEY en .env")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("--- Listando modelos disponibles ---")
        models = client.models.list()
        for i, model in enumerate(models):
            if i == 0:
                print(f"Atributos de ejemplo del modelo: {dir(model)}")
            print(f"Nombre del modelo: {model.name}")
        
        print(f"\n--- Probando el modelo por defecto de {APP_NAME} ({DEFAULT_TEXT_MODEL}) para {RUNTIME_VERSION} ---")
        response = client.models.generate_content(
            model=DEFAULT_TEXT_MODEL,
            contents="Hola, ¿estás operativo?"
        )
        print(f"Respuesta: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
