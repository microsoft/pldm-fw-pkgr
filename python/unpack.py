import json 
from datetime import datetime
import binascii
import operator
import sys
import zlib
import argparse
import os
from pathlib import Path
from functools import reduce

#to store the output of PackageHeaderInformation
#will be used to extract the length of ApplicableComponents stored in ComponentBitmapBitLength
info = {} 

#decoded data bytes will be stored here to calculate checksum
header_checksum_data = b""

CRC_Match = False

def parse_field(data, data_type):
    """
    This function decodes the data to more readable form depending upon the data type
        Parameters:
            data: Extracted firmware data for a particular field 
            data_type: data types(hex,int,ASCII)
    """
    if isinstance(data, bytes):
        if data_type == 'hex-le':
            value = hex(int.from_bytes(data, byteorder='little')) if data else ''
            return value
        elif data_type == 'UUID':
            value = hex(int.from_bytes(data, byteorder='big'))
            return value
        elif data_type == 'hex-be':
            value = hex(int.from_bytes(data, byteorder='big'))
            return value
        elif data_type == 'int':
            return int.from_bytes(data, byteorder='little')
        elif data_type == 'string':
            return data.decode()
        elif data_type == 'timestamp':
            return decode_timestamp(data)
        elif data_type == 'ASCII':
            data = data.hex()
            bytes_obj = binascii.unhexlify(data)
            return bytes_obj.decode()
        elif data_type == 'UTF8':
            return data.decode('utf-8')
        elif data_type == 'UTF16':
            return data.decode('utf-16')
        elif data_type == 'UTF16LE':
            return data.decode('utf-16le')
        elif data_type == 'UTF16BE':
            return data.decode('utf-16be')
        
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
    #Determine sign and format UTC offset
    sign = '+' if utc_offset >= 0 else '-'
    utc_offset_str = str(abs(utc_offset)).zfill(4)
    
    resolution_str = f"0x{utc_time_resolution:02x}"
    return dt.strftime("%Y-%m-%d %H:%M:%S:%f") + f" {sign}{utc_offset_str} ({resolution_str})"

def process(firmware_data, output_dict, field_name, data_length, data_type, offset):
    """
    This function extracts the bytes of length "data_length" and pass the extracted bytes to parse field for decoding and removes 
    them form the firmware data
        Parameters:
            firmware_data: PLDM firmware package
            output_dict: output dictionary with all the decoded values
            field name :current field
            data_length: length of field extracted from spec folder
            data_type: data_type of field extracted from spec folder
            folder:output folder
    """
    global header_checksum_data
    global CRC_Match
    operators = ["+", "-", "*", "/"]
    functions = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
    #When the length field has +,-,/,*
    if isinstance(data_length, str):
        for op in operators:
            if op in data_length:
                parts = data_length.split(op)
                converted_parts = [int(part) if part.isdigit() else output_dict[part] for part in parts]
                data_length = reduce(functions[op], converted_parts)
                break
        else:
            data_length = output_dict[data_length]
    # calculating checksum
    if(field_name == "PackageHeaderChecksum"):
        print("Unpacked Header Checksum = ",parse_field(firmware_data[offset:offset + data_length], data_type))
        output_dict[field_name] = zlib.crc32(header_checksum_data)
        print("Calculated Header Checksum =",output_dict[field_name])
        if parse_field(firmware_data[offset:offset + data_length], data_type) == output_dict[field_name]:
            CRC_Match = True
        else:
            CRC_Match = False
    else:
        output_dict[field_name] = parse_field(firmware_data[offset:offset + data_length], data_type if not data_type in output_dict else output_dict[data_type])

    #appending decoded bytes -this will be used to calculate checksum while unpacking
    header_checksum_data += firmware_data[offset: offset + data_length]
    offset = offset + data_length
    return offset

