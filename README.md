## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.


# PLDM Firmware Packager

This tool provides provides means to unpack a PLDM bundle image into the respective component image (bin) files and the PLDM header file.
The tool can also repack the components and the PLDM header file into a PLDM bundle file.
In addition the tool supports corrupting the components and header images prior to packaging them into a PLDM bundle file.

The pldm_spec.json file acts as the spec reference. Any changes in spec will need this file to be respectively changed. 

The code is sensitive to the following rules
	i) Every field has a "length" and "data_type" attribute that the code looks for. 
	ii) You could have a repeated section by using the "count" field - means that the bytstream has to be repeat-decoded for everything underneath the "count" attribute (if found).  
	iii) The "count" and "length" fields can be indirect references of other fields or a calculation/expression of two fields with an operator inbetween. 
	iv) The "data type" decode types are limited - check for supported data types - UUID, hex-le, hex-be, int, string, timestamp, ASCII, utf-8, utf-16, utf-16le and utf-16be.
	v) The "data type" could also have a variable decode, in which case the "decode" field needs to be added.  

Refer the pldm_spec.json file for examples of these rules. 

To build an executable using PyInstaller, run the below command line. 
```bash
python -m pip install PyInstaller
python -m PyInstaller --add-data "spec/pldm_spec.json;spec" --collect-submodules python --collect-submodules spec --collect-submodules invoker invoker/pldm.py
```
And then use the pldm.exe under dist/pldm folder to use the tool in the below ways. Alternatively you can replace pldm.exe with "python invoker/pldm.py" and run with the same options

## Getting Started with the executable

1. To unpack a firmware bundle (.fwpkg file)
	Copy the fwpkg file to any workspace folder and run
	```bash
	pldm.exe -F workspace\<name of bundle file>.fwpkg -N unpack
	# or
	python invoker/pldm.py -F workspace\<name of bundle file>.fwpkg -N unpack
	```
	If the package is PLDM compliant, this will create an "unpack" folder within the workspace folder and generate  
		i) component image files (as <ComponentIdentifier>_<ComponentVersionString>_image_<count>.bin)
		ii) header.json file (PLDM Header file)

2. To repack a firmware bundle
	Point to the unpack folder which contains the component image files (.bin) and header.json file (populated) and run
	```bash
	pldm.exe -F workspace\unpack -N repack
	# or
	python invoker/pldm.py -F workspace\unpack -N repack
	```
	If the components and header are PLDM compliant, then it would create a "repack" folder, with the PLDM bundle image (repacked_data.fwpkg)

3. To inject error
	Point to the PLDM bundle image or repacked_data.fwpkg to inject error
	```bash
	pldm.exe -F workspace\repack\repacked_data.fwpkg -E descriptor OR 
	pldm.exe -F workspace\repack\repacked_data.fwpkg -E UUID OR
	pldm.exe -F workspace\repack\repacked_data.fwpkg -E image OR 
	pldm.exe -F workspace\repack\repacked_data.fwpkg -E signkey OR 
	pldm.exe -F workspace\repack\repacked_data.fwpkg -E largefile
	```
	In each of the cases above, a new folder gets created inside workspace with the new set of unpacked and repacked fwpkg file.

4. To dump only the header.json file from a fwpkg file
	Point to the PLDM bundle image or repacked_data.fwpkg to dump only the header.json file
	```bash
	pldm.exe -F workspace\repacked_data.fwpkg --dump_header_json
	# or
	python invoker/pldm.py -F workspace\repacked_data.fwpkg --dump_header_json
	```
	This will create a header.json file in the unpack folder.

## TODO
1. Error injection is very component specific (like a specific component can have its UUID corrupted). Need to make this random instead.

