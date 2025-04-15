#!/usr/bin/python3
# app.py (Tado Auto-Assist - Firefox Automation - Double-Checking Definitions)

import sys
import time
import os
import logging
import json

import socketserver
from http.server import BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

# --- Selenium Imports ---
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
except ImportError:
    print("ERROR: Selenium library not found. Please install: pip install selenium")
    sys.exit(1)
# --- End Selenium Imports ---

try:
    # Adjust these imports if your library structure is different
    from PyTado.interface import Tado
    from PyTado.http import DeviceActivationStatus
    from PyTado.exceptions import TadoException, TadoCredentialsException
except ImportError as e:
    print(f"ERROR: Failed to import PyTado library: {e}")
    sys.exit(1)

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
tado_username: str | None = None
tado_password: str | None = None

# --- Health Check Server ---
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        status_code = 503; status_message = "Error: Tado Not Initialized"
        if t is not None:
             try:
                current_status = t.device_activation_status()
                if current_status == DeviceActivationStatus.COMPLETED:
                    status_code = 200; status_message = "OK: Authenticated"
                elif current_status == DeviceActivationStatus.PENDING:
                    status_code = 200; status_message = "OK: Pending User Auth"
                else:
                    status_code = 503; status_message = f"Error: Status {current_status}"
             except Exception as e:
                 status_code = 503; status_message = f"Error: Failed status ({e.__class__.__name__})"
                 logger.warning(f"Health check failed: {e}", exc_info=False)
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
        logger.error(f"Health check server failed: {e}", exc_info=True)

# --- Browser Automation Function ---
def automate_tado_approval(url: str, user_code: str) -> bool:
    """
    Automates the device code approval flow:
      1. On the device code page (stage 1), click the “Submit” button.
      2. On the login page (stage 2), enter the credentials and click the “Sign in” button.
    Returns True on successful automated approval; False otherwise.
    """
    global tado_username, tado_password
    if not tado_username or not tado_password:
        logger.error("TADO_USERNAME and TADO_PASSWORD env vars required for browser automation.")
        return False

    logger.info("Attempting automated browser approval using Firefox...")
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = None
    geckodriver_path = "/usr/bin/geckodriver"  # Adjust if necessary
    try:
        if not os.path.exists(geckodriver_path):
            logger.error(f"GeckoDriver executable not found at specified path: {geckodriver_path}")
            return False

        service = FirefoxService(executable_path=geckodriver_path)
        driver = webdriver.Firefox(service=service, options=options)
        wait = WebDriverWait(driver, 20)

        logger.info(f"Navigating to verification URL: {url}")
        driver.get(url)
        time.sleep(5)
        try:
            driver.save_screenshot("debug_after_navigating.png")
        except Exception as ss_e:
            logger.error(f"Screenshot failed: {ss_e}")

        # --- Stage 1: Device Code Page ---
        # If the device code form is present, then we are on the page where the user code is pre-populated.
        try:
            device_form = wait.until(EC.presence_of_element_located((By.ID, "device-form")))
            logger.info("Device code page detected. Proceeding with code submission.")
            # The button on this page:
            submit_locator_code = (By.CSS_SELECTOR, "button.c-btn.c-btn--primary.primary.button")
            submit_button = wait.until(EC.element_to_be_clickable(submit_locator_code))
            logger.info("Clicking the Submit button on device code page.")
            submit_button.click()
            time.sleep(5)
            try:
                driver.save_screenshot("debug_after_code_submit.png")
            except Exception as ss_e:
                logger.error(f"Screenshot failed after code submit: {ss_e}")
        except TimeoutException:
            logger.info("Device code form not found; assuming already past device code stage.")

        # --- Stage 2: Login Page ---
        try:
            username_locator = (By.ID, "loginId")
            password_locator = (By.ID, "password")
            # The Sign In button on the login page (the button text is “Sign in”)
            signin_locator = (By.CSS_SELECTOR, "button.c-btn.c-btn--primary.button")
            login_username_field = wait.until(EC.presence_of_element_located(username_locator))
            logger.info("Login page loaded (username field found). Entering credentials...")
            login_username_field.clear()
            login_username_field.send_keys(tado_username)
            login_password_field = driver.find_element(*password_locator)
            login_password_field.clear()
            login_password_field.send_keys(tado_password)
            signin_button = wait.until(EC.element_to_be_clickable(signin_locator))
            logger.info("Clicking the Sign in button.")
            signin_button.click()
            time.sleep(7)
            try:
                driver.save_screenshot("debug_after_login.png")
            except Exception as ss_e:
                logger.error(f"Screenshot failed after login: {ss_e}")
            logger.info("Browser approval submitted (logged-out flow, assuming success after login).")
            return True
        except TimeoutException:
            logger.error("TimeoutException: Login page did not appear after code submission.")
            return False
        except Exception as e:
            logger.error(f"Error during login form submission: {e}", exc_info=True)
            return False

    except Exception as e:
        if "executable needs to be in PATH" in str(e) or "Unable to obtain driver" in str(e):
            logger.error(f"WebDriver Error: {e}")
        else:
            logger.error(f"Error during browser automation: {e}", exc_info=True)
        return False
    finally:
        if driver:
            logger.debug("Closing WebDriver.")
            driver.quit()

