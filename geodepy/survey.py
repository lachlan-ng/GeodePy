#!/usr/bin/env python3

"""
Geoscience Australia - Python Geodesy Package
Survey Module
"""

import os
import numpy as np
from math import sqrt, degrees, radians, sin, cos, asin
from geodepy.convert import dd2dms, dms2dd


# Defines a bunch of classes required to
# convert GSI (or any other format) to DynaNet v3 Format


class AngleObs(object):
    def __init__(self, degree=0, minute=0, second=0):
        self.degree = abs(int(degree))
        self.minute = abs(int(minute))
        self.second = abs(round(float(second), 3))

    def __repr__(self):
        return repr(self.degree) + 'd '\
               + repr(self.minute) + '\' '\
               + repr(self.second) + '\"'

    def decimal(self):
        dd = abs(self.degree + self.minute / 60 + self.second / 3600)
        return dd if self.degree >= 0 else -dd

    def hp(self):
        hp = abs(self.degree + self.minute / 100 + self.second / 10000)
        return hp if self.degree >= 0 else -hp

    def __add__(self, other):
        degreeadd = self.degree + other.degree
        minuteadd = abs(self.minute) + abs(other.minute)
        secondadd = abs(self.second) + abs(other.second)
        while secondadd >= 60:
            minuteadd += 1
            secondadd -= 60
        while minuteadd >= 60:
            degreeadd += 1
            minuteadd -= 60
        return AngleObs(degreeadd, minuteadd, secondadd)

    def __sub__(self, other):
        degreesub = self.degree - other.degree
        minutesub = abs(self.minute) - abs(other.minute)
        secondsub = abs(self.second) - abs(other.second)
        while secondsub < 0:
            secondsub += 60
            minutesub -= 1
        while minutesub < 0:
            minutesub += 60
            degreesub -= 1
        return AngleObs(degreesub, minutesub, secondsub)

    def __truediv__(self, other):
        degreediv, degreerem = divmod(self.degree, other)
        minutediv, minuterem = divmod(self.minute, other)
        seconddiv, secondrem = divmod(self.second, other)
        minutediv = minutediv + ((degreerem / other) * 60)
        seconddiv = seconddiv + ((minuterem / other) * 60) + (secondrem / other)
        return AngleObs(degreediv, minutediv, seconddiv)


class Coordinate(object):
    def __init__(self, pt_id, system, hz_datum,
                 vert_datum, epoch, x=0.0, y=0.0, z=0.0):
        self.pt_id = pt_id
        self.system = system
        self.hz_datum = hz_datum
        self.vert_datum = vert_datum
        self.epoch = epoch
        self.x = x
        self.y = y
        self.z = z

    def __repr__(self):
        return ('{' + str(self.hz_datum) + ', '
                + str(self.x) + ', '
                + str(self.y) + ', '
                + str(self.z) + '}')


class InstSetup(object):
    def __init__(self, pt_id, coordinate, observation=None):
        self.pt_id = pt_id
        self.coordinate = coordinate
        if observation is None:
            self.observation = []
        else:
            self.observation = []
            self.observation.append(observation)

    def __repr__(self):
        return ('{InstSetup: ' + repr(self.pt_id)
                + ' ' + repr(self.coordinate)
                + '}\n Observations:\n'
                + repr(self.observation)) + '\n\n'

    def addobs(self, observation):
        return self.observation.append(observation)

    def __iter__(self):
        return self


