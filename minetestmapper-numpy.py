#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# COPYING for more details.

# Made by Jogge, modified by celeron55
# 2011-05-29: j0gge: initial release
# 2011-05-30: celeron55: simultaneous support for sectors/sectors2, removed
# 2011-06-02: j0gge: command line parameters, coordinates, players, ...
# 2011-06-04: celeron55: added #!/usr/bin/python2 and converted \r\n to \n
#                        to make it easily executable on Linux
# 2011-07-30: WF: Support for content types extension, refactoring
# 2011-07-30: erlehmann: PEP 8 compliance.
# 2014-03-05: spillz: Refactored code, use argparse for better command line handling,
#                use numpy for speed boost and reduced memory usage

# Requires Python Imaging Library: http://www.pythonware.com/products/pil/
# Requires Numpy: http://www.scipy.org

import zlib
import os
import string
import time
import argparse
import sys
import traceback
import numpy
import itertools
from PIL import Image, ImageDraw, ImageFont, ImageColor

try:
    from cStringIO import StringIO as BytesIO
except:
    from io import BytesIO


TRANSLATION_TABLE = {
    1: 0x800,  # CONTENT_GRASS
    4: 0x801,  # CONTENT_TREE
    5: 0x802,  # CONTENT_LEAVES
    6: 0x803,  # CONTENT_GRASS_FOOTSTEPS
    7: 0x804,  # CONTENT_MESE
    8: 0x805,  # CONTENT_MUD
    10: 0x806,  # CONTENT_CLOUD
    11: 0x807,  # CONTENT_COALSTONE
    12: 0x808,  # CONTENT_WOOD
    13: 0x809,  # CONTENT_SAND
    18: 0x80a,  # CONTENT_COBBLE
    19: 0x80b,  # CONTENT_STEEL
    20: 0x80c,  # CONTENT_GLASS
    22: 0x80d,  # CONTENT_MOSSYCOBBLE
    23: 0x80e,  # CONTENT_GRAVEL
    24: 0x80f,  # CONTENT_SANDSTONE
    25: 0x810,  # CONTENT_CACTUS
    26: 0x811,  # CONTENT_BRICK
    27: 0x812,  # CONTENT_CLAY
    28: 0x813,  # CONTENT_PAPYRUS
    29: 0x814}  # CONTENT_BOOKSHELF


def hex_to_int(h):
    i = int(h, 16)
    if(i > 2047):
        i -= 4096
    return i


def hex4_to_int(h):
    i = int(h, 16)
    if(i > 32767):
        i -= 65536
    return i


def int_to_hex3(i):
    if(i < 0):
        return "%03X" % (i + 4096)
    else:
        return "%03X" % i


def int_to_hex4(i):
    if(i < 0):
        return "%04X" % (i + 65536)
    else:
        return "%04X" % i


#def signedToUnsigned(i, max_positive):
#    if i >= 0:
#        return i
#    else:
#        return i + 2*max_positive
#def getBlockAsInteger(p):
#    return signedToUnsigned(p[2],2048)*16777216 + signedToUnsigned(p[1],2048)*4096 + signedToUnsigned(p[0],2048)

def getBlockAsInteger(p):
    return p[2]*16777216 + p[1]*4096 + p[0]

def unsignedToSigned(i, max_positive):
    if i < max_positive:
        return i
    else:
        return i - 2*max_positive

def getIntegerAsBlock(i):
    x = unsignedToSigned(i % 4096, 2048)
    i = int((i - x) / 4096)
    y = unsignedToSigned(i % 4096, 2048)
    i = int((i - y) / 4096)
    z = unsignedToSigned(i % 4096, 2048)
    return x,y,z

def readU8(f):
    return ord(f.read(1))

def readU16(f):
    return ord(f.read(1))*256 + ord(f.read(1))

def readU32(f):
    return ord(f.read(1))*256*256*256 + ord(f.read(1))*256*256 + ord(f.read(1))*256 + ord(f.read(1))

def readS32(f):
    return unsignedToSigned(ord(f.read(1))*256*256*256 + ord(f.read(1))*256*256 + ord(f.read(1))*256 + ord(f.read(1)), 2**31)

CONTENT_WATER = 2

def content_is_ignore(d):
    return d == 0
    #return d in [0, "ignore"]

def content_is_water(d):
    return (d == 2) | (d == 9)
    #return d in [2, 9]

def content_is_air(d):
    return (d == 126) | (d == 127) | (d == 254)
#    return d in [126, 127, 254, "air"]

#NOT USED
def read_content(mapdata, version, datapos=None):
    if datapos==None:
        if version >= 24:
            mapdata = numpy.array(mapdata)
            x=numpy.arange(4096)
            return (mapdata[x*2] << 8) | (mapdata[x*2 + 1])

    if version >= 24:
        return (mapdata[datapos*2] << 8) | (mapdata[datapos*2 + 1])
    elif version >= 20:
        if mapdata[datapos] < 0x80:
            return mapdata[datapos]
        else:
            return (mapdata[datapos] << 4) | (mapdata[datapos + 0x2000] >> 4)
    elif 16 <= version < 20:
        return TRANSLATION_TABLE.get(mapdata[datapos], mapdata[datapos])
    else:
        raise Exception("Unsupported map format: " + str(version))