def process_decode(firmware_data, output_dict, field_name, data_length, data_type,decode,field_info, offset):
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
    global header_checksum_data
    #Length is an integer and names associated with the extracted value is stored in decode key
    if isinstance(field_info["length"],int):
        output_dict[field_name] = parse_field(firmware_data[offset:offset + data_length], data_type)
        value = output_dict[field_name]
        output_dict[field_name] = next(
            (v for k, v in decode.items() if int(value, 16) == int(k, 16)),
            None
        )
        # output_dict[field_name] = decode[str(value)] if str(value) in decode else decode[value]
        header_checksum_data +=firmware_data[offset:offset + data_length]
        offset = offset + data_length
    # For AdditionalDescriptorType having AdditionalDescriptorType as Vendor Defined and indirect data length
    elif("Vendor Defined" in decode):
        if(output_dict["AdditionalDescriptorType"] == "Vendor Defined"):
            data_length = output_dict[data_length]
            firmware_data_vendor = firmware_data[offset:offset + data_length]
            _=search(firmware_data_vendor,decode["Vendor Defined"],output_dict, 0)
            offset += data_length
        else:
            #For AdditionalDescriptorType having indirect data length
            data_length = output_dict[data_length]
            output_dict[field_name] = parse_field(firmware_data[offset:offset + data_length], data_type)
            # if data_type == "hex-le" and output_value:    
            #     output_value = int(output_value, 16)
            #     output_value = hex(output_value)
            # output_dict[field_name] = output_value
            header_checksum_data +=firmware_data[offset:offset + data_length]
            offset += data_length
    else:
        #data_type and data_length are indirect and the decode section doesn't have vendor defined section
        data_length = output_dict[data_length]
        data_type_no = output_dict[data_type]
        data_type = decode[str(data_type_no)]
        output_dict[field_name] = parse_field(firmware_data[offset:offset + data_length], data_type)
        #process data added to header_checksum_data
        header_checksum_data +=firmware_data[offset:offset + data_length]
        offset += data_length
    return offset

def process_count(firmware_data, output_dict, field_name, input_json_data, count_field, offset):
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
        offset = search(firmware_data, input_json_data_precount, output_dict[field_name][0], offset)
        #Update count_index for the array of repeated entries
        count_index=1
    #for fields having multiple instances in firmware data
    for i in range(count_index, count):
        output_dict[field_name].append({})
        offset = search(firmware_data, input_json_data_copy, output_dict[field_name][i], offset)
    if output_dict[field_name] == []:
        output_dict.pop(field_name)
    return offset

def search(firmware_data, input_json_data, output_dict, offset):
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
                    offset = process_decode(firmware_data, output_dict,field_name, data_length, field_info["data_type"],field_info["decode"],field_info, offset)
                else:
                    offset = process_decode(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"],field_info["decode"],field_info, offset)
            #if length is present, it means we have reached the innermost level
            elif "length" in field_info:
                if(field_info["length"]=="ComponentBitmapBitLength"):
                    data_length = int(info["ComponentBitmapBitLength"]/8)
                    offset = process(firmware_data, output_dict,field_name, data_length, field_info["data_type"], offset)
                else:
                    offset = process(firmware_data, output_dict,field_name, field_info["length"], field_info["data_type"], offset)
            #for keys having additional key count in them
            elif "count" in field_info:
                offset=process_count(firmware_data,output_dict,field_name,field_info,field_info["count"], offset)
            #none of the conditons were true-recursive call
            else:
                offset = search(firmware_data, field_info,output_dict[field_name], offset)
            #for applicable component field as value of length is present in another field which is present in another level of the dictionary
            if(field_name == "PackageVersionString"):
                info = output_dict
    return offset

def image_extraction(firmware_data,image_json,folder, dump_header):
    """
    This function extracts the images from the firmware package and creates bin files using identifier and version as the file name
        Parameters:
            firmware_data_new  = full firmware bundle
            image_json: image dictionary from spec
            folder: output folder
            dump_header: flag to indicate whether to dump only header.json or extract images too
    """
    payload_data = b''
    count = image_json["ComponentImageCount"]
    for i in range(count):
        file_name_version = image_json['ComponentImageInformation'][i]['ComponentVersionString']
        file_name_identifier = image_json['ComponentImageInformation'][i]['ComponentIdentifier']
        file_name = file_name_identifier + "_" + file_name_version + "_image_" + str(i) + ".bin"
        #from the output file extracting the index from where the image starts
        image_start = image_json['ComponentImageInformation'][i]['ComponentLocationOffset']
        #from the output file extracting the index where the image ends
        image_end = image_start+image_json['ComponentImageInformation'][i]['ComponentSize']
        image_data = firmware_data[image_start:image_end]
        payload_data+=image_data
        file_name_path = folder/file_name
        if not dump_header:
            with open(file_name_path,'wb') as f:
                f.write(image_data)
    #extracting the sign key and creating a bin file for it
    lastImage = count-1
    start = image_json['ComponentImageInformation'][lastImage]['ComponentLocationOffset'] + image_json['ComponentImageInformation'][lastImage]['ComponentSize']
    end = sys.getsizeof(firmware_data)
    remaining_data = firmware_data[start:end]
    if not dump_header:
        with open(folder/"remaining_firmwareData.bin",'wb') as f:
            f.write(remaining_data)
    return payload_data
        
def main(file_path,output,spec_path, dump_header):
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
        
    spec_path += ".json"
    spec_json_file_path = os.path.join("spec",spec_path)
    
    # For header extraction
    with open(spec_json_file_path, 'r') as json_file:
        spec_data = json.load(json_file)
    with open(file_path, 'rb') as firmware_file:
        firmware_data = firmware_file.read()
    output_dict = {}
    offset = 0
    firmware_data=search(firmware_data, spec_data, output_dict, offset)

    # make unpack folder
    new_path = folder / "unpack"
    
    if new_path.exists():
        # Find the highest backup number
        backup_number = 1
        while (folder / f"unpack_backup_{backup_number}").exists():
            backup_number += 1

        # Rename existing unpack folder
        new_path.rename(folder / f"unpack_backup_{backup_number}")
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
    
    payload_data = image_extraction(firmware_data_new,image_json,new_path, dump_header)
    if "PLDMFWPackagePayloadChecksum" in spec_data:
        payload_checksum = zlib.crc32(payload_data)
        print("Unpacked Payload Checksum = ", output_dict["PLDMFWPackagePayloadChecksum"])
        print("Calculated Payload Checksum = ", payload_checksum)
        if output_dict["PLDMFWPackagePayloadChecksum"] == payload_checksum:
            payload_crc_match = True
        else:
            payload_crc_match = False
    return CRC_Match and payload_crc_match if "PLDMFWPackagePayloadChecksum" in spec_data else CRC_Match

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    #take fwpkg file name along with folder from the user
    parser.add_argument("-F", "--fwpkg-file-path", help="Name of the PLDM FW update package", dest="fwpkg_file_path", required=True)
    #take the spec version 
    parser.add_argument("-S", "--spec-path", help="Version of the PLDM FW update Spec", dest="spec_path", choices=["pldm_spec_1.0.0","pldm_spec_1.1.0","pldm_spec_1.2.0","pldm_spec_1.3.0"], default="pldm_spec_1.0.0")
    #take the output folder name in which the unpaked data will be stored
    parser.add_argument("-E", "--output", required=False, help="output folder")#for error injection
    # Return only header.json file as output
    parser.add_argument("-D", "--dump_header_json", help="Dump Header.json from bundle", dest="dump_header_json", action="store_true", required=False)
    # take the output path in which unpacked data/header.json file will be stored
    # parser.add_argument("-O", "--output", help="Provide directory path for storing output data", dest="output", required=False)
    args = parser.parse_args()
    file_path = args.fwpkg_file_path
    spec_path = args.spec_path
    dump_header = args.dump_header_json
    output_dir = args.output
    if main(file_path, output_dir, spec_path, dump_header):
        print("Unpack was successful. CRC matches! Package is PLDM compliant.")
    else:
        print("Unpack completed. CRC mismatch detected! Package is NOT PLDM compliant.")
    

    