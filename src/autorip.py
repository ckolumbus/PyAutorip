#!/usr/bin/python
# -*- coding: latin-1 -*-

# Copyright (C) 2005-2008 Chris Drexler
# All rights reserved.
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# Author   : Chris Drexler <chris@drexler-family.com>
# Based on : http://autorip.sourceforge.net/
# Modified : autorip\@elvenhome.net


# Resource/Info from:
#  unicode writing/reading of dos files and in general
#  http://mail.python.org/pipermail/tutor/2003-January/019732.html 
#  http://effbot.org/zone/unicode-objects.htm 
#
#  http://trac.edgewall.org/wiki/TracDev/UnicodeGuidelines

# TODO: check http://www.tux.org/~peterw/autorip.html for improvements

from optparse import OptionParser
import sys, os
import DiscID, CDDB # install python-CDDB for these both packages
import time
import eyeD3        # install python-eyeD3 for this
from mutagen.flac import FLAC   # will replace eyeD3 (sooner or later :-)
import utf8
import re
import shutil
import locale
import md5
import codecs
import types

#eyeD3.utils.TRACE=1


ENCODING = locale.getpreferredencoding()

version = "0.2"
debug = False
no_action = False

#############################################################################

g_sansa_root="/media/Sansa_e260"
g_sansa_music=os.path.join(g_sansa_root, "music")
g_sansa_playlists=os.path.join(g_sansa_root, "PLAYLISTS")

#############################################################################
eject_cmd = "eject %(rip_device)s"
rip_device = "/dev/cdrom"

rip_cmd = "cdparanoia -d %(rip_device)s -qw %(tracknr)d \"%(wavfilename)s\""
rip_ext = "wav"

#enc_cmd = "nice lame -b 128 -S %(wavfilename)s %(encfilename)s > /dev/null 2>&1"
# the following does not work with the Sansa & UTF-8 characters in titles
# (strange!!). Seems to be true for all non ABR 'preset' modes
#enc_cmd = "nice lame --preset medium -V 8 -S %(wavfilename)s %(encfilename)s > /dev/null 2>&1"

def tagFlacFile(file, trackNr, info):
    file = FLAC(file)
    file["album"]  = unicode(info['album'],'latin-1')
    file["artist"] = unicode(info['artist%d' % trackNr],'latin-1')
    file["title"]  = unicode(info["track%d" % trackNr],'latin-1')
    file["date"]   = unicode(info['year'],'latin-1')
    file["tracknumber"] = unicode("%02d" % (trackNr+1),'latin-1')
    file["tracktotal"]  = unicode("%02d" % (info['nrTracks']),'latin-1')
    file["comment"] = unicode("DiscID %s" % (info['discId']),'latin-1')
    try:
        file["genre"]  = unicode(info['genre'],'latin-1')
    except:
        file["genre"] = u""
    file.save()


def tagMp3File(file, trackNr, info):
    tag = eyeD3.Tag()
    tag.link(file)
    tag.setVersion(eyeD3.ID3_V2_4)
    tag.setTextEncoding(eyeD3.UTF_8_ENCODING)
    tag.setArtist(utf8.to_utf8(info['artist%d' % trackNr]))
    tag.setAlbum(utf8.to_utf8(info['album']))
    tag.setTitle(utf8.to_utf8(info["track%d" % trackNr]))
    tag.setTrackNum((trackNr+1, info['nrTracks']))
    try:
        tag.setGenre(utf8.to_utf8(info['genre']))
    except:
        tag.setGenre("")

    tag.setDate(utf8.to_utf8(info['year']))
    tag.addComment(info['discId'], "DiscID")
    tag.update( eyeD3.ID3_V2)
    #tag.update( eyeD3.ID3_V1_1)


encoder_config = (1, )
encoders = [
("nice lame --preset 128 -S \"%(wavfilename)s\" \"%(encfilename)s\" > /dev/null 2>&1", "mp3", tagMp3File ),
("nice flac -s --best -o \"%(encfilename)s\" \"%(wavfilename)s\"", "flac", tagFlacFile)
]
# "flac --best -o %o --tag=Artist=%{artist} --tag=Album=%{albumtitle} --tag=Date=%{year} --tag=Title=%{title} --tag=Tracknumber=%{number} --tag=Genre=%{genre} %f"

