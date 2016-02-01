#!/usr/bin/env python

import cStringIO
import urllib2
import struct
import zlib

import zip_utils

DEBUG = False

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
        print "[*] size of the cd:", zip_utils.sizeEndCentDir
    cd_data = get_data(url, total_file_size - zip_utils.sizeEndCentDir)

    if DEBUG:
        print "[*] size of the cd data:", len(cd_data)
        hexdump(cd_data)

    # directly taken from the python standard library ZipFile class of zipfile module line 219 - 228
    if len(cd_data) == zip_utils.sizeEndCentDir and cd_data[0:4] == zip_utils.stringEndArchive and cd_data[-2:] == b"\000\000":
        # the signature is correct and there's no comment, unpack structure
        endrec = struct.unpack(zip_utils.structEndArchive, cd_data)
        endrec = list(endrec)

        # Append a blank comment and record start offset
        endrec.append("")
        endrec.append(total_file_size - zip_utils.sizeEndCentDir)

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
        centdir = fp.read(zip_utils.sizeCentralDir)

        if len(centdir) != zip_utils.sizeCentralDir:
            raise Exception("Truncated central directory")

        centdir = struct.unpack(zip_utils.structCentralDir, centdir)
        if centdir[zip_utils._CD_SIGNATURE] != zip_utils.stringCentralDir:
            raise Exception("Bad magic number for central directory")

        filename = fp.read(centdir[zip_utils._CD_FILENAME_LENGTH])

        # print "[**]", filename

        # Create ZipInfo instance to store file information
        x = zip_utils.ZipInfo(filename)
        x.extra = fp.read(centdir[zip_utils._CD_EXTRA_FIELD_LENGTH])
        x.comment = fp.read(centdir[zip_utils._CD_COMMENT_LENGTH])
        x.header_offset = centdir[zip_utils._CD_LOCAL_HEADER_OFFSET]
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
        total = (total + zip_utils.sizeCentralDir + centdir[zip_utils._CD_FILENAME_LENGTH]
                 + centdir[zip_utils._CD_EXTRA_FIELD_LENGTH]
                 + centdir[zip_utils._CD_COMMENT_LENGTH])
    return filelist

def get_file_from_zip(url, zipinfo):
    if DEBUG:
        print "sizeFileHeader", zip_utils.sizeFileHeader, zipinfo.compress_type
        print "fetching ", (zip_utils.sizeFileHeader + zipinfo.compress_size - 1)

    # get the header
    data = get_data(url, zipinfo.header_offset, zipinfo.header_offset + zip_utils.sizeFileHeader - 1)
    fheader = struct.unpack(zip_utils.structFileHeader, data)

    data = get_data(url, zipinfo.header_offset + zip_utils.sizeFileHeader,
                    zipinfo.header_offset + zip_utils.sizeFileHeader + fheader[zip_utils._FH_FILENAME_LENGTH] + fheader[
                        zip_utils._FH_EXTRA_FIELD_LENGTH] + zipinfo.compress_size - 1)
    # hexdump(data)
    fp = cStringIO.StringIO(data)

    if fheader[zip_utils._FH_EXTRA_FIELD_LENGTH]:
        fp.read(fheader[zip_utils._FH_EXTRA_FIELD_LENGTH])

    header_bytes = zipinfo.compress_size - zipinfo.file_size
    plist_data = None
    if zipinfo.compress_type == zip_utils.ZIP_STORED:
        if DEBUG:
            print "[*] header bytes", header_bytes

        fp.read(header_bytes)
        plist_data = fp.read(zipinfo.file_size)
        hexdump(plist_data)

        if len(plist_data) != zipinfo.file_size:
            return None

        if DEBUG:
            print "read", len(plist_data)

    elif zipinfo.compress_type == zip_utils.ZIP_DEFLATED:
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


