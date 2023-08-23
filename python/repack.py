# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import struct
from datetime import datetime
import binascii
import operator
import argparse
from pathlib import Path
import os

info = {}
output_dict = {}

def encode_timestamp(value):
    """
    This function is used to encode timestamp. The timestamp is formatted as series of 13 bytes defined in DSP0240 specification.
        Parameters:
            value: PackageReleaseDateTime field value
    """
    dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S:%f %z')
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second
    microsecond = dt.microsecond
    utc_offset = dt.utcoffset().total_seconds()
    utc_time_resolution = 0 
    packedData = struct.pack(
            "<hBBBBBBBBHB",
            int(utc_offset),
            microsecond & 0xFF,
            (microsecond >> 8) & 0xFF,
            (microsecond >> 16) & 0xFF,
            second,
            minute,
            hour,
            day,
            month,
            year,
            utc_time_resolution
        )
    return packedData

def encode_data(value,data_type,data_length):
    """
    This function encodes the data to hex or int and then convert it into bytes object
        Parameters:
            data: Extracted firmware data for a particular field 
            data_type: data types(hex,int,ASCII)
            data_length: length of the field
    """
    if isinstance(value,int):
        return struct.pack(f"{data_length}s", value.to_bytes(data_length, "little"))
    if isinstance(value,str):
        if data_type == "hex":
            # packs the hexadecimal value into a binary string using the struct module
            return struct.pack(f"{data_length}s", bytes.fromhex(value))
        elif data_type == "timestamp":
            return encode_timestamp(value)
        elif data_type == "special_decode":
            #convert hexadecimal string into an integer
            int_value = int(value,16) #use 16 as the base argument
            #convert integer into bytes object
            return int_value.to_bytes(data_length,"little")
        elif data_type == "ASCII":
            hex_string = binascii.hexlify(value.encode()).decode() 
            return bytes.fromhex(hex_string)
        elif data_type == "utf-8":
            hex_string = binascii.hexlify(value.encode('utf-8')).decode('utf-8') 
            return bytes.fromhex(hex_string)
        elif data_type == "utf-16":
            hex_string = binascii.hexlify(value.encode('utf-8')).decode('utf-16') 
            return bytes.fromhex(hex_string)
        elif data_type == "utf-16le":
            hex_string = binascii.hexlify(value.encode('utf-16le')).decode('utf-16le') 
            return bytes.fromhex(hex_string)
        elif data_type == "utf-16be":
            hex_string = binascii.hexlify(value.encode('utf-16be')).decode('utf-16be') 
            return bytes.fromhex(hex_string)
        else:
            return str(value).encode()
 

def process(firmware_data,output_dict,field_name,data_length,data_type):
    """
    This function extracts the value from output dicitonary and then passes it to the encode_data function  
    firmware data
        Parameters:
            firmware_data: PLDM firmware package
            output_dict: output dicitionary with all the decoded values
            field name :current field
            data_length: length of field extarcted from spec folder
            data_type: data_type of field extracted from spec folder
    """
    operators = ["+", "-", "*", "/"]
    functions = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
    #When the length field has +,-,/,*
    if isinstance(data_length, str):
        for op in operators:
            if op in data_length:
                parts = data_length.split(op)
                before = parts[0]
                after = parts[1]
                before_num = output_dict[before]
                after_num = output_dict[after]
                data_length = functions[op](before_num, after_num)
                break
        else:
            data_length = output_dict[data_length]

    value = output_dict[field_name]
    packedData = encode_data(value,data_type,data_length)
    #adding the encoded data to firmware data
    firmware_data +=packedData
    return firmware_data

def process_count(firmware_data, output_dict, field_name, input_json_data, count_field):
    """
    This function is for the fields having multiple instances in the firmware data eg records and descriptors 
    Parameters:
        firmware_data: PLDM firmware package
        output_dict: output dicitionary with all the decoded values
        field name :current field
        input_json_data:input json for that specific field
        count_field: value of count key
    """
    #First check if count is the first field or not. Store the index for now. 
    count_index = list(input_json_data).index('count')
    #When the count field is indirect and string and has some operation in it
    if isinstance(count_field, str):
        operators = ["+", "-", "*", "/"]
        functions = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
        for op in operators:
            if op in count_field:
                parts = count_field.split(op)
                before = parts[0]
                after = parts[1]
                before_num = output_dict[before]
                after_num = int(after)
                count = functions[op](before_num, after_num)
                break
        else: # This will execute only if the loop did not break
            count = output_dict[count_field]        
    else:
        count = count_field
    #keep a copy of input json file before passing to the search function
    input_json_data_copy = input_json_data.copy()
    #removing count or it will go into infinite loop
    input_json_data_copy.pop("count")
    #Check if there are elements in the spec before count - these should not be repeated. 
    #But together they will be treated as one element
    if count_index!=0:
        input_json_data_precount={}
        for i in range(count_index):
            input_json_data_precount[list(input_json_data_copy)[0]]=input_json_data_copy[list(input_json_data_copy)[0]]
            input_json_data_copy.pop(list(input_json_data_copy)[0])
        firmware_data = search(firmware_data, input_json_data_precount, output_dict[field_name][0])
        #Update count_index for the array of repeated entries
        count_index=1
    for i in range(count_index, count):
        firmware_data = search(firmware_data, input_json_data_copy, output_dict[field_name][i])
    return firmware_data