class Observation(object):
    def __init__(self, from_id, to_id, inst_height=0.0, target_height=0.0,
                 face='FL', hz_obs=AngleObs(0, 0, 0), va_obs=AngleObs(0, 0, 0),
                 sd_obs=0.0, hz_dist=0.0, vert_dist=0.0):
        self.from_id = from_id
        self.to_id = to_id
        self.inst_height = inst_height
        self.target_height = target_height
        self.face = face
        self.hz_obs = hz_obs
        self.va_obs = va_obs
        self.sd_obs = sd_obs
        self.hz_dist = hz_dist
        self.vert_dist = vert_dist

    def __repr__(self):
        return ('{from: ' + repr(self.from_id)
                + 'to: ' + repr(self.to_id)
                + '; inst_height ' + repr(self.inst_height)
                + '; target_height ' + repr(self.target_height)
                + '; face ' + repr(self.face)
                + '; hz_obs ' + repr(self.hz_obs)
                + '; va_obs ' + repr(self.va_obs)
                + '; sd_obs ' + repr(self.sd_obs)
                + '}')


    def changeface(self):
        # Change Horizontal Angle
        if 0 <= self.hz_obs.degree < 180:
            hz_switch = self.hz_obs + AngleObs(180)
        elif 180 <= self.hz_obs.degree < 360:
            hz_switch = self.hz_obs - AngleObs(180)
        else:
            raise ValueError('Horizontal Angle out of range (0 to 360 degrees)')
        # Change Vertical Angle
        if 0 <= self.va_obs.degree < 360:
            va_switch = AngleObs(360) - self.va_obs
        else:
            raise ValueError('Vertical Angle out of range (0 to 360 degrees)')
        # Change Face Label
        if self.face == 'FL':
            newface = 'FR'
        elif self.face == 'FR':
            newface = 'FL'
        return Observation(self.from_id,
                           self.to_id,
                           self.inst_height,
                           self.target_height,
                           newface,
                           hz_switch,
                           va_switch,
                           self.sd_obs,
                           self.hz_obs,
                           self.vert_dist)


# Functions to read in data from fbk format (Geomax Zoom90 Theodolite used
# in Surat Survey

testfbk = '\\geodepy\\tests\\resources\\Site01-152.fbk'

terms = ['PRISM', 'STN', 'F1', 'F2']


def stripfile(filedata, listofterms):
    """
    Creates a list with lines starting with strings from a list
    :param filedata: File Data in list form
    :param listofterms: list of strings to use as search terms
    :return: list of file lines starting with strings from list of terms
    """
    datawithterms = []
    for line in filedata:
        if type(line) == str:
            for i in listofterms:
                if line.startswith(i):
                    datawithterms.append(line)
        elif type(line) == list:
            for i in listofterms:
                if line[0] == i:
                    datawithterms.append(line)
    return datawithterms


def addprismht(fbklist):
    prismlist = []
    rowto = []
    numlines = 0
    # Build array with prism height, startline and endline
    for num, line in enumerate(fbklist, 1):
        numlines += 1
        if line.startswith('PRISM'):
            prismlist.append([line[6:11], num])
    prismarray = np.asarray(prismlist)
    prismarrayrows = prismarray.shape[0]
    for num, row in enumerate(prismarray, 1):
        if num > prismarrayrows:
            break
        elif num == prismarrayrows:
            rowto.append(numlines)
        else:
            rowto.append(prismarray[num, 1])
    rowtoarray = np.asarray(rowto)
    prismrange = np.append(prismarray,
                           rowtoarray.reshape(rowtoarray.size, 1),
                           axis=1)
    # Add Prism Heights to each observation in file
    filecontents = [x.strip() for x in fbklist]
    for prism in prismrange:
        for i in range(int(prism[1]), int(prism[2])):
            if not (not filecontents[i].startswith('F1')
                    and not filecontents[i].startswith('F2')):
                filecontents[i] = filecontents[i] + ' ' + prism[0]
    filecontents = [x + '\n' for x in filecontents]
    return filecontents


def readfbk(filepath):
    with open(filepath) as f:
        # Remove non-obs data
        stage1 = stripfile(f, ['PRISM', 'NEZ', 'STN', 'F1', 'F2'])
        # Add prism heights to each observation
        stage2 = addprismht(stage1)
        # Remove Spaces from Obs Descriptions (inside "")
        def wscommstrip(string):
            string_list = list(string)
            commrange = [pos for pos, char in enumerate(string) if char == '\"']
            if len(commrange) != 2:
                return string
            else:
                for char in range(commrange[0] + 1, commrange[1]):
                    if string_list[char] == ' ':
                        string_list[char] = '_'
                string_us = ''.join(string_list)
                return string_us
        stage3 = []
        for line in stage2:
            stage3.append(wscommstrip(line))
        # Split obs
        stage4 = []
        for num, i in enumerate(stage3):
            stage4.append(stage3[num].split())
        # Add coordinates in file to stations
        coordlist = []
        for i in stage4:
            if i[0] == 'NEZ':
                coordlist.append(i)
        stage5 = stripfile(stage4, ['STN', 'F1', 'F2'])
        for coord in coordlist:
            for num, line in enumerate(stage4):
                if line[1] == coord[1]:
                   stage5[num] = line + coord[2:]
        # Group by Setup
        stn_index = [0]
        for num, i in enumerate(stage5, 1):
            # Create list of line numbers of station records
            # (Only stations have 'STN' string)
            if 'STN' in i:
                lnid = num
                stn_index.append(lnid)
        fbk_listbystation = []
        # Create lists of fbk data with station records as first element
        for i in range(0, (len(stn_index) - 1)):
            fbk_listbystation.append(stage5[(stn_index[i])
                                            - 1:(stn_index[i + 1])])
        del fbk_listbystation[0]
    return fbk_listbystation


