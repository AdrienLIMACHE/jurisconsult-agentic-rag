"""
backend/main.py
Point d'entrée du serveur FastAPI RAG Jurisprudence.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import api_router
from backend.services.data_service import data_service
from backend.config import HOST, PORT

app = FastAPI(
    title="RAG Jurisprudence API (LangChain + Ollama)",
    description="API de recherche hybride, résumé structuré et Q&A sur les décisions de justice.",
    version="2.0.0"
)

# Configuration CORS pour autoriser le frontend React (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup():
    print("[INFO] Démarrage du serveur FastAPI...")
    try:
        data_service.load_data()
        print(f"[INFO] {data_service.count()} affaires chargées en mémoire.")
    except Exception as e:
        print(f"[WARN] Initialisation des données : {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
