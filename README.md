# RizomUV Bridge for Cinema4D

RizomUV VS bridge for Cinema4D. Extended version.

Setup:
	Unpack the plugin in ../Cinema4D/plugins/ directory or in C:/Users/[name]/AppData/Roaming/MAXON/Cinema 4D RXX/plugins/).
	Start Cinema4D and open Options window: Plugins > RizomUV-Bridge-for-Cinema4D-master > Options or Extensions > RizomUV-Bridge-for-Cinema4D-master > Options
	Specify the path to rizomuv.exe \ rizomUV.app

Config Directory

On Windows:
If you are updating the plugin, please, delete the settings.json file from C:\Users\"username"\AppData\Roaming\MAXON\Cinema 4D RXX_XXXXXXXX\prefs\RizomUV.

On MacOS:
If you are updating the plugin, please, delete the settings.json file from /Users/"username"/Library/Preferences/MAXON/Cinema 4D RXX_XXXXXXXX/prefs/RizomUV.

Usage:
When you click on the export icon, the model is exported and the RizomUV window opens.
When you hold the [Shift] button and click on the export icon the settings window will open.
Pressing [Ctrl-S] in RizomUV (or save icon) will return the object to Cinema4D.

Options:

	New UVW - Reset uv
	Auto Close - Automatically close RizomUV window after loading the model
	No materials - Materials will not be imported
	Keep History - Objects are not deleted after import but become hidden

Extended version:
Allows you to run scripts from Cinema4D. To create a script, just copy the commands (any commands after the ZomLoad function) from the Script Log Window to RizomUV. Also, the extended version allows you to convert and export the current selection of edges to RizomUV.

Added MacOS support, for now only tested on OSX Ventura 13.6.1 and Monterey 12.6.8
