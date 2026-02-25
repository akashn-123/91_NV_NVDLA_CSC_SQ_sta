\# Specification: NV\_NVDLA\_CSC\_sg (Convolution Sequence Generator)



\## 1. Overview



The `NV\_NVDLA\_CSC\_sg` module is the \*\*Sequence Generator\*\* submodule of the NVDLA (NVIDIA Deep Learning Accelerator) Convolutional Sequence Controller (CSC). It generates ordered sequences of data and weight loading commands to the downstream data loader (`sg2dl`) and weight loader (`sg2wl`) pipelines, coordinating convolution scheduling across multiple operational modes.



---



\## 2. Interface Specification



\### 2.1 Clock and Reset



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `nvdla\_core\_clk` | I | 1 | Primary clock for all datapath logic |

| `nvdla\_core\_ng\_clk` | I | 1 | Non-gated clock for credit/cbuf tracking logic |

| `nvdla\_core\_rstn` | I | 1 | Active-low synchronous reset |



\### 2.2 Register Interface (reg2dp)



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `reg2dp\_op\_en` | I | 1 | Operation enable (layer start trigger) |

| `reg2dp\_conv\_mode` | I | 1 | Convolution mode: 0=direct conv, 1=Winograd |

| `reg2dp\_proc\_precision` | I | 2 | Precision: 0=INT8, 1=INT16, 2=FP16 |

| `reg2dp\_data\_reuse` | I | 1 | Data reuse enable |

| `reg2dp\_skip\_data\_rls` | I | 1 | Skip data release from CBUF |

| `reg2dp\_weight\_reuse` | I | 1 | Weight reuse enable |

| `reg2dp\_skip\_weight\_rls` | I | 1 | Skip weight release from CBUF |

| `reg2dp\_batches` | I | 5 | Number of batches minus one |

| `reg2dp\_datain\_format` | I | 1 | Input format: 0=feature, 1=pixel/image |

| `reg2dp\_datain\_height\_ext` | I | 13 | Input data height extended (height-1) |

| `reg2dp\_y\_extension` | I | 2 | Y-direction extension for multi-batch (0,1,2 valid) |

| `reg2dp\_weight\_width\_ext` | I | 5 | Weight width extended (width-1) |

| `reg2dp\_weight\_height\_ext` | I | 5 | Weight height extended (height-1) |

| `reg2dp\_weight\_channel\_ext` | I | 13 | Weight channel extended (channel-1) |

| `reg2dp\_weight\_kernel` | I | 13 | Number of weight kernels minus one |

| `reg2dp\_dataout\_width` | I | 13 | Output feature map width minus one |

| `reg2dp\_dataout\_height` | I | 13 | Output feature map height minus one |

| `reg2dp\_data\_bank` | I | 4 | CBUF data bank assignment |

| `reg2dp\_weight\_bank` | I | 4 | CBUF weight bank assignment |

| `reg2dp\_atomics` | I | 21 | Number of atomic operations |

| `reg2dp\_rls\_slices` | I | 12 | Number of slices to release per layer |



\### 2.3 CDMA Upstream Interface



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `cdma2sc\_dat\_updt` | I | 1 | Data CBUF update valid strobe |

| `cdma2sc\_dat\_entries` | I | 12 | Number of data entries updated |

| `cdma2sc\_dat\_slices` | I | 12 | Number of data slices updated |

| `cdma2sc\_wt\_updt` | I | 1 | Weight CBUF update valid strobe |

| `cdma2sc\_wt\_entries` | I | 12 | Number of weight entries updated |

| `cdma2sc\_wt\_kernels` | I | 14 | Number of weight kernels updated |

| `cdma2sc\_wmb\_entries` | I | 9 | Number of WMB entries updated |

| `cdma2sc\_dat\_pending\_ack` | I | 1 | Acknowledgement for data pending request |

| `cdma2sc\_wt\_pending\_ack` | I | 1 | Acknowledgement for weight pending request |



\### 2.4 Accumulator Credit Interface



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `accu2sc\_credit\_vld` | I | 1 | Credit return valid from accumulator |

