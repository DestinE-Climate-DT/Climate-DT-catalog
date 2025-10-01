#!/bin/bash
# filepath: /users/cadaumar/EN4_management.sh

# Script to download, process, and merge EN4 oceanographic data
# With post-processing to match existing data grid

#set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

# Functions for safe file operations
safe_move() {
    local src="$1"
    local dst="$2"
    
    if [ ! -f "$src" ]; then
        error "Source file $src not found."
        return 1
    fi
    
    # Try with mv first, if it fails use rsync
    if mv "$src" "$dst" 2>/dev/null; then
        success "File moved via mv: $dst"
        return 0
    else
        warning "mv failed, trying with rsync..."
        if rsync -av --progress "$src" "$dst" && rm "$src"; then
            success "File moved with rsync: $dst"
            return 0
        else
            error "Cannot move file $src"
            return 1
        fi
    fi
}

# Function for variable processing
process_variable() {
    local monthly_file="$1"
    local var_config="$2"
    local year="$3"
    local month_str="$4"
    
    # Parse variable configuration: "original_name:final_name:uncertainty_name:long_name:standard_name"
    IFS=':' read -r orig_name final_name uncert_name long_name standard_name <<< "$var_config"
    
    local temp_file="temp_${final_name}_${year}${month_str}.nc"
    local combined_file="${final_name}_${year}${month_str}.nc"
    
    info "Processing $final_name for $monthly_file" >&2
    
    # 1. Extract variable + uncertainty
    if ! cdo selvar,${orig_name},${uncert_name} "$monthly_file" "$temp_file" 2>/dev/null; then
        error "$orig_name or $uncert_name not found in $monthly_file"  >&2
        error "Both main variable and uncertainty are required!" >&2
        return 1
    fi
    
    success "Extracted $orig_name + $uncert_name" >&2
    
    # 2. Remove problematic attributes
    ncatted -O -a valid_max,$orig_name,d,, "$temp_file" 2>/dev/null || true
    ncatted -O -a valid_min,$orig_name,d,, "$temp_file" 2>/dev/null || true
    ncatted -O -a valid_max,$uncert_name,d,, "$temp_file" 2>/dev/null || true
    ncatted -O -a valid_min,$uncert_name,d,, "$temp_file" 2>/dev/null || true
    
    # 3. Rename variables
    ncrename -v $orig_name,$final_name "$temp_file" 2>/dev/null || true
    ncrename -v ${uncert_name},${final_name}_uncertainty "$temp_file" 2>/dev/null || true
    
    # 4. Change attributes
    ncatted -O -a long_name,$final_name,m,c,"$long_name" "$temp_file" 2>/dev/null || true
    ncatted -O -a standard_name,$final_name,m,c,"$standard_name" "$temp_file" 2>/dev/null || true
    
    # 5. Rename depth dimension to lev
    ncrename -d depth,lev -v depth,lev "$temp_file" 2>/dev/null || true
    ncatted -O -a standard_name,lev,c,c,"depth" "$temp_file" 2>/dev/null || true
    
    # 6. Convert time to float
    local final_temp="temp_final_${final_name}_${year}${month_str}.nc"
    ncap2 -O -s "time=float(time)" "$temp_file" "$final_temp" 2>/dev/null || cp "$temp_file" "$final_temp"
    
    # 7. Regridding (if grid file is available)
    if [ -n "$GRID_FILE" ] && [ -f "$GRID_FILE" ]; then
        info "Applying regridding to $final_name..." >&2
        cdo -s remapbil,"$GRID_FILE" "$final_temp" "$combined_file"
        rm "$final_temp"
        success "$final_name regridding completed" >&2
    else
        mv "$final_temp" "$combined_file"
        warning "Regridding skipped (grid not available)" >&2
    fi
    
    # Cleanup temporary file
    rm -f "$temp_file"
    
    success "Processed $final_name: $combined_file" >&2
    echo "$combined_file"  # Return the filename
    return 0
}