def fbk2class(fbk_list):

    def parse_angle(obs_string):
        dms = float(obs_string)
        degmin, second = divmod(abs(dms) * 1000, 10)
        degree, minute = divmod(degmin, 100)
        return AngleObs(degree, minute, second * 10)

    project = []
    for setup_list in fbk_list:
        obs_list = []
        if setup_list[0][0] == 'STN' and len(setup_list[0]) <= 3:
            # This is the station information part
            from_id = setup_list[0][1]
            inst_height = setup_list[0][2]
            coord = Coordinate(from_id, 'utm', 'gda94', 'gda94',
                               '2018.1', 0, 0, 0)
            setup = InstSetup(from_id, coord)
        elif setup_list[0][0] == 'STN' and len(setup_list[0]) > 3:
            from_id = setup_list[0][1]
            inst_height = setup_list[0][2]
            east = float(setup_list[0][3])
            north = float(setup_list[0][4])
            elev = float(setup_list[0][5])
            coord = Coordinate(from_id, 'utm', 'gda94', 'gda94',
                               '2018.1', east, north, elev)
            setup = InstSetup(from_id, coord)
        for record in setup_list:
            if record[0] == 'F1' or record[0] == 'F2':
                """
                This is the obs information part
                from_id, to_id, inst_height, target_height
                face
                hz_obs
                va_obs
                sd_obs
                hz_dist
                vert_dist
                """
                # Read Face
                if int(float(record[5])) in range(0,180):
                    face = 'FL'
                elif int(float(record[5])) in range(180,360):
                    face = 'FR'
                else:
                    ValueError('Invalid Vertical Angle in ' + record)
                to_id = record[2]  # Read To ID
                hz_obs = parse_angle(record[3])  # 3 is Hz Ob (HP)
                sd_obs = record[4]
                va_obs = parse_angle(record[5])  # 5 is Vert Ob (HP)
                target_height = float(record[7])
                obs = Observation(from_id, to_id,
                                  inst_height, target_height,
                                  face, hz_obs, va_obs, sd_obs)
                obs_list.append(obs)
            # else:
            #     raise ValueError('Unexpected format found')
        for i in obs_list:
                setup.addobs(i)
    #         pt_id = parse_ptid(record[0])
    #         easting = parse_easting(record[0])
    #         northing = parse_northing(record[0])
    #         elev = parse_elev(record[0])
    #         coord = Coordinate(pt_id, 'utm', 'gda94', 'gda94',
    #                            '2018.1', easting, northing, elev)
    #         setup = InstSetup(pt_id, coord)
    #         for i in range(0, len(obs_list)):
    #             setup.addobs(obs_list[i])
        project.append(setup)
    return project


# Functions to read data to classes from Leica GSI format file (GA_Survey2.frt)


def readgsi(filepath):
    """
    Takes in a gsi file (GA_Survey2.frt) and returns a list
    of stations with their associated observations.
    :param filepath:
    :return:
    """
    # Check file extension, throw except if not .gsi
    ext = os.path.splitext(filepath)[-1].lower()
    try:
        if ext != '.gsi':
            raise ValueError
    except ValueError:
        print('ValueError: file must have .gsi extension')
        return
    # Read data from gsi file
    with open(filepath, 'r') as file:
        gsidata = file.readlines()
        stn_index = [0]
        for i in gsidata:
            # Create list of line numbers of station records
            # (Only stations have '84..' string)
            if '84..' in i:
                lnid = i[3:7]
                lnid = int(lnid.lstrip('0'))
                stn_index.append(lnid)
        gsi_listbystation = []
        # Create lists of gsi data with station records as first element
        for i in range(0, (len(stn_index) - 1)):
            gsi_listbystation.append(gsidata[(stn_index[i])
                                             - 1:(stn_index[i + 1])])
        del gsi_listbystation[0]
    return gsi_listbystation


