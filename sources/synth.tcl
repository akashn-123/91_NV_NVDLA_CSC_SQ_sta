# 1. Setup Variables
set MODULE "NV_NVDLA_CSC_sg"
set LIB_FILE "./lib/nangate45nm.lib" 
set RTL_DIR "./csc"
set OUTPUT_DIR "./netlist"
set VLIB_DIR "./vlibs"

# 2. Read Library and Cell Models
yosys read_liberty -lib $LIB_FILE
#yosys read_verilog -sv -lib ./csc/rams/*.v
#yosys read_verilog -sv -lib {*}[glob ./csc/rams/*.v]

set files [glob $RTL_DIR/*.v]
foreach f $files {
    yosys read_verilog -sv $f
}
yosys read_verilog -sv -overwrite -lib ./vlibs/NV_CLK_gate_power.v

# 3. Elaborate Hierarchy
yosys hierarchy -check -top $MODULE -libdir $VLIB_DIR

# Define NVDLA-specific sink/source modules as blackboxes to prevent the error
#yosys blackbox NV_BLKBOX_SINK
#yosys blackbox NV_BLKBOX_SRC
#yosys blackbox NV_DW_lsd

# Re-run hierarchy to link everything now that blackboxes are defined
yosys hierarchy -check -top $MODULE

# 4. Synthesis Flow
yosys proc
yosys opt -full
yosys fsm
yosys opt -full
yosys wreduce
yosys techmap
yosys techmap -map +/adff2dff.v
yosys opt -full

# 5. Map to Target Library (ABC) - STANDARD MAPPING
yosys dfflibmap -liberty $LIB_FILE
# Removed -retime and aggressive scripts
yosys abc -liberty $LIB_FILE -D 900
yosys opt -full

# 6. Final Netlist Cleaning
yosys flatten
yosys splitnets -format __
yosys opt_clean -purge
yosys simplemap
yosys abc -liberty $LIB_FILE -g gates
yosys opt_clean -purge

# 7. Write Outputs
yosys stat -liberty $LIB_FILE
yosys write_verilog -noattr -noexpr -nohex "netlist.v"