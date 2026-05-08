from __future__ import annotations

import asyncio

import typer

from real_estate_monitor.configs.config_loader import load_sources, sync_sources_to_db
from real_estate_monitor.database import get_session, init_db as db_init_db
from real_estate_monitor.models.models import Listing, ListingEvent, Source
from real_estate_monitor.services.runner import RunnerService
from real_estate_monitor.services.text_utils import extract_neighborhood

app = typer.Typer(help="Real Estate Monitor CLI")


@app.command()
def migrate_db():
    """Apply pending database schema migrations."""
    from sqlalchemy import text

    session = get_session()
    engine = session.get_bind()

    migrations = [
        (
            "ALTER TABLE listing_events ADD COLUMN verified BOOLEAN DEFAULT 0 NOT NULL",
            "Added 'verified' column to listing_events.",
        ),
        (
            "ALTER TABLE listings ADD COLUMN is_favorite BOOLEAN DEFAULT 0 NOT NULL",
            "Added 'is_favorite' column to listings.",
        ),
        (
            "ALTER TABLE sources ADD COLUMN config_id TEXT",
            "Added 'config_id' column to sources.",
        ),
        (
            "ALTER TABLE listings ADD COLUMN missing_runs_count INTEGER NOT NULL DEFAULT 0",
            "Added 'missing_runs_count' column to listings.",
        ),
    ]

    for sql, msg in migrations:
        try:
            conn = engine.connect()
            conn.execute(text(sql))
            conn.commit()
            conn.close()
            typer.echo(msg)
        except Exception:
            typer.echo(f"Já aplicada ou não necessária: {msg}")

    # Create any new tables (e.g. listing_duplicates) without touching existing ones
    from real_estate_monitor.models.models import Base
    Base.metadata.create_all(engine)
    typer.echo("Tabelas novas criadas (se necessário).")

    session.close()
    typer.echo("Migration complete.")


@app.command()
def init_db():
    """Initialize the database."""
    db_init_db()
    typer.echo("Database initialized.")


@app.command()
def list_sources():
    """List all configured sources."""
    session = get_session()
    sources = sync_sources_to_db(load_sources(), session)
    for src in sources:
        status = "enabled" if src.enabled else "disabled"
        typer.echo(f"[{src.id}] {src.name} - {src.url} ({status})")
    session.close()


@app.command()
def run_source(source_id: int):
    """Run scraping for a specific source."""
    runner = RunnerService()
    asyncio.run(runner.run_source(source_id))


@app.command()
def dry_run_source(source_id: int):
    """Run scraping for a source without persisting results."""
    runner = RunnerService()
    asyncio.run(runner.dry_run_source(source_id))


@app.command()
def run_all():
    """Run scraping for all enabled sources."""
    runner = RunnerService()
    asyncio.run(runner.run_all())


@app.command()
def show_events(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of events to show"),
    verified: str = typer.Option(
        None,
        "--verified",
        "-v",
        help="Filter by verified status: yes, no, or omit for all",
    ),
    source_id: int = typer.Option(
        None,
        "--source",
        "-s",
        help="Filter by source ID",
    ),
    show_url: bool = typer.Option(
        False,
        "--url",
        "-u",
        help="Show listing URL",
    ),
):
    """Show recent listing events."""
    session = get_session()
    query = session.query(ListingEvent)

    if verified is not None:
        if verified.lower() in ("yes", "true", "1"):
            query = query.filter(ListingEvent.verified == True)
        elif verified.lower() in ("no", "false", "0"):
            query = query.filter(ListingEvent.verified == False)
        else:
            typer.echo(
                "Invalid value for --verified. Use: yes, no, true, false, 1, or 0."
            )
            session.close()
            return
    if source_id is not None:
        query = query.filter(ListingEvent.source_id == source_id)

    events = query.order_by(ListingEvent.created_at.desc()).limit(limit).all()
    if not events:
        typer.echo("No events found.")
        session.close()
        return

    for event in events:
        listing_title = "N/A"
        listing_url = ""
        if event.listing:
            listing_title = event.listing.title or event.listing.external_id
            if show_url and event.listing.url:
                listing_url = f" | {event.listing.url}"
        verified_mark = "[x]" if event.verified else "[ ]"
        typer.echo(
            f"[{event.id}] {verified_mark} [{event.created_at}] {event.event_type} - {listing_title}"
            f" (source: {event.source.name}){listing_url}"
        )
    session.close()


