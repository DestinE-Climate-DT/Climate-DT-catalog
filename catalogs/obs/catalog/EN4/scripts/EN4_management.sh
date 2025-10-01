#!/bin/bash
# filepath: /users/cadaumar/EN4_management.sh

# Script to download, process, and merge EN4 oceanographic data
# With post-processing to match existing data grid

set -e  # Exit on error


# colors for output
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
    
    # Check file size
    local file_size=$(stat -f%z "$src" 2>/dev/null || stat -c%s "$src" 2>/dev/null)
    info "File size: $(($file_size / 1024 / 1024)) MB"
    
    # Check available space in destination directory
    local dst_dir=$(dirname "$dst")
    local available_space=$(df "$dst_dir" | awk 'NR==2 {print $4}')
    local required_space_kb=$((file_size / 1024))
    
    if [ $available_space -lt $required_space_kb ]; then
        error "Not enough space in $dst_dir"
        error "Required: $((required_space_kb / 1024)) MB, Available: $((available_space / 1024)) MB"
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

# Variables configuration
BASE_URL="https://www.metoffice.gov.uk/hadobs/en4/data/en4-2-1"
WORK_DIR="/users/cadaumar/en4_download" #TO BE CHANGED AS NEEDED
FINAL_DIR="/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/EN4"
START_YEAR=2023
START_MONTH=1
END_YEAR=2025
END_MONTH=6

# work directory setup
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

info "=== Grid extraction for existing data ==="

# Look for a reference file to extract the grid
GRID_FILE="$WORK_DIR/target_grid.txt"
reference_file=""

# Look for a reference file in FINAL_DIR
if [ -f "$FINAL_DIR/thetao-1950_2022.nc" ]; then
    reference_file="$FINAL_DIR/thetao-1950_2022.nc"
elif [ -f "$FINAL_DIR/so-1950_2022.nc" ]; then
    reference_file="$FINAL_DIR/so-1950_2022.nc"
else
    # Look for any thetao or so file as fallback
    reference_file=$(ls "$FINAL_DIR"/thetao*.nc "$FINAL_DIR"/so*.nc 2>/dev/null | head -1 || echo "")
fi

if [ -n "$reference_file" ] && [ -f "$reference_file" ]; then
    success "Extracting grid from: $reference_file"
    cdo griddes "$reference_file" > "$GRID_FILE"
    success "Grid extracted and saved on: $GRID_FILE"
    
    # Show grid info
    info "Target grid info:"
    head -10 "$GRID_FILE"
else
    warning "No reference file found to extract grid."
    warning "Regridding will be skipped."
    GRID_FILE=""
fi

info "=== EN4 data download from ${START_YEAR}-$(printf "%02d" $START_MONTH) to ${END_YEAR}-$(printf "%02d" $END_MONTH) ==="

# Array for processed combined files
processed_so_combined_files=()
processed_thetao_combined_files=()

