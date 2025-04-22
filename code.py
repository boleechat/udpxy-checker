import csv
import requests
import time
import re
import concurrent.futures
import threading
import shutil

# --- Configuration ---
INPUT_CSV_FILE = "new.csv" # Use the correct filename
OUTPUT_FILE = "valid_udpxy_sorted_from_csv.txt"
MULTICAST_PATH = "/udp/239.45.3.209:5140" # The specific UDP stream path

TEST_DURATION = 10 # Seconds to download for
REQUEST_TIMEOUT = TEST_DURATION + 10 # Allow time for connection + download duration + buffer
MAX_WORKERS = 15 # Adjust based on your connection/CPU
MIN_DOWNLOAD_KB = 10 # Minimum KB downloaded in TEST_DURATION to be considered valid
# --- End Configuration ---


def _read_targets_from_file(f):
    """Helper function to read targets from an opened file object."""
    targets = set()
    reader = csv.reader(f)
    try:
        header = next(reader) # Skip header row
        print(f"CSV Header: {header}") # Optional: print header to verify columns
        required_cols = 3 # Need at least ip (col 1) and port (col 2)
    except StopIteration:
        print("[⚠️] CSV file appears to be empty or has no header.")
        return set() # Return empty set
    except Exception as e:
        print(f"[❌] Error reading CSV header: {e}")
        return None # Indicate critical error

    for i, row in enumerate(reader):
        if len(row) >= required_cols:
            ip = row[1].strip()
            port_str = row[2].strip()
            if ip and port_str.isdigit():
                port = int(port_str)
                targets.add((ip, port))
            else:
                # print(f"Skipping row {i+2}: Invalid IP '{ip}' or Port '{port_str}'")
                pass
        else:
            # print(f"Skipping row {i+2}: Insufficient columns ({len(row)})")
            pass
    return targets


def parse_csv_for_targets(path):
    """
    Reads the CSV file and extracts unique (ip, port) targets.
    Tries UTF-8 first, then falls back to GBK.
    """
    targets = None
    try:
        print(f"[ℹ️] Trying to read '{path}' with UTF-8 encoding...")
        with open(path, mode='r', encoding='utf-8', newline='') as f:
            targets = _read_targets_from_file(f)
        print(f"[✅] Successfully read using UTF-8 encoding.")
    except UnicodeDecodeError:
        print(f"[⚠️] UTF-8 decoding failed. Trying GBK encoding...")
        try:
            with open(path, mode='r', encoding='gbk', newline='') as f:
                targets = _read_targets_from_file(f)
            print(f"[✅] Successfully read using GBK encoding.")
        except Exception as e:
            print(f"[❌] Failed to decode '{path}' using both UTF-8 and GBK. Error: {e}")
            return None
    except Exception as e:
        print(f"[❌] Error reading CSV file '{path}': {e}")
        return None

    if targets is None:
        print("[❌] Failed to extract targets from CSV.")
        return None

    unique_targets = list(targets)
    print(f"Found {len(unique_targets)} unique IP:Port combinations from {path}")
    return unique_targets


# --- measure_stream_for_duration function remains the same ---
def measure_stream_for_duration(url, duration=TEST_DURATION, timeout=REQUEST_TIMEOUT):
    """
    Measures how much data can be downloaded in a fixed duration.
    Returns:
        tuple: (url, total_kb_downloaded, avg_speed_kbs) or None if failed or below threshold.
    """
    total_read = 0
    start_time = time.time()
    r = None
    conn_error = False
    stop_event = threading.Event()

    def download_thread_func():
        nonlocal total_read, r, conn_error
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            _r = requests.get(url, timeout=timeout, stream=True, headers=headers)

            if _r.status_code != 200:
                conn_error = True
                if _r: _r.close() # Close connection if status not 200
                return

            r = _r
            for chunk in r.iter_content(chunk_size=8192):
                if stop_event.is_set():
                    break
                if chunk:
                    total_read += len(chunk)
            # Ensure connection closed after normal loop exit
            if r and hasattr(r, 'raw') and r.raw and not r.raw.closed:
                 r.close()

        except requests.exceptions.Timeout:
            conn_error = True
        except requests.exceptions.RequestException:
            conn_error = True
        except Exception:
             conn_error = True # Catch potential broader errors
        finally:
            # Ensure connection is closed if an error occurred before or during loop
             if r and hasattr(r, 'raw') and r.raw and not r.raw.closed:
                  r.close()


    download_thread = threading.Thread(target=download_thread_func)
    download_thread.start()
    download_thread.join(timeout=duration)
    stop_event.set()
    download_thread.join(timeout=2)

    end_time = time.time()
    actual_duration = end_time - start_time

    if conn_error or total_read == 0:
         return None

    calc_duration = min(actual_duration, duration)
    if calc_duration <= 0: calc_duration = 0.01

    total_kb = total_read / 1024
    avg_speed = total_kb / calc_duration

    if total_kb < MIN_DOWNLOAD_KB:
        # print(f"[📉] {url} | Low Download: {total_kb:.2f} KB < {MIN_DOWNLOAD_KB} KB. Discarding.") # Make less verbose
        return None

    print(f"[✅] {url} | {total_kb:.2f} KB in ~{duration:.1f}s | {avg_speed:.1f} KB/s") # Shorter success message
    return (url, total_kb, avg_speed)

