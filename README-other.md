Walkthrough: Separating assets/ and workspace/
I've successfully separated the static assets from the dynamically generated course contents!

What was changed
Configuration Update: Added WORKSPACE_DIR pointing to the new workspace/ folder inside config/settingsSALLE.py.

Python Code Migration: Ran a script to cleanly update over 15 references to "assets" across your Python backend (server.py, data_parser.py, unidades_intro_parser.py, etc.). They now correctly point to workspace.

Folder Restructuring:

Created the new workspace/ folder.
Migrated all dynamic course folders (70801, 66710, etc.) and test folders out of assets/ into workspace/.
assets/ now cleanly holds only your static source (course-review) and logos.
Gitignore Update: Appended workspace/ to your .gitignore. Now, git will properly ignore all the heavy, temporary docx and html outputs, while keeping your assets/ safely tracked.