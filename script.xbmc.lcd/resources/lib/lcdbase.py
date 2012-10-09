'''
    XBMC LCDproc addon
    Copyright (C) 2012 Team XBMC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import platform
import xbmc
import xbmcgui
import sys
import os
import re
import telnetlib
import time

from xml.etree import ElementTree as xmltree
from array import array

__scriptname__ = sys.modules[ "__main__" ].__scriptname__
__settings__ = sys.modules[ "__main__" ].__settings__
__cwd__ = sys.modules[ "__main__" ].__cwd__
__icon__ = sys.modules[ "__main__" ].__icon__
__lcdxml__ = xbmc.translatePath( os.path.join("special://masterprofile","LCD.xml"))

from settings import *
 
# global functions
def log(loglevel, msg):
  xbmc.log("### [%s] - %s" % (__scriptname__,msg,),level=loglevel ) 

# enumerations
class DISABLE_ON_PLAY:
  DISABLE_ON_PLAY_NONE = 0
  DISABLE_ON_PLAY_VIDEO = 1
  DISABLE_ON_PLAY_MUSIC = 2
  
class LCD_MODE:
  LCD_MODE_GENERAL     = 0
  LCD_MODE_MUSIC       = 1
  LCD_MODE_VIDEO       = 2
  LCD_MODE_NAVIGATION  = 3
  LCD_MODE_SCREENSAVER = 4
  LCD_MODE_XBE_LAUNCH  = 5
  LCD_MODE_MAX         = 6

class CUSTOM_CHARSET:
  CUSTOM_CHARSET_DEFAULT      = 0
  CUSTOM_CHARSET_SMALLCHAR    = 1
  CUSTOM_CHARSET_MEDIUMCHAR   = 2
  CUSTOM_CHARSET_BIGCHAR      = 3
  CUSTOM_CHARSET_MAX          = 4

class LcdBase():
  def __init__(self):
    self.m_disableOnPlay = DISABLE_ON_PLAY.DISABLE_ON_PLAY_NONE
    self.m_eCurrentCharset = CUSTOM_CHARSET.CUSTOM_CHARSET_DEFAULT
    self.m_lcdMode = [None] * LCD_MODE.LCD_MODE_MAX
    self.m_bDimmedOnPlayback = False
    self.m_strInfoLabelEncoding = sys.getfilesystemencoding()
    self.m_strLCDEncoding = "iso-8859-1"

    log(xbmc.LOGDEBUG, "Determined InfoLabelEncoding: " + self.m_strInfoLabelEncoding)

#  @abstractmethod
  def _concrete_method(self):
      pass
#  @abstractmethod
  def Stop(self):
    pass

#  @abstractmethod
  def Suspend(self):
    pass

#  @abstractmethod   
  def Resume(self):
    pass

#  @abstractmethod   
  def SetBackLight(self, iLight):
    pass

#  @abstractmethod  
  def SetContrast(self, iContrast):
    pass

#  @abstractmethod     
  def SetLine(self, iLine, strLine):
    pass
    
#  @abstractmethod	
  def GetColumns(self):
    pass

#  @abstractmethod
  def GetRows(self):
    pass

#  @abstractmethod
  def SetProgressBar(self, percent, lineIdx):
    pass

  def GetProgressBarPercent(self, tCurrent, tTotal):
    return float(tCurrent)/float(tTotal)

  def SetCharset(self,_nCharset):
    if _nCharset < CUSTOM_CHARSET.CUSTOM_CHARSET_MAX:
      self.m_eCurrentCharset = _nCharset

  def Initialize(self):
    self.m_eCurrentCharset = CUSTOM_CHARSET.CUSTOM_CHARSET_DEFAULT
    self.m_disableOnPlay = DISABLE_ON_PLAY.DISABLE_ON_PLAY_NONE
    self.LoadSkin(__lcdxml__)

    # Big number blocks, used for screensaver clock
    # Note, the big block isn't here, it's in the LCD's ROM

  def IsConnected(self):
    return True


  def LoadSkin(self, xmlFile):
    self.Reset()
    doc = xmltree.parse(xmlFile)
    for element in doc.getiterator():
      #PARSE LCD infos
      if element.tag == "lcd":
        # load our settings  
        disableOnPlay = element.find("disableonplay") 
        if disableOnPlay != None:
          self.m_disableOnPlay = DISABLE_ON_PLAY.DISABLE_ON_PLAY_NONE
          if str(disableOnPlay.text).find("video") >= 0:
            self.m_disableOnPlay += DISABLE_ON_PLAY.DISABLE_ON_PLAY_VIDEO
          if str(disableOnPlay.text).find("music") >= 0:
            self.m_disableOnPlay += DISABLE_ON_PLAY.DISABLE_ON_PLAY_MUSIC
        #load moads
        tmpMode = element.find("music")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_MUSIC)

        tmpMode = element.find("video")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_VIDEO)

        tmpMode = element.find("general")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_GENERAL)

        tmpMode = element.find("navigation")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_NAVIGATION)
    
        tmpMode = element.find("screensaver")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_SCREENSAVER)

        tmpMode = element.find("xbelaunch")
        self.LoadMode(tmpMode, LCD_MODE.LCD_MODE_XBE_LAUNCH)


  def LoadMode(self, node, mode):
    if node == None:
      return
    for line in node.findall("line"):
      self.m_lcdMode[mode].append(str(line.text))

  def Reset(self):
    self.m_disableOnPlay = DISABLE_ON_PLAY.DISABLE_ON_PLAY_NONE
    for i in range(0,LCD_MODE.LCD_MODE_MAX):
      self.m_lcdMode[i] = []			#clear list

  def timeToSecs(self, timeAr):
    arLen = len(timeAr)
    if arLen == 1:
      currentSecs = int(timeAr[0])
    elif arLen == 2:
      currentSecs = int(timeAr[0]) * 60 + int(timeAr[1])
    elif arLen == 3:
      currentSecs = int(timeAr[0]) * 60 * 60 + int(timeAr[1]) * 60 + int(timeAr[2])
    return currentSecs

  def getCurrentTimeSecs(self):
    currentTimeAr = xbmc.getInfoLabel("Player.Time").split(":")
    return self.timeToSecs(currentTimeAr)
 
  def getCurrentDurationSecs(self):
    currentDurationAr = xbmc.getInfoLabel("Player.Duration").split(":")
    return self.timeToSecs(currentDurationAr)

  def Render(self, mode, bForce):
    outLine = 0
    inLine = 0

    while (outLine < int(self.GetRows()) and inLine < len(self.m_lcdMode[mode])):
      #parse the progressbar infolabel by ourselfs!
      if self.m_lcdMode[mode][inLine] == "$INFO[LCD.ProgressBar]":
        # get playtime and duration and convert into seconds
        currentSecs = self.getCurrentTimeSecs()
        durationSecs = self.getCurrentDurationSecs()
        percent = self.GetProgressBarPercent(currentSecs,durationSecs)
        pixelsWidth = self.SetProgressBar(percent, outLine)
        line = "p" + str(pixelsWidth)
      else:
        line = xbmc.getInfoLabel(self.m_lcdMode[mode][inLine])
        if self.m_strInfoLabelEncoding != self.m_strLCDEncoding:
          line = line.decode(self.m_strInfoLabelEncoding).encode(self.m_strLCDEncoding, "replace")
        self.SetProgressBar(0, -1)

      inLine += 1
      if len(line) > 0:
#        log(xbmc.LOGDEBUG, "Request write of line" + str(outLine) + ": " + str(line))
        self.SetLine(outLine, line, bForce)
        outLine += 1

    # fill remainder with empty space
    while outLine < int(self.GetRows()):
#      log(xbmc.LOGDEBUG, "Request write of emptyline" + str(outLine))
      self.SetLine(outLine, "", bForce)
      outLine += 1

  def DisableOnPlayback(self, playingVideo, playingAudio):
    if (playingVideo and (self.m_disableOnPlay & DISABLE_ON_PLAY.DISABLE_ON_PLAY_VIDEO)) or (playingAudio and (self.m_disableOnPlay & DISABLE_ON_PLAY.DISABLE_ON_PLAY_MUSIC)):
      if not self.m_bDimmedOnPlayback:
        self.SetBackLight(0)
        self.m_bDimmedOnPlayback = True
    elif self.m_bDimmedOnPlayback:
      self.SetBackLight(1)
      self.m_bDimmedOnPlayback = False