def replace_m3u_ip(m3u_in, m3u_out, old_ip_port, new_ip_port):
    """
    替换m3u文件中所有http://old_ip:old_port/udp/xxx为http://new_ip:new_port/udp/xxx
    """
    with open(m3u_in, 'r', encoding='utf-8') as fin, open(m3u_out, 'w', encoding='utf-8') as fout:
        for line in fin:
            # 只替换以http://old_ip:old_port/udp/开头的行
            if line.startswith(f"http://{old_ip_port}/udp/"):
                # 提取udp部分
                udp_part = line.split('/udp/', 1)[-1]
                new_line = f"http://{new_ip_port}/udp/{udp_part}"
                fout.write(new_line)
            else:
                fout.write(line)

# --- main function remains the same ---
def main():
    targets = parse_csv_for_targets(INPUT_CSV_FILE)
    if not targets:
        print("No valid targets found in CSV. Exiting.")
        return

    print(f"\nTesting {len(targets)} potential URLs ({TEST_DURATION}s download, {REQUEST_TIMEOUT}s timeout, Min {MIN_DOWNLOAD_KB}KB)...\n")

    results = []
    urls_to_test = [f"http://{ip}:{port}{MULTICAST_PATH}" for ip, port in targets]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(measure_stream_for_duration, url, TEST_DURATION, REQUEST_TIMEOUT): url for url in urls_to_test}

        total_tasks = len(future_to_url)
        completed_tasks = 0

        for future in concurrent.futures.as_completed(future_to_url):
            completed_tasks += 1
            url = future_to_url[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as exc:
                print(f'[❗] {url} generated an exception during result processing: {exc}')

            print(f"--- Progress: {completed_tasks}/{total_tasks} ---", end='\r')
        print("\n--- All tasks completed ---")


    if not results:
        print("\nNo valid/performing URLs found after testing.")
        return

    # Sort primarily by total KB downloaded (descending)
    results.sort(key=lambda x: (-x[1], -x[2]))

    print(f"\n--- Sorting Results (Higher 'Total KB' downloaded in {TEST_DURATION}s is better) ---")

    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(f"# Results sorted by Total KB downloaded (descending) in {TEST_DURATION} seconds from {INPUT_CSV_FILE}.\n")
            f.write(f"# Multicast Path: {MULTICAST_PATH}\n")
            f.write(f"# Min Download Threshold: {MIN_DOWNLOAD_KB} KB\n")
            f.write(f"# Format: URL  # Total KB Downloaded, Avg Speed (KB/s)\n\n")
            for url, total_kb, speed in results:
                f.write(f"{url}  # {total_kb:.2f} KB, {speed:.2f} KB/s\n")
        print(f"\n✅ Test complete. {len(results)} valid URLs written to {OUTPUT_FILE}")
    except IOError as e:
        print(f"[❌] Error writing to output file '{OUTPUT_FILE}': {e}")
        return

    # 自动替换itvspeed.m3u.txt中的老ip为最快ip，生成新的itvspeed.m3u
    # 1. 找到最快的url
    fastest_url = results[0][0]  # e.g. http://223.167.74.79:4022/udp/239.45.3.209:5140
    # 2. 提取ip:port
    m = re.match(r"http://([\d.]+:\d+)/udp/", fastest_url)
    if not m:
        print("[❌] Fastest URL format error, cannot extract ip:port")
        return
    new_ip_port = m.group(1)
    # 3. 旧ip:port（假定为101.83.65.9:8899）
    old_ip_port = "101.83.65.9:8899"
    # 4. 替换
    replace_m3u_ip("itvspeed.m3u.txt", "itvspeed.m3u", old_ip_port, new_ip_port)
    print(f"\n✅ 替换完成，已生成新的itvspeed.m3u，所有频道已使用最快ip: {new_ip_port}")

if __name__ == "__main__":
    # Set INPUT_CSV_FILE correctly before running
    INPUT_CSV_FILE = "new.csv"
    main()
