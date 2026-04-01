"""Weather service for match conditions -- dew, rain, humidity affect game strategy."""
import httpx
from typing import Optional

# IPL venue coordinates
VENUE_COORDS = {
    "Mumbai": (19.07, 72.88),       # Wankhede
    "Chennai": (13.08, 80.27),      # Chepauk
    "Bengaluru": (12.98, 77.60),    # Chinnaswamy
    "Kolkata": (22.57, 88.36),      # Eden Gardens
    "Delhi": (28.64, 77.24),        # Arun Jaitley
    "Hyderabad": (17.41, 78.55),    # Rajiv Gandhi
    "Jaipur": (26.89, 75.80),       # Sawai Mansingh
    "Lucknow": (26.85, 80.95),      # Ekana
    "Ahmedabad": (23.09, 72.60),    # Narendra Modi
    "Chandigarh": (30.69, 76.74),   # Mullanpur (Punjab Kings)
    "Dharamsala": (32.22, 76.32),    # HPCA
    "Guwahati": (26.14, 91.77),     # Barsapara
    "Raipur": (21.25, 81.63),       # Shaheed Veer Narayan
}


async def fetch_weather(city: str) -> dict:
    """Fetch current weather for a city. Returns conditions relevant to cricket."""
    coords = VENUE_COORDS.get(city)
    if not coords:
        # Try partial match
        for k, v in VENUE_COORDS.items():
            if k.lower() in city.lower() or city.lower() in k.lower():
                coords = v
                break
    if not coords:
        return {"available": False, "city": city}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": coords[0],
                "longitude": coords[1],
                "current": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,wind_speed_10m,cloud_cover",
                "timezone": "Asia/Kolkata",
            })
            data = resp.json()
            current = data.get("current", {})

            temp = current.get("temperature_2m", 25)
            humidity = current.get("relative_humidity_2m", 50)
            dew_point = current.get("dew_point_2m", 15)
            precipitation = current.get("precipitation", 0)
            wind = current.get("wind_speed_10m", 10)
            cloud = current.get("cloud_cover", 30)

            # Cricket-relevant conditions
            dew_factor = "heavy" if humidity > 80 and temp > 20 else "moderate" if humidity > 65 else "minimal"
            rain_risk = "high" if precipitation > 0.5 else "moderate" if cloud > 70 else "low"

            # Dew impact: heavy dew makes the ball wet, harder to grip
            # -> batting easier in 2nd innings, spinners less effective
            # humidity > 80% after sunset = heavy dew
            dew_impact = []
            if dew_factor == "heavy":
                dew_impact = [
                    "Heavy dew expected -- bowling second will be difficult",
                    "Spinners will struggle with wet ball -- prefer pace at death",
                    "Batting second has significant advantage",
                    "Win toss -> BAT FIRST (set target, bowl while dry)",
                ]
            elif dew_factor == "moderate":
                dew_impact = [
                    "Moderate dew likely in second innings",
                    "Some grip issues for spinners later",
                ]

            return {
                "available": True,
                "city": city,
                "temperature": temp,
                "humidity": humidity,
                "dew_point": dew_point,
                "dew_factor": dew_factor,
                "precipitation_mm": precipitation,
                "rain_risk": rain_risk,
                "wind_speed_kmh": wind,
                "cloud_cover_pct": cloud,
                "impact": dew_impact,
                "toss_recommendation_adjustment": (
                    "bat_first" if dew_factor == "heavy"
                    else "field_first" if rain_risk == "high"
                    else None
                ),
            }
    except Exception as e:
        return {"available": False, "city": city, "error": str(e)}
