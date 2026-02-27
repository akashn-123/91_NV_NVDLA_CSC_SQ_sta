#!/usr/bin/env python3
import re
import argparse
import os

def swap_cell(instance_name, new_cell_type, netlist_path):
    """
    Enhanced ECO tool for Nangate 45nm with Docker sync support
    """
    if not os.path.exists(netlist_path):
        print(f"ERROR: Netlist not found at {netlist_path}")
        return False

    with open(netlist_path, 'r') as f:
        content = f.read()

    # Nangate pattern: CellName_XDrive InstanceName (
    # Example: NOR3_X1 _3835_ (
    pattern = rf"(\w+)\s+{re.escape(instance_name)}\s*\("
    
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        print(f"ERROR: Instance '{instance_name}' not found in {netlist_path}!")
        return False
    
    old_cell = matches[0].group(1)
    
    # Replace old cell type with the new one
    new_content = re.sub(pattern, rf"{new_cell_type} {instance_name} (", content)

    with open(netlist_path, 'w') as f:
        f.write(new_content)
    
    print(f"SUCCESS: Swapped {instance_name}")
    print(f"          From: {old_cell}")
    print(f"          To:   {new_cell_type}")
    
    sync_to_docker_if_needed(netlist_path)
    return True

def sync_to_docker_if_needed(netlist_path):
    container_file = "./sources/.container_name"
    state_file = "./sources/.active_task_id"
    
    if os.path.exists(container_file) and os.path.exists(state_file):
        with open(container_file, 'r') as f:
            container_name = f.read().strip()
        with open(state_file, 'r') as f:
            task_id = f.read().strip()
        
        docker_path = f"/openlane/{task_id}/netlist.v"
        
        print(f"Syncing modified netlist to Docker container: {container_name}...")
        
        import subprocess
        result = subprocess.run(
            ["docker", "cp", netlist_path, f"{container_name}:{docker_path}"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"  ✓ Netlist synced successfully")
        else:
            print(f"  ⚠ Warning: Could not sync to Docker")

def list_weak_cells(netlist_path, drive_strength="1"):
    """
    Helper function to find Nangate cells with specific drive (e.g., X1)
    """
    if not os.path.exists(netlist_path):
        print(f"ERROR: Netlist not found")
        return
    
    with open(netlist_path, 'r') as f:
        content = f.read()
    
    # Matches Nangate pattern: ANYCELL_X1 _1234_ (
    pattern = rf"(\w+_X{re.escape(drive_strength)})\s+(_\d+_)\s*\("
    matches = re.findall(pattern, content)
    
    if matches:
        print(f"\nFound {len(matches)} cells with drive strength 'X{drive_strength}':")
        for cell_type, instance in matches[:20]:
            print(f"{instance:<15} {cell_type}")
    else:
        print(f"No cells found with drive strength 'X{drive_strength}'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nangate 45nm ECO Tool")
    
    parser.add_argument("--instance", help="Instance name (e.g., _3835_)")
    parser.add_argument("--new_cell", help="New cell type (e.g., BUF_X8)")
    parser.add_argument("--list-weak", action="store_true", help="List X1 cells")
    parser.add_argument("--drive-strength", default="1", help="Default drive to search (1 for X1)")
    parser.add_argument("--file", default="./sources/netlist.v", help="Path to netlist")
    
    args = parser.parse_args()
    
    if args.list_weak:
        list_weak_cells(args.file, args.drive_strength)
    elif args.instance and args.new_cell:
        swap_cell(args.instance, args.new_cell, args.file)
    else:
        parser.print_help()