def gsi2class(gsi_list):
    """
    Takes a list where first entry is station record and
    all remaining records are observations and creates
    a InstSetup Object with Observation Objects included.
    :param gsi_list:
    :return:
    """
    def readgsiword16(linestring, word_id):
        wordstart = str.find(linestring, word_id)
        word_val = linestring[(wordstart + 7):(wordstart + 23)]
        word_val = word_val.lstrip('0')
        if word_val == '':
            return 0
        else:
            return int(word_val)

    def parse_ptid(gsi_line):
        ptid = gsi_line[8:24]
        ptid = ptid.lstrip('0')
        return ptid

    def parse_easting(gsi_line):
        return (readgsiword16(gsi_line, '84..')) / 10000

    def parse_northing(gsi_line):
        return (readgsiword16(gsi_line, '85..')) / 10000

    def parse_elev(gsi_line):
        return (readgsiword16(gsi_line, '86..')) / 10000

    def parse_hz(gsi_line):
        dms = readgsiword16(gsi_line, '21.324') / 100000
        degmin, second = divmod(abs(dms) * 1000, 10)
        degree, minute = divmod(degmin, 100)
        return AngleObs(degree, minute, second * 10)

    def parse_slope(gsi_line):
        return (readgsiword16(gsi_line, '31..')) / 10000

    def parse_dist(gsi_line):
        return (readgsiword16(gsi_line, '32..')) / 10000

    def parse_tgtht(gsi_line):
        return (readgsiword16(gsi_line, '87..')) / 10000

    def parse_instht(gsi_line):
        return (readgsiword16(gsi_line, '88..')) / 10000

    def parse_vert(gsi_line):
        dms = readgsiword16(gsi_line, '22.324') / 100000
        degmin, seconds = divmod(abs(dms) * 1000, 10)
        degrees, minutes = divmod(degmin, 100)
        return AngleObs(degrees, minutes, seconds * 10)

    project = []
    for record in gsi_list:
        from_stn = parse_ptid(record[0])
        obs_list = []
        for line in record:
            if '31..' in line:
                to_stn = parse_ptid(line)
                hz = parse_hz(line)
                vert = parse_vert(line)
                slope = parse_slope(line)
                tgtht = parse_tgtht(line)
                instht = parse_instht(line)
                obs = Observation(from_stn, to_stn, instht, tgtht,
                                  'FL', hz, vert, slope)
                obs_list.append(obs)
        if '84..' in record[0]:
            pt_id = parse_ptid(record[0])
            easting = parse_easting(record[0])
            northing = parse_northing(record[0])
            elev = parse_elev(record[0])
            coord = Coordinate(pt_id, 'utm', 'gda94', 'gda94',
                               '2018.1', easting, northing, elev)
            setup = InstSetup(pt_id, coord)
            for i in range(0, len(obs_list)):
                setup.addobs(obs_list[i])
        project.append(setup)
    return project


def readgsiword16(linestring, word_id):
    wordstart = str.find(linestring, word_id)
    word_val = linestring[(wordstart + 7):(wordstart + 23)]
    word_val = 0.0 if word_val.lstrip('0') == '' else int(word_val.lstrip('0'))
    return word_val


# Functions to write out station and obs data to DNA format


def reducedataset(project):
    reducedproj = []
    # Change all obs to FL sense
    for setup in project:
        for num, obs in enumerate(setup.observation):
            if obs.face == 'FR':
                setup.observation[num] = obs.changeface()
    # todo sort out how to mean obs into new list and return to object
    return reducedproj

