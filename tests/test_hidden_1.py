import os
import re
import subprocess
import pytest
from pathlib import Path
from cocotb_tools.runner import get_runner, Verilog
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, ClockCycles

# --- CONFIGURATION ---
CONTAINER_ID = "openlane"
WNS_TARGET = 0.0 

def get_dynamic_container_path(state_file_override=None):
    if state_file_override:
        state_file = state_file_override
    else:
        base_dir = os.getenv("ISOLATED_SOURCES")
        if base_dir:
            state_file = Path(base_dir).resolve() / ".task_dir"
        else:
            test_dir = Path(__file__).resolve().parent
            state_file = test_dir.parent / "sources" / ".task_dir"
    
    if state_file.exists():
        path = state_file.read_text().strip()
        if path: return path
    return "/openlane/PHINITY"

# ==============================================================================
# 1. THE ORCHESTRATOR (Synthesis & Simulation)
# ==============================================================================
def test_vlsi_signoff_runner():
    """Orchestrates sync, container lifecycle, synthesis, and Cocotb simulation."""
  ##  os.environ["DOCKER_HOST"] = "tcp://host.docker.internal:2375"
    
    sim = os.getenv("SIM", "icarus")
    
    # --- DYNAMIC PATH DISCOVERY ---
    base_dir = os.getenv("ISOLATED_SOURCES")
    if base_dir:
        sources_dir = Path(base_dir).resolve()
        state_file = sources_dir / ".task_dir"
    else:
        proj_path = Path(__file__).resolve().parent.parent 
        sources_dir = proj_path / "sources"
        state_file = sources_dir / ".task_dir"

    current_task_path = get_dynamic_container_path(state_file)

    # --- Step 1: Ensure unique container exists ---
    print(f"\n>>> Using unique container: {CONTAINER_ID}")
    print(f">>> Task path: {current_task_path}")
    
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name={CONTAINER_ID}"],
        capture_output=True,
        text=True
    )
    
    if not result.stdout.strip():
        print(f">>> Creating new container: {CONTAINER_ID}")
        subprocess.run([
            "docker", "run", "-d", 
            "--name", CONTAINER_ID,
            "efabless/openlane:latest",
            "tail", "-f", "/dev/null"
        ], check=True)
    
    # --- Step 2: Sync to Docker ---
    print(f"\nSyncing to Docker container {CONTAINER_ID} at {current_task_path}...")
    subprocess.run(["docker", "exec", CONTAINER_ID, "mkdir", "-p", current_task_path], check=True)
    subprocess.run(f"docker cp \"{sources_dir}/.\" {CONTAINER_ID}:{current_task_path}/", shell=True, check=True)

# --- Step 3: Setup Cocotb Runner & Synthesis ---

    netlist_path = sources_dir / "netlist.v"
    # Matches the NVDLA Sequence Generator filename
    rtl_path = sources_dir / "NV_NVDLA_CSC_sg.v"
    wt_fifo_path = sources_dir / "NV_NVDLA_CSC_SG_wt_fifo.v"
    dat_fifo_path = sources_dir / "NV_NVDLA_CSC_SG_dat_fifo.v"

    assert_path = Verilog(sources_dir / "vlibs" / "nv_assert_no_x.vlib")
    clk_gate_path = sources_dir / "NV_CLK_gate_power.v"
    
    # Path to the Nangate 45nm model file found to clear the blocker
    stdcell_path = sources_dir / "cells" / "stdcells.v"

    if not netlist_path.exists():
        print(">>> [INIT] Netlist not found. Generating initial baseline netlist...")
        # Execute the synthesis portion ONLY
        subprocess.run([
            "docker", "exec", CONTAINER_ID, "bash", "-c", 
            f"cd {current_task_path} && yosys -t script.tcl"
        ], check=True)
        # Pull it to host so the runner can build the simulation
        subprocess.run([
            "docker", "cp", f"{CONTAINER_ID}:{current_task_path}/netlist.v", str(netlist_path)
        ], check=True)
    else:
        print(">>> [SKIP] Netlist exists. Using current version for testing.")

    # We run functional tests on the RTL to check the 12-cycle pipeline
    # Ordered sources: Library Models -> vlibs -> Sub-modules (Weight & Data FIFOs) -> Top-level RTL
    sources = [stdcell_path] + [wt_fifo_path, dat_fifo_path, rtl_path, clk_gate_path, assert_path]
    
    runner = get_runner(sim)

    runner.build(
        sources=sources,
        hdl_toplevel="NV_NVDLA_CSC_sg",
        always=True,
        build_args=[
            f"-y{sources_dir}/cells",
            f"-y{sources_dir}/vlibs",
            f"-I{sources_dir}/cells",
            f"-I{sources_dir}/vlibs",
            "-Y.v",     
            "-grelative-include",
            "-g2012"
        ]
    )    

    runner.test(
        hdl_toplevel="NV_NVDLA_CSC_sg",
        test_module=Path(__file__).stem,
        extra_env={"ACTIVE_CONTAINER_ID": CONTAINER_ID}
    )
