# 1. Load the Sky130 Library
read_liberty ./lib/nangate45nm.lib

# Load Library and Netlist
read_verilog ./netlist.v
link_design NV_NVDLA_CSC_sg

# Load Constraints
read_sdc NV_NVDLA_partition_c.sdc

# Report Timing to File
#report_checks -path_delay max -format full_clock_expanded -fields {cap trans incr path} -digits 3 > ./netlist/sta_full_report.rpt

#report_checks -path_delay max -fields {cap slew incr path} -digits 3 > ./netlist/sta_full_report.rpt
# This format typically forces the inclusion of every pin in the path
report_checks -path_delay max -fields {cap slew incr path} -format full -digits 3 > ./netlist/sta_full_report.rpt
# Optional: Report Power
report_power > ./netlist/power_report.rpt

# Check if the clock actually exists on the pins
report_clock_properties

# List all registers to see their names
all_registers

exit