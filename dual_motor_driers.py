#motor driver part 2 but this is a dual one
from motor_driver import MotorDriver
from machine import Pin


class DualMotorDriver:
    def __init__(self, left_ids, right_ids, stby_id):
        # left_ids and right_ids are tuples: (pwm, in1, in2)
        self.left_motor = MotorDriver(*left_ids)
        self.right_motor = MotorDriver(*right_ids)
        self.stby_pin = Pin(stby_id, Pin.OUT)
        
        self.disable()
        
    def disable(self):
        self.stby_pin.off()
        
    def enable(self):
        self.stby_pin.on()
        
    def stop(self):
        self.left_motor.stop()
        self.right_motor.stop()
        
    def linear_forward(self, speed=0):
        self.left_motor.forward(speed * 0.9)
        self.right_motor.forward(speed)
        
    def linear_backward(self, speed=0):
        self.left_motor.backward(speed * 0.9)
        self.right_motor.backward(speed)
        
    def spin_left(self, speed=0): 
        self.left_motor.backward(speed)
        self.right_motor.forward(speed)
        
    def spin_right(self, speed=0):
        self.left_motor.forward(speed)
        self.right_motor.backward(speed)  
        

#test
if __name__=="__main__":
    from time import sleep
    
    #setup
    
    dmd = DualMotorDriver(left_ids=(15, 13, 14), right_ids=(16, 18, 17), stby_id=12)
    dmd.stby_pin.on()
    
    
    dmd.linear_forward(speed=0.5) # <--- THIS MAKES BOTH MOVE
    sleep(1.0)
    
    dmd.spin_left(speed=0.3)
    sleep(0.5)
    
    dmd.linear_backward(speed=0.5) # <--- THIS MAKES BOTH MOVE
    sleep(1.0)
    
    dmd.spin_right(speed=0.3)
    sleep(0.5)
    
    dmd.stop()
    dmd.disable()
  
    #  STOP
    print("Stopping")
    dmd.stop()
    dmd.disable()
    
    
   #dmd.linear_motor.forward(speed = 0.5)
    #sleep(2)
    #dmd.left_motor.stop()
    #disables the motor
   #dmd.right_motor.backward(speed = 0.7)
    
    
#create new ****************************
#from two_driver import DualMotorDriver
#     ^same as file name  ^same as class
#