import pytest
from bs4 import BeautifulSoup

from real_estate_monitor.adapters.playwright_bs_adapter import PlaywrightBSAdapter
from real_estate_monitor.schemas.schemas import NormalizedListing


SAMPLE_HTML = """
<html>
<body>
  <div class="listing-item">
    <h2 class="listing-title">Beautiful House</h2>
    <span class="listing-price">R$ 2.500,00</span>
    <p class="listing-address">123 Main St</p>
    <a class="listing-link" href="/listing/1">View</a>
    <span class="listing-bedrooms">3</span>
    <span class="listing-bathrooms">2</span>
    <span class="listing-parking">1</span>
    <span class="listing-area">120 m2</span>
    <p class="listing-description">Nice place</p>
    <img class="listing-image" src="/img1.jpg"/>
  </div>
  <div class="listing-item">
    <h2 class="listing-title">Small Apartment</h2>
    <span class="listing-price">R$ 1.200,00</span>
    <p class="listing-address">456 Oak Ave</p>
    <a class="listing-link" href="/listing/2">View</a>
    <span class="listing-bedrooms">1</span>
    <span class="listing-bathrooms">1</span>
    <span class="listing-parking">0</span>
    <span class="listing-area">45 m2</span>
    <p class="listing-description">Cozy</p>
    <img class="listing-image" src="/img2.jpg"/>
  </div>
</body>
</html>
"""


@pytest.fixture
def adapter():
    config = {
        "url": "https://test.com",
        "config": {
            "headless": True,
            "wait_selector": ".listing-item",
            "wait_timeout": 5000,
            "listing_selector": ".listing-item",
            "fields": {
                "title": ".listing-title",
                "price": ".listing-price",
                "address": ".listing-address",
                "url": "a.listing-link",
                "bedrooms": ".listing-bedrooms",
                "bathrooms": ".listing-bathrooms",
                "parking": ".listing-parking",
                "area": ".listing-area",
                "description": ".listing-description",
                "image_url": "img.listing-image",
            },
        },
    }
    return PlaywrightBSAdapter(config)


@pytest.mark.asyncio
async def test_parse_listings_from_html(adapter):
    adapter._html = SAMPLE_HTML
    listings = await adapter.fetch_listings()
    assert len(listings) == 2
    assert listings[0].title == "Beautiful House"
    assert listings[0].price == 2500.0
    assert listings[0].address == "123 Main St"
    assert listings[0].url == "/listing/1"
    assert listings[0].bedrooms == 3
    assert listings[0].bathrooms == 2
    assert listings[0].parking == 1
    assert listings[0].area == 120.0
    assert listings[0].description == "Nice place"
    assert listings[0].image_url == "/img1.jpg"


@pytest.mark.asyncio
async def test_second_listing(adapter):
    adapter._html = SAMPLE_HTML
    listings = await adapter.fetch_listings()
    assert listings[1].title == "Small Apartment"
    assert listings[1].price == 1200.0
    assert listings[1].bedrooms == 1


@pytest.mark.asyncio
async def test_fetch_page_html(adapter):
    adapter._html = SAMPLE_HTML
    html = await adapter.fetch_page_html()
    assert "listing-item" in html