def anglerounds(setup):
    """

    :param setup:
    :return:
    """
    def meanhz(angle1, angle2):
        if angle1.degree < angle2.degree:
            return (angle1 + (angle2 - AngleObs(180))) / 2
        else:
            return (angle1 + (angle2 + AngleObs(180))) / 2

    # def meanva(angle1, angle2):
    #     "Broken - Need to incorporate new FL/FR from Class Attribute"
    #     if angle1.degree < 180:
    #         return (angle1 + (AngleObs(360) - angle2)) / 2
    #     else:
    #         return (angle2 + (AngleObs(360) - angle1)) / 2
    # # Build a round of FL/FR obs
    # start_round = setup.observation[0].to_id
    # ind = []
    # for c, ob in enumerate(setup.observation):
    #     if ob.to_id == start_round:
    #         ind.append(c)
    # roundofobs = setup.observation[ind[0]:ind[1] + 1]
    # # Test for Even Palindromic to_stn names
    # meanround = []
    # fl = 0
    # fr = -1
    # while len(roundofobs)/2 > fl + 1:
    #     meanhz = meanhz(roundofobs[fl].hz_obs, roundofobs[fr].hz_obs)
    #     meanva = meanva(roundofobs[fr].va_obs, roundofobs[fr].va_obs)
    #     meanob = Observation(roundofobs[fl].from_id,
    #                          roundofobs[fl].to_id,
    #                          roundofobs[fl].inst_height,
    #                          roundofobs[fl].target_height,
    #                          meanhz,
    #                          meanva,
    #                          roundofobs[fl].sd_obs,
    #                          roundofobs[fl].hz_dist,
    #                          roundofobs[fl].vert_dist)
    #     meanround.append(meanob)
    #     fl += 1
    #     fr -= 1
    # Create new list of meaned rounds of obs
    # For first and last in round
    #     mean_va = (FL_va + FR_hz) / 2 (tbd)
    #     mean_sd = (FL_sd + FL_sd) / 2
    #     Observation(All same + mean_hz, mean_va, mean_sd)
    #     Add above to list of meaned rounds of obs
    #     Remove first and last in round
    # Repeat until all obs in round meaned
    # Repeat above until all rounds meaned
    # Return new list of meaned obs per round (no non-round obs included)
    pass


def anglepairs(allobsfromInstSetup):
    # For first to_stn
        # Find next occurrence of to_stn
        # Check (FL_hz ~= (FR_hz +- 180)
    # Create new list of meaned rounds of obs
    # For FL/FR pair of obs
    def meanhz(angle1, angle2):
        if angle1.degree < angle2.degree:
            return (angle1 + (angle2 - AngleObs(180))) / 2
        else:
            return (angle1 + (angle2 + AngleObs(180))) / 2

    def meanva(angle1, angle2):
        if angle1.degree < 180:
            return (angle1 + (AngleObs(360) - angle2)) / 2
        else:
            return (angle2 + (AngleObs(360) - angle1)) / 2
        # mean_sd = (FL_sd + FL_sd) / 2
        # Observation(All same + mean_hz, mean_va, mean_sd)
        # Remove pair from list
    # Repeat until all pairs of obs in round meaned
    # Return new list of meaned pairs of obs (no single-face obs included)
    pass


def dnaout_dirset(allobsfromInstSetup):
    # Find index of next obs with same to_stn (defines direction set)
    # If no next, include all obs
    # Set default std_dev
    # For obs in unique list
        # First line is first obs
        # For remaining obs
            # Include to_stn and direction
    pass


def dnaout_sd(observation):
    return ('S '
            + observation.from_id.ljust(20)
            + observation.to_id.ljust(20)
            + ''.ljust(20)
            + str(observation.sd_obs).ljust(14)  # 76
            + ''.ljust(14)
            + '0.0010'.ljust(9)         # add standard deviation
            + str(1.7960).ljust(7)      # add intrument height
            + str(observation.target_height).ljust(7))


def dnaout_va(observation):
    return ('V '
            + observation.from_id.ljust(20)
            + observation.to_id.ljust(20)
            + ''.ljust(34)
            + str(observation.va_obs.degree).rjust(3)
            + ' '
            + str('%02d' % observation.va_obs.minute)
            + ' '
            + str(observation.va_obs.second).ljust(8)
            + '1.0000'.ljust(9)         # add standard deviation
            + str(1.7960).ljust(7)      # add intrument height
            + str(observation.target_height).ljust(7))


