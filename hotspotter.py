from PIL import Image, ImageDraw
from typing import List
from os import getcwd, walk, listdir, remove
from os.path import join
from bitstring import ConstBitStream, BitStream
from subprocess import run
import numpy as np

LZS_COMPRESS = join("..","lzs-compression","c","src","utils","lzs-compress")
#LEFT_EXIT = rect((0,0), (20,143))
#RIGHT_EXIT = rect((244,0), (264,143))

def rect(ul: tuple[int], lr: tuple[int]) -> List[tuple]:
    return [ul, (ul[0],lr[1]), lr, (lr[0],ul[1])]

def parse_instance(lines: List[str]) -> list:
    #hacky way of determining predefined exitfeature instances is by name
    #TODO: implement proper checking of param earlier in script
    if any(name in lines[0] for name in
             ['efExitRight', 'efExitTurn180']:
        nsLeft = 244
        nsTop = 0
        nsRight = 264
        nsBottom = 143
    elif any(name in lines[0] for name in
             ['efExitLeft','efTurnAround','efExitUTurnLeft','efExitDrawer']):
        nsLeft = 0
        nsTop = 0
        nsRight = 20
        nsBottom = 143
    #now that defaults are loaded, time to parse the lines
    #TODO: figure out how to refactor this code
    # so it doesn't look like this
    for line in lines:
        if 'nsLeft' in line:
            nsLeft = int(line.split(' ')[-1])
        elif 'nsTop' in line:
            nsTop = int(line.split(' ')[-1])
        elif 'nsRight' in line:
            nsRight = int(line.split(' ')[-1])
        elif 'nsBottom' in line:
            nsBottom = int(line.split(' ')[-1])
        elif 'createPoly' in line:
            point_string = line.split(':')[-1].replace(')','')
                                            .lstrip().rstrip()
            point_ints = [int(a) for a in point_string.split(' ')]
            poly = [(point_ints[i],point_ints[i+1])
                    for i in range(0,len(point_ints)-2,2)]
            return poly
    return rect((nsLeft, nsTop), (nsRight, nsBottom))

def get_hotspots(script: str) -> list:
    polys = list()
    lines = script.split('\n')
    #parse each instance - outside of exitfeatures, currently irrelevant
    for i, line in enumerate(lines):
        if '(instance' in line and 'ExitFeature' in line and 'UNUSED' not in line:
            eoi = i
            while (lines[eoi] or lines[eoi-1] != ')'):
                eoi += 1
            polys.append(parse_instance(lines[i:eoi]))
        
    return polys

def get_image_data(data: str, as_matrix: bool = False) -> list:
    HEADER_LENGTHS = 0x48
    offset = int.from_bytes(data[0x3e:0x40],'little')
    width  = int.from_bytes(data[0x12:0x14],'little')
    height = int.from_bytes(data[0x14:0x16],'little')
    img = data[offset+HEADER_LENGTHS:]
    if as_matrix:
        img = [list(img[i:i+width]) for i in range(0,len(img),width)]
    return img

def draw_hotspots(image : Image, polys : list) -> Image:
    draw = ImageDraw.Draw(image)
    for poly in polys:
        # scale to the size of the image
        POLY_SCALE = (264, 143)
        sf = [a / b for a, b in zip(image.size, POLY_SCALE)]
        scaled_poly = [(int(p[0]*sf[0]),int(p[1]*sf[1])) for p in poly]
        # going to stick with color 182 (lime green)
        draw.polygon(scaled_poly,None,0xB6,3)
    return image

def process_script(filename: str) -> None:
    with open(filename,'r') as f:
        script = f.read()
           
    #step 1: read in the script and determine which p56 to read in
    resources = list()
    for line in script.split('\n'):
        if 'picture' in line:
            resource = int(line.split(' ')[-1].replace(')',''))
            resources.append(resource)
    if not resources:
        print(f"Failed to find picture information in script {filename}")
        return
           
    #step 2: get the hotspots
    hotspots = get_hotspots(script)
           
    #for each resource
    for resource in resources:
        #step 3: get the image data
        try:
            with open(join(getcwd(),"p56s",f"{resource}.p56"),'rb') as f:
                p56 = f.read()
        except Exception as e:
            print(e)
            continue
        data = get_image_data(p56, True)
        #step 4: draw the hotspots
        original_image = Image.fromarray(np.array(data,dtype=np.byte), mode='L')
        drawn_image = draw_hotspots(original_image, hotspots)
        processed_data = bytes(drawn_image.getdata())
        #step 5: write p56s to files
        with open(join(getcwd(),"processed_p56s",f"{resource}.p56"),'wb') as f:
            f.write(p56[:len(p56)-len(processed_data)])
            f.write(processed_data)
    return

def read_map(file: str) -> dict:
    with open(file,'rb') as f:
        mapfile = f.read()
    readable_map = dict()
    seekhead = 0
           
    #first, we need the header
    while True:
        entry = mapfile[seekhead:seekhead+3]
        rtype = entry[0]
        rloc = int.from_bytes(entry[1:3],'little')
        entry_dict = {"location": rloc, "table": list()}
        readable_map[rtype] = entry_dict
        if rtype == 255:
            break
        seekhead += 3
           
    #next, we grab all the entries
    keys = list(readable_map.keys())
    for i, key in enumerate(keys[:-1]):
        seekhead = readable_map[key]["location"]
        while seekhead < readable_map[keys[i+1]]["location"]:
            table_entry = mapfile[seekhead:seekhead+6]
            resource = int.from_bytes(table_entry[:2],'little')
            value = int.from_bytes(table_entry[2:],'little')
            readable_map[key]["table"].append((resource, value))
            seekhead += 6
    return readable_map

def process_all_files()-> None:
    print("processing all files...")
    for subdir, dirs, files in walk(join(".","shivers-win-1.02","src")):
        for file in files:
            if ".sco" not in file and "rm" in file:
                print(file)
                process_script(join(".","shivers-win-1.02","src",file))

def append_new_picture(ressci: bytes, rname: int, rdata: bytes) -> bytes:
    #generate header for data
    header = b''
    header += b'\x01' #picture type
    header += rname.to_bytes(2,'little') #resource name
    header += len(rdata).to_bytes(4,'little') #size post-compression
    header += len(rdata).to_bytes(4,'little') #size pre-compression
    header += b'\x00' #uncompressed type
    assert len(header) == 12
    return ressci + header + rdata

def replace_picture(ressci: bytes, rname: int, raddr: int, file: str) -> bytes:
    header = ressci[raddr:raddr+12]
    compressed_size = int.from_bytes(header[3:7],'little')
           
    #compress the candidate file (with stripped header)
    with open(join(".","processed_p56s", file),'rb') as f:
        data = f.read()[4:]
    with open("candin.tmp",'wb') as f:
        f.write(data)
    run([LZS_COMPRESS,"candin.tmp","candout.tmp"])
    with open("candout.tmp",'rb') as f:
        candout = f.read()
    remove("candin.tmp")
    remove("candout.tmp")
           
    if len(candout) > compressed_size:
        print("Unable to replace: new size is {}, old size is {}, diff = {}"
              .format(len(candout),compressed_size,len(candout)-compressed_size))
        with open("replace.log","a") as f:
            f.write("{}\n".format(rname))
        return ressci
    #otherwise, we can construct the new entry!
    new_header = header[:3] + len(candout).to_bytes(4,'little') + header[7:] + b'\x00'
    new_entry = new_header + candout + b'\x00'*(compressed_size-len(candout))
    return ressci[:raddr] + new_entry + ressci[raddr+len(new_entry):]

def generate_resources_append() -> None:
    with open("RESMAP.000",'rb') as f:
        resmap = bytearray(f.read())
    with open("RESSCI.000",'rb') as f:
        ressci = bytearray(f.read())
           
    file_list = [f for f in listdir(join(".","processed_p56s")) if f.endswith(".p56")]
    #starting at 4375 (this value will not change, since we're only modifying files)
    for entry in range(4375,17689,6):
        #go through each entry, and if the file is in the processed list, append and change address
        resource = int.from_bytes(resmap[entry:entry+2],'little')
        candfile = "{}.p56".format(resource)
        if candfile in file_list:
            print("{} found!".format(candfile))
            address = len(ressci)
            with open(join(".\\processed_p56s",candfile),'rb') as f:
                ressci = append_new_picture(ressci, resource, f.read())
            resmap[entry+2:entry+6] = address.to_bytes(4,'little')
           
    # easy peasy! just write out the files from here
    with open("newRESMAP.000",'wb') as f:
        f.write(resmap)
    with open("newRESSCI.000",'wb') as f:
        f.write(ressci)
    return

def generate_resources_replace() -> None:
    with open("RESMAP.000",'rb') as f:
        resmap = bytearray(f.read())
    with open("RESSCI.000",'rb') as f:
        ressci = bytearray(f.read())
    file_list = [f for f in listdir(join(".","processed_p56s")) if f.endswith(".p56")]
    #starting at 4375 (this value will not change, since we're only modifying files)
    for entry in range(4375,17689,6):
        resource = int.from_bytes(resmap[entry:entry+2],'little')
        address  = int.from_bytes(resmap[entry+2:entry+6],'little')
        candfile = "{}.p56".format(resource)
        if candfile in file_list:
            print("{} found!".format(candfile))
            ressci = replace_picture(ressci, resource, address, candfile)
            #no need to change the resmap
                
    # easy peasy! just write out RESSCI from here
    with open("newRESSCI.000",'wb') as f:
        f.write(ressci)
    return

def unpack_LZS(data : bytes) -> bytes:
    stream = ConstBitStream(data)
    output = b''
    while stream:
        if stream.read('uint:1'): #compressed bytes follow
            #print("#decompressing...")
            if stream.read('uint:1'): #seven bit offset follows
                offset = stream.read('uint:7')
                if not offset:
                    break
            else:
                offset = stream.read('uint:11')
            clen = getCompLen_LZS(stream)
            if not clen:
                #return output
                raise Exception("hey idiot, your clen is 0. seeking at {}".format(stream.bitpos))
            output = copyComp_LZS(output, offset, clen)
            #print("##offset={},clen={}".format(offset,clen))
            #print(output.hex())
        else: #uncompressed byte here
            uncbyte = stream.read('bytes1')
            output += uncbyte
            #print("#literal byte = {}".format(uncbyte))
            #print(output.hex())
    return output


def getCompLen_LZS(stream : ConstBitStream) -> int:
    match stream.read('uint:2'):
        case 0:
            return 2
        case 1:
            return 3
        case 2:
            return 4
        case _:
            match stream.read('uint:2'):
                case 0:
                    return 5
                case 1:
                    return 6
                case 2:
                    return 7
                case _:
                    clen = 8
                    while True:
                        nibble = stream.read('uint:4')
                        clen += nibble
                        if nibble != 0xf:
                            break
                    return clen

def copyComp_LZS(output : bytes, offset : int, clen : int) -> bytes:
    #we go back x bytes in the output
    while clen:
        output += output[len(output)-offset:len(output)-offset+1]
        clen -= 1
        offset += 1
    return output
                
if __name__ == '__main__':
    print("kiss my ass")