convertAlbumArt = "convert \"%(src)s\" \"%(dst)s\""
#############################################################################

# global setting: MUST MATCH AMAROK SETTINGS FOR DEVICE
## Amarok related options
amarokAlbumArt = "/home/chris/.kde/share/apps/amarok/albumcovers/large"
# ascii path only
asciiPath = 1
# vfat safe path
vfatSafePath = 1
# convert spaces
replaceSpacesPath = 0
# ignore "The" option of Amarok not implemented yet

# amarok device format
tagFormatAmarokDevice = "%A\\%a\\%n-%t.mp3"

#############################################################################

# host filesystem format
tagFormat = "%e/%A/%a/%n-%t.%e"

#############################################################################
tmpdir = '/tmp'
myPid = os.getpid()

tmpFilePrefix = "%s/tmp.%s" % (tmpdir, myPid)
tmpFileFormat = "%s.%%02d.%%s" % (tmpFilePrefix)

#############################################################################
# taken from the amarok source code
def cleanPath(s1):
    s = u"%s" % (s1);
 
    # accented vowels
    d = dict ([
                ( 'a', [ chr(0xe0),chr(0xe1),chr(0xe2),chr(0xe3),chr(0xe5)] ),
                ( 'A', [ chr(0xc0),chr(0xc1),chr(0xc2),chr(0xc3),chr(0xc5)] ),
                ( 'e', [ chr(0xe8),chr(0xe9),chr(0xea),chr(0xeb)] ),
                ( 'E', [ chr(0xc8),chr(0xc9),chr(0xca),chr(0xcb)] ),
                ( 'i', [ chr(0xec),chr(0xed),chr(0xee),chr(0xef)] ),
                ( 'I', [ chr(0xcc),chr(0xcd),chr(0xce),chr(0xcf)] ),
                ( 'o', [ chr(0xf2),chr(0xf3),chr(0xf4),chr(0xf5),chr(0xf8)] ),
                ( 'O', [ chr(0xd2),chr(0xd3),chr(0xd4),chr(0xd5),chr(0xd8)] ),
                ( 'u', [ chr(0xf9),chr(0xfa),chr(0xfb)] ),
                ( 'U', [ chr(0xd9),chr(0xda),chr(0xdb)] ) ])

    for k, v in d.iteritems():
        for  c in v:
            s = s.replace(unichr(ord(c)), k)

    # german umlauts
    s = s.replace(unichr(0x00e4),"ae")
    s = s.replace(unichr(0x00c4),"Ae")
    s = s.replace(unichr(0x00f6),"oe")
    s = s.replace(unichr(0x00d6),"Oe")
    s = s.replace(unichr(0x00fc),"ue")
    s = s.replace(unichr(0x00dc),"Ue")
    s = s.replace(unichr(0x00df),"ss")

    # some strange accents
    s = s.replace( unichr(0x00e7), "c" ).replace( unichr(0x00c7), "C" );
    s = s.replace( unichr(0x00fd), "y" ).replace( unichr(0x00dd), "Y" );
    s = s.replace( unichr(0x00f1), "n" ).replace( unichr(0x00d1), "N" );

    return s

def asciiPath(s):
    s2 = ""
    for i in xrange (0, len(s)):
        if ord(s[i])>128 or ord(s[i]) == 0:
            s2 += '_'
        else: 
            s2 += s[i]
    return s2