# Loop to download and process data year by year
for year in $(seq $START_YEAR $END_YEAR); do
    # Annual zip filename
    zip_filename="EN.4.2.2.analyses.g10.${year}.zip"
    url="${BASE_URL}/${zip_filename}"
    
    echo "Downloading: $zip_filename"
    
    # Download con wget
    if ! wget -c "$url"; then
        error "Error in the download of $zip_filename, continuing with next year..."
        continue
    fi
    
    # Check the zip files has been downloaded correctly
    if [ -f "$zip_filename" ]; then
        success "Extracting: $zip_filename"
        
        # Extract zip file content
        unzip -o "$zip_filename"
        
        # Remove the full zip file to save space
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
            # Monthly file name
            monthly_file="EN.4.2.2.f.analysis.g10.${year}${month_str}.nc"
            
            if [ -f "$monthly_file" ]; then
                echo "Processing: $monthly_file"
                
                # Temp file for single variable
                so_temp="temp_so_${year}${month_str}.nc"
                thetao_temp="temp_thetao_${year}${month_str}.nc"
                
                # Final combined filenames
                so_combined="so_${year}${month_str}.nc"
                thetao_combined="thetao_${year}${month_str}.nc"
                
                # Flag to verify if extraction was successful
                so_extracted=false
                thetao_extracted=false
                
                # === PROCESSING SO (SALINITY) ===
                info "Processing salinity for $monthly_file"
                
                # 1. Extract salinity + salinity_uncertainty
                if cdo selvar,salinity,salinity_uncertainty "$monthly_file" "$so_temp" 2>/dev/null; then
                    success "Extracted salinity + salinity_uncertainty"
                    so_extracted=true
                elif cdo selvar,salinity "$monthly_file" "$so_temp" 2>/dev/null; then
                    warning "Only salinity has been extracted (uncertainty not available)"
                    so_extracted=true
                else
                    warning "salinity not found in $monthly_file"
                fi
                
                if [ "$so_extracted" = true ]; then
                    # 2. Remove problematic attributes (valid_min/max)
                    ncatted -O -a valid_max,salinity,d,, "$so_temp" 2>/dev/null || true
                    ncatted -O -a valid_min,salinity,d,, "$so_temp" 2>/dev/null || true
                    ncatted -O -a valid_max,salinity_uncertainty,d,, "$so_temp" 2>/dev/null || true
                    ncatted -O -a valid_min,salinity_uncertainty,d,, "$so_temp" 2>/dev/null || true
                    
                    # 3. Rename variables
                    ncrename -v salinity,so "$so_temp" 2>/dev/null || true
                    ncrename -v salinity_uncertainty,so_uncertainty "$so_temp" 2>/dev/null || true
                    
                    # 4. Change attributes
                    ncatted -O -a long_name,so,m,c,"Sea water salinity" "$so_temp" 2>/dev/null || true
                    ncatted -O -a standard_name,so,m,c,"sea_water_salinity" "$so_temp" 2>/dev/null || true
                    
                    # 5. Rename depth dimension to lev
                    ncrename -d depth,lev -v depth,lev "$so_temp" 2>/dev/null || true
                    ncatted -O -a standard_name,lev,c,c,"depth" "$so_temp" 2>/dev/null || true
                    
                    # 6. Convert time to float
                    ncap2 -O -s "time=float(time)" "$so_temp" "temp_final_so_${year}${month_str}.nc" 2>/dev/null || cp "$so_temp" "temp_final_so_${year}${month_str}.nc"
                    
                    # 7. Regridding (if grid file is available)
                    if [ -n "$GRID_FILE" ] && [ -f "$GRID_FILE" ]; then
                        info "Applying regridding to so..."
                        cdo -s remapbil,"$GRID_FILE" "temp_final_so_${year}${month_str}.nc" "$so_combined"
                        rm "temp_final_so_${year}${month_str}.nc"
                        success "so regridding completed"
                    else
                        mv "temp_final_so_${year}${month_str}.nc" "$so_combined"
                        warning "Regridding skipped (grid not available)"
                    fi
                    
                    processed_so_combined_files+=("$so_combined")
                    success "Processed so: $so_combined"
                fi
                
                # === PROCESSING THETAO (POTENTIAL TEMPERATURE) ===
                info "Processing temperature for $monthly_file"
                
                # 1. Extract temperature + temperature_uncertainty
                if cdo selvar,temperature,temperature_uncertainty "$monthly_file" "$thetao_temp" 2>/dev/null; then
                    success "Extracted potential temperature + temperature_uncertainty"
                    thetao_extracted=true
                elif cdo selvar,temperature "$monthly_file" "$thetao_temp" 2>/dev/null; then
                    warning "Only potential temperature (uncertainty not available)"
                    thetao_extracted=true
                else
                    warning "potential temperature not found in $monthly_file"
                fi
                
                if [ "$thetao_extracted" = true ]; then
                    # 2. Remove problematic attributes (valid_min/max)
                    ncatted -O -a valid_max,temperature,d,, "$thetao_temp" 2>/dev/null || true
                    ncatted -O -a valid_min,temperature,d,, "$thetao_temp" 2>/dev/null || true
                    ncatted -O -a valid_max,temperature_uncertainty,d,, "$thetao_temp" 2>/dev/null || true
                    ncatted -O -a valid_min,temperature_uncertainty,d,, "$thetao_temp" 2>/dev/null || true
                    
                    # 3. Rename variables
                    ncrename -v temperature,thetao "$thetao_temp" 2>/dev/null || true
                    ncrename -v temperature_uncertainty,thetao_uncertainty "$thetao_temp" 2>/dev/null || true
                    
                    # 4. Change attributes
                    ncatted -O -a long_name,thetao,m,c,"Potential temperature" "$thetao_temp" 2>/dev/null || true
                    ncatted -O -a standard_name,thetao,m,c,"sea_water_potential_temperature" "$thetao_temp" 2>/dev/null || true
                    
                    # 5. Rename depth dimension to lev
                    ncrename -d depth,lev -v depth,lev "$thetao_temp" 2>/dev/null || true
                    ncatted -O -a standard_name,lev,c,c,"depth" "$thetao_temp" 2>/dev/null || true
                    
                    # 6. Convert time to float
                    ncap2 -O -s "time=float(time)" "$thetao_temp" "temp_final_thetao_${year}${month_str}.nc" 2>/dev/null || cp "$thetao_temp" "temp_final_thetao_${year}${month_str}.nc"
                    
                    # 7. Regridding (if grid file is available)
                    if [ -n "$GRID_FILE" ] && [ -f "$GRID_FILE" ]; then
                        info "Applying regridding to thetao..."
                        cdo -s remapbil,"$GRID_FILE" "temp_final_thetao_${year}${month_str}.nc" "$thetao_combined"
                        rm "temp_final_thetao_${year}${month_str}.nc"
                        success "thetao regridding completed"
                    else
                        mv "temp_final_thetao_${year}${month_str}.nc" "$thetao_combined"
                        warning "Regridding skipped (grid not available)"
                    fi
                    
                    processed_thetao_combined_files+=("$thetao_combined")
                    success "Processed thetao: $thetao_combined"
                fi
                
                # Cleanup temporary files
                rm -f "$so_temp" "$thetao_temp"
                
                # Se no extraction was successful, show available variables for debugging
                if [ "$so_extracted" = false ] && [ "$thetao_extracted" = false ]; then
                    error "Error inprocessing $monthly_file - check variable names"
                    warning "Available variables in $monthly_file:"
                    cdo showname "$monthly_file" || ncdump -h "$monthly_file" | grep -A 20 "variables:"
                fi
                
                # Remove original monthly file to save space
                rm "$monthly_file"
            else
                warning "Monthly file $monthly_file not found."
            fi
        done
        
        # Clean up any remaining .nc files extracted but not processed
        rm -f EN.4.2.2.f.analysis.g10.${year}*.nc
        
    else
        error "File $zip_filename not downloaded correctly."
    fi
