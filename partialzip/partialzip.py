#!/usr/bin/env python

import argparse
import cStringIO
import os
import urllib2
import struct
import sys
import zlib


DEBUG = False

# taken from the standard library

# The "end of central directory" structure, magic number, size, and indices
# (section V.I in the format document)
structEndArchive = "<4s4H2LH"
stringEndArchive = "PK\005\006"
sizeEndCentDir = struct.calcsize(structEndArchive)

_ECD_SIGNATURE = 0
_ECD_DISK_NUMBER = 1
_ECD_DISK_START = 2
_ECD_ENTRIES_THIS_DISK = 3
_ECD_ENTRIES_TOTAL = 4
_ECD_SIZE = 5
_ECD_OFFSET = 6
_ECD_COMMENT_SIZE = 7

_ECD_COMMENT = 8
_ECD_LOCATION = 9

# The "central directory" structure, magic number, size, and indices
# of entries in the structure (section V.F in the format document)
structCentralDir = "<4s4B4HL2L5H2L"
stringCentralDir = "PK\001\002"
sizeCentralDir = struct.calcsize(structCentralDir)

# indexes of entries in the central directory structure
_CD_SIGNATURE = 0
_CD_CREATE_VERSION = 1
_CD_CREATE_SYSTEM = 2
_CD_EXTRACT_VERSION = 3
_CD_EXTRACT_SYSTEM = 4
_CD_FLAG_BITS = 5
_CD_COMPRESS_TYPE = 6
_CD_TIME = 7
_CD_DATE = 8
_CD_CRC = 9
_CD_COMPRESSED_SIZE = 10
_CD_UNCOMPRESSED_SIZE = 11
_CD_FILENAME_LENGTH = 12
_CD_EXTRA_FIELD_LENGTH = 13
_CD_COMMENT_LENGTH = 14
_CD_DISK_NUMBER_START = 15
_CD_INTERNAL_FILE_ATTRIBUTES = 16
_CD_EXTERNAL_FILE_ATTRIBUTES = 17
_CD_LOCAL_HEADER_OFFSET = 18

# The "local file header" structure, magic number, size, and indices
# (section V.A in the format document)
structFileHeader = "<4s2B4HL2L2H"
stringFileHeader = "PK\003\004"
sizeFileHeader = struct.calcsize(structFileHeader)

_FH_SIGNATURE = 0
_FH_EXTRACT_VERSION = 1
_FH_EXTRACT_SYSTEM = 2
_FH_GENERAL_PURPOSE_FLAG_BITS = 3
_FH_COMPRESSION_METHOD = 4
_FH_LAST_MOD_TIME = 5
_FH_LAST_MOD_DATE = 6
_FH_CRC = 7
_FH_COMPRESSED_SIZE = 8
_FH_UNCOMPRESSED_SIZE = 9
_FH_FILENAME_LENGTH = 10
_FH_EXTRA_FIELD_LENGTH = 11

# constants for Zip file compression methods
ZIP_STORED = 0
ZIP_DEFLATED = 8


class ZipInfo(object):
    def __init__(self, filename="NoName", date_time=(1980, 1, 1, 0, 0, 0)):
        self.orig_filename = filename  # Original file name in archive

        # Terminate the file name at the first null byte.  Null bytes in file
        # names are used as tricks by viruses in archives.
        null_byte = filename.find(chr(0))
        if null_byte >= 0:
            filename = filename[0:null_byte]
        # This is used to ensure paths in generated ZIP files always use
        # forward slashes as the directory separator, as required by the
        # ZIP format specification.
        if os.sep != "/" and os.sep in filename:
            filename = filename.replace(os.sep, "/")

        self.filename = filename  # Normalized file name
        self.date_time = date_time  # year, month, day, hour, min, sec

        if date_time[0] < 1980:
            raise ValueError('ZIP does not support timestamps before 1980')

        # Standard values:
        self.compress_type = ZIP_STORED  # Type of compression for the file
        self.comment = ""  # Comment for each file
        self.extra = ""  # ZIP extra data
        if sys.platform == 'win32':
            self.create_system = 0  # System which created ZIP archive
        else:
            # Assume everything else is unix-y
            self.create_system = 3  # System which created ZIP archive
        self.create_version = 20  # Version which created ZIP archive
        self.extract_version = 20  # Version needed to extract archive
        self.reserved = 0  # Must be zero
        self.flag_bits = 0  # ZIP flag bits
        self.volume = 0  # Volume number of file header
        self.internal_attr = 0  # Internal attributes
        self.external_attr = 0  # External file attributes

    # Other attributes are set by class ZipFile:
    # header_offset         Byte offset to the file header
    # CRC                   CRC-32 of the uncompressed file
    # compress_size         Size of the compressed file
    # file_size             Size of the uncompressed file

    def _decodeFilename(self):
        if self.flag_bits & 0x800:
            return self.filename.decode('utf-8')
        else:
            return self.filename

