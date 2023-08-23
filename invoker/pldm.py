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
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path",required=True) #file path
    # Define the name argument with the custom action class
    parser.add_argument("-N","--name", help="Enter name of the program", choices=["unpack", "repack"], action=UpdateChoices)
    # Define the error argument as an optional choice
    parser.add_argument("-E","--error_file",help="Enter the type of error to be injected", dest="error_file",choices=["descriptor", "UUID", "image","signkey","largefile"])
    args = parser.parse_args()

    file_path = args.fwpkg_file_path # path of the firmware package
    program_name = args.name #name of the python code
    error_file = args.error_file #type of error
    
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
    
#debugging 
elif(program_name):
    output_parent_folder = str(folder)
    if(program_name == "unpack"):
        #unpack
        output_folder = output_parent_folder +"/unpack"
        error_file=None
        unpack.main(file_path,error_file)
        print("\nUnpack was successful.CRC matches! Package is PLDM compliant.")
        output_path = os.path.abspath(output_folder)
        print(f"Unpacked files are available here: {output_path}")
    elif(program_name == "repack"):
        #repack
        output_folder = output_parent_folder +"/repack/repacked_data.fwpkg"
        repack.main(file_path,error_file)
        print("\nRepack was successful.")
        output_path = os.path.abspath(output_folder)
        print(f"Repacked file is available at: {output_path}")
       
#both
elif not (program_name) and not (error_file):
    output_parent_folder = str(folder)
    #unpack
    output_folder = output_parent_folder +"/unpack"
    error_file=None
    unpack.main(file_path,error_file)
    print("\nUnpack was successful.CRC matches! Package is PLDM compliant.")
    output_path = os.path.abspath(output_folder)
    print(f"Unpacked files are available here: {output_path}")
    
    #repack
    output_folder = output_parent_folder +"/repack/repacked_data.fwpkg"
    repack.main(file_path,error_file)
    print("\nRepack was successful.")
    output_path = os.path.abspath(output_folder)
    print(f"Repacked file is available at: {output_path}")