# --- Main Tado Logic ---
def printm(message):
    """Logs a message only if it's different from the last one."""
    global lastMessage
    if message != lastMessage:
        logger.info(message)
        lastMessage = message

def initialize_tado():
    """Initializes Tado connection, handling auth and automation."""
    global t, token_file_path, tado_username, tado_password
    tado_username = os.getenv("TADO_USERNAME")
    tado_password = os.getenv("TADO_PASSWORD")
    token_file_path = os.getenv("TADO_TOKEN_FILE")
    if not token_file_path:
        logger.critical("TADO_TOKEN_FILE env var missing.")
        sys.exit(1)
    token_dir = os.path.dirname(token_file_path)
    if token_dir and not os.path.exists(token_dir):
         try:
             os.makedirs(token_dir, exist_ok=True)
             logger.info(f"Created token dir: {token_dir}")
         except OSError as e:
             logger.error(f"Cannot create token dir {token_dir}: {e}")
             sys.exit(1)
    logger.info(f"Initializing Tado. Token file: {token_file_path}")
    while True:
        t = None
        try:
            t = Tado(token_file_path=token_file_path, debug=(logger.level == logging.DEBUG))
            status = t.device_activation_status()
            if status == DeviceActivationStatus.COMPLETED:
                printm("Tado connection successful (token OK).")
                return t
            elif status == DeviceActivationStatus.PENDING:
                user_code = t._http.user_code
                verification_url = t.device_verification_url()
                if verification_url and user_code:
                     printm("Device flow pending. Attempting automated browser approval...")
                     auto_approved = automate_tado_approval(verification_url, user_code)
                     if auto_approved:
                         printm("Automated approval attempt finished. Polling...")
                     else:
                         printm("Automated approval failed. Manual approval might be needed.")
                         printm(f"!!! MANUAL: Go to {verification_url} Code: {user_code} !!!")
                else:
                     printm(f"Could not get URL/Code. Manual approval needed: {user_code or 'UNKNOWN'}")
                activation_success = t.device_activation()
                logger.debug(f"t.device_activation() returned: {activation_success} (Type: {type(activation_success)})")
                if activation_success:
                    printm("Device authorization successful (API polling confirmed)!")
                    final_status = t.device_activation_status()
                    if final_status == DeviceActivationStatus.COMPLETED:
                        printm("Tado connection successful (new token).")
                        return t
                    else:
                        printm(f"Error: Activation OK but status {final_status}. Retrying...")
                        time.sleep(errorRetringInterval)
                        continue
                else:
                    printm("Device activation failed (API polling failed after auto-attempt).")
                    time.sleep(errorRetringInterval)
                    continue
            else:
                printm(f"Error: Init status {status}. Retrying...")
                time.sleep(errorRetringInterval)
                continue
        except TadoCredentialsException as e:
            printm(f"Auth Error startup: {e}.")
            time.sleep(errorRetringInterval)
            continue
        except TadoException as e:
            printm(f"Tado Conn/Init Error: {e}. Retrying...")
            time.sleep(errorRetringInterval)
            continue
        except Exception as e:
            logger.error(f"Unexpected error during init: {e}", exc_info=True)
            time.sleep(errorRetringInterval)
            continue

