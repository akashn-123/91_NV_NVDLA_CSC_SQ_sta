#!/bin/bash
# Smart ECO workflow for NVDLA CSC Sequence Generator

export DOCKER_HOST=tcp://host.docker.internal:2375

# Configuration
SYNTHESIS_TIMEOUT=300  
STA_TIMEOUT=120       

# ==============================================================================
# BLOCK-SPECIFIC CONFIGURATION (UPDATED)
# ==============================================================================
STATE_FILE="./sources/.active_task_id"
CONTAINER_FILE="./sources/.container_name"

# Updated to your NVDLA Top-level RTL
RTL_FILE="./sources/NV_NVDLA_CSC_sg.v"
NETLIST_FILE="./sources/netlist.v"

# Additional sub-modules required for full sync
SUBMODULE_1="./sources/NV_NVDLA_CSC_SG_wt_fifo.v"
SUBMODULE_2="./sources/NV_NVDLA_CSC_SG_dat_fifo.v"

# ==============================================================================
# CONTAINER MANAGEMENT (Reuse same container for same workspace)
# ==============================================================================

if [ -f "$CONTAINER_FILE" ]; then
    CONTAINER_NAME=$(cat "$CONTAINER_FILE")
    echo ">>> RESUMING: Using existing container: $CONTAINER_NAME"
    
    if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then
        echo ">>> WARNING: Container $CONTAINER_NAME not found. Creating new one."
        CONTAINER_NAME="nvdla_csc_$$"
        echo "$CONTAINER_NAME" > "$CONTAINER_FILE"
        docker run -d --name "$CONTAINER_NAME" efabless/openlane:latest tail -f /dev/null
        sleep 2
    else
        if [ ! "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
            docker start "$CONTAINER_NAME"
            sleep 1
        fi
    fi
else
    CONTAINER_NAME="nvdla_csc_$$"
    echo "$CONTAINER_NAME" > "$CONTAINER_FILE"
    echo ">>> FIRST RUN: Creating new container: $CONTAINER_NAME"
    docker run -d --name "$CONTAINER_NAME" efabless/openlane:latest tail -f /dev/null
    sleep 2
fi

# ==============================================================================
# DIRECTORY MANAGEMENT
# ==============================================================================

if [ -f "$STATE_FILE" ]; then
    TASK_ID=$(cat "$STATE_FILE")
    UNIQUE_DIR="/openlane/$TASK_ID"
else
    TIMESTAMP_NS=$(date +%s%N 2>/dev/null || echo $(date +%s))
    TASK_ID="nvdla_csc_${TIMESTAMP_NS}"
    UNIQUE_DIR="/openlane/$TASK_ID"
    echo "$TASK_ID" > "$STATE_FILE"
fi

# ==============================================================================
# SMART SYNTHESIS DECISION
# ==============================================================================

SHOULD_SYNTHESIZE=false

if [ ! -f "$NETLIST_FILE" ]; then
    echo ">>> DECISION: Netlist not found → SYNTHESIZE"
    SHOULD_SYNTHESIZE=true
elif [ "$RTL_FILE" -nt "$NETLIST_FILE" ]; then
    echo ">>> DECISION: RTL modified → RE-SYNTHESIZE"
    SHOULD_SYNTHESIZE=true
else
    echo ">>> DECISION: ECO mode active (using existing netlist)"
    SHOULD_SYNTHESIZE=false
fi

# ==============================================================================
# SYNC FILES TO CONTAINER
# ==============================================================================

echo ">>> Syncing NVDLA sources to container..."
docker exec "$CONTAINER_NAME" mkdir -p "$UNIQUE_DIR" 2>/dev/null
docker cp "./sources/." "$CONTAINER_NAME":"$UNIQUE_DIR/"

# ==============================================================================
# SYNTHESIS WITH TIMEOUT PROTECTION
# ==============================================================================

if [ "$SHOULD_SYNTHESIZE" = true ]; then
    echo ">>> RUNNING NVDLA SYNTHESIS (Timeout: ${SYNTHESIS_TIMEOUT}s)..."
    
    # We use your existing script.tcl (Yosys)
    timeout $SYNTHESIS_TIMEOUT docker exec "$CONTAINER_NAME" bash -c "cd $UNIQUE_DIR && yosys -s script.tcl"
    SYNTH_EXIT=$?
    
    if [ $SYNTH_EXIT -eq 124 ]; then
        echo "⚠️  TIMEOUT: Synthesis took too long. Check logic depth in $RTL_FILE."
        exit 1
    fi
    
    docker cp "$CONTAINER_NAME":"$UNIQUE_DIR/netlist.v" "./sources/netlist.v"
    touch "./sources/netlist.v"
fi

# ==============================================================================
# TIMING ANALYSIS (STA)
# ==============================================================================

echo ">>> RUNNING STA (Nangate 45nm Library)..."
timeout $STA_TIMEOUT docker exec "$CONTAINER_NAME" bash -c "cd $UNIQUE_DIR && sta -no_init run_sta.tcl"

# ==============================================================================
# SHOW REPORTS & SUMMARY
# ==============================================================================

echo "============================================================"
echo "NVDLA CSC SG TIMING SUMMARY:"
docker exec "$CONTAINER_NAME" cat "$UNIQUE_DIR/timing_report.rpt" 2>/dev/null | grep -E "slack|VIOLATED|arrival|required"
echo "============================================================"

# Copy results back
docker cp "$CONTAINER_NAME":"$UNIQUE_DIR/netlist.v" "./sources/netlist.v" 2>/dev/null
docker cp "$CONTAINER_NAME":"$UNIQUE_DIR/timing_report.rpt" "./timing_report.rpt" 2>/dev/null

echo "Next steps:"
if [ "$SHOULD_SYNTHESIZE" = true ]; then
    echo "  - Fresh netlist created. Check slack."
else
    echo "  - ECO changes preserved. Review timing_report.rpt."
fi
echo "  - Apply fixes: python sources/eco_fix.py --instance _XXXX_ --new_cell BUF_X8"
echo "============================================================"