def vfatPath(s):
    s2 = ""
    for i in xrange (0, len(s)):
       # leave '/' and '\' out because path
       # is handled as a whole, not each segement individually
       # missing line below:  or  s[i] == '/' or  s[i] == '\\' 
        if ord(s[i])<0x20 or  \
               s[i] == '*' or s[i] == '?' or \
               s[i] == '<' or s[i] == '>' or \
               s[i] == '|' or s[i] == '"' or \
               s[i] == ':' or s[i] == '/' or  s[i] == '\\' : 
            s2 += '_'
        else: 
            s2 += s[i]

    if debug:
        print "%s => %s" % (s, s2)

    length = len(s2)
    if (length == 3) or ( (length > 3) and (s2[3] == '.' ) ):
        l = s2[:3].lower()
        if l == "aux" or l == "con" or l == "nul" or l == "prn":
            s2 = "_"+s2
        
    elif (length == 4) or ( (length > 4) and (s2[4] == '.' ) ):
        l = s[:3]
        d = s[3]
        if ( l == "com" or l == "lpt" ) and \
                ord(d) >= ord("0") and ord(d) <= ord("9") :
            s2 = "_" + s2

    # cut leading "."
    while s[0] == ".":
        s2 = s2[1:]
    
    # cut trailing "."
    while s2[-1] == ".":
        s2 = s2[:-1]

    # restrict to 255 characters
    s2 = s2[:255]

    # change possible trailing space to "_"
    if s2[-1] == " ":
        s2 = s2[:-1]+"_"

    return s2

def replaceSpaces(s):
    return s.replace(" ","_")

def formatFilename(f, tagFormat, enc_ext='mp3', joinChar='/'):

    #if not eyeD3.tag.isMp3File(f):
    #
    #    return None
    #
    #audioFile = eyeD3.tag.Mp3AudioFile(f);
    #tag = audioFile.getTag();
    #n1 = tag.tagToString(tagFormat) 

    artist = "Unknown"
    album = ""
    track = ""

    if type(f) in types.StringTypes:
        if debug:
            print "formatFilename: getting info from \"%s\"" % (f)
        info = getFileInfo(f)
        title = os.path.basename(f)
    else:
        if debug:
            print "formatFilename: gotten info : " , f
        info = f
        title = ""

    if info:
        if info['artist']:
            artist = info['artist']
            
        if info['album']:
            album = info['album']
            
        if info['track']:
            track = info['track']
            
        if info['title']:
            title = info['title']

    
    dirElements = tagFormat.split('/')
   
    name = ""
    for e in dirElements:
        n1 = e.replace("%A", artist )
        n1 = n1.replace("%a", album)
        n1 = n1.replace("%n", "%02d" % track)
        n1 = n1.replace("%t", title)
        n1 = n1.replace("%e", enc_ext)

        n1 = cleanPath(n1)

        if asciiPath:
            n1 = asciiPath(n1)

        if vfatSafePath:
            n1 = vfatPath(n1)
        
        if replaceSpacesPath:
            n1 = replaceSpaces(n1)
      
        if len(n1) > 0:
            if len(name) == 0:
                name = n1 
            else:
                name = name + joinChar + n1

    return name


def convertM3uToPla(fileIn, fileOut=None, tagFormat="%A/%a/%n-%t.%(ext)s"):
    fObjIn  = open( fileIn, "rU")

    if not fileOut:
        fileBase = os.path.splitext( os.path.basename(fileIn))
        fileOut = os.path.join(g_sansa_playlists,fileBase[0])+".pla"

    if debug:
        print "Converting m3u : \"%s\"" % fileIn
        print "        to pla : \"%s\"" % fileOut

    s = "PLP PLAYLIST\r\nVERSION 1.20\r\n\r\n"
    fileList = [] 
    for l in fObjIn.xreadlines():
        l = l.strip()
        if l[0] == '#':
            continue
        if len(l) == 0:
            continue
        if l[0] != "/":
            l = os.path.join(os.path.dirname(fileIn), l)
        filesysFile = os.path.abspath(l)
        deviceFile = formatFilename(filesysFile, tagFormat, '\\')
        s += "HARP, MUSIC\\"+deviceFile+"\r\n"
        fileList.append( (filesysFile, deviceFile.replace("\\","/") ) )

    #print s
    fObjOut = codecs.open( fileOut, "wt", "utf-16le")
    fObjOut.write(s)
    return fileList

