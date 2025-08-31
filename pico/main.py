from machine import Pin, I2C #import the classes Pin and I2C from the module machine
import time #import the module time (part of Micropython's standard library)
from ina219 import INA219 #from the module ina219 import the class INA219
import os

i2c = I2C(0, scl=Pin(9), sda=Pin(8)) #I2C(I2C bus id, scl pin, sda pin, freq(optional))
ina = INA219(i2c) #INA219(I2C communication) - it must pass a machine.I2C object
ina.set_calibration_32V_2A()
button = Pin(15, Pin.IN, Pin.PULL_UP) #Pin(pin_number,mode,pull=none) - mode specifies if input or output pin, pull specifies if internal resistors to be used

#Configurable parameters
delay = 5
COST = 0.192 #average Canadian electricity cost

#Initial states
phantom_time = 0 #will measure how long phatom measurements run for
reading_number = 1 #tracks the reading being taken
button_was_pressed = False #
toggle_state = False #allows for toggling between on and off
session_ended = False #ensures total measurements are outputed once only
session_number = 1
session_file_name = None
led = Pin(14,Pin.OUT)
led.value(0)

#Debounce protection variables
last_button_press = 0
DEBOUNCE_ms = 200

#Real Readings
total_energy_Wh = 0
total_energy_spent = 0

#phantom Readings
total_phantom_energy_Wh = 0
total_phantom_energy_spent = 0

def chunk_sleep(seconds):
    # sleep in 0.1s chunks so button presses are seen quickly
    steps = int(seconds*10)
    for _ in range(steps):
        time.sleep(0.1)
        if button.value()==0:  # allow immediate toggle on next loop
            break

while True:
    # keep LED in sync every loop so it's OFF in phantom/idle and ON in active
    led.value(1 if toggle_state else 0)

    if button.value()==0 and not button_was_pressed:
        #Deboune protection within 200 ms
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time,last_button_press) >DEBOUNCE_ms:
            toggle_state = not toggle_state
            button_was_pressed = True
            last_button_press = current_time

            if toggle_state:
                led.value(1)  # on immediately for the video

                #creates a csv file to store the session information
                session_file_name = f"energy_log_{session_number}.csv"
                print("Writing to:", session_file_name)
                session_number += 1  # avoid accidental overwrite if you press again

                with open(session_file_name, "w") as file:
                    file.write(f"Delay (seconds): {delay}\n")
                    file.write("Reading #, voltage (V), current (mA), power (W), energy (Wh), Cost (CAD)\n") #creates a csv file

                #reset all values for a new session (new device)
                session_ended = False
                reading_number = 1
                total_energy_Wh = 0.0
                total_energy_spent = 0.0
                phantom_time = 0
                total_phantom_energy_Wh = 0.0
                total_phantom_energy_spent = 0.0
            else:
                led.value(0)  # off immediately for the video
                print("[STATE] Active stopped -> entering PHANTOM")

    elif button.value() == 1:
        button_was_pressed = False

    if toggle_state:
        #obtaining values from sensor
        voltage = ina.bus_voltage
        current = abs(ina.current)
        power_W = voltage*(current/1000.0)

        #calculating values
        delay_hours = delay/3600 #(convert period over which measurement is taken to hours)
        current_energy_Wh = power_W * delay_hours #(calculate energy via E/t=P)
        current_energy_spent = (current_energy_Wh/1000) * COST #(covert energy to kW and find cost)

        #incrimenting totals
        total_energy_Wh = total_energy_Wh + current_energy_Wh
        total_energy_spent = total_energy_spent + current_energy_spent

        #adding current reading to .csv file (with debug)
        line = f"{reading_number},{voltage},{current},{power_W}, {current_energy_Wh},{current_energy_spent}"
        print("[ACTIVE WRITE]", line)  # show the exact line in REPL

        try:
            with open(session_file_name, "a") as file:
                file.write(line + "\n")
            try:
                os.sync()
            except Exception:
                pass
            print("[SIZE]", session_file_name, os.stat(session_file_name)[6], "bytes")
        except Exception as e:
            print("[ERROR] active write failed:", e)

        reading_number += 1
        session_ended = False
        chunk_sleep(delay)  # << responsive sleep

    elif not toggle_state and phantom_time<60:
        if session_file_name is not None:
            if phantom_time == 0:
                print("[STATE] PHANTOM started (will take 60 samples)")
            print(f"[STATE] PHANTOM cycle {phantom_time+1}/60")

            #obtaining values from sensor
            phantom_voltage = ina.bus_voltage
            phantom_current = abs(ina.current)
            phantom_power_W = phantom_voltage *(phantom_current/1000.0)

            phantom_delay_hours = delay/3600
            current_phantom_energy_Wh = phantom_power_W * phantom_delay_hours
            current_phantom_energy_spent = (current_phantom_energy_Wh/1000) * COST

            #incrimenting total
            total_phantom_energy_Wh += current_phantom_energy_Wh
            total_phantom_energy_spent += current_phantom_energy_spent

            #adding measurements to .csv file (with debug)
            try:
                with open(session_file_name, "a") as file:
                    if phantom_time ==0:
                        file.write("\nphantom measurements will now be taken!\n")
                        file.write("phantom voltage (V), phantom current (mA), phantom power (W), phantom energy (Wh), Cost (CAD)\n")
                    line = f"{phantom_voltage},{phantom_current},{phantom_power_W},{current_phantom_energy_Wh},{current_phantom_energy_spent}"
                    print("[PHANTOM WRITE]", line)
                    file.write(line + "\n")
                try:
                    os.sync()
                except Exception:
                    pass
                print("[SIZE]", session_file_name, os.stat(session_file_name)[6], "bytes")
            except Exception as e:
                print("[ERROR] phantom write failed:", e)

            #incrimenting phantom time
            phantom_time = phantom_time + 1
            chunk_sleep(delay)  # << responsive sleep
        else:
            time.sleep(0.2)
            continue

    elif not toggle_state and not session_ended and phantom_time >=60:
        #adds real and phantom measurements
        total_energy_Wh = total_energy_Wh + total_phantom_energy_Wh
        total_energy_spent = total_energy_spent + total_phantom_energy_spent

        #outputs total in csv file
        with open(session_file_name, "a") as file:
            file.write("\nSession Summary\n")
            file.write("Total Energy(Wh), Total Cost(CAD)\n")
            file.write(f"{total_energy_Wh},{total_energy_spent}\n")

        session_number +=1
        session_ended = True #ensures this elif block cannot run again so that the total prints once only
        print("[STATE] Summary written. You can open Mu Files and download:", session_file_name)
