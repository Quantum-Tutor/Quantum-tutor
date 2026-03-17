import subprocess
import time
import re
import qrcode
import sys
import threading
import os
import urllib.request

def run_streamlit():
    """Ejecuta Streamlit en un hilo separado."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app_quantum_tutor.py", "--server.headless=true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env
    )

def deploy_and_generate_qr():
    print("[*] Iniciando QuantumTutor v2.0...")
    
    # Levantar Streamlit
    threading.Thread(target=run_streamlit, daemon=True).start()
    time.sleep(4)  # Esperar a que Streamlit esté listo
    
    print("[*] Levantando túnel público (localhost.run via SSH) en el puerto 8501...")
    
    # Iniciar túnel SSH reverso con localhost.run
    try:
        process = subprocess.Popen(
            ["ssh", "-R", "80:localhost:8501", "-o", "StrictHostKeyChecking=no", "nokey@localhost.run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    except Exception as e:
        print(f"[!] Error al iniciar el túnel SSH: {e}")
        return

    public_url = None
    
    # Leer la salida en vivo para capturar la URL
    start_time = time.time()
    while time.time() - start_time < 30:
        line = process.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
            
        print(f"  > {line.strip()}")
        # Busca el patrón: https://<algo>.lhr.life o similar
        match = re.search(r"(https://[a-zA-Z0-9.-]+\.lhr\.[a-z]+)", line)
        if match:
            public_url = match.group(1).strip()
            break
            
    if not public_url:
        print("[!] No se pudo extraer la URL pública. Comprueba tu conexión SSH o el firewall.")
        print("[*] Cerrando proceso defectuoso...")
        try:
            process.kill()
        except:
            pass
        return

    print(f"\n[SUCCESS] Tutor desplegado exitosamente en: {public_url}")
    print("[*] Generando código QR para acceso móvil...")
    

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(public_url)
    qr.make(fit=True)
    
    # Guardar la imagen QR
    img_path = "acceso_tutor.png"
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_path)
    
    print(f"[SUCCESS] Código QR guardado en: {os.path.abspath(img_path)}")
    print("\n" + "="*70)
    print("ACCESO MÓVIL (QuantumTutor v2.0)")
    print("="*70)
    print("1. Abre tu teléfono móvil (o escanea desde la pantalla).")
    print(f"2. Escanea {img_path} o ingresa a:")
    print(f"   ►►►  {public_url}  ◄◄◄")
    print("3. Pasa la barrera de autenticación de Google.")
    print("4. Manten esta ventana abierta para no caiga el servidor.")
    print("="*70 + "\n")
    
    # Mantener el script vivo para mantener el túnel
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\n[*] Cerrando túnel y servidor...")
        process.kill()

if __name__ == "__main__":
    deploy_and_generate_qr()