# Variables configuration
BASE_URL="https://www.metoffice.gov.uk/hadobs/en4/data/en4-2-1"
WORK_DIR="/users/cadaumar/en4_download" #TO BE CHANGED AS NEEDED
FINAL_DIR="/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/EN4"
START_YEAR=2025
START_MONTH=1
END_YEAR=2025
END_MONTH=6

# Variable configurations: "original_name:final_name:uncertainty_name:long_name:standard_name"
declare -A VAR_CONFIGS
VAR_CONFIGS[so]="salinity:so:salinity_uncertainty:Sea water salinity:sea_water_salinity"
VAR_CONFIGS[thetao]="temperature:thetao:temperature_uncertainty:Potential temperature:sea_water_potential_temperature"

# Arrays for processed files
declare -a processed_so_files
declare -a processed_thetao_files


info "=== Grid configuration setup ==="

# Save original directory
ORIGINAL_DIR="$(pwd)"

# Get script directory using realpath if available
if command -v realpath >/dev/null 2>&1; then
    SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
else
    # Fallback method
    SCRIPT_PATH="${BASH_SOURCE[0]}"
    if [[ "$SCRIPT_PATH" != /* ]]; then
        SCRIPT_PATH="$ORIGINAL_DIR/$SCRIPT_PATH"
    fi
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
fi

GRID_FILE="$SCRIPT_DIR/EN4_target_grid.txt"

info "Original directory: $ORIGINAL_DIR"
info "Script directory: $SCRIPT_DIR"
info "Grid file path: $GRID_FILE"


# Check if the grid file exists
if [ -f "$GRID_FILE" ]; then
    success "Using target grid file: $GRID_FILE"
    
    # Show grid info
    info "Target grid info:"
    head -10 "$GRID_FILE"
else
    warning "Target grid file not found: $GRID_FILE"
    warning "Regridding will be skipped."
    GRID_FILE=""
fi

# Work directory setup
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"


info "=== EN4 data download from ${START_YEAR}-$(printf "%02d" $START_MONTH) to ${END_YEAR}-$(printf "%02d" $END_MONTH) ==="

# Loop to download and process data year by year
for year in $(seq $START_YEAR $END_YEAR); do
    # Annual zip filename
    zip_filename="EN.4.2.2.analyses.g10.${year}.zip"
    url="${BASE_URL}/${zip_filename}"
    
    echo "Downloading: $zip_filename"
    
    # Download with wget
    if ! wget -c "$url"; then
        error "Error in the download of $zip_filename, continuing with next year..."
        continue
    fi
    
    if [ -f "$zip_filename" ]; then
        success "Extracting: $zip_filename"
        unzip -o "$zip_filename"
        rm "$zip_filename"
        
        # Determine start and end months for this year
        if [ $year -eq $START_YEAR ]; then
            start_m=$START_MONTH
        else
            start_m=1
        fi
        
        if [ $year -eq $END_YEAR ]; then
            end_m=$END_MONTH
        else
            end_m=12
        fi
        
        # Process monthly files extracted for this year
        for month in $(seq $start_m $end_m); do
            month_str=$(printf "%02d" $month)
            monthly_file="EN.4.2.2.f.analysis.g10.${year}${month_str}.nc"
            
            if [ -f "$monthly_file" ]; then
                echo "Processing: $monthly_file"
                
                variables_processed=0
                
                # Process each variable
                for var_name in "${!VAR_CONFIGS[@]}"; do
                    if processed_file=$(process_variable "$monthly_file" "${VAR_CONFIGS[$var_name]}" "$year" "$month_str"); then
                        if [ "$var_name" = "so" ]; then
                            processed_so_files+=("$processed_file")
                        elif [ "$var_name" = "thetao" ]; then
                            processed_thetao_files+=("$processed_file")
                        fi
                        ((variables_processed++))
                    fi
                done
                
                # Show debug info if no variables were processed
                if [ $variables_processed -eq 0 ]; then
                    error "Error in processing $monthly_file - check variable names"
                    warning "Available variables in $monthly_file:"
                    cdo showname "$monthly_file" || ncdump -h "$monthly_file" | grep -A 20 "variables:"
                fi
                
                rm "$monthly_file"
            else
                warning "Monthly file $monthly_file not found."
            fi
        done
        
        # Clean up any remaining .nc files
        rm -f EN.4.2.2.f.analysis.g10.${year}*.nc
        
    else
        error "File $zip_filename not downloaded correctly."
    fi
done

info "=== Temporal merge of processed data ==="

mkdir -p "$FINAL_DIR"

# Process each variable type
for var_name in "${!VAR_CONFIGS[@]}"; do
    # Determine which array to use
    if [ "$var_name" = "so" ]; then
        current_files=("${processed_so_files[@]}")
        file_count=${#processed_so_files[@]}
    elif [ "$var_name" = "thetao" ]; then
        current_files=("${processed_thetao_files[@]}")
        file_count=${#processed_thetao_files[@]}
    fi
    
    if [ $file_count -gt 0 ]; then
        success "Processed ${var_name} files: $file_count"
        
        # Sort files by date
        IFS=$'\n' sorted_files=($(sort <<<"${current_files[*]}"))
        unset IFS
        
        # Temporal merge
        merged_file="${var_name}_EN4_${START_YEAR}$(printf "%02d" $START_MONTH)_${END_YEAR}$(printf "%02d" $END_MONTH).nc"
        info "Creating ${var_name} temporal merge: $merged_file"
        
        cdo mergetime "${sorted_files[@]}" "$merged_file"
        
        # Move to final directory
        info "Moving $merged_file to $FINAL_DIR"
        if safe_move "$merged_file" "$FINAL_DIR/$(basename "$merged_file")"; then
            success "$var_name file moved successfully"
        else
            error "Error moving $var_name file - it stays in $WORK_DIR"
        fi
        
        # Cleanup temporary files
        rm -f "${current_files[@]}"
        
        # Store merged filename for later use
        eval "merged_${var_name}_file=\"$merged_file\""
    else
        error "No ${var_name} files were processed correctly."
    fi
done

info "=== Merge with existing data ==="

cd "$FINAL_DIR"

# Merge with existing data for each variable
for var_name in "${!VAR_CONFIGS[@]}"; do
    merged_var="merged_${var_name}_file"
    if [ -n "${!merged_var}" ]; then
        existing_files=($(ls ${var_name}_EN4_*.nc ${var_name}-*.nc 2>/dev/null | grep -v "$(basename "${!merged_var}")" || true))
        
        if [ ${#existing_files[@]} -gt 0 ]; then
            success "Found existing $var_name files: ${existing_files[*]}"
            
            final_merged="${var_name}_EN4_complete_$(date +%Y%m%d).nc"
            info "Creating complete $var_name merge: $final_merged"
            
            all_files=("${existing_files[@]}" "$(basename "${!merged_var}")")
            cdo mergetime "${all_files[@]}" "$final_merged"
            
            success "$var_name complete merge saved as: $final_merged"
            eval "final_merged_${var_name}=\"$final_merged\""
        fi
    fi
done

# Final cleanup
info "=== Final cleanup ==="
if [ -f "$GRID_FILE" ]; then
    info "Keeping grid file: $GRID_FILE"
fi

success "=== Script successfully completed ==="
success "Final files available in $FINAL_DIR"
if [ -n "$GRID_FILE" ] && [ -f "$GRID_FILE" ]; then
    success "Data regridded to match existing data grid."
else
    warning "Regridding was skipped. Manually check grid consistency if needed."
fi

# Show final info
info "=== Final info of generated files ==="
for var_name in "${!VAR_CONFIGS[@]}"; do
    final_var="final_merged_${var_name}"
    merged_var="merged_${var_name}_file"
    
    if [ -n "${!final_var}" ]; then
        echo -e "${GREEN}--- $(echo $var_name | tr '[:lower:]' '[:upper:]') Complete ---${NC}"
        cdo info "${!final_var}" | head -5
    elif [ -n "${!merged_var}" ]; then
        echo -e "${GREEN}--- $(echo $var_name | tr '[:lower:]' '[:upper:]') New ---${NC}"
        cdo info "$(basename "${!merged_var}")" | head -5
    fi
done



info "=== TEMPORARY: Coordinate comparison ==="

# Function to compare coordinates between reference and new data
compare_coordinates() {
    local reference_file="$1"
    local new_file="$2"
    local var_name="$3"
    
    if [ ! -f "$reference_file" ]; then
        warning "Reference file not found: $reference_file"
        return 1
    fi
    
    if [ ! -f "$new_file" ]; then
        warning "New file not found: $new_file"
        return 1
    fi
    
    echo -e "${BLUE}=== Comparing coordinates for $var_name ===${NC}"
    
    # Compare grid properties
    echo -e "${GREEN}--- GRID COMPARISON ---${NC}"
    echo "Reference grid:"
    cdo griddes "$reference_file" | head -10
    
    echo "New data grid:"
    cdo griddes "$new_file" | head -10
    
    # Check if grids are identical
    echo "Checking if grids are identical..."
    if cdo diffn "$reference_file" "$new_file" > /dev/null 2>&1; then
        success "✓ Grids are IDENTICAL"
    else
        # More detailed comparison
        echo "Grid differences found, checking coordinates..."
        
        # Compare coordinate ranges using showname first
        echo "Reference variables: $(cdo showname "$reference_file")"
        echo "New variables: $(cdo showname "$new_file")"
        
        # Simple lat/lon range check using ncdump
        echo "Reference lat/lon dimensions:"
        ncdump -h "$reference_file" | grep -E "^\s*(lat|lon)\s*="
        
        echo "New data lat/lon dimensions:"
        ncdump -h "$new_file" | grep -E "^\s*(lat|lon)\s*="
    fi
    
    echo ""
    
    # Compare time values
    echo -e "${GREEN}--- TIME COMPARISON ---${NC}"
    echo "Reference time info:"
    echo "Time range:"
    cdo showtimestamp "$reference_file" | head -1
    echo "..."
    cdo showtimestamp "$reference_file" | tail -1
    echo "Total timesteps: $(cdo ntime "$reference_file")"
    
    echo ""
    echo "New data time info:"
    echo "Time range:"
    cdo showtimestamp "$new_file" | head -1
    echo "..."
    cdo showtimestamp "$new_file" | tail -1
    echo "Total timesteps: $(cdo ntime "$new_file")"
    
    # Check temporal overlap
    echo ""
    echo "Time overlap analysis:"
    ref_start=$(cdo showtimestamp "$reference_file" | head -1 | awk '{print $1}')
    ref_end=$(cdo showtimestamp "$reference_file" | tail -1 | awk '{print $NF}')
    new_start=$(cdo showtimestamp "$new_file" | head -1 | awk '{print $1}')
    new_end=$(cdo showtimestamp "$new_file" | tail -1 | awk '{print $NF}')
    
    echo "Reference: $ref_start to $ref_end"
    echo "New data: $new_start to $new_end"
    
    echo -e "${BLUE}=== End comparison for $var_name ===${NC}"
    echo ""
}

# Find files to compare
reference_so="$FINAL_DIR/so-1950_2022.nc"

# Check what SO files we have
if [ -n "${final_merged_so:-}" ] && [ -f "$FINAL_DIR/$final_merged_so" ]; then
    new_so="$FINAL_DIR/$final_merged_so"
    info "Comparing with complete merged SO file"
elif [ -n "${merged_so_file:-}" ] && [ -f "$FINAL_DIR/$(basename "$merged_so_file")" ]; then
    new_so="$FINAL_DIR/$(basename "$merged_so_file")"
    info "Comparing with new SO file only"
else
    warning "No new SO file found for comparison"
    new_so=""
fi

# Perform comparison if we have both files
if [ -n "$new_so" ]; then
    compare_coordinates "$reference_so" "$new_so" "SO"
else
    warning "Cannot perform coordinate comparison - missing files"
    echo "Reference: $reference_so (exists: $([ -f "$reference_so" ] && echo "yes" || echo "no"))"
    echo "New: $new_so"
fi