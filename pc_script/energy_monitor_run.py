#importing
import csv 
from pathlib import Path
from energy_monitoring_helper_functions import (ask_float, get_time_modified, ceil_samples, to_float, infer_rate)

#---obtaining user input--- 

#ask prompts
device_name = input("What is the name of the device you're analyzing? ").strip()
if not device_name:
    device_name = "Unnamed_Device"
hours_plugged_in = ask_float("How many hours per day is the device plugged in (eg: if plugged in for 12h but only used for 2h, enter 12 here and 2 in next prompt) :")
hours_per_day = ask_float("How many hours per day do you use this device :")
delay_seconds = ask_float("What was the delay between readings in seconds (says it on your csv file) :")
cost_override = ask_float("What is the cost of your electricity in CAD/kWh (press Enter to use the average Canadian value) :", allow_blank=True)
daily_use = input("Do you use this device every day?").strip().lower()

#csv selection
csv_name = input("What is the name of the csv file you would like to analyse (press Enter to use the latest file) :").strip()

if csv_name:
    csv_path = Path(csv_name) #makes a path object which represents a file or directory
else:
    files = list(Path(".").glob("energy_log_*.csv")) #will generate a list of all files that match that pattern in this directoy
    if not files:
        print("No energy logs found. Please provide a file name")
        raise SystemExit(1) 
    files.sort(key=get_time_modified, reverse =True) #arranges them from most recent to earliest file
    csv_path = files[0] #obtains the last modified file

if not csv_path.exists():
    print(f"Couldn't find '{csv_path.name}'. Make sure its here and try again")
    raise SystemExit(1)
print(f"Using CSV: {csv_path.name}")

#-----parsing throuhg csv----
mode = "main"
main_energy = []
main_cost = []
main_power = []
phantom_energy = []
phantom_cost = []
phantom_power = []
summary_energy_Wh = None
summary_cost = None

#find first non empty row
with open(csv_path, "r", newline = "") as f:
    rdr= csv.reader(f)
    for row in rdr:
        if not row or all(c.strip()=="" for c in row): #if row is empty or all values are empty skip it ("  "  or ",,,")
            continue

        first = row[0].strip().lower()

        #switching modes based on reading type
        if "phantom measurements" in first:
            mode = "phantom"
            continue                    #skips remaining code to avoid parsin through words, immediatly goes to next row (will be the readings of that mode)
        if "session summary" in first:
            mode = "summary"
            continue 

        #skipping headers
        if any(k in first for k in ["reading #", "phantom voltage", "total energy(wh)"]):
            continue

        #obtaining numeric values
        vals = [to_float(c) for c in row]
        nums = [x for x in vals if x is not None] #since to_float will return None on non-numeric values, nums contains numerical values only
        if not nums:
            continue                            #if there was no numerical values, go to next row

        
        if mode == "main":
            #last 2 numeric cells in main are energy_Wh and cost
            if len(nums) >= 3:
                power_W = nums[-3]
                energy_Wh = nums[-2] 
                cost = nums[-1]
                main_energy.append(energy_Wh if energy_Wh is not None else 0.0)
                main_cost.append(cost if cost is not None else 0.0)
                main_power.append(power_W if power_W is not None else 0.0)

        elif mode == "phantom":
            if len(nums) >=3:
                power_W = nums[-3]
                energy_Wh = nums[-2]
                cost = nums[-1]
                phantom_energy.append(energy_Wh if energy_Wh is not None else 0.0)
                phantom_cost.append(cost if cost is not None else 0.0)
                phantom_power.append(power_W if power_W is not None else 0.0)

            
        elif mode == "summary":
            if len(nums)>=2 and summary_energy_Wh is None:
                summary_energy_Wh = nums[0]
                summary_cost = nums[1]


#---Potential errors-----
if not main_energy:
    print("No readings found. Cannot proceed")
    raise SystemExit(1)

dt = delay_seconds/3600.9 #converting delay to hours
if dt<=0:
    print("Delay must be larger than 0")
    raise SystemExit(1)

#------Prefix + Tail Computation------
if hours_plugged_in is None:
    hours_plugged_in = 0.0
hours_plugged_in = max(0.0,min(24,float(hours_plugged_in)))

H = float(hours_per_day)
H = max(0.0,min(24,H))
T = len(main_energy)*dt #test period

if cost_override is None:
    rate_kWh = infer_rate(main_energy, main_cost)
else:
    rate_kWh = cost_override

#ON (main block)
#daily device use duration is same or less than device test duration
if H<= T:
    n = ceil_samples(H, dt)
    daily_on_Wh = sum(main_energy[0:n])
    tail_avg_W = None
else:
    whole_Wh = sum(main_energy)
    m = int(max(5,0.1*(len(main_energy))))
    if m > 0:
        tail_avg_W = sum(main_energy[-m:])/(m*dt)
    else:
        tail_avg_W=0.0
    daily_on_Wh = whole_Wh + (tail_avg_W)*(H - T)

#OFF(Phantom)
if len(phantom_energy)>0:
    phantom_avg_W = sum(phantom_energy)/(len(phantom_energy)*dt)
else:
    phantom_avg_W = 0.0
daily_off_Wh = phantom_avg_W * max(0.0, hours_plugged_in - H)

#totals
daily_total_Wh = daily_on_Wh + daily_off_Wh

if rate_kWh is not None:
    daily_cost = (daily_total_Wh/1000.0) * rate_kWh
    no_phantom_daily_cost = (daily_on_Wh/1000.0) * rate_kWh
