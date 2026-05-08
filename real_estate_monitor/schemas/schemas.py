from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class SourceConfig(BaseModel):
    id: str | None = None
    name: str
    url: str | None = None
    url_template: str | None = None
    filters: dict = Field(default_factory=dict)
    adapter: str = "playwright_bs"
    enabled: bool = True
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def resolve_url(self) -> "SourceConfig":
        if self.url_template and not self.url:
            try:
                self.url = self.url_template.format(**self.filters)
            except KeyError as e:
                raise ValueError(f"Filtro ausente no url_template: {e}") from e
        if not self.url:
            raise ValueError("É necessário fornecer 'url' ou 'url_template' + 'filters'")
        return self


class NormalizedListing(BaseModel):
    external_id: str
    title: str | None = None
    price: float | None = None
    currency: str = "BRL"
    address: str | None = None
    url: str | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    parking: int | None = None
    area: float | None = None
    description: str | None = None
    image_url: str | None = None
