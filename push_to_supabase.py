import time
from datetime import datetime, timezone
from supabase import create_client, Client
import random

# Supabase credentials
SUPABASE_URL = "https://jqoukirgtuhkuibvulni.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Impxb3VraXJndHVoa3VpYnZ1bG5pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDUwNDk0MDYsImV4cCI6MjA2MDYyNTQwNn0.Cw-OxxX3iZgXbDdTXvqfsF6iFjaec2BxfAFNcKmRxs8"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEVICE_ID = "RP1"
SITE_NAME = "SiteA"

# Sensor definitions: sensor_type -> sensor_ids
SENSOR_MAP = {
    "turbidity": ["Sensor1", "Sensor2"],
    # Add more sensor types as needed
}

CONFIG_CACHE = {}  # sensor_type -> (timestamp, config)

def get_config(sensor_type):
    now = time.time()
    cache = CONFIG_CACHE.get(sensor_type)

    if cache and now - cache[0] < 10:
        return cache[1]

    try:
        response = supabase.table("device_config") \
            .select("interval_sec, enabled") \
            .eq("device_id", DEVICE_ID) \
            .eq("sensor_type", sensor_type) \
            .execute()

        data = response.data

        if len(data) != 1:
            CONFIG_CACHE[sensor_type] = (now, None)
            return None

        CONFIG_CACHE[sensor_type] = (now, data[0])
        return data[0]

    except Exception as e:
        print(f"[ERROR] {sensor_type}: Could not fetch config: {e}")
        return None

def round_timestamp(interval_sec):
    now = datetime.now(timezone.utc)
    rounded = round(now.timestamp() / interval_sec) * interval_sec
    return datetime.fromtimestamp(rounded, tz=timezone.utc).isoformat()

def read_sensor(sensor_type, sensor_id):
    raw_value = random.randint(14000, 16000)
    voltage = round(3.3 * raw_value / 20000, 2)
    return raw_value, voltage

def upload_batch(sensor_data, sensor_type, timestamp):
    try:
        for entry in sensor_data:
            entry.update({
                "timestamp": timestamp,
                "site": SITE_NAME,
                "sensor_type": sensor_type
            })
        supabase.table("turbidity_data").insert(sensor_data).execute()
    except Exception as e:
        print(f"[ERROR] Failed to upload {sensor_type} batch: {e}")

if __name__ == "__main__":
    last_run = {}

    while True:
        for sensor_type, sensor_ids in SENSOR_MAP.items():
            config = get_config(sensor_type)
            if not config or not config["enabled"]:
                continue

            interval = config["interval_sec"]
            now = time.time()
            last = last_run.get(sensor_type, 0)

            if now - last >= interval:
                # Use rounded timestamp for alignment
                timestamp = round_timestamp(interval)

                sensor_data = []
                for sensor_id in sensor_ids:
                    raw, volt = read_sensor(sensor_type, sensor_id)
                    sensor_data.append({
                        "sensor_id": sensor_id,
                        "raw_value": raw,
                        "voltage": volt
                    })

                upload_batch(sensor_data, sensor_type, timestamp)
                last_run[sensor_type] = now

        time.sleep(1)
