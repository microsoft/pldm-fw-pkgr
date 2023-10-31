# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json 
from datetime import datetime
import binascii
import operator
import sys
import zlib
import argparse
import os
from pathlib import Path

#to store the output of PackageHeaderInformation
#will be used to extract the length of ApplicableComponents stored in ComponentBitmapBitLength
info = {} 

#decoded data bytes will be stored here to calculate checksum
checksum_data = b""

def parse_field(data, data_type):
    """
    This function decodes the data to more readable form depending upon the data type
        Parameters:
            data: Extracted firmware data for a particular field 
            data_type: data types(hex,int,ASCII)
    """
    if isinstance(data, bytes):
        if data_type == 'hex':  
            return data.hex()
        #this is used to handle the cases of reversed outputs
        elif data_type == 'special_decode':
            return hex(int.from_bytes(data, byteorder='little'))
        elif data_type == 'int':  
            return int.from_bytes(data, byteorder='little')
        elif data_type == 'string':  
            return data.decode()
        elif data_type == 'timestamp':
            return decode_timestamp(data)
        elif data_type == 'bytes':
            return int.from_bytes(data,'little')
        elif data_type == 'ASCII':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode()
        elif data_type == 'utf-8':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode('utf-8')
        elif data_type == 'utf-16':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode('utf-16')
        elif data_type == 'utf-16le':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode('utf-16le')
        elif data_type == 'utf-16be':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode('utf-16be')
        
    elif isinstance(data, str):
        # Handle string data
        return data
    return None

def decode_timestamp(data):
    """
    This function is used to decode timestamp. The timestamp is formatted as series of 13 bytes defined in DSP0240 specification.
        Parameters:
            data: Extracted firmware data for PackageReleaseDateTime
    """
    utc_time_resolution = data[12]               #UTC and Time resolution (1 byte)
    year = int.from_bytes(data[10:12], 'little') #year(2 bytes)
    month = data[9]                              #the month (1 byte)
    day = data[8]                                #day(1 byte)
    hour = data[7]                               #hour(1 byte)
    minute = data[6]                             #minute(1 byte)
    second = data[5]                             #the second (1 byte)
    microsecond = int.from_bytes(data[2:5], 'little')# the microsecond (3 bytes)
    utc_offset = int.from_bytes(data[:2], 'little', signed=True) # the UTC offset (2 bytes)
    dt = datetime(year, month, day, hour, minute, second, microsecond)
    utc_offset_str = str(utc_offset).zfill(4)
    return dt.strftime("%Y-%m-%d %H:%M:%S:%f")+" +"+ utc_offset_str

def process(firmware_data, output_dict, field_name, data_length, data_type):
    """
    This function extracts the bytes of length "data_length" and pass the extracted bytes to parse field for decoding and removes 
    them form the firmware data
        Parameters:
            firmware_data: PLDM firmware package
            output_dict: output dicitionary with all the decoded values
            field name :current field
            data_length: length of field extarcted from spec folder
            data_type: data_type of field extracted from spec folder
            folder:output folder
    """
    global checksum_data
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
    # calculating checksum
    if(field_name == "Package Header Checksum"):
        output_dict[field_name] = zlib.crc32(checksum_data) 
    else:
        output_dict[field_name] = parse_field(firmware_data[:data_length], data_type)
    #appending decoded bytes -this will be used to calculate checksum while unpacking
    checksum_data += firmware_data[:data_length] 
    #removing the processed bytes
    firmware_data = firmware_data[data_length:] 
    return firmware_data

def process_decode(firmware_data, output_dict, field_name, data_length, data_type,decode,field_info):
    """
    This function is for fields having special key-decode
        Parameter:
            firmware_data: PLDM firmware package
            output_dict: output dicitionary with all the decoded values
            field name :current field
            data_length: length of field extarcted from spec folder
            data_type: data_type of field extracted from spec folder
            decode: decode spec from json file
            field info: value of the current field
    """
    global checksum_data
    #Length is an integer and names associated with the extracted value is stored in decode key
    if isinstance(field_info["length"],int):
        output_dict[field_name] = parse_field(firmware_data[:data_length], data_type)
        value = output_dict[field_name]
        output_dict[field_name] = decode[value]
        checksum_data +=firmware_data[:data_length]
    # For AdditionalDescriptorType having AdditionalDescriptorType as Vendor Defined and indirect data length
    elif("Vendor Defined" in decode):
        if(output_dict["AdditionalDescriptorType"] == "Vendor Defined"):
            data_length = output_dict[data_length]
            firmware_data_vendor = firmware_data[:data_length]
            firmware_data_dump=search(firmware_data_vendor,decode["Vendor Defined"],output_dict)
        else:
            #For AdditionalDescriptorType having indirect data length
            data_length = output_dict[data_length]
            output_dict[field_name] = parse_field(firmware_data[:data_length], data_type)
            checksum_data +=firmware_data[:data_length]
    else: 
        #data_type and data_length are indirect 
        data_length = output_dict[data_length]
        data_type_no = output_dict[data_type]
        data_type = decode[str(data_type_no)]
        output_dict[field_name] = parse_field(firmware_data[:data_length], data_type)
        #process data added to checksum_data
        checksum_data +=firmware_data[:data_length]
    #processed bytes are removed and firmware data is updated
    firmware_data = firmware_data[data_length:]
    return firmware_data

