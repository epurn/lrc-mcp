#!/usr/bin/env python3
"""External Lightroom launcher that can be called from command line."""

import os
import sys
import subprocess
import logging

# Set up logging to a file with append mode
logging.basicConfig(
    filename='external_launcher.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    filemode='a'  # Append mode
)

def launch_lightroom_external(lightroom_path):
    """Launch Lightroom with maximum isolation using bulletproof launcher."""
    try:
        logging.info(f"External launcher attempting to launch: {lightroom_path}")
        
        # Use the bulletproof launcher
        try:
            # Import the bulletproof launcher
            bulletproof_script = os.path.join(os.path.dirname(__file__), 'bulletproof_lightroom_launcher.py')
            
            if not os.path.exists(bulletproof_script):
                # Fallback to current directory
                bulletproof_script = 'bulletproof_lightroom_launcher.py'
            
            if os.path.exists(bulletproof_script):
                logging.info(f"Using bulletproof launcher: {bulletproof_script}")
                
                result = subprocess.run(
                    [sys.executable, bulletproof_script, lightroom_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logging.info("✅ Bulletproof launcher succeeded")
                    return True
                else:
                    logging.error(f"Bulletproof launcher failed: {result.stderr}")
            else:
                logging.warning("Bulletproof launcher not found, falling back to basic methods")
                
        except Exception as e:
            logging.error(f"Failed to use bulletproof launcher: {e}")
        
        # Fallback to basic methods if bulletproof launcher fails
        logging.info("Falling back to basic launch methods...")
        
        # Validate the path
        if not os.path.exists(lightroom_path):
            logging.error(f"Lightroom executable not found: {lightroom_path}")
            return False
            
        if not os.path.isfile(lightroom_path):
            logging.error(f"Lightroom path is not a file: {lightroom_path}")
            return False
        
        # Try basic methods in order of preference
        methods_tried = []
        
        # Method 1: os.startfile (Windows native)
        try:
            logging.info("Trying os.startfile fallback")
            os.startfile(lightroom_path)
            logging.info("os.startfile fallback succeeded")
            return True
        except Exception as e:
            error_msg = f"os.startfile failed: {e}"
            logging.error(error_msg)
            methods_tried.append(error_msg)
        
        # Method 2: CREATE_BREAKAWAY_FROM_JOB subprocess
        try:
            logging.info("Trying CREATE_BREAKAWAY_FROM_JOB subprocess")
            process = subprocess.Popen(
                [lightroom_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=0x01000000  # CREATE_BREAKAWAY_FROM_JOB
            )
            logging.info(f"Breakaway subprocess launched with PID: {process.pid}")
            return True
        except Exception as e:
            error_msg = f"breakaway subprocess failed: {e}"
            logging.error(error_msg)
            methods_tried.append(error_msg)
        
        # Method 3: Basic subprocess
        try:
            logging.info("Trying basic subprocess")
            process = subprocess.Popen(
                [lightroom_path],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            logging.info(f"Basic subprocess launched with PID: {process.pid}")
            return True
        except Exception as e:
            error_msg = f"basic subprocess failed: {e}"
            logging.error(error_msg)
            methods_tried.append(error_msg)
        
        logging.error(f"All fallback launch methods failed. Methods tried: {methods_tried}")
        return False
        
    except Exception as e:
        logging.error(f"Unexpected error in launch_lightroom_external: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logging.info("External launcher started")
    
    if len(sys.argv) != 2:
        logging.error("Usage: launch_lightroom_external.py <lightroom_path>")
        print("Usage: launch_lightroom_external.py <lightroom_path>")
        sys.exit(1)
    
    lightroom_path = sys.argv[1]
    logging.info(f"Lightroom path provided: {lightroom_path}")
    
    # Additional validation
    logging.info(f"Current working directory: {os.getcwd()}")
    logging.info(f"Lightroom path exists: {os.path.exists(lightroom_path)}")
    logging.info(f"Lightroom path is file: {os.path.isfile(lightroom_path)}")
    
    if os.path.exists(lightroom_path):
        logging.info(f"Lightroom file size: {os.path.getsize(lightroom_path)} bytes")
    
    success = launch_lightroom_external(lightroom_path)
    
    if success:
        logging.info("External launcher completed successfully")
        print("Lightroom launch initiated successfully")
        sys.exit(0)
    else:
        logging.error("External launcher failed")
        print("Lightroom launch failed")
        sys.exit(1)