def get_data( file_url, start, end=0):
    byte_range = "bytes=%d-%d" % (start, end) if end else "bytes=%d-" % (start,)
    headers = {"Range": byte_range}
    req = urllib2.Request(file_url, headers=headers)
    response = urllib2.urlopen(req)

    return response.read()

def get_filesize_url(url):
    req = urllib2.Request(url)
    response = urllib2.urlopen(req)
    return response.headers.getheader('content-length')

def get_end_record_data(url, total_file_size):
    if DEBUG:
        print "[*] size of the cd:", sizeEndCentDir
    cd_data = get_data(url, total_file_size - sizeEndCentDir)

    if DEBUG:
        print "[*] size of the cd data:", len(cd_data)
        hexdump(cd_data)

    # directly taken from the python standard library ZipFile class of zipfile module line 219 - 228
    if len(cd_data) == sizeEndCentDir and cd_data[0:4] == stringEndArchive and cd_data[-2:] == b"\000\000":
        # the signature is correct and there's no comment, unpack structure
        endrec = struct.unpack(structEndArchive, cd_data)
        endrec = list(endrec)

        # Append a blank comment and record start offset
        endrec.append("")
        endrec.append(total_file_size - sizeEndCentDir)

        if DEBUG:
            print "[*] end record data ", endrec

        return endrec

def get_central_directory(url, size, offset):
    cd = get_data(url, offset, offset + size - 1)  # offset point to the first byte ...

    if DEBUG:
        print "[*] size of the central directory:", len(cd)
    # hexdump(cd)

    return cd

# directly taken from the python standard library ZipFile class
def parse_central_directory(data):
    size_cd = len(data)
    fp = cStringIO.StringIO(data)
    total = 0
    filelist = []
    NameToInfo = {}
    while total < size_cd:
        centdir = fp.read(sizeCentralDir)

        if len(centdir) != sizeCentralDir:
            raise Exception("Truncated central directory")

        centdir = struct.unpack(structCentralDir, centdir)
        if centdir[_CD_SIGNATURE] != stringCentralDir:
            raise Exception("Bad magic number for central directory")

        filename = fp.read(centdir[_CD_FILENAME_LENGTH])

        # print "[**]", filename

        # Create ZipInfo instance to store file information
        x = ZipInfo(filename)
        x.extra = fp.read(centdir[_CD_EXTRA_FIELD_LENGTH])
        x.comment = fp.read(centdir[_CD_COMMENT_LENGTH])
        x.header_offset = centdir[_CD_LOCAL_HEADER_OFFSET]
        (x.create_version, x.create_system, x.extract_version, x.reserved,
         x.flag_bits, x.compress_type, t, d,
         x.CRC, x.compress_size, x.file_size) = centdir[1:12]
        x.volume, x.internal_attr, x.external_attr = centdir[15:18]
        # Convert date/time code to (year, month, day, hour, min, sec)
        x._raw_time = t
        x.date_time = ((d >> 9) + 1980, (d >> 5) & 0xF, d & 0x1F, t >> 11, (t >> 5) & 0x3F, (t & 0x1F) * 2)

        # x._decodeExtra()
        x.header_offset = x.header_offset + 0  # concat
        x.filename = x._decodeFilename()
        # print "[*]", x.filename , "offset >>" , x.header_offset
        filelist.append(x)
        NameToInfo[x.filename] = x

        # update total bytes read from central directory
        total = (total + sizeCentralDir + centdir[_CD_FILENAME_LENGTH]
                 + centdir[_CD_EXTRA_FIELD_LENGTH]
                 + centdir[_CD_COMMENT_LENGTH])
    return filelist

