from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.search import router as search_router
app = FastAPI(
    title="ProCart API",
    description="Product catalogue API for ProCart",
    version="0.1.0",
)
app.include_router(search_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": f"The endpoint '{request.url.path}' is not available.",
        },
    )