def getCddbDiscInfo():
    
    cdrom = DiscID.open(rip_device)
    disc_id = None
    print "Waiting for disc ..."
    while not disc_id: 
        try:
            disc_id = DiscID.disc_id(cdrom)
        except:
            time.sleep(2)

    if debug:
        print "Disc ID: %08lx Num tracks: %d" % (disc_id[0], disc_id[1])

    info_local  = getCddbDiscInfoLocal(disc_id)
    info_remote = getCddbDiscInfoRemote(disc_id)

    return info_remote

def searchtree(fname, top = "."):
    """Walk the directory tree, starting from top. Credit to Noah Spurrier and Doug Fort."""
    import os, stat, types
    names = os.listdir(top)

    result = None
    for name in names:
        try:
            st = os.lstat(os.path.join(top, name))
        except os.error:
            continue
        if stat.S_ISREG(st.st_mode):
            if name== fname:
                result = os.path.join(top,fname)
                break
        if stat.S_ISDIR(st.st_mode):
            result = searchtree (fname, os.path.join(top, name))
            if (None != result):
                break
    return result


def getCddbDiscInfoLocal(disc_id, path="~/.cddb"):

    if debug:
        print "Querying local '%s' path for info on disc..." % (path)

    cddb_file =  searchtree("%08lx" %(disc_id[0]), os.path.expanduser(path))

    info = None
    if (None != cddb_file):
        if debug:
            print "Local file find at '%s'" %( cddb_file)
        info = {}
        info['type']       = "CD"
        info['discId']     = "%x" % disc_id[0]
        info['nrTracks']   = disc_id[1]

        info['discIdCddb'] = ''
        info['category']   = ''
        info['artist']   = info['discId']
        info['album']    = 'unknown'
        info['year']     = ""
        info['genre']    = ""
        for i in range(0, disc_id[1]):
            info ["artist%d" % i] = info['discId']
            info ["track%d" % i] = "Track %02d" % (i+1)

    return info

def getCddbDiscInfoRemote(disc_id):

    if debug:
        print "Querying CDDB for info on disc...",

    (query_stat, query_info) = CDDB.query(disc_id)

    disc_info = None
    track_info = None
    if query_stat == 210 or query_stat == 211:
        disc_info = query_info[0]
        #print "multiple matches found! "
        if debug:
            print "multiple matches found! Matches are:"
            for i in query_info:
                print "ID: %s Category: %s Title: %s" % \
                      (i['disc_id'], i['category'], i['title'])


    elif query_stat == 200:
        if debug:
            print ("success, found single disc entry!")
        disc_info = query_info

    else:
        if debug:
            print "failure getting disc info, status %i" % query_stat


    #print repr(disc_info['title'])
    #print cleanPath(unicode(disc_info['title'],ENCODING))

    info = {}
    info['type']       = "CD"
    info['discId']     = "%x" % disc_id[0]
    info['nrTracks']   = disc_id[1]

    if not disc_info:
        info['discIdCddb'] = ''
        info['category']   = ''
        info['artist']   = info['discId']
        info['album']    = 'unknown'
        info['year']     = ""
        info['genre']    = ""
        for i in range(0, disc_id[1]):
            info ["artist%d" % i] = info['discId']
            info ["track%d" % i] = "Track %02d" % (i+1)
        
    else:
        info['discIdCddb']  = disc_info['disc_id']
        info['category']    = disc_info['category']

        #m = re.match(u"(.*)\s+/(\s+(.*))?", disc_info['title'])
        #artist  = m.group(1)
        #try:
        #    album   = m.group(3)
        #except:
        #    album = "unknown"

        m = disc_info['title'].find("/")
        if m != -1:
            artist = disc_info['title'][:m].strip()
            album  = disc_info['title'][m+1:].strip()
        else:
            artist = disc_info['title'].strip()
            album  = "unknown"

        info['artist']   = artist
        info['album']    = album
        info['year']     = ""
        info['genre']    = ""

        if debug:
            print "USING ID: %s, Category: %s, Title: %s" % \
                     (info['discIdCddb'], info['category'], 
                      disc_info['title'])

        (track_stat, track_info) = CDDB.read(disc_info['category'], 
                                           disc_info['disc_id'])
        if track_stat == 210:
            if debug:
                print "success getting track info!"
            try:
                info['year'] = track_info['DYEAR']    
            except:
                pass
            try:
                info['genre'] = track_info['DGENRE']    
            except:
                pass

            for i in range(0, disc_id[1]):
                # update info structure and handle samplers where title
                # encode actual artist & title
                oTitle = track_info['TTITLE' + `i`]

                m = oTitle.find("/")
                if m != -1:
                    artist = oTitle[:m].strip()
                    title  = oTitle[m+1:].strip()
                else:
                    artist = info['artist']
                    title  = oTitle
                    
                info["artist%d" % i] = artist
                info["track%d" % i] = title
                if len(info["track%d" % i]) == 0:
                    info["track%d" % i] = "Track %02d" % (i+1)
        else:
            if debug:
                print "failure getting track info, status: %i" % track_stat

            for i in range(0, disc_id[1]):
                info ["artist%d" % i] = info['artist']
                info ["track%d" % i] = "Track %02d" % (i+1)
            track_info = None

    if debug:
        print info
        print ""

    return info

