#!/usr/bin/env python

import argparse
import sys

import utils
import zip_utils

DEBUG = False

def main(url):

    pz = PartialZip(url)
    pz.print_files()

class PartialZip:

    def __init__(self, zip_url):
        self.zip_url = zip_url
        self.filesize = int(utils.get_filesize_url(url))
        self._all_zip_infos = None

    def _zip_infos(self):
        if self._all_zip_infos:
            return self._all_zip_infos
        else:
            endrec = utils.get_end_record_data(url, self.filesize)

            size_cd = endrec[zip_utils._ECD_SIZE]  # bytes in central directory
            offset_cd = endrec[zip_utils._ECD_OFFSET]  # offset of central directory

            if DEBUG:
                print "[*] size of the central directory ", utils.readable_size(size_cd), "offset", utils.readable_size(offset_cd)

            central_directory = utils.get_central_directory(url, size_cd, offset_cd)
            self._all_zip_infos = utils.parse_central_directory(central_directory)
            return self._all_zip_infos


    def _print_files(self , file_list, pretty=False):
        if not pretty:
            for x in file_list:
                if x.flag_bits == 0x8:
                    print "[*] File:", x.filename , "compressed size:", utils.readable_size(x.compress_size), "actual size:", utils.readable_size(x.file_size)
                elif x.flag_bits == 0:
                    print "[*] Directory:", x.filename
                else:
                    print "[!] Unknown type", x.filename
        else:
            print "[:(] not implemented yet!"

    def print_files(self):
        self._print_files(self._zip_infos())




if __name__ == '__main__':
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "http://appldnld.apple.com/ios9.2/031-29213-20151203-67549F46-8D8A-11E5-96EE-63618B8BECEB/iPhone5,2_9.2_13C75_Restore.ipsw"

    main(url)
