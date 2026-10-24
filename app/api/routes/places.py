from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.location.assistant import LocationDep

router = APIRouter(tags=["places"])


class SavedPlaceOut(BaseModel):
    label: str
    name: str
    address: str


@router.get("/places")
async def list_places(location: LocationDep) -> list[SavedPlaceOut]:
    """The user's saved places (saved by telling a persona, e.g. "save my home as …")."""
    if location is None:
        return []
    return [
        SavedPlaceOut(label=s.label, name=s.place.name, address=s.place.address)
        for s in location.saved.all()
    ]


@router.delete("/places/{label}", status_code=204)
async def delete_place(label: str, location: LocationDep) -> Response:
    if location is None or not location.saved.delete(label):
        raise HTTPException(status_code=404, detail="No saved place with that label")
    return Response(status_code=204)