| `accu2sc\_credit\_size` | I | 3 | Size of credit being returned |



\### 2.5 Downstream Data Loader Interface



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `sg2dl\_pvld` | O | 1 | Data loader packet valid |

| `sg2dl\_pd` | O | 31 | Data loader packet payload |

| `sg2dl\_reuse\_rls` | O | 1 | Data reuse release signal to data loader |



\### 2.6 Downstream Weight Loader Interface



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `sg2wl\_pvld` | O | 1 | Weight loader packet valid |

| `sg2wl\_pd` | O | 18 | Weight loader packet payload |

| `sg2wl\_reuse\_rls` | O | 1 | Weight reuse release signal to weight loader |



\### 2.7 Status and Pending Outputs



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `sc\_state` | O | 2 | Current FSM state exposed to register interface |

| `dp2reg\_done` | O | 1 | Layer completion done pulse to register interface |

| `sc2cdma\_dat\_pending\_req` | O | 1 | Data pending request to CDMA |

| `sc2cdma\_wt\_pending\_req` | O | 1 | Weight pending request to CDMA |



\### 2.8 Miscellaneous



| Port | Dir | Width | Description |

|------|-----|-------|-------------|

| `pwrbus\_ram\_pd` | I | 32 | Power bus for internal RAM power-down |



---



\## 3. Operational Modes



The module supports three convolution modes, encoded in `cur\_mode\[2:0]`:



| Mode | Encoding | Description |

|------|----------|-------------|

| DC (Direct Convolution) | `3'b001` | Standard direct convolution, feature input |

| Winograd | `3'b010` | Winograd-transformed convolution |

| Image (Pixel) | `3'b100` | Direct convolution with pixel/image input |



Mode is derived combinatorially from register inputs and is sampled at layer start.



---



\## 4. Top-Level FSM



\### 4.1 States



```

SG\_STATE\_IDLE = 2'b00

SG\_STATE\_PEND = 2'b01

SG\_STATE\_BUSY = 2'b10

SG\_STATE\_DONE = 2'b11

```



\### 4.2 Transition Diagram



```

&nbsp;        reg2dp\_op\_en \& need\_pending

IDLE ─────────────────────────────────► PEND

&nbsp; │                                       │

&nbsp; │ reg2dp\_op\_en \& ~need\_pending          │ pending\_done

&nbsp; │                                       ▼

&nbsp; └──────────────────────────────────── BUSY

&nbsp;                                         │

&nbsp;             layer\_done \& fifo\_is\_clear  │

&nbsp;                   \& ~pkg\_vld            │

&nbsp;                                         ▼

IDLE ◄──────────────────────────────── DONE

&nbsp;         dp2reg\_done

```



\### 4.3 State Descriptions



| State | Description |

|-------|-------------|

| \*\*IDLE\*\* | Module is idle, waiting for `reg2dp\_op\_en`. Bank change check occurs here. |

| \*\*PEND\*\* | Waiting for CBUF bank change handshake. Data and weight pending requests issued to CDMA. Module waits until both pending clears are acknowledged. |

| \*\*BUSY\*\* | Active sequence generation. Iterates over all convolution loop dimensions, generating data and weight load commands. |

| \*\*DONE\*\* | Layer convolution complete. Waits for downstream FIFOs to drain and for a flush delay before asserting `dp2reg\_done`. Returns to IDLE. |



\### 4.4 need\_pending Condition



`need\_pending` is asserted when either the data bank or weight bank assignment has changed from the previous layer (`last\_data\_bank != reg2dp\_data\_bank` or `last\_weight\_bank != reg2dp\_weight\_bank`). This forces a PEND state to allow CDMA to flush the CBUF before the new layer begins.



---



\## 5. Loop Sequencing Architecture



\### 5.1 Nested Loop Order



The sequence generator implements a 7-level nested loop for direct convolution. The outer-to-inner ordering is:



```

Layer

&nbsp; └─ Group (kernel group)

&nbsp;      └─ Output-Height (image mode only)

&nbsp;           └─ Stripe (output width segments)

&nbsp;                └─ Channel (input channel blocks)

&nbsp;                     └─ R (weight height)

&nbsp;                          └─ S (weight width)  ← innermost, advances every cycle

```



Each level has a corresponding up-counter and a `is\_last\_\*` signal. An operation enable signal (`op\_\*\_en`) is generated for each level based on whether all inner levels have completed.



\### 5.2 Loop Counter Descriptions



| Counter | Width | Description |

|---------|-------|-------------|

| `group\_up\_cnt` | 10 | Kernel group index; wraps at `weight\_groups` |

| `dataout\_h\_up\_cnt` | 13 | Output height index (image mode); wraps at `reg2dp\_dataout\_height` |

| `stripe\_up\_cnt` | 22 | Output stripe position; increments by `upper\_limit` |

| `channel\_up\_cnt` | 14 | Input channel offset; increments by `c\_fetch\_size` (4 for Winograd, 64 for others) |

| `weight\_r\_up\_cnt` | 5 | Weight row (R) index; increments by `weight\_r\_add` |

| `weight\_s\_up\_cnt` | 5 | Weight column (S) index; increments by 1 |



All counters reset to 0 at `layer\_st` and wrap to 0 at their respective `is\_last\_\*` conditions.



\### 5.3 Advance Condition (pkg\_adv)



The sequence advances one step (`pkg\_adv`) when all of the following are true:



\- FSM is in BUSY state (`is\_running`)

\- CBUF has sufficient data and weight entries (`cbuf\_ready`)

\- Layer is not yet done (`~layer\_done`)

\- Either no pending packet (`~pkg\_vld`) or the downstream FIFOs are both ready (`fifo\_push\_ready`)



---



\## 6. Package Generation



\### 6.1 Data Loader Packet (`sg2dl\_pd`, 31 bits)



Each `pkg\_adv` event captures loop state into registered packet fields, which are then pushed into the data FIFO. Fields are packed as:



| Bits | Field | Width | Description |

|------|-------|-------|-------------|

| \[4:0] | `w\_offset` | 5 | Weight S (column) offset = `weight\_s\_up\_cnt` |

| \[9:5] | `h\_offset` | 5 | Weight R (row) offset = `weight\_r\_up\_cnt` |

| \[16:10] | `channel\_size` | 7 | Number of input channels in this block = `cur\_channel` |

| \[23:17] | `stripe\_length` | 7 | Number of output atoms in this stripe = `cur\_stripe` |

| \[25:24] | `cur\_sub\_h` | 2 | Current sub-height for y-extension = `cur\_r\[1:0]` |

| \[26] | `block\_end` | 1 | Last S and R iteration (complete weight block) |

| \[27] | `channel\_end` | 1 | Last channel iteration |

| \[28] | `group\_end` | 1 | Last group, stripe, height iteration |

| \[29] | `layer\_end` | 1 | Last of all dimensions |

| \[30] | `dat\_release` | 1 | Release data CBUF slices (`layer\_end \& ~skip\_data\_rls`) |



A 2-bit `pkg\_idx` tag is prepended to form the 33-bit FIFO write data.



\### 6.2 Weight Loader Packet (`sg2wl\_pd`, 18 bits)



| Bits | Field | Width | Description |

|------|-------|-------|-------------|

| \[6:0] | `weight\_size` | 7 | Weight channels per block (64 for Winograd, else `cur\_channel`) |

| \[12:7] | `kernel\_size` | 6 | Number of kernels in current group = `cur\_kernel` |

| \[14:13] | `cur\_sub\_h` | 2 | Sub-height = `cur\_r\[1:0]` |

| \[15] | `channel\_end` | 1 | Same as data packet `channel\_end` |

| \[16] | `group\_end` | 1 | Same as data packet `group\_end` |

| \[17] | `wt\_release` | 1 | Release weight CBUF (`group\_end \& ~skip\_weight\_rls`) |



