# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json 
import zlib
import argparse
from pathlib import Path
import random
import sys
import os
sys.path.append("../python")
# Get the parent directory path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Append the parent directory to the Python path
sys.path.append(parent_dir)
# Now you can import unpack.py
from python import unpack
from python import repack



def corrupt_binary_data(data):
    # first byte align the hex string 
    odd_length=0
    if len(data)%2 == 1:
        data = '0x0' + data.split('0x')[1]
        odd_length=1
    #remove '0x' and create a bytearray
    data = bytearray.fromhex(data[2:])
    import random
    #Go byte wise and chose a bit to corrupt
    for corrupt_byte_index in range (0, len(data)):
        corrupt_bit_index = (random.randint(0,7))
        data[corrupt_byte_index] ^= 1 << corrupt_bit_index
        #print(corrupt_byte_index, corrupt_bit_index, len(data), data[corrupt_byte_index], data)
    #Convert back to hexstring
    data = '0x' + data.hex()[odd_length:]
    print(data)
    return data

def descriptor_error(output_dict):
    """
    This function injects error to the initial descriptor data of the first record
    Parameter:
        output_dict: ouptut dictionary having all the values
    """
    data = output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"][0]["RecordDescriptors"][0]["InitialDescriptorData"]
    #data = bytearray(data,"utf-8")
    #corrupted_data = corrupt_binary_data(data)#function for corruption data
    corrupted_data = corrupt_binary_data(data)#function for corruption data
    #corrupted_data_hex = corrupted_data.decode("utf-8")
    output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"][0]["RecordDescriptors"][0]["InitialDescriptorData"] = corrupted_data
    #### Data is corruptes inside output dictionary

