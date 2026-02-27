import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles
from cocotb.handle import Force, Release

# ─────────────────────────────────────────
# BIT FIELD MAP for sg2dl_pd
# Verify these offsets against your RTL port definition
# ─────────────────────────────────────────
SG2DL_LAYER_END_BIT = 29   # Bit position of layer_end in sg2dl_pd
SG2DL_SLICE_ID_LSB  = 0    # Example: slice ID starts at bit 0
SG2DL_SLICE_ID_MSB  = 12   # Example: slice ID ends at bit 12

def extract_bit(val, bit):
    return (val >> bit) & 0x1

def extract_field(val, msb, lsb):
    mask = (1 << (msb - lsb + 1)) - 1
    return (val >> lsb) & mask

# ─────────────────────────────────────────
# RESET + INIT
# ─────────────────────────────────────────
async def reset_and_init(dut):
    # ── CLOCK GATE BYPASS ──
    dut.u_dat_fifo.clk_mgated_enable.value        = Force(1)
    dut.u_wt_fifo.clk_mgated_enable.value         = Force(1)
    dut.u_dat_fifo.master_clk_gating_disabled.value = Force(1)
    dut.u_wt_fifo.master_clk_gating_disabled.value  = Force(1)

    # ── TIME 0 GROUNDING ──
    dut.nvdla_core_rstn.value          = 0
    dut.pwrbus_ram_pd.value            = 0
    dut.reg2dp_op_en.value             = 0
    dut.cdma2sc_dat_updt.value         = 0
    dut.cdma2sc_wt_updt.value          = 0
    dut.accu2sc_credit_vld.value       = 0
    dut.accu2sc_credit_size.value      = 0
    dut.cdma2sc_dat_pending_ack.value  = 0
    dut.cdma2sc_wt_pending_ack.value   = 0
    dut.reg2dp_conv_mode.value         = 0
    dut.reg2dp_proc_precision.value    = 0
    dut.reg2dp_batches.value           = 0
    dut.reg2dp_datain_height_ext.value = 3
    dut.reg2dp_dataout_height.value    = 3
    dut.reg2dp_dataout_width.value     = 3
    dut.reg2dp_atomics.value           = 3
    dut.reg2dp_weight_kernel.value     = 0
    dut.reg2dp_rls_slices.value        = 3
    dut.reg2dp_skip_data_rls.value     = 0
    dut.reg2dp_skip_weight_rls.value   = 0
    dut.reg2dp_data_reuse.value        = 0
    dut.reg2dp_weight_reuse.value      = 0

    # ── FIFO STATE FORCES ──
    dut.u_dat_fifo.wr_count.value    = Force(0)
    dut.u_wt_fifo.wr_count.value     = Force(0)
    dut.u_dat_fifo.rd_count.value    = Force(0)
    dut.u_wt_fifo.rd_count.value     = Force(0)
    dut.u_dat_fifo.wr_busy_int.value = Force(0)
    dut.u_wt_fifo.wr_busy_int.value  = Force(0)

    # ── RESET PULSE ──
    await ClockCycles(dut.nvdla_core_clk, 100)
    dut.nvdla_core_rstn.value = 1
    await ClockCycles(dut.nvdla_core_clk, 50)  # Fix: 50 not 20

    # ── RELEASE FIFO FORCES (keep clock gate forces) ──
    dut.u_dat_fifo.wr_count.value    = Release()
    dut.u_wt_fifo.wr_count.value     = Release()
    dut.u_dat_fifo.rd_count.value    = Release()
    dut.u_wt_fifo.rd_count.value     = Release()
    dut.u_dat_fifo.wr_busy_int.value = Release()
    dut.u_wt_fifo.wr_busy_int.value  = Release()

    # ── DIAGNOSTIC LOG (always, not just on failure) ──
    dut._log.info(f"clk_mgated_enable (dat) = {dut.u_dat_fifo.clk_mgated_enable.value}")
    dut._log.info(f"clk_mgated_enable (wt)  = {dut.u_wt_fifo.clk_mgated_enable.value}")

    # ── ROBUST IDLE CHECK ──
    idle_seen = False
    for i in range(50):
        await RisingEdge(dut.nvdla_core_clk)
        val = dut.sc_state.value
        if val.is_resolvable and int(val) == 0:
            idle_seen = True
            dut._log.info(f"FSM reached IDLE at cycle {i}.")
            break

    if not idle_seen:
        dut._log.error(f"sc_state             = {dut.sc_state.value}")
        dut._log.error(f"clk_mgated_enable    = {dut.u_dat_fifo.clk_mgated_enable.value}")
        dut._log.error(f"master_clk_gating_disabled = {dut.u_dat_fifo.master_clk_gating_disabled.value}")
        raise AssertionError("FSM Deadlock: Clock gate likely still stuck.")

# ─────────────────────────────────────────
# MAIN TEST
# ─────────────────────────────────────────
@cocotb.test()
async def test_exact_io_match(dut):
    # Start Clocks
    cocotb.start_soon(Clock(dut.nvdla_core_clk, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.nvdla_core_ng_clk, 10, unit="ns").start())

    # IMPORTANT: Allow clocks to settle and propagate Force values 
    # through the combinational cloud before the reset sequence.
    await ClockCycles(dut.nvdla_core_clk, 3) 
    
    await reset_and_init(dut)
    
    # ... rest of your test ...

def test_vlsi_signoff_runner():
    import os
    from pathlib import Path
    from cocotb_tools.runner import get_runner, Verilog

    sim = os.getenv("SIM", "icarus")
    
    # 1. Path Discovery
    base_dir = os.getenv("ISOLATED_SOURCES")
    sources_dir = Path(base_dir).resolve() if base_dir else Path(__file__).resolve().parent.parent / "sources"

    # 2. Strategic Source Selection
    # We only explicitly include files that Icarus might struggle to find 
    # automatically or that define the base primitives.
    sources = [
        sources_dir / "cells" / "stdcells.v",
        # Only include the specific vlib that was previously missing
        Verilog(sources_dir / "vlibs" / "nv_assert_no_x.vlib"),
        sources_dir / "NV_CLK_gate_power.v",
        sources_dir / "NV_NVDLA_CSC_SG_dat_fifo.v",
        sources_dir / "NV_NVDLA_CSC_SG_wt_fifo.v",
        sources_dir / "NV_NVDLA_CSC_sg.v",
    ]

    # 3. Build and Test
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel="NV_NVDLA_CSC_sg",
        always=True,
        build_args=[
            f"-y{sources_dir}/cells",
            f"-y{sources_dir}/vlibs", # This handles the rest of the vlibs automatically
            f"-I{sources_dir}/cells",
            f"-I{sources_dir}/vlibs",
            "-Y.v",
            "-Y.vlib", # IMPORTANT: Tell Icarus to look for .vlib files in the -y directories
            "-grelative-include",
            "-g2012",
            "-D", "VLIB_BYPASS_POWER_CG"
        ]
    )

    runner.test(
        hdl_toplevel="NV_NVDLA_CSC_sg",
        test_module=Path(__file__).stem,
        plusargs=["+fifogen_disable_master_clk_gating"]
    )