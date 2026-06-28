#!/usr/bin/env python3
"""Seed MongoDB with realistic synthetic agricultural data for ML training.

Generates 90 days of 10-min interval time series for 4 zones with:
  - Daily temperature sinusoid (18-35°C)
  - Soil moisture with irrigation events and natural dry-down
  - Rain events (random)
  - Humidity, pressure, wind
  - Valve state changes

Usage:
    python scripts/seed_data.py [--days 90] [--zones 4] [--clean]
"""

import argparse
import random
import math
import sys
import os
from datetime import datetime, timedelta

from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

random.seed(42)


def generate_zone_data(zone_name: str, days: int = 90, interval_min: int = 10):
    """Generate realistic agricultural time series for one zone."""
    client = MongoClient("mongodb://localhost:27017/")
    db = client["agricol_ts"]
    collection = db["mesures_capteurs"]

    start = datetime.utcnow() - timedelta(days=days)
    points_per_day = 1440 // interval_min
    total = days * points_per_day

    BASE_TEMP = {"sol_serre": 24, "champ_ble": 20, "verger": 22, "serre_tomates": 26}
    BASE_HUM = {"sol_serre": 60, "champ_ble": 55, "verger": 65, "serre_tomates": 70}

    base_temp = BASE_TEMP.get(zone_name, 22)
    base_hum = BASE_HUM.get(zone_name, 55)

    soil_moisture = 65.0  # start well-watered
    last_irrigation = -999
    irrigation_on = False
    valve_cycle_count = 0
    valve_open_since = None
    # For valve cycle detection
    last_valve_close = None
    valve_cycle_times = []

    batch = []
    BATCH_SIZE = 500

    print(f"  Génération {zone_name}... ", end="")

    for i in range(total):
        ts = start + timedelta(minutes=i * interval_min)
        hour = ts.hour
        day_progress = hour / 24.0

        # Temperature: sinusoid with random noise
        temp = base_temp + 8 * math.sin(math.pi * (day_progress - 0.35)) + random.gauss(0, 1.5)
        temp = round(max(5, min(45, temp)), 1)

        # Humidity: inverse of temperature + noise
        humid = base_hum - 15 * math.sin(math.pi * (day_progress - 0.35)) + random.gauss(0, 5)
        humid = round(max(20, min(98, humid)), 1)

        # Pressure: slight daily variation
        pressure = round(1013 + random.gauss(0, 5), 1)

        # Rain: random events
        rain = 0.0
        if random.random() < 0.015:  # ~1.5% chance per 10min
            rain = round(random.uniform(0.5, 8.0), 1)

        # Wind
        wind = round(abs(random.gauss(0, 8) + 3 * math.sin(2 * math.pi * day_progress)), 1)

        # --- Soil moisture model ---
        # Natural dry-down (faster during day when plants transpire)
        daytime_factor = 0.3 + 0.7 * max(0, math.sin(math.pi * (day_progress - 0.3)))
        dry_down = 0.02 + 0.08 * daytime_factor

        # Rain adds moisture
        rain_infiltration = rain * 0.4

        # Irrigation logic: if soil < 35%, irrigate for 20 min
        if soil_moisture < 35 and not irrigation_on:
            irrigation_on = True
            last_irrigation = i
            valve_open_since = ts
            valve_cycle_count += 1

        if irrigation_on:
            if (i - last_irrigation) * interval_min < 20:
                soil_moisture += 2.5  # irrigation rate per 10min
            else:
                irrigation_on = False
                if valve_open_since:
                    cycle_time = (ts - valve_open_since).total_seconds()
                    valve_cycle_times.append(cycle_time)
                    valve_open_since = None
                    last_valve_close = ts

        # Soil moisture can't exceed 100
        soil_moisture = min(100, soil_moisture - dry_down + rain_infiltration +
                            (1.5 if irrigation_on else 0))
        soil_moisture = round(max(5, soil_moisture), 1)

        # Irrigation flag for status
        irrigating = 1 if irrigation_on else 0

        doc = {
            "zone": zone_name,
            "timestamp": ts,
            "temperature": temp,
            "humidite": humid,
            "pression": pressure,
            "humidite_sol": soil_moisture,
            "pluie": rain,
            "vent": wind,
            "irrigation": irrigating,
        }

        # Add valve metadata for anomaly detection
        if valve_cycle_times:
            doc["vanne_cycles"] = valve_cycle_count
            doc["vanne_cycle_time"] = round(valve_cycle_times[-1])

        batch.append(doc)

        if len(batch) >= BATCH_SIZE:
            collection.insert_many(batch)
            batch.clear()
            print(".", end="", flush=True)

    if batch:
        collection.insert_many(batch)

    collection.create_index([("zone", 1), ("timestamp", -1)])
    print(f" {total} points OK")


def main():
    parser = argparse.ArgumentParser(description="Seed MongoDB with agricultural data")
    parser.add_argument("--days", type=int, default=90, help="Days of historical data")
    parser.add_argument("--zones", nargs="*",
                        default=["sol_serre", "champ_ble", "verger", "serre_tomates"],
                        help="Zone names to generate")
    parser.add_argument("--clean", action="store_true", help="Drop existing data first")
    args = parser.parse_args()

    client = MongoClient("mongodb://localhost:27017/")
    db = client["agricol_ts"]

    if args.clean:
        print("Nettoyage de la collection...")
        db["mesures_capteurs"].drop()

    existing = db["mesures_capteurs"].count_documents({})
    print(f"Collection: {existing} documents existants")
    print(f"Génération de {args.days} jours pour {len(args.zones)} zones...\n")

    for zone in args.zones:
        generate_zone_data(zone, days=args.days)
        print()

    total = db["mesures_capteurs"].count_documents({})
    print(f"\nTotal: {total} documents dans agricol_ts.mesures_capteurs")


if __name__ == "__main__":
    main()
