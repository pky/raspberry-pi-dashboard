#!/usr/bin/env python3
"""
GPIO Process Monitor Script for Raspberry Pi Dashboard
Standalone script for monitoring and cleaning GPIO zombie processes
Can be run via cron or manually for system maintenance
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from gpio_cleanup_manager import get_gpio_manager
from logging_config import setup_logging

def main():
    """Main monitoring and cleanup function"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting GPIO process monitoring and cleanup")
    
    try:
        # Get GPIO manager instance
        manager = get_gpio_manager()
        
        # Get current process statistics
        stats = manager.get_process_statistics()
        logger.info(f"Current GPIO process statistics: {stats}")
        
        # Check if cleanup is needed
        cleanup_needed = False
        if stats['gpio_zombies'] > 5:
            logger.warning(f"High number of GPIO zombie processes: {stats['gpio_zombies']}")
            cleanup_needed = True
        
        if stats['active_gpio_processes'] > 10:
            logger.warning(f"High number of active GPIO processes: {stats['active_gpio_processes']}")
            cleanup_needed = True
        
        # Perform cleanup if needed
        if cleanup_needed:
            logger.info("Performing GPIO process cleanup")
            
            # Standard cleanup first
            zombie_cleaned = manager.cleanup_zombie_processes()
            logger.info(f"Standard cleanup removed {zombie_cleaned} zombie processes")
            
            # If still too many zombies, force cleanup
            updated_stats = manager.get_process_statistics()
            if updated_stats['gpio_zombies'] > 10:
                logger.warning("Standard cleanup insufficient, performing force cleanup")
                force_result = manager.force_cleanup_gpio_processes()
                logger.info(f"Force cleanup removed {force_result} processes")
            
            # Final statistics
            final_stats = manager.get_process_statistics()
            logger.info(f"Post-cleanup GPIO process statistics: {final_stats}")
            
            # Alert if cleanup was insufficient
            if final_stats['gpio_zombies'] > 15:
                logger.error(f"GPIO cleanup insufficient! Still {final_stats['gpio_zombies']} zombie processes")
                return 1
        else:
            logger.info("No GPIO process cleanup needed")
        
        # Display current zombie and GPIO processes for monitoring
        zombies = manager.get_zombie_processes()
        gpio_processes = manager.get_gpio_related_processes()
        
        if zombies:
            logger.info("Current zombie processes:")
            for zombie in zombies[:5]:  # Show up to 5 for brevity
                logger.info(f"  PID {zombie['pid']}: {zombie['command']}")
            if len(zombies) > 5:
                logger.info(f"  ... and {len(zombies) - 5} more zombie processes")
        
        if gpio_processes:
            logger.info("Current GPIO processes:")
            for proc in gpio_processes[:10]:  # Show up to 10 for brevity
                state_info = f" (state: {proc['state']})" if proc['state'] != 'R' else ""
                logger.info(f"  PID {proc['pid']}{state_info}: {proc['command']}")
            if len(gpio_processes) > 10:
                logger.info(f"  ... and {len(gpio_processes) - 10} more GPIO processes")
        
        logger.info("GPIO process monitoring completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"GPIO process monitoring failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)