def homeStatus():
    """Checks initial home/away status and syncs if needed."""
    global devicesHome
    if t is None:
        printm("Error: Tado not init homeStatus().")
        return False
    try:
        if t.device_activation_status() != DeviceActivationStatus.COMPLETED:
            printm(f"Error: Tado not auth ({t.device_activation_status()}) homeStatus().")
            return False
    except Exception as e:
         printm(f"Error get status homeStatus(): {e}.")
         return False
    printm("Checking initial status...");
    try:
        homeState = t.get_home_state()["presence"]
        devicesHome = []
        mobile_devices = t.get_mobile_devices()
        if not mobile_devices:
             printm("Warning: No mobile devices found.")
        for mobileDevice in mobile_devices:
            dev_name = mobileDevice.get("name", f"DeviceID_{mobileDevice.get('id', 'Unknown')}")
            if mobileDevice.get("settings", {}).get("geoTrackingEnabled"):
                 if mobileDevice.get("location") and mobileDevice["location"].get("atHome"):
                      devicesHome.append(dev_name)
                 else:
                      printm(f"Warn: No location for {dev_name}")
        num_home = len(devicesHome)
        dev_str = ", ".join(devicesHome) if num_home > 0 else "none"
        if num_home > 0 and homeState == "HOME":
             printm(f"HOME Mode. Devices: {dev_str}.")
        elif num_home == 0 and homeState == "AWAY":
             printm("AWAY Mode. No devices home.")
        elif num_home == 0 and homeState == "HOME":
             printm("HOME Mode, no devices home -> AWAY.")
             t.set_away()
             printm("AWAY set.")
        elif num_home > 0 and homeState == "AWAY":
             printm(f"AWAY Mode, devices ({dev_str}) home -> HOME.")
             t.set_home()
             printm("HOME set.")
        printm("Initial status check complete.")
        return True
    except TadoCredentialsException as e:
         printm(f"Auth Error status check: {e}. Re-init needed.")
         return False
    except TadoException as e:
         printm(f"API error status check: {e}. Retry later.")
         return False
    except KeyError as e:
         logger.error(f"KeyError status check: {e}", exc_info=True)
         printm(f"API Response Error. Retry later.")
         return False
    except Exception as e:
         logger.error(f"Unexpected status check error: {e}", exc_info=True)
         printm(f"Unexpected status error. Retry later.")
         return False