def va_conv(verta_hp, slope_dist, height_inst=0, height_tgt=0):
    """
    Function to convert vertical angles (zenith distances) and slope distances
    into horizontal distances and changes in height. Instrument and Target
    heights can be entered to allow computation of zenith and slope distances
    between ground points.

    :param verta_hp:        Vertical Angle from Instrument to Target, expressed
                            in HP Format (DDD.MMSSSSSS)
    :param slope_dist:      Slope Distance from Instrument to Target in metres
    :param height_inst:     Height of Instrument. Optional - Default Value of 0m
    :param height_tgt:      Height of Target. Optional - Default Value of 0m

    :return: verta_pt_hp:   Vertical Angle between Ground Points, expressed
                            in HP Format (DDD.MMSSSSSS)
    :return: slope_dist_pt: Slope Distance between Ground Points in metres
    :return: hz_dist:       Horizontal Distance
    :return: delta_ht:      Change in height between Ground Points in metres
    """
    # Convert Zenith Angle to Vertical Angle
    try:
        if verta_hp == 0 or verta_hp == 180:
            raise ValueError
        elif 0 < verta_hp < 180:
            verta = radians(90 - dms2dd(verta_hp))
        elif 180 < verta_hp < 360:
            verta = radians(270 - dms2dd(verta_hp))
        else:
            raise ValueError
    except ValueError:
        print('ValueError: Vertical Angle Invalid')
        return
    # Calculate Horizontal Dist and Delta Height
    hz_dist = slope_dist * cos(verta)
    delta_ht = slope_dist * sin(verta)
    # Account for Target and Instrument Heights
    if height_inst == 0 and height_tgt == 0:
        verta_pt_hp = verta_hp
        slope_dist_pt = slope_dist
    else:
        delta_ht = height_inst + delta_ht - height_tgt
        slope_dist_pt = sqrt(delta_ht ** 2 + hz_dist ** 2)
        verta_pt = asin(delta_ht / slope_dist)
        verta_pt_hp = dd2dms(degrees(verta_pt) + 90)
    return verta_pt_hp, slope_dist_pt, hz_dist, delta_ht


"""
to_stn = ['GA03', 'GA02', 'SYM2', 'ATWR', 'MAHON', 'MAHON', 'ATWR', 'SYM2', 'GA02', 'GA03']
flfr = [359.59597, 14.48289, 25.35515, 215.57043, 300.59046, 120.59060, 35.57045, 205.35530, 194.48282, 179.59581]
flfr_vert = [90.30228, 90.09547, 89.50396, 88.03600, 87.58014, 272.01587, 271.55593, 270.09227, 269.50091, 269.29414]
"""


def hz_round(brg_list):
    """
    Input: an even palindromic list of horizontal angle observations in two faces
    (e.g. [fl1, fl2, fl3, fr3, fr2, fr1])
    Output: an averaged face-left sense list of horizontal angles.
    """
    brg_avg = []
    obs = int((len(brg_list))/2)
    for i in range(0, obs):
        hz_avg = (dms2dd(brg_list[i]) + (dms2dd(brg_list[-(i+1)])-180))/2
        brg_avg.append(round(dd2dms(hz_avg), 7))
    return brg_avg


def va_round(va_list):
    """
    Input: an even palindromic list of vertical angle observations in two faces
    (e.g. [fl1, fl2, fl3, fr3, fr2, fr1])
    Output: an averaged face-left sense list of vertical angles.
    """
    va_avg = []
    obs = int((len(va_list))/2)
    for i in range(0, obs):
        fl_ang = dms2dd(va_list[i]) - 90
        fr_ang = 270 - dms2dd(va_list[-(i+1)])
        ang_avg = (fl_ang + fr_ang)/2 + 90
        va_avg.append(round(dd2dms(ang_avg), 7))
    return va_avg


"""
# Test for round of obs
if to_stn == to_stn[::-1] and len(to_stn) % 2 == 0:
    brg_avg = hz_round(flfr)
    va_avg = va_round(flfr_vert)
    to_stn_avg = to_stn[0:int(len(to_stn)/2)]
else:
    brg_avg = ['nope']
"""