def process_count(firmware_data, output_dict, field_name, input_json_data, count_field):
    """
    This function is for the fields having multiple instances in firmware data and having same spec
    Parameters:
        firmware_data: PLDM firmware package
        output_dict: output dicitionary with all the decoded values
        field name :current field
        input_json_data:input json for that specific field
        count_field: value of count field
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
        #count field is direct
        count = count_field
    
    #keep a copy of input json file before passing to the search function
    input_json_data_copy = input_json_data.copy()
    #removing count or it will go into infinite loop
    input_json_data_copy.pop("count")
    
    #Elements will always be a list. Initialize array.
    output_dict[field_name] = []
    #Check if there are elements in the spec before count - these should not be repeated. 
    #But together they will be treated as one element
    if count_index!=0:
        input_json_data_precount={}
        for i in range(count_index):
            input_json_data_precount[list(input_json_data_copy)[0]]=input_json_data_copy[list(input_json_data_copy)[0]]
            input_json_data_copy.pop(list(input_json_data_copy)[0])
        output_dict[field_name].append({})
        firmware_data = search(firmware_data, input_json_data_precount, output_dict[field_name][0])
        #Update count_index for the array of repeated entries
        count_index=1
    #for fields having multiple instances in firmware data
    for i in range(count_index, count):
        output_dict[field_name].append({})
        firmware_data = search(firmware_data, input_json_data_copy, output_dict[field_name][i])
    return firmware_data

def search(firmware_data, input_json_data, output_dict):
    """
    It is a recursive function used to get the keys inside the innermost dictionary of spec json
    Parameters:
        firmware_data: PLDM firmware package
        input_json_data:input json for that specific field
        output_dict: output dicitionary with all the decoded values
        folder: output folder 
    """
    global info
    for field_name, field_info in input_json_data.items():
        if isinstance(field_info, dict):
            output_dict[field_name] = {}
            #if fields having additional key decode in them
            if "decode" in field_info:#with decode
                if(field_info["length"]=="ComponentBitmapBitLength"):
                    #a special case for applicable components field
                    data_length = int(info["ComponentBitmapBitLength"]/8)
                    firmware_data = process_decode(firmware_data, output_dict,field_name, data_length, field_info["data_type"],field_info["decode"],field_info)
                else:
                    firmware_data = process_decode(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"],field_info["decode"],field_info)
                continue
            #if length is present, it means we have reached the innermost level
            elif "length" in field_info:
                if(field_info["length"]=="ComponentBitmapBitLength"):
                    data_length = int(info["ComponentBitmapBitLength"]/8)
                    firmware_data = process(firmware_data, output_dict,field_name, data_length, field_info["data_type"])
                else:
                    firmware_data = process(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"])
            #for keys having additional key count in them
            elif "count" in field_info:
                firmware_data=process_count(firmware_data,output_dict,field_name,field_info,field_info["count"])
                continue
            #none of the conditons were true-recursive call
            else:
                firmware_data = search(firmware_data, field_info,output_dict[field_name])
            #for applicable component field as value of length is present in another field which is present in another level of the dictionary
            if(field_name == "PackageVersionString"):
                info = output_dict
    return firmware_data


def image_extraction(firmware_data_new,image_json,folder):
    """
    This function extracts the images from the firmware package and creates bin files using identifier and version as the file name
        Parameters:
            firmware_data_new  = firmware data
            image_json: image dictionary from spec
            folder:output folder
    """
    count = image_json["ComponentImageCount"]
    for i in range(count):
        file_name_version = image_json['ComponentImageInformation'][i]['ComponentVersionString']
        file_name_identifier = image_json['ComponentImageInformation'][i]['ComponentIdentifier']
        file_name = str(file_name_identifier)+"_"+str(file_name_version) + "_image.bin"
        #from the output file extracting the index from where the image starts
        image_start = image_json['ComponentImageInformation'][i]['ComponentLocationOffset']
        #from the output file extracting the index where the image ends
        image_end = image_start+image_json['ComponentImageInformation'][i]['ComponentSize']
        image_data = firmware_data_new[image_start:image_end]
        file_name_path = folder/file_name
        with open(file_name_path,'wb') as f:
            f.write(image_data)
    #extracting the sign key and creting a bin file for it
    lastImage = count-1
    start = image_json['ComponentImageInformation'][lastImage]['ComponentLocationOffset'] + image_json['ComponentImageInformation'][lastImage]['ComponentSize']
    end = sys.getsizeof(firmware_data_new)
    remaining_data = firmware_data_new[start:end]
    with open(folder/"remaining_firmwareData.bin",'wb') as f:
        f.write(remaining_data)

def main(file_path,output):
    file = Path(file_path)
    #name of main folder
    output_folder = (file.parent)
    if(output != None):
        output=Path(output)
    #this is for handling error injection folder problem
    folder = output or output_folder
    # create the output folder if it does not exist
    if not os.path.exists(folder):
        os.mkdir(folder)
    json_file_path = "spec/pldm_spec.json"
    
    # For header extraction
    with open(json_file_path, 'r') as json_file:
        json_data = json.load(json_file)
    with open(file_path, 'rb') as firmware_file:
        firmware_data = firmware_file.read()

    output_dict = {}
    firmware_data=search(firmware_data, json_data, output_dict)

    # make unpack folder
    new_path = folder / "unpack"
    new_path.mkdir()

    output_json = new_path/"header.json" #unpack folder inside worspace 
    with open(output_json, "w") as file:
        json.dump(output_dict, file, indent=4)

    # For image extraction
    with open(file_path, 'rb') as firmware_file:
        firmware_data_new = firmware_file.read()

    with open(output_json, 'r') as f:
        output_dict_data = json.load(f)

    image_json = output_dict_data["ComponentImageInformationArea"]
    firmware_data_new = image_extraction(firmware_data_new,image_json,new_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    #take fwpkg file name along with folder from the user
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path")
    #take the output folder name in which the unpaked data will be stored
    parser.add_argument("-E", "--output", required=False, help="output folder")#for error injection
    args = parser.parse_args()
    file_path = args.fwpkg_file_path
    main(file_path,args.output)

    

    