def getFileInfo(f):
    if not eyeD3.tag.isMp3File(f):
        return None

    audioFile = eyeD3.tag.Mp3AudioFile(f);
    tag = audioFile.getTag();
    
    info = {}
    info['type']        = "FILE"
    info['artist']      = tag.getArtist()
    info['album']       = tag.getAlbum()
    info['title']       = tag.getTitle()
    info['category']    = ""
    info['genre']       = tag.getGenre()
    info['year']        = tag.getYear()
    info['track'], info['nrTracks']    = tag.getTrackNum()
    if not info['track']:
        info['track'] = 0
        
    if not info['nrTracks']:
        info['nrTracks'] = 0
        
    # amarok style md5 hash, e.g. for encoding album cover name
    info['md5']  =  md5.new((info['artist']+info['album']).lower().encode(ENCODING)).hexdigest()

    if debug: 
        printInfo(info)

    return info

def printInfo(info):
    iType = info['type']
    print "Info Type         : %s" % iType
    if iType == "CD":
        print "DiskID (act/cddb) : %s/%s" % (info['discId'], info['discIdCddb'])
        print "Artist / Album    : %s / %s" % (
                  info['artist'], info['album'])
        print "Category / Genre  : %s / %s" % (info['category'], info['genre']) 
        print "Year              : %s " % info['year'] 
        print "Nr of Tracks      : %02d"  % info['nrTracks'] 
        for i in range(0, info['nrTracks']):
            if info['artist%d' % i] != info['artist']:
                print "Track %.02d: %s / %s" % (i+1, 
                        info['artist%d' % i], info['track%d' % i])
            else:
                print "Track %.02d: %s" % (i+1, info['track%d' % i])

    elif iType == "FILE":
        #print "DiskID (act/cddb) : %s/%s" % (info['discId'],info['discIdCddb'])
        print "Artist / Album    : %s / %s" % (
                   info['artist'],
                   info['album'])
        #print "Category / Genre  : %s / %s" % (
        #           info['category'],
        #           info['genre'] )
        print "Year              : %s " % info['year'] 
        print "Track Nr/Total    : %02d/%02d"  % (info['track'], info['nrTracks'] )
        print "Track Title       : %s" % info['title']
    else :
        print "Unknown info type"

    print

def rip(track, wavfilename):
    pid = os.fork()

    if pid != 0:
        return pid

    print "Start Rip: %02d" % (track+1)

    cmd = rip_cmd % {"rip_device": rip_device, "wavfilename": wavfilename, "tracknr" : track+1} 
    if no_action:
        print ( cmd )
    else:
        os.system( cmd )

    print "End   Rip: %02d" % (track+1)
    #sys.exit()
    os._exit(os.EX_OK)


def enc(track, format, info ):
    pid = os.fork()
    if pid != 0:
        return pid

    s = ""
    for i in encoder_config:
       s = s+ " %s" % (encoders[i][1]) 

    print "Start Enc: %02d%s" % (track+1, s)
    for i in encoder_config:
        in_file  = format % (track , rip_ext)
        out_file = format % (track , encoders[i][1])
        print "      Enc: %02d %s" % (track+1, encoders[i][1])
        cmd = encoders[i][0] % {"wavfilename": in_file, "encfilename" : out_file}
        if no_action:
            print cmd
        else:
            os.system(cmd )

    print "End   Enc: %02d" % (track+1)
    #sys.exit()
    os._exit(os.EX_OK)

