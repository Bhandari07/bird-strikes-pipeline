"""Domain normalization with record-level issues; source values stay unchanged."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from .contracts import EXTRA


def normalize(r):
    issues = []

    def issue(rule, field, detail):
        issues.append((rule, field, str(r.get(field, "")), detail))

    def number(field):
        value = r.get(field, "")
        if not value:
            return None
        try:
            n = Decimal(value.replace(",", ""))
            if n < 0 or not n.is_finite() or n != n.to_integral_value():
                raise ValueError()
            return int(n)
        except (ValueError, OverflowError, InvalidOperation):
            issue(
                "INVALID_NONNEGATIVE_INTEGER",
                field,
                "Must be a nonnegative whole number",
            )
            return None

    date = None
    try:
        date = (
            datetime.strptime(r.get("FlightDate", ""), "%d/%m/%Y %H:%M")
            .date()
            .isoformat()
        )
    except ValueError:
        issue(
            "MISSING_OR_INVALID_DATE",
            "FlightDate",
            "Expected day/month/year hour:minute",
        )
    height = number("Feet above ground")
    count = number("Wildlife: Number Struck Actual")
    cost = number("Cost: Total $")
    injuries = number("Number of people injured")
    engines = number(EXTRA)
    altitude = r.get("Altitude bin", "")
    altitude_status = "valid"
    if height is None or not altitude:
        altitude_status = "missing"
        issue("ALTITUDE_MISSING", "Feet above ground", "Height or altitude bin missing")
    elif height == 1000:
        altitude_status = "boundary"
        issue(
            "ALTITUDE_BOUNDARY",
            "Altitude bin",
            "Exactly 1000 feet: supplier boundary definition needed",
        )
    elif altitude not in ("< 1000 ft", "> 1000 ft") or (height < 1000) != (
        altitude == "< 1000 ft"
    ):
        altitude_status = "mismatch"
        issue("ALTITUDE_MISMATCH", "Altitude bin", f"Height is {height} feet")
    category = r.get("Wildlife: Number struck", "")
    valid_range = {
        "1": lambda x: x == 1,
        "2 to 10": lambda x: 2 <= x <= 10,
        "11 to 100": lambda x: 11 <= x <= 100,
        "Over 100": lambda x: x > 100,
    }
    if (
        count is not None
        and category in valid_range
        and (not valid_range[category](count))
    ):
        issue(
            "BIRD_COUNT_RANGE_MISMATCH",
            "Wildlife: Number Struck Actual",
            f"Conflicts with category {category}",
        )
    elif count is None or category not in valid_range:
        issue(
            "BIRD_COUNT_MISSING_OR_CATEGORY",
            "Wildlife: Number struck",
            "Missing count or unsupported category",
        )
    weather = r.get("Conditions: Precipitation", "")
    tokens = {v.strip() for v in weather.split(",")} if weather else set()
    known = (
        bool(tokens)
        and tokens <= {"None", "Rain", "Fog", "Snow"}
        and (not ("None" in tokens and len(tokens) > 1))
    )
    if not known:
        issue(
            "PRECIPITATION_UNKNOWN",
            "Conditions: Precipitation",
            "Missing or unsupported combination",
        )
    if not r.get("Airport: Name", ""):
        issue("AIRPORT_MISSING", "Airport: Name", "Retained under Unknown airport")
    damage = {"No damage": 0, "Caused damage": 1}.get(r.get("Effect: Indicated Damage"))
    if damage is None:
        issue(
            "DAMAGE_UNKNOWN", "Effect: Indicated Damage", "Unsupported damage category"
        )
    return (
        dict(
            record_id=r["Record ID"],
            flight_date=date,
            airport=r.get("Airport: Name") or "Unknown",
            state=r.get("Origin State") or "Unknown",
            aircraft_type=r.get("Aircraft: Type") or "Unknown",
            aircraft_model=r.get("Aircraft: Make/Model") or "Unknown",
            operator=r.get("Aircraft: Airline/Operator") or "Unknown",
            species=r.get("Wildlife: Species") or "Unknown",
            wildlife_size=r.get("Wildlife: Size") or "Unknown",
            phase=r.get("When: Phase of flight") or "Unknown",
            sky=r.get("Conditions: Sky") or "Unknown",
            precipitation=weather or "Unknown",
            has_rain=int("Rain" in tokens) if known else None,
            has_fog=int("Fog" in tokens) if known else None,
            has_snow=int("Snow" in tokens) if known else None,
            damage=damage,
            cost=cost,
            injuries=injuries,
            birds_struck=count,
            feet_above_ground=height,
            altitude_source=altitude or None,
            altitude_derived=(
                None
                if height is None
                else (
                    "<1000" if height < 1000 else "=1000" if height == 1000 else ">1000"
                )
            ),
            altitude_status=altitude_status,
            engines=engines,
            impact=r.get("Effect: Impact to flight") or "Unknown",
            pilot_warned={"Y": 1, "N": 0}.get(
                r.get("Pilot warned of birds or wildlife?")
            ),
            dq_issue_count=len(issues),
        ),
        issues,
    )