def get_file_from_zip(url, zipinfo):
    if DEBUG:
        print "sizeFileHeader", sizeFileHeader, zipinfo.compress_type
        print "fetching ", (sizeFileHeader + zipinfo.compress_size - 1)
    
    # get the header
    data = get_data(url, zipinfo.header_offset, zipinfo.header_offset + sizeFileHeader - 1)
    fheader = struct.unpack(structFileHeader, data)

    data = get_data(url, zipinfo.header_offset + sizeFileHeader,
                    zipinfo.header_offset + sizeFileHeader + fheader[_FH_FILENAME_LENGTH] + fheader[
                        _FH_EXTRA_FIELD_LENGTH] + zipinfo.compress_size - 1)
    # hexdump(data)
    fp = cStringIO.StringIO(data)

    if fheader[_FH_EXTRA_FIELD_LENGTH]:
        fp.read(fheader[_FH_EXTRA_FIELD_LENGTH])

    header_bytes = zipinfo.compress_size - zipinfo.file_size
    plist_data = None
    if zipinfo.compress_type == ZIP_STORED:
        if DEBUG:
            print "[*] header bytes", header_bytes
            
        fp.read(header_bytes)
        plist_data = fp.read(zipinfo.file_size)
        hexdump(plist_data)
        
        if len(plist_data) != zipinfo.file_size:
            return None
        
        if DEBUG:
            print "read", len(plist_data)

    elif zipinfo.compress_type == ZIP_DEFLATED:
        decompressor = zlib.decompressobj(-15)
        return decompressor.decompress(fp.read(), zipinfo.file_size)

    return plist_data

def readable_size(size):
    size = float(size)
    for size_name in ["bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]:
        if size < 1024.0:
            return "%.2f %s" % (size, size_name)
        size = size / 1024.0

    return "%.2f %s" % (size, "humngus!!")

# this is a pretty hex dumping function directly taken from
# http://code.activestate.com/recipes/142812-hex-dumper/
def hexdump(src, length=16):
    result = []
    digits = 4 if isinstance(src, unicode) else 2

    for i in xrange(0, len(src), length):
        s = src[i:i + length]
        hexa = b' '.join(["%0*X" % (digits, ord(x)) for x in s])
        text = b''.join([x if 0x20 <= ord(x) < 0x7F else b'.' for x in s])
        result.append(b"%04X   %-*s   %s" % (i, length * (digits + 1), hexa, text))

    print b'\n'.join(result)

def save_zip_to_file(url , zipinfo , save_path):
    with open(save_path, 'wb') as fout:
        data = get_file_from_zip(url , zipinfo)
        fout.write(data)


def print_files(file_list, pretty=False):
    if not pretty:
        for x in file_list:
            if x.flag_bits == 0x8:
                print "[*] File:", x.filename , "compressed size:", readable_size(x.compress_size), "actual size:", readable_size(x.file_size)
            elif x.flag_bits == 0:
                print "[*] Directory:", x.filename
            else:
                print "[!] Unknown type", x.filename
    else:
        print "[:(] not implemented yet!"


def main(url):
    print "[*] Collecting Information about zip."
    total_file_size = int(get_filesize_url(url))
    print "[*] total file size:", readable_size(total_file_size)

    endrec = get_end_record_data(url, total_file_size)

    size_cd = endrec[_ECD_SIZE]  # bytes in central directory
    offset_cd = endrec[_ECD_OFFSET]  # offset of central directory

    if DEBUG:
        print "[*] size of the central directory ", readable_size(size_cd), "offset", readable_size(offset_cd)

    central_directory = get_central_directory(url, size_cd, offset_cd)
    concat = endrec[_ECD_LOCATION] - size_cd - offset_cd
    file_list = parse_central_directory(central_directory)


    print_files(file_list)
    # for x in file_list:
    #     print "flag bits",x.flag_bits
    #     print "compress type:",x.compress_type
    #     print "[***] file found", x.filename, "header offset:", x.header_offset, "compressed size:", readable_size(x.compress_size), "file size:", readable_size(x.file_size)
    #     # data = get_file_from_zip(url, x)
    #     if x.filename == "kernelcache.release.n42":
    #         save_zip_to_file(url , x , "/Users/better/Desktop/kernelcache.release.n42")

        # data = get_data(url , x.header_offset , 128)
        # hexdump(data)

def main_2():
    pass



if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "http://appldnld.apple.com/ios9.2/031-29213-20151203-67549F46-8D8A-11E5-96EE-63618B8BECEB/iPhone5,2_9.2_13C75_Restore.ipsw"

    main(url)
