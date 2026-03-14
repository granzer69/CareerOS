from fastapi import APIRouter

router = APIRouter(prefix="/roadmap", tags=["roadmap"])

@router.get("/")
async def get_roadmap():
    return {"message": "Roadmap feature coming soon"}
