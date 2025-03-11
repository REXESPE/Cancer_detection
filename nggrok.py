import uvicorn
from pyngrok import ngrok, conf

# Configurar la ruta del ejecutable de ngrok
conf.get_default().ngrok_path = r"C:\Users\carlos\Downloads\ngrok-v3-stable-windows-amd64 (1)\ngrok.exe"

# Abre un túnel ngrok en el puerto 8000
ngrok_tunnel = ngrok.connect(8000)
print(f"ngrok tunnel \"{ngrok_tunnel.public_url}\" -> \"http://127.0.0.1:8000\"")

# Inicia la aplicación FastAPI en el puerto 8000
uvicorn.run("main:app", host="0.0.0.0", port=8000)