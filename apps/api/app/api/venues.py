"""Venue API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.models import Venue, VenueStats, Match
from app.services.stats import get_venue_stats

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("")
def list_venues(
    city: str = Query(None, description="Filter by city"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """List all venues."""
    q = db.query(Venue)
    if city:
        q = q.filter(Venue.city.ilike(f"%{city}%"))

    venues = q.order_by(Venue.name).limit(limit).all()
    result = []
    for v in venues:
        vs = db.query(VenueStats).filter(VenueStats.venue_id == v.id).first()
        result.append({
            "id": v.id,
            "name": v.name,
            "city": v.city,
            "matches_played": vs.matches_played if vs else 0,
        })

    return result


@router.get("/{venue_id}")
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    """Get venue intelligence with detailed stats."""
    venue = db.query(Venue).get(venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    stats = get_venue_stats(db, venue_id)

    # Recent matches at this venue
    recent_matches = (
        db.query(Match)
        .filter(Match.venue_id == venue_id)
        .order_by(Match.date.desc())
        .limit(10)
        .all()
    )

    recent = []
    for m in recent_matches:
        recent.append({
            "match_id": m.id,
            "date": str(m.date) if m.date else None,
            "season": m.season,
            "first_innings_score": m.first_innings_score,
            "second_innings_score": m.second_innings_score,
        })

    return {
        "venue": stats,
        "recent_matches": recent,
    }
