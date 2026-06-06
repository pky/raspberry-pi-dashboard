"""
GPIO Process Cleanup Manager for Raspberry Pi Dashboard
Manages and cleans up zombie GPIO processes to prevent system instability
"""

import os
import time
import signal
import logging
import subprocess
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class GPIOProcessManager:
    """
    GPIO process monitoring and cleanup manager
    Prevents accumulation of zombie libgpiod_pulsei processes
    """
    
    def __init__(self):
        self.monitoring = False
        self.monitor_thread = None
        self.max_zombie_processes = 5
        self.cleanup_interval = 30  # seconds
        self.process_whitelist = ['python3', 'systemd', 'kernel']
        
    def get_zombie_processes(self) -> List[Dict[str, str]]:
        """Get list of zombie processes"""
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            
            zombies = []
            for line in lines[1:]:  # Skip header
                if '<defunct>' in line:
                    parts = line.split()
                    if len(parts) >= 11:
                        pid = parts[1]
                        cmd = ' '.join(parts[10:])
                        zombies.append({
                            'pid': pid,
                            'command': cmd,
                            'line': line
                        })
            
            return zombies
        except Exception as e:
            logger.error(f"Failed to get zombie processes: {e}")
            return []
    
    def get_gpio_related_processes(self) -> List[Dict[str, str]]:
        """Get GPIO-related processes including libgpiod_pulsei"""
        try:
            result = subprocess.run(['pgrep', '-f', 'libgpiod'], capture_output=True, text=True)
            pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            processes = []
            for pid in pids:
                if pid:
                    try:
                        proc_info = subprocess.run(['ps', '-p', pid, '-o', 'pid,ppid,state,comm,cmd'], 
                                                 capture_output=True, text=True)
                        if proc_info.returncode == 0:
                            lines = proc_info.stdout.strip().split('\n')
                            if len(lines) > 1:  # Skip header
                                parts = lines[1].split()
                                processes.append({
                                    'pid': parts[0],
                                    'ppid': parts[1],
                                    'state': parts[2],
                                    'command': ' '.join(parts[3:])
                                })
                    except Exception as e:
                        logger.debug(f"Error getting process info for PID {pid}: {e}")
            
            return processes
        except Exception as e:
            logger.error(f"Failed to get GPIO processes: {e}")
            return []
    
    def cleanup_zombie_processes(self) -> int:
        """Clean up zombie processes, return number cleaned"""
        zombies = self.get_zombie_processes()
        gpio_zombies = [z for z in zombies if 'libgpiod' in z['command'] or 'pulsei' in z['command']]
        
        cleaned_count = 0
        
        for zombie in gpio_zombies:
            try:
                pid = int(zombie['pid'])
                
                # Try to get parent PID and send SIGCHLD
                result = subprocess.run(['ps', '-o', 'ppid=', '-p', str(pid)], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    ppid = result.stdout.strip()
                    if ppid.isdigit():
                        parent_pid = int(ppid)
                        try:
                            os.kill(parent_pid, signal.SIGCHLD)
                            logger.info(f"Sent SIGCHLD to parent process {parent_pid} for zombie {pid}")
                            cleaned_count += 1
                        except (ProcessLookupError, PermissionError):
                            logger.debug(f"Cannot signal parent process {parent_pid}")
                
            except (ValueError, ProcessLookupError, PermissionError) as e:
                logger.debug(f"Cannot clean zombie process {zombie['pid']}: {e}")
            except Exception as e:
                logger.error(f"Error cleaning zombie process {zombie['pid']}: {e}")
        
        return cleaned_count
    
    def force_cleanup_gpio_processes(self) -> int:
        """Force cleanup of stuck GPIO processes (use with caution)"""
        processes = self.get_gpio_related_processes()
        killed_count = 0
        
        for process in processes:
            if process['state'] == 'Z':  # Zombie state
                continue  # Cannot kill zombies directly
                
            try:
                pid = int(process['pid'])
                # Only kill libgpiod_pulsei processes that are not from system processes
                if 'libgpiod_pulsei' in process['command']:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.1)
                    
                    # Check if process still exists, then use SIGKILL
                    try:
                        os.kill(pid, 0)  # Test if process exists
                        os.kill(pid, signal.SIGKILL)
                        logger.info(f"Force killed libgpiod process {pid}")
                        killed_count += 1
                    except ProcessLookupError:
                        logger.info(f"Process {pid} terminated gracefully")
                        killed_count += 1
                        
            except (ValueError, ProcessLookupError, PermissionError) as e:
                logger.debug(f"Cannot force kill process {process['pid']}: {e}")
            except Exception as e:
                logger.error(f"Error force killing process {process['pid']}: {e}")
        
        return killed_count
    
    def get_process_statistics(self) -> Dict[str, int]:
        """Get current process statistics"""
        zombies = self.get_zombie_processes()
        gpio_processes = self.get_gpio_related_processes()
        gpio_zombies = [z for z in zombies if 'libgpiod' in z['command'] or 'pulsei' in z['command']]
        
        return {
            'total_zombies': len(zombies),
            'gpio_zombies': len(gpio_zombies),
            'active_gpio_processes': len([p for p in gpio_processes if p['state'] != 'Z']),
            'zombie_gpio_processes': len([p for p in gpio_processes if p['state'] == 'Z'])
        }
    
    def monitor_and_cleanup(self):
        """Background monitoring and cleanup thread"""
        logger.info("Starting GPIO process monitoring and cleanup")
        
        while self.monitoring:
            try:
                stats = self.get_process_statistics()
                
                if stats['gpio_zombies'] > self.max_zombie_processes:
                    logger.warning(f"Too many GPIO zombie processes: {stats['gpio_zombies']}")
                    cleaned = self.cleanup_zombie_processes()
                    
                    if cleaned == 0 and stats['gpio_zombies'] > self.max_zombie_processes * 2:
                        logger.warning("Standard cleanup failed, attempting force cleanup")
                        force_cleaned = self.force_cleanup_gpio_processes()
                        logger.info(f"Force cleaned {force_cleaned} GPIO processes")
                    else:
                        logger.info(f"Cleaned up {cleaned} zombie processes")
                
                # Log statistics periodically
                if stats['total_zombies'] > 0 or stats['active_gpio_processes'] > 0:
                    logger.debug(f"Process stats: {stats}")
                
                time.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in GPIO process monitoring: {e}")
                time.sleep(self.cleanup_interval)
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_and_cleanup)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            logger.info("GPIO process monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            logger.info("GPIO process monitoring stopped")
    
    def emergency_cleanup(self) -> Dict[str, int]:
        """Emergency cleanup of all GPIO-related processes"""
        logger.warning("Performing emergency GPIO process cleanup")
        
        # First try standard cleanup
        zombie_cleaned = self.cleanup_zombie_processes()
        
        # Then force cleanup if needed
        force_cleaned = self.force_cleanup_gpio_processes()
        
        # Wait a moment for processes to clean up
        time.sleep(1)
        
        final_stats = self.get_process_statistics()
        
        result = {
            'zombie_cleaned': zombie_cleaned,
            'force_cleaned': force_cleaned,
            'remaining_zombies': final_stats['gpio_zombies'],
            'remaining_active': final_stats['active_gpio_processes']
        }
        
        logger.info(f"Emergency cleanup completed: {result}")
        return result

# Global instance
_gpio_manager_instance = None

def get_gpio_manager() -> GPIOProcessManager:
    """Get singleton GPIO manager instance"""
    global _gpio_manager_instance
    if _gpio_manager_instance is None:
        _gpio_manager_instance = GPIOProcessManager()
    return _gpio_manager_instance

def cleanup_gpio_processes():
    """Convenience function for manual cleanup"""
    manager = get_gpio_manager()
    return manager.cleanup_zombie_processes()

def emergency_cleanup_gpio():
    """Convenience function for emergency cleanup"""
    manager = get_gpio_manager()
    return manager.emergency_cleanup()

if __name__ == "__main__":
    # Test the manager
    logging.basicConfig(level=logging.INFO)
    manager = GPIOProcessManager()
    
    print("Current process statistics:")
    stats = manager.get_process_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nZombie processes:")
    zombies = manager.get_zombie_processes()
    for zombie in zombies:
        print(f"  PID {zombie['pid']}: {zombie['command']}")
    
    print("\nGPIO processes:")
    gpio_procs = manager.get_gpio_related_processes()
    for proc in gpio_procs:
        print(f"  PID {proc['pid']} (state: {proc['state']}): {proc['command']}")
    
    print("\nPerforming cleanup...")
    cleaned = manager.cleanup_zombie_processes()
    print(f"Cleaned {cleaned} zombie processes")