Same `pkg\_idx` tag is prepended to form 20-bit FIFO write data.



---



\## 7. Internal FIFOs



\### 7.1 Data FIFO (`NV\_NVDLA\_CSC\_SG\_dat\_fifo`)



| Parameter | Value |

|-----------|-------|

| Data width | 33 bits (`pkg\_idx\[1:0]` + `dat\_pkg\_pd\[30:0]`) |

| Interface | ready/valid with empty flag |

| Clock | `nvdla\_core\_clk` |

| Reset | `nvdla\_core\_rstn` |



Both `dat\_push\_req` and `wt\_push\_req` are gated by the opposing FIFO's `push\_ready` to ensure atomicity — both packets push together or neither does.



\### 7.2 Weight FIFO (`NV\_NVDLA\_CSC\_SG\_wt\_fifo`)



| Parameter | Value |

|-----------|-------|

| Data width | 20 bits (`pkg\_idx\[1:0]` + `wt\_pkg\_pd\[17:0]`) |

| Interface | ready/valid with empty flag |

| Clock | `nvdla\_core\_clk` |

| Reset | `nvdla\_core\_rstn` |



`fifo\_is\_clear` requires both FIFOs to be empty and both pop requests to be de-asserted.



---



\## 8. Issue Control (Pop Scheduling)



\### 8.1 Pop Arbitration



Data and weight packets are popped from their respective FIFOs under different conditions:



\*\*Weight pop (`wt\_pop\_ready`):\*\* Asserted when:

\- A weight packet is available (`wt\_pop\_req`), AND

\- Either the pop counter has expired AND credit is available, OR

\- The `pkg\_idx` of the data and weight packets match (same iteration, weight can be issued alongside data)



\*\*Data pop (`dat\_pop\_ready`):\*\* Asserted when:

\- A data packet is available (`dat\_pop\_req`), AND

\- Pop counter has reached zero, AND

\- Credit is available, AND

\- The data packet is from a different `pkg\_idx` than the pending weight packet, OR no weight packet is pending



\### 8.2 Pop Counter



The pop counter (`pop\_cnt`) controls inter-issue spacing. When either a data or weight pop occurs, it is loaded with `max\_cycles` and counts down. This enforces a minimum spacing between successive data issues equal to the larger of the data stripe processing time and the weight loading time.



`max\_cycles` is derived as:

```

max\_cycles = max(dat\_max\_cycles, wt\_max\_cycles) - 1

```



Where:

\- `dat\_max\_cycles` = `max(dat\_stripe\_length, 10)` when data pop is active

\- `wt\_max\_cycles` = kernel-size-derived weight cycles when weight pop is active



---



\## 9. CBUF Availability Tracking



\### 9.1 Data Slice Availability (`slices\_avl`, 12 bits)



Tracks the number of data slices available in CBUF. Runs on `nvdla\_core\_ng\_clk`.



\*\*Increment:\*\* On `cdma2sc\_dat\_updt`, add `cdma2sc\_dat\_slices`



\*\*Decrement:\*\* On `dat\_release` (layer end), subtract `rls\_slices`; on `dat\_reuse\_release`, subtract `last\_slices`



\*\*Reset to 0:\*\* When `dat\_pending\_req` is asserted (bank change flush)



`dat\_cbuf\_ready` is true when `slices\_avl >= data\_in\_height\[11:0]`.



\### 9.2 Kernel Availability (`kernels\_avl`, 15 bits)



Tracks the number of weight kernels available in CBUF. Runs on `nvdla\_core\_ng\_clk`.



\*\*Increment:\*\* On `cdma2sc\_wt\_updt`, add `cdma2sc\_wt\_kernels`



\*\*Decrement:\*\* On `wt\_release` (group end), subtract `cur\_kernel`; on `wt\_reuse\_release`, subtract `last\_kernels`



\*\*Reset to 0:\*\* When `wt\_pending\_req` is asserted



`wt\_cbuf\_ready` checks `required\_kernels\_inc <= kernels\_avl`, where `required\_kernels\_inc` accumulates kernel counts across groups when `skip\_weight\_rls` is set.



