import time
from datetime import datetime, timezone
from supabase import create_client, Client
import random

# Supabase credentials
SUPABASE_URL = "https://jqoukirgtuhkuibvulni.supabase.co"
SUPABASE_KEY = "your-new-secret-key-here"  # replace with fresh token

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEVICE_ID = "RP1"
SITE_NAME = "SiteA"

# Sensor definitions: sensor_type -> sensor_ids
SENSOR_MAP = {
    "turbidity": ["Sensor1", "Sensor2"],
    # Add more types as needed
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
        print(f"[DEBUG] Config for {sensor_type}: {data}")

        if len(data) != 1:
            print(f"[WARN] {sensor_type}: expected 1 row, got {len(data)} — skipping")
            CONFIG_CACHE[sensor_type] = (now, None)
            return None

        CONFIG_CACHE[sensor_type] = (now, data[0])
        return data[0]

    except Exception as e:
        print(f"[ERROR] {sensor_type}: Could not fetch config: {e}")
        return None

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
        print(f"[{timestamp}] Uploaded batch for {sensor_type}")
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
                # Use one timestamp per batch, in ISO format with milliseconds
                timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')

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