def UUID_error(output_dict):
    """
    This function injects error to the descriptor data of descriptor UUID of 4th record
    Parameter:
        output_dict: ouptut dictionary having all the values
    """
    target_record = random.randint(0,len(output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"])-1)
    index = 0
    for element in output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"][target_record]["RecordDescriptors"]:
        if 'AdditionalDescriptorType' in element and element['AdditionalDescriptorType']=='UUID':
            target_desc = index
        index = index + 1
    data = output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"][target_record]["RecordDescriptors"][target_desc]["AdditionalDescriptorIdentifierData"]
    print(data)
    #data = bytearray(data,"utf-8")
    #corrupted_data = corrupt_binary_data(data, [2, 4, 4])#function for corruption data
    corrupted_data = corrupt_binary_data(data)#function for corruption data
    #corrupted_data_hex = corrupted_data.decode("utf-8")
    output_dict["FirmwareDeviceIdentificationArea"]["FirmwareDeviceIDRecords"][target_record]["RecordDescriptors"][1]["AdditionalDescriptorIdentifierData"] = corrupted_data
    #### Data is corruptes inside output dictionary


def image_error(output_dict,firmware_data,error_folder):
    """
    This function randomly picks the individual image components and injects error in them 
    Parameter:
        output_dict: ouptut dictionary having all the values
        firmware_data:Pldm firmware package
        error_folder:output error folder
    """
    error_folder = str(error_folder)
    image_information_index=0
    for image_information_index in range(0,len(output_dict["ComponentImageInformationArea"]['ComponentImageInformation'])):
        file_name_version = output_dict["ComponentImageInformationArea"]['ComponentImageInformation'][image_information_index]['ComponentVersionString']
        file_name_identifier = output_dict["ComponentImageInformationArea"]['ComponentImageInformation'][image_information_index]['ComponentIdentifier']
        file_name = file_name_identifier+"_"+file_name_version + "_image.bin"
        image_start = output_dict["ComponentImageInformationArea"]['ComponentImageInformation'][image_information_index]['ComponentLocationOffset']
        image_end = image_start+output_dict["ComponentImageInformationArea"]['ComponentImageInformation'][image_information_index]['ComponentSize']
        image_information_index = image_information_index+1
        #extarct the image data
        image_data = firmware_data[image_start:image_end]
        mask = 0b00000010 # create a mask with a 1 bit at position 7
        corrupted_data = bytes([image_data[0] ^ mask] + list(image_data[1:])) # flip the bit using bitwise XOR and create a new byte string
        file_name_path = error_folder+"/unpack/"+file_name
        #write back the corrupted data to image bin file
        with open(file_name_path,'wb') as f:
                f.write(corrupted_data)

def signkey_error(signkey_data,error_folder):
    """
    This function injects error to the sign key that is stored inside remaining firmware data file
    Parameter:
        signkey_data:data inside remaininf_firmwareData file
        error_folder: output error folder
    """
    error_folder = str(error_folder)
    mask = 0b00000010 # create a mask with a 1 bit at position 7
    corrupted_data = bytes([signkey_data[0] ^ mask] + list(signkey_data[1:])) # flip the bit using bitwise XOR and create a new byte string
    file_name_path = error_folder+"/unpack/remaining_firmwareData.bin"
    with open(file_name_path,'wb') as f:
            f.write(corrupted_data)

def largefile_error(file_name,start,end):
    """
    This function increase the size of firmware package by padding zeroes and increase the size between 100MB and 200Mb
    Parameter:
        file_name: remaining_firmwareData file
        start:100MB
        end:200MB
    """
    # Open the bin file in append mode
    with open(file_name, "ab") as f:
        # Choose a random padding size from the range
        padding = random.randint(start, end)
        # Write zeros to the file padding times
        f.write(b"\x00" * padding)

def main(file_path, error_file, spec_path):
    file = Path(file_path)
    #name of the file
    file_name = file.name
    #name of main folder
    folder = (file.parent)

    #creating a specific error folder
    error_folder = str(folder)+"_error_"+str(error_file)
    
    unpack.main(file_path, error_folder, spec_path, None)

    #loading data in output dictionary
    with open(error_folder+"/unpack/header.json","r") as f:
        output_dict = json.load(f)

    # injecting error
    if(error_file == "descriptor"):
        descriptor_error(output_dict)  
    elif(error_file == "UUID"):
        UUID_error(output_dict)
    elif(error_file == "image"):
        with open(file_path, 'rb') as firmware_file:
            firmware_data = firmware_file.read()
        image_error(output_dict,firmware_data,error_folder)  
    elif(error_file == "signkey"):
        with open(error_folder+"/unpack/remaining_firmwareData.bin", 'rb') as signkey_file:
            signkey_data = signkey_file.read()
        signkey_error(signkey_data,error_folder)  
    elif(error_file == "largefile"):
        file_name = error_folder+"/unpack/remaining_firmwareData.bin"
        largefile_error(file_name,(100*1024*1024),(200*1024*1024))  

    #dump the output inside unpack folder of error folder 
    with open(error_folder+"/unpack/header.json", "w") as file:
        json.dump(output_dict, file, indent=4)

    #repack the output file having corrupted data

    file_path = os.path.join(error_folder, "unpack")
    repack.main(file_path, error_folder, spec_path)

    #loading header info
    with open(error_folder+"/header_info.bin", 'rb') as file:
        header_info = file.read()

    #remove the last 4 bytes--wrong checksum
    length_without_checksum = len(header_info)-4
    corrupted_data_without_Checksum = header_info[0:length_without_checksum]
    #calculate checksum of the corrupted data
    correct_checksum = zlib.crc32(corrupted_data_without_Checksum)
    correct_checksum_bytes =correct_checksum.to_bytes(4,"little")#convert to 4 bytes in little endian order
    #this is the corrupted data with correct checksum
    corrupted_data_correct_checksum = corrupted_data_without_Checksum + correct_checksum_bytes
    #update the fields inside output_dict
    output_dict["PackageHeaderChecksum"] = correct_checksum

    #rewrite the correct checksum in output dictionary
    with open(error_folder+"/unpack/header.json", "w") as file:
        json.dump(output_dict, file, indent=4)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    #take fwpkg file name along with folder from the user
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path")
    #take the spec version 
    parser.add_argument("-S","--spec-path", required=True, help="Version of the PLDM FW Update Spec", dest="spec_path")
    #takes the error from the user  
    parser.add_argument("-E","--error_file",help="Enter the type of error to be injected", dest="error_file",choices=["descriptor", "UUID", "image","signkey","largefile"])
    args = parser.parse_args()
    file_path = args.fwpkg_file_path # path of the firmware package
    spec_path = args.spec_path
    error_file = args.error_file
    main(file_path, error_file, spec_path)
    
