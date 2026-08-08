from fastapi import FastAPI

app = FastAPI(
    title="InterviewAI Pro",
    version="1.0.0"
)

@app.get("/")
def home():
    return {"message": "InterviewAI Pro API is running 🚀"}

@app.get("/health")
def health():
    return {"status": "healthy"}