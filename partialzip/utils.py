#!/usr/bin/env python

import cStringIO
import math
import urllib2
import struct
import zlib

import zip_utils

DEBUG = False


def get_data(file_url, start, end=0, cb=None, num_cb=0, to_file_path=None):
    byte_range = "bytes=%d-%d" % (start, end) if end else "bytes=%d-" % (start,)
    headers = {"Range": byte_range}
    req = urllib2.Request(file_url, headers=headers)
    response = urllib2.urlopen(req)
    if not cb or num_cb == 0:
        data = response.read()
        if to_file_path:
            with open(to_file_path, 'wb') as f:
                f.write(data)
        else:
            return data
    else:
        total_size = response.headers.getheader('content-length').strip()
        total_size = int(total_size)
        chunk_size = int(math.ceil(total_size / num_cb))
        response_data = ""
        bytes_so_far = 0
        fout = None
        if to_file_path:
            fout = open(to_file_path, 'wb')
        for x in xrange(0, total_size, chunk_size):
            data = response.read(chunk_size)
            bytes_so_far += len(data)
            if to_file_path:
                fout.write(data)
                fout.flush()
            else:
                response_data += data
            cb(bytes_so_far, total_size)

        last_data = response.read()
        if to_file_path:
            fout.write(last_data)
            fout.close()
        else:
            response_data += last_data
            return response_data


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


def save_zip_to_file(url, zipinfo, save_path):
    with open(save_path, 'wb') as fout:
        data = get_file_from_zip(url, zipinfo)
        fout.write(data)


def tree_print(node, level=0):
    if len(node.keys()) == 0:
        return
    else:
        for x in node.keys():
            print(("%s|-%s") % ("| " * level, x))
            tree_print(node[x], level + 1)


def add_file(files, f):
    xs = f.split("/")
    level = files
    for e in xs:
        if e:
            if not level.has_key(e):
                level[e] = {}
            level = level[e]


def print_files(partial_zip, pretty=False):
    if not pretty:
        for x in partial_zip.zipped_files:
            if x.is_file:
                print "[*] File:", x.file_name, "compressed size:", readable_size(
                        x.compressed_size), "actual size:", readable_size(x.uncompressed_size)
            elif x.is_dir:
                print "[*] Directory:", x.file_name
            else:
                print "[!] Unknown type", x.file_name
    else:
        files = {}
        file_list = [x.file_name if x.is_dir else "%s[%s]"%(x.file_name,readable_size(x.uncompressed_size)) for x in partial_zip.zipped_files]
        for e in file_list:
            add_file(files, e)
        if files:
            tree_print(files)
