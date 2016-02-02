#!/usr/bin/env python

import argparse
import cStringIO
import struct
import sys

import utils
import zip_utils

DEBUG = False


class ZippedFile:
    def __init__(self, zip_info):
        self.zipped_file_info = zip_info
        self.file_name = zip_info.filename
        self.dir_name = zip_info.filename
        self.compressed_size = zip_info.compress_size
        self.uncompressed_size = zip_info.file_size

        self.deflated = True if zip_info.compress_type == zip_utils.ZIP_DEFLATED else False


class PartialZip:
    def __init__(self, zip_url):
        self.zip_url = zip_url
        self.filesize = int(utils.get_filesize_url(url))
        self._all_zip_infos = None
        self._zipped_files = None

    def _parse_zip_central_directory(self):
        endrec = self._get_end_record_data()
        size_cd = endrec[zip_utils._ECD_SIZE]  # bytes in central directory
        offset_cd = endrec[zip_utils._ECD_OFFSET]  # offset of central directory

        if DEBUG:
            print "[*] size of the central directory ", utils.readable_size(size_cd), "offset", utils.readable_size(
                offset_cd)

        central_directory = self._get_central_directory(size_cd, offset_cd)
        self._all_zip_infos, self._zipped_files = self._parse_central_directory(central_directory)

    def _zip_infos(self):
        if not self._all_zip_infos:
            self._parse_zip_central_directory()

        return self._all_zip_infos

    @property
    def zipped_files(self):
        if not self._zipped_files:
            self._parse_zip_central_directory()
        return  self._zipped_files

    def _print_files(self, file_list, pretty=False):
        if not pretty:
            for x in file_list:
                if x.flag_bits == 0x8:
                    print "[*] File:", x.filename, "compressed size:", utils.readable_size(
                        x.compress_size), "actual size:", utils.readable_size(x.file_size)
                elif x.flag_bits == 0:
                    print "[*] Directory:", x.filename
                else:
                    print "[!] Unknown type", x.filename
        else:
            print "[:(] not implemented yet!"

    def print_files(self):
        self._print_files(self._zip_infos())

    def _get_end_record_data(self):
        if DEBUG:
            print "[*] size of the cd:", zip_utils.sizeEndCentDir
        cd_data = utils.get_data(self.zip_url, self.filesize - zip_utils.sizeEndCentDir)

        if DEBUG:
            print "[*] size of the cd data:", len(cd_data)
            utils.hexdump(cd_data)

        # directly taken from the python standard library ZipFile class of zipfile module line 219 - 228
        if len(cd_data) == zip_utils.sizeEndCentDir and cd_data[0:4] == zip_utils.stringEndArchive and cd_data[
                                                                                                       -2:] == b"\000\000":
            # the signature is correct and there's no comment, unpack structure
            endrec = struct.unpack(zip_utils.structEndArchive, cd_data)
            endrec = list(endrec)

            # Append a blank comment and record start offset
            endrec.append("")
            endrec.append(self.filesize - zip_utils.sizeEndCentDir)

            if DEBUG:
                print "[*] end record data ", endrec

            return endrec

    def _get_central_directory(self, size, offset):
        cd = utils.get_data(self.zip_url, offset, offset + size - 1)  # offset point to the first byte ...
        if DEBUG:
            print "[*] size of the central directory:", len(cd)
        # hexdump(cd)
        return cd
    # directly taken from the python standard library ZipFile class
    def _parse_central_directory(self, data):
        size_cd = len(data)
        fp = cStringIO.StringIO(data)
        total = 0
        filelist = []
        NameToInfo = {}
        zipped_files = []
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
            zipped_files.append(ZippedFile(x))

            # update total bytes read from central directory
            total = (total + zip_utils.sizeCentralDir + centdir[zip_utils._CD_FILENAME_LENGTH]
                     + centdir[zip_utils._CD_EXTRA_FIELD_LENGTH]
                     + centdir[zip_utils._CD_COMMENT_LENGTH])


        return filelist , zipped_files


def main(url):
    pz = PartialZip(url)
    pz.print_files()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "http://appldnld.apple.com/ios9.2/031-29213-20151203-67549F46-8D8A-11E5-96EE-63618B8BECEB/iPhone5,2_9.2_13C75_Restore.ipsw"

    main(url)
