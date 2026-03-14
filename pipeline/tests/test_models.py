from src.models import RawListing, ScoreResult


def test_raw_listing_minimal():
    listing = RawListing(
        source="idealista",
        url="https://idealista.it/123",
        raw_data={"key": "value"},
    )
    assert listing.source == "idealista"
    assert listing.title is None
    assert listing.has_video is False


def test_raw_listing_full():
    listing = RawListing(
        source="immobiliare",
        url="https://immobiliare.it/456",
        title="Bilocale Milano",
        price=900,
        rooms=2,
        size_sqm=55,
        lat=45.46,
        lon=9.19,
        raw_data={"full": "data"},
    )
    assert listing.price == 900
    assert listing.rooms == 2


def test_raw_listing_extra_scraper_fields():
    listing = RawListing(
        source="idealista",
        url="https://idealista.it/789",
        elevator=True,
        condition="renovated",
        condo_fees=150,
    )
    assert listing.elevator is True
    assert listing.condition == "renovated"
    assert listing.condo_fees == 150


def test_score_result_defaults():
    result = ScoreResult(score=75)
    assert result.score == 75
    assert result.details == {}


def test_score_result_with_details():
    result = ScoreResult(
        score=85,
        details={"zone": "Isola", "factor": 1.0},
    )
    assert result.details["factor"] == 1.0