@app.command()
def show_event_details(
    event_id: int = typer.Argument(..., help="ID of the event to show details for"),
):
    """Show detailed information for a specific event."""
    session = get_session()
    event = session.get(ListingEvent, event_id)
    if not event:
        typer.echo(f"Event {event_id} not found.")
        session.close()
        return

    typer.echo(f"{'=' * 60}")
    typer.echo(f"Event ID: {event.id}")
    typer.echo(f"Type: {event.event_type}")
    typer.echo(f"Created: {event.created_at}")
    typer.echo(f"Source: {event.source.name}")
    typer.echo(f"Verified: {'Yes' if event.verified else 'No'}")
    if event.old_price is not None:
        typer.echo(f"Old Price: R$ {event.old_price:,.2f}")
    if event.new_price is not None:
        typer.echo(f"New Price: R$ {event.new_price:,.2f}")
    if event.snapshot_path:
        typer.echo(f"Snapshot: {event.snapshot_path}")
    if event.details:
        typer.echo(f"Details: {event.details}")

    if event.listing:
        listing = event.listing
        typer.echo(f"{'=' * 60}")
        typer.echo("Listing Details:")
        typer.echo(f"  External ID: {listing.external_id}")
        typer.echo(f"  Title: {listing.title}")
        typer.echo(
            f"  Price: R$ {listing.price:,.2f}" if listing.price else "  Price: N/A"
        )
        typer.echo(f"  Address: {listing.address}")
        typer.echo(f"  URL: {listing.url}")
        typer.echo(f"  Bedrooms: {listing.bedrooms}")
        typer.echo(f"  Bathrooms: {listing.bathrooms}")
        typer.echo(f"  Parking: {listing.parking}")
        typer.echo(f"  Area: {listing.area} m²" if listing.area else "  Area: N/A")
        typer.echo(f"  Active: {listing.is_active}")
        typer.echo(f"  Image: {listing.image_url}")
        if listing.description:
            typer.echo(f"  Description: {listing.description[:200]}")
    typer.echo(f"{'=' * 60}")
    session.close()


@app.command()
def reset_source(source_id: int):
    """Delete all listings and events for a specific source."""
    session = get_session()
    source = session.get(Source, source_id)
    if not source:
        typer.echo(f"Source {source_id} not found.")
        session.close()
        return

    listings = session.query(Listing).filter(Listing.source_id == source_id).all()
    listing_ids = [l.id for l in listings]
    if listing_ids:
        deleted_events = (
            session.query(ListingEvent)
            .filter(ListingEvent.listing_id.in_(listing_ids))
            .delete(synchronize_session=False)
        )
    else:
        deleted_events = 0

    deleted_listings = (
        session.query(Listing).filter(Listing.source_id == source_id).delete()
    )
    deleted_source_events = (
        session.query(ListingEvent)
        .filter(ListingEvent.source_id == source_id, ListingEvent.listing_id.is_(None))
        .delete(synchronize_session=False)
    )
    session.commit()
    session.close()

    typer.echo(f"Reset source: {source.name}")
    typer.echo(f"  Deleted {deleted_events} listing events")
    typer.echo(f"  Deleted {deleted_source_events} source-only events")
    typer.echo(f"  Deleted {deleted_listings} listings")


@app.command()
def reset_all():
    """Delete all listings and events from all sources."""
    session = get_session()
    deleted_events = session.query(ListingEvent).delete(synchronize_session=False)
    deleted_listings = session.query(Listing).delete(synchronize_session=False)
    session.commit()
    session.close()

    typer.echo("Reset all sources.")
    typer.echo(f"  Deleted {deleted_events} events")
    typer.echo(f"  Deleted {deleted_listings} listings")


@app.command()
def find_duplicates():
    """Detecta duplicatas entre fontes e salva no banco."""
    from real_estate_monitor.services.duplicate_service import DuplicateDetectionService

    svc = DuplicateDetectionService()
    new_pairs = svc.detect_all()
    svc.close()
    typer.echo(f"Detecção concluída. {new_pairs} novo(s) par(es) encontrado(s).")
    typer.echo("Use a interface web (/duplicates) para revisar.")