def copyFile(src, dst):
   
    if debug or no_action:
        print "copying \"%s\" to \"%s\"" % ( src, dst)
                     
    if not no_action:
        dstdir =  os.path.dirname(dst)
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)

        shutil.copy(src, dst)

def moveFile(src, dst):
   
    if debug or no_action:
        print "moving \"%s\" to \"%s\"" % ( src, dst)
    
    if not no_action:
        dstdir =  os.path.dirname(dst)
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)

        shutil.move(src, dst)

def syncPlayList(playlist):
   
    # convert playlist and store directly on Sansa
    fileList = convertM3uToPla(playlist)
    if debug:
        for e in fileList:
            srcFile = e[0]
            dstFile = os.path.join(g_sansa_music,e[1])
        print fileList
    for e in fileList:
        srcFile = e[0]
        dstFile = os.path.join(g_sansa_music,e[1])
        if debug:
            print "Syncing \"%s\"" % srcFile
            print "     to \"%s\"" % dstFile
        if not os.path.exists(dstFile):
            if debug:
                print "        copy (dst not existent)"
            copyFile(srcFile,dstFile)
        dstDir =  os.path.dirname(dstFile)
        copyAlbumArt(dstDir)

def ripCd(info):
    """ 
    rips a whole CD according to 'info' data
    returns False if stopped with Ctrl-C, True otherwise
    """
    return_val = False

    rip_pid = None
    ripping_track = None
    enc_pid = None
    encoding_track = None

    try:
        tracks_pending = range(0, info['nrTracks'])
        encodes_pending = []

        while 1: 
            if len(tracks_pending) and  not rip_pid:
                t = tracks_pending.pop(0)
                rip_pid = rip(t, tmpFileFormat % (t, rip_ext))
                ripping_track = t
                       
            if len(encodes_pending) and  not enc_pid:
                e = encodes_pending.pop(0)
                enc_pid = enc(e, tmpFileFormat, info)
                encoding_track = e

            # if we're neither ripping nor encoding, we're done -> exit loop
            if not rip_pid and not enc_pid:
                break

            pid = os.wait()
           
            # we're in an encoding thread!
            if enc_pid and (enc_pid == pid[0]):
                # remove rip file
                #ripfile = tmpFileFormat % (encoding_track, rip_ext) 
                #os.remove(ripfile)

                # tag and move encoded file
                for i in encoder_config:
                    outfile = tmpFileFormat % (
                            encoding_track, 
                            encoders[i][1]) 

                    if no_action:
                        print "Tagging file : %s" % (outfile)
                    else:
                        encoders[i][2]( outfile , encoding_track, info)
                
                    # handle Sampler cases so that all songs are under
                    # <artist>/<album title> and <artist> is, e.g. "Various"
                    # otherwise all tracks would get split up.
                    # This seems a reasonable default for full CD ripping and
                    # can be changed with other tools later if needed

                    # create trackinfo 
                    trackInfo = { 
                        'artist': unicode(info['artist'],'latin-1'),
                        'album' : unicode(info['album'],'latin-1'),
                        'title' : unicode(info["track%d" % (encoding_track)],'latin-1'),
                        'track' : encoding_track+1
                        }

                    dstpath =  formatFilename(trackInfo, tagFormat, enc_ext=encoders[i][1])
                    moveFile(outfile, dstpath) 
                
                # mark as done encoding
                encoding_track = None
                enc_pid = None

            # here we are in an ripping thread!
            if rip_pid and (rip_pid == pid[0]):
                encodes_pending.append(ripping_track)
                ripping_track = None
                rip_pid = None

        os.system(eject_cmd % {"rip_device":rip_device})
        return_val = True        

    except KeyboardInterrupt:
        return_val = False
        #os.system(eject_cmd)
        pass
 
    return return_val