done

info "=== Temporal merge of processed data ==="

# Check the final directory exists
mkdir -p "$FINAL_DIR"

# Merge for SO COMBINED (salinity + uncertainty)
if [ ${#processed_so_combined_files[@]} -gt 0 ]; then
    success "Processed so_combined files: ${#processed_so_combined_files[@]}"
    
    # Sort files by date
    IFS=$'\n' sorted_so_combined_files=($(sort <<<"${processed_so_combined_files[*]}"))
    unset IFS
    
    # Temporal merge of all monthly so_combined files
    merged_so_combined_file="so_EN4_${START_YEAR}$(printf "%02d" $START_MONTH)_${END_YEAR}$(printf "%02d" $END_MONTH).nc"
    info "Creating so_combined temporal merge: $merged_so_combined_file"
    
    cdo mergetime "${sorted_so_combined_files[@]}" "$merged_so_combined_file"
    
    # Move the merged file to the final directory using the safe function
    info "Moving $merged_so_combined_file to $FINAL_DIR"
    if safe_move "$merged_so_combined_file" "$FINAL_DIR/$(basename "$merged_so_combined_file")"; then
        success "File so moved successfully"
    else
        error "Error moving the fil so - it stays in $WORK_DIR"
    fi
    
    # Temporary cleanup of so_combined files
    rm -f "${processed_so_combined_files[@]}"
else
    error "No so_combined file was processed correctly."
fi

# Merge for THETAO COMBINED (potential temperature + uncertainty)
if [ ${#processed_thetao_combined_files[@]} -gt 0 ]; then
    success "thetao_combined processed files: ${#processed_thetao_combined_files[@]}"
    
    # Sort files by date
    IFS=$'\n' sorted_thetao_combined_files=($(sort <<<"${processed_thetao_combined_files[*]}"))
    unset IFS
    
    # Temporal merge of all monthly thetao_combined files
    merged_thetao_combined_file="thetao_EN4_${START_YEAR}$(printf "%02d" $START_MONTH)_${END_YEAR}$(printf "%02d" $END_MONTH).nc"
    info "creating thetao_combined temporal merge: $merged_thetao_combined_file"
    
    cdo mergetime "${sorted_thetao_combined_files[@]}" "$merged_thetao_combined_file"
    
    # Move the merged file to the final directory using the safe function
    info "Moving $merged_thetao_combined_file to $FINAL_DIR"
    if safe_move "$merged_thetao_combined_file" "$FINAL_DIR/$(basename "$merged_thetao_combined_file")"; then
        success "thetao file moved successfully"
    else
        error "Impossibile spostare il file thetao - rimane in $WORK_DIR"
    fi
    
    # Cleanup dei file temporanei thetao_combined
    rm -f "${processed_thetao_combined_files[@]}"
else
    error "Nessun file thetao_combined è stato processato correttamente!"
fi

info "=== Merge con dati esistenti ==="

cd "$FINAL_DIR"

# Merge per SO COMBINED
so_existing_files=($(ls so_EN4_*.nc so-*.nc 2>/dev/null | grep -v "$(basename "$merged_so_combined_file")" || true))
if [[ ${#so_existing_files[@]} -gt 0 && -n "${merged_so_combined_file:-}" ]]; then
    success "Trovati file so esistenti: ${so_existing_files[*]}"
    
    final_merged_so="so_EN4_complete_$(date +%Y%m%d).nc"
    info "Creando merge completo so: $final_merged_so"
    
    all_so_files=("${so_existing_files[@]}" "$(basename "$merged_so_combined_file")")
    cdo mergetime "${all_so_files[@]}" "$final_merged_so"
    
    success "Merge so completo salvato come: $final_merged_so"
fi

# Merge per THETAO COMBINED
thetao_existing_files=($(ls thetao_EN4_*.nc thetao-*.nc 2>/dev/null | grep -v "$(basename "$merged_thetao_combined_file")" || true))
if [[ ${#thetao_existing_files[@]} -gt 0 && -n "${merged_thetao_combined_file:-}" ]]; then
    success "found existing thetao files: ${thetao_existing_files[*]}"
    
    final_merged_thetao="thetao_EN4_complete_$(date +%Y%m%d).nc"
    info "Creating complete thetao merge: $final_merged_thetao"
    
    all_thetao_files=("${thetao_existing_files[@]}" "$(basename "$merged_thetao_combined_file")")
    cdo mergetime "${all_thetao_files[@]}" "$final_merged_thetao"
    
    success "thetao complete merge saved as: $final_merged_thetao"
fi

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
if [ -n "${final_merged_so:-}" ]; then
    echo -e "${GREEN}--- SO (Salinity) Complete ---${NC}"
    cdo info "$final_merged_so" | head -5
elif [ -n "${merged_so_combined_file:-}" ]; then
    echo -e "${GREEN}--- SO (Salinity) New ---${NC}"
    cdo info "$(basename "$merged_so_combined_file")" | head -5
fi

if [ -n "${final_merged_thetao:-}" ]; then
    echo -e "${GREEN}--- THETAO (Temperature) Complete ---${NC}"
    cdo info "$final_merged_thetao" | head -5
elif [ -n "${merged_thetao_combined_file:-}" ]; then
    echo -e "${GREEN}--- THETAO (Temperature) New ---${NC}"
    cdo info "$(basename "$merged_thetao_combined_file")" | head -5
fi