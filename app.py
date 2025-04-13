#!/usr/bin/python3
# tado_aa.py (Tado Auto-Assist for Geofencing and Open Window Detection)
# Adjusted for Device Flow Authentication and Docker usage

import sys
import time
import inspect
import os
import logging 
import json 

import socketserver
from http.server import BaseHTTPRequestHandler

from datetime import datetime
try:
    from PyTado.interface import Tado
    from PyTado.http import DeviceActivationStatus
    from PyTado.exceptions import TadoException, TadoCredentialsException
except ImportError as e:
     print(f"ERROR: Failed to import PyTado library. Make sure it's installed. Details: {e}")
     sys.exit(1)

from threading import Thread

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler = logging.StreamHandler(sys.stdout) 
log_handler.setFormatter(log_formatter)
logger = logging.getLogger("TadoAA") 
logger.addHandler(log_handler)
logger.setLevel(logging.INFO) 

# --- Global Variables ---
t: Tado | None = None 
token_file_path: str | None = None
checkingInterval: float = 10.0
errorRetringInterval: float = 30.0
lastMessage: str = "" 

# --- Health Check Server ---
# (Health Check Server code remains the same as previous version)
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        status_code = 503 
        status_message = "Error: Tado Not Initialized"
        if t is not None:
             try:
                current_status = t.device_activation_status() 
                if current_status == DeviceActivationStatus.COMPLETED:
                    status_code = 200
                    status_message = "OK: Authenticated"
                elif current_status == DeviceActivationStatus.PENDING:
                    status_code = 200 
                    status_message = "OK: Pending User Auth"
                else: 
                    status_code = 503
                    status_message = f"Error: Status {current_status}"
             except Exception as e:
                  status_code = 503
                  status_message = f"Error: Failed to get Tado status ({e.__class__.__name__})"
                  logger.warning(f"Health check failed to get Tado status: {e}", exc_info=False)
        self.send_response(status_code)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(f"{status_message}\n".encode("utf-8"))
    def log_message(self, format, *args):
        return

def health_check_server():
    port = int(os.getenv("TADO_HEALTHCHECK_PORT", default=8080))
    logger.info(f"Starting health check status server on port {port}")
    try:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("0.0.0.0", port), MyHandler)
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Could not start health check server on port {port}: {e}", exc_info=True)

# --- Main Logic ---

def printm(message):
    global lastMessage
    if message != lastMessage:
        logger.info(message) 
        lastMessage = message

