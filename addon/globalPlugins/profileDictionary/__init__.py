import addonHandler
import speechDictHandler
import globalPluginHandler
import api
import config
import gui
import wx
import os
from speechDictHandler import speechDictsPath

try:
	from globalCommands import SCRCAT_SPEECH
except:
	SCRCAT_SPEECH = None

addonHandler.initTranslation()

# Temp dictionary use taken from emoticons add-on
class ProfileDict(object):

	def __init__(self, name, dict=None, active=False):
		self.name = name
		self.speechDict = dict
		self._active = active
		self.path = os.path.join(profileDictsPath, name + ".dic")

	def isActive(self):
		return self._active

	def isSpeechDictLoaded(self):
		return self.speechDict is not None

	def loadSpeechDict(self):
		if not os.path.isfile(self.path):
			if not os.path.exists(profileDictsPath):
				os.makedirs(profileDictsPath)
			open(self.path, "a").close()
		self.speechDict = speechDictHandler.SpeechDict()
		self.speechDict.load(self.path)

	def addToTempDict(self):
		speechDictHandler.dictionaries["temp"].extend(self.speechDict)
		self._active = True

	def removeFromTempDict(self):
		tempDict = speechDictHandler.dictionaries["temp"]
		for e in self.speechDict: 
			if e in tempDict:
				tempDict.remove(e)
		self._active = False

	def removeSpeechDict(self):
		if os.path.isfile(self.path):
			os.remove(self.path)
			self.speechDict = None

	def rename(self, newName):
		newPath = os.path.join(profileDictsPath, newName + ".dic")
		active = self.isActive()
		if active:
			self.removeFromTempDict()
		if os.path.isfile(self.path):
			os.rename(self.path, newPath)
		self.name = newName
		self.path = newPath
		self.loadSpeechDict()
		if active:
			self.addToTempDict()


def decorator(originalFunc, funcAfter):
	def funcWrapper(*args, **kwargs):
		out = originalFunc(*args, **kwargs)
		funcAfter(*args, **kwargs)
		return out
	return funcWrapper

def onProfileSwitch():
	setActiveDicts()

def onDeleteProfile(conf, name):
	if not os.path.isfile(conf._getProfileFn(name)) and name in dicts:
		dicts[name].removeSpeechDict()
		del dicts[name]

def onRenameProfile(conf, oldName, newName):
	if newName.lower() != oldName.lower() and os.path.isfile(conf._getProfileFn(newName)):
		dicts[oldName].rename(newName)
		dicts[newName] = dicts.pop(oldName)

def addActions():
	config.post_configProfileSwitch.register(onProfileSwitch)
	config.ConfigManager.deleteProfile = decorator(config.ConfigManager.deleteProfile, onDeleteProfile)
	config.ConfigManager.renameProfile = decorator(config.ConfigManager.renameProfile, onRenameProfile)

def loadEmptyDicts():
	dictNames = []
	if os.path.exists(profileDictsPath):
		dictNames = [f[:-4] for f in os.listdir(profileDictsPath) if os.path.isfile(os.path.join(profileDictsPath, f)) and f.endswith(".dic")]
	return {n: ProfileDict(n) for n in dictNames if n != getProfileNameFromPath(config.conf.profiles[0])}

def getProfileNameFromPath(profile):
	return os.path.splitext(os.path.basename(profile.filename))[0]

def setActiveDicts():
	activeProfileNames = set([p.name for p in config.conf.profiles[1:]])
	profileDictNames = set([n for n in dicts])
	for d in dicts.values():
		if d.isActive():
			d.removeFromTempDict()
	activeDictNames = activeProfileNames.intersection(profileDictNames)
	for d in [dicts[n] for n in activeDictNames]:
		if not d.isSpeechDictLoaded():
			d.loadSpeechDict()
		d.addToTempDict()

if not api.globalVars.appArgs.secure:
	addActions()
	profileDictsPath = os.path.join(speechDictsPath, "profileDicts")
	dicts = loadEmptyDicts()
	setActiveDicts()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super(globalPluginHandler.GlobalPlugin, self).__init__()
		self.dictsMenu = gui.mainFrame.sysTrayIcon.preferencesMenu.GetMenuItems()[1].GetSubMenu()
		# Translators: The label for the menu item to open profile-specific speech dictionary dialog.
		self.profDictDialog = self.dictsMenu.Append(wx.ID_ANY, _("&Profile Dictionary..."), _("A dialog where you can set profile-specific dictionary entries"))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.script_editDict, self.profDictDialog)

	def script_editDict(self, gesture):
		if not api.globalVars.appArgs.secure:
			if len(config.conf.profiles) <= 1:
				wx.CallAfter(gui.messageBox, _("You can not add a profile dictionary to the NVDA normal configuration."), _("Invalid Operation"), wx.OK | wx.ICON_WARNING)
				return
			profileName = config.conf.profiles[-1].name
			profileDict = dicts[profileName] if profileName in dicts else None
			if profileDict is None:
				profileDict = ProfileDict(profileName)
				dicts[profileName] = profileDict
				profileDict.loadSpeechDict()
			else:
				profileDict.removeFromTempDict()
			gui.mainFrame._popupSettingsDialog(ProfileDictDialog, _("Profile dictionary for %s") % profileName, profileDict)
	script_editDict.category = SCRCAT_SPEECH
	script_editDict.__doc__ = _("Shows the dictionary dialog to insert entries valid only for the active profile.")

	__gestures = {
		"kb:NVDA+Shift+p": "editDict",
}


class ProfileDictDialog(gui.DictionaryDialog):

	def __init__(self, parent, title, profileDict):
		super(ProfileDictDialog, self).__init__(parent, title, profileDict.speechDict)
		self.profileDict = profileDict

	def onCancel(self, evt):
		super(ProfileDictDialog, self).onCancel(evt)
		self.profileDict.addToTempDict()

	def onOk(self, evt):
		super(ProfileDictDialog, self).onOk(evt)
		self.profileDict.addToTempDict()