def process_decode(firmware_data, output_dict,field_name, data_length, data_type,decode):
    """
    This function is for fields having specical decode feature
        Parameter:
            firmware_data: PLDM firmware package
            output_dict: output dicitionary with all the decoded values
            field name :current field
            data_length: length of field extarcted from spec folder
            data_type: data_type of field extracted from spec folder
            decode: decode spec from json file
    """
    if isinstance(data_length,int):#initial descriptor type and additional descriptor type
        value = output_dict[field_name]
        key = None
        for k,v in decode.items():
            if v == value:
                key = k
                break
        packedData = encode_data(key,data_type,data_length)#is this data length same?
        firmware_data += packedData
    # For AdditionalDescriptorType having AdditionalDescriptorType as Vendor Defined and indirect data length
    elif("Vendor Defined" in decode): #AdditionalDescriptorIdentifierData
        if(output_dict["AdditionalDescriptorType"] == "Vendor Defined"):
            data_length = output_dict[data_length]
            packedData = b""
            vendorData=search(packedData,decode["Vendor Defined"],output_dict)
            if(data_length != len(vendorData)):
                vendorData = vendorData[:data_length]
            firmware_data+= vendorData
        else:
            data_length = output_dict[data_length]
            value = output_dict[field_name]
            packedData = encode_data(value, data_type, data_length)
            if(packedData):
                firmware_data += packedData
    else: 
        #data_type and data_length are indirect 
        data_length = output_dict[data_length]
        data_type_no = output_dict[data_type]
        data_type = decode[str(data_type_no)]
        value = output_dict[field_name]
        #call the encode_data function
        packedData = encode_data(value, data_type,data_length)
        #add the encoded data into firmware data
        firmware_data += packedData
            
    return firmware_data

def search(firmware_data,input_json_data, output_dict):
    """
    It is a recursive function use to get the keys inside the innermost dictionary of spec json
    Parameters:
        firmware_data: PLDM firmware package
        input_json_data:input json for that specific field
        output_dict: output dicitionary with all the decoded values
    """
    global info
    for field_name, field_info in input_json_data.items():
        if isinstance(field_info, dict):
            if "decode" in field_info:
                #for fields having additional key -decode
                firmware_data = process_decode(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"],field_info["decode"])
                # continue
            #for fields having only length key
            elif "length" in field_info:
                if(field_info["length"]=="ComponentBitmapBitLength"):
                    data_length = int(info["ComponentBitmapBitLength"]/8)
                    firmware_data = process(firmware_data, output_dict,field_name, data_length, field_info["data_type"])
                else:
                    firmware_data = process(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"])
            #for fields having additional key- count
            elif "count" in field_info:
                firmware_data=process_count(firmware_data,output_dict,field_name,field_info,field_info["count"])
                continue
            #recursively calls the search function
            else:
                firmware_data = search(firmware_data,field_info,output_dict[field_name])
            #for applicable component field as value of length is present in another fields which is on a different level
            if(field_name == "PackageVersionString"):
                info = output_dict
    return firmware_data

def image_gluing(firmware_data,image_output_data,folder):
    """
    This function extracts data from image bin files present in the unpack folder and append it to the firmware package
        Parameters:
            firmware_data_new  = firmware data
            image_json: image dictionary from spec
            folder:output folder
    """
    #number of images present in the package
    count = image_output_data["ComponentImageCount"]
    for i in range(count):
        # creating file path of the image bin file
        file_name_version = image_output_data['ComponentImageInformation'][i]['ComponentVersionString']  #file version for file name
        file_name_identifier = image_output_data['ComponentImageInformation'][i]['ComponentIdentifier'] #file identifier for file name
        file_name = file_name_identifier+"_"+file_name_version + "_image" #file name
        image_start = image_output_data['ComponentImageInformation'][i]['ComponentLocationOffset'] #image offset

        #if image does not start immediately where the firmware_data ends
        if(image_start != len(firmware_data)+1): 
            size = image_start-len(firmware_data) #zero padding
            bytes_obj =bytes(size)
            firmware_data+=bytes_obj 

        # adding image data to firmware data
        file_path = folder/"unpack"/(file_name+'.bin')  
        with open(file_path, 'rb') as image_file: #open image bin file
            image_data = image_file.read()
        firmware_data+=image_data # add image data to firmware_data
    return firmware_data #return the final image data

def main(file_path,output):
    file = Path(file_path)
    
    #output is when there is error
    #output_folder is used when the file is repacked without any errors then parent folder is being used

    #name of main folder
    output_folder = (file.parent)
    if(output != None):
        output=Path(output)
    
    #this is for handling folders-error files will go to new folder
    folder = output or output_folder

    #path to the spec json file
    json_file_path = "spec\pldm_spec.json"

    with open(json_file_path, 'r') as json_file:
        json_data = json.load(json_file)

    with open(folder/"unpack/header.json","r") as f:
        output_dict = json.load(f)
    
    #creating an empty byte object
    firmware_data = b""
    firmware_data = search(firmware_data,json_data,output_dict)

    #storing header info in a bin file-will be used for calculating the checksum
    with open(folder/"header_info.bin",'wb') as f:
        f.write(firmware_data)

    firmware_data_updated = image_gluing(firmware_data,output_dict["ComponentImageInformationArea"],folder)
    
    # adding signature or remaining data from the firmware file
    remaining_data_file_path = folder/"unpack/remaining_firmwareData.bin"
    with open(remaining_data_file_path, 'rb') as file: #open remaining firmware data bin file
        remaining_data = file.read()
    firmware_data_updated+= remaining_data #add the remaining data to firmware file

    #create repack folder
    new_path = folder / "repack"
    new_path.mkdir()
    with open(new_path/"repacked_data.fwpkg","wb") as f:
        f.write(firmware_data_updated)

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    #take fwpkg file name along with folder from the user
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path")
    #takes the output folder in which the corrupted package will be stored
    parser.add_argument("-E", "--output", required=False, help="output folder")#for error injection
    args = parser.parse_args()
    file_path = args.fwpkg_file_path
    main(file_path,args.output)
    