\### 9.3 Combined CBUF Ready



`cbuf\_ready = dat\_cbuf\_ready \& wt\_cbuf\_ready`



This gates `pkg\_adv` to stall the loop until sufficient data and weights exist in CBUF.



---



\## 10. Credit Control



The credit controller runs on `nvdla\_core\_ng\_clk` and tracks accumulator processing credits.



\### 10.1 Credit Counter (`credit\_cnt`, 9 bits)



\- \*\*Initialized\*\* to `9'h100` (256) on reset

\- \*\*Incremented\*\* by `credit\_size` on each `credit\_vld` pulse from accumulator

\- \*\*Decremented\*\* by `dat\_impact\_cnt` on each `dat\_pop\_ready \& sg2dat\_channel\_end`

\- \*\*Maximum\*\* value: 256 (`9'h100`)



\### 10.2 Credit Request Size Calculation



```

dat\_impact\_cnt depends on mode:

&nbsp; Winograd + INT8:   stripe\_size × 8

&nbsp; Winograd + non-INT8: stripe\_size × 4

&nbsp; non-Winograd + INT8: stripe\_size × 2

&nbsp; non-Winograd + non-INT8: stripe\_size × 1



credit\_req\_size = dat\_impact\_cnt + batch\_delta

```



`batch\_delta` is 0 for non-DC or single-batch; for multi-batch DC it is `2 × data\_batch` (INT8) or `data\_batch` (non-INT8).



\### 10.3 Credit Ready



`credit\_ready = ~sg2dat\_channel\_end | (credit\_cnt >= credit\_req\_size)`



Credit is only checked at channel boundaries (when `channel\_end` is set in the outgoing data packet).



---



\## 11. Reuse and Release Logic



\### 11.1 Data Reuse Release (`dat\_reuse\_release`)



Triggered at layer start (`is\_idle \& reg2dp\_op\_en`) when:

\- Data reuse is disabled (`~reg2dp\_data\_reuse`), OR

\- Operation mode has changed from last layer (`is\_mode\_change`), AND

\- Previous layer left residual slices in CBUF (`|last\_slices`)



Causes `last\_slices` to be subtracted from `slices\_avl` and `sg2dl\_reuse\_rls` to pulse.



\### 11.2 Weight Reuse Release (`wt\_reuse\_release`)



Triggered at layer start when:

\- Weight reuse is disabled (`~reg2dp\_weight\_reuse`), AND

\- Last layer used skip-weight-release (`last\_skip\_weight\_rls`)



Causes `last\_kernels` to be subtracted from `kernels\_avl` and `sg2wl\_reuse\_rls` to pulse.



\### 11.3 Per-Layer Release



\- `dat\_release`: pulsed at `pkg\_adv \& pkg\_layer\_end \& ~skip\_data\_rls`; decrements `slices\_avl` by `rls\_slices`

\- `wt\_release`: pulsed at `pkg\_adv \& ~skip\_weight\_rls \& pkg\_group\_end`; decrements `kernels\_avl` by `cur\_kernel`



---



\## 12. Layer Completion and Done Sequence



\### 12.1 Layer Done



`layer\_done` is set when `is\_last\_group` is observed during `op\_layer\_en` and cleared at `layer\_st`.



The FSM transitions BUSY → DONE when `layer\_done \& fifo\_is\_clear \& ~pkg\_vld`.



\### 12.2 Flush Counter (`sg\_dn\_cnt`)



On entering DONE state (first cycle of `is\_nxt\_done`), `sg\_dn\_cnt` is loaded with:

```

flush\_cycles = dat\_stripe\_size + 0x30

```



`sg\_dn\_cnt` decrements by 1 each cycle while in DONE state.



\### 12.3 dp2reg\_done



`dp2reg\_done` is asserted for one cycle when:

```

is\_done \& (sg\_dn\_cnt == 6'h1)

```



This triggers saving of `last\_\*` state registers and the FSM returns to IDLE on the following cycle.



---



