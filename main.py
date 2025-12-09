import sys
from machine import Pin, PWM
from time import sleep, ticks_ms, ticks_diff
from distance_sensor import DistanceSensor
from dual_motor_driers import DualMotorDriver

# --- Setup ---
# LED Setup
led_red = Pin(26, Pin.OUT)
led_blue = Pin(28, Pin.OUT)
led_green_pwm = PWM(Pin(27)) 
led_green_pwm.freq(1000)

button = Pin(22, Pin.IN, Pin.PULL_DOWN)

# Motor & Sensor Setup
sensor = DistanceSensor(echo_id=8, trig_id=9, trig_freq=15)
dmd = DualMotorDriver(left_ids=(15, 13, 14), right_ids=(16, 18, 17), stby_id=12)
dmd.enable()

# --- Global State Variables ---
paused = False             # Tracks if we are currently paused
last_button_time = 0       # For debounce
total_paused_time = 0      # Total time spent in pause mode
pause_start_timestamp = 0  # When the current pause started
button_hold_start = 0      # Timer for the 3-second hold termination
start_time = ticks_ms()    # Global start timer

# --- Helper Functions ---

def set_leds(r, g_pwm, b):
    """
    r, b: 0 or 1 (Digital)
    g_pwm: 0 to 65535 (PWM Brightness)
    """
    led_red.value(r)
    led_blue.value(b)
    led_green_pwm.duty_u16(g_pwm)

def toggle_pause(pin):
    """Interrupt Handler: Toggles Pause State"""
    global paused, last_button_time, pause_start_timestamp, total_paused_time
    current = ticks_ms()
    
    # Debounce (300ms)
    if ticks_diff(current, last_button_time) > 300:
        paused = not paused
        last_button_time = current
        
        # Time Management for Battery Logic
        if paused:
            pause_start_timestamp = current # Mark when pause began
        else:
            if pause_start_timestamp != 0:
                duration = ticks_diff(current, pause_start_timestamp)
                total_paused_time += duration # Add to total paused time

# Attach Interrupt
button.irq(trigger=Pin.IRQ_RISING, handler=toggle_pause)

def check_battery_and_get_speed():
    """
    Handles Pause Loop, Termination Check, and Battery Logic.
    Returns: (speed, force_blue_led)
    """
    global button_hold_start

    # --- 1. PAUSE HANDLING (Blocking) ---
    if paused:
        print(">>> PAUSED")
        dmd.stop()
        set_leds(0, 0, 0)
        
        # Fading Variables
        duty = 0
        step = 2000 
        direction = 1
        
        # Blocking Loop: Stays here while paused
        while paused:
            # Breathing Green LED Logic
            duty += (step * direction)
            if duty >= 65535:
                duty = 65535
                direction = -1
            elif duty <= 0:
                duty = 0
                direction = 1
            led_green_pwm.duty_u16(duty)
            sleep(0.01)
        
        print(">>> RESUMING")
        led_green_pwm.duty_u16(0) 

    # --- 2. TERMINATION CHECK (Hold Button > 3s) ---
    if button.value() == 1:
        if button_hold_start == 0: 
            button_hold_start = ticks_ms()
        elif ticks_diff(ticks_ms(), button_hold_start) > 3000:
            print("System Terminated by User (Hold).")
            dmd.stop()
            dmd.disable()
            set_leds(0, 0, 0)
            sys.exit()
    else:
        button_hold_start = 0

    # --- 3. BATTERY CALCULATION ---
    current_time = ticks_ms()
    # Real Work Time = Total Elapsed - Total Paused
    elapsed = ticks_diff(current_time, start_time) - total_paused_time
    
    # Critical Battery (> 55s)
    if elapsed > 55000:
        print("CRITICAL BATTERY: Shutdown")
        dmd.stop()
        set_leds(1, 0, 0)
        # Blink Red 5s
        end = ticks_ms() + 5000
        while ticks_ms() < end:
            set_leds(0, 0, 1)
            sleep(0.05)
            set_leds(0, 0, 0)
            sleep(0.05)
        sys.exit()

    # Low Battery (> 45s)
    elif elapsed > 45000:
        return 0.25, True # 50% Speed, Blue LED Override
        
    # Normal Mode
    else:
        return 0.5, False # Normal Speed

