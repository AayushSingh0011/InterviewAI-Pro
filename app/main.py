from fastapi import FastAPI

from app.api.interview import router as interview_router

app = FastAPI(
    title="InterviewAI Pro",
    description="AI-powered adaptive technical interview backend",
    version="1.0.0"
)

# Register API routes
app.include_router(interview_router)


@app.get("/")
def root():
    return {
        "message": "InterviewAI Pro API is running 🚀",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }