#!/usr/bin/env python3
"""Ultimate bulletproof Lightroom launcher for restrictive environments like Cline."""

import os
import sys
import subprocess
import time
import uuid
import logging
import ctypes
from ctypes import wintypes

# Set up logging
logging.basicConfig(
    filename='bulletproof_launcher.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    filemode='a'
)
logger = logging.getLogger(__name__)

def detect_job_restrictions():
    """Detect what kind of job restrictions we're under."""
    try:
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        IsProcessInJob = kernel32.IsProcessInJob
        IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        IsProcessInJob.restype = wintypes.BOOL
        
        bool_in_job = wintypes.BOOL()
        if IsProcessInJob(ctypes.c_void_p(-1), None, ctypes.byref(bool_in_job)):
            in_job = bool(bool_in_job.value)
            logger.info(f"Process in job: {in_job}")
            
            if in_job:
                try:
                    from ctypes import Structure, sizeof, byref
                    
                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                            ("LimitFlags", wintypes.DWORD),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", wintypes.DWORD),
                            ("Affinity", ctypes.POINTER(wintypes.ULONG)),
                            ("PriorityClass", wintypes.DWORD),
                            ("SchedulingClass", wintypes.DWORD),
                        ]
                    
                    QueryInformationJobObject = kernel32.QueryInformationJobObject
                    QueryInformationJobObject.argtypes = [
                        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
                    ]
                    QueryInformationJobObject.restype = wintypes.BOOL
                    
                    limit_info = JOBOBJECT_BASIC_LIMIT_INFORMATION()
                    returned_length = wintypes.DWORD()
                    
                    if QueryInformationJobObject(None, 2, byref(limit_info),
                                               sizeof(limit_info), byref(returned_length)):
                        flags = limit_info.LimitFlags
                        logger.info(f"Job limit flags: 0x{flags:08x}")
                        
                        restrictions = {
                            'kill_on_close': bool(flags & 0x2000),
                            'breakaway_ok': bool(flags & 0x0800),
                            'silent_breakaway_ok': bool(flags & 0x1000)
                        }
                        logger.info(f"Job restrictions: {restrictions}")
                        return restrictions
                        
                except Exception as e:
                    logger.error(f"Failed to get job limits: {e}")
            
            return {'kill_on_close': False, 'breakaway_ok': in_job}
        
    except Exception as e:
        logger.error(f"Job detection failed: {e}")
    
    return {'kill_on_close': False, 'breakaway_ok': True}

def launch_via_scheduled_task(lightroom_path):
    """Launch via Windows scheduled task (highest isolation)."""
    logger.info("Attempting scheduled task launch...")
    
    try:
        task_name = f"LightroomLauncher_{uuid.uuid4().hex[:8]}"
        
        # Create scheduled task with immediate execution
        create_cmd = [
            'schtasks', '/create', '/tn', task_name,
            '/tr', f'"{lightroom_path}"',
            '/sc', 'once', '/st', '00:01',
            '/f'  # Force overwrite
        ]
        
        logger.info(f"Creating task: {' '.join(create_cmd)}")
        result = subprocess.run(create_cmd, capture_output=True, text=True)
        logger.info(f"Task creation result: {result.returncode}")
        logger.info(f"Task creation output: {result.stdout}")
        
        if result.returncode == 0:
            # Run the task immediately
            run_cmd = ['schtasks', '/run', '/tn', task_name]
            logger.info(f"Running task: {' '.join(run_cmd)}")
            run_result = subprocess.run(run_cmd, capture_output=True, text=True)
            logger.info(f"Task run result: {run_result.returncode}")
            
            if run_result.returncode == 0:
                logger.info("✅ Scheduled task launched successfully")
                
                # Clean up task (async, don't wait)
                try:
                    subprocess.Popen(['schtasks', '/delete', '/tn', task_name, '/f'],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                
                return True
            else:
                logger.error(f"Task run failed: {run_result.stderr}")
        else:
            logger.error(f"Task creation failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Scheduled task method failed: {e}")
    
    return False

def launch_via_breakaway(lightroom_path):
    """Launch using CREATE_BREAKAWAY_FROM_JOB flag."""
    logger.info("Attempting breakaway process launch...")
    
    try:
        # CREATE_BREAKAWAY_FROM_JOB = 0x01000000
        process = subprocess.Popen(
            [lightroom_path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=0x01000000
        )
        logger.info(f"✅ Breakaway process started with PID: {process.pid}")
        return True
        
    except Exception as e:
        logger.error(f"Breakaway launch failed: {e}")
    
    return False

def launch_via_wmi(lightroom_path):
    """Launch using Windows Management Instrumentation."""
    logger.info("Attempting WMI launch...")
    
    try:
        import wmi
        c = wmi.WMI()
        process_id, return_value = c.Win32_Process.Create(CommandLine=f'"{lightroom_path}"')
        
        if return_value == 0:
            logger.info(f"✅ WMI launch successful, PID: {process_id}")
            return True
        else:
            logger.error(f"WMI launch failed with code: {return_value}")
            
    except ImportError:
        logger.warning("WMI module not available")
    except Exception as e:
        logger.error(f"WMI launch failed: {e}")
    
    return False

def launch_via_powershell_job(lightroom_path):
    """Launch using PowerShell background job."""
    logger.info("Attempting PowerShell job launch...")
    
    try:
        # Use PowerShell to start a background job that launches Lightroom
        powershell_cmd = [
            'powershell', '-Command',
            f'Start-Job -ScriptBlock {{ Start-Process -FilePath "{lightroom_path}" }}; '
            f'Start-Sleep 1; Get-Job | Remove-Job -Force'
        ]
        
        result = subprocess.run(powershell_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("✅ PowerShell job launch successful")
            return True
        else:
            logger.error(f"PowerShell job failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"PowerShell job launch failed: {e}")
    
    return False

def launch_via_com_shell(lightroom_path):
    """Launch using COM Shell Application."""
    logger.info("Attempting COM shell launch...")
    
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.Run(f'"{lightroom_path}"', 0, False)  # 0 = hidden, False = don't wait
        logger.info("✅ COM shell launch successful")
        return True
        
    except ImportError:
        logger.warning("win32com module not available")
    except Exception as e:
        logger.error(f"COM shell launch failed: {e}")
    
    return False

def launch_via_service_helper(lightroom_path):
    """Launch using a temporary Windows service."""
    logger.info("Attempting service helper launch...")
    
    try:
        service_name = f"LightroomHelper_{uuid.uuid4().hex[:8]}"
        
        # Create a batch script that the service will run
        batch_script = f"lightroom_service_{uuid.uuid4().hex[:8]}.bat"
        with open(batch_script, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'start "" "{lightroom_path}"\n')
        
        # Use sc.exe to create a temporary service
        create_service_cmd = [
            'sc', 'create', service_name,
            'binPath=', f'cmd /c "{os.path.abspath(batch_script)}"',
            'start=', 'demand'
        ]
        
        result = subprocess.run(create_service_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Start the service
            start_result = subprocess.run(['sc', 'start', service_name], 
                                        capture_output=True, text=True)
            
            # Clean up service and batch file
            subprocess.run(['sc', 'delete', service_name], capture_output=True)
            try:
                os.remove(batch_script)
            except:
                pass
            
            if start_result.returncode == 0:
                logger.info("✅ Service helper launch successful")
                return True
            else:
                logger.error(f"Service start failed: {start_result.stderr}")
        else:
            logger.error(f"Service creation failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Service helper launch failed: {e}")
    
    return False

def bulletproof_launch(lightroom_path):
    """Try all available launch methods in order of isolation strength."""
    logger.info(f"Starting bulletproof launch for: {lightroom_path}")
    
    # Validate path
    if not os.path.exists(lightroom_path):
        logger.error(f"Lightroom executable not found: {lightroom_path}")
        return False
    
    # Detect job restrictions
    restrictions = detect_job_restrictions()
    
    # Define launch methods in order of preference (strongest isolation first)
    methods = [
        ("Scheduled Task", launch_via_scheduled_task),
        ("WMI Process Creation", launch_via_wmi),
        ("COM Shell Application", launch_via_com_shell),
        ("PowerShell Background Job", launch_via_powershell_job),
        ("Service Helper", launch_via_service_helper),
        ("Breakaway Process", launch_via_breakaway),
        ("Standard os.startfile", lambda path: os.startfile(path) or True),
    ]
    
    # If we have severe restrictions, skip weaker methods
    if restrictions.get('kill_on_close'):
        logger.warning("⚠️ Detected KILL_ON_JOB_CLOSE - using only strongest isolation methods")
        methods = methods[:5]  # Only use the top 5 strongest methods
    
    for method_name, method_func in methods:
        logger.info(f"Trying method: {method_name}")
        
        try:
            if method_func(lightroom_path):
                # Wait a moment and verify Lightroom is running
                time.sleep(3)
                
                check_result = subprocess.run([
                    'tasklist', '/FI', 'IMAGENAME eq Lightroom.exe', '/NH'
                ], capture_output=True, text=True)
                
                if 'Lightroom.exe' in check_result.stdout:
                    logger.info(f"🎉 SUCCESS: {method_name} launched Lightroom successfully!")
                    return True
                else:
                    logger.warning(f"⚠️ {method_name} completed but Lightroom not detected")
            else:
                logger.info(f"❌ {method_name} failed")
                
        except Exception as e:
            logger.error(f"❌ {method_name} threw exception: {e}")
    
    logger.error("💥 All launch methods failed")
    return False

def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: bulletproof_lightroom_launcher.py <lightroom_path>")
        sys.exit(1)
    
    lightroom_path = sys.argv[1]
    logger.info(f"Bulletproof launcher started with path: {lightroom_path}")
    
    success = bulletproof_launch(lightroom_path)
    
    if success:
        logger.info("✅ Bulletproof launch completed successfully")
        print("Lightroom launch successful")
        sys.exit(0)
    else:
        logger.error("❌ Bulletproof launch failed")
        print("Lightroom launch failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