\## 13. Computed Parameters



\### 13.1 Stripe Sizing



| Variable | Computation |

|----------|-------------|

| `lower\_limit` | Minimum stripe step size based on mode and batch count |

| `upper\_limit` | Maximum stripe step size (2× lower\_limit in most modes) |

| `cur\_stripe` | `data\_out\_atomic - stripe\_up\_cnt` (last stripe) or `lower\_limit` (normal) |

| `dat\_stripe\_size` | `cur\_stripe × data\_batch` (normal) or `cur\_stripe` (image mode) |

| `dat\_stripe\_length` | Accounts for y-extension alignment in image mode |



\### 13.2 Kernel Group Sizing



| Variable | Computation |

|----------|-------------|

| `weight\_groups` | `ceil(weight\_kernel / 16)` for INT16/FP16; `ceil(weight\_kernel / 32)` for INT8 |

| `cur\_kernel` | 16 or 32 for non-last groups; remainder for last group |



\### 13.3 Channel Block Sizing



| Variable | Computation |

|----------|-------------|

| `c\_fetch\_size` | 4 for Winograd, 64 for DC/Image |

| `cur\_channel` | `c\_fetch\_size` unless last channel; then `weight\_channel\_ext\[5:0] + 1` |



---



\## 14. Constraint and Configuration Assertions



The RTL includes numerous `nv\_assert\_never` checks that define valid configuration ranges. These encode the following rules:



| Rule | Constraint |

|------|------------|

| Input height | `data\_in\_height <= 3840` |

| Atomic count | `data\_out\_atomic <= 3840 × 128` |

| Winograd inputs | Weight width and height must both be 3 (i.e., 4×4 kernel) |

| Winograd mode | Cannot be combined with pixel/image input |

| Winograd output | `dataout\_width\[1:0]` and `dataout\_height\[1:0]` must be `2'b11` |

| Image input | `weight\_channel\_ext` must be ≤ 127 |

| y\_extension | Must be 0, 1, or 2 (not 3) |

| y\_extension | Cannot be used with batch count > 0 |

| y\_extension | `weight\_channel × weight\_r\_add <= 64` |

| At least one mode | `is\_conv | is\_winograd` must be true |



---



\## 15. Pending (Bank Change) Handshake Protocol



When a bank change is detected at layer start:



1\. FSM enters PEND state

2\. `dat\_pending\_req` is asserted if `dat\_bank\_change` is true

3\. `wt\_pending\_req` is always asserted in PEND state

4\. CDMA acknowledges via `cdma2sc\_dat\_pending\_ack` / `cdma2sc\_wt\_pending\_ack`

5\. `dat\_pending\_clr` and `wt\_pending\_clr` are set on acknowledgement

6\. `pending\_done` triggers when `dat\_pending\_clr ~^ dat\_pending\_req` (XNOR: both match) AND `wt\_pending\_clr ~^ wt\_pending\_req`

7\. FSM transitions to BUSY; `slices\_avl` and `kernels\_avl` are reset to 0



---



\## 16. Clock Domain Partitioning



| Logic Block | Clock Domain | Rationale |

|-------------|-------------|-----------|

| FSM, loop counters, FIFO push logic | `nvdla\_core\_clk` | Can be clock-gated |

| Credit counter, CBUF availability tracking, reuse release | `nvdla\_core\_ng\_clk` | Must remain active during power-gating; tracks shared resource state |

| Credit input flop (`credit\_vld`, `credit\_size`) | `nvdla\_core\_ng\_clk` | Cross-partition boundary, requires non-gated sampling |



---



\## 17. Timing-Critical Paths (Optimization Guidance for Agent)



The following dataflow paths span multiple levels of logic and are candidates for pipeline register insertion. The agent must identify appropriate cut points independently based on timing analysis:



\### 17.1 CBUF Ready to pkg\_adv



