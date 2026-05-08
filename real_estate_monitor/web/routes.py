from __future__ import annotations

import asyncio
import os

from flask import jsonify, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from real_estate_monitor.database import get_session
from real_estate_monitor.models.models import Listing, ListingDuplicate, ListingEvent, Source
from real_estate_monitor.web.auth import login, login_required, logout
from real_estate_monitor.services.runner import RunnerService


def register_routes(app):
    app.add_url_rule("/login", "login", login, methods=["GET", "POST"])
    app.add_url_rule("/logout", "logout", logout, methods=["GET"])
    app.add_url_rule("/", "index", index, methods=["GET"])
    app.add_url_rule("/listings", "listings", listings, methods=["GET"])
    app.add_url_rule("/favorites", "favorites", favorites, methods=["GET"])
    app.add_url_rule("/events", "events", events, methods=["GET"])
    app.add_url_rule(
        "/events/<int:event_id>/toggle-verify",
        "toggle_verify",
        toggle_verify,
        methods=["POST"],
    )
    app.add_url_rule("/run/<int:source_id>", "run_source", run_source, methods=["POST"])
    app.add_url_rule("/run-all", "run_all", run_all, methods=["POST"])
    app.add_url_rule(
        "/listings/<int:listing_id>/toggle-favorite",
        "toggle_favorite",
        toggle_favorite,
        methods=["POST"],
    )
    app.add_url_rule("/duplicates", "duplicates", duplicates_view, methods=["GET"])
    app.add_url_rule(
        "/duplicates/<int:dup_id>/review",
        "review_duplicate",
        review_duplicate,
        methods=["POST"],
    )


@login_required
def index():
    db_session = get_session()
    unverified_events = (
        db_session.query(ListingEvent)
        .options(joinedload(ListingEvent.listing), joinedload(ListingEvent.source))
        .filter(ListingEvent.verified == False)
        .order_by(ListingEvent.created_at.desc())
        .limit(50)
        .all()
    )

    total_listings = db_session.query(Listing).count()
    total_events = db_session.query(ListingEvent).count()
    unverified_count = (
        db_session.query(ListingEvent).filter(ListingEvent.verified == False).count()
    )
    favorite_count = (
        db_session.query(Listing).filter(Listing.is_favorite == True).count()
    )
    sources = db_session.query(Source).filter(Source.enabled == True).all()
    favorites = (
        db_session.query(Listing)
        .options(joinedload(Listing.source))
        .filter(Listing.is_favorite == True)
        .order_by(Listing.created_at.desc())
        .limit(12)
        .all()
    )
    duplicate_count = (
        db_session.query(ListingDuplicate)
        .filter(ListingDuplicate.confirmed == None)
        .count()
    )

    db_session.close()
    return render_template(
        "index.html",
        events=unverified_events,
        total_listings=total_listings,
        total_events=total_events,
        unverified_count=unverified_count,
        favorite_count=favorite_count,
        favorites=favorites,
        sources=sources,
        duplicate_count=duplicate_count,
    )


@login_required
def favorites():
    db_session = get_session()
    favorites = (
        db_session.query(Listing)
        .options(joinedload(Listing.source))
        .filter(Listing.is_favorite == True)
        .order_by(Listing.created_at.desc())
        .all()
    )
    db_session.close()
    return render_template("favorites.html", listings=favorites)


@login_required
def listings():
    db_session = get_session()
    query = (
        db_session.query(Listing)
        .options(joinedload(Listing.source))
        .filter(Listing.is_active == True)
    )

    source_id = request.args.get("source", type=int)
    verified = request.args.get("verified")
    search = request.args.get("search", "")

    if source_id:
        query = query.filter(Listing.source_id == source_id)
    if verified == "yes":
        query = query.join(ListingEvent).filter(ListingEvent.verified == True)
    elif verified == "no":
        query = query.join(ListingEvent).filter(ListingEvent.verified == False)
    if search:
        query = query.filter(
            Listing.title.ilike(f"%{search}%") | Listing.address.ilike(f"%{search}%")
        )

    listings = query.order_by(Listing.created_at.desc()).limit(100).all()
    sources = db_session.query(Source).filter(Source.enabled == True).all()

    db_session.close()
    return render_template("listings.html", listings=listings, sources=sources)


@login_required
def events():
    db_session = get_session()
    query = db_session.query(ListingEvent).options(
        joinedload(ListingEvent.listing), joinedload(ListingEvent.source)
    )

    verified = request.args.get("verified")
    source_id = request.args.get("source", type=int)
    event_type = request.args.get("type", "")

    if verified == "yes":
        query = query.filter(ListingEvent.verified == True)
    elif verified == "no":
        query = query.filter(ListingEvent.verified == False)
    if source_id:
        query = query.filter(ListingEvent.source_id == source_id)
    if event_type:
        query = query.filter(ListingEvent.event_type == event_type)

    events = query.order_by(ListingEvent.created_at.desc()).limit(100).all()
    sources = db_session.query(Source).all()

    db_session.close()
    return render_template("events.html", events=events, sources=sources)


@login_required
def toggle_verify(event_id):
    db_session = get_session()
    event = db_session.get(ListingEvent, event_id)
    if event:
        event.verified = not event.verified
        db_session.commit()
        result = event.verified
    else:
        result = False
    db_session.close()
    return jsonify({"verified": result})


@login_required
def run_source(source_id):
    db_session = get_session()
    source = db_session.get(Source, source_id)
    source_name = source.name if source else "Unknown"
    db_session.close()

    def _run():
        runner = RunnerService()
        asyncio.run(runner.run_source(source_id))

    import threading

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "source": source_name})


@login_required
def run_all():
    def _run():
        runner = RunnerService()
        asyncio.run(runner.run_all())

    import threading

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@login_required
def toggle_favorite(listing_id):
    db_session = get_session()
    listing = db_session.get(Listing, listing_id)
    if listing:
        listing.is_favorite = not listing.is_favorite
        db_session.commit()
        result = listing.is_favorite
    else:
        result = False
    db_session.close()
    return jsonify({"favorite": result})


@login_required
def duplicates_view():
    db_session = get_session()
    pairs = (
        db_session.query(ListingDuplicate)
        .options(
            joinedload(ListingDuplicate.listing_a).joinedload(Listing.source),
            joinedload(ListingDuplicate.listing_b).joinedload(Listing.source),
        )
        .filter(ListingDuplicate.confirmed == None)
        .order_by(ListingDuplicate.score.desc(), ListingDuplicate.created_at.desc())
        .all()
    )
    db_session.close()
    return render_template("duplicates.html", pairs=pairs)


@login_required
def review_duplicate(dup_id):
    action = request.json.get("action")  # "confirm" or "reject"
    if action not in ("confirm", "reject"):
        return jsonify({"error": "invalid action"}), 400
    db_session = get_session()
    dup = db_session.get(ListingDuplicate, dup_id)
    if dup:
        dup.confirmed = action == "confirm"
        db_session.commit()
    db_session.close()
    return jsonify({"ok": True})