# --- Main Execution ---

if __name__ == "__main__":
    try:
        print("Wall Sensing Started")
        
        # System Check Blink
        if sensor.distance is not None:
            for _ in range(5):
                set_leds(1, 65535, 1) # All ON
                sleep(0.1)
                set_leds(0, 0, 0)     # All OFF
                sleep(0.1)
        
        while True:
            
            # --- Move 1: Forward to 0.25m ---
            print("--- Moving Forward ---")
            while True:
                speed, force_blue = check_battery_and_get_speed()
                
                # LED Logic
                if force_blue:
                    set_leds(1, 0, 0) # Blue
                else:
                    set_leds(0, 65535, 0) # Green
                
                dmd.left_motor.forward(speed * 0.9)
                dmd.right_motor.forward(speed * 0.95)
                
                # Check Sensor & Print Distance
                d = sensor.distance
                if d is not None:
                    print(f"Distance: {d:.2f} m") # <--- PRINTING DISTANCE HERE
                    if 0.15 <= d <= 0.4:
                        break
                sleep(0.05)
            
            # Stop
            dmd.stop()
            set_leds(0, 65535, 0)
            sleep(0.5)

            # --- Move 2: Backward to 1.0m ---
            print("--- Moving Backward ---")
            while True:
                speed, force_blue = check_battery_and_get_speed()
                set_leds(0, 65535, 0) # Blue Logic for backward
                
                dmd.left_motor.backward(speed * 0.9)
                dmd.right_motor.backward(speed * 0.95)
                
                d = sensor.distance
                if d is not None:
                    print(f"Distance: {d:.2f} m") # <--- PRINTING DISTANCE HERE
                    if 0.9 <= d <= 1.1:
                        break
                sleep(0.05)
                
            dmd.stop()
            set_leds(0, 65535, 0)
            sleep(1.0)
            
            #####
#             print(">>> Turning")
            turn_start = ticks_ms()
            
            # Turn for 0.8 seconds (Adjust this number to turn more or less)
            while ticks_diff(ticks_ms(), turn_start) < 500: 
                speed, _ = check_battery_and_get_speed() # Keep checking status!
                
                # Spin Logic
                dmd.left_motor.backward(speed) 
                dmd.right_motor.forward(speed)
                
                # 
                set_leds(0, 65535, 0) 
                sleep(0.05)
            
            # 4. Stop and Resume Loop
            dmd.stop()
            set_leds(0, 65535, 0)
            sleep(0.5)
#             ######

            # --- Move 3: Forward to 0.25m ---
            print("--- Moving Forward ---")
            while True:
                speed, force_blue = check_battery_and_get_speed()
                
                if force_blue:
                    set_leds(0, 0, 1)
                else:
                    set_leds(0, 65535, 0)
                
                dmd.left_motor.forward(speed * 0.9)
                dmd.right_motor.forward(speed * 0.95)
                
                d = sensor.distance
                if d is not None:
                    print(f"Distance: {d:.2f} m") # <--- PRINTING DISTANCE HERE
                    if 0.15 <= d <= 0.35:
                        break
                sleep(0.05) 

            dmd.stop()
            set_leds(0, 65535, 0)
            sleep(1.0)

            # --- Move 4: Backward to 0.55m ---
            print("--- Moving Backward ---")
            while True:
                speed, force_blue = check_battery_and_get_speed()
                set_leds(0, 0, 1)
                
                dmd.left_motor.backward(speed * 0.9)
                dmd.right_motor.backward(speed * 0.95)            
                
                d = sensor.distance
                if d is not None:
                    print(f"Distance: {d:.2f} m") # <--- PRINTING DISTANCE HERE
                    if 0.3 <= d <= 0.5:
                        break
                sleep(0.05)
                
            dmd.stop()
            set_leds(0, 0, 1)
            print("Finished sequence.")
            sleep(1.0)
            
    except KeyboardInterrupt:
        dmd.stop()
        dmd.disable()
        set_leds(0, 0, 0)
        print("Stopped by user")
