# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from pathlib import Path
import os
import sys
sys.path.append("../python")
# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Append the parent directory to the Python path
sys.path.append(parent_dir)
# Now you can import unpack.py
from python import unpack
from python import repack
from python import error_injection


class UpdateChoices(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Get the error argument value
        error = getattr(namespace, "error_file")
        # Get the name argument choices
        choices = self.choices
        # If error is present, add one more choice
        if error:
            choices.append("error_injection")
            # Set the name argument value to error_injection
            values = "error_injection"
        # Check if the name argument value is valid
        if values not in choices:
            parser.error(f"invalid choice: {values} (choose from {', '.join(choices)})")
        # Set the name argument value
        setattr(namespace, self.dest, values)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    #take fwpkg file name along with folder from the user
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path") #file path
    #Define the PLDM FW Update Specification Version
    parser.add_argument("-S", "--spec-path", help="Version of the PLDM FW update Spec", dest="spec_path", choices=["pldm_spec_1.0.0","pldm_spec_1.1.0","pldm_spec_1.2.0","pldm_spec_1.3.0"], default="pldm_spec_1.0.0") 
    # Define the name argument with the custom action class
    parser.add_argument("-N","--name", help="Enter name of the program", choices=["unpack", "repack"], action=UpdateChoices)
    # Define the error argument as an optional choice
    parser.add_argument("-E","--error_file",help="Enter the type of error to be injected", dest="error_file",choices=["descriptor", "UUID", "image","signkey","largefile"])
    # Return only header.json file as output
    parser.add_argument("-D", "--dump_header_json", help="Dump Header.json from bundle", dest="dump_header_json", action="store_true")
    # take the output path in which unpacked data/header.json file will be stored
    parser.add_argument("-O", "--output", help="Provide directory path for storing output data", dest="output", required=False)
    args = parser.parse_args()
    if args.name in ["unpack", "repack"] and not args.fwpkg_file_path:
        parser.error("argument -F/--fwpkg-file-path is required when --mode is ['unpack', 'repack']")

    file_path = args.fwpkg_file_path # path of the firmware package
    spec_path = args.spec_path
    program_name = args.name #name of the python code
    error_file = args.error_file #type of error
    dump_header = args.dump_header_json
    output_dir = args.output
    
    file = Path(file_path)
    #name of main folder
    folder = (file.parent)
    if(error_file):
        program_name = "error_injection"
#handling error files
if(error_file):
    output_parent_folder = str(folder)+"_error_"+str(error_file)
    error_injection.main(file_path,error_file)
    output_folder = output_parent_folder
    print("\nError Injected successfully.")
    output_path = os.path.abspath(output_folder)
    print(f"Corrupted files are available here: {output_path}")
    image_file_path  =Path("repack/repacked_data.fwpkg")
    image_path = output_path/image_file_path
    print("Full image is available here:",image_path)
    
elif(program_name):
    if (output_dir != None):
        output_parent_folder = output_dir
    else:
        output_parent_folder = str(folder)
    if(program_name == "unpack"):
        #unpack
        output_folder = output_parent_folder +"/unpack"
        error_file=None
        if unpack.main(file_path, output_dir, spec_path, None):
            print("\nUnpack was successful. CRC matches! Package is PLDM compliant.")
        else: 
            print("\nUnpack was successful. But CRC mismatches!")
        output_path = os.path.abspath(output_folder)
        print(f"Unpacked files are available here: {output_path}")
    elif(program_name == "repack"):
        #repack
        output_folder = output_parent_folder +"/repack/repacked_data.fwpkg"
        repack.main(file_path, output_dir, spec_path)
        print("\nRepack was successful.")
        output_path = os.path.abspath(output_folder)
        print(f"Repacked file is available at: {output_path}")

#unpack and repack both
elif not (program_name) and not (error_file) and not (dump_header):
    if (output_dir != None):
        output_parent_folder = output_dir
    else:
        output_parent_folder = str(folder)
    #unpack
    output_folder = output_parent_folder +"/unpack"
    if unpack.main(file_path, output_dir, spec_path, None):
        print("\nUnpack was successful. CRC matches! Package is PLDM compliant.")
    else: 
        print("\nUnpack was successful. But CRC mismatches!")
    output_path = os.path.abspath(output_folder)
    print(f"Unpacked files are available here: {output_path}")
    
    #repack
    output_folder = output_parent_folder +"/repack/repacked_data.fwpkg"
    repack.main(file_path, output_dir, spec_path)
    print("\nRepack was successful.")
    output_path = os.path.abspath(output_folder)
    print(f"Repacked file is available at: {output_path}")
    
#only dump header.json
elif dump_header:
    if (output_dir != None):
        output_parent_folder = output_dir
    else:
        output_parent_folder = str(folder)
    output_folder = output_parent_folder +"/unpack"
    if unpack.main(file_path, output_dir, spec_path, dump_header):
        print("\nHeader.json file saved. CRC matches! Package is PLDM compliant.")
    else: 
        print("\nHeader.json file saved. But CRC mismatches!")
    output_path = os.path.abspath(output_folder)
    print(f"header.json file available here: {output_path}")