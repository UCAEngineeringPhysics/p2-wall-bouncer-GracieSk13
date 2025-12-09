from machine import Pin, PWM, reset
from time import ticks_us

class DistanceSensor:
    def __init__(self, trig_id, echo_id, trig_freq=12):
        self.trig_pin = PWM(Pin(trig_id), freq=trig_freq, duty_ns=10_000)
       
        self.echo_pin = Pin(echo_id, Pin.IN, Pin.PULL_DOWN)
        self.echo_pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._echo_handler)
        
        self.distance = 0.0
        self._start_time = None

    def _echo_handler(self, pin):
        if pin.value() == 1:
            self._start_time = ticks_us()
            
        else:
            dt = ticks_us() - self._start_time
            if dt < 100:
                self.distance = 0.0
            elif 100 <= dt < 38000:
                self.distance = dt / 58 / 100
            else:
                self.distance = None

if __name__ == "__main__":
    from time import sleep_ms

    sensor = DistanceSensor(trig_id=9, echo_id=8, trig_freq=15)

    try:
        while True:
            print(f"Distance: {sensor.distance} m")
            sleep_ms(200)
            
    except KeyboardInterrupt:
        reset()
        
        