def engine():
    """Main monitoring loop."""
    if t is None:
         printm("Error: Tado not init engine().")
         return
    try:
         if t.device_activation_status() != DeviceActivationStatus.COMPLETED:
              printm(f"Error: Tado not auth ({t.device_activation_status()}) engine().")
              return
    except Exception as e:
         printm(f"Error get status engine(): {e}.")
         return
    printm("Starting monitoring loop...")
    last_presence_check_msg = ""
    while True:
        try:
            # Open Window Detection (OWD)
            zones = t.get_zones()
            if zones:
                 for z in zones:
                     zoneID = z.get("id")
                     zoneName = z.get("name", f"Zone {zoneID}")
                     if not zoneID:
                          logger.warning("Zone with no ID.")
                          continue
                     try:
                         owd_info = t.get_open_window_detected(zoneID)
                         if owd_info.get("openWindowDetected"):
                              zone_state = t.get_state(zoneID)
                              if not zone_state.get("openWindow"):
                                   printm(f"{zoneName}: OWD detected -> activating.")
                                   t.set_open_window(zoneID)
                                   printm(f"{zoneName}: OWD activated.")
                     except TadoException as e:
                          if "Open window" not in lastMessage:
                               printm(f"Error OWD {zoneName}: {e}")
                     except KeyError as e:
                          logger.warning(f"KeyError OWD {zoneName}: {e}")
            # Geofencing
            homeState = t.get_home_state()["presence"]
            currentDevicesHome = []
            mobile_devices = t.get_mobile_devices()
            if mobile_devices:
                for mobileDevice in mobile_devices:
                     dev_name = mobileDevice.get("name", f"Dev_{mobileDevice.get('id', 'Unk')}")
                     if mobileDevice.get("settings", {}).get("geoTrackingEnabled"):
                         if mobileDevice.get("location") and mobileDevice["location"].get("atHome"):
                              currentDevicesHome.append(dev_name)
            num_home = len(currentDevicesHome)
            dev_str = ", ".join(currentDevicesHome) if num_home > 0 else "none"
            if num_home > 0 and homeState == "AWAY":
                 printm(f"Devices ({dev_str}) home, but AWAY -> HOME.")
                 t.set_home()
                 printm("HOME activated.")
                 last_presence_check_msg = ""
                 printm("Waiting...")
            elif num_home == 0 and homeState == "HOME":
                 printm(f"No devices home, but HOME -> AWAY.")
                 t.set_away()
                 printm("AWAY activated.")
                 last_presence_check_msg = ""
                 printm("Waiting...")
            else:
                 current_msg = f"Presence: {num_home} home ({dev_str}), Mode: {homeState}. No change."
                 if current_msg != last_presence_check_msg:
                      if "No change" not in last_presence_check_msg:
                           logger.info(current_msg)
                      else:
                           logger.debug(current_msg)
                      last_presence_check_msg = current_msg
            time.sleep(checkingInterval)
        except TadoCredentialsException as e:
             printm(f"CRITICAL Auth Error: {e}. Re-init required.")
             break
        except TadoException as e:
             printm(f"API Error: {e}. Retrying in {errorRetringInterval}s.")
             time.sleep(errorRetringInterval)
        except KeyError as e:
             logger.error(f"KeyError: {e}", exc_info=True)
             printm(f"API Resp Error. Retrying...")
             time.sleep(errorRetringInterval)
        except Exception as e:
             logger.error(f"Unexpected Engine Error: {e}", exc_info=True)
             printm(f"Unexpected Error. Retrying...")
             time.sleep(errorRetringInterval)

def main():
    """Main setup and execution loop."""
    global checkingInterval, errorRetringInterval, t
    log_level_str = os.getenv("TADO_LOG_LEVEL", default="INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)
    logger.info(f"Log level: {log_level_str}")
    try:
         checkingInterval = float(os.getenv("TADO_CHECK_INTERVAL", default=10.0))
         errorRetringInterval = float(os.getenv("TADO_RETRY_INTERVAL", default=30.0))
         if checkingInterval <= 0 or errorRetringInterval <= 0:
             raise ValueError("Intervals must be positive")
    except ValueError as e:
         logger.error(f"Invalid intervals ({e}). Using defaults.")
         checkingInterval = 10.0
         errorRetringInterval = 30.0
    logger.info(f"Tado Auto-Assist Starting Up")
    logger.info(f"Check: {checkingInterval:.1f}s, Retry: {errorRetringInterval:.1f}s")
    health_thread = Thread(target=health_check_server, daemon=True)
    health_thread.start()
    while True:
        logger.info("Attempting Tado initialization...")
        t = initialize_tado()
        logger.info("Initialization complete. Performing initial status check...")
        if homeStatus():
             logger.info("Initial status check OK. Starting engine.")
             engine()
        printm("Engine stopped or initial check failed. Restarting initialization...")
        t = None
        time.sleep(5)

if __name__ == "__main__":
    try:
         main()
    except KeyboardInterrupt:
         printm("Interrupted. Exiting.")
         sys.exit(0)
    except SystemExit as e:
         logger.info(f"Script exited code {e.code}.")
         sys.exit(e.code)
    except Exception as e:
         logger.critical(f"Critical unhandled error: {e}", exc_info=True)
         sys.exit(1)

