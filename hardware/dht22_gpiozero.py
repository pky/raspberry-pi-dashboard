"""
DHT22 sensor reading using gpiozero for Raspberry Pi 5
Based on DHT22 datasheet timing specifications
"""

import time
from gpiozero import DigitalInputDevice, DigitalOutputDevice

class DHT22:
    def __init__(self, pin):
        self.pin = pin
        
    def read(self):
        """Read temperature and humidity from DHT22 sensor"""
        try:
            # Send start signal
            output = DigitalOutputDevice(self.pin)
            output.on()
            time.sleep(0.25)  # Wait 250ms
            output.off()
            time.sleep(0.02)  # Wait 20ms
            output.close()
            
            # Switch to input mode
            input_device = DigitalInputDevice(self.pin, pull_up=True)
            
            # Wait for sensor response (should go LOW)
            timeout = time.time() + 0.1
            while input_device.value == 1:
                if time.time() > timeout:
                    input_device.close()
                    return None, None
            
            # Wait for sensor to go HIGH (start of data transmission)
            timeout = time.time() + 0.1
            while input_device.value == 0:
                if time.time() > timeout:
                    input_device.close()
                    return None, None
            
            # Wait for sensor to go LOW (end of response signal)
            timeout = time.time() + 0.1
            while input_device.value == 1:
                if time.time() > timeout:
                    input_device.close()
                    return None, None
            
            # Read 40 bits of data
            data = []
            for i in range(40):
                # Wait for bit start (LOW to HIGH)
                timeout = time.time() + 0.1
                while input_device.value == 0:
                    if time.time() > timeout:
                        input_device.close()
                        return None, None
                
                # Measure HIGH duration
                start_time = time.time()
                timeout = time.time() + 0.1
                while input_device.value == 1:
                    if time.time() > timeout:
                        input_device.close()
                        return None, None
                
                duration = time.time() - start_time
                # If HIGH duration > 40μs, it's a '1', otherwise '0'
                data.append(1 if duration > 0.00004 else 0)
            
            input_device.close()
            
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
        # gpiozero handles cleanup automatically
        pass