@app.command()
def favorite_listing(
    listing_id: int = typer.Argument(..., help="ID of the listing to favorite"),
):
    """Mark a listing as favorite."""
    session = get_session()
    listing = session.get(Listing, listing_id)
    if not listing:
        typer.echo(f"Listing {listing_id} not found.")
        session.close()
        return

    listing.is_favorite = True
    session.commit()
    session.close()
    typer.echo(f"Listing {listing_id} marked as favorite.")


@app.command()
def unfavorite_listing(
    listing_id: int = typer.Argument(..., help="ID of the listing to unfavorite"),
):
    """Remove a listing from favorites."""
    session = get_session()
    listing = session.get(Listing, listing_id)
    if not listing:
        typer.echo(f"Listing {listing_id} not found.")
        session.close()
        return

    listing.is_favorite = False
    session.commit()
    session.close()
    typer.echo(f"Listing {listing_id} removed from favorites.")


@app.command()
def list_favorites():
    """List all favorite listings."""
    session = get_session()
    favorites = session.query(Listing).filter(Listing.is_favorite == True).all()
    if not favorites:
        typer.echo("No favorite listings.")
        session.close()
        return

    for l in favorites:
        src = session.get(Source, l.source_id)
        src_name = src.name if src else "Unknown"
        typer.echo(
            f"[{l.id}] [{src_name}] {l.title or l.external_id} | R$ {l.price:,.2f}"
            if l.price
            else f"[{l.id}] [{src_name}] {l.title or l.external_id} | N/A"
        )
        if l.url:
            typer.echo(f"     {l.url}")
    session.close()


@app.command()
def inspect_source(
    url: str = typer.Argument(..., help="URL da página a inspecionar"),
    selector: str = typer.Option(
        "", "--selector", "-s", help="Testar um seletor CSS como container de listagem"
    ),
):
    """Analisa uma página e sugere seletores CSS para configurar um novo source."""
    asyncio.run(_inspect_source(url, selector))


async def _inspect_source(url: str, selector: str) -> None:
    import re
    from collections import Counter

    from bs4 import BeautifulSoup

    from real_estate_monitor.services.browser import BrowserWrapper

    typer.echo(f"Carregando {url} ...")
    async with BrowserWrapper(headless=True) as browser:
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        html = await page.content()

    soup = BeautifulSoup(html, "lxml")

    if selector:
        elements = soup.select(selector)
        typer.echo(f"\n{len(elements)} elemento(s) encontrado(s) com '{selector}'")
        if not elements:
            return
        typer.echo("\nEstrutura do primeiro elemento (tag.classe → texto/atributos):")
        typer.echo(f"{'=' * 70}")
        for child in elements[0].find_all(True):
            cls = ".".join(child.get("class", []))
            selector_hint = f".{cls}" if cls else child.name
            text = child.get_text(strip=True)[:80]
            attrs = []
            if child.get("href"):
                attrs.append(f'href="{child["href"][:60]}"')
            if child.get("src"):
                attrs.append(f'src="{child["src"][:60]}"')
            for data_attr in [a for a in child.attrs if a.startswith("data-")]:
                attrs.append(f'{data_attr}="{str(child[data_attr])[:40]}"')
            attr_str = f"  [{', '.join(attrs)}]" if attrs else ""
            if text or attrs:
                typer.echo(f"  {selector_hint:<45} {text}{attr_str}")
    else:
        class_counts: Counter = Counter()
        for el in soup.find_all(True):
            for cls in el.get("class", []):
                class_counts[cls] += 1

        typer.echo("\nTop 30 classes CSS mais frequentes:")
        typer.echo(f"{'=' * 50}")
        for cls, count in class_counts.most_common(30):
            typer.echo(f"  {count:4d}x  .{cls}")

        typer.echo("\nCandidatos a container de listagem (5+ elementos com texto de preço):")
        typer.echo(f"{'=' * 50}")
        price_re = re.compile(r"R\$\s*[\d]|[\d]{3,}[,.][\d]{2}")
        found_any = False
        for cls, count in class_counts.most_common(100):
            if count < 5:
                break
            elements = soup.select(f".{cls}")
            with_price = sum(1 for el in elements if price_re.search(el.get_text()))
            if with_price >= 3:
                typer.echo(f"  .{cls:<40}  {count} elementos, {with_price} com preço")
                found_any = True
        if not found_any:
            typer.echo("  Nenhum candidato óbvio encontrado.")

        typer.echo(
            "\nDica: use --selector '.nome-da-classe' para ver a estrutura interna de um elemento."
        )


if __name__ == "__main__":
    app()
