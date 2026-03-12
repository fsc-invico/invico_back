import uvicorn

if __name__ == "__main__":  # 🔹 Importante para evitar problemas en Windows
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",  # 127.0.0.1
        port=8000,
        reload=False,
        loop="asyncio",
    )
# uvicorn src.main:app --loop asyncio
