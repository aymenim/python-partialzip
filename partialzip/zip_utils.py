#!/usr/bin/env python

import cStringIO
import struct
import os
import sys

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
