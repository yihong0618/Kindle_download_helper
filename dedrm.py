import os
import sys
import time
import shutil

from mobi import extract
from kindle_download_helper.dedrm import MobiBook, get_pid_list

def read_key_from_file(directory):
    key_file_path = os.path.join(directory, 'key.txt')
    try:
        with open(key_file_path, 'r') as file:
            for line in file:
                if line.startswith('Key is:'):
                    return line.strip().split('Key is:')[1].strip()
    except FileNotFoundError:
        print(f"No key file found in {directory}. Proceeding without a key.")
    return None

def process_azw_files(source_directory, output_directory='DeDRMed', device_serial_number=None, dump_azw=True, dump_epub=True):
    if device_serial_number is None:
        device_serial_number = read_key_from_file(source_directory)
        if device_serial_number is None:
            print("No device serial number provided and key.txt not found. Exiting.")
            sys.exit(1)

    azw_output_dir = os.path.join(output_directory, 'azw')
    epub_output_dir = os.path.join(output_directory, 'epub')

    # Create output directories if they don't exist
    os.makedirs(azw_output_dir, exist_ok=True)
    os.makedirs(epub_output_dir, exist_ok=True)

    for filename in os.listdir(source_directory):
        if filename.endswith((".azw", ".azw3")):
            print(f"Processed {filename}: ", end="")
            path = os.path.join(source_directory, filename)
            try:
                out = path  # Original file path
                file_base, file_extension = os.path.splitext(filename)
                out_dedrm = os.path.join(azw_output_dir, f"{file_base}_dedrm{file_extension}")  # Maintain original extension for DeDRMed file

                # Process for DeDRM
                mb = MobiBook(out)
                md1, md2 = mb.get_pid_meta_info()
                totalpids = get_pid_list(md1, md2, [device_serial_number], [])
                totalpids = list(set(totalpids))
                mb.make_drm_file(totalpids, out_dedrm)
                time.sleep(1)

                if dump_azw:
                    print(f"DeDRMed file saved in {azw_output_dir} ")

                if not dump_epub: continue

                # Extract and determine if output is EPUB or HTML
                epub_dir, output_file = extract(out_dedrm)
                output_extension = os.path.splitext(output_file)[1].lower()

                # Determine final output path based on file type
                if output_extension in ['.html', '.htm']:
                    # Handle HTML files differently
                    final_output_path = os.path.join(epub_output_dir, f"{file_base}{output_extension}")
                else:
                    # Default to EPUB handling
                    final_output_path = os.path.join(epub_output_dir, f"{file_base}.epub")

                shutil.copy2(output_file, final_output_path)
                shutil.rmtree(epub_dir)  # Clean up extraction directory

                print(f"EPUB/HTML saved as {final_output_path}.")
                if not dump_azw:
                    os.remove(out_dedrm)
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    cmd_usage = "Usage: script.py <source_directory> [output_directory] [device_serial_number] [specific_filetype(azw/epub)]"
    if len(sys.argv) < 2:
        print(cmd_usage)
        sys.exit(1)

    source_directory = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else 'DeDRMed'
    device_serial_number = sys.argv[3] if len(sys.argv) > 3 else None

    dump_azw = True
    dump_epub = True
    if len(sys.argv) > 4:
        if sys.argv[4] == 'azw':
            dump_epub = False
        elif sys.argv[4] == 'epub':
            dump_azw = False
        else:
            print(cmd_usage)
            sys.exit(1)

    process_azw_files(source_directory, output_directory, device_serial_number, dump_azw, dump_epub)