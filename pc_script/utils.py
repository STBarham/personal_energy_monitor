import csv 
from pathlib import Path
import math


#function to ask prompts
def ask_float(prompt,allow_blank = False): 
    while True:                         #infinite loop to ensure it continues until valid input obtained
        s = input(prompt).strip()
        if allow_blank and s=="":
            return None
        else:
            try:
                return float(s)
            except ValueError:
                print("Please enter a number")


#function to obtain time of file modification
def get_time_modified(path_object: Path):
    return path_object.stat().st_mtime #obtains the time of modification of each file

#returns the number of readings that would be taken during the period of device use
def ceil_samples(hours:float,dt:float):
    if dt<0:
        return 0
    return int(math.ceil(hours/dt)) #rounds up

def to_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

#using standard candian cost
def infer_rate(main_energy,main_cost):
    total_energy = sum(main_energy)
    total_cost = sum(main_cost)
    if total_energy >0:
        return total_cost/(total_energy/1000.0)
    return None