```

slices\_avl / kernels\_avl

&nbsp; → dat\_cbuf\_ready / wt\_cbuf\_ready

&nbsp;   → cbuf\_ready

&nbsp;     → pkg\_adv

&nbsp;       → loop counter enables (op\_\*\_en)

&nbsp;         → updated loop state (cur\_stripe, cur\_channel, cur\_r, cur\_kernel)

&nbsp;           → pkg\_\*\_end\_w / pkg\_\*\_size\_w

&nbsp;             → FIFO push data

```



This is the main sequence generation critical path. Multiple pipeline stages may be inserted anywhere along this chain.



\### 17.2 Credit Path



```

accu2sc\_credit\_vld / accu2sc\_credit\_size (ng\_clk input)

&nbsp; → credit\_cnt (ng\_clk)

&nbsp;   → credit\_ready (combinatorial)

&nbsp;     → dat\_pop\_ready / wt\_pop\_ready (core\_clk domain crossing)

&nbsp;       → sg2dl\_pvld / sg2wl\_pvld (registered output)

```



This path crosses a clock domain boundary and involves a comparison against a computed threshold.



\### 17.3 Pop Scheduling Path



```

dat\_stripe\_size / wt\_cycles / pop\_cnt

&nbsp; → max\_cycles (comparison + subtraction)

&nbsp;   → pop\_cnt\_w

&nbsp;     → pop\_cnt (registered)

&nbsp;       → dat\_pop\_ready / wt\_pop\_ready

```



\### 17.4 Stripe Count Path



```

stripe\_up\_cnt + upper\_limit

&nbsp; → stripe\_up\_cnt\_inc

&nbsp;   → is\_last\_stripe

&nbsp;     → cur\_stripe\_inc (subtraction: data\_out\_atomic - stripe\_up\_cnt)

&nbsp;       → cur\_stripe

&nbsp;         → stripe\_length\_w → dat\_pkg\_stripe\_length

&nbsp;         → dat\_stripe\_size\_w → dat\_stripe\_size → dat\_max\_cycles → max\_cycles

```



\### 17.5 Weight Block Determination



```

weight\_r\_up\_cnt + weight\_r\_add

&nbsp; → weight\_r\_up\_cnt\_inc

&nbsp;   → is\_last\_r

&nbsp;     → cur\_r

&nbsp;       → is\_last\_block

&nbsp;         → op\_channel\_en, op\_stripe\_en, op\_group\_en, op\_layer\_en

&nbsp;           → pkg\_\*\_end\_w

```



\### 17.6 Kernel Availability Path



```

required\_kernels + cur\_kernel

&nbsp; → required\_kernels\_inc

&nbsp;   → wt\_cbuf\_ready (comparison vs kernels\_avl)

&nbsp;     → cbuf\_ready → pkg\_adv

```



---



\## 18. Functional Coverage Points



The RTL defines the following functional coverage scenarios that must be preserved across any pipeline modification:



| ID | Coverage Point |

|----|---------------|

| 0 | `pkg\_vld` asserted but `dat\_push\_ready` de-asserted (data FIFO backpressure) |

| 1 | Data CBUF update and data release in same cycle |

| 2 | Weight CBUF update and weight release in same cycle |

| 3 | Data pop request pending but credit not ready |

| 4 | Weight pop request pending but credit not ready |

| 5 | Weight packet forwarded ahead of data (pop\_cnt > 0) |

| 6 | Layer-to-layer mode and precision transitions (all combinations of DC/Winograd/Image × INT8/INT16/FP16) |



---



\## 19. Behavioral Summary



On each active clock edge while in BUSY state, the module:



1\. Checks CBUF readiness (`cbuf\_ready`)

2\. If ready and the downstream FIFO can accept, asserts `pkg\_adv`

3\. Advances the innermost loop counter (S dimension) unconditionally

4\. Rolls over outer counters (R, channel, stripe, height, group, layer) as their inner loops complete

5\. Captures current loop state into registered packet fields

6\. Writes both data and weight packets simultaneously into their respective FIFOs

7\. The pop scheduler reads from both FIFOs and issues them to `sg2dl` and `sg2wl` with appropriate timing separation controlled by the pop counter and credit system.

