from __future__ import annotations

from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from real_estate_monitor.adapters.base import BaseAdapter
from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.browser import BrowserWrapper
from real_estate_monitor.services.money_parser import parse_money
from real_estate_monitor.services.property_extractor import (
    extract_area,
    extract_bathrooms,
    extract_bedrooms,
    extract_parking,
)
from real_estate_monitor.services.text_utils import normalize_text


class PlaywrightBSAdapter(BaseAdapter):
    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self.config = source_config.get("config", {})
        self.fields = self.config.get("fields", {})
        self.headless = self.config.get("headless", True)
        self.wait_selector = self.config.get("wait_selector", ".listing-item")
        self.wait_timeout = self.config.get("wait_timeout", 10000)
        self.listing_selector = self.config.get("listing_selector", ".listing-item")
        self.pagination_type = self.config.get("pagination_type", "none")
        self.pagination_config = self.config.get("pagination", {})
        self.max_pages = self.pagination_config.get("max_pages", 20)
        self.scroll_to_load_images = self.config.get("scroll_to_load_images", False)
        self._htmls: list[str] = []

    async def _trigger_lazy_images(self, page) -> None:
        if not self.scroll_to_load_images:
            return
        await page.evaluate("""
            async () => {
                const step = window.innerHeight * 0.8;
                const total = document.body.scrollHeight;
                for (let y = step; y <= total; y += step) {
                    window.scrollTo(0, y);
                    await new Promise(r => setTimeout(r, 150));
                }
                window.scrollTo(0, 0);
            }
        """)
        await page.wait_for_timeout(800)

    async def _load_page(self) -> str:
        async with BrowserWrapper(headless=self.headless) as browser:
            page = await browser.new_page()
            await page.goto(self.source_config["url"], timeout=self.wait_timeout)
            await page.wait_for_selector(self.wait_selector, timeout=self.wait_timeout)
            await self._trigger_lazy_images(page)

            if self.pagination_type == "scroll":
                await self._handle_scroll_pagination(page)
                self._htmls = [await page.content()]
            elif self.pagination_type == "click":
                self._htmls = await self._handle_click_pagination(page)
            else:
                self._htmls = [await page.content()]
            return self._htmls[0] if self._htmls else ""

    async def _handle_scroll_pagination(self, page) -> None:
        scroll_pause = self.pagination_config.get("scroll_pause", 1.5)
        scroll_selector = self.pagination_config.get("scroll_selector")
        prev_count = len(await page.query_selector_all(self.listing_selector))
        no_change = 0

        for _ in range(self.max_pages):
            if scroll_selector:
                el = await page.query_selector(scroll_selector)
                if el:
                    await el.scroll_into_view_if_needed()
                else:
                    await page.mouse.wheel(0, 10000)
            else:
                await page.mouse.wheel(0, 10000)

            await page.wait_for_timeout(scroll_pause * 1000)
            curr_count = len(await page.query_selector_all(self.listing_selector))

            if curr_count == prev_count:
                no_change += 1
                if no_change >= 3:
                    break
            else:
                no_change = 0
            prev_count = curr_count

    async def _handle_click_pagination(self, page) -> list[str]:
        next_selector = self.pagination_config.get(
            "next_button", ".jet-filters-pagination .prev-next.next"
        )
        wait_after_click = self.pagination_config.get("wait_after_click", 2.0)
        max_stale = self.pagination_config.get("max_stale_clicks", 4)

        all_html = [await page.content()]
        all_urls = set()
        for el in await page.query_selector_all(self.listing_selector):
            link = await el.query_selector("a[href]")
            if link:
                all_urls.add(await link.get_attribute("href"))

        stale = 0
        for _ in range(self.max_pages * 2):
            try:
                if not await page.query_selector(next_selector):
                    break

                await page.click(next_selector, timeout=5000, force=True)
                await page.wait_for_timeout(wait_after_click * 1000)

                try:
                    await page.wait_for_selector(
                        self.wait_selector,
                        timeout=self.wait_timeout,
                        state="attached",
                    )
                except Exception:
                    break

                current_urls = set()
                for el in await page.query_selector_all(self.listing_selector):
                    link = await el.query_selector("a[href]")
                    if link:
                        current_urls.add(await link.get_attribute("href"))

                if current_urls - all_urls:
                    all_urls.update(current_urls)
                    all_html.append(await page.content())
                    stale = 0
                else:
                    stale += 1
                    if stale >= max_stale:
                        break
            except Exception:
                break

        return all_html

    async def _load_url_pages(self) -> list[str]:
        url_pattern = self.pagination_config.get("url_pattern", "")
        if not url_pattern:
            return []

        htmls = []
        for page_num in range(1, self.max_pages + 1):
            url = url_pattern.format(page=page_num)
            async with BrowserWrapper(headless=self.headless) as browser:
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=self.wait_timeout)
                    await page.wait_for_selector(
                        self.wait_selector, timeout=self.wait_timeout
                    )
                    await self._trigger_lazy_images(page)
                    htmls.append(await page.content())
                except Exception:
                    break
        return htmls

    async def fetch_page_html(self) -> str:
        if not self._htmls:
            await self._load_page()
        return self._htmls[0] if self._htmls else ""

    async def fetch_all_pages_html(self) -> list[str]:
        if self.pagination_type == "url":
            return await self._load_url_pages()
        if not self._htmls:
            await self._load_page()
        return self._htmls

    _TRACKING_PARAMS = frozenset({
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "gclsrc", "dclid", "msclkid",
        "_ga", "_gl", "_gcl_aw", "_gcl_au", "_gcl_dc",
        "session", "sid", "token", "ts", "_t", "_", "rand", "random",
        "nc", "r", "d", "v", "ver", "cb", "t", "cache",
    })

    @staticmethod
    def _normalize_url(url: str | None) -> str | None:
        if not url:
            return url
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in PlaywrightBSAdapter._TRACKING_PARAMS
        ]
        cleaned_query = "&".join(f"{k}={v}" for k, v in params)
        normalized = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path.rstrip("/"),
            parsed.params, cleaned_query, parsed.fragment,
        ))
        return normalized.rstrip("?&")

    def _extract_text(self, element, selector: str) -> str | None:
        if not selector:
            return None
        el = element.select_one(selector)
        if el:
            return normalize_text(el.get_text())
        if selector.startswith("[data-") and element.get(selector.strip("[]")):
            return normalize_text(element.get(selector.strip("[]")))
        return None

    def _extract_attr(self, element, selector: str, attr: str) -> str | None:
        if not selector:
            return None
        el = element.select_one(selector)
        if el and el.get(attr):
            return el.get(attr)
        if selector.startswith("[data-") and element.get(selector.strip("[]")):
            return element.get(selector.strip("[]"))
        return None

    def _parse_listing(self, element) -> NormalizedListing:
        title = self._extract_text(element, self.fields.get("title", ""))
        price_raw = self._extract_text(element, self.fields.get("price", ""))
        price = parse_money(price_raw)
        address = self._extract_text(element, self.fields.get("address", ""))
        url = self._extract_attr(element, self.fields.get("url", ""), "href")
        if not url and element.name == "a" and element.get("href"):
            url = element.get("href")
        if url and not url.startswith(("http://", "https://")):
            url = urljoin(self.source_config["url"], url)
        bedrooms_raw = self._extract_text(element, self.fields.get("bedrooms", ""))
        bathrooms_raw = self._extract_text(element, self.fields.get("bathrooms", ""))
        parking_raw = self._extract_text(element, self.fields.get("parking", ""))
        area_raw = self._extract_text(element, self.fields.get("area", ""))
        description = self._extract_text(element, self.fields.get("description", ""))
        image_url = self._extract_attr(element, self.fields.get("image_url", ""), "src")
        if image_url and not image_url.startswith(("http://", "https://")):
            image_url = urljoin(self.source_config["url"], image_url)
        property_code = self._extract_text(element, self.fields.get("property_code", ""))

        id_url = self._normalize_url(url)
        external_id = property_code or id_url or title or ""

        return NormalizedListing(
            external_id=external_id,
            title=title,
            price=price,
            address=address,
            url=url,
            bedrooms=extract_bedrooms(bedrooms_raw),
            bathrooms=extract_bathrooms(bathrooms_raw),
            parking=extract_parking(parking_raw),
            area=extract_area(area_raw),
            description=description,
            image_url=image_url,
            property_code=property_code or None,
        )

    async def fetch_listings(self) -> list[NormalizedListing]:
        all_listings: list[NormalizedListing] = []
        seen_ids: set[str] = set()

        htmls = await self.fetch_all_pages_html()

        for html in htmls:
            if not html:
                continue
            soup = BeautifulSoup(html, "lxml")
            elements = soup.select(self.listing_selector)
            for el in elements:
                listing = self._parse_listing(el)
                if listing.external_id not in seen_ids:
                    seen_ids.add(listing.external_id)
                    all_listings.append(listing)

        return all_listings
