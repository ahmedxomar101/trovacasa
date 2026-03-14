"""Tests for scraper normalize methods."""

from src.models import RawListing
from src.scrapers.idealista import IdealistaScraper
from src.scrapers.immobiliare import ImmobiliareScraper


class TestIdealistaNormalize:
    """Test IdealistaScraper.normalize with realistic data."""

    def setup_method(self):
        self.scraper = IdealistaScraper()

    def test_basic_listing(self):
        raw = {
            "url": "/immobile/12345/",
            "price": 950,
            "rooms": 2,
            "size": 55,
            "address": "Via Roma 10",
            "district": "Isola",
            "municipality": "Milano",
            "latitude": 45.4854,
            "longitude": 9.1892,
            "description": "Nice apartment near metro",
            "floor": "3",
            "bathrooms": 1,
            "thumbnail": "https://img.idealista.com/thumb.jpg",
        }
        result = self.scraper.normalize(raw)

        assert isinstance(result, RawListing)
        assert result.source == "idealista"
        assert result.url == "https://www.idealista.it/immobile/12345/"
        assert result.price == 950
        assert result.rooms == 2
        assert result.size_sqm == 55
        assert result.address == "Via Roma 10, Isola, Milano"
        assert result.lat == 45.4854
        assert result.lon == 9.1892
        assert result.floor == "3"
        assert result.bathrooms == 1
        assert result.image_url == "https://img.idealista.com/thumb.jpg"

    def test_price_as_dict(self):
        raw = {
            "url": "https://www.idealista.it/immobile/99/",
            "price": {"amount": 800},
            "rooms": 1,
            "size": 40,
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.price == 800

    def test_contact_info_parsing(self):
        raw = {
            "url": "/immobile/555/",
            "price": 1000,
            "contactInfo": {
                "commercialName": "Tecnocasa Milano",
                "phone1": {
                    "phoneNumberForMobileDialing": "+39 02 1234567",
                },
                "userType": "professional",
            },
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.agent == "Tecnocasa Milano"
        assert result.phone == "+39 02 1234567"
        assert result.is_private is False

    def test_private_listing(self):
        raw = {
            "url": "/immobile/777/",
            "price": 900,
            "contactInfo": {
                "contactName": "Mario",
                "userType": "private",
            },
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.is_private is True

    def test_features_extraction(self):
        raw = {
            "url": "/immobile/888/",
            "price": 1050,
            "features": {
                "hasAirConditioning": True,
                "hasTerrace": True,
            },
            "hasLift": True,
            "status": "renew",
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.air_conditioning is True
        assert result.terrace is True
        assert result.elevator is True
        assert result.condition == "renovated"

    def test_creation_date_conversion(self):
        raw = {
            "url": "/immobile/111/",
            "price": 750,
            "firstActivationDate": 1710000000000,
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.creation_date is not None
        assert "2024-03" in result.creation_date

    def test_no_price_returns_listing(self):
        """normalize should return the listing even without price."""
        raw = {
            "url": "/immobile/222/",
            "rooms": 2,
            "size": 50,
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.price is None

    def test_full_url_unchanged(self):
        raw = {
            "url": "https://www.idealista.it/immobile/333/",
            "price": 900,
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.url == "https://www.idealista.it/immobile/333/"


class TestImmobiliareNormalize:
    """Test ImmobiliareScraper.normalize with memo23 format data."""

    def setup_method(self):
        self.scraper = ImmobiliareScraper()

    def test_basic_listing(self):
        raw = {
            "title": "Bilocale in affitto a Milano",
            "shareUrl": "https://www.immobiliare.it/annunci/12345/?ref=search",
            "price": {"raw": 900},
            "topology": {
                "rooms": 2,
                "surface": {"size": 60},
                "bathrooms": 1,
                "floor": "2",
            },
            "geography": {
                "geolocation": {
                    "latitude": 45.4654,
                    "longitude": 9.1859,
                },
                "street": "Via Torino",
                "macrozone": {"name": "Centro"},
                "municipality": {"name": "Milano"},
            },
            "analytics": {
                "advertiser": "agency",
                "agencyName": "Gabetti",
            },
            "media": {
                "images": [
                    {"hd": "https://img.immobiliare.it/hd.jpg"},
                ],
            },
            "description": {
                "content": "Beautiful apartment in the center",
            },
        }
        result = self.scraper.normalize(raw)

        assert isinstance(result, RawListing)
        assert result.source == "immobiliare"
        assert result.url == "https://www.immobiliare.it/annunci/12345/"
        assert result.title == "Bilocale in affitto a Milano"
        assert result.price == 900
        assert result.rooms == 2
        assert result.size_sqm == 60
        assert result.address == "Via Torino, Centro, Milano"
        assert result.lat == 45.4654
        assert result.lon == 9.1859
        assert result.agent == "Gabetti"
        assert result.bathrooms == 1
        assert result.num_photos == 1

    def test_skip_agency_data(self):
        raw = {"dataType": "agency", "name": "Some Agency"}
        result = self.scraper.normalize(raw)
        assert result is None

    def test_private_listing(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/99/",
            "price": {"raw": 800},
            "topology": {"rooms": 1},
            "geography": {},
            "analytics": {"advertiser": "privato"},
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.agent == "privato"
        assert result.is_private is True

    def test_condition_mapping(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/55/",
            "price": {"raw": 1000},
            "topology": {},
            "geography": {},
            "analytics": {
                "propertyStatus": "Buono / Abitabile",
            },
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.condition == "good"

    def test_condo_fees_extraction(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/66/",
            "price": {"raw": 950},
            "topology": {},
            "geography": {},
            "analytics": {},
            "costs": [
                {
                    "label": "Spese condominio",
                    "value": "150 EUR/mese",
                },
            ],
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.condo_fees == 150

    def test_furnished_from_main_data(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/77/",
            "price": {"raw": 1100},
            "topology": {},
            "geography": {},
            "analytics": {},
            "mainData": [
                {
                    "rows": [
                        {"label": "Furnished", "value": "Yes"},
                    ],
                },
            ],
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.furnished == "full"

    def test_air_conditioning_from_main_data(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/88/",
            "price": {"raw": 1000},
            "topology": {},
            "geography": {},
            "analytics": {},
            "mainData": [
                {
                    "rows": [
                        {
                            "label": "Air conditioning",
                            "value": "Yes",
                        },
                    ],
                },
            ],
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.air_conditioning is True

    def test_energy_class_extraction(self):
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/44/",
            "price": {"raw": 850},
            "topology": {},
            "geography": {},
            "analytics": {},
            "energyClass": {
                "consumptions": [{"value": "D"}],
            },
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.energy_class == "D"

    def test_fallback_url_from_id(self):
        raw = {
            "id": 999,
            "price": {"raw": 700},
            "topology": {},
            "geography": {},
            "analytics": {},
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.url == "https://www.immobiliare.it/annunci/999/"

    def test_no_price_returns_listing(self):
        """normalize should return listing even without price."""
        raw = {
            "shareUrl": "https://www.immobiliare.it/annunci/33/",
            "topology": {"rooms": 2, "surface": {"size": 50}},
            "geography": {},
            "analytics": {},
        }
        result = self.scraper.normalize(raw)

        assert result is not None
        assert result.price is None
        assert result.rooms == 2