# ==============================================================================
# 2. VLSI SIGN-OFF TESTS (STA Timing)
# ==============================================================================

@cocotb.test()
async def test_wns_slack(dut):
    """Cocotb Test: STA check. Pipelined branch must have slack >= 0."""
    current_task_path = get_dynamic_container_path()
    
    # Step 1: Execute OpenSTA inside container
    cmd = ["docker", "exec", CONTAINER_ID, "bash", "-c", f"cd {current_task_path} && sta -no_init run_sta.tcl"]
    subprocess.run(cmd, check=True)

    # Step 2: Copy report back to host
    subprocess.run(f"docker cp {CONTAINER_ID}:{current_task_path}/timing_report.rpt .", shell=True, check=True)

    # Step 3: Parse Slacks
    with open("timing_report.rpt", "r") as f:
        report_content = f.read()

    all_slacks = re.findall(r"([-+]?[\d\.]+)\s+slack", report_content)
    if all_slacks:
        wns = min(float(s) for s in all_slacks)
        dut._log.info(f"Worst Negative Slack: {wns}ns (Target: >= {WNS_TARGET})")
        assert wns >= WNS_TARGET, f"Timing check failed: WNS is {wns}ns"
    else:
        raise RuntimeError("Could not find slack values in the STA report.")




@cocotb.test()
async def test_basic_sg_operation(dut):
    """
    Test: Apply inputs for a simple Direct Convolution (DC) operation
    and verify corresponding outputs (sg2dl_pvld, sg2wl_pvld, sc_state).
    """

    # ------------------------------------------------------------------ #
    # 1. Clock setup
    # ------------------------------------------------------------------ #
    cocotb.start_soon(Clock(dut.nvdla_core_clk,    10, units="ns").start())
    cocotb.start_soon(Clock(dut.nvdla_core_ng_clk, 10, units="ns").start())

    # ------------------------------------------------------------------ #
    # 2. Reset
    # ------------------------------------------------------------------ #
    dut.nvdla_core_rstn.value = 0

    # Drive all inputs to safe defaults
    dut.reg2dp_op_en.value            = 0
    dut.reg2dp_conv_mode.value        = 0   # DC mode
    dut.reg2dp_proc_precision.value   = 0   # INT8
    dut.reg2dp_data_reuse.value       = 0
    dut.reg2dp_skip_data_rls.value    = 0
    dut.reg2dp_weight_reuse.value     = 0
    dut.reg2dp_skip_weight_rls.value  = 0
    dut.reg2dp_batches.value          = 0   # batch=1
    dut.reg2dp_datain_format.value    = 0   # feature map (not pixel)
    dut.reg2dp_datain_height_ext.value  = 3  # height = 4
    dut.reg2dp_y_extension.value      = 0
    dut.reg2dp_weight_width_ext.value = 0   # R=1
    dut.reg2dp_weight_height_ext.value= 0   # S=1
    dut.reg2dp_weight_channel_ext.value = 0 # C=1
    dut.reg2dp_weight_kernel.value    = 0   # K=1
    dut.reg2dp_dataout_width.value    = 3   # W_out=4
    dut.reg2dp_dataout_height.value   = 3
    dut.reg2dp_data_bank.value        = 0
    dut.reg2dp_weight_bank.value      = 0
    dut.reg2dp_atomics.value          = 3   # atomics=4
    dut.reg2dp_rls_slices.value       = 3

    dut.cdma2sc_dat_updt.value        = 0
    dut.cdma2sc_dat_entries.value     = 0
    dut.cdma2sc_dat_slices.value      = 0
    dut.cdma2sc_wt_updt.value         = 0
    dut.cdma2sc_wt_kernels.value      = 0
    dut.cdma2sc_wt_entries.value      = 0
    dut.cdma2sc_wmb_entries.value     = 0
    dut.cdma2sc_dat_pending_ack.value = 0
    dut.cdma2sc_wt_pending_ack.value  = 0
    dut.accu2sc_credit_vld.value      = 0
    dut.accu2sc_credit_size.value     = 0
    dut.pwrbus_ram_pd.value           = 0

    # Hold reset for 5 cycles
    await ClockCycles(dut.nvdla_core_clk, 5)
    dut.nvdla_core_rstn.value = 1
    await ClockCycles(dut.nvdla_core_clk, 2)

    # ------------------------------------------------------------------ #
    # 3. Check initial state = IDLE (sc_state == 0)
    # ------------------------------------------------------------------ #
    await RisingEdge(dut.nvdla_core_clk)
    sc_state_val = int(dut.sc_state.value)
    assert sc_state_val == 0, \
        f"[FAIL] After reset, expected sc_state=0 (IDLE), got {sc_state_val}"
    cocotb.log.info(f"[PASS] sc_state=IDLE ({sc_state_val}) after reset")

    # ------------------------------------------------------------------ #
    # 4. Feed CDMA data & weight availability updates
    #    (slices_avl and kernels_avl must be >= threshold before FSM
    #     enters BUSY and generates packages)
    # ------------------------------------------------------------------ #
    # Provide 8 slices of data
    dut.cdma2sc_dat_updt.value   = 1
    dut.cdma2sc_dat_slices.value = 8
    dut.cdma2sc_dat_entries.value= 4
    await RisingEdge(dut.nvdla_core_clk)
    dut.cdma2sc_dat_updt.value   = 0

    # Provide 4 kernels of weights
    dut.cdma2sc_wt_updt.value    = 1
    dut.cdma2sc_wt_kernels.value = 4
    dut.cdma2sc_wt_entries.value = 4
    await RisingEdge(dut.nvdla_core_clk)
    dut.cdma2sc_wt_updt.value    = 0

    # ------------------------------------------------------------------ #
    # 5. Assert op_en -> FSM should move IDLE -> BUSY (no bank change)
    # ------------------------------------------------------------------ #
    dut.reg2dp_op_en.value = 1
    await RisingEdge(dut.nvdla_core_clk)
    dut.reg2dp_op_en.value = 0   # pulse for one cycle is typical

    # Wait up to 20 cycles for sc_state to reach BUSY (2)
    busy_seen = False
    for _ in range(20):
        await RisingEdge(dut.nvdla_core_clk)
        s = int(dut.sc_state.value)
        cocotb.log.info(f"  sc_state = {s}")
        if s == 2:
            busy_seen = True
            break

    assert busy_seen, "[FAIL] sc_state never reached BUSY (2)"
    cocotb.log.info("[PASS] sc_state reached BUSY")

    # ------------------------------------------------------------------ #
    # 6. Provide accumulator credits so dat_pop_ready can fire
    # ------------------------------------------------------------------ #
    dut.accu2sc_credit_vld.value  = 1
    dut.accu2sc_credit_size.value = 7   # max credit
    await ClockCycles(dut.nvdla_core_clk, 3)
    dut.accu2sc_credit_vld.value  = 0

    # ------------------------------------------------------------------ #
    # 7. Wait and check that sg2dl_pvld and sg2wl_pvld eventually pulse
    # ------------------------------------------------------------------ #
    dl_seen = False
    wl_seen = False

    for cycle in range(60):
        await RisingEdge(dut.nvdla_core_clk)

        dl = int(dut.sg2dl_pvld.value)
        wl = int(dut.sg2wl_pvld.value)
        s  = int(dut.sc_state.value)

        cocotb.log.info(
            f"  cycle={cycle:3d} | sc_state={s} | "
            f"sg2dl_pvld={dl} sg2dl_pd=0x{int(dut.sg2dl_pd.value):08x} | "
            f"sg2wl_pvld={wl} sg2wl_pd=0x{int(dut.sg2wl_pd.value):05x}"
        )

        if dl:
            dl_seen = True
            # Basic sanity: stripe_length field [23:17] should be > 0
            pd_val      = int(dut.sg2dl_pd.value)
            stripe_len  = (pd_val >> 17) & 0x7F
            assert stripe_len > 0, \
                f"[FAIL] sg2dl_pd stripe_length=0 (pd=0x{pd_val:08x})"
            cocotb.log.info(
                f"[PASS] sg2dl_pvld=1 | stripe_length={stripe_len} | "
                f"pd=0x{pd_val:08x}"
            )

        if wl:
            wl_seen = True
            wt_pd    = int(dut.sg2wl_pd.value)
            wt_size  = wt_pd & 0x7F          # bits [6:0]
            assert wt_size > 0, \
                f"[FAIL] sg2wl_pd weight_size=0 (pd=0x{wt_pd:05x})"
            cocotb.log.info(
                f"[PASS] sg2wl_pvld=1 | weight_size={wt_size} | "
                f"pd=0x{wt_pd:05x}"
            )

        if dl_seen and wl_seen:
            break

    assert dl_seen, "[FAIL] sg2dl_pvld never went high"
    assert wl_seen, "[FAIL] sg2wl_pvld never went high"

    cocotb.log.info("=" * 60)
    cocotb.log.info("[PASS] Both sg2dl_pvld and sg2wl_pvld observed.")
    cocotb.log.info("       Output packets contain non-zero payload fields.")
    cocotb.log.info("       Basic input -> output verification PASSED.")
    cocotb.log.info("=" * 60)
