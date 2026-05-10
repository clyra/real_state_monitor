from __future__ import annotations

import json
import urllib.request

from real_estate_monitor.adapters.base import BaseAdapter
from real_estate_monitor.schemas.schemas import NormalizedListing
from real_estate_monitor.services.text_utils import normalize_text

_SEARCH_API = "https://55mrb5weq7.execute-api.us-east-1.amazonaws.com/hml/properties/search/main"

_BASE_BODY = {
    "business": "Locacao",
    "business_subfilter": "Mensal",
    "reference": "",
    "city": "",
    "country": "Brasil",
    "district": [],
    "property_type": ["Casa-Residencial", "Sobrado-Residencial"],
    "property_type_combo": [],
    "bedrooms": [],
    "garage": [],
    "bathrooms": [],
    "area_max": "0,00 m²",
    "area_min": "0,00 m²",
    "address": None,
    "address_number": None,
    "open_search": "",
    "in_condominium": False,
    "include_condominium_price": False,
    "conveniences": [],
    "recreation": [],
    "facilities": [],
    "rooms": [],
    "idLoja": None,
    "mensal": None,
    "showStoreImmobiles": True,
    "order": "price_desc",
    "size": 12,
    "fields": [
        "IsFeiraoApolar", "tipo", "transacao", "finalidade", "cidade", "bairro",
        "referencia", "Quartos", "condominio", "garagem", "dormitorios",
        "areaterreno", "area_total", "banheiro", "ValorAnterior",
        "valor_considerado", "situacao", "foto_principal", "endereco",
        "linksite", "popup_fotos", "descricao", "vlrcondominio",
        "lojacelular", "lojatelefone", "idtipomoeda", "valor_total",
    ],
    "area": [0, 0],
}


def _post_json(body: dict) -> dict:
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        _SEARCH_API,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.apolar.com.br/",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


class ApolarAdapter(BaseAdapter):
    """Adapter for Apolar Imóveis — uses their internal Elasticsearch POST API."""

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        cfg = source_config.get("config", {})
        self.min_price: int = cfg.get("min_price", 2000)
        self.max_price: int = cfg.get("max_price", 4000)
        self._raw_json: str = ""

    @staticmethod
    def _fmt_price(value: int) -> str:
        """Format integer as Brazilian currency string: 2000 → 'R$ 2.000,00'."""
        return f"R$ {value:,}".replace(",", ".") + ",00"

    def _fetch_all(self) -> list[dict]:
        body = {
            **_BASE_BODY,
            "price_min": self._fmt_price(self.min_price),
            "price_max": self._fmt_price(self.max_price),
            "price": [self.min_price, self.max_price],
        }

        results: list[dict] = []
        seen_ids: set = set()
        scroll_id: str | None = None

        for _ in range(30):  # max 30 pages × 12 = 360 listings
            if scroll_id:
                body["scroll_id"] = scroll_id
            elif "scroll_id" in body:
                del body["scroll_id"]

            data = _post_json(body)
            self._raw_json = json.dumps(data, ensure_ascii=False)

            page_items = data.get("data", [])
            if not page_items:
                break

            # De-duplicate by referencia (safety net against cycling)
            new_items = [i for i in page_items if i.get("referencia") not in seen_ids]
            if not new_items:
                break
            seen_ids.update(i.get("referencia") for i in new_items)
            results.extend(new_items)

            scroll_id = data.get("scroll_id")
            total = data.get("total", 0)
            if len(results) >= total:
                break

        return results

    def _parse_item(self, item: dict) -> NormalizedListing | None:
        ref = item.get("referencia")
        if not ref:
            return None

        # Skip already-rented properties
        if item.get("situacao") == "Locado":
            return None

        price = item.get("valor_considerado")
        address_parts = [item.get("endereco") or "", item.get("bairro") or ""]
        address = ", ".join(p for p in address_parts if p)
        beds = item.get("Quartos") or item.get("dormitorios")

        return NormalizedListing(
            external_id=str(ref),
            title=normalize_text(
                f"{item.get('tipo', 'Imóvel')} – {item.get('bairro', '')}"
            ),
            price=float(price) if price is not None else None,
            address=normalize_text(address) or None,
            url=item.get("linksite") or None,
            bedrooms=int(beds) if beds is not None else None,
            bathrooms=int(item["banheiro"]) if item.get("banheiro") is not None else None,
            parking=int(item["garagem"]) if item.get("garagem") is not None else None,
            area=float(item["area_total"]) if item.get("area_total") is not None else None,
            image_url=item.get("foto_principal") or None,
            property_code=str(ref),
        )

    async def fetch_listings(self) -> list[NormalizedListing]:
        items = self._fetch_all()
        results = []
        for item in items:
            listing = self._parse_item(item)
            if listing:
                results.append(listing)
        return results

    async def fetch_page_html(self) -> str:
        return self._raw_json
