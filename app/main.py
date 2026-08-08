from fastapi import FastAPI
from app.api.interview import router as interview_router
app = FastAPI(
    title="Interview Agent API",
    description="AI-powered adaptive technical interview backend",
    version="1.0.0"
)

app.include_router(interview_router)

@app.get("/")
def root():
    return {
        "message": "Interview Agent API is running",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }