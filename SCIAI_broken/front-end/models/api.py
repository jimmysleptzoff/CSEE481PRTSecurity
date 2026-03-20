# api.py
"""
Frontend API module - Direct database access for cart commands

CHANGE: Removed HTTP-based communication to backend Server.py
OLD: Used requests.post() to send commands to localhost:2650
NEW: Writes directly to database tables that backend polls

Architecture:
- send_cart_to_station() -> Updates PRTCarts.destination directly
- remove_cart() -> Inserts into PRTRemoveCart table

Backend (main.py) reads from these tables:
- PRTCarts: Read when PLC requests routing info for a cart
- PRTRemoveCart: Polled for new removal commands
"""

from models.db import (
    update_cart_destination,
    insert_remove_cart_command,
    log_event
)


def send_cart_to_station(cart_id, station_id):
    """
    Update cart destination directly in database.
    Backend will read this when PLC requests routing info.

    :param cart_id: Cart barcode (e.g., "0001" or "1")
    :param station_id: Station name (e.g., "Station_1")
    """
    station_map = {
        "Station_1": 1,
        "Station_2": 2,
        "Station_3": 3,
        "Station_4": 4
    }
    destination = station_map.get(station_id)

    if destination is None:
        print(f"Invalid station: {station_id}")
        return False

    # Normalize barcode to 4 digits to match PRTCarts (e.g., "1" -> "0001")
    barcode = str(cart_id).zfill(4) if cart_id else cart_id

    # Update destination in PRTCarts table
    success = update_cart_destination(barcode, destination)

    # Log the action to cart_logs for activity tracking
    if success:
        log_event(barcode, station_id, "Destination Updated", "Command")
        print(f"Cart {barcode} destination set to {station_id}")
    else:
        log_event(barcode, station_id, "Update Failed", "Error")
        print(f"Failed to update cart {barcode} destination")

    return success


def remove_cart(cart_id, area):
    """
    Insert cart removal command into database.
    Backend will poll PRTRemoveCart and process the command.

    :param cart_id: Cart barcode (e.g., "0001" or "1")
    :param area: Removal area number (5-9)
    """
    # Normalize barcode to 4 digits to match PRTCarts
    barcode = str(cart_id).zfill(4) if cart_id else cart_id

    # Insert removal command into PRTRemoveCart table
    success = insert_remove_cart_command(barcode, area)

    # Log the action to cart_logs for activity tracking
    if success:
        log_event(barcode, f"Remove_Area_{area}", "Removal Requested", "Command")
        print(f"Cart {barcode} removal requested to area {area}")
    else:
        log_event(barcode, f"Remove_Area_{area}", "Removal Failed", "Error")
        print(f"Failed to request removal for cart {barcode}")

    return success