def parse_args():
    parser = argparse.ArgumentParser(description='A mapper for minetest')
    parser.add_argument('--bgcolor', default='black', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the background color (e.g. white or "#FFFFFF")')
    parser.add_argument('--scalecolor', default='white', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the ruler and text color for the scale')
    parser.add_argument('--origincolor', default='red', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the color for the map origin')
    parser.add_argument('--playercolor', default='red', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the color for player markers')
    parser.add_argument('--fogcolor', default='grey', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the color for fog (default grey)')
    parser.add_argument('--ugcolor', default='purple', metavar = 'COLOR', type=ImageColor.getrgb, help = 'set the color for underground areas (default purple)')
    parser.add_argument('--drawscale',action='store_const', const = True, default=False, help = 'draw a scale on the border of the map')
    parser.add_argument('--drawplayers',action='store_const', const = True, default = False, help = 'draw markers for players')
    parser.add_argument('--draworigin',action='store_const', const = True, default = False, help = 'draw the position of the origin (0,0)')
    parser.add_argument('--drawunderground',dest='drawunderground',action='store_const', const = 1, default = 0, help = 'draw underground areas overlaid on the map')
    parser.add_argument('--drawunderground-standalone',dest='drawunderground',action='store_const', const = 2, help = 'draw underground areas as a standalone map')
#    parser.add_argument('--drawunderground',type=str, choices = ('','overlay','standalone'), default = '', help = 'draw underground areas (NOT IMPLEMENTED!)')
    parser.add_argument('--region', nargs=4, type = int, metavar = ('XMIN','XMAX','ZMIN','ZMAX'), default = (-2000,2000,-2000,2000),help = 'set the bounding x,z coordinates for the map (units are nodes, default = -2000 2000 -2000 2000)')
    parser.add_argument('--maxheight', type = int, metavar = ('YMAX'), default = 500, help = 'don\'t draw above height YMAX (default = 500)')
    parser.add_argument('--minheight', type = int, metavar = ('YMIN'), default = -500, help = 'don\'t draw below height YMIN (defualt = -500)')
    parser.add_argument('--pixelspernode', type = int, metavar = ('PPN'), default = 1, help = 'number of pixels per node (default = 1)')
    parser.add_argument('--facing', type = str, choices = ('up','down','north','south','east','west'),default='down',help = 'direction to face when drawing (north, south, east or west will draw a cross-section)')
    parser.add_argument('--fog', type = float, metavar = ('FOGSTRENGTH'), default = 0.0, help = 'use fog strength of FOGSTRENGTH (0.0 by default, max of 1.0)')
    parser.add_argument('world_dir',help='the path to the world you want to map')
    parser.add_argument('output',nargs='?',default='map.png',help='the output filename')
    args = parser.parse_args()
    if args.world_dir is None:
        print("Please select world path (eg. -i ../worlds/yourworld) (or use --help)")
        sys.exit(1)
    if not os.path.isdir(args.world_dir):
        print ("World does not exist")
        sys.exit(1)
    args.world_dir = os.path.abspath(args.world_dir) + os.path.sep
    return args

# Load color information for the blocks.
def load_colors(fname = "colors.txt"):
    uid_to_color = {}
    str_to_uid = {}
    uid=2 #unique id, we always use ignore == 0, air == 1 because these are never drawn
    try:
        f = open("colors.txt")
    except IOError:
        f = open(os.path.join(os.path.dirname(__file__), "colors.txt"))

    for line in f:
        values = line.split()
        if len(values) < 4:
            continue
        identifier = values[0]
        is_hex = True
        for c in identifier:
            if c not in "0123456789abcdefABCDEF":
                is_hex = False
                break
        if is_hex:
            str_to_uid[int(values[0],16)] = uid
            uid_to_color[uid] = (
                int(values[1]),
                int(values[2]),
                int(values[3]))
        else:
            str_to_uid[values[0]] = uid
            uid_to_color[uid] = (
                int(values[1]),
                int(values[2]),
                int(values[3]))
        uid+=1
    f.close()
    return uid_to_color, str_to_uid

#print("colors: "+repr(colors))
#sys.exit(1)

def legacy_fetch_sector_data(args, sectortype, sector_data, ypos):
    yhex = int_to_hex4(ypos)
    if sectortype == "old":
        filename = args.world_dir + "sectors/" + sector_data[0] + "/" + yhex.lower()
    else:
        filename = args.world_dir + "sectors2/" + sector_data[1] + "/" + yhex.lower()
    return open(filename, "rb")


def legacy_sector_scan(args,sectors_xmin, sector_xmax, sector_zmin, sector_zmax):
    if os.path.exists(args.world_dir + "sectors2"):
        for filename in os.listdir(args.world_dir + "sectors2"):
            for filename2 in os.listdir(args.world_dir + "sectors2/" + filename):
                x = hex_to_int(filename)
                z = hex_to_int(filename2)
                if x < sector_xmin or x > sector_xmax:
                    continue
                if z < sector_zmin or z > sector_zmax:
                    continue
                xlist.append(x)
                zlist.append(z)

    if os.path.exists(args.world_dir + "sectors"):
        for filename in os.listdir(args.world_dir + "sectors"):
            x = hex4_to_int(filename[:4])
            z = hex4_to_int(filename[-4:])
            if x < sector_xmin or x > sector_xmax:
                continue
            if z < sector_zmin or z > sector_zmax:
                continue
            xlist.append(x)
            zlist.append(z)

def legacy_fetch_ylist(args,xpos,zpos,ylist):
    sectortype =""
    xhex = int_to_hex3(xpos)
    zhex = int_to_hex3(zpos)
    xhex4 = int_to_hex4(xpos)
    zhex4 = int_to_hex4(zpos)

    sector1 = xhex4.lower() + zhex4.lower()
    sector2 = xhex.lower() + "/" + zhex.lower()
    try:
        for filename in os.listdir(args.world_dir + "sectors/" + sector1):
            if(filename != "meta"):
                pos = int(filename, 16)
                if(pos > 32767):
                    pos -= 65536
                ylist.append(pos)

        if len(ylist)>0:
            sectortype = "old"

        if sectortype == "":
            try:
                for filename in os.listdir(args.world_dir + "sectors2/" + sector2):
                    if(filename != "meta"):
                        pos = int(filename, 16)
                        if(pos > 32767):
                            pos -= 65536
                        ylist.append(pos)
                        sectortype = "new"
            except OSError:
                pass

    except OSError:
        pass
    return sectortype


#Alternative map_block
def find(arr,value,axis=-1):
    return ((arr==value).cumsum(axis=axis)==0).sum(axis=axis)
#
#        if False:
#            mapdata = numpy.swapaxes(mapdata.reshape(16,16,16),0,2)
#            mapdata = numpy.swapaxes(mapdata,1,2).reshape(256,16)
#            content = mapdata[plist]
#            opaques = ~( (content == ignore) | (content == air) )
#            h = find(opaques,True,1)
#            po = (h<16)
#            hpo = h[po]
#            hdata[po] = chunkypos + 16 - hpo
#            cdata[po] = content[po][:,hpo]
#            dnddata[po] = day_night_differs
#            plist = plist[~po]


def map_block(mapdata, version, ypos, maxy, plist, cdata, hdata, dnddata, day_night_differs, id_map, ignore, air, face_swap_order):
    chunkypos = ypos * 16
    mapdata = mapdata[:4096]
    mapdata = id_map[mapdata]
    if (mapdata==ignore).all():
##        return (~( (cdata == ignore) | (cdata == air) )).all()
        return plist
    (swap1a,swap1b),(swap2a,swap2b) = face_swap_order[1:]
    mapdata = numpy.swapaxes(mapdata.reshape(16,16,16),swap1a,swap1b)
    mapdata = numpy.swapaxes(mapdata,swap2a,swap2b).reshape(16,256)
    if face_swap_order[0]>0:
        r = range(maxy,-1,-1)
    else:
        r = range(maxy,16,1)
#        mapdata=mapdata[::-1]
    y=maxy
#    if True:
#        mapdata = mapdata[y:]
#        opaques = ~( (mapdata == ignore) | (mapdata == air) )
#        copaques = ~( (cdata == ignore) | (cdata == air) )
#        h = find(opaques,True,0)
#        po = (h<16-y)
#        hpo = h*po
#        hdata[~copaques] = chunkypos + 16 - hpo[~copaques]
#        cdata[~copaques] = mapdata[hpo][~copaques]
#        dnddata[~copaques] = day_night_differs
#        if (~( (cdata == ignore) | (cdata == air) )).all():
#            return []
#        else:
#            return plist
    for y in r:
        if len(plist)==0:
            break
        content = mapdata[y][plist]
#            watercontent = content_is_water(content)
#            wdata[plist] += watercontent
#            opaques = ~( (content_is_air(content) | content_is_ignore(content) | watercontent))
        opaques = ~( (content == ignore) | (content == air) )
        po = plist[opaques]
        pno = plist[~opaques]
        cdata[po] = content[opaques]
        hdata[po] = chunkypos + y
        dnddata[po] = day_night_differs
        plist = plist[~opaques]
        y-=1
    return plist

def map_block_ug(mapdata, version, ypos, maxy, cdata, hdata, udata, uhdata, dnddata, day_night_differs, id_map, ignore, air, underground, face_swap_order):
    chunkypos = ypos * 16
    mapdata = mapdata[:4096]
    mapdata = id_map[mapdata]
    if (mapdata==ignore).all():
        return (~( (cdata == ignore) | (cdata == air) )).all()
    (swap1a,swap1b),(swap2a,swap2b) = face_swap_order[1:]
    mapdata = numpy.swapaxes(mapdata.reshape(16,16,16),swap1a,swap1b)
    mapdata = numpy.swapaxes(mapdata,swap2a,swap2b).reshape(16,256)
    if face_swap_order[0]>0:
        r = range(maxy,-1,-1)
    else:
        r = range(maxy,16,1)
    y=maxy
    for y in r:
        content = mapdata[y]
        opaques = ~( (content == ignore) | (content == air) )
        copaques = ~( (cdata == ignore) | (cdata == air) )
        air = (content == air)
        cdata[~copaques] = content[~copaques]
        hdata[~copaques] = chunkypos + y
        dnddata[~copaques] = day_night_differs
        uhdata += (udata==0)*(chunkypos + y)*(air * copaques)*(~opaques)*underground
        udata += (air * copaques)*(~opaques)*underground
    return (~( (cdata == ignore) | (cdata == air) )).all()
#        y-=1

def get_db(args):
    if not os.path.exists(args.world_dir+"world.mt"):
        return None
    with open(args.world_dir+"world.mt") as f:
        keyvals = f.read().splitlines()
    keyvals = [kv.split("=") for kv in keyvals]
    backend = None
    for k,v in keyvals:
        if k.strip() == "backend":
            backend = v.strip()
            break
    if backend == "sqlite3":
        return SQLDB(args.world_dir + "map.sqlite")
    if backend == "leveldb":
        return LVLDB(args.world_dir + "map.db")

class SQLDB:
    def __init__(self, path):
        import sqlite3
        conn = sqlite3.connect(path)
        self.cur = conn.cursor()

    def __iter__(self):
        self.cur.execute("SELECT `pos` FROM `blocks`")
        while True:
            r = self.cur.fetchone()
            if not r:
                break
            x, y, z = getIntegerAsBlock(r[0])
            yield x,y,z,r[0]

    def get(self, pos):
        self.cur.execute("SELECT `data` FROM `blocks` WHERE `pos`==? LIMIT 1", (pos,))
        r = self.cur.fetchone()
        if not r:
            return
        return BytesIO(r[0])

class LVLDB:
    def __init__(self, path):
        import leveldb
        self.conn = leveldb.LevelDB(path)

    def __iter__(self):
        for k in self.conn.RangeIter():
            x, y, z = getIntegerAsBlock(int(k[0]))
            yield x, y, z, k[0]

    def get(self, pos):
        return BytesIO(self.conn.Get(pos))



class World:
    def __init__(self,args):
        self.xlist = []
        self.zlist = []
        self.args = args
        self.db = None
        self.minx = None
        self.minz = None
        self.maxx = None
        self.maxz = None
        self.mapinfo = None

    def facing(self,x,y,z):
        if self.args.facing in ['up','down']:
            return x,y,z
        if self.args.facing in ['east','west']:
            return z,x,y
        if self.args.facing in ['north','south']:
            return x,z,y

    def generate_sector_list(self):
        '''
        List all sectors to memory and calculate the width and heigth of the
        resulting picture.
        '''
        args = self.args
        sector_xmin,sector_xmax,sector_zmin,sector_zmax = numpy.array(args.region)/16
        sector_ymin = args.minheight/16
        sector_ymax = args.maxheight/16
        xlist = []
        zlist = []
        self.lookup={}
        self.db = get_db(args)
        if self.db is not None:
            for x, y, z, pos in self.db:
                if x < sector_xmin or x > sector_xmax:
                    continue
                if z < sector_zmin or z > sector_zmax:
                    continue
                if y < sector_ymin or y > sector_ymax:
                    continue

                x, y, z = self.facing(x, y, z)
                try:
                    self.lookup[(x,z)].append((y,pos))
                except KeyError:
                    self.lookup[(x,z)]=[(y,pos)]
                xlist.append(x)
                zlist.append(z)
        else:
            legacy_sector_scan(args, sectors_xmin, sector_xmax, sector_zmin, sector_zmax)

        if len(xlist)>0:
            # Get rid of duplicates
            self.xlist, self.zlist = zip(*sorted(set(zip(xlist, zlist))))

            self.minx = min(xlist)
            self.minz = min(zlist)
            self.maxx = max(xlist)
            self.maxz = max(zlist)

            x0,x1,z0,z1 = numpy.array(args.region)
            y0 = args.minheight
            y1 = args.maxheight
            self.minypos = self.facing(int(x0),int(y0),int(z0))[1]
            self.maxypos = self.facing(int(x1),int(y1),int(z1))[1]

            self.w = (self.maxx - self.minx) * 16 + 16
            self.h = (self.maxz - self.minz) * 16 + 16

    def generate_map_info(self,str_to_uid):
        read_map_time = 0
        db = self.db
        xlist = self.xlist
        zlist = self.zlist
        args = self.args
        minx = self.minx
        minz = self.minz
        maxx = self.maxx
        maxz = self.maxz
        w = self.w
        h = self.h

        #x,y,z becomes y,x,z for up/down
        #      becomes x,z,y for east/west
        #      becomes z,x,y for north/south
        if args.facing in ['up','down']:
            face_swap_order = [1,(1,0),(1,2)]
        elif args.facing in ['east','west']:
            face_swap_order = [1,(2,0),(2,1)]
        elif args.facing in ['north','south']:
            face_swap_order = [1,(0,0),(1,2)]
        if args.facing in ['up','east','north']:
            face_swap_order[0] = -1

        mapinfo = {
            'height':numpy.zeros([w,h],dtype = 'i2'),
            'content':numpy.zeros([w,h],dtype='u2'),
            'water':numpy.zeros([w,h],dtype = 'u2'),
            'dnd':numpy.zeros([w,h],dtype=bool)}
        if args.drawunderground:
            mapinfo['underground'] = numpy.zeros([w,h],dtype = 'u2')
            mapinfo['undergroundh'] = numpy.zeros([w,h],dtype = 'i2')


        unknown_node_names = set()
        unknown_node_ids = set()

        starttime = time.time()
        # Go through all sectors.
        for n in range(len(xlist)):
            #if n > 500:
            #   break
            if n % 200 == 0:
                nowtime = time.time()
                dtime = nowtime - starttime
                try:
                    n_per_second = 1.0 * n / dtime
                except ZeroDivisionError:
                    n_per_second = 0
                if n_per_second != 0:
                    seconds_per_n = 1.0 / n_per_second
                    time_guess = seconds_per_n * len(xlist)
                    remaining_s = time_guess - dtime
                    remaining_minutes = int(remaining_s / 60)
                    remaining_s -= remaining_minutes * 60
                    print("Processing sector " + str(n) + " of " + str(len(xlist))
                            + " (" + str(round(100.0 * n / len(xlist), 1)) + "%)"
                            + " (ETA: " + str(remaining_minutes) + "m "
                            + str(int(remaining_s)) + "s)")

            xpos = xlist[n]
            zpos = zlist[n]

            ylist = []

            sectortype = ""

            if db is not None:
                ymin = self.minypos/16 #-2048 if args.minheight is None else args.minheight/16+1
                ymax = self.maxypos/16+1 #2047 if args.maxheight is None else args.maxheight/16+1
                for k in self.lookup[(xpos,zpos)]:
                    ylist.append(k)
                sectortype = "sqlite"
            else:
                sectortype,sector_data = legacy_fetch_ylist(args,xpos,zpos,ylist)

            if sectortype == "":
                continue

            ylist.sort()
            if face_swap_order[0]>0:
                ylist.reverse()

            if args.facing in ['south','west','down']:
                miny = self.minypos-1
            else:
                miny = self.maxypos+1
            # Create map related info for the sector that will be filled as we seek down the y axis
            cdata = numpy.zeros(256,dtype='i4')
            hdata = numpy.ones(256,dtype='i4')*miny
            wdata = numpy.zeros(256,dtype='i4')
            dnddata = numpy.zeros(256,dtype=bool)
            if args.drawunderground:
                udata = numpy.zeros(256,dtype='i4')
                uhdata = numpy.zeros(256,dtype='i4')
            plist = numpy.arange(256)

            # Go through the Y axis from top to bottom.
            for ypos,ps in ylist:
                try:

                    if db is not None:
                        f = db.get(ps)
                    else:
                        f = legacy_fetch_sector_data(args, sectortype, sector_data, ypos)

                    # Let's just memorize these even though it's not really necessary.
                    version = readU8(f)
                    flags = f.read(1)

                    #print("version="+str(version))
                    #print("flags="+str(version))

                    # Check flags
                    is_underground = ((ord(flags) & 1) != 0)
                    day_night_differs = ((ord(flags) & 2) != 0)
                    lighting_expired = ((ord(flags) & 4) != 0)
                    generated = ((ord(flags) & 8) != 0)

                    #print("is_underground="+str(is_underground))
                    #print("day_night_differs="+str(day_night_differs))
                    #print("lighting_expired="+str(lighting_expired))
                    #print("generated="+str(generated))

                    if version >= 22:
                        content_width = readU8(f)
                        params_width = readU8(f)

                    # Node data
                    dec_o = zlib.decompressobj()
                    try:
                        s = dec_o.decompress(f.read())
                        mapdata = numpy.fromstring(s,">u2")
                    except:
                        mapdata = []

                    # Reuse the unused tail of the file
                    f.close();
                    f = BytesIO(dec_o.unused_data)
                    #print("unused data: "+repr(dec_o.unused_data))

                    # zlib-compressed node metadata list
                    dec_o = zlib.decompressobj()
                    try:
                        s=dec_o.decompress(f.read())
                        metaliststr = numpy.fromstring(s,"u1")
                        # And do nothing with it
                    except:
                        metaliststr = []

                    # Reuse the unused tail of the file
                    f.close();
                    f = BytesIO(dec_o.unused_data)
                    #print("* dec_o.unused_data: "+repr(dec_o.unused_data))
                    data_after_node_metadata = dec_o.unused_data

                    if version <= 21:
                        # mapblockobject_count
                        readU16(f)

                    if version == 23:
                        readU8(f) # Unused node timer version (always 0)
                    if version == 24:
                        ver = readU8(f)
                        if ver == 1:
                            num = readU16(f)
                            for i in range(0,num):
                                readU16(f)
                                readS32(f)
                                readS32(f)

                    static_object_version = readU8(f)
                    static_object_count = readU16(f)
                    for i in range(0, static_object_count):
                        # u8 type (object type-id)
                        object_type = readU8(f)
                        # s32 pos_x_nodes * 10000
                        pos_x_nodes = readS32(f)/10000
                        # s32 pos_y_nodes * 10000
                        pos_y_nodes = readS32(f)/10000
                        # s32 pos_z_nodes * 10000
                        pos_z_nodes = readS32(f)/10000
                        # u16 data_size
                        data_size = readU16(f)
                        # u8[data_size] data
                        data = f.read(data_size)

                    timestamp = readU32(f)
                    #print("* timestamp="+str(timestamp))

                    id_to_name = {}
                    name_to_id = {}
                    air = 1
                    ignore = 0
                    if version >= 22:
                        name_id_mapping_version = readU8(f)
                        num_name_id_mappings = readU16(f)
                        #print("* num_name_id_mappings: "+str(num_name_id_mappings))
                        for i in range(0, num_name_id_mappings):
                            node_id = readU16(f)
                            name_len = readU16(f)
                            name = f.read(name_len).decode('utf8')
                            try:
                                id_to_name[node_id] = str_to_uid[name]
                            except:
                                ##TODO: Add to list of unknown colors
                                unknown_node_names.add(name)
                                unknown_node_ids.add(node_id)
                                id_to_name[node_id] = 0
                            if name == 'air':
                                air = id_to_name[node_id]
                            if name == 'ignore':
                                ignore = id_to_name[node_id]
                    if len(id_to_name)==0:
                        id_map = numpy.array([0,1],dtype='i4')
                    else:
                        id_map = numpy.array([id_to_name[i] for i in sorted(id_to_name)],dtype='i4')

                    # Node timers
                    if version >= 25:
                        timer_size = readU8(f)
                        num = readU16(f)
                        for i in range(0,num):
                            readU16(f)
                            readS32(f)
                            readS32(f)
                    ##facing in down,south,west use maxheight, otherwise use minheight
                    if face_swap_order[0]>0:
                        maxy = 15
                        if ypos*16 + 15 > self.maxypos:
                            maxy = self.maxypos - ypos*16
                    else:
                        maxy = 0
                        if ypos*16 + 15 < self.minypos:
                            maxy = ypos*16 - self.minypos
                    if maxy>=0:
                        if args.drawunderground:
                            plist = map_block_ug(mapdata, version, ypos, maxy, cdata, hdata, udata, uhdata, dnddata, day_night_differs, id_map, ignore, air, is_underground, face_swap_order)
                        else:
                            plist = map_block(mapdata, version, ypos, maxy, plist, cdata, hdata, dnddata, day_night_differs, id_map, ignore, air, face_swap_order)
                            ##plist = map_block(mapdata, version, ypos, maxy, cdata, hdata, dnddata, day_night_differs, id_map, ignore, air, face_swap_order)
                    # After finding all the pixels in the sector, we can move on to
                    # the next sector without having to continue the Y axis.
                    if (not args.drawunderground and len(plist) == 0) or ypos==ylist[-1][0]:
                    ##if plist == True or ypos==ylist[-1][0]:
                        chunkxpos = (xpos-minx)*16
                        chunkzpos = (zpos-minz)*16
                        if True: #face_swap_order[0]<0:
                            pass
                            #chunkxpos = (maxx-minx)*16 - chunkxpos #-16?
                            #chunkzpos = (maxz-minz)*16 - chunkzpos #-16?
                        pos = (slice(chunkxpos,chunkxpos+16),slice(chunkzpos,chunkzpos+16))
                        mapinfo['height'][pos] = hdata.reshape(16,16)
                        mapinfo['content'][pos] = cdata.reshape(16,16)
                        mapinfo['water'][pos] = wdata.reshape(16,16)
                        mapinfo['dnd'][pos] = dnddata.reshape(16,16)
                        if args.drawunderground:
                            mapinfo['underground'][pos] = udata.reshape(16,16)
                            mapinfo['undergroundh'][pos] = uhdata.reshape(16,16)
                        break
                except Exception as e:
                    print("Error at ("+str(xpos)+","+str(ypos)+","+str(zpos)+"): "+str(e))
                    traceback.print_exc()
                    sys.stdout.write("Block data: ")
                    for c in r[0]:
                        sys.stdout.write("%2.2x "%ord(c))
                    sys.stdout.write(os.linesep)
                    sys.stdout.write("Data after node metadata: ")
                    for c in data_after_node_metadata:
                        sys.stdout.write("%2.2x "%ord(c))
                    sys.stdout.write(os.linesep)
                    traceback.print_exc()
        self.mapinfo = mapinfo
        if unknown_node_names:
            sys.stdout.write("Unknown node names:")
            for name in unknown_node_names:
                sys.stdout.write(" "+name)
            sys.stdout.write(os.linesep)
        if unknown_node_ids:
            sys.stdout.write("Unknown node ids:")
            for node_id in unknown_node_ids:
                sys.stdout.write(" "+str(hex(node_id)))
            sys.stdout.write(os.linesep)
#        print str_to_uid

def draw_image(world,uid_to_color):
    # Drawing the picture
    args = world.args
    stuff = world.mapinfo
    minx = world.minx
    minz = world.minz
    maxx = world.maxx
    maxz = world.maxz
    w = world.w
    h = world.h
    reverse_dirs = ['east','south','up']

    print("Drawing image")
    starttime = time.time()
    border = 40 if args.drawscale else 0
    im = Image.new("RGB", (w*args.pixelspernode + border, h*args.pixelspernode + border), args.bgcolor)
    draw = ImageDraw.Draw(im)

    if args.pixelspernode>1:
        stuff['content'] = stuff['content'].repeat(args.pixelspernode,axis=0).repeat(args.pixelspernode,axis=1)
        stuff['dnd'] = stuff['dnd'].repeat(args.pixelspernode,axis=0).repeat(args.pixelspernode,axis=1)
        stuff['height'] = stuff['height'].repeat(args.pixelspernode,axis=0).repeat(args.pixelspernode,axis=1)
        stuff['water'] = stuff['water'].repeat(args.pixelspernode,axis=0).repeat(args.pixelspernode,axis=1)

    if args.facing in reverse_dirs:
        stuff['content'] = stuff['content'][::-1,:]
        stuff['dnd'] = stuff['dnd'][::-1,:]
        stuff['height'] = stuff['height'][::-1,:]
        stuff['water'] = stuff['water'][::-1,:]

    count_dnd=0
    count_height=0
    count_zero=0

    c = stuff['content']
    dnd = stuff['dnd']
    hgh = stuff['height']
    c0 = c[1:,:-1]
    c1 = c[:-1,1:]
    c2 = c[1:, 1:]
    dnd0 = dnd[1:,:-1]
    dnd1 = dnd[:-1,1:]
    dnd2 = dnd[1:, 1:]
    h0 = hgh[1:,:-1]
    h1 = hgh[:-1,1:]
    h2 = hgh[1:, 1:]
    drop = (2*h0 - h1 - h2) * 12
    if args.facing in ['east','north','up']:
        drop = -drop
    drop = numpy.clip(drop,-32,32)

    if args.fog>0:
        fogstrength = 1.0* (stuff['height']-stuff['height'].min())/(stuff['height'].max()-stuff['height'].min())
        if args.facing in reverse_dirs:
            fogstrength = 1-fogstrength
        fogstrength = args.fog * fogstrength
        fogstrength = fogstrength[:,:,numpy.newaxis]
    if args.drawunderground:
        ugcoeff = 0.9 if args.drawunderground == 2 else 0.4
        ugstrength = 1.0*(stuff['underground'])/6 #normalize so that 6 blocks of air underground is considered "big"
        ugstrength = (ugstrength>0)*0.1 + ugcoeff*ugstrength
        ugstrength = ugstrength - (ugstrength-0.75)*(ugstrength>0.75)
        ugstrength = ugstrength[:,:,numpy.newaxis]
        print('ugmin',stuff['undergroundh'].min())
        print('ugmax',stuff['undergroundh'].max())
        ugdepth = 1.0* (stuff['undergroundh']-stuff['undergroundh'].min())/(stuff['undergroundh'].max()-stuff['undergroundh'].min())
        ugdepth = ugdepth[:,:,numpy.newaxis]
        u = stuff['underground']
        u0 = u[1:,:-1]>0
        u1 = u[:-1,1:]>0
        u2 = u[1:, 1:]>0
        hgh = stuff['undergroundh']
        h0 = hgh[1:,:-1]
        h1 = hgh[:-1,1:]
        h2 = hgh[1:, 1:]
        dropg = (2*h0 - h1 - h2) * 12 * u0 * u1 * u2
        if args.facing in reverse_dirs:
            dropg = -dropg
        dropg = numpy.clip(dropg,-32,32)


    if args.drawunderground < 2: #normal map or cave with map overlay
        colors = numpy.array([args.bgcolor,args.bgcolor]+[uid_to_color[c] for c in sorted(uid_to_color)],dtype = 'i2')
    else:
        colors = numpy.array([args.bgcolor,args.bgcolor]+[args.bgcolor for c in sorted(uid_to_color)],dtype = 'i2')

    pix = colors[stuff['content']]
    if args.drawunderground < 2:
        pix[1:,:-1] += drop[:,:,numpy.newaxis]
        pix = numpy.clip(pix,0,255)
        if args.fog>0:
            pix = args.fogcolor*fogstrength + pix*(1-fogstrength)
            pix = numpy.clip(pix,0,255)
    if args.drawunderground:
        ugpd = args.ugcolor*ugdepth + args.bgcolor * (1-ugdepth) ##average with background color based on depth (deeper caves will be more bg color)
        pix = ugpd*ugstrength + pix*(1-ugstrength)
        pix[1:,:-1] += dropg[:,:,numpy.newaxis]
        pix = numpy.clip(pix,0,255)

    pix = numpy.array(pix,dtype = 'u1')
    impix = Image.fromarray(pix,'RGB')
    impix = impix.transpose(Image.ROTATE_90)
    im.paste(impix,(border,border))


    if args.draworigin:
        if args.facing in ['east','north','up']:
            draw.ellipse(((w - (minx * -16 - 5))*args.pixelspernode + border, (h - minz * -16 - 6)*args.pixelspernode + border,
                (w - (minx * -16 + 5))*args.pixelspernode + border, (h - minz * -16 + 4))*args.pixelspernode + border,
                outline=args.origincolor)
        else:
            draw.ellipse(((minx * -16 - 5)*args.pixelspernode + border, (h - minz * -16 - 6)*args.pixelspernode + border,
                (minx * -16 + 5)*args.pixelspernode + border, (h - minz * -16 + 4)*args.pixelspernode + border),
                outline=args.origincolor)

    font = ImageFont.load_default()

    if args.drawscale:
        if args.facing in ['up','down']:
            draw.text((24, 0), "X", font=font, fill=args.scalecolor)
            draw.text((2, 24), "Z", font=font, fill=args.scalecolor)
        elif args.facing in ['east','west']:
            draw.text((24, 0), "Z", font=font, fill=args.scalecolor)
            draw.text((2, 24), "Y", font=font, fill=args.scalecolor)
        elif args.facing in ['north','south']:
            draw.text((24, 0), "X", font=font, fill=args.scalecolor)
            draw.text((2, 24), "Y", font=font, fill=args.scalecolor)

        if args.facing in reverse_dirs:
            for n in range(int(minx / -4) * -4, maxx+1, 4):
                draw.text(((w - (minx * -16 + n * 16))*args.pixelspernode + border + 2, 0), str(n * 16),
                    font=font, fill=args.scalecolor)
                draw.line(((w - (minx * -16 + n * 16))*args.pixelspernode + border, 0,
                    (w - (minx * -16 + n * 16))*args.pixelspernode + border, border - 1), fill=args.scalecolor)
        else:
            for n in range(int(minx / -4) * -4, maxx, 4):
                draw.text(((minx * -16 + n * 16)*args.pixelspernode + border + 2 , 0), str(n * 16),
                    font=font, fill=args.scalecolor)
                draw.line(((minx * -16 + n * 16)*args.pixelspernode + border, 0,
                    (minx * -16 + n * 16)*args.pixelspernode + border, border - 1), fill=args.scalecolor)

        for n in range(int(maxz / 4) * 4, minz, -4):
            draw.text((2, (h - 1 - (n * 16 - minz * 16))*args.pixelspernode + border), str(n * 16),
                font=font, fill=args.scalecolor)
            draw.line((0, (h - 1 - (n * 16 - minz * 16))*args.pixelspernode + border, border - 1,
                (h - 1 - (n * 16 - minz * 16))*args.pixelspernode + border), fill=args.scalecolor)

    if args.drawplayers:
        try:
            for filename in os.listdir(args.world_dir + "players"):
                f = open(args.world_dir + "players/" + filename)
                lines = f.readlines()
                name = ""
                position = []
                for line in lines:
                    p = line.split()
                    if p[0] == "name":
                        name = p[2]
                        print(filename + ": name = " + name)
                    if p[0] == "position":
                        position = p[2][1:-1].split(",")
                        print(filename + ": position = " + p[2])
                if len(name) < 0 and len(position) == 3:
                    x,y,z = [int(float(p)/10) for p in position]
                    x,y,z = world.facing(x,y,z)
                    if args.facing in reverse_dirs:
                        x = (w - x - minx * 16)*args.pixelspernode
                        z = (h - z - minz * 16)*args.pixelspernode
                    else:
                        x = (x - minx * 16)*args.pixelspernode
                        z = (h - z - minz * 16)*args.pixelspernode
                    draw.ellipse(((x - 2)*args.pixelspernode + border, (z - 2)*args.pixelspernode + border,
                        (x + 2)*args.pixelspernode + border, (z + 2)*args.pixelspernode + border), outline=args.playercolor)
                    draw.text(((x + 2)*args.pixelspernode + border, (z + 2)*args.pixelspernode + border), name,
                        font=font, fill=args.playercolor)
                f.close()
        except OSError:
            pass

#    print("args: ", args)
#    print("stuff: ", stuff)
#    print("world.xlist: ", world.xlist)
#    print("world.zlist: ", world.zlist)
#    print("world.args: ", world.args)
#    print("world.db: ", world.db)
#    print("world.mapinfo: ", world.mapinfo)#
#    print("PNG Limits: ", args.region)	# metavar = ('XMIN','XMAX','ZMIN','ZMAX')
#    worldlimits=[minx*16, maxx*16, minz*16, maxz*16]
#    print("World Limits: ", worldlimits)

    # region is incorrect if world limits are exceeded. The following attempts to correct this
    # worldlimits are measured in cubes of 16x16x16
    # this code generates incorrect values if the requested region is greater than the world dimensions
    pngminx = int(args.region[0]/16)*16 if args.region[0] < minx*16 else minx*16
    pngmaxx = int((args.region[1]+16)/16)*16 if args.region[1] > maxx*16 else maxx*16
    pngminz = int(args.region[2]/16)*16 if args.region[2] < minz*16 else minz*16
    pngmaxz = int((args.region[3]+16)/16)*16 if args.region[3] > maxz*16 else maxz*16
    pngminx = minx*16
    pngmaxx = maxx*16
    pngminz = minz*16
    pngmaxz = maxz*16
    pngregion=[pngminx, pngmaxx, pngminz, pngmaxz]

    print("Saving to: "+ args.output)
    print("PNG Region: ", pngregion)
    print("Pixels PerNode: ", args.pixelspernode)
    print("border: ", border)
#    print("w: ", w)
#    print("h: ", h)

    # This saves data in tEXt chunks (non-standard naming tags are allowed according to the PNG specification)
    im.info["pngRegion"] = str(pngregion[0])+ ","+ str(pngregion[1])+ ","+ str(pngregion[2])+ ","+ str(pngregion[3])
    im.info["pngMinX"] = str(pngminx)
    im.info["pngMaxZ"] = str(pngmaxz)
    im.info["border"] = str(border)
    im.info["pixPerNode"] = str(args.pixelspernode)
    pngsave(im, args.output)


    thumbSize = 512
    imSize = im.size
    if imSize[0] > imSize[1]:
      reSize=(thumbSize, int(thumbSize*(int(imSize[1])/imSize[0])))
    else:
      reSize=(int(thumbSize*(float(imSize[0])/imSize[1])), thumbSize)

    thumbBorder=((thumbSize-reSize[0])/2, (thumbSize-reSize[1])/2, thumbSize-(thumbSize-reSize[0])/2, thumbSize-(thumbSize-reSize[1])/2)
    thumbIm = Image.new("RGB", (thumbSize,thumbSize), args.bgcolor)
    thumbIm.paste(im.resize(reSize),thumbBorder)
    thumbIm.save(args.output.replace(".png", "_thumb.png"), "PNG")


#                                                                                                                                      
# wrapper around PIL 1.1.6 Image.save to preserve PNG metadata
#
# public domain, Nick Galbreath                                                                                                        
# http://blog.client9.com/2007/08/28/python-pil-and-png-metadata-take-2.html                                                                 
#                                                                                                                                       
def pngsave(im, file):
    # these can be automatically added to Image.info dict                                                                              
    # they are not user-added metadata
    reserved = ('interlace', 'gamma', 'dpi', 'transparency', 'aspect')

    # undocumented class
    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()

    # copy metadata into new object
    for k,v in im.info.iteritems():
        if k in reserved: continue
        meta.add_text(k, v, 0)

    # and save
    im.save(file, "PNG", pnginfo=meta)


def main():
    args = parse_args()

    uid_to_color, str_to_uid = load_colors()

    world = World(args)

    world.generate_sector_list()

    if len(world.xlist) == 0:
        print("World data does not exist.")
        sys.exit(1)

    print("Result image (w=" + str(world.w) + " h=" + str(world.h) + ") will be written to "
            + args.output)

    world.generate_map_info(str_to_uid)

    draw_image(world,uid_to_color)

if __name__ == '__main__':
    main()