else:
    daily_cost = None

while daily_use not in ("yes","no"):
    print("only yes/no are valid answer types")
    daily_use = input("Do you use this device every day?").strip().lower()

uses_daily = None
if daily_use == "yes":
    uses_daily = True

if uses_daily == True:
    monthly_Wh = daily_total_Wh * 30
    monthly_cost = daily_cost * 30 if daily_cost is not None else None
    no_phantom_monthly_total = daily_on_Wh *30 
    no_phantom_monthly_cost = no_phantom_daily_cost * 30
    yearly_Wh = monthly_Wh *12
    yearly_cost = monthly_cost * 12
    no_phantom_yearly_total = no_phantom_monthly_total *12
    no_phantom_yearly_cost = no_phantom_monthly_cost * 12

else:
    monthly_Wh = None
    monthly_cost = None

#----Reporting-----
print("\n=======Energy Report=======")
print(f"Device name:{device_name}")
print(f"Main readings:{len(main_energy)}     Phantom readings: {len(phantom_energy)}")
print(f"Delay: {delay_seconds} s   (dt:{dt:.3f} h)")
print(f"User daily ON time: {H:.3f} h")

if H<= T:
    print(f"Method: Prefix (used first {ceil_samples(H,dt)} readings)")
else:
    print(f"Method: PREFIX + TAIL (used all {len(main_energy)} readings, then tail avg for {H - T:.3f} h)")
    print(f"Tail steady-state ~ {tail_avg_W:.3f} W")

print(f"\nDaily ON energy:   {daily_on_Wh:.6f} Wh")
print(f"Daily OFF energy:  {daily_off_Wh:.6f} Wh  (phantom avg ~ {phantom_avg_W:.3f} W)")
print(f"Daily TOTAL:       {daily_total_Wh:.6f} Wh")

if daily_cost is not None:
    print(f"Daily COST:  {daily_cost:.6f}  (rate ~ {rate_kWh:.6f} per kWh)")
else:
    print("Daily COST:        N/A (no cost rate provided or inferable)")

if monthly_Wh is not None:
    print(f"Monthly TOTAL (assuming daily use): {monthly_Wh:.3f} Wh")
    print(f"Monthly COST (assuming daily use): {monthly_cost:.3f} CAD")
    print(f"Yearly Total (assuming daily use) : {yearly_Wh:.3f} Wh")
    print(f"Yearly COST (assuming daily use): {yearly_cost:.3f} CAD")
    print("If you unplugged your device while not in use, you could reduce phantom load")
    print(f"This would reduce\n your yearly total to {no_phantom_yearly_total}\n your yearly cost to {no_phantom_yearly_cost}")

#-----Plotting------
import matplotlib.pyplot as plt

#Builing time axis
t_main = []
t_ph = []

for i in range(len(main_power)):
    t_main.append(i*dt)

T_main = len(main_power) * dt

for i in range(len(phantom_power)):
    t_ph.append(T_main + (i *dt))

#creating plot
plt.figure()
plt.plot(t_main, main_power, label="ON (main)")
if phantom_power:
    plt.plot(t_ph, phantom_power, label="OFF (phantom)")

plt.xlabel("Time (hours)")
plt.ylabel("Instant Power (W)")
plt.title(f"Power vs Time — {device_name}")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

#-----Creating Final User Report

report_path = "energy_report.txt"

with open(report_path, "w", encoding="utf-8") as rep:
    rep.write("=======Energy Report=======\n")
    rep.write(f"\nDevice name:{device_name}\n")
    rep.write(f"Main readings:{len(main_energy)}     Phantom readings: {len(phantom_energy)}\n")
    rep.write(f"Delay: {delay_seconds} s   (dt:{dt:.3f} h)\n")
    rep.write(f"User daily ON time: {H:.3f} h\n")

    if H <= T:
        rep.write(f"\nMethod: Prefix (used first {ceil_samples(H,dt)} readings)\n")
    else:
        rep.write(f"\nMethod: PREFIX + TAIL (used all {len(main_energy)} readings, then tail avg for {H - T:.3f} h)\n")
        rep.write(f"Tail steady-state ~ {tail_avg_W:.3f} W\n")

    rep.write(f"\nDaily ON energy:   {daily_on_Wh:.6f} Wh\n")
    rep.write(f"Daily OFF energy:  {daily_off_Wh:.6f} Wh  (phantom avg ~ {phantom_avg_W:.3f} W)\n")
    rep.write(f"Daily TOTAL:       {daily_total_Wh:.6f} Wh\n")

    if daily_cost is not None:
        rep.write(f"\nDaily COST:  {daily_cost:.6f}  (rate ~ {rate_kWh:.6f} per kWh)\n")
    else:
        rep.write("Daily COST:        N/A (no cost rate provided or inferable)\n")

    if monthly_Wh is not None:
        rep.write(f"Monthly TOTAL (assuming daily use): {monthly_Wh:.3f} Wh\n")
        rep.write(f"Monthly COST (assuming daily use): {monthly_cost:.3f} CAD\n")
        rep.write(f"Yearly Total (assuming daily use) : {yearly_Wh:.3f} Wh\n")
        rep.write(f"Yearly COST (assuming daily use): {yearly_cost:.3f} CAD\n")
        rep.write("If you unplugged your device while not in use, you could reduce phantom load\n")
        rep.write(f"This would reduce\n your yearly total to {no_phantom_yearly_total}\n your yearly cost to {no_phantom_yearly_cost}\n")

print("Text report saved to:", report_path)

plt.show()