def ripCdContinous():
    try:
        # loop until Ctrl-C
        continueRip = True
        while continueRip:

            info = getCddbDiscInfo()
            printInfo(info)
            continueRip = ripCd(info)

    except KeyboardInterrupt:
        pass


def copyAlbumArt(dstPath):
    """ assume all mp3 files in one dir belong to the same artis/album """
    for root, dirs, files in os.walk(dstPath):
        if len(files) != 0:
            info = getFileInfo(os.path.join(root,files[0]))
            src = os.path.join(amarokAlbumArt,info['md5'])
            dst = os.path.join(root,"Album Art.jpg")
            if os.path.exists(src) and not os.path.exists(dst) :
                if debug:
                    print "Copy \"%s\" to  %s/%s"  % (
                        info['md5'],
                        info['artist'],
                        info['album'] )
                os.system(convertAlbumArt % {"src" : src, "dst": dst})


def renameMp3(srcPath, dstPath, format="%A/%a/%n-%t.mp3"):
    """ rename all mp3 file in srcPath according to given format to dstPath
        (recursivly)
    """
    for root, dirs, files in os.walk(srcPath):
        for f in files:
            srcfile = os.path.join(root, f)
            info = getFileInfo(srcfile)
            if info:
                dstfile = formatFilename(srcfile, format)
                if debug:
                    print "move \"%s\"" % srcfile
                    print "  to \"%s\"" % os.path.join(dstPath, dstfile)
                moveFile(srcfile, os.path.join(dstPath, dstfile))

def main():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-i", "--info", action="store_true", dest="info",
                        help="output info only, then exit (no ripping)")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                        help="switch on debugging output")
    parser.add_option("-n", "--noaction", action="store_true", dest="no_action",
                        help="switch off and system action (no actual ripping, just print commands)")

    parser.add_option("-p", "--playlist", nargs=2, dest="playlist",
                        help="convert m3u playlist to pla format")
    parser.add_option("-s", "--sync", dest="syncplaylist",
                        help="convert m3u playlist to pla format and sync files")
    parser.add_option("-r", "--rename", nargs=2, dest="rename",
                        help="rename and copy all file found in subtree according to tag format")
    parser.add_option("-a", "--albumart", dest="album_art",
                        help="copy amorok album art to given subdirectory tree (recursivly to each subdir)")
    parser.add_option("-f", "--file", dest="filename",
                        help="print MP3 file info, no ripping")

    (options, args) = parser.parse_args()
    global no_action, debug 
    debug = options.debug
    no_action = options.no_action

    #if len(args) != 1:
    #    parser.error("incorrect number of arguments")
    #if options.verbose:
    #    print "reading %s..." % options.filename

    if options.album_art:    
        copyAlbumArt(options.album_art)

    elif options.playlist:    
        fileList = convertM3uToPla(options.playlist[0], options.playlist[1])
        #print fileList

    elif options.syncplaylist:    
        fileList = syncPlayList(options.syncplaylist)
        print fileList


    elif options.rename:    
        renameMp3(options.rename[0], options.rename[1])

    elif options.filename:    
        info = getFileInfo(options.filename)
        printInfo(info)
        return

    elif options.info:
        info = getCddbDiscInfo()
        printInfo(info)

    else:        
        ripCdContinous() 


if __name__ == "__main__":

    print """
autorip.py %(version)s - the no-frills mp3 encoding front-end.
License: GPL
Author: chris at drexler-family dot com
Based on: http://autorip.sourceforge.net/
Modified: autorip\@elvenhome.net

Simple five-step usage guide:
	1. configure by editing %(progname)s
	2. run %(progname)s
	3. Drop audio CD into the CD-ROM tray.
	4. Do something else until autorip ejects your CD.
	5. Repeat steps 3-4 until CD supply is exhausted.

""" % {"version": version, "progname": sys.argv[0]}

    main()
    sys.exit()


#    fileIn  = sys.argv[1]
#    fileOut = sys.argv[2]
#
#    convertM3uToPla(fileIn, fileOut, tagFormatAmarokDevice)
