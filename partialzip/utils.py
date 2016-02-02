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


