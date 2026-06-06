"""
Simple DHT22 sensor reading using lgpio for Raspberry Pi 5
Based on DHT22 datasheet timing specifications
"""

import time
import lgpio

class DHT22:
    def __init__(self, pin):
        self.pin = pin
        self.h = lgpio.gpiochip_open(0)
        
    def read(self):
        """Read temperature and humidity from DHT22 sensor"""
        try:
            # Send start signal
            lgpio.gpio_claim_output(self.h, self.pin)
            lgpio.gpio_write(self.h, self.pin, 1)
            time.sleep(0.05)
            lgpio.gpio_write(self.h, self.pin, 0)
            time.sleep(0.02)
            lgpio.gpio_claim_input(self.h, self.pin, lgpio.SET_PULL_UP)
            
            # Wait for sensor response
            timeout = time.time() + 0.1
            while lgpio.gpio_read(self.h, self.pin) == 1:
                if time.time() > timeout:
                    return None, None
                    
            # Read data bits
            data = []
            for i in range(40):
                # Wait for bit start
                timeout = time.time() + 0.1
                while lgpio.gpio_read(self.h, self.pin) == 0:
                    if time.time() > timeout:
                        return None, None
                        
                # Measure bit duration
                start = time.time()
                timeout = time.time() + 0.1
                while lgpio.gpio_read(self.h, self.pin) == 1:
                    if time.time() > timeout:
                        return None, None
                        
                duration = time.time() - start
                data.append(1 if duration > 0.00005 else 0)
            
            # Convert bits to bytes
            humidity_bits = data[0:16]
            temperature_bits = data[16:32]
            checksum_bits = data[32:40]
            
            humidity = 0
            for bit in humidity_bits:
                humidity = (humidity << 1) | bit
                
            temperature = 0
            for bit in temperature_bits:
                temperature = (temperature << 1) | bit
                
            checksum = 0
            for bit in checksum_bits:
                checksum = (checksum << 1) | bit
                
            # Verify checksum
            calculated_checksum = ((humidity >> 8) + (humidity & 0xFF) + 
                                  (temperature >> 8) + (temperature & 0xFF)) & 0xFF
            
            if checksum != calculated_checksum:
                return None, None
                
            # Convert to actual values
            humidity = humidity / 10.0
            temperature = temperature / 10.0
            
            # Handle negative temperatures
            if temperature > 1000:
                temperature = -(temperature - 1000)
                
            return temperature, humidity
            
        except Exception as e:
            print(f"DHT22 read error: {e}")
            return None, None
        
    def cleanup(self):
        if hasattr(self, 'h'):
            lgpio.gpiochip_close(self.h)