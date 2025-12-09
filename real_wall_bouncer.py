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
work_accumulated_time = 0  # Total time spent working (excluding current session)
session_start_time = 0     # When the current work session started
last_button_time = 0       # For debounce
button_press_start = 0     # For detecting 3-second hold

# Constants
DUTY_MAX = 65535
FADE_STEP = 2000           # How fast the light fades

# --- Helper Functions ---

def set_leds(r, g_pwm, b):
    """
    Sets LED colors.
    r, b: 0 or 1 (Digital)
    g_pwm: 0 to 65535 (PWM Brightness)
    """
    led_red.value(r)
    led_blue.value(b)
    led_green_pwm.duty_u16(g_pwm)

def toggle_pause_irq(pin):
    """
    Interrupt Handler: Only flips the pause flag.
    Logic is handled in the main loop.
    """
    global paused, last_button_time, work_accumulated_time, session_start_time
    
    current = ticks_ms()
    # Debounce: Ignore clicks faster than 300ms
    if ticks_diff(current, last_button_time) > 300:
        if not paused:
            # We are SWITCHING TO PAUSE
            # Save the time we just spent working
            work_accumulated_time += ticks_diff(current, session_start_time)
            paused = True
        else:
            # We are RESUMING
            # Reset the session timer
            session_start_time = current
            paused = False
            
        last_button_time = current

# Attach Interrupt
button.irq(trigger=Pin.IRQ_RISING, handler=toggle_pause_irq)

def check_status():
    """
    THE BRAIN: Checks Pause, Termination, and Battery.
    Returns: (speed, use_blue_led_flag)
    """
    global paused, button_press_start, work_accumulated_time, session_start_time

    # --- 1. TERMINATION CHECK (Hold Button > 3s) ---
    # We check the raw pin value here because IRQs are for clicks, polling is better for holds.
    if button.value() == 1:
        if button_press_start == 0:
            button_press_start = ticks_ms()
        elif ticks_diff(ticks_ms(), button_press_start) > 3000:
            print("System Terminated by User (Hold).")
            dmd.stop()
            dmd.disable()
            set_leds(0, 0, 0)
            sys.exit()
    else:
        button_press_start = 0

    # --- 2. PAUSE HANDLING ---
    if paused:
        print(">>> PAUSED")
        dmd.stop()
        set_leds(0, 0, 0) # Clear LEDs
        
        # Breathing Loop (Blocks here until unpaused)
        while paused:
            # Fade In
            for duty in range(0, DUTY_MAX, FADE_STEP):
                if not paused: break 
                led_green_pwm.duty_u16(duty)
                sleep(0.01)
            # Fade Out
            for duty in range(DUTY_MAX, 0, -FADE_STEP):
                if not paused: break
                led_green_pwm.duty_u16(duty)
                sleep(0.01)
        
        print(">>> RESUMING")
        # Ensure correct LED state immediately upon resume
        led_green_pwm.duty_u16(65535) 

    # --- 3. BATTERY LOGIC ---
    # Calculate total actual work time (Previous sessions + current session)
    total_work_ms = work_accumulated_time + ticks_diff(ticks_ms(), session_start_time)
    
    # Critical Battery (> 55 seconds)
    if total_work_ms > 55000:
        print("CRITICAL BATTERY: Shutdown")
        dmd.stop()
        set_leds(0, 0, 0)
        
        # Blink Red 10Hz for 5 seconds
        end_time = ticks_ms() + 5000
        while ticks_ms() < end_time:
            led_red.value(1)
            sleep(0.05)
            led_red.value(0)
            sleep(0.05)
        sys.exit()

    # Low Battery (> 45 seconds)
    elif total_work_ms > 45000:
        # Return: Speed 0.25, Blue LED = True
        return 0.25, True 
        
    # Normal Mode
    else:
        # Return: Speed 0.5, Blue LED = False
        return 0.5, False

# --- Main Execution ---

if __name__ == "__main__":
    try:
        print("Wall Sensing Started")
        
        # Start the global timer for the first session
        session_start_time = ticks_ms()

        # System Check Blink
        if sensor.distance is not None:
            for _ in range(5):
                set_leds(1, 65535, 1) # All ON
                sleep(0.1)
                set_leds(0, 0, 0)     # All OFF
                sleep(0.1)
        
        # Main Movement Loop
        while True:
            
            # --- Move 1: Forward to 0.25m ---
            print("Forward until 0.25m")
            while True:
                # 1. Check Status (Pause/Battery)
                speed, force_blue = check_status()
                
                # 2. Set LEDs based on status
                if force_blue:
                    set_leds(0, 0, 1) # Blue (Low Battery)
                else:
                    set_leds(0, 65535, 0) # Green (Normal)
                
                # 3. Move Motors
                dmd.left_motor.forward(speed * 0.9)
                dmd.right_motor.forward(speed)
                
                # 4. Check Sensor
                d = sensor.distance
                # print(f"Dist: {d}") 
                if d is not None and 0.15 <= d <= 0.35:
                    break
                sleep(0.05)
            
            # Stop 1 second
            dmd.stop()
            set_leds(1, 0, 0) # Red ON during stop
            sleep(1.0)

            # --- Move 2: Backward to 1.0m ---
            print("Backward until 1.0m")
            while True:
                speed, force_blue = check_status()
                
                # Backward always uses Blue LED, unless we want to strictly follow battery logic.
                # Usually backward indicates Blue, so we keep Blue on.
                set_leds(0, 0, 1) 
                
                dmd.left_motor.backward(speed * 0.9)
                dmd.right_motor.backward(speed)
                
                d = sensor.distance
                if d is not None and 0.9 <= d <= 1.1:
                    break
                sleep(0.05)
                
            dmd.stop()
            set_leds(1, 0, 0)
            sleep(1.0)

            # --- Move 3: Forward to 0.25m (Repeat) ---
            print("Forward until 0.25m")
            while True:
                speed, force_blue = check_status()
                
                if force_blue:
                    set_leds(0, 0, 1)
                else:
                    set_leds(0, 65535, 0)
                
                dmd.left_motor.forward(speed * 0.9)
                dmd.right_motor.forward(speed)
                
                d = sensor.distance
                if d is not None and 0.15 <= d <= 0.35:
                    break
                sleep(0.05) 

            dmd.stop()
            set_leds(1, 0, 0)
            sleep(1.0)
            
    except KeyboardInterrupt:
        dmd.stop()
        dmd.disable()
        set_leds(0, 0, 0)
        print("Stopped by user")