def initialize_tado():
    global t
    global token_file_path

    token_file_path = os.getenv("TADO_TOKEN_FILE") 
    if not token_file_path:
        logger.critical("CRITICAL ERROR: TADO_TOKEN_FILE environment variable not set. Cannot proceed.")
        sys.exit(1) 

    token_dir = os.path.dirname(token_file_path)
    if token_dir and not os.path.exists(token_dir):
         try:
             os.makedirs(token_dir, exist_ok=True)
             logger.info(f"Created token directory: {token_dir}")
         except OSError as e:
             logger.error(f"Could not create token directory {token_dir}: {e}. Token persistence will fail.")
             sys.exit(1) 

    logger.info(f"Initializing Tado connection. Token file: {token_file_path}")

    while True:
        t = None 
        try:
            t = Tado(token_file_path=token_file_path, debug=(logger.level == logging.DEBUG))
            status = t.device_activation_status() 

            if status == DeviceActivationStatus.COMPLETED:
                printm("Tado connection successful (used saved/refreshed token).")
                return t 

            elif status == DeviceActivationStatus.PENDING:
                user_code = t._http.user_code 
                # --- !!! FIX 1: Correctly call the method for the URL !!! ---
                verification_url = t.device_verification_url() 
                # --- ---------------------------------------------------- ---
                printm("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                printm("!!! WAITING FOR USER AUTHORIZATION !!!")
                printm(f"!!! Please go to: {verification_url}") # Now prints the actual URL
                printm(f"!!! User code should be pre-filled. If not, enter: {user_code}")
                printm("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                printm("Script will wait here until you authorize the device in your browser...")

                activation_success = t.device_activation() 
                
                # --- !!! FIX 2: Add debug logging !!! ---
                logger.debug(f"t.device_activation() returned: {activation_success} (Type: {type(activation_success)})")
                # --- ---------------------------------- ---

                if activation_success: 
                    # This block should now execute based on library logs
                    printm("Device authorization successful!") 
                    final_status = t.device_activation_status() 
                    if final_status == DeviceActivationStatus.COMPLETED:
                         printm("Tado connection successful (new token obtained).")
                         return t 
                    else:
                         printm(f"Error: Activation reported success but status is {final_status}. Retrying initialization...")
                         time.sleep(errorRetringInterval)
                         continue 
                else: 
                    # This block was incorrectly entered before
                    printm("Device activation failed (Returned False - likely Denied by user, Code Expired, or Connection Error during polling).")
                    printm(f"Check browser/Tado app. Will retry initialization in {errorRetringInterval} seconds.")
                    time.sleep(errorRetringInterval)
                    continue 

            else: 
                printm(f"Error: Tado library initialization resulted in unexpected status: {status}. Retrying...") 
                time.sleep(errorRetringInterval)
                continue 

        except TadoCredentialsException as e:
            printm(f"Authentication Error on startup: {e}. Possible invalid saved token.")
            if os.path.exists(token_file_path):
                try:
                    os.remove(token_file_path)
                    printm(f"Removed potentially invalid token file: {token_file_path}")
                except OSError as remove_err:
                    printm(f"Warning: Could not remove token file {token_file_path}: {remove_err}")
            printm(f"Retrying initialization in {errorRetringInterval} seconds.")
            time.sleep(errorRetringInterval)
            continue 
        except TadoException as e:
            printm(f"Tado Connection/Init Error: {e}. Retrying in {errorRetringInterval} seconds.")
            time.sleep(errorRetringInterval)
            continue 
        except Exception as e:
            logger.error(f"Unexpected error during Tado initialization: {e}", exc_info=True)
            printm(f"Unexpected initialization error. Retrying in {errorRetringInterval} seconds.")
            time.sleep(errorRetringInterval)
            continue 

# --- homeStatus and engine functions remain the same as previous version ---
def homeStatus():
    """Checks initial home/away status and syncs if needed."""
    global devicesHome 
    if t is None:
         printm("Error: Tado object not initialized in homeStatus(). Skipping initial check.")
         return False 
    try:
        if t.device_activation_status() != DeviceActivationStatus.COMPLETED:
            printm(f"Error: Tado not authenticated ({t.device_activation_status()}) in homeStatus(). Skipping initial check.")
            return False
    except Exception as e:
        printm(f"Error getting Tado status in homeStatus(): {e}. Skipping initial check.")
        return False
    printm("Checking initial Tado Home/Away status...")
    try:
        homeState = t.get_home_state()["presence"]
        devicesHome = [] 
        mobile_devices = t.get_mobile_devices()
        if not mobile_devices:
             printm("Warning: No mobile devices found in Tado account.")
        for mobileDevice in mobile_devices:
            dev_name = mobileDevice.get("name", f"DeviceID_{mobileDevice.get('id', 'Unknown')}")
            if mobileDevice.get("settings", {}).get("geoTrackingEnabled"):
                 if mobileDevice.get("location"):
                    if mobileDevice["location"].get("atHome"):
                        devicesHome.append(dev_name)
                 else:
                     printm(f"Warning: No location data currently available for geotracked device: {dev_name}")
        num_devices_home = len(devicesHome)
        devices_str = ", ".join(devicesHome) if num_devices_home > 0 else "none"
        if num_devices_home > 0 and homeState == "HOME":
            printm(f"Home is in HOME Mode. Devices at home: {devices_str}.")
        elif num_devices_home == 0 and homeState == "AWAY":
            printm("Home is in AWAY Mode. No tracked devices at home.")
        elif num_devices_home == 0 and homeState == "HOME":
            printm("Home is in HOME Mode but no tracked devices are at home.")
            printm("Activating AWAY mode.")
            t.set_away()
            printm("AWAY mode activated.")
        elif num_devices_home > 0 and homeState == "AWAY":
            printm(f"Home is in AWAY Mode but devices ({devices_str}) are at home.")
            printm("Activating HOME mode.")
            t.set_home()
            printm("HOME mode activated.")
        printm("Initial status check complete.")
        return True 
    except TadoCredentialsException as e:
         printm(f"Authentication Error during status check: {e}. Will attempt re-auth.")
         return False 
    except TadoException as e:
         printm(f"Tado API error during status check: {e}. Retrying later.")
         return False 
    except KeyError as e:
         logger.error(f"Unexpected API response format (KeyError: {e}) during status check.", exc_info=True)
         printm(f"Error processing Tado status response. Retrying later.")
         return False 
    except Exception as e:
         logger.error(f"Unexpected error during status check: {e}", exc_info=True)
         printm(f"Unexpected error checking Tado status. Retrying later.")
         return False 

def engine():
    """Main monitoring loop for geofencing and open window detection."""
    if t is None:
         printm("Error: Tado object not initialized in engine(). Exiting monitoring loop.")
         return      
    try:
         if t.device_activation_status() != DeviceActivationStatus.COMPLETED:
              printm(f"Error: Tado not authenticated ({t.device_activation_status()}) in engine(). Exiting monitoring loop.")
              return
    except Exception as e:
         printm(f"Error getting Tado status in engine(): {e}. Exiting monitoring loop.")
         return
    printm("Starting monitoring loop (Geofencing & Open Window)...")
    last_presence_check_msg = "" 
    while True:
        try:
            # Open Window Detection
            zones = t.get_zones()
            if not zones: printm("Warning: No zones found.")
            for z in zones:
                zoneID = z.get("id"); zoneName = z.get("name", f"Zone {zoneID}")
                if not zoneID: logger.warning("Zone with no ID found."); continue
                try:
                    owd_info = t.get_open_window_detected(zoneID)
                    if owd_info.get("openWindowDetected"):
                         zone_state = t.get_state(zoneID)
                         if not zone_state.get("openWindow"):
                             printm(f"{zoneName}: OWD detected, activating overlay."); t.set_open_window(zoneID); printm(f"{zoneName}: OWD overlay activated.")
                except TadoException as e:
                     if "Open window" not in lastMessage: printm(f"Error checking OWD for {zoneName}: {e}")
                except KeyError as e: logger.warning(f"KeyError checking OWD for {zoneName}: {e}")
            # Geofencing
            homeState = t.get_home_state()["presence"]
            currentDevicesHome = [] 
            mobile_devices = t.get_mobile_devices()
            for mobileDevice in mobile_devices:
                 dev_name = mobileDevice.get("name", f"DeviceID_{mobileDevice.get('id', 'Unknown')}")
                 if mobileDevice.get("settings", {}).get("geoTrackingEnabled"):
                     if mobileDevice.get("location") and mobileDevice["location"].get("atHome"): currentDevicesHome.append(dev_name)
            num_devices_home = len(currentDevicesHome); devices_str = ", ".join(currentDevicesHome) if num_devices_home > 0 else "none"
            if num_devices_home > 0 and homeState == "AWAY":
                printm(f"Devices ({devices_str}) home, but AWAY. Activating HOME."); t.set_home(); printm("HOME activated."); last_presence_check_msg = ""; printm("Waiting...")
            elif num_devices_home == 0 and homeState == "HOME":
                printm(f"No devices home, but HOME. Activating AWAY."); t.set_away(); printm("AWAY activated."); last_presence_check_msg = ""; printm("Waiting...")
            else: 
                 current_msg = f"Presence check: {num_devices_home} device(s) home ({devices_str}), Mode: {homeState}. No change."
                 if current_msg != last_presence_check_msg:
                     if "No change" not in last_presence_check_msg: logger.info(current_msg)
                     else: logger.debug(current_msg) 
                     last_presence_check_msg = current_msg
            time.sleep(checkingInterval)
        except TadoCredentialsException as e: printm(f"CRITICAL Auth Error: {e}. Re-init required."); break 
        except TadoException as e: printm(f"API Error: {e}. Retrying in {errorRetringInterval}s."); time.sleep(errorRetringInterval)
        except KeyError as e: logger.error(f"KeyError: {e}", exc_info=True); printm(f"API Response Error. Retrying in {errorRetringInterval}s."); time.sleep(errorRetringInterval)
        except Exception as e: logger.error(f"Unexpected Engine Error: {e}", exc_info=True); printm(f"Unexpected Error. Retrying in {errorRetringInterval}s."); time.sleep(errorRetringInterval)

def main():
    global checkingInterval, errorRetringInterval, t 
    log_level_str = os.getenv("TADO_LOG_LEVEL", default="INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level); logger.info(f"Log level: {log_level_str}")
    try:
        checkingInterval = float(os.getenv("TADO_CHECK_INTERVAL", default=10.0))
        errorRetringInterval = float(os.getenv("TADO_RETRY_INTERVAL", default=30.0))
        if checkingInterval <= 0 or errorRetringInterval <=0: raise ValueError("Intervals must be positive")
    except ValueError as e: logger.error(f"Invalid intervals ({e}). Using defaults."); checkingInterval=10.0; errorRetringInterval=30.0
    logger.info(f"Tado Auto-Assist Starting Up"); logger.info(f"Check: {checkingInterval:.1f}s, Retry: {errorRetringInterval:.1f}s")
    health_thread = Thread(target=health_check_server, daemon=True); health_thread.start()
    while True:
        logger.info("Attempting Tado initialization..."); t = initialize_tado() 
        logger.info("Initialization complete. Performing initial status check...")
        if homeStatus(): logger.info("Initial status check OK. Starting engine."); engine() 
        printm("Engine stopped or initial check failed. Restarting initialization..."); t = None; time.sleep(5) 

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: printm("Interrupted. Exiting."); sys.exit(0)
    except SystemExit as e: logger.info(f"Script exited code {e.code}."); sys.exit(e.code) # Exit with the code
    except Exception as e: logger.critical(f"Critical unhandled error: {e}", exc_info=